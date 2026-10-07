import { randomUUID } from 'node:crypto';
import path from 'node:path';
import { createTokenProvider } from '../auth/tokens.js';
import { loadConfig } from '../config.js';
import * as workload from '../crm/workload.js';
import { createFabricClient, dataAgentMcpUrl } from '../fabric/client.js';
import { createMockFabric } from '../fabric/mock.js';
import { agentModelSource } from './agent.js';
import { QUESTION_LOG_SIZE, createAssistant } from './assistant.js';
import { auditTenant } from './audit.js';
import { createIdentityBroker } from './identities.js';
import { createProvisioner } from './provisioner.js';
import { createEmbedConfig, isStandardReport, listReporting } from './reporting.js';
import { createMemorySecretStore, createSecretStore } from './secrets.js';
import { emailDomain } from './sessions.js';
import { createTenantStore, newTenantRecord } from './store.js';
import { USAGE_LOG_SIZE, recordUsage, usageEntry } from './usage.js';
import { accessOf } from './users.js';

// The framework's controls (FRAMEWORK.md, section 6) and the validator that checks them: npm run validate.
//
// Each control is checked in one or more ways:
//   auto     against a running platform, read-only: the emulator (the default) or live Fabric (--live)
//   browser  in Microsoft Edge or Google Chrome, with the embed tokens the app would issue (--live --browser)
//   tests    by the automated tests (npm test), which the validator names but doesn't run
// test/framework.test.js keeps this catalog and the one in FRAMEWORK.md in step.

const LEARN = 'https://learn.microsoft.com';

export const CONTROLS = Object.freeze([
  { id: 'ISO-01', area: 'Isolation', how: ['auto'], title: 'Each tenant has its own workspace, database, models, report, data agent, connection and identities', tests: ['test/isolation.test.js', 'test/robustness.test.js'], source: `${LEARN}/power-bi/developer/embedded/embed-multi-tenancy` },
  { id: 'ISO-02', area: 'Isolation', how: ['auto'], title: "A tenant's identity is refused at every other tenant's workspace, items, models, reports and data agent", tests: ['test/isolation.test.js', 'test/admin-api.test.js'] },
  { id: 'ISO-03', area: 'Isolation', how: ['tests'], title: "Sessions work only at their own tenant's address, and unknown host names are refused", tests: ['test/tenancy.test.js', 'test/signins.test.js', 'test/isolation.test.js'] },
  { id: 'ISO-04', area: 'Isolation', how: ['tests'], title: 'Customers never see Fabric errors, IDs or account names', tests: ['test/isolation.test.js'] },
  { id: 'IDN-01', area: 'Identity', how: ['auto'], title: 'Each tenant has its own service principal, Admin of its own workspace and nothing else', tests: ['test/isolation.test.js', 'test/identities.test.js'], source: `${LEARN}/power-bi/developer/embedded/embed-service-principal` },
  { id: 'IDN-02', area: 'Identity', how: ['auto'], title: 'The platform identity keeps no standing access to tenant workspaces, confirmed by a refused call', tests: ['test/isolation.test.js'] },
  { id: 'IDN-03', area: 'Identity', how: ['auto'], title: "The workspace identity is Contributor of its own workspace and the models' only data credential", tests: ['test/isolation.test.js'], source: `${LEARN}/fabric/security/workspace-identity` },
  { id: 'IDN-04', area: 'Identity', how: ['auto'], title: 'No person has standing access to a tenant workspace, other than documented break-glass access', tests: ['test/isolation.test.js'] },
  { id: 'IDN-05', area: 'Identity', how: ['auto'], title: 'Service principals sign in with a federated credential or a certificate (client secrets only in development); stored credentials are encrypted at rest, in date and rotatable', tests: ['test/identities.test.js', 'test/credential-types.test.js', 'test/robustness.test.js'] },
  { id: 'IDN-06', area: 'Identity', how: ['auto'], title: 'The service principal tenant settings apply only to a security group of the platform\'s service principals, and none of them can call the Fabric admin APIs that make changes', tests: ['test/framework.test.js'], source: `${LEARN}/fabric/admin/service-admin-portal-developer` },
  { id: 'DAT-01', area: 'Data', how: ['auto'], title: "Each tenant's database accepts that tenant's identity and refuses every other tenant's", tests: ['test/signins.test.js'] },
  { id: 'DAT-02', area: 'Data', how: ['tests'], title: 'Transient database faults, such as resuming after auto-pause, are retried; writes never run twice', tests: ['test/crm.test.js'], source: `${LEARN}/fabric/database/sql/usage-reporting` },
  { id: 'DAT-03', area: 'Data', how: ['tests'], title: 'Database connection pools are bounded per tenant, and idle ones close', tests: ['test/robustness.test.js'] },
  { id: 'EMB-01', area: 'Embedding', how: ['auto'], title: "Embed tokens are generated on the server by the tenant's identity with Generate Token V2, for one report and its model, view only", tests: ['test/admin-api.test.js', 'test/standard-report.test.js'], source: `${LEARN}/power-bi/developer/embedded/generate-embed-token` },
  { id: 'EMB-02', area: 'Embedding', how: ['auto'], title: 'Embed tokens are short-lived, created with a Microsoft Entra token that outlives them, and refreshed before they expire', tests: ['test/robustness.test.js', 'test/fabric-client.test.js', 'test/mcp-and-tokens.test.js'], source: `${LEARN}/javascript/api/overview/powerbi/refresh-token` },
  { id: 'EMB-03', area: 'Embedding', how: ['tests'], title: "Only standard reports in the tenant's own workspace are embedded, and IDs from the browser are checked", tests: ['test/customer-app.test.js', 'test/standard-report.test.js', 'test/isolation.test.js'] },
  { id: 'EMB-04', area: 'Embedding', how: ['tests'], title: 'The browser gets an embed token and URL only: never a Microsoft Entra token, a secret or the token request', tests: ['test/customer-app.test.js', 'test/robustness.test.js'], source: `${LEARN}/power-bi/guidance/white-paper-powerbi-security` },
  { id: 'EMB-05', area: 'Embedding', how: ['tests'], title: 'Frames are limited to Power BI, and the Power BI client library is pinned with Subresource Integrity', tests: ['test/admin-api.test.js', 'test/robustness.test.js'] },
  { id: 'EMB-06', area: 'Embedding', how: ['tests'], title: 'Editing and creating reports are granted per person; only people who may create get a token that names the workspace (Save as, New report)', tests: ['test/personas.test.js'], source: 'https://github.com/PowerBiDevCamp/App-Owns-Data-Starter-Kit' },
  { id: 'RLS-01', area: 'Row-level security', how: ['auto'], title: "Reports read a model with row-level security, and every embed token names the viewer and their roles from the server's session", tests: ['test/personas.test.js', 'test/report.test.js'], source: `${LEARN}/power-bi/developer/embedded/embedded-row-level-security` },
  { id: 'RLS-02', area: 'Row-level security', how: ['auto'], title: 'People limited by row-level security never get a token for a model without it', tests: ['test/personas.test.js'] },
  { id: 'RLS-03', area: 'Row-level security', how: ['browser'], title: 'The rendered report shows each person only their rows, and its numbers match the database', tests: [], source: `${LEARN}/fabric/security/service-admin-row-level-security` },
  { id: 'RLS-04', area: 'Row-level security', how: ['auto'], title: "The app's own data access applies the same scope as the report", tests: ['test/personas.test.js', 'test/crm.test.js'] },
  { id: 'RLS-05', area: 'Row-level security', how: ['auto'], title: 'Direct Lake reads OneLake through a fixed-identity cloud connection with single sign-on off', tests: ['test/isolation.test.js'], source: `${LEARN}/fabric/fundamentals/direct-lake-security-integration` },
  { id: 'AI-01', area: 'AI', how: ['auto'], title: "The data agent is called at its published MCP endpoint, as the tenant's identity", tests: ['test/mcp-and-tokens.test.js'], source: `${LEARN}/fabric/data-science/data-agent-mcp-server` },
  { id: 'AI-02', area: 'AI', how: ['auto'], title: 'The agent reads the role-free model, so only people who may see every row reach it', tests: ['test/assistant.test.js', 'test/personas.test.js'] },
  { id: 'AI-03', area: 'AI', how: ['auto'], title: 'The agent answers on the tenant capacity; when it cannot, the app falls back and records why', tests: ['test/assistant.test.js'] },
  { id: 'AI-04', area: 'AI', how: ['auto'], title: 'Questions and answers are logged per tenant, bounded, and reading them is audited', tests: ['test/standard-report.test.js', 'test/assistant.test.js'], source: `${LEARN}/fabric/data-science/data-agent-purview-governance` },
  { id: 'OPS-01', area: 'Operations', how: ['tests'], title: 'Provisioning is idempotent and recovers from a failure at any step', tests: ['test/robustness.test.js', 'test/provisioner.test.js'] },
  { id: 'OPS-02', area: 'Operations', how: ['auto'], title: 'The drift audit passes for every tenant', tests: ['test/isolation.test.js'] },
  { id: 'OPS-03', area: 'Operations', how: ['tests'], title: 'Operators sign in, and every look at tenant data is recorded', tests: ['test/robustness.test.js', 'test/standard-report.test.js'] },
  { id: 'OPS-04', area: 'Operations', how: ['tests'], title: 'Rate limits apply per tenant and per user', tests: ['test/robustness.test.js'] },
  { id: 'OPS-05', area: 'Operations', how: ['auto'], title: 'Tenants run on an active capacity that supports every workload: a paid F2 or larger for data agents', tests: [], source: `${LEARN}/fabric/data-science/data-agent-mcp-server#prerequisites` },
  { id: 'OPS-06', area: 'Operations', how: ['auto'], title: 'Report use is logged per tenant: who viewed or saved what, load and render times, and the token and correlation IDs', tests: ['test/usage.test.js'], source: 'https://github.com/PowerBiDevCamp/App-Owns-Data-Starter-Kit' },
]);

// Worst first: a control's result is the worst of its findings.
const ORDER = ['fail', 'warn', 'pass', 'skip'];
const same = (a, b) => Boolean(a && b) && String(a).toLowerCase() === String(b).toLowerCase();
const short = (id) => String(id || '').slice(0, 8);
const clip = (text, max = 140) => {
  const flat = String(text || '').replace(/\s+/g, ' ').trim();
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat;
};
const reasonOf = (error) => (error?.upstreamStatus ? `HTTP ${error.upstreamStatus}` : clip(error?.message, 90));

// A refusal from Fabric, Power BI, SQL or an MCP server. A capacity refusal ("SKU Not Supported") isn't one: it comes
// after the caller was let in.
export function refused(error) {
  if (!error) return false;
  const message = String(error.message || error);
  if (/SKU Not Supported/i.test(message)) return false;
  if ([401, 403, 404].includes(error.upstreamStatus) || [401, 403, 404].includes(error.status)) return true;
  return /not authori[sz]ed|unauthori[sz]ed|forbidden|InsufficientPrivileges|PowerBINotAuthorized|could not be found|not found|Login failed|Cannot open server/i.test(message);
}

async function attempt(fn) {
  try {
    return { ok: true, value: await fn() };
  } catch (error) {
    return { ok: false, error };
  }
}

// A person with every territory and one limited to some: the tenant's own people when it has them.
export function probePeople(tenant) {
  const domain = tenant.domains?.[0] || 'example.com';
  const users = tenant.users || [];
  const manager = users.find((u) => accessOf(u).territories === null);
  const rep = users.find((u) => accessOf(u).role === 'rep' && accessOf(u).territories.length);
  return {
    manager: { email: manager?.email || `validator.manager@${domain}`, territories: null },
    rep: rep ? { email: rep.email, territories: accessOf(rep).territories } : { email: `validator.rep@${domain}`, territories: [workload.TERRITORIES[0]] },
  };
}

// IDN-06, from the tenant settings as the platform identity reads them. A service principal can read them only through
// "Service principals can access read-only admin APIs", so when every group allowed that is also allowed the admin APIs
// used for updates, the platform identity can make admin changes too. The tenants' service principals are in the groups
// of "Service principals can call Fabric public APIs", so a group shared with an admin API setting reaches them too.
export function assessTenantSettings(settings, { platformIsServicePrincipal = true } = {}) {
  const notes = [];
  const add = (status, detail) => notes.push({ status, detail });
  const find = (name) => settings.find((s) => s.settingName === name);
  const ids = (s) => (s?.enabledSecurityGroups || []).map((g) => g.graphId || g.name);
  const names = (s) => (s?.enabledSecurityGroups || []).map((g) => g.name || g.graphId).join(', ');
  for (const name of ['ServicePrincipalAccessPermissionAPIs', 'ServicePrincipalAccessGlobalAPIs']) {
    const setting = find(name);
    if (!setting) add('warn', `The tenant has no setting named ${name}.`);
    else if (!setting.enabled) add('fail', `"${setting.title}" is off, so the platform's service principals can't use Fabric.`);
    else if (!ids(setting).length) add('warn', `"${setting.title}" applies to the entire organization. Limit it to a security group holding the platform identity and every tenant's service principal.`);
    else add('pass', `"${setting.title}" applies only to ${names(setting)}.`);
  }
  const apis = find('ServicePrincipalAccessPermissionAPIs');
  const shared = (setting) => ids(setting).filter((id) => ids(apis).includes(id));
  const sharedNames = (setting) => (setting.enabledSecurityGroups || []).filter((g) => shared(setting).includes(g.graphId || g.name)).map((g) => g.name || g.graphId).join(', ');
  const read = find('AllowServicePrincipalsUseReadAdminAPIs');
  const write = find('AllowServicePrincipalsUseWriteAdminAPIs');
  if (read?.enabled) {
    if (!ids(read).length) add('warn', `"${read.title}" applies to the entire organization, so every service principal, the tenants' included, can read every workspace's users, items and metadata. Limit it to the platform identity, or turn it off.`);
    else if (shared(read).length) add('warn', `"${read.title}" applies to ${sharedNames(read)}, which "${apis.title}" uses for the service principals, so the tenants' service principals may read every workspace's users, items and metadata. Give the platform identity a group of its own.`);
    else if (platformIsServicePrincipal) add('pass', `The platform identity reads these settings through "${read.title}" (${names(read)}). It's optional: without it, check them in the admin portal.`);
  }
  if (write?.enabled) {
    const everyone = !ids(write).length;
    const platformCan = platformIsServicePrincipal && !everyone && Boolean(read?.enabled) && ids(read).length > 0 && ids(read).every((id) => ids(write).includes(id));
    if (everyone) add('warn', `"${write.title}" applies to the entire organization, so every service principal, the platform's and the tenants', can call the Fabric admin APIs that make changes, such as updating tenant settings. The platform needs none of them.`);
    if (platformCan) add('warn', `"${write.title}" applies to ${names(write)}. The platform identity reads these settings through ${names(read)}, so it can also call the Fabric admin APIs that make changes, such as updating tenant settings. It needs none: take it out of ${names(write)}, and give it a group of its own for "${read.title}" if the validator should keep reading them.`);
    if (!everyone && shared(write).length) add('warn', `"${write.title}" applies to ${sharedNames(write)}, which "${apis.title}" uses for the service principals, so the tenants' service principals may call the Fabric admin APIs that make changes.`);
    if (!everyone && !platformCan && !shared(write).length) add('pass', `"${write.title}" applies only to ${names(write)}. Keep the platform's service principals out of it.`);
  } else if (write) add('pass', `"${write.title}" is off.`);
  return notes;
}

// `browser`, when given, opens embedded reports: { exportVisual(embedConfig, visualTitle) -> { rows: [{ label, value }] } }.
// `secrets` is the store that holds the service principals' secrets.
export async function validatePlatform({ config, fabric, identities, crm, tenants, secrets = null, mode = 'live', browser = null, now = () => Date.now() }) {
  const live = mode === 'live';
  const findings = new Map(CONTROLS.map((c) => [c.id, []]));
  const note = (id, status, detail) => findings.get(id).push({ status, detail });
  const ready = tenants.filter((t) => t.status === 'ready' && t.fabric?.workspaceId);
  for (const t of tenants.filter((x) => !ready.includes(x))) note('OPS-02', 'warn', `${t.name} isn't ready (${t.status}), so it wasn't validated.`);
  const clients = new Map();
  const probes = [];
  // The capacity SKU a data agent named when it refused to run ("FT1 SKU Not Supported"), per tenant.
  const refusedSku = new Map();

  for (const tenant of ready) {
    let client;
    try {
      client = await identities.fabricFor(tenant);
      clients.set(tenant.id, client);
    } catch (error) {
      note('IDN-01', 'fail', `${tenant.name}: can't sign in as its service account: ${error.message}`);
      continue;
    }
    for (const check of [checkIdentity, checkPlatformReleased, checkAudit, checkEmbedding, checkAgent, checkQuestionLog, checkUsageLog, checkCapacity, ...(live ? [checkOwnDatabase] : [])]) {
      try {
        await check(tenant, client);
      } catch (error) {
        note('OPS-02', 'fail', `${tenant.name}: ${check.name} stopped: ${error.message}`);
      }
    }
  }
  checkDistinct();
  await checkCrossTenant();
  checkSecretStore();
  await checkTenantSettings();
  if (!live) note('DAT-01', 'skip', "The emulator keeps each tenant's data in its own SQLite database; run with --live to check SQL database in Fabric.");
  if (browser) await checkRendered();
  else note('RLS-03', 'skip', live ? 'Add --browser to open the report as each person in Microsoft Edge or Google Chrome.' : 'Needs live Power BI: run with --live --browser.');
  return summarize(findings);

  async function checkIdentity(tenant, client) {
    if (identities.usesPlatformIdentity(tenant)) {
      note('IDN-01', 'fail', `${tenant.name} runs as the shared platform identity, not its own service account.`);
      return;
    }
    const name = tenant.identity.name;
    const others = (await client.listWorkspaces()).filter((w) => !same(w.id, tenant.fabric.workspaceId));
    const own = (await client.listRoleAssignments(tenant.fabric.workspaceId)).find((r) => same(r.principal?.id, tenant.identity.objectId));
    if (others.length) note('IDN-01', 'fail', `${name} can see ${others.length} other workspace(s): ${others.map((w) => w.displayName || short(w.id)).join(', ')}.`);
    else if (own?.role !== 'Admin') note('IDN-01', 'fail', `${name} is ${own?.role || 'not a member'} of ${tenant.name}'s workspace; it needs Admin.`);
    else note('IDN-01', 'pass', `${name} sees one workspace, ${tenant.name}'s, and is its Admin.`);
  }

  async function checkPlatformReleased(tenant) {
    if (config.platformWorkspaceAccess !== 'release') {
      note('IDN-02', 'warn', `PLATFORM_WORKSPACE_ACCESS=${config.platformWorkspaceAccess}: the platform identity stays Admin of ${tenant.name}'s workspace.`);
      return;
    }
    const opened = await attempt(() => fabric.getWorkspace(tenant.fabric.workspaceId));
    if (opened.ok) note('IDN-02', 'fail', `The platform identity can still open ${tenant.name}'s workspace. A removed role can take about an hour to stop working; check again later.`);
    else if (refused(opened.error)) note('IDN-02', 'pass', `The platform identity is refused at ${tenant.name}'s workspace (${reasonOf(opened.error)}).`);
    else note('IDN-02', 'warn', `${tenant.name}: inconclusive: ${reasonOf(opened.error)}`);
  }

  async function checkAudit(tenant) {
    const report = await auditTenant({ tenant, fabric, identities, config, now });
    const checks = report.checks || [];
    const map = (key, id) => {
      for (const c of checks.filter((x) => x.key === key)) note(id, c.status === 'info' ? 'pass' : c.status, `${tenant.name}: ${c.detail}`);
    };
    map('model-connection', 'RLS-05');
    map('role:workspace', 'IDN-03');
    map('service-account', 'IDN-05');
    const people = checks.filter((c) => c.key.startsWith('role:other:'));
    if (people.length) for (const c of people) note('IDN-04', 'warn', `${tenant.name}: ${c.detail}`);
    else note('IDN-04', 'pass', `${tenant.name}: no one else has a role in the workspace.`);
    const failing = checks.filter((c) => c.status === 'fail');
    const count = (status) => checks.filter((c) => c.status === status).length;
    if (failing.length) note('OPS-02', 'fail', `${tenant.name}: the audit fails ${failing.map((c) => c.title).join(', ')}.`);
    else note('OPS-02', 'pass', `${tenant.name}: audit ${count('pass')} pass, ${count('warn')} to review, 0 failing.`);
  }

  async function checkEmbedding(tenant, client) {
    const f = tenant.fabric;
    if (!f.semanticModelId) {
      note('EMB-01', 'skip', `${tenant.name}'s edition has no reports.`);
      return;
    }
    const listing = await listReporting({ fabric: client, tenant });
    const report = listing.reports.find((r) => isStandardReport(tenant, r));
    if (!report) {
      note('EMB-01', 'fail', `${tenant.name} has no standard report to embed.`);
      return;
    }
    const datasets = await client.pbiListDatasets(f.workspaceId);
    const model = datasets.find((d) => same(d.id, report.datasetId));
    const twin = datasets.find((d) => same(d.id, f.assistantModelId));
    if (!model || !same(model.id, f.semanticModelId)) note('RLS-01', 'fail', `${tenant.name}'s "${report.name}" reads ${model?.name || short(report.datasetId)}, not the model with row-level security.`);
    else if (!model.isEffectiveIdentityRequired) note('RLS-01', 'fail', `${model.name} has no row-level security roles: Power BI doesn't ask who is viewing.`);
    else note('RLS-01', 'pass', `${tenant.name}: "${report.name}" reads ${model.name}, which requires the viewer's identity and roles.`);
    if (twin) {
      const exposed = listing.reports.filter((r) => isStandardReport(tenant, r) && same(r.datasetId, twin.id));
      if (exposed.length) note('RLS-02', 'fail', `${tenant.name}: "${exposed[0].name}" reads ${twin.name}, the model without row-level security.`);
      else note('RLS-02', 'pass', `${tenant.name}: no standard report reads ${twin.name}, the model without row-level security.`);
    }

    const people = probePeople(tenant);
    const embeds = {};
    for (const [kind, person] of Object.entries(people)) {
      const identity = { username: person.email, roles: workload.rolesFor(person.territories), limited: person.territories !== null };
      const started = now();
      const embed = await createEmbedConfig({
        fabric: client,
        tenant,
        mode: 'view',
        reportId: report.id,
        lifetimeMinutes: config.embedTokenMinutes,
        identity,
        datasetIds: [f.semanticModelId],
        allowReport: (r) => isStandardReport(tenant, r),
      });
      const request = embed.tokenRequest;
      const scoped =
        request.reports?.length === 1 && same(request.reports[0].id, report.id) && !request.reports[0].allowEdit && request.datasets?.length === 1 && same(request.datasets[0].id, f.semanticModelId) && !request.targetWorkspaces;
      const by = identities.usesPlatformIdentity(tenant) ? 'the platform identity' : tenant.identity.name;
      note('EMB-01', scoped ? 'pass' : 'fail', `${tenant.name}, ${kind}: ${scoped ? `${by} got a token for "${report.name}" and its model only, view only` : `the token request covers more than one report and its model`}.`);

      const given = request.identities?.[0];
      const named = given && given.username === person.email && JSON.stringify(given.roles) === JSON.stringify(identity.roles) && given.datasets?.some((d) => same(d, f.semanticModelId));
      note('RLS-01', named ? 'pass' : 'fail', `${tenant.name}, ${kind} ${person.email}: ${named ? `effective identity with role ${given.roles.join(' + ')}` : 'the token request has no matching effective identity'}.`);

      const minutes = (Date.parse(embed.expiration) - started) / 60_000;
      const asked = request.lifetimeInMinutes;
      if (!(asked <= 60) || minutes > asked + 1) note('EMB-02', 'fail', `${tenant.name}, ${kind}: the token lasts ${Math.round(minutes)} minutes; ${asked} were asked for.`);
      else if (minutes < asked - 2) note('EMB-02', 'warn', `${tenant.name}, ${kind}: Power BI issued a ${Math.round(minutes)}-minute token instead of ${asked}: the Microsoft Entra token used had less time left.`);
      else note('EMB-02', 'pass', `${tenant.name}, ${kind}: ${asked}-minute token (expires ${embed.expiration.slice(11, 16)} UTC).`);
      embeds[kind] = { person, embed };
    }
    await checkScopedData(tenant, embeds);
  }

  async function checkScopedData(tenant, embeds) {
    const repo = await crm.forTenant(tenant);
    for (const [kind, { person, embed }] of Object.entries(embeds)) {
      const answer = await repo.scoped(person.territories).quickAnswer(workload.RLS_PROBE.question);
      const rows = answer?.rows || [];
      const labels = rows.map((r) => r.label);
      if (person.territories) {
        const outside = labels.filter((l) => !person.territories.includes(l));
        note('RLS-04', outside.length ? 'fail' : 'pass', `${tenant.name}, ${kind} (${person.territories.join(', ')}): ${outside.length ? `also sees ${outside.join(', ')}` : `sees ${labels.join(', ') || 'no rows'}`}.`);
      } else {
        note('RLS-04', labels.length ? 'pass' : 'warn', `${tenant.name}, ${kind} (every territory): sees ${labels.join(', ') || 'no rows'}.`);
      }
      probes.push({ tenant, kind, person, embed, rows });
    }
  }

  async function checkAgent(tenant, client) {
    const f = tenant.fabric;
    if (!f.dataAgentId) {
      note('AI-01', 'skip', `${tenant.name}'s edition has no data agent.`);
      return;
    }
    const definition = await attempt(() => client.getItemDefinition(f.workspaceId, f.dataAgentId));
    if (!definition.ok) note('AI-02', 'fail', `${tenant.name}: can't read the agent's definition: ${reasonOf(definition.error)}`);
    else {
      const source = agentModelSource(definition.value?.definition);
      if (!source) note('AI-02', 'fail', `${tenant.name}: the agent isn't published with a semantic model as its source.`);
      else if (same(source.artifactId, f.semanticModelId)) note('AI-02', 'fail', `${tenant.name}: the agent reads the model with row-level security, which a service principal can't query as a person.`);
      else if (!same(source.artifactId, f.assistantModelId)) note('AI-02', 'warn', `${tenant.name}: the agent reads ${source.display_name || short(source.artifactId)}, not the platform's role-free model.`);
      else note('AI-02', 'pass', `${tenant.name}: the published agent reads ${source.display_name || 'the role-free model'}.`);
    }
    const limited = (tenant.questions || []).filter((q) => q.scope && q.scope !== 'All territories');
    const leaked = limited.filter((q) => q.answeredBy === 'data agent');
    if (leaked.length) note('AI-02', 'fail', `${tenant.name}: ${leaked.length} question(s) from people limited to territories were answered by the agent.`);
    else note('AI-02', 'pass', `${tenant.name}: none of the ${limited.length} logged question(s) from people limited to territories reached the agent.`);

    const url = dataAgentMcpUrl(config.endpoints.fabric, f.workspaceId, f.dataAgentId);
    const documented = /\/v1\/mcp\/workspaces\/[0-9a-f-]{36}\/dataagents\/[0-9a-f-]{36}\/agent$/i.test(url);
    const who = identities.usesPlatformIdentity(tenant) ? 'the platform identity' : tenant.identity.name;
    const started = now();
    const asked = await attempt(() => client.askDataAgent(f.workspaceId, f.dataAgentId, workload.AGENT_PROBE_QUESTION));
    const seconds = Math.round((now() - started) / 1000);
    if (!documented) note('AI-01', 'fail', `${tenant.name}: ${url} isn't the documented MCP endpoint format.`);
    if (asked.ok) {
      if (documented) note('AI-01', 'pass', `${tenant.name}: ${url} answered as ${who} in ${seconds} s.`);
      note('AI-03', 'pass', `${tenant.name}: "${clip(asked.value.answer, 110)}"`);
      return;
    }
    const message = String(asked.error.message || asked.error);
    if (/SKU Not Supported/i.test(message)) {
      refusedSku.set(tenant.id, /(\w+) SKU Not Supported/i.exec(message)?.[1] || null);
      if (documented) note('AI-01', 'pass', `${tenant.name}: ${url} reached the published agent as ${who}, and the capacity refused to run it.`);
      note('AI-03', 'fail', `${tenant.name}: ${clip(message, 90)}. Data agents need a paid F2 or larger capacity (or P1 with Fabric); until then the app gives quick answers.`);
    } else if (/could not be found|-32601/i.test(message)) note('AI-01', 'fail', `${tenant.name}: the endpoint doesn't know the agent. Is it published? ${clip(message, 90)}`);
    else if (refused(asked.error)) note('AI-01', 'fail', `${tenant.name}: its own service account is refused by its agent: ${clip(message, 90)}`);
    else note('AI-03', 'fail', `${tenant.name}: ${clip(message, 120)}`);
  }

  function checkQuestionLog(tenant) {
    const log = tenant.questions || [];
    const answered = log.filter((q) => 'answer' in q).length;
    note('AI-04', log.length <= QUESTION_LOG_SIZE ? 'pass' : 'fail', `${tenant.name}: ${log.length} question(s) logged (at most ${QUESTION_LOG_SIZE}), ${answered} with their answers.`);
  }

  // The usage log is the tenant's own: bounded, and naming only people on its sign-in domains.
  function checkUsageLog(tenant) {
    const log = tenant.reportUsage || [];
    const foreign = log.filter((u) => !(tenant.domains || []).includes(emailDomain(u.email)));
    const views = log.filter((u) => u.event === 'view');
    if (log.length > USAGE_LOG_SIZE) note('OPS-06', 'fail', `${tenant.name}: ${log.length} usage entries; the log keeps at most ${USAGE_LOG_SIZE}.`);
    else if (foreign.length) note('OPS-06', 'fail', `${tenant.name}: ${foreign.length} usage entries name people outside its sign-in domains.`);
    else if (!log.length) note('OPS-06', 'skip', `${tenant.name}: nobody has opened a report since the usage log started.`);
    else {
      const timed = views.filter((u) => Number.isFinite(u.renderMs)).length;
      const traced = views.filter((u) => u.tokenId && u.correlationId).length;
      note('OPS-06', 'pass', `${tenant.name}: ${log.length} entries (at most ${USAGE_LOG_SIZE}): ${views.length} views, ${timed} with load and render times, ${traced} with token and correlation IDs.`);
    }
  }

  // Microsoft's App-Owns-Data Starter Kit limits the service principal settings to one security group ("Power BI
  // Apps"), so no other app in the tenant can use the Fabric APIs as a service principal.
  async function checkTenantSettings() {
    if (typeof fabric.listTenantSettings !== 'function') {
      note('IDN-06', 'skip', "This platform can't read tenant settings.");
      return;
    }
    const listed = await attempt(() => fabric.listTenantSettings());
    if (!listed.ok) {
      note('IDN-06', 'skip', `The platform identity can't read the tenant settings (${reasonOf(listed.error)}). Check them in the Fabric admin portal, or allow it the read-only admin APIs.`);
      return;
    }
    for (const { status, detail } of assessTenantSettings(listed.value, { platformIsServicePrincipal: config.authMode !== 'cli' })) note('IDN-06', status, detail);
  }

  async function checkCapacity(tenant, client) {
    const workspace = await client.getWorkspace(tenant.fabric.workspaceId);
    let capacity = null;
    for (const source of [fabric, client]) {
      const list = await attempt(() => source.listCapacities());
      capacity = list.ok ? list.value.find((c) => same(c.id, workspace.capacityId)) : null;
      if (capacity) break;
    }
    if (!workspace.capacityId) note('OPS-05', 'fail', `${tenant.name}'s workspace has no capacity.`);
    else if (!capacity && refusedSku.get(tenant.id)) {
      const sku = refusedSku.get(tenant.id);
      note('OPS-05', 'warn', `${tenant.name}: capacity ${short(workspace.capacityId)} isn't visible to the platform identity, but the data agent named its SKU, ${sku}${/^FT/i.test(sku) ? ': a trial, fine for development. Production needs a paid F SKU, and data agents need F2 or larger' : ''}.`);
    } else if (!capacity) note('OPS-05', 'warn', `${tenant.name}: capacity ${short(workspace.capacityId)} isn't visible to the platform identity, so its SKU is unknown.`);
    else {
      const sku = String(capacity.sku || '');
      const label = `${capacity.displayName} (${sku})`;
      if (capacity.state && capacity.state !== 'Active') note('OPS-05', 'fail', `${tenant.name}: ${label} is ${capacity.state}.`);
      else if (/^FT/i.test(sku)) note('OPS-05', 'warn', `${tenant.name}: ${label} is a trial: fine for development. Production needs a paid F SKU, and data agents need F2 or larger.`);
      else if (/^(PP|A|EM)\d/i.test(sku)) note('OPS-05', 'fail', `${tenant.name}: ${label} can't host Fabric items such as the SQL database and the data agent.`);
      else note('OPS-05', 'pass', `${tenant.name}: ${label}, active.`);
    }
  }

  async function checkOwnDatabase(tenant) {
    const db = tenant.fabric.crm;
    if (!db?.server) {
      note('DAT-01', 'skip', `${tenant.name} has no SQL database.`);
      return;
    }
    const result = await query(tenant, db);
    if (result.ok) note('DAT-01', 'pass', `${tenant.name}: its own identity reads its database (${result.value} accounts).`);
    else note('DAT-01', 'fail', `${tenant.name}: its own identity can't read its database: ${reasonOf(result.error)}`);
  }

  // Reads the tenant database `db` signed in as `as`. Failures come back rather than throw.
  async function query(as, db, { retry = true } = {}) {
    let store;
    return attempt(async () => {
      const tokens = await identities.tokensFor(as);
      store = await workload.createFabricSqlStore({ server: db.server, database: db.database, tokens, poolMax: 1, ...(retry ? {} : { retryDelaysMs: [] }) });
      const [row] = await store.query('SELECT COUNT(*) AS n FROM accounts');
      return Number(row?.n);
    }).finally(() => store?.close().catch(() => {}));
  }

  function checkSecretStore() {
    const kind = secrets?.kind;
    if (kind === 'keyvault') note('IDN-05', 'pass', 'Stored credentials are in Azure Key Vault.');
    else if (kind === 'file') note('IDN-05', 'pass', 'Stored credentials are encrypted at rest (AES-256-GCM, keyed by SECRETS_KEY, which is asked for at start or comes from the environment, never from the data folder). Production uses Key Vault.');
    else if (kind === 'memory') note('IDN-05', live ? 'fail' : 'pass', live ? 'Credentials are only in memory: they are lost when the server restarts.' : 'The emulator keeps credentials in memory.');
    else note('IDN-05', 'warn', "The credential store wasn't given to the validator, so where credentials are kept wasn't checked.");
    // The platform identity's own credential. Microsoft recommends certificates over secrets; federated needs neither.
    const own = config.credential?.type;
    if (own === 'federated' || own === 'certificate') note('IDN-05', 'pass', `The platform identity signs in with a ${own === 'federated' ? 'federated credential (managed identity)' : `certificate valid until ${config.credential.notAfter.slice(0, 10)}`}.`);
    else if (own === 'secret') note('IDN-05', 'warn', 'The platform identity signs in with a client secret. Use a certificate (AZURE_CLIENT_CERTIFICATE_PATH) or a federated credential (MANAGED_IDENTITY_CLIENT_ID); production refuses secrets.');
  }

  function checkDistinct() {
    if (ready.length < 2) {
      note('ISO-01', 'warn', 'Only one tenant is ready: isolation needs at least two to compare.');
      return;
    }
    const parts = [
      ['workspace', (t) => t.fabric.workspaceId],
      ['database', (t) => t.fabric.crmDatabaseId],
      ['reports model', (t) => t.fabric.semanticModelId],
      ['agent model', (t) => t.fabric.assistantModelId],
      ['standard report', (t) => t.fabric.starterReportId],
      ['data agent', (t) => t.fabric.dataAgentId],
      ['connection', (t) => t.fabric.modelConnectionId],
      ['service principal', (t) => t.identity?.appId],
      ['workspace identity', (t) => t.fabric.workspaceIdentity?.servicePrincipalId],
    ];
    const shared = [];
    for (const [label, value] of parts) {
      const owners = new Map();
      for (const t of ready) {
        const v = value(t);
        if (!v) continue;
        const key = String(v).toLowerCase();
        if (owners.has(key)) shared.push(`${label} ${short(v)} (${owners.get(key)} and ${t.name})`);
        else owners.set(key, t.name);
      }
    }
    if (shared.length) note('ISO-01', 'fail', `Shared between tenants: ${shared.join('; ')}.`);
    else note('ISO-01', 'pass', `${ready.map((t) => t.name).join(', ')}: each has its own ${parts.map(([label]) => label).join(', ')}.`);
  }

  async function checkCrossTenant() {
    if (ready.length < 2) {
      note('ISO-02', 'warn', 'Only one tenant is ready: there is no other tenant to try.');
      return;
    }
    for (const a of ready) {
      const client = clients.get(a.id);
      if (!client) continue;
      for (const b of ready.filter((t) => t !== a)) {
        const theirs = b.fabric;
        const tries = [
          ['open its workspace', () => client.getWorkspace(theirs.workspaceId)],
          ['list its items', () => client.listItems(theirs.workspaceId)],
          ['list its semantic models', () => client.pbiListDatasets(theirs.workspaceId)],
          ...(theirs.starterReportId ? [['get an embed token for its report', () => client.pbiGenerateToken({ reports: [{ id: theirs.starterReportId }], datasets: [{ id: theirs.semanticModelId }], lifetimeInMinutes: 5 })]] : []),
          ...(theirs.dataAgentId ? [['ask its data agent', () => client.askDataAgent(theirs.workspaceId, theirs.dataAgentId, 'How many accounts are there?')]] : []),
        ];
        const leaks = [];
        const unclear = [];
        for (const [what, fn] of tries) {
          const result = await attempt(fn);
          if (result.ok) leaks.push(what);
          else if (!refused(result.error)) unclear.push(`${what}: ${reasonOf(result.error)}`);
        }
        if (leaks.length) note('ISO-02', 'fail', `${a.name}'s identity could ${leaks.join(', ')} of ${b.name}.`);
        else if (unclear.length) note('ISO-02', 'warn', `${a.name} → ${b.name}: not clearly refused: ${unclear.join('; ')}.`);
        else note('ISO-02', 'pass', `${a.name}'s identity is refused at ${b.name}'s ${tries.map(([what]) => what.replace(/^(open|list|get|ask) (its |an )?/, '')).join(', ')}.`);

        if (live && theirs.crm?.server) {
          const result = await query(a, theirs.crm, { retry: false });
          if (result.ok) note('DAT-01', 'fail', `${a.name}'s identity can read ${b.name}'s database.`);
          else if (refused(result.error)) note('DAT-01', 'pass', `${a.name}'s identity is refused by ${b.name}'s database (${reasonOf(result.error)}).`);
          else note('DAT-01', 'warn', `${a.name} → ${b.name}'s database: inconclusive: ${reasonOf(result.error)}`);
        }
      }
    }
  }

  async function checkRendered() {
    const widen = workload.RLS_PROBE.column ? { ...workload.RLS_PROBE.column, values: [...workload.TERRITORIES] } : null;
    for (const probe of probes) {
      const who = `${probe.tenant.name}, ${probe.kind} ${probe.person.email}`;
      const shown = await attempt(() => browser.exportVisual(probe.embed, workload.RLS_PROBE.visual, { widen }));
      if (!shown.ok) {
        note('RLS-03', 'fail', `${who}: "${workload.RLS_PROBE.visual}" didn't render: ${reasonOf(shown.error)}`);
        continue;
      }
      const rows = shown.value.rows;
      const labels = rows.map((r) => r.label);
      const allowed = probe.person.territories;
      const outside = allowed ? labels.filter((l) => !allowed.includes(l)) : [];
      const expected = new Map(probe.rows.map((r) => [r.label, Number(r.value)]));
      const differ = rows.filter((r) => !expected.has(r.label) || Math.abs(expected.get(r.label) - r.value) > 0.5).map((r) => r.label);
      const missing = [...expected.keys()].filter((l) => !labels.includes(l));
      const listing = rows.map((r) => `${r.label} ${r.value}`).join(', ') || 'no rows';
      // A report filter for every territory: the same rows as before, or row-level security is only a filter.
      const widened = shown.value.widenedRows || null;
      const widenedOutside = widened && allowed ? widened.map((r) => r.label).filter((l) => !allowed.includes(l)) : [];
      const widenedNote = widened ? ` A report filter for every ${widen.column.toLowerCase()} still shows ${widened.map((r) => r.label).join(', ') || 'nothing more'}.` : '';
      if (outside.length) note('RLS-03', 'fail', `${who}: the report shows ${outside.join(', ')}, outside ${allowed.join(', ')}.`);
      else if (widenedOutside.length) note('RLS-03', 'fail', `${who}: a report filter for every ${widen.column.toLowerCase()} shows ${widenedOutside.join(', ')}, outside ${allowed.join(', ')}.`);
      else if (differ.length || missing.length) note('RLS-03', 'warn', `${who}: shows ${listing}; the database differs for ${[...differ, ...missing].join(', ')} (the model may not have picked up recent changes yet).`);
      else note('RLS-03', 'pass', `${who}: shows ${listing}, as the database does.${widenedNote}`);
    }
    if (!probes.length) note('RLS-03', 'skip', 'No report to open.');
  }
}

export function summarize(findings) {
  return CONTROLS.map((control) => {
    const details = findings.get(control.id) || [];
    const status = details.length ? ORDER.find((s) => details.some((d) => d.status === s)) : control.how.includes('tests') ? 'tests' : 'skip';
    return { ...control, status, details };
  });
}

export function countResults(results) {
  const counts = { pass: 0, warn: 0, fail: 0, skip: 0, tests: 0 };
  for (const r of results) counts[r.status] += 1;
  return counts;
}

const LABEL = { pass: 'PASS', warn: 'WARN', fail: 'FAIL', skip: 'SKIP', tests: 'TESTS' };

export function formatScorecard(results, { heading }) {
  const lines = [heading, ''];
  let area = null;
  for (const r of results) {
    if (r.area !== area) {
      area = r.area;
      lines.push(area);
    }
    lines.push(`  ${r.id.padEnd(7)}${LABEL[r.status].padEnd(7)}${r.title}`);
    for (const d of r.details) lines.push(`${' '.repeat(16)}${d.status === r.status ? '' : `[${d.status}] `}${d.detail}`);
    if (r.status === 'tests') lines.push(`${' '.repeat(16)}Verified by npm test: ${r.tests.join(', ')}`);
  }
  const c = countResults(results);
  lines.push('', `${c.pass} pass, ${c.warn} to review, ${c.fail} failing, ${c.skip} skipped; ${c.tests} verified by the automated tests (npm test).`);
  return lines.join('\n');
}

export function toMarkdown(results, { heading }) {
  const cell = (text) => String(text).replace(/\|/g, '\\|');
  const rows = results.map((r) => {
    const evidence = r.status === 'tests' ? `npm test: ${r.tests.map((t) => `\`${t.replace('test/', '')}\``).join(', ')}` : r.details.map((d) => cell(d.detail)).join('<br>');
    return `| ${r.id} | ${cell(r.title)} | **${LABEL[r.status]}** | ${evidence} |`;
  });
  const c = countResults(results);
  return [`### ${heading}`, '', '| Control | Requirement | Result | Evidence |', '| --- | --- | --- | --- |', ...rows, '', `${c.pass} pass, ${c.warn} to review, ${c.fail} failing, ${c.skip} skipped; ${c.tests} verified by the automated tests.`, ''].join('\n');
}

// Two tenants built in the Fabric emulator with the production settings: their own service accounts, and the platform
// identity released. Nothing leaves the machine.
export async function createEmulatedPlatform({ names = ['Fabrikam', 'Contoso'], env = {} } = {}) {
  const config = loadConfig({ FABRIC_AUTH_MODE: 'mock', DATA_DIR: 'unused', TENANT_IDENTITY_MODE: 'required', PLATFORM_WORKSPACE_ACCESS: 'release', ...env });
  const fabric = createMockFabric();
  const store = createTenantStore();
  const secrets = createMemorySecretStore();
  const identities = createIdentityBroker({ config, platformTokens: null, platformFabric: fabric, secrets });
  const crm = workload.createCrmService({ fabric, identities });
  const provisioner = createProvisioner({ fabric, store, config, identities, crm, waitMs: 0, refreshPollMs: 0, capacityPollMs: 0 });
  for (const name of names) {
    const tenant = newTenantRecord({ name, plan: 'enterprise', domains: [`${name.toLowerCase()}.com`] });
    await store.save(tenant);
    const done = await provisioner.provision(tenant.id);
    if (done.status !== 'ready') throw new Error(`${name} is ${done.status}: ${done.error}`);
  }
  // A question from each kind of person, so the question log has entries to check.
  const assistant = createAssistant({ store, identities, crm, mock: true });
  for (const tenant of store.list()) {
    const people = probePeople(tenant);
    for (const person of Object.values(people)) await assistant.ask(tenant, workload.RLS_PROBE.question, { email: person.email, territories: person.territories });
  }
  // A browser opening the standard report as each of them, so the usage log has entries too. No browser here, so no
  // load or render times.
  for (const tenant of store.list()) {
    const client = await identities.fabricFor(tenant);
    for (const person of Object.values(probePeople(tenant))) {
      const identity = { username: person.email, roles: workload.rolesFor(person.territories), limited: person.territories !== null };
      const embed = await createEmbedConfig({ fabric: client, tenant, mode: 'view', reportId: tenant.fabric.starterReportId, identity, datasetIds: [tenant.fabric.semanticModelId] });
      const scope = person.territories ? person.territories.join(', ') : 'All territories';
      recordUsage(tenant, usageEntry({ event: 'view', reportId: embed.reportId, reportName: embed.name, correlationId: randomUUID(), tokenId: embed.tokenId }, { email: person.email, scope, rights: { edit: false, create: false } }));
    }
    await store.save(tenant);
  }
  return { config, fabric, identities, crm, store, secrets, tenants: store.list(), mode: 'emulator', close: () => crm.closeAll() };
}

// This deployment: the tenant registry in DATA_DIR and live Fabric, signed in as configured. Read-only.
export function createLivePlatform(env = process.env) {
  const config = loadConfig(env);
  if (config.authMode === 'mock') throw new Error('--live needs FABRIC_AUTH_MODE=sp or cli, as for the server.');
  const tokens = createTokenProvider(config);
  const fabric = createFabricClient({ tokens, endpoints: config.endpoints });
  const secrets = createSecretStore(config, { tokens });
  const identities = createIdentityBroker({ config, platformTokens: tokens, platformFabric: fabric, secrets });
  const crm = workload.createCrmService({ fabric, identities });
  const store = createTenantStore({ file: path.join(config.dataDir, 'tenants.json') });
  return { config, fabric, identities, crm, store, secrets, tenants: store.list(), mode: 'live', close: () => crm.closeAll() };
}
