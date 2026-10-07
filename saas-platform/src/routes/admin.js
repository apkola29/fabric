import { isGuid } from '../config.js';
import { ALL_TERRITORIES_ROLE } from '../crm/model.js';
import { TERRITORIES } from '../crm/schema.js';
import { dataAgentMcpUrl } from '../fabric/client.js';
import { clientAddress } from '../http/limits.js';
import { HttpError, readBody, readJson, sendJson } from '../http/router.js';
import { syncDataAgent } from '../platform/agent.js';
import { QUESTION_LOG_SIZE, loggedAnswer, safeImages } from '../platform/assistant.js';
import { auditTenant } from '../platform/audit.js';
import { LOGO_MAX_BYTES, brandOf, logoUrl, parseColor, sendLogo, setLogo } from '../platform/branding.js';
import { MAX_UPLOAD_BYTES, importFromWeb, ingestBytes, refreshAgentAfterLoad, syncAppData } from '../platform/ingest.js';
import { getPlan, listAddons, listPlans, entitlements, ADDONS } from '../platform/plans.js';
import { createEmbedConfig, listReporting } from '../platform/reporting.js';
import { parseDomains } from '../platform/sessions.js';
import { addActivity, newTenantRecord } from '../platform/store.js';
import { customerUrl, subdomainOf, uniqueSubdomain } from '../platform/tenancy.js';
import { summarizeUsage } from '../platform/usage.js';
import { ROLES, addUser, publicUser, removeUser, resetPassword, updateUser, usersOf } from '../platform/users.js';

// Back office for the platform team: create customers, set their plan (entitlements) and sign-in domains,
// provision Fabric, and support them. Customers never see these routes or this vocabulary.

const RUNNABLE = { DataPipeline: 'Pipeline', Notebook: 'RunNotebook' };
const BUSY = new Set(['provisioning', 'deprovisioning']);

export function decodeHeader(value) {
  if (!value) return '';
  try {
    return decodeURIComponent(String(value));
  } catch {
    return String(value);
  }
}

export function registerAdminRoutes(router, { config, fabric, store, tokens, provisioner, identities, crm, fetchOptions, operators, limiter = null }) {
  // Customer-level work runs as the customer's own service account (falls back to the platform identity if allowed).
  const scoped = (tenant) => identities.fabricFor(tenant);
  // Who did it, for the customer's activity log. Operators sign in with a shared key, so the name is self-declared.
  const operatorName = (req) => (req.operator?.name ? `Operator ${req.operator.name}` : 'An operator');
  const describeAccess = (user) => {
    const { role, territories, canEdit, canCreate } = publicUser(user);
    const rights = [canEdit && 'edits reports', canCreate && 'creates reports'].filter(Boolean);
    return `${role === 'manager' ? 'manager, every territory' : `rep, ${territories.join(', ')}`}${rights.length ? `; ${rights.join(', ')}` : ''}`;
  };

  // Looking at a customer's data from the back office is recorded in that customer's activity log.
  async function audit(tenant, req, message) {
    addActivity(tenant, `${operatorName(req)} ${message}`, 'audit');
    await store.save(tenant);
  }

  function capacityOrError(input) {
    const value = String(input ?? '').trim();
    if (!value) return null;
    if (fabric.kind === 'live' && !isGuid(value)) throw new HttpError(400, 'The capacity ID must be a GUID.');
    if (value.length > 64) throw new HttpError(400, 'That capacity ID is too long.');
    return value;
  }

  const summary = (t) => ({
    id: t.id,
    name: t.name,
    plan: t.plan,
    planName: getPlan(t.plan)?.name || t.plan,
    addons: t.addons || [],
    status: t.status,
    domains: t.domains || [],
    // The customer's own address (APP_DOMAIN), where its people sign in.
    url: customerUrl(config, t),
    subdomain: config.appDomain ? subdomainOf(t) : null,
    workspaceName: t.fabric?.workspaceName || null,
    capacityId: t.capacityId || null,
    serviceAccount: identities.describe(t).status,
    userCount: usersOf(t).length,
    updatedAt: t.updatedAt,
  });

  const detail = (t) => {
    const { features, resources } = entitlements(t);
    return {
      ...summary(t),
      error: t.error,
      createdAt: t.createdAt,
      provisionedAt: t.provisionedAt || null,
      sampleData: t.sampleData !== false,
      features,
      resources,
      identity: identities.describe(t),
      branding: { ...brandOf(t), logoUrl: logoUrl(t, `/api/admin/tenants/${t.id}/logo`) },
      // The data agent the app asks, through its MCP server, as this customer's service account.
      assistant: t.fabric?.dataAgentId
        ? { dataAgentId: t.fabric.dataAgentId, mcpUrl: dataAgentMcpUrl(config.endpoints.fabric, t.fabric.workspaceId, t.fabric.dataAgentId), codeInterpreter: config.dataAgentCodeInterpreter, questions: (t.questions || []).length }
        : null,
      users: usersOf(t).map(publicUser),
      territories: TERRITORIES,
      roles: ROLES,
      fabric: t.fabric,
      steps: Object.entries(t.steps).map(([key, step]) => ({ key, ...step })),
      activity: t.activity.slice(0, 30),
      ingestions: t.ingestions.slice(0, 20),
      portalUrl: t.fabric?.workspaceId && fabric.kind === 'live' ? `https://app.fabric.microsoft.com/groups/${t.fabric.workspaceId}` : null,
    };
  };

  function addonsOrError(input) {
    const addons = [...new Set((Array.isArray(input) ? input : []).map(String))];
    const unknown = addons.filter((a) => !ADDONS[a]);
    if (unknown.length) throw new HttpError(400, `Unknown add-on: ${unknown.join(', ')}.`);
    return addons;
  }

  function tenantOr404(id) {
    const tenant = store.get(id);
    if (!tenant) throw new HttpError(404, 'There is no customer with that ID.');
    return tenant;
  }

  function usableTenant(id) {
    const tenant = tenantOr404(id);
    if (BUSY.has(tenant.status) || provisioner.isBusy(id)) throw new HttpError(409, 'Provisioning is running for this customer. Try again when it finishes.');
    if (!tenant.fabric?.workspaceId) throw new HttpError(409, "This customer doesn't have a workspace yet.");
    return tenant;
  }

  function requireFeature(tenant, feature) {
    const { plan, features } = entitlements(tenant);
    if (!features[feature]) throw new HttpError(403, `The ${plan.name} edition doesn't include this feature.`);
  }

  function domainsOrError(input, exceptTenantId) {
    let domains;
    try {
      domains = parseDomains(input);
    } catch (error) {
      throw new HttpError(400, error.message);
    }
    for (const domain of domains) {
      const owner = store.list().find((t) => t.id !== exceptTenantId && (t.domains || []).includes(domain));
      if (owner) throw new HttpError(409, `${domain} already signs in as ${owner.name}.`);
    }
    return domains;
  }

  // Operator sign-in for the back office. Open on loopback without ADMIN_KEY (local development only).
  router.get('/api/admin/session', ({ req, res }) => {
    const operator = operators.read(req.headers.cookie);
    sendJson(res, 200, { required: operators.required, signedIn: !operators.required || Boolean(operator), name: operator?.name || null });
  });

  router.post('/api/admin/session', async ({ req, res }) => {
    if (!operators.required) throw new HttpError(400, 'Operator sign-in is off because ADMIN_KEY is not set (loopback only).');
    limiter?.enforce([{ key: `operatorSignInPerIp|${clientAddress(req, config)}`, limit: config.limits?.operatorSignInPerIp, message: 'Too many sign-in attempts. Wait a minute and try again.' }]);
    const body = await readJson(req, 4096);
    if (!operators.verifyKey(body.key)) throw new HttpError(401, 'That key is not correct.');
    res.setHeader('set-cookie', operators.issue({ name: body.name }));
    sendJson(res, 200, { signedIn: true });
  });

  router.delete('/api/admin/session', ({ res }) => {
    res.setHeader('set-cookie', operators.clear());
    sendJson(res, 200, { signedIn: false });
  });

  router.get('/api/admin/config', ({ res }) =>
    sendJson(res, 200, {
      mode: config.authMode,
      live: fabric.kind === 'live',
      identity: tokens?.describe() || { mode: 'mock', label: 'Mock (no Fabric calls)' },
      capacityConfigured: Boolean(config.capacityId),
      templateConfigured: Boolean(config.templateWorkspaceId),
      opsAccessConfigured: Boolean(config.opsPrincipal),
      productName: config.productName,
      warnings: config.warnings,
      plans: listPlans(),
      addons: listAddons(),
      serviceAccounts: { mode: identities.mode, autoCreate: identities.canCreate() },
      security: {
        environment: config.production ? 'production' : 'development',
        operatorSignIn: operators.required,
        platformWorkspaceAccess: config.platformWorkspaceAccess,
        embedTokenMinutes: config.embedTokenMinutes,
        secureCookies: config.secureCookies,
      },
      provisioning: provisioner.stats(),
      crmConnections: crm.stats?.() || null,
    }),
  );

  router.get('/api/admin/tenants', ({ res }) => sendJson(res, 200, store.list().map(summary)));

  router.post('/api/admin/tenants', async ({ req, res }) => {
    const body = await readJson(req);
    const name = String(body.name || '').trim().replace(/\s+/g, ' ');
    if (name.length < 2 || name.length > 60) throw new HttpError(400, 'The company name must be 2 to 60 characters.');
    const plan = getPlan(body.plan);
    if (!plan) throw new HttpError(400, 'Pick one of the plans.');
    if (store.list().some((t) => t.name.toLowerCase() === name.toLowerCase())) throw new HttpError(409, 'A customer with that name already exists.');
    const domains = domainsOrError(body.domains);
    const workspaceId = String(body.workspaceId || '').trim() || null;
    if (workspaceId) {
      if (fabric.kind === 'live' && !isGuid(workspaceId)) throw new HttpError(400, 'The workspace ID must be a GUID.');
      if (store.list().some((t) => String(t.fabric?.workspaceId).toLowerCase() === workspaceId.toLowerCase())) {
        throw new HttpError(409, 'Another customer already uses that workspace.');
      }
    }
    const tenant = newTenantRecord({
      name,
      plan: plan.id,
      workspaceId,
      domains,
      addons: addonsOrError(body.addons),
      sampleData: body.sampleData !== false && (body.sampleData === true || config.sampleDataDefault !== false),
      capacityId: capacityOrError(body.capacityId),
      subdomain: uniqueSubdomain(name, store.list()),
    });
    addActivity(tenant, `Customer added with the ${plan.name} edition${workspaceId ? `, using existing workspace ${workspaceId}` : ''}${tenant.capacityId ? ` on dedicated capacity ${tenant.capacityId}` : ''}`);
    await store.save(tenant);
    provisioner.provision(tenant.id);
    sendJson(res, 202, detail(tenant));
  });

  router.get('/api/admin/tenants/:id', ({ res, params }) => sendJson(res, 200, detail(tenantOr404(params.id))));

  // Named sign-ins for the customer's people. A generated password appears once, in the response that created it.
  router.get('/api/admin/tenants/:id/users', ({ res, params }) => sendJson(res, 200, usersOf(tenantOr404(params.id)).map(publicUser)));

  router.post('/api/admin/tenants/:id/users', async ({ req, res, params }) => {
    const tenant = tenantOr404(params.id);
    const body = await readJson(req, 8192);
    const { user, password } = await addUser({ store, tenant, email: body.email, name: body.name, password: body.password, role: body.role, territories: body.territories, canEdit: body.canEdit, canCreate: body.canCreate });
    addActivity(tenant, `${operatorName(req)} added a sign-in for ${user.email} (${describeAccess(user)})`, 'audit');
    await store.save(tenant);
    sendJson(res, 201, { user: publicUser(user), password });
  });

  // Role, territories and report permissions. Changing them signs the person out, so nothing they have open keeps the
  // old access.
  router.patch('/api/admin/tenants/:id/users/:userId', async ({ req, res, params }) => {
    const tenant = tenantOr404(params.id);
    const body = await readJson(req, 8192);
    const { user, signedOut } = updateUser({ tenant, userId: params.userId, name: body.name, role: body.role, territories: body.territories, canEdit: body.canEdit, canCreate: body.canCreate });
    addActivity(tenant, `${operatorName(req)} updated the sign-in of ${user.email} (${describeAccess(user)})${signedOut ? '; their sessions ended' : ''}`, 'audit');
    await store.save(tenant);
    sendJson(res, 200, { user: publicUser(user), signedOut });
  });

  router.post('/api/admin/tenants/:id/users/:userId/password', async ({ req, res, params }) => {
    const tenant = tenantOr404(params.id);
    const body = await readJson(req, 8192);
    const { user, password } = await resetPassword({ tenant, userId: params.userId, password: body.password });
    addActivity(tenant, `${operatorName(req)} reset the password of ${user.email}; their sessions ended`, 'audit');
    await store.save(tenant);
    sendJson(res, 200, { user: publicUser(user), password });
  });

  router.delete('/api/admin/tenants/:id/users/:userId', async ({ req, res, params }) => {
    const tenant = tenantOr404(params.id);
    const user = removeUser({ tenant, userId: params.userId });
    addActivity(tenant, `${operatorName(req)} removed the sign-in of ${user.email}`, 'audit');
    await store.save(tenant);
    sendJson(res, 200, { removed: true });
  });

  // Change the plan (re-provisions), the sign-in domains and/or the accent color.
  router.patch('/api/admin/tenants/:id', async ({ req, res, params }) => {
    const tenant = tenantOr404(params.id);
    const body = await readJson(req);
    if (body.domains !== undefined) {
      tenant.domains = domainsOrError(body.domains, tenant.id);
      addActivity(tenant, tenant.domains.length ? `Sign-in domains set to ${tenant.domains.join(', ')}` : 'Sign-in domains cleared');
      await store.save(tenant);
    }
    if (body.color !== undefined) {
      let color;
      try {
        color = parseColor(body.color);
      } catch (error) {
        throw new HttpError(400, error.message);
      }
      tenant.branding = { ...(tenant.branding || {}), color };
      addActivity(tenant, color ? `${operatorName(req)} set the accent color to ${color}` : `${operatorName(req)} removed the accent color`, 'audit');
      await store.save(tenant);
    }
    let reprovision = false;
    if (body.capacityId !== undefined) {
      const capacityId = capacityOrError(body.capacityId);
      if ((capacityId || null) !== (tenant.capacityId || null)) {
        if (provisioner.isBusy(tenant.id) || BUSY.has(tenant.status)) throw new HttpError(409, 'Provisioning is already running for this customer.');
        tenant.capacityId = capacityId;
        addActivity(tenant, capacityId ? `Moving to dedicated capacity ${capacityId}` : 'Moving back to the default capacity');
        reprovision = true;
      }
    }
    if (body.plan !== undefined || body.addons !== undefined) {
      const plan = body.plan !== undefined ? getPlan(body.plan) : getPlan(tenant.plan);
      if (!plan) throw new HttpError(400, 'Pick one of the editions.');
      const addons = body.addons !== undefined ? addonsOrError(body.addons) : tenant.addons || [];
      if (provisioner.isBusy(tenant.id) || BUSY.has(tenant.status)) throw new HttpError(409, 'Provisioning is already running for this customer.');
      if (plan.id !== tenant.plan) {
        addActivity(tenant, `Edition changed from ${getPlan(tenant.plan).name} to ${plan.name}`);
        tenant.plan = plan.id;
      }
      if (JSON.stringify(addons) !== JSON.stringify(tenant.addons || [])) {
        addActivity(tenant, addons.length ? `Add-ons set to ${addons.join(', ')}` : 'Add-ons removed');
        tenant.addons = addons;
      }
      await store.save(tenant);
      provisioner.provision(tenant.id);
      sendJson(res, 202, detail(tenant));
      return;
    }
    if (reprovision) {
      await store.save(tenant);
      provisioner.provision(tenant.id);
      sendJson(res, 202, detail(tenant));
      return;
    }
    sendJson(res, 200, detail(tenant));
  });

  router.post('/api/admin/tenants/:id/provision', ({ res, params }) => {
    const tenant = tenantOr404(params.id);
    if (tenant.status === 'deprovisioning') throw new HttpError(409, 'This customer is being deleted.');
    provisioner.provision(tenant.id);
    sendJson(res, 202, detail(tenant));
  });

  // The customer's logo: the raw image as the body (SVG, PNG, JPEG or WebP, 64 KB at most). It shows on the
  // customer's sign-in page and in its app.
  router.put('/api/admin/tenants/:id/logo', async ({ req, res, params }) => {
    const tenant = tenantOr404(params.id);
    let logo;
    try {
      logo = setLogo(tenant, await readBody(req, LOGO_MAX_BYTES));
    } catch (error) {
      if (error instanceof HttpError) throw error;
      throw new HttpError(400, error.message);
    }
    addActivity(tenant, `${operatorName(req)} set a new logo (${logo.contentType}, ${Math.ceil(logo.bytes / 1024)} KB)`, 'audit');
    await store.save(tenant);
    sendJson(res, 200, detail(tenant));
  });

  router.delete('/api/admin/tenants/:id/logo', async ({ req, res, params }) => {
    const tenant = tenantOr404(params.id);
    if (tenant.branding?.logo) {
      tenant.branding = { ...tenant.branding, logo: null };
      addActivity(tenant, `${operatorName(req)} removed the logo`, 'audit');
      await store.save(tenant);
    }
    sendJson(res, 200, detail(tenant));
  });

  router.get('/api/admin/tenants/:id/logo', ({ res, params }) => {
    if (!sendLogo(res, tenantOr404(params.id))) throw new HttpError(404, 'This customer has no logo.');
  });

  // What people asked the assistant and what they were told, newest first, and who answered. It's the customer's
  // content, so looking at it is recorded in their activity log.
  router.get('/api/admin/tenants/:id/questions', async ({ req, res, params }) => {
    const tenant = tenantOr404(params.id);
    await audit(tenant, req, 'viewed the questions people asked the assistant');
    sendJson(res, 200, { questions: tenant.questions || [] });
  });

  // Who opened and saved which reports, and how fast they loaded and rendered (platform/usage.js). Also the
  // customer's information, so looking at it is recorded too.
  router.get('/api/admin/tenants/:id/usage', async ({ req, res, params }) => {
    const tenant = tenantOr404(params.id);
    await audit(tenant, req, 'viewed report usage');
    const entries = tenant.reportUsage || [];
    sendJson(res, 200, { entries, reports: summarizeUsage(entries) });
  });

  router.delete('/api/admin/tenants/:id', async ({ res, params, url }) => {
    const tenant = tenantOr404(params.id);
    if (url.searchParams.get('confirm') !== tenant.name) throw new HttpError(400, 'Confirm by sending the exact customer name.');
    const keepWorkspace = url.searchParams.get('keepWorkspace') === 'true';
    await provisioner.deprovision(tenant.id, { keepWorkspace });
    sendJson(res, 200, { deleted: true, id: tenant.id, workspaceDeleted: !keepWorkspace });
  });

  router.get('/api/admin/tenants/:id/items', async ({ res, params }) => {
    const tenant = usableTenant(params.id);
    const items = await (await scoped(tenant)).listItems(tenant.fabric.workspaceId);
    sendJson(
      res,
      200,
      items
        .filter((i) => i.type !== 'SQLEndpoint')
        .map(({ id, type, displayName, description }) => ({ id, type, displayName, description, runnable: Boolean(RUNNABLE[type]) }))
        .sort((a, b) => a.type.localeCompare(b.type) || a.displayName.localeCompare(b.displayName)),
    );
  });

  router.get('/api/admin/tenants/:id/tables', async ({ res, params }) => {
    const tenant = usableTenant(params.id);
    if (!tenant.fabric.lakehouseId) throw new HttpError(409, "This customer doesn't have a lakehouse yet.");
    const tables = await (await scoped(tenant)).listLakehouseTables(tenant.fabric.workspaceId, tenant.fabric.lakehouseId);
    sendJson(res, 200, tables.map(({ name, format, type }) => ({ name, format, type })).sort((a, b) => a.name.localeCompare(b.name)));
  });

  router.post('/api/admin/tenants/:id/uploads', async ({ req, res, params, url }) => {
    const tenant = usableTenant(params.id);
    requireFeature(tenant, 'ingestion');
    const fileName = decodeHeader(req.headers['x-file-name']);
    if (!fileName) throw new HttpError(400, 'Send the file name in the x-file-name header.');
    const bytes = await readBody(req, MAX_UPLOAD_BYTES);
    const record = await ingestBytes({ fabric: await scoped(tenant), tenant, bytes, fileName, table: url.searchParams.get('table'), mode: url.searchParams.get('mode') || 'Overwrite' });
    const agent = await refreshAgentAfterLoad({ fabric: await scoped(tenant), tenant });
    await audit(tenant, req, `loaded ${fileName} into ${record.table}`);
    sendJson(res, 201, { ...record, agent });
  });

  router.post('/api/admin/tenants/:id/imports/web', async ({ req, res, params }) => {
    const tenant = usableTenant(params.id);
    requireFeature(tenant, 'ingestion');
    const body = await readJson(req);
    const record = await importFromWeb({ fabric: await scoped(tenant), tenant, url: String(body.url || '').trim(), table: body.table, mode: body.mode || 'Overwrite', fetchOptions });
    const agent = await refreshAgentAfterLoad({ fabric: await scoped(tenant), tenant });
    await audit(tenant, req, `imported ${record.table} from the web`);
    sendJson(res, 201, { ...record, agent });
  });

  router.post('/api/admin/tenants/:id/imports/app-data', async ({ req, res, params }) => {
    const tenant = usableTenant(params.id);
    const records = await syncAppData({ fabric: await scoped(tenant), tenant });
    const agent = await refreshAgentAfterLoad({ fabric: await scoped(tenant), tenant });
    await audit(tenant, req, 'copied the CRM data to the lakehouse');
    sendJson(res, 201, { records, agent });
  });

  router.post('/api/admin/tenants/:id/items/:itemId/jobs', async ({ req, res, params }) => {
    const tenant = usableTenant(params.id);
    if (!isGuid(params.itemId)) throw new HttpError(400, 'That is not a valid item ID.');
    const item = (await (await scoped(tenant)).listItems(tenant.fabric.workspaceId)).find((i) => i.id === params.itemId);
    if (!item) throw new HttpError(404, "That item isn't in this customer's workspace.");
    const jobType = RUNNABLE[item.type];
    if (!jobType) throw new HttpError(400, `A ${item.type} can't be run from here.`);
    const job = await (await scoped(tenant)).runItemJob(tenant.fabric.workspaceId, item.id, jobType);
    await audit(tenant, req, `started ${item.displayName}`);
    sendJson(res, 202, { itemId: item.id, name: item.displayName, jobType, jobInstanceId: job.jobInstanceId, status: job.status });
  });

  router.get('/api/admin/tenants/:id/items/:itemId/jobs/:jobId', async ({ res, params }) => {
    const tenant = usableTenant(params.id);
    if (!isGuid(params.itemId) || !isGuid(params.jobId)) throw new HttpError(400, 'That is not a valid ID.');
    const job = await (await scoped(tenant)).getItemJob(tenant.fabric.workspaceId, params.itemId, params.jobId);
    // A finished pipeline or notebook may have written new tables; let the data agent see them.
    if (job.status === 'Completed') {
      const agent = await refreshAgentAfterLoad({ fabric: await scoped(tenant), tenant });
      if (agent?.added?.length || agent?.error) await store.save(tenant);
    }
    sendJson(res, 200, {
      id: job.id,
      status: job.status,
      startTimeUtc: job.startTimeUtc || null,
      endTimeUtc: job.endTimeUtc || null,
      failureReason: job.failureReason?.message || job.failureReason || null,
    });
  });

  router.get('/api/admin/tenants/:id/reports', async ({ res, params }) => {
    const tenant = usableTenant(params.id);
    requireFeature(tenant, 'reports');
    sendJson(res, 200, await listReporting({ fabric: await scoped(tenant), tenant }));
  });

  router.post('/api/admin/tenants/:id/embed', async ({ req, res, params }) => {
    const tenant = usableTenant(params.id);
    requireFeature(tenant, 'reports');
    const body = await readJson(req);
    const mode = body.mode || 'view';
    // Operators support the whole customer, so they see every territory.
    const identity = { username: req.operator?.name ? `operator:${req.operator.name}` : 'operator', roles: [ALL_TERRITORIES_ROLE] };
    const embed = await createEmbedConfig({ fabric: await scoped(tenant), tenant, mode, reportId: body.reportId, datasetId: body.datasetId, lifetimeMinutes: config.embedTokenMinutes, identity });
    await audit(tenant, req, `opened ${embed.kind === 'create' ? `a new report on ${embed.name}` : `the report "${embed.name}"`} (${mode})`);
    sendJson(res, 200, { ...embed, mock: fabric.kind === 'mock' });
  });

  router.post('/api/admin/tenants/:id/agent/ask', async ({ req, res, params }) => {
    const tenant = usableTenant(params.id);
    requireFeature(tenant, 'agent');
    if (!tenant.fabric.dataAgentId) throw new HttpError(409, "The data agent isn't set up yet. Run provisioning again.");
    const question = String((await readJson(req)).question || '').trim();
    if (!question || question.length > 2000) throw new HttpError(400, 'Ask a question of up to 2,000 characters.');
    await audit(tenant, req, `asked the assistant: "${question.length > 120 ? `${question.slice(0, 117)}...` : question}"`);
    const started = Date.now();
    const entry = { email: operatorName(req), scope: 'All territories', question: question.slice(0, 500), answeredBy: 'data agent', agent: 'answered', chart: false };
    let result;
    try {
      result = await (await scoped(tenant)).askDataAgent(tenant.fabric.workspaceId, tenant.fabric.dataAgentId, question);
    } catch (error) {
      Object.assign(entry, { answeredBy: 'nobody', agent: 'failed', error: String(error.message || error).slice(0, 300) });
      throw error;
    } finally {
      tenant.questions = [{ at: new Date().toISOString(), ...entry, ...loggedAnswer(result?.answer), images: result?.images?.length || 0, ms: Date.now() - started }, ...(tenant.questions || [])].slice(0, QUESTION_LOG_SIZE);
      await store.save(tenant);
    }
    const images = safeImages(result.images);
    sendJson(res, 200, { answer: result.answer, tool: result.tool, ms: Date.now() - started, ...(images.length ? { images } : {}) });
  });

  // What the platform team checks after provisioning: row counts and headline numbers from the customer's CRM database.
  router.get('/api/admin/tenants/:id/crm', async ({ req, res, params }) => {
    const tenant = usableTenant(params.id);
    requireFeature(tenant, 'crm');
    const repo = await crm.forTenant(tenant);
    const result = { counts: await repo.counts(), summary: await repo.scoped(null).summary() };
    await audit(tenant, req, 'viewed CRM row counts and headline numbers');
    sendJson(res, 200, result);
  });

  // Least-privilege and drift check: who has which role, what exists, how the model signs in. Read-only.
  router.get('/api/admin/tenants/:id/audit', async ({ res, params }) => {
    const tenant = tenantOr404(params.id);
    sendJson(res, 200, await auditTenant({ tenant, fabric, identities, config }));
  });

  router.post('/api/admin/tenants/:id/agent/sync', async ({ res, params }) => {
    const tenant = usableTenant(params.id);
    requireFeature(tenant, 'agent');
    const result = await syncDataAgent({ fabric: await scoped(tenant), tenant });
    if (result.added?.length) addActivity(tenant, `The data agent can now query ${result.added.join(', ')}`);
    await store.save(tenant);
    sendJson(res, 200, result);
  });
}
