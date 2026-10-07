import { createApp } from '../src/app.js';
import { loadConfig } from '../src/config.js';
import { createCrmService } from '../src/crm/index.js';
import { MOCK_TEMPLATE_ID, createMockFabric } from '../src/fabric/mock.js';
import { createIdentityBroker } from '../src/platform/identities.js';
import { createProvisioner } from '../src/platform/provisioner.js';
import { createMemorySecretStore } from '../src/platform/secrets.js';
import { createTenantStore, newTenantRecord } from '../src/platform/store.js';
import { inject } from './helpers.js';

export const WEB = { 'x-platform-client': 'web' };
export const FAST = { waitMs: 0, refreshPollMs: 0, capacityPollMs: 0 };

// The whole app in mock mode, with the template workspace so customers get a report to open. Report authoring (the
// next phase, off by default) is on here so its code stays tested; standard-report.test.js covers the default.
export function makeApp({ env = {}, template = true } = {}) {
  const config = loadConfig({ FABRIC_AUTH_MODE: 'mock', DATA_DIR: 'unused', REPORT_AUTHORING: 'true', ...(template ? { FABRIC_TEMPLATE_WORKSPACE_ID: MOCK_TEMPLATE_ID } : {}), ...env });
  const fabric = createMockFabric();
  const store = createTenantStore();
  const app = createApp({ config, fabric, store, log: null, provisionerOptions: FAST });
  return { app, fabric, store, config, call: (options) => inject(app.handler, options) };
}

export async function createReadyTenant(call, app, { name = 'Fabrikam', plan = 'enterprise', domains, addons } = {}) {
  const created = await call({ method: 'POST', url: '/api/admin/tenants', headers: WEB, body: { name, plan, domains, addons } });
  if (created.status !== 202) throw new Error(`Creating ${name} failed: ${created.text}`);
  const { id } = created.json();
  await app.provisioner.provision(id);
  const detail = (await call({ url: `/api/admin/tenants/${id}` })).json();
  if (detail.status !== 'ready') throw new Error(`${name} is ${detail.status}: ${detail.error}`);
  return detail;
}

// The whole app plus helpers: an operator for the back office, customers, and signed-in users.
export function makePlatform(options) {
  const platform = makeApp(options);
  const { app, call } = platform;
  let operatorCookie = null;
  const admin = (request) => call({ ...request, headers: { ...WEB, ...(operatorCookie ? { cookie: operatorCookie } : {}), ...(request.headers || {}) } });
  async function operatorSignIn(key, name = 'test operator') {
    const res = await call({ method: 'POST', url: '/api/admin/session', headers: WEB, body: { key, name } });
    if (res.status !== 200) throw new Error(`Operator sign-in failed: ${res.text}`);
    operatorCookie = res.headers['set-cookie'].split(';')[0];
    return operatorCookie;
  }
  async function addCustomer(name, plan, domain, extra = {}) {
    const created = await admin({ method: 'POST', url: '/api/admin/tenants', body: { name, plan, domains: [domain], ...extra } });
    if (created.status !== 202) throw new Error(`Creating ${name} failed: ${created.text}`);
    const tenant = await app.provisioner.provision(created.json().id);
    if (tenant.status !== 'ready') throw new Error(`${name} is ${tenant.status}: ${tenant.error}`);
    return tenant.id;
  }
  async function signIn(email, headers = {}) {
    const res = await call({ method: 'POST', url: '/api/session', headers: { ...WEB, ...headers }, body: { email } });
    if (res.status !== 200) throw new Error(`Sign-in failed for ${email}: ${res.status} ${res.text}`);
    const cookie = res.headers['set-cookie'].split(';')[0];
    return (request) => call({ ...request, headers: { ...WEB, ...(request.headers || {}), cookie } });
  }
  return { ...platform, admin, operatorSignIn, addCustomer, signIn };
}

// Just the provisioner and its collaborators, for tests that look at what lands in "Fabric".
export function provisioningKit({ config: overrides = {}, identityConfig, fabric = createMockFabric() } = {}) {
  const config = { ...loadConfig({ FABRIC_AUTH_MODE: 'mock', DATA_DIR: 'unused' }), ...overrides };
  const store = createTenantStore();
  const identities = createIdentityBroker({ config: identityConfig || config, platformTokens: null, platformFabric: fabric, secrets: createMemorySecretStore() });
  const crm = createCrmService({ fabric, identities });
  const provisioner = createProvisioner({ fabric, store, config, identities, crm, ...FAST });
  async function provisionNew({ name = 'Fabrikam', plan = 'enterprise', addons = [], workspaceId = null, sampleData = true } = {}) {
    const tenant = newTenantRecord({ name, plan, addons, workspaceId, sampleData, domains: [`${name.toLowerCase().replace(/[^a-z]/g, '')}.com`] });
    await store.save(tenant);
    await provisioner.provision(tenant.id);
    return store.get(tenant.id);
  }
  return { config, fabric, store, identities, crm, provisioner, provisionNew };
}
