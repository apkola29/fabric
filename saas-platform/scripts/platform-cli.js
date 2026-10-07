#!/usr/bin/env node
// Command-line back office: the same operations as /admin, for scripting and for checking a live tenant.
// Usage: node scripts/platform-cli.js --help

import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { parseArgs } from 'node:util';
import { PromptCancelled, askForSecrets } from '../src/auth/runtime-secrets.js';
import { createTokenProvider } from '../src/auth/tokens.js';
import { isGuid, loadConfig } from '../src/config.js';
import { createCrmService } from '../src/crm/index.js';
import { MODEL_NAME, buildSemanticModelDefinition, rolesFor } from '../src/crm/model.js';
import { TERRITORIES } from '../src/crm/schema.js';
import { sampleSeedOf } from '../src/crm/seed.js';
import { createFabricClient, dataAgentMcpUrl } from '../src/fabric/client.js';
import { createMockFabric } from '../src/fabric/mock.js';
import { syncDataAgent } from '../src/platform/agent.js';
import { createAssistant } from '../src/platform/assistant.js';
import { auditTenant } from '../src/platform/audit.js';
import { brandOf, parseColor, setLogo } from '../src/platform/branding.js';
import { createIdentityBroker } from '../src/platform/identities.js';
import { importFromWeb, ingestBytes, refreshAgentAfterLoad } from '../src/platform/ingest.js';
import { ADDONS, entitlements, getPlan, listPlans } from '../src/platform/plans.js';
import { createProvisioner } from '../src/platform/provisioner.js';
import { createEmbedConfig, listReporting } from '../src/platform/reporting.js';
import { createSecretStore } from '../src/platform/secrets.js';
import { parseDomains } from '../src/platform/sessions.js';
import { addActivity, createTenantStore, newTenantRecord } from '../src/platform/store.js';
import { signInUrl, uniqueSubdomain } from '../src/platform/tenancy.js';
import { summarizeUsage } from '../src/platform/usage.js';
import { ROLES, accessOf, addUser, findUser, publicUser, removeUser, resetPassword, updateUser, usersOf } from '../src/platform/users.js';

const HELP = `Usage: node scripts/platform-cli.js <command> [arguments]

Customers
  list                                      Customers, editions and status
  add <name> [--plan id] [--addon id] [--domain d] [--workspace id] [--capacity id] [--no-sample-data]
                                            Add a customer and provision it. --domain: email domain its users sign in with
                                            (repeatable); --workspace adopts a workspace an admin created; --capacity puts
                                            it on a dedicated Fabric capacity
  domains <customer> <domain...>            Set the sign-in email domains
  brand <customer> [--logo file] [--color #RRGGBB] [--no-logo]
                                            Set the logo (SVG, PNG, JPEG or WebP, 64 KB at most) and accent color that
                                            the customer's sign-in page and app show
  edition <customer> <edition>              Change the edition, then provision
  addons <customer> [addon...]              Set the add-ons (none to remove all), then provision
  capacity <customer> [capacity-id]         Move to a dedicated capacity (none: back to the default), then provision
  provision <customer>                      Run provisioning again (idempotent)
  status <customer>                         Steps, service account, Fabric IDs and recent activity
  remove <customer> [--keep-workspace]      Remove the customer, its workspace, connection and service account

Service accounts (one per customer, Admin of that customer's workspace only)
  identity <customer>                       Show the customer's service account and how it signs in
  identity-register <customer> --app-id <guid> --object-id <guid> (--certificate-file <pem> | --federated | --secret-env <VAR>)
           [--display-name <name>]
                                            Register an account an Entra admin created (scripts/bootstrap-identities.ps1).
                                            --certificate-file: a PEM with the private key, kept encrypted (recommended);
                                            --federated: the app trusts the platform's managed identity (nothing stored);
                                            --secret-env: a client secret in an environment variable (development);
                                            --display-name: the app registration's name in Entra ID
  identity-rotate <customer>                New certificate or secret for an account the platform created

Sign-ins for the customer's people (once a customer has any, only they can sign in)
  users <customer>                          List the sign-ins with their role and territories
  user-add <customer> <email> --role manager|rep [--territory T]... [--name "Full Name"] [--password-env VAR]
           [--reports view|edit|create|edit,create]
                                            Add a sign-in. Managers see every territory; reps see the territories named
                                            (${TERRITORIES.join(', ')}). Everyone may view reports; --reports also lets
                                            them edit reports and create new ones, where report authoring is on.
                                            Without --password-env a password is generated and shown once
  user-access <customer> <email> [--role manager|rep] [--territory T]... [--reports view|edit|create|edit,create]
                                            Change the role, territories or report permissions; the person's sessions end
  user-reset <customer> <email> [--password-env VAR]
                                            New password; the person's sessions end
  user-remove <customer> <email>            Remove a sign-in; the person's sessions end

Checks
  audit <customer>                          Least-privilege and drift check: workspace roles, items, the model's
                                            connection, capacity and schema (read-only; exits 1 when something fails)
  items <customer>                          Items in the customer's workspace
  crm <customer>                            CRM row counts and headline numbers (read as the customer's account)
  reseed <customer> --confirm               Delete every CRM record and load the sample data again (demo customers only)
  model <customer>                          Semantic model version, connection binding and recent refreshes
  reports <customer>                        Reports and semantic models
  embed <customer> [report] [--mode view|edit|create] [--territory T]...
                                            Request an embed token as a manager, or as a rep for the territories named
                                            (prints the request, never the token)
  ask <customer> <question> [--territory T]...
                                            Ask the assistant as a manager (data agent, then quick answers), or as a
                                            rep for the territories named (quick answers)
  questions <customer> [--limit n] [--full] What people asked the assistant and what they were told, who answered (the
                                            data agent or a quick answer) and why the agent wasn't used when it wasn't
  usage <customer> [--limit n]              Who opened and saved which reports, and how long they took to load and
                                            render, per report and per view (with the correlation IDs)

Data integration add-on
  upload <customer> <file> [--table name] [--mode Overwrite|Append]
  import-web <customer> <url> [--table name]
  sync-agent <customer>                     Add new lakehouse tables to the assistant

Options: --fabric-header name=value adds a header to Fabric API calls (repeatable).
<customer> is a name or ID. Editions: ${listPlans().map((p) => p.id).join(', ')}. Add-ons: ${Object.keys(ADDONS).join(', ')}.`;

const { values: options, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    plan: { type: 'string', default: 'enterprise' },
    addon: { type: 'string', multiple: true },
    domain: { type: 'string', multiple: true },
    workspace: { type: 'string' },
    capacity: { type: 'string' },
    'no-sample-data': { type: 'boolean', default: false },
    table: { type: 'string' },
    mode: { type: 'string' },
    'keep-workspace': { type: 'boolean', default: false },
    'app-id': { type: 'string' },
    'object-id': { type: 'string' },
    'secret-env': { type: 'string' },
    'certificate-file': { type: 'string' },
    'display-name': { type: 'string' },
    federated: { type: 'boolean', default: false },
    name: { type: 'string' },
    'password-env': { type: 'string' },
    role: { type: 'string' },
    territory: { type: 'string', multiple: true },
    reports: { type: 'string' },
    confirm: { type: 'boolean', default: false },
    logo: { type: 'string' },
    color: { type: 'string' },
    'no-logo': { type: 'boolean', default: false },
    limit: { type: 'string' },
    full: { type: 'boolean', default: false },
    'fabric-header': { type: 'string', multiple: true },
    help: { type: 'boolean', short: 'h' },
  },
});
const [command, ...args] = positionals;
if (!command || options.help) {
  console.log(HELP);
  process.exit(0);
}

const fabricHeaders = Object.fromEntries((options['fabric-header'] || []).map((h) => [h.slice(0, h.indexOf('=')), h.slice(h.indexOf('=') + 1)]));
// Credentials are asked for here (or come from the environment), never from a file in the project.
let config;
try {
  config = loadConfig(await askForSecrets(process.env, { purpose: 'cli' }));
} catch (error) {
  console.error(error instanceof PromptCancelled ? 'Cancelled.' : error.message);
  process.exit(1);
}
const mock = config.authMode === 'mock';
const tokens = mock ? null : createTokenProvider(config);
const fabric = mock
  ? createMockFabric({ stateFile: path.join(config.dataDir, 'mock-fabric.json') })
  : createFabricClient({ tokens, endpoints: config.endpoints, fabricHeaders });
const store = createTenantStore({ file: path.join(config.dataDir, mock ? 'tenants.mock.json' : 'tenants.json') });
const secrets = createSecretStore(config, { tokens });
const identities = createIdentityBroker({ config, platformTokens: tokens, platformFabric: fabric, secrets, clientOptions: { fabricHeaders } });
const crm = createCrmService({ fabric, identities, sqliteDir: mock ? config.dataDir : null, ...config.crmPools });
const assistant = createAssistant({ store, identities, crm, mock });
const provisioner = createProvisioner({ fabric, store, config, identities, crm });
const scoped = (tenant) => identities.fabricFor(tenant);

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const fail = (message) => {
  throw new Error(message);
};

function checkedCapacity(value) {
  const id = String(value || '').trim();
  if (id && !mock && !isGuid(id)) fail('The capacity ID must be a GUID.');
  return id || null;
}

// Passwords come from an environment variable, never from the command line (shell history, process lists).
function passwordFromEnv() {
  const variable = options['password-env'];
  if (!variable) return null;
  return process.env[variable] || fail(`The environment variable ${variable} is empty.`);
}

// --role, defaulting to rep when territories are named. Validation happens in users.js.
const roleOption = () => options.role || (options.territory?.length ? 'rep' : fail('Choose --role manager (every territory) or --role rep with --territory.'));
// --reports view|edit|create|edit,create: what the person may do with reports where report authoring is on.
function reportsOption() {
  if (options.reports === undefined) return {};
  const words = options.reports.toLowerCase().split(',').map((w) => w.trim()).filter(Boolean);
  const unknown = words.filter((w) => !['view', 'edit', 'create', 'all'].includes(w));
  if (unknown.length || !words.length) fail('--reports takes view, edit, create or edit,create.');
  const all = words.includes('all');
  return { canEdit: all || words.includes('edit'), canCreate: all || words.includes('create') };
}
const accessText = (user) => {
  const { role, territories, canEdit, canCreate } = publicUser(user);
  const rights = [canEdit && 'edits', canCreate && 'creates'].filter(Boolean);
  return `${role === 'manager' ? `${ROLES.manager}, every territory` : `${ROLES.rep}, ${territories.join(', ')}`}${rights.length ? `; ${rights.join(' and ')} reports` : ''}`;
};
// Territories for embed and ask: none means a manager's view.
const territoriesOption = () => (options.territory?.length ? accessOf({ role: 'rep', territories: options.territory }).territories : null);

function findTenant(ref) {
  if (!ref) fail('Name the customer (name or ID).');
  const tenant = store.list().find((t) => t.id === ref || t.name.toLowerCase() === ref.toLowerCase());
  return tenant || fail(`No customer called "${ref}". Run "list" to see them.`);
}

function requireFeature(tenant, feature) {
  const { plan, features } = entitlements(tenant);
  if (!features[feature]) fail(`The ${plan.name} edition doesn't include this.`);
}

function checkedDomains(input, exceptId) {
  const domains = parseDomains(input);
  for (const domain of domains) {
    const owner = store.list().find((t) => t.id !== exceptId && (t.domains || []).includes(domain));
    if (owner) fail(`${domain} already signs in as ${owner.name}.`);
  }
  return domains;
}

function checkedAddons(list) {
  const unknown = list.filter((a) => !ADDONS[a]);
  if (unknown.length) fail(`Unknown add-on: ${unknown.join(', ')}.`);
  return [...new Set(list)];
}

function printIdentity(tenant) {
  const id = identities.describe(tenant);
  const where = id.appId ? `app ${id.appId}, object ${id.objectId}, created by ${id.createdBy}, signs in with a ${id.credential}${id.credentialExpiresAt ? ` (expires ${id.credentialExpiresAt.slice(0, 10)})` : ''}` : 'not created yet';
  console.log(`  Service account: ${id.name} [${id.status}${id.workspaceRole ? `, ${id.workspaceRole} of the workspace` : ''}] ${where}${id.simulated ? ' (simulated in demo mode)' : ''}`);
}

function printStatus(tenant) {
  const addons = tenant.addons?.length ? ` + ${tenant.addons.join(', ')}` : '';
  console.log(`${tenant.name}  [${tenant.status}]  ${getPlan(tenant.plan).name}${addons}  sign-in: ${(tenant.domains || []).map((d) => `@${d}`).join(', ') || 'none'} at ${signInUrl(config, tenant)}`);
  const brand = brandOf(tenant);
  if (brand.logo || brand.color) console.log(`  Branding: ${brand.logo ? `logo ${brand.logo.contentType} (${Math.ceil(brand.logo.bytes / 1024)} KB)` : 'no logo'}, ${brand.color ? `accent ${brand.color}` : 'default accent'}`);
  if (tenant.error) console.log(`  Error: ${tenant.error}`);
  printIdentity(tenant);
  const people = usersOf(tenant);
  console.log(`  Sign-ins: ${people.length ? people.map((u) => `${u.email} (${accessText(u)})`).join(', ') : 'none yet (demo sign-in by email domain)'}`);
  for (const [, step] of Object.entries(tenant.steps)) {
    console.log(`  ${step.status.padEnd(8)} ${step.title}${step.detail ? `: ${step.detail}` : ''}${step.error ? `: ${step.error}` : ''}`);
  }
  const ids = Object.entries(tenant.fabric).filter(([, value]) => typeof value === 'string');
  if (ids.length) console.log(`  Fabric: ${ids.map(([key, value]) => `${key}=${value}`).join('  ')}`);
  if (tenant.fabric.dataAgentId) {
    console.log(`  Assistant: data agent over MCP at ${dataAgentMcpUrl(config.endpoints.fabric, tenant.fabric.workspaceId, tenant.fabric.dataAgentId)}${config.dataAgentCodeInterpreter ? ' (code interpreter on)' : ''}; ${(tenant.questions || []).length} question(s) logged`);
  }
}

async function provisionAndReport(tenant) {
  const result = (await provisioner.provision(tenant.id)) || store.get(tenant.id);
  printStatus(result);
  if (result.status !== 'ready') process.exitCode = 1;
}

async function refreshAgent(tenant, client) {
  const agent = await refreshAgentAfterLoad({ fabric: client, tenant });
  if (agent?.added?.length) console.log(`The assistant can now query: ${agent.added.join(', ')}`);
  if (agent?.error) console.log(`Assistant not updated: ${agent.error}`);
  await store.save(tenant);
}

const commands = {
  async list() {
    const tenants = store.list();
    if (!tenants.length) return console.log('No customers yet.');
    for (const t of tenants) {
      console.log(`${t.id}  ${t.status.padEnd(12)} ${getPlan(t.plan).name.padEnd(13)} ${identities.describe(t).status.padEnd(8)} ${t.name}  (${t.fabric.workspaceName || 'no workspace'})`);
    }
  },
  async add(name) {
    if (!name) fail('Give the customer a name.');
    const plan = getPlan(options.plan) || fail(`Unknown edition ${options.plan}.`);
    if (store.list().some((t) => t.name.toLowerCase() === name.toLowerCase())) fail('A customer with that name already exists.');
    const tenant = newTenantRecord({
      name,
      plan: plan.id,
      addons: checkedAddons(options.addon || []),
      workspaceId: options.workspace || null,
      domains: checkedDomains(options.domain || []),
      sampleData: !options['no-sample-data'],
      capacityId: checkedCapacity(options.capacity),
      subdomain: uniqueSubdomain(name, store.list()),
    });
    addActivity(tenant, `Customer added with the ${plan.name} edition${tenant.capacityId ? ` on capacity ${tenant.capacityId}` : ''} (CLI)`);
    await store.save(tenant);
    console.log(`Added ${name} (${tenant.id}). Provisioning…`);
    await provisionAndReport(tenant);
  },
  async domains(ref, ...domains) {
    const tenant = findTenant(ref);
    tenant.domains = checkedDomains(domains, tenant.id);
    addActivity(tenant, tenant.domains.length ? `Sign-in domains set to ${tenant.domains.join(', ')} (CLI)` : 'Sign-in domains cleared (CLI)');
    await store.save(tenant);
    console.log(tenant.domains.length ? `${tenant.name} users sign in with ${tenant.domains.map((d) => `@${d}`).join(', ')}.` : `${tenant.name} has no sign-in domain.`);
  },
  async brand(ref) {
    const tenant = findTenant(ref);
    if (!options.logo && options.color === undefined && !options['no-logo']) fail('Give --logo <file>, --color <#RRGGBB> (empty to reset) or --no-logo.');
    const changes = [];
    if (options['no-logo']) {
      tenant.branding = { ...(tenant.branding || {}), logo: null };
      changes.push('logo removed');
    } else if (options.logo) {
      const logo = setLogo(tenant, await readFile(options.logo));
      changes.push(`logo set (${logo.contentType}, ${Math.ceil(logo.bytes / 1024)} KB)`);
    }
    if (options.color !== undefined) {
      const color = parseColor(options.color);
      tenant.branding = { ...(tenant.branding || {}), color };
      changes.push(color ? `accent color ${color}` : 'default accent color');
    }
    addActivity(tenant, `Branding: ${changes.join(', ')} (CLI)`, 'audit');
    await store.save(tenant);
    console.log(`${tenant.name}: ${changes.join(', ')}. People see it at ${signInUrl(config, tenant)}`);
  },
  async provision(ref) {
    await provisionAndReport(findTenant(ref));
  },
  async edition(ref, planId) {
    const tenant = findTenant(ref);
    const plan = getPlan(planId) || fail(`Unknown edition ${planId}.`);
    if (plan.id !== tenant.plan) {
      addActivity(tenant, `Edition changed from ${getPlan(tenant.plan).name} to ${plan.name} (CLI)`);
      tenant.plan = plan.id;
      await store.save(tenant);
    }
    await provisionAndReport(tenant);
  },
  async addons(ref, ...list) {
    const tenant = findTenant(ref);
    tenant.addons = checkedAddons(list);
    addActivity(tenant, tenant.addons.length ? `Add-ons set to ${tenant.addons.join(', ')} (CLI)` : 'Add-ons removed (CLI)');
    await store.save(tenant);
    await provisionAndReport(tenant);
  },
  async capacity(ref, capacityId) {
    const tenant = findTenant(ref);
    tenant.capacityId = checkedCapacity(capacityId);
    addActivity(tenant, tenant.capacityId ? `Moving to dedicated capacity ${tenant.capacityId} (CLI)` : 'Moving back to the default capacity (CLI)');
    await store.save(tenant);
    await provisionAndReport(tenant);
  },
  async audit(ref) {
    const report = await auditTenant({ tenant: findTenant(ref), fabric, identities, config });
    const marks = { pass: 'ok  ', info: 'note', warn: 'WARN', fail: 'FAIL' };
    console.log(`${report.tenant}: ${report.counts.pass} ok, ${report.counts.warn} to review, ${report.counts.fail} failing (identity mode ${report.settings.identityMode}, platform access ${report.settings.platformWorkspaceAccess})`);
    for (const check of report.checks) console.log(`  ${marks[check.status]}  ${check.title}: ${check.detail}`);
    if (!report.ok) process.exitCode = 1;
  },
  async status(ref) {
    const tenant = findTenant(ref);
    printStatus(tenant);
    for (const entry of tenant.activity.slice(0, 10)) console.log(`  ${entry.at}  ${entry.level === 'info' ? '' : `${entry.level.toUpperCase()} `}${entry.message}`);
  },
  async identity(ref) {
    printIdentity(findTenant(ref));
  },
  async users(ref) {
    const tenant = findTenant(ref);
    const list = usersOf(tenant);
    if (!list.length) return console.log(`${tenant.name} has no named sign-ins: anyone at ${(tenant.domains || []).map((d) => `@${d}`).join(', ') || '(no domain)'} can use the demo sign-in.`);
    for (const u of list) {
      console.log(`${u.email.padEnd(32)} ${(u.name || '').padEnd(20)} ${accessText(u).padEnd(32)} last sign-in ${u.lastSignInAt ? u.lastSignInAt.slice(0, 16).replace('T', ' ') : 'never'}`);
    }
  },
  async 'user-add'(ref, email) {
    const tenant = findTenant(ref);
    const { user, password } = await addUser({ store, tenant, email, name: options.name, password: passwordFromEnv(), role: roleOption(), territories: options.territory || [], ...reportsOption() });
    addActivity(tenant, `Sign-in added for ${user.email}, ${accessText(user)} (CLI)`, 'audit');
    await store.save(tenant);
    console.log(`Added ${user.email} to ${tenant.name}: ${accessText(user)}.`);
    if (password) console.log(`Password (shown once, give it to ${user.name || user.email} privately): ${password}`);
  },
  async 'user-access'(ref, email) {
    const tenant = findTenant(ref);
    const existing = findUser(tenant, email) || fail(`${tenant.name} has no sign-in for ${email}.`);
    const rights = reportsOption();
    if (!options.role && !options.territory?.length && !Object.keys(rights).length) fail('Give --role, --territory or --reports.');
    const role = options.role || (options.territory?.length ? 'rep' : undefined);
    const { user, signedOut } = updateUser({ tenant, userId: existing.id, role, territories: options.territory?.length ? options.territory : undefined, ...rights });
    addActivity(tenant, `Access of ${user.email} set to ${accessText(user)} (CLI)${signedOut ? '; their sessions ended' : ''}`, 'audit');
    await store.save(tenant);
    console.log(`${user.email}: ${accessText(user)}${signedOut ? '. Their sessions have ended.' : ' (unchanged).'}`);
  },
  async 'user-reset'(ref, email) {
    const tenant = findTenant(ref);
    const existing = findUser(tenant, email) || fail(`${tenant.name} has no sign-in for ${email}.`);
    const { user, password } = await resetPassword({ tenant, userId: existing.id, password: passwordFromEnv() });
    addActivity(tenant, `Password reset for ${user.email} (CLI); their sessions ended`, 'audit');
    await store.save(tenant);
    console.log(password ? `New password for ${user.email} (shown once): ${password}` : `Password for ${user.email} set from ${options['password-env']}.`);
  },
  async 'user-remove'(ref, email) {
    const tenant = findTenant(ref);
    const existing = findUser(tenant, email) || fail(`${tenant.name} has no sign-in for ${email}.`);
    removeUser({ tenant, userId: existing.id });
    addActivity(tenant, `Sign-in removed for ${existing.email} (CLI)`, 'audit');
    await store.save(tenant);
    console.log(`Removed ${existing.email}; their sessions have ended.`);
  },
  async 'identity-register'(ref) {
    const tenant = findTenant(ref);
    // Best first: --federated (the app trusts the platform's managed identity), --certificate-file (a PEM bundle with
    // the private key; delete the file afterwards, the platform keeps it encrypted), --secret-env (development).
    const chosen = [options.federated, options['certificate-file'], options['secret-env']].filter(Boolean).length;
    if (chosen !== 1) fail('Give one credential: --certificate-file <pem>, --federated, or --secret-env <VAR> (development).');
    const credential = {};
    if (options.federated) credential.federated = true;
    else if (options['certificate-file']) credential.certificate = await readFile(options['certificate-file'], 'utf8').catch(() => fail(`Can't read ${options['certificate-file']}.`));
    else credential.secret = process.env[options['secret-env']] || fail(`The environment variable ${options['secret-env']} is empty.`);
    console.log('Checking that the service account can sign in…');
    await identities.register(tenant, { appId: options['app-id'], objectId: options['object-id'], displayName: options['display-name'], ...credential });
    addActivity(tenant, `Service account ${tenant.identity.name} registered with a ${identities.describe(tenant).credential} (CLI)`);
    await store.save(tenant);
    console.log(`Registered ${tenant.identity.name} (${identities.describe(tenant).credential}). Run "provision ${tenant.name}" to make it Admin of the workspace and hand the work over to it.`);
  },
  async 'identity-rotate'(ref) {
    const tenant = findTenant(ref);
    const identity = await identities.rotate(tenant);
    addActivity(tenant, `Service account ${identities.describe(tenant).credential} rotated (CLI)`);
    await store.save(tenant);
    console.log(`New ${identities.describe(tenant).credential} stored; it expires ${String(identity.credentialExpiresAt || '').slice(0, 10)}. The old one was removed.`);
  },
  async items(ref) {
    const tenant = findTenant(ref);
    for (const item of await (await scoped(tenant)).listItems(tenant.fabric.workspaceId)) console.log(`${item.id}  ${item.type.padEnd(16)} ${item.displayName}`);
  },
  async crm(ref) {
    const tenant = findTenant(ref);
    const repo = await crm.forTenant(tenant);
    console.log('Rows:', JSON.stringify(await repo.counts()));
    console.log('Summary:', JSON.stringify(await repo.scoped(null).summary()));
    for (const territory of TERRITORIES) console.log(`  ${territory}:`, JSON.stringify(await repo.scoped([territory]).summary()));
  },
  async reseed(ref) {
    const tenant = findTenant(ref);
    requireFeature(tenant, 'crm');
    if (!options.confirm) fail(`This deletes every account, contact, deal and activity in ${tenant.name}'s CRM. Run again with --confirm.`);
    const repo = await crm.forTenant(tenant);
    await repo.migrate();
    const loaded = await repo.replaceWithSampleData(sampleSeedOf(tenant), { companyDomain: tenant.domains?.[0] });
    addActivity(tenant, 'CRM data replaced with the sample data (CLI)', 'warning');
    await store.save(tenant);
    console.log(`Loaded ${Object.entries(loaded).map(([table, n]) => `${n} ${table}`).join(', ')}. Reports catch up once Fabric has replicated the changes (about a minute).`);
  },
  async model(ref) {
    const tenant = findTenant(ref);
    const client = await scoped(tenant);
    const { workspaceId, semanticModelId, crm: db } = tenant.fabric;
    if (!semanticModelId) fail('The model is not published yet.');
    const current = buildSemanticModelDefinition({ workspaceId, sqlDatabaseId: db.sqlDatabaseId }).fingerprint;
    console.log(`${MODEL_NAME} ${semanticModelId}: version ${tenant.fabric.semanticModelFingerprint}${current === tenant.fabric.semanticModelFingerprint ? ' (current)' : ` (current is ${current}; run provision)`}`);
    for (const c of await client.listItemConnections(workspaceId, semanticModelId)) {
      console.log(`  Data source ${c.connectionDetails.type} ${c.connectionDetails.path}: ${c.connectivityType}${c.displayName ? ` "${c.displayName}" (${c.id})` : ''}`);
    }
    for (const r of await client.pbiListRefreshes(workspaceId, semanticModelId, 5)) console.log(`  Refresh ${r.startTime}  ${r.status}${r.serviceExceptionJson ? `  ${r.serviceExceptionJson}` : ''}`);
  },
  async reports(ref) {
    const tenant = findTenant(ref);
    const { reports, datasets } = await listReporting({ fabric: await scoped(tenant), tenant });
    console.log(reports.length ? 'Reports:' : 'No reports yet.');
    for (const r of reports) console.log(`  ${r.id}  ${r.name}  (semantic model ${r.datasetId || '-'})`);
    console.log(datasets.length ? 'Semantic models:' : 'No semantic models.');
    for (const d of datasets) console.log(`  ${d.id}  ${d.name}`);
  },
  async embed(ref, reportRef) {
    const tenant = findTenant(ref);
    const client = await scoped(tenant);
    const mode = options.mode || (reportRef ? 'view' : 'create');
    let request = { mode };
    if (mode === 'create') request.datasetId = tenant.fabric.semanticModelId;
    else {
      const { reports } = await listReporting({ fabric: client, tenant });
      request.reportId = (reports.find((r) => r.id === reportRef || r.name === reportRef) || fail(`No report called ${reportRef}.`)).id;
    }
    const territories = territoriesOption();
    const identity = { username: territories ? `cli-rep:${territories.join('+')}` : 'cli-manager', roles: rolesFor(territories), limited: territories !== null };
    const embed = await createEmbedConfig({ fabric: client, tenant, ...request, lifetimeMinutes: config.embedTokenMinutes, identity });
    console.log(`Embed token issued (${embed.kind}, ${mode}) for ${embed.name}; it expires ${embed.expiration}.`);
    console.log(`Embed URL: ${embed.embedUrl}`);
    console.log(`Token request: ${JSON.stringify(embed.tokenRequest)}`);
  },
  async ask(ref, ...words) {
    const tenant = findTenant(ref);
    requireFeature(tenant, 'agent');
    const question = words.join(' ').trim() || fail('Ask a question.');
    const started = Date.now();
    const result = await assistant.ask(tenant, question, { email: 'cli', territories: territoriesOption() });
    console.log(result.answer);
    for (const row of (result.rows || []).slice(0, 10)) console.log(`  ${String(row.label).padEnd(30)} ${row.display}`);
    console.log(`(${result.source === 'assistant' ? 'data agent' : 'quick answer from the CRM database'}, ${((Date.now() - started) / 1000).toFixed(1)} s)`);
    if (result.images?.length) console.log(`The agent drew ${result.images.length} chart(s).`);
    await store.save(tenant);
  },
  async usage(ref) {
    const tenant = findTenant(ref);
    const entries = tenant.reportUsage || [];
    if (!entries.length) return console.log(`Nobody has opened a ${tenant.name} report since the usage log started.`);
    const s = (ms) => (Number.isFinite(ms) ? `${(ms / 1000).toFixed(1)} s` : '-');
    for (const r of summarizeUsage(entries)) {
      console.log(`${(r.reportName || r.reportId).padEnd(28)} ${r.views} view(s) by ${r.people} person(s); median load ${s(r.medianLoadMs)}, render ${s(r.medianRenderMs)}${r.saves ? `; ${r.saves} save(s)` : ''}`);
    }
    console.log('');
    for (const u of entries.slice(0, Number(options.limit) || 20)) {
      const timing = u.event === 'view' ? `  load ${s(u.loadMs)}, render ${s(u.renderMs)}` : '';
      console.log(`${u.at.slice(0, 19).replace('T', ' ')}  ${String(u.email).padEnd(30)} ${String(u.scope).padEnd(16)} ${u.event.padEnd(6)} ${u.reportName || u.reportId}${timing}${u.correlationId ? `  correlation ${u.correlationId}` : ''}`);
    }
    addActivity(tenant, 'Viewed report usage (CLI)', 'audit');
    await store.save(tenant);
  },
  async questions(ref) {
    const tenant = findTenant(ref);
    const list = (tenant.questions || []).slice(0, Number(options.limit) || 20);
    if (!list.length) return console.log(`Nobody has asked ${tenant.name}'s assistant anything yet.`);
    for (const q of list) {
      const reasons = [q.answeredBy === 'data agent' ? null : `agent: ${q.agent}${q.error ? `, ${q.error}` : ''}`, q.quickError ? `quick answer failed: ${q.quickError}` : null].filter(Boolean);
      const why = reasons.length ? ` (${reasons.join('; ')})` : '';
      console.log(`${q.at.slice(0, 19).replace('T', ' ')}  ${String(q.email).padEnd(30)} ${String(q.scope).padEnd(16)} ${q.answeredBy}${why}${q.chart ? ', chart' : ''}${q.images ? `, ${q.images} image(s)` : ''}, ${q.ms} ms`);
      console.log(`    Q: ${q.question}`);
      if (q.answer) {
        const text = q.answer.replace(/\s+/g, ' ').trim();
        console.log(`    A: ${options.full || text.length <= 300 ? text : `${text.slice(0, 300)}…`}`);
      } else console.log(`    A: ${'answer' in q ? '(none: nobody could answer)' : '(not logged: asked before answers were kept)'}`);
    }
    addActivity(tenant, 'Viewed the questions and answers of the assistant (CLI)', 'audit');
    await store.save(tenant);
  },
  async upload(ref, file) {
    const tenant = findTenant(ref);
    requireFeature(tenant, 'ingestion');
    if (!file) fail('Name the file to upload.');
    const client = await scoped(tenant);
    const record = await ingestBytes({ fabric: client, tenant, bytes: await readFile(file), fileName: path.basename(file), table: options.table, mode: options.mode || 'Overwrite' });
    console.log(`Loaded ${record.table} (${record.mode.toLowerCase()}, ${record.bytes.toLocaleString('en-US')} bytes) from ${record.file}`);
    await refreshAgent(tenant, client);
  },
  async 'import-web'(ref, url) {
    const tenant = findTenant(ref);
    requireFeature(tenant, 'ingestion');
    const client = await scoped(tenant);
    const record = await importFromWeb({ fabric: client, tenant, url, table: options.table, mode: options.mode || 'Overwrite' });
    console.log(`Loaded ${record.table} from ${url}`);
    await refreshAgent(tenant, client);
  },
  async 'sync-agent'(ref) {
    const tenant = findTenant(ref);
    const result = await syncDataAgent({ fabric: await scoped(tenant), tenant });
    console.log(result.added?.length ? `Added: ${result.added.join(', ')}` : 'The assistant already knows every table.');
    await store.save(tenant);
  },
  async remove(ref) {
    const tenant = findTenant(ref);
    await provisioner.deprovision(tenant.id, { keepWorkspace: options['keep-workspace'] });
    console.log(options['keep-workspace'] ? `Removed ${tenant.name}; kept its workspace.` : `Removed ${tenant.name} and deleted its workspace.`);
  },
};

const handler = commands[command];
if (!handler) {
  console.error(`Unknown command "${command}".\n\n${HELP}`);
  process.exit(1);
}
try {
  await handler(...args);
} catch (error) {
  console.error(`Error: ${error.message}`);
  if (error.requestId) console.error(`Fabric request ID: ${error.requestId}`);
  process.exitCode = 1;
} finally {
  // Open database pools would keep the process alive.
  await crm.closeAll();
  await sleep(0);
}
