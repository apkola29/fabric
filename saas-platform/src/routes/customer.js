import { QUICK_EXAMPLES, describeVisual } from '../crm/insights.js';
import { fieldCatalog, rolesFor } from '../crm/model.js';
import { TERRITORIES } from '../crm/workload.js';
import { isLoopbackHost } from '../config.js';
import { clientAddress } from '../http/limits.js';
import { HttpError, readBody, readJson, sendJson } from '../http/router.js';
import { brandOf, logoUrl, sendLogo, themeOf } from '../platform/branding.js';
import { MAX_UPLOAD_BYTES, importFromWeb, ingestBytes, refreshAgentAfterLoad, syncAppData } from '../platform/ingest.js';
import { entitlements } from '../platform/plans.js';
import { createEmbedConfig, isStandardReport, listReporting } from '../platform/reporting.js';
import { emailDomain } from '../platform/sessions.js';
import { addActivity } from '../platform/store.js';
import { customerUrl, platformUrl } from '../platform/tenancy.js';
import { recordUsage, usageEntry } from '../platform/usage.js';
import { ROLES, accessOf, findUser, normalizeEmail, rejectSlowly, reportRightsOf, usersOf, verifyPassword } from '../platform/users.js';
import { decodeHeader } from './admin.js';

// A request from this computer: IPv4 loopback, IPv6 loopback, or IPv4 loopback written as IPv6.
const isLoopbackAddress = (address) => /^(127\.|::1$|::ffff:127\.)/.test(String(address || ''));

// The end customer's app. The tenant always comes from the session, never from the request, and responses use the
// product's language: accounts, deals, reports and questions. No workspaces, editions or Fabric item names reach the
// browser. Fabric calls run as the customer's own service account.
//
// With APP_DOMAIN, each customer has its own address (see platform/tenancy.js): it signs in only that customer's
// people, and a session is only accepted at its own customer's address.
//
// Within a customer, each person's territories limit what they see: CRM queries are scoped in SQL, embed tokens carry
// the person's row-level security roles, and the assistant answers from scoped SQL. Data integration is for managers.

const BUSY = new Set(['pending', 'provisioning', 'deprovisioning']);
const APP_TABLES = { crm_accounts: 'Accounts', crm_opportunities: 'Opportunities', crm_activities: 'Activities' };

export function datasetName(table, tenant) {
  if (tenant?.datasetNames?.[table]) return tenant.datasetNames[table];
  if (APP_TABLES[table]) return APP_TABLES[table];
  const words = table.replace(/^gold_/, '').replace(/_/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function datasetSource(table, lastLoad, productName) {
  if (table.startsWith('crm_')) return productName;
  if (lastLoad?.source === 'File upload' || lastLoad?.source === 'upload') return 'File upload';
  const web = /^web \((.+)\)$/.exec(lastLoad?.source || '');
  if (web) return `Web: ${web[1]}`;
  if (table.startsWith('gold_')) return 'Calculated';
  return 'Other';
}

// What this customer can use right now: their entitlements, intersected with what has actually been set up.
// Once a customer has been ready, later runs (upgrades, edition changes, retries) keep serving what already works:
// the app doesn't switch to "setting up", and a failed step doesn't hide the CRM or reports that exist.
export function customerAccess(tenant, provisioner) {
  const { features } = entitlements(tenant);
  const fabricState = tenant.fabric || {};
  const established = Boolean(tenant.provisionedAt && fabricState.workspaceId);
  let status = 'ready';
  if (tenant.status === 'deprovisioning') status = 'unavailable';
  else if (!established && (BUSY.has(tenant.status) || provisioner.isBusy(tenant.id))) status = 'setting-up';
  else if (!established && tenant.steps?.workspace?.status !== 'done') status = 'unavailable';
  const ready = status === 'ready';
  const crm = ready && Boolean(features.crm) && Boolean(fabricState.crmSchemaVersion || tenant.steps?.['crm-schema']?.status === 'done');
  const reports = ready && Boolean(features.reports) && Boolean(fabricState.semanticModelId);
  return {
    status,
    features: {
      crm,
      reports,
      authoring: reports && Boolean(features.authoring),
      ask: crm && Boolean(features.agent),
      data: ready && Boolean(features.ingestion) && Boolean(fabricState.lakehouseId),
    },
  };
}

async function mapLimit(items, limit, fn) {
  const results = new Array(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const index = next++;
      results[index] = await fn(items[index]);
    }
  });
  await Promise.all(workers);
  return results;
}

export function registerCustomerRoutes(router, { config, fabric, store, sessions, provisioner, identities, crm, assistant, fetchOptions, limiter = null }) {
  // Per-customer and per-user budgets for the expensive calls, so one busy customer can't slow down the others.
  const limits = config.limits || {};
  const limit = (...rules) => limiter?.enforce(rules.map(([name, key]) => ({ key: `${name}|${key}`, limit: limits[name] })));
  const userKey = ({ tenant, session }) => `${tenant.id}|${session.email}`;

  function current(req) {
    const site = req.site || { kind: 'single' };
    // The platform's own address hosts no customer sessions, and an address no customer has has none either.
    if (site.kind === 'apex' || site.kind === 'unknown') throw new HttpError(401, 'Please sign in.');
    const session = sessions.read(req.headers.cookie);
    if (!session) throw new HttpError(401, 'Please sign in.');
    // A session only works at its own customer's address. Browsers already keep cookies per address; this also
    // covers a cookie copied or planted from another customer's address.
    if (site.kind === 'customer' && session.tenantId !== site.tenant.id) throw new HttpError(401, 'Please sign in.');
    const tenant = store.get(session.tenantId);
    // The email's domain must still belong to the customer named in the session, so removing a domain (or moving
    // it to another customer) ends existing sessions straight away instead of when the cookie expires.
    if (!tenant || !(tenant.domains || []).includes(emailDomain(session.email))) throw new HttpError(401, 'Your session has ended. Please sign in again.');
    // Customers with named sign-ins: the person must still exist and their password must not have been reset since.
    // A session from the demo sign-in ends as soon as a customer gets named sign-ins.
    let user = null;
    if (usersOf(tenant).length) {
      user = findUser(tenant, session.email);
      if (!user || user.sessionVersion !== session.sv) throw new HttpError(401, 'Your session has ended. Please sign in again.');
    } else if (session.sv) {
      throw new HttpError(401, 'Your session has ended. Please sign in again.');
    }
    const access = accessOf(user);
    const context = customerAccess(tenant, provisioner);
    // Loading data and connecting sources change what everyone sees, so they're for managers only.
    if (access.role !== 'manager') context.features.data = false;
    // Building and editing reports is the next phase: until REPORT_AUTHORING is on, the standard reports, view only.
    if (!config.reportAuthoring) context.features.authoring = false;
    // Within an edition that has authoring, editing and creating are granted per person (users.js).
    const rights = reportRightsOf(user);
    const reportPermissions = { view: context.features.reports, edit: context.features.authoring && rights.edit, create: context.features.authoring && rights.create };
    return { session, tenant, user, access, reportPermissions, ...context };
  }

  function need(context, feature) {
    if (context.status === 'setting-up') throw new HttpError(409, "We're still getting this ready. Please try again in a few minutes.");
    if (!context.features[feature]) throw new HttpError(403, "This isn't available for your account.");
    return context;
  }

  // `right`: 'edit', 'create', or 'author' for either. The edition decides first, then the person's permissions.
  function needReportRight(context, right) {
    need(context, 'authoring');
    const { edit, create } = context.reportPermissions;
    if (right === 'author' ? !(edit || create) : !context.reportPermissions[right]) {
      throw new HttpError(403, `You don't have permission to ${right === 'create' ? 'create' : 'edit'} reports. Ask your administrator.`);
    }
    return context;
  }

  // The customer sees a plain message; the platform team sees the cause in the back office.
  async function friendly(tenant, email, what, error) {
    if (error instanceof HttpError) throw error;
    if (error?.status === 400 || error?.status === 403 || error?.status === 404 || error?.status === 409) throw new HttpError(error.status, error.message);
    addActivity(tenant, `${what} failed for ${email}: ${error?.message || error}`, 'error');
    await store.save(tenant).catch(() => {});
    throw new HttpError(503, "Something went wrong on our side. We've let our team know.");
  }

  // Runs a CRM repository call for the signed-in customer.
  function crmRoute(method, pattern, status, handler) {
    const writes = method === 'post' || method === 'patch';
    router[method](pattern, async ({ req, res, url, params }) => {
      const context = need(current(req), 'crm');
      if (writes) limit(['crmWritePerTenant', context.tenant.id]);
      const body = writes ? await readJson(req) : null;
      let result;
      try {
        const repo = (await crm.forTenant(context.tenant)).scoped(context.access.territories);
        result = await handler(repo, { body, params, query: Object.fromEntries(url.searchParams) });
      } catch (error) {
        await friendly(context.tenant, context.session.email, 'A CRM request', error);
      }
      if (result === null || result === undefined) throw new HttpError(404, 'Not found.');
      sendJson(res, status, result);
    });
  }

  router.get('/api/product', ({ res }) => sendJson(res, 200, { product: config.productName }));

  // Which company this address belongs to, with its name and logo, before anyone signs in. Without APP_DOMAIN, the
  // signed-in person's company (nothing before sign-in).
  function siteTenant(req) {
    const site = req.site || { kind: 'single' };
    if (site.kind === 'customer') return site.tenant;
    if (site.kind !== 'single') return null;
    try {
      return current(req).tenant;
    } catch {
      return null;
    }
  }

  router.get('/api/site', ({ req, res }) => {
    const site = req.site || { kind: 'single' };
    if (site.kind === 'unknown') throw new HttpError(404, "There's no company at this address.");
    const tenant = siteTenant(req);
    const brand = tenant ? brandOf(tenant) : null;
    sendJson(res, 200, {
      product: config.productName,
      // customer: a company's own address; platform: "find your company"; shared: one address for everyone.
      mode: site.kind === 'customer' ? 'customer' : site.kind === 'apex' ? 'platform' : 'shared',
      company: tenant?.name || null,
      logoUrl: tenant ? logoUrl(tenant, '/api/site/logo') : null,
      theme: brand ? themeOf(brand.color) : null,
      platformUrl: site.kind === 'customer' ? platformUrl(config) : null,
    });
  });

  router.get('/api/site/logo', ({ req, res }) => {
    if (!sendLogo(res, siteTenant(req))) throw new HttpError(404, 'No logo.');
  });

  router.post('/api/session', async ({ req, res }) => {
    limit(['signInPerIp', clientAddress(req, config)]);
    const { email, password } = await readJson(req, 8192);
    const domain = emailDomain(email);
    if (!domain) throw new HttpError(400, 'Enter your work email address.');
    limit(['signInPerDomain', domain]);
    const address = normalizeEmail(email);
    const site = req.site || { kind: 'single' };
    if (site.kind === 'unknown') throw new HttpError(404, "There's no company at this address.");
    const owner = store.list().find((t) => (t.domains || []).includes(domain));
    if (site.kind === 'apex') {
      // Find your company: nothing is signed in here; the person continues at their company's own address.
      if (!owner) throw new HttpError(401, "We couldn't find an account for that email address.");
      sendJson(res, 200, { signedIn: false, url: customerUrl(config, owner) });
      return;
    }
    // At a company's own address, people from any other company get the same answer as someone unknown.
    const tenant = site.kind === 'customer' ? (owner?.id === site.tenant.id ? owner : null) : owner;
    if (site.kind === 'customer' && !tenant && usersOf(site.tenant).length) {
      limit(['signInPerAccount', address]);
      await rejectSlowly(password);
      throw new HttpError(401, 'That email and password don\'t match.');
    }
    if (tenant && usersOf(tenant).length) {
      // Named sign-ins: the same answer for an unknown person and a wrong password.
      limit(['signInPerAccount', address]);
      const user = findUser(tenant, address);
      const valid = user ? await verifyPassword(String(password || ''), user.passwordHash) : await rejectSlowly(password);
      if (!valid) throw new HttpError(401, 'That email and password don\'t match.');
      user.lastSignInAt = new Date().toISOString();
      await store.save(tenant);
      res.setHeader('set-cookie', sessions.issue({ tenantId: tenant.id, email: address, sv: user.sessionVersion }));
      sendJson(res, 200, { signedIn: true });
      return;
    }
    if (!tenant) throw new HttpError(401, "We couldn't find an account for that email address.");
    // Demo sign-in by email domain, only for customers without named sign-ins and never in production by default.
    if (!config.allowDemoSignIn) throw new HttpError(401, 'Ask your administrator for a sign-in.');
    res.setHeader('set-cookie', sessions.issue({ tenantId: tenant.id, email: address }));
    sendJson(res, 200, { signedIn: true });
  });

  router.delete('/api/session', ({ res }) => {
    res.setHeader('set-cookie', sessions.clear());
    sendJson(res, 200, { signedIn: false });
  });

  // "View as": switch between a company's people without a password, to show what each one sees. For local demos and
  // testing only: PERSONA_SWITCHER (never in production, nor behind a proxy), only from this computer, not relayed by a
  // proxy, and only at a local address, so a web page elsewhere can't reach it through DNS rebinding. A session still
  // works only at its own company's address, so another company's people are signed in at theirs.
  function personaSite(req) {
    const host = String(req.headers.host || '').toLowerCase().replace(/:\d+$/, '').replace(/^\[|\]$/g, '');
    const localHost = isLoopbackHost(host) || host.endsWith('.localhost');
    const relayed = Boolean(req.headers['x-forwarded-for'] || req.headers['x-forwarded-host'] || req.headers.forwarded);
    const site = req.site || { kind: 'single' };
    if (!config.personaSwitcher || relayed || !isLoopbackAddress(clientAddress(req, config)) || !localHost || site.kind === 'unknown') throw new HttpError(404, 'Not found.');
    return site;
  }

  const personaOf = (user) => {
    const access = accessOf(user);
    return { email: user.email, name: user.name || user.email, role: access.role, roleName: ROLES[access.role], territories: access.territories };
  };
  // The manager first, then the reps in territory order.
  const personasOf = (tenant) => {
    const rank = (p) => (p.role === 'manager' ? -1 : TERRITORIES.indexOf(p.territories?.[0]));
    return usersOf(tenant).map(personaOf).sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name));
  };
  // Who signs in at this address: the company's own people at its address, everyone's at a shared address.
  const signsInHere = (site, tenant) => site.kind === 'single' || (site.kind === 'customer' && tenant.id === site.tenant.id);

  router.get('/api/personas', ({ req, res }) => {
    const site = personaSite(req);
    let signedIn = null;
    try {
      signedIn = current(req).session.email;
    } catch {
      signedIn = null;
    }
    const companies = store
      .list()
      .filter((t) => usersOf(t).length)
      .map((t) => {
        const here = signsInHere(site, t);
        return { company: t.name, here, url: site.kind === 'single' ? null : customerUrl(config, t), personas: here ? personasOf(t) : [] };
      })
      .sort((a, b) => Number(b.here) - Number(a.here) || a.company.localeCompare(b.company));
    sendJson(res, 200, { current: signedIn, companies });
  });

  router.post('/api/persona', async ({ req, res }) => {
    const site = personaSite(req);
    const { email } = await readJson(req, 4096);
    const domain = emailDomain(email);
    const tenant = site.kind === 'customer' ? site.tenant : site.kind === 'single' ? store.list().find((t) => (t.domains || []).includes(domain)) : null;
    const user = tenant && signsInHere(site, tenant) ? findUser(tenant, email) : null;
    if (!user) throw new HttpError(404, "There's no such person at this address.");
    res.setHeader('set-cookie', sessions.issue({ tenantId: tenant.id, email: user.email, sv: user.sessionVersion }));
    sendJson(res, 200, { signedIn: true, persona: personaOf(user) });
  });

  router.get('/api/me', ({ req, res }) => {
    const context = current(req);
    sendJson(res, 200, {
      email: context.session.email,
      name: context.user?.name || null,
      role: context.access.role,
      roleName: ROLES[context.access.role],
      territories: context.access.territories,
      company: context.tenant.name,
      product: config.productName,
      status: context.status,
      features: context.features,
      reportPermissions: context.reportPermissions,
      examples: QUICK_EXAMPLES,
      demo: fabric.kind === 'mock',
      personaSwitcher: Boolean(config.personaSwitcher),
    });
  });

  // CRM records
  crmRoute('get', '/api/me/crm/summary', 200, (repo) => repo.summary());
  crmRoute('get', '/api/me/crm/options', 200, (repo) => repo.options());
  crmRoute('get', '/api/me/crm/lookup/accounts', 200, (repo, { query }) => repo.lookupAccounts(query.q));
  crmRoute('get', '/api/me/crm/accounts', 200, (repo, { query }) => repo.listAccounts(query));
  crmRoute('post', '/api/me/crm/accounts', 201, (repo, { body }) => repo.createAccount(body));
  crmRoute('get', '/api/me/crm/accounts/:id', 200, (repo, { params }) => repo.getAccount(params.id));
  crmRoute('patch', '/api/me/crm/accounts/:id', 200, (repo, { body, params }) => repo.updateAccount(params.id, body));
  crmRoute('get', '/api/me/crm/opportunities', 200, (repo, { query }) => repo.listOpportunities(query));
  crmRoute('post', '/api/me/crm/opportunities', 201, (repo, { body }) => repo.createOpportunity(body));
  crmRoute('patch', '/api/me/crm/opportunities/:id', 200, (repo, { body, params }) => repo.updateOpportunity(params.id, body));
  crmRoute('get', '/api/me/crm/activities', 200, (repo, { query }) => repo.listActivities(query));
  crmRoute('post', '/api/me/crm/activities', 201, (repo, { body }) => repo.createActivity(body));
  crmRoute('patch', '/api/me/crm/activities/:id', 200, (repo, { body, params }) => repo.updateActivity(params.id, body));
  crmRoute('get', '/api/me/crm/contacts', 200, (repo, { query }) => repo.listContacts(query));
  crmRoute('post', '/api/me/crm/contacts', 201, (repo, { body }) => repo.createContact(body));

  // Reports: view, edit and create, embedded with tokens scoped to this customer's workspace.
  router.get('/api/me/reports', async ({ req, res }) => {
    const context = need(current(req), 'reports');
    let listing;
    try {
      listing = await listReporting({ fabric: await identities.fabricFor(context.tenant), tenant: context.tenant });
    } catch (error) {
      await friendly(context.tenant, context.session.email, 'Listing reports', error);
    }
    sendJson(res, 200, {
      // Without authoring, only the reports the platform provides; customers' own reports come with authoring.
      reports: listing.reports.filter((r) => context.features.authoring || isStandardReport(context.tenant, r)).map(({ id, name }) => ({ id, name })),
      // New reports are built on Platform app Insights only: it's the model with row-level security. Only for people who may create.
      models: context.reportPermissions.create ? listing.datasets.filter((d) => d.canCreateReport && d.id === context.tenant.fabric.semanticModelId).map(({ id, name }) => ({ id, name })) : [],
    });
  });

  router.post('/api/me/embed', async ({ req, res }) => {
    const context = need(current(req), 'reports');
    limit(['embedPerUser', userKey(context)]);
    const body = await readJson(req);
    const mode = body.mode || 'view';
    if (mode === 'edit') needReportRight(context, 'edit');
    else if (mode !== 'view') needReportRight(context, 'create');
    let embed;
    try {
      embed = await createEmbedConfig({
        fabric: await identities.fabricFor(context.tenant),
        tenant: context.tenant,
        mode,
        reportId: body.reportId,
        datasetId: body.datasetId,
        lifetimeMinutes: config.embedTokenMinutes,
        identity: { username: context.session.email, roles: rolesFor(context.access.territories), limited: context.access.territories !== null },
        datasetIds: [context.tenant.fabric.semanticModelId],
        allowReport: context.features.authoring ? null : (report) => isStandardReport(context.tenant, report),
        // "Save as" puts a new report in the workspace, so the token names the workspace only for people who may create.
        canCreate: context.reportPermissions.create,
      });
    } catch (error) {
      await friendly(context.tenant, context.session.email, 'Opening a report', error);
    }
    const { tokenRequest, ...embedConfig } = embed;
    sendJson(res, 200, { ...embedConfig, demo: fabric.kind === 'mock' });
  });

  // Report usage from the browser (platform/usage.js): what was opened or saved, and how long it took to load and
  // render. Who it was and which customer come from the session, never from the request.
  router.post('/api/me/reports/usage', async ({ req, res }) => {
    const context = need(current(req), 'reports');
    limit(['usagePerUser', userKey(context)]);
    const entry = usageEntry(await readJson(req, 4096), {
      email: context.session.email,
      scope: context.access.territories === null ? 'All territories' : context.access.territories.join(', '),
      rights: context.reportPermissions,
    });
    recordUsage(context.tenant, entry);
    await store.save(context.tenant);
    sendJson(res, 202, { recorded: true });
  });

  router.get('/api/me/reports/fields', ({ req, res }) => {
    needReportRight(current(req), 'author');
    sendJson(res, 200, fieldCatalog());
  });

  // "Describe a chart": the browser builds the visual with the Power BI report authoring API. In demo mode there's
  // no Power BI, so the data comes along and the browser draws a simple chart.
  router.post('/api/me/reports/describe', async ({ req, res }) => {
    const context = needReportRight(current(req), 'author');
    limit(['describePerTenant', context.tenant.id]);
    const text = String((await readJson(req)).text || '').trim();
    if (!text || text.length > 300) throw new HttpError(400, 'Describe the chart in up to 300 characters.');
    const visual = describeVisual(text);
    if (visual.ok && fabric.kind === 'mock' && context.features.crm) {
      const preview = await (await crm.forTenant(context.tenant)).scoped(context.access.territories).quickAnswer(text).catch(() => null);
      if (preview) visual.preview = { rows: preview.rows };
    }
    sendJson(res, 200, visual);
  });

  router.post('/api/me/ask', async ({ req, res }) => {
    const context = need(current(req), 'ask');
    limit(['askPerUser', userKey(context)], ['askPerTenant', context.tenant.id]);
    const question = String((await readJson(req)).question || '').trim();
    if (!question || question.length > 2000) throw new HttpError(400, 'Ask a question of up to 2,000 characters.');
    let result;
    try {
      result = await assistant.ask(context.tenant, question, { email: context.session.email, territories: context.access.territories });
    } catch (error) {
      await friendly(context.tenant, context.session.email, 'A question', error);
    }
    sendJson(res, 200, result);
  });

  // Data integration add-on: files and web feeds the customer loads next to their CRM data.
  router.get('/api/me/data', async ({ req, res }) => {
    const { tenant } = need(current(req), 'data');
    const client = await identities.fabricFor(tenant);
    const { workspaceId, lakehouseId } = tenant.fabric;
    const tables = await client.listLakehouseTables(workspaceId, lakehouseId);
    const datasets = await mapLimit(tables, 4, async (table) => {
      const lastLoad = tenant.ingestions.find((i) => i.table === table.name);
      let rows = null;
      try {
        rows = (await client.countTableRows(workspaceId, lakehouseId, table.name)).rows;
      } catch {
        rows = null;
      }
      return {
        id: table.name,
        name: datasetName(table.name, tenant),
        source: datasetSource(table.name, lastLoad, config.productName),
        builtIn: table.name.startsWith('crm_'),
        rows,
        updatedAt: lastLoad?.at || null,
      };
    });
    datasets.sort((a, b) => Number(b.builtIn) - Number(a.builtIn) || a.name.localeCompare(b.name));
    sendJson(res, 200, datasets);
  });

  async function afterLoad(tenant, client) {
    await refreshAgentAfterLoad({ fabric: client, tenant });
    await store.save(tenant);
  }

  // Keeps the name the customer typed ("NPS survey") for display; the table itself gets a safe technical name.
  function rememberName(tenant, table, typedName) {
    const label = String(typedName || '').trim().replace(/\s+/g, ' ').slice(0, 80);
    if (!label) return;
    tenant.datasetNames = { ...(tenant.datasetNames || {}), [table]: label };
  }

  router.post('/api/me/uploads', async ({ req, res, url }) => {
    const { tenant } = need(current(req), 'data');
    limit(['dataLoadPerTenant', tenant.id]);
    const client = await identities.fabricFor(tenant);
    const fileName = decodeHeader(req.headers['x-file-name']);
    if (!fileName) throw new HttpError(400, 'The file name is missing.');
    const bytes = await readBody(req, MAX_UPLOAD_BYTES);
    const typedName = url.searchParams.get('name');
    const record = await ingestBytes({ fabric: client, tenant, bytes, fileName, table: typedName || undefined, mode: url.searchParams.get('mode') || 'Overwrite' });
    rememberName(tenant, record.table, typedName);
    await afterLoad(tenant, client);
    sendJson(res, 201, { id: record.table, name: datasetName(record.table, tenant) });
  });

  router.post('/api/me/imports/web', async ({ req, res }) => {
    const { tenant } = need(current(req), 'data');
    limit(['dataLoadPerTenant', tenant.id]);
    const client = await identities.fabricFor(tenant);
    const body = await readJson(req);
    const record = await importFromWeb({ fabric: client, tenant, url: String(body.url || '').trim(), table: body.name || undefined, mode: 'Overwrite', fetchOptions });
    rememberName(tenant, record.table, body.name);
    await afterLoad(tenant, client);
    sendJson(res, 201, { id: record.table, name: datasetName(record.table, tenant) });
  });

  router.post('/api/me/sync', async ({ req, res }) => {
    const { tenant } = need(current(req), 'data');
    limit(['dataLoadPerTenant', tenant.id]);
    const client = await identities.fabricFor(tenant);
    const records = await syncAppData({ fabric: client, tenant });
    await afterLoad(tenant, client);
    sendJson(res, 201, { synced: records.map((r) => datasetName(r.table, tenant)) });
  });

  // Integrations the platform team sets up for the customer, such as a database on their network.
  router.post('/api/me/requests', async ({ req, res }) => {
    const { tenant, session } = current(req);
    limit(['crmWritePerTenant', tenant.id]);
    const body = await readJson(req);
    const message = String(body.message || '').trim().slice(0, 1000);
    if (!message) throw new HttpError(400, 'Tell us what you would like to connect.');
    addActivity(tenant, `Request from ${session.email}: ${message}`, 'request');
    await store.save(tenant);
    sendJson(res, 201, { received: true });
  });
}
