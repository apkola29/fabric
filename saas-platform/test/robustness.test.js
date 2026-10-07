import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { loadConfig } from '../src/config.js';
import { createCrmService } from '../src/crm/index.js';
import { FabricApiError } from '../src/fabric/client.js';
import { MOCK_TEMPLATE_ID, createMockFabric } from '../src/fabric/mock.js';
import { clientAddress, createRateLimiter } from '../src/http/limits.js';
import { createLimiter } from '../src/platform/provisioner.js';
import { createFileSecretStore } from '../src/platform/secrets.js';
import { createJsonWriter } from '../src/util/files.js';
import { WEB, makePlatform, provisioningKit } from './support.js';

const ADMIN_KEY = 'a-long-operator-key-for-tests-0123456789';
const tempDir = (prefix) => mkdtempSync(path.join(os.tmpdir(), prefix));

// Makes the next matching call fail once. after: the call reaches Fabric first and only the response is lost,
// which is the case that creates duplicates when a retry doesn't look before it creates.
function failOnce(kit, { who, method, after = false, when = () => true }) {
  const state = { fired: false };
  const wrap = (client) => {
    const real = client[method];
    client[method] = async (...args) => {
      if (state.fired || !when(...args)) return real(...args);
      state.fired = true;
      if (after) await real(...args);
      throw new FabricApiError(`Injected failure in ${method}`, { upstreamStatus: 503, code: 'ServiceUnavailable' });
    };
    return client;
  };
  if (who === 'platform') wrap(kit.fabric);
  else {
    const as = kit.fabric.as;
    kit.fabric.as = (principal) => wrap(as(principal));
  }
  return state;
}

function assertNoDuplicates(kit, tenant) {
  const state = kit.fabric.inspect();
  const items = Object.values(state.items).filter((i) => i.workspaceId === tenant.fabric.workspaceId);
  const names = items.map((i) => `${i.type}:${i.displayName}`);
  assert.equal(new Set(names).size, names.length, `duplicate items: ${names.join(', ')}`);
  assert.equal(Object.values(state.workspaces).filter((w) => w.displayName === tenant.fabric.workspaceName).length, 1, 'one workspace');
  assert.equal(Object.keys(state.connections).length, 1, 'one connection');
  const principals = state.roleAssignments[tenant.fabric.workspaceId].map((a) => a.principal.id);
  assert.equal(new Set(principals).size, principals.length, 'one role per principal');
}

const FAULTS = [
  { step: 'workspace', who: 'platform', method: 'createWorkspace', after: true },
  { step: 'service-account', who: 'platform', method: 'addRoleAssignment', after: true },
  { step: 'crm-database', who: 'account', method: 'createItem', after: true, when: (_, item) => item.type === 'SQLDatabase' },
  { step: 'workspace-identity', who: 'account', method: 'addRoleAssignment', after: true },
  { step: 'semantic-model', who: 'account', method: 'createItem', after: true, when: (_, item) => item.type === 'SemanticModel' },
  { step: 'model-connection', who: 'account', method: 'createConnection', after: true },
  { step: 'model-connection', who: 'account', method: 'bindSemanticModelConnection' },
  { step: 'model-connection', who: 'account', method: 'pbiRefreshDataset' },
  { step: 'templates', who: 'account', method: 'createItem', after: true, when: (_, item) => item.type === 'Report' },
  { step: 'data-agent', who: 'account', method: 'createItem', after: true, when: (_, item) => item.type === 'DataAgent' },
];

test('a failure at any step leaves nothing half-done: the next run finishes without duplicates', async () => {
  for (const fault of FAULTS) {
    const label = `${fault.method}${fault.after ? ' (response lost)' : ''} in ${fault.step}`;
    const kit = provisioningKit({ config: { templateWorkspaceId: MOCK_TEMPLATE_ID } });
    const injected = failOnce(kit, fault);
    const first = await kit.provisionNew();
    assert.ok(injected.fired, `${label}: the fault fired`);
    // Some steps recover inside the same run (they look again before retrying); the others stop and resume.
    if (first.status !== 'ready') assert.equal(first.steps[fault.step].status, 'failed', `${label}: ${JSON.stringify(first.steps[fault.step])}`);
    const recovered = first.status === 'ready' ? first : await kit.provisioner.provision(first.id);
    assert.equal(recovered.status, 'ready', `${label}: ${recovered.error}`);
    assertNoDuplicates(kit, recovered);
  }
});

test('calls for the same customer share one run; customers queue behind a concurrency limit', async () => {
  const kit = provisioningKit({ config: { provisioning: { maxConcurrent: 2 } }, fabric: createMockFabric({ latencyMs: 1 }) });
  const tenant = await kit.provisionNew();
  const [a, b, c] = await Promise.all([kit.provisioner.provision(tenant.id), kit.provisioner.provision(tenant.id), kit.provisioner.provision(tenant.id)]);
  assert.ok(a === b && b === c, 'the same run is returned');
  assert.equal(tenant.activity.filter((e) => /^Provisioning started/.test(e.message)).length, 2, 'one run for the three calls (plus the first one)');

  const names = Array.from({ length: 6 }, (_, i) => `Queue ${i}`);
  const results = await Promise.all(names.map((name) => kit.provisionNew({ name })));
  assert.ok(results.every((t) => t.status === 'ready'), results.map((t) => t.error).join(' '));
  const stats = kit.provisioner.stats();
  assert.ok(stats.peak <= 2, `peak ${stats.peak}`);
  assert.equal(stats.peak, 2, 'runs did overlap up to the limit');

  const limiter = createLimiter(3);
  let active = 0;
  let peak = 0;
  await Promise.all(
    Array.from({ length: 12 }, () =>
      limiter.run(async () => {
        peak = Math.max(peak, ++active);
        await new Promise((resolve) => setTimeout(resolve, 2));
        active -= 1;
      }),
    ),
  );
  assert.equal(peak, 3);
  await assert.rejects(limiter.run(async () => Promise.reject(new Error('boom'))), /boom/);
  assert.equal(await limiter.run(async () => 'still works'), 'still works', 'a failed job frees its slot');
});

test('upgrades keep the app up: customers keep what works while a later run is busy or has failed', async () => {
  const platform = makePlatform();
  const { app, fabric, store, admin, addCustomer, signIn } = platform;

  // Before the first success the app says "setting up". The gate holds the run at its first Fabric call.
  const realCreateWorkspace = fabric.createWorkspace;
  let openGate;
  const gate = new Promise((resolve) => {
    openGate = resolve;
  });
  fabric.createWorkspace = async (...args) => {
    await gate;
    return realCreateWorkspace(...args);
  };
  const created = (await admin({ method: 'POST', url: '/api/admin/tenants', body: { name: 'Fresh Co', plan: 'enterprise', domains: ['fresh.com'] } })).json();
  const fresh = await signIn('li@fresh.com');
  assert.equal((await fresh({ url: '/api/me' })).json().status, 'setting-up');
  assert.equal((await fresh({ url: '/api/me/crm/summary' })).status, 409);
  openGate();
  await app.provisioner.provision(created.id);
  fabric.createWorkspace = realCreateWorkspace;
  assert.equal((await fresh({ url: '/api/me' })).json().status, 'ready');

  const realGetWorkspace = fabric.getWorkspace;
  const id = await addCustomer('Fabrikam', 'enterprise', 'fabrikam.com');
  const ana = await signIn('ana@fabrikam.com');
  const before = (await ana({ url: '/api/me' })).json();
  assert.equal(before.status, 'ready');

  // An upgrade run that pauses, then fails at the model step.
  let resume;
  const paused = new Promise((resolve) => {
    resume = resolve;
  });
  fabric.getWorkspace = async (...args) => {
    await paused;
    return realGetWorkspace(...args);
  };
  const tenant = store.get(id);
  tenant.fabric.semanticModelFingerprint = 'an-older-version';
  await store.save(tenant);
  const realAs = fabric.as;
  fabric.as = (principal) => {
    const client = realAs(principal);
    client.updateItemDefinition = async () => {
      throw new FabricApiError('Injected model deployment failure', { upstreamStatus: 500 });
    };
    return client;
  };
  const run = app.provisioner.provision(id);
  const during = (await ana({ url: '/api/me' })).json();
  assert.equal(during.status, 'ready', 'still usable while the upgrade runs');
  assert.deepEqual(during.features, before.features);
  assert.equal((await ana({ url: '/api/me/crm/summary' })).status, 200);
  resume();
  const failedRun = await run;
  fabric.getWorkspace = realGetWorkspace;
  fabric.as = realAs;
  assert.equal(failedRun.status, 'failed');
  assert.equal(failedRun.steps['semantic-model'].status, 'failed');
  const after = (await ana({ url: '/api/me' })).json();
  assert.equal(after.status, 'ready', 'a failed upgrade does not take the app away');
  assert.deepEqual(after.features, before.features);
  assert.equal((await ana({ url: '/api/me/crm/accounts' })).status, 200);
  const { reports } = (await ana({ url: '/api/me/reports' })).json();
  assert.equal((await ana({ method: 'POST', url: '/api/me/embed', body: { mode: 'view', reportId: reports[0].id } })).status, 200);
});

test("rate limits are per customer and per user: one busy customer doesn't block another", async () => {
  const { addCustomer, signIn } = makePlatform({ env: { RATE_LIMITS: JSON.stringify({ askPerUser: [2, 60000], askPerTenant: [3, 60000], signInPerDomain: [50, 60000] }) } });
  await addCustomer('Fabrikam', 'enterprise', 'fabrikam.com');
  await addCustomer('Contoso', 'enterprise', 'contoso.com');
  const ask = (as) => as({ method: 'POST', url: '/api/me/ask', body: { question: 'How many accounts are there?' } });
  const ana = await signIn('ana@fabrikam.com');
  const ben = await signIn('ben@fabrikam.com');
  const cy = await signIn('cy@fabrikam.com');
  const li = await signIn('li@contoso.com');

  assert.equal((await ask(ana)).status, 200);
  assert.equal((await ask(ana)).status, 200);
  const limited = await ask(ana);
  assert.equal(limited.status, 429, 'per-user budget');
  assert.ok(Number(limited.headers['retry-after']) >= 1, 'tells the browser when to retry');
  assert.equal((await ask(ben)).status, 200, 'another user of the same customer still has budget');
  assert.equal((await ask(cy)).status, 429, 'the customer-wide budget is used up');
  assert.equal((await ask(li)).status, 200, 'another customer is unaffected');
});

test('sign-in attempts are limited per address, and X-Forwarded-For is only trusted behind a known proxy', async () => {
  const { addCustomer, call } = makePlatform({ env: { RATE_LIMITS: JSON.stringify({ signInPerIp: [3, 60000] }) } });
  await addCustomer('Fabrikam', 'standard', 'fabrikam.com');
  const attempt = (email) => call({ method: 'POST', url: '/api/session', headers: WEB, body: { email } });
  for (let i = 0; i < 3; i += 1) assert.notEqual((await attempt(`user${i}@nowhere.com`)).status, 429);
  assert.equal((await attempt('ana@fabrikam.com')).status, 429);

  const req = { headers: { 'x-forwarded-for': '203.0.113.7, 10.0.0.1' }, socket: { remoteAddress: '10.0.0.1' } };
  assert.equal(clientAddress(req, { trustProxy: false }), '10.0.0.1', 'a client can spoof the header, so it is ignored by default');
  assert.equal(clientAddress(req, { trustProxy: true }), '203.0.113.7');

  let clock = 0;
  const limiter = createRateLimiter({ now: () => clock });
  const rule = [{ key: 'k', limit: [2, 1000] }];
  limiter.enforce(rule);
  limiter.enforce(rule);
  assert.throws(() => limiter.enforce(rule), (error) => error.status === 429 && error.retryAfter === 1);
  clock = 500;
  limiter.enforce(rule);
  assert.throws(() => limiter.enforce(rule), (error) => error.status === 429);

  const flooded = createRateLimiter({ now: () => 0, maxKeys: 100 });
  for (let i = 0; i < 1000; i += 1) flooded.take(`domain-${i}.example`, [5, 60000]);
  assert.ok(flooded.size() <= 100, `a flood of new keys stays bounded (${flooded.size()})`);
});

test('the back office needs operator sign-in when ADMIN_KEY is set, and operator data access is logged', async () => {
  const { call, admin, operatorSignIn, signIn, app } = makePlatform({ env: { ADMIN_KEY } });
  assert.equal((await call({ url: '/api/admin/tenants' })).status, 401);
  assert.equal((await call({ method: 'POST', url: '/api/admin/tenants', headers: WEB, body: { name: 'Sneaky', plan: 'standard' } })).status, 401);
  assert.deepEqual((await call({ url: '/api/admin/session' })).json(), { required: true, signedIn: false, name: null });
  assert.equal((await call({ method: 'POST', url: '/api/admin/session', headers: WEB, body: { key: 'wrong-key-wrong-key-wrong-key' } })).status, 401);

  const cookie = await operatorSignIn(ADMIN_KEY, 'Alice');
  const issued = (await call({ method: 'POST', url: '/api/admin/session', headers: WEB, body: { key: ADMIN_KEY } })).headers['set-cookie'];
  assert.match(issued, /HttpOnly/);
  assert.match(issued, /SameSite=Strict/);
  assert.match(issued, /Path=\/api\/admin/);
  assert.equal((await admin({ url: '/api/admin/tenants' })).status, 200);

  const [name, value] = cookie.split('=');
  const [payload, signature] = value.split('.');
  const forged = Buffer.from(JSON.stringify({ ...JSON.parse(Buffer.from(payload, 'base64url')), exp: 9999999999 })).toString('base64url');
  assert.equal((await call({ url: '/api/admin/tenants', headers: { cookie: `${name}=${forged}.${signature}` } })).status, 401, 'a tampered cookie is refused');

  const created = await admin({ method: 'POST', url: '/api/admin/tenants', body: { name: 'Fabrikam', plan: 'enterprise', domains: ['fabrikam.com'] } });
  const { id } = created.json();
  await app.provisioner.provision(id);
  const ana = await signIn('ana@fabrikam.com');
  assert.equal((await ana({ url: '/api/admin/tenants' })).status, 401, "a customer's session is not an operator session");

  const { reports } = (await admin({ url: `/api/admin/tenants/${id}/reports` })).json();
  assert.equal((await admin({ method: 'POST', url: `/api/admin/tenants/${id}/embed`, body: { mode: 'view', reportId: reports[0].id } })).status, 200);
  assert.equal((await admin({ method: 'POST', url: `/api/admin/tenants/${id}/agent/ask`, body: { question: 'How many accounts?' } })).status, 200);
  const activity = (await admin({ url: `/api/admin/tenants/${id}` })).json().activity;
  assert.ok(activity.some((a) => a.level === 'audit' && /^Operator Alice opened the report "/.test(a.message)));
  assert.ok(activity.some((a) => a.level === 'audit' && /^Operator Alice asked the assistant: "How many accounts\?"/.test(a.message)));

  assert.match((await admin({ method: 'DELETE', url: '/api/admin/session' })).headers['set-cookie'], /Max-Age=0/);
  for (let i = 0; i < 5; i += 1) await call({ method: 'POST', url: '/api/admin/session', headers: WEB, body: { key: `guess-${i}-guess-guess-guess-guess` } });
  assert.equal((await call({ method: 'POST', url: '/api/admin/session', headers: WEB, body: { key: ADMIN_KEY } })).status, 429, 'guessing is throttled');
});

test('unsafe configurations are refused before the server starts', () => {
  const refuses = (env, pattern) => assert.throws(() => loadConfig({ FABRIC_AUTH_MODE: 'mock', DATA_DIR: 'unused', ...env }), pattern);
  refuses({ HOST: '0.0.0.0' }, /exposes the back office/);
  refuses({ TRUST_PROXY: 'true' }, /reachable through a proxy/);
  refuses({ ADMIN_KEY: 'too-short' }, /ADMIN_KEY must be at least 24/);
  refuses({ EMBED_TOKEN_MINUTES: '120' }, /EMBED_TOKEN_MINUTES/);
  refuses({ RATE_LIMITS: '{"askPerTenant":[0,1]}' }, /RATE_LIMITS\.askPerTenant/);
  refuses({ RATE_LIMITS: '{"nope":[1,1]}' }, /unknown limit/);
  refuses({ PLATFORM_WORKSPACE_ACCESS: 'release', TENANT_IDENTITY_MODE: 'off' }, /needs customer service accounts/);

  let message = '';
  try {
    loadConfig({ APP_ENV: 'production', FABRIC_AUTH_MODE: 'mock', DATA_DIR: 'unused' });
  } catch (error) {
    message = error.message;
  }
  for (const expected of [/FABRIC_AUTH_MODE=sp/, /KEY_VAULT_URL/, /SESSION_SECRET/, /ADMIN_KEY/, /PUBLIC_ORIGIN/, /email-only customer sign-in is a demo/]) assert.match(message, expected);

  const production = loadConfig({
    APP_ENV: 'production',
    FABRIC_AUTH_MODE: 'sp',
    AZURE_TENANT_ID: '00000000-0000-4000-8000-000000000001',
    AZURE_CLIENT_ID: '00000000-0000-4000-8000-000000000002',
    MANAGED_IDENTITY_CLIENT_ID: '00000000-0000-4000-8000-000000000003',
    FABRIC_CAPACITY_ID: '00000000-0000-4000-8000-000000000004',
    KEY_VAULT_URL: 'https://platform-kv.vault.azure.net',
    SESSION_SECRET: 's'.repeat(40),
    ADMIN_KEY: 'k'.repeat(40),
    PUBLIC_ORIGIN: 'https://platform.example.com',
    ALLOW_DEMO_SIGNIN: 'true',
    DATA_DIR: 'unused',
  });
  assert.equal(production.identity.mode, 'required');
  assert.equal(production.platformWorkspaceAccess, 'release');
  assert.equal(production.secrets.provider, 'keyvault');
  assert.equal(production.secureCookies, true);
  assert.equal(production.sampleDataDefault, false, 'real customers start with an empty CRM');
  assert.equal(production.credential.type, 'federated', 'the platform identity trusts its managed identity: no secret');

  // Microsoft recommends certificates over secrets; production refuses a client secret for the platform identity.
  refuses({ APP_ENV: 'production', FABRIC_AUTH_MODE: 'sp', AZURE_TENANT_ID: 'contoso.onmicrosoft.com', AZURE_CLIENT_ID: '00000000-0000-4000-8000-000000000002', AZURE_CLIENT_SECRET: 'not-a-real-secret' }, /production needs a federated credential .* or a certificate .*Client secrets are for development/);
  refuses({ FABRIC_AUTH_MODE: 'sp', AZURE_TENANT_ID: 'contoso.onmicrosoft.com', AZURE_CLIENT_ID: '00000000-0000-4000-8000-000000000002' }, /needs a credential for the platform identity/);
  refuses({ FABRIC_AUTH_MODE: 'sp', AZURE_TENANT_ID: 'contoso.onmicrosoft.com', AZURE_CLIENT_ID: '00000000-0000-4000-8000-000000000002', AZURE_CLIENT_CERTIFICATE_PATH: 'no-such-file.pem' }, /AZURE_CLIENT_CERTIFICATE_PATH: no file at no-such-file\.pem/);
});

test('.env.example loads as documented: development defaults as-is, production once the secrets are filled in', () => {
  const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
  // Like node --env-file: a quoted value loses its quotes.
  const env = Object.fromEntries(
    readFileSync(path.join(root, '.env.example'), 'utf8')
      .split(/\r?\n/)
      .filter((line) => /^[A-Z_]+=/.test(line))
      .map((line) => [line.slice(0, line.indexOf('=')), line.slice(line.indexOf('=') + 1).replace(/^"(.*)"$/, '$1')]),
  );
  const development = loadConfig({ ...env, DATA_DIR: 'unused' });
  assert.equal(development.productName, 'Platform app');
  assert.equal(development.identity.mode, 'preferred');
  assert.equal(development.platformWorkspaceAccess, 'keep');
  assert.equal(development.sampleDataDefault, true, 'an empty SAMPLE_DATA_DEFAULT keeps the default');
  assert.equal(development.embedTokenMinutes, 30);
  assert.deepEqual(development.limits.askPerUser, [10, 60000]);

  const production = loadConfig({
    ...env,
    APP_ENV: 'production',
    FABRIC_AUTH_MODE: 'sp',
    AZURE_TENANT_ID: '00000000-0000-4000-8000-000000000001',
    AZURE_CLIENT_ID: '00000000-0000-4000-8000-000000000002',
    MANAGED_IDENTITY_CLIENT_ID: '00000000-0000-4000-8000-000000000003',
    KEY_VAULT_URL: 'https://platform-kv.vault.azure.net',
    SESSION_SECRET: 's'.repeat(40),
    ADMIN_KEY: 'k'.repeat(40),
    PUBLIC_ORIGIN: 'https://platform.example.com',
    ALLOW_DEMO_SIGNIN: 'true',
    DATA_DIR: 'unused',
  });
  assert.equal(production.identity.mode, 'required');
  assert.equal(production.platformWorkspaceAccess, 'release');
  assert.equal(production.secrets.provider, 'keyvault');
});

test('security headers, Secure cookies behind HTTPS, and pinned CDN scripts', async () => {
  const { call } = makePlatform();
  const page = await call({ url: '/' });
  assert.equal(page.status, 200);
  const csp = page.headers['content-security-policy'];
  for (const directive of ["frame-ancestors 'none'", "object-src 'none'", "base-uri 'none'", "default-src 'self'"]) assert.ok(csp.includes(directive), directive);
  assert.equal(page.headers['x-frame-options'], 'DENY');
  assert.equal(page.headers['cross-origin-opener-policy'], 'same-origin');
  assert.match(page.headers['permissions-policy'], /camera=\(\)/);
  assert.equal(page.headers['strict-transport-security'], undefined, 'no HSTS on plain HTTP');

  const secure = makePlatform({ env: { PUBLIC_ORIGIN: 'https://platform.example.com', ADMIN_KEY } });
  await secure.operatorSignIn(ADMIN_KEY);
  await secure.addCustomer('Fabrikam', 'standard', 'fabrikam.com');
  const signedIn = await secure.call({ method: 'POST', url: '/api/session', headers: WEB, body: { email: 'ana@fabrikam.com' } });
  assert.match(signedIn.headers['set-cookie'], /; Secure/);
  assert.match(signedIn.headers['strict-transport-security'], /max-age=31536000/);

  const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'public');
  for (const file of ['index.html', 'admin/index.html']) {
    const html = readFileSync(path.join(root, file), 'utf8');
    const external = [...html.matchAll(/<script[^>]+src="https:[^"]+"[^>]*>/g)].map((m) => m[0]);
    assert.ok(external.length > 0, file);
    for (const tag of external) {
      assert.match(tag, /integrity="sha384-[A-Za-z0-9+/=]{64}"/, `${file}: ${tag}`);
      assert.match(tag, /crossorigin="anonymous"/, `${file}: ${tag}`);
    }
  }
  assert.match(readFileSync(path.join(root, 'app.js'), 'utf8'), /integrity: 'sha384-[A-Za-z0-9+/=]{64}'/, 'the Excel converter loaded on demand is pinned too');
});

test('embed tokens are short-lived', async () => {
  for (const [env, minutes] of [
    [{}, 30],
    [{ EMBED_TOKEN_MINUTES: '10' }, 10],
  ]) {
    const { addCustomer, signIn } = makePlatform({ env });
    await addCustomer('Fabrikam', 'enterprise', 'fabrikam.com');
    const ana = await signIn('ana@fabrikam.com');
    const { reports } = (await ana({ url: '/api/me/reports' })).json();
    const embed = (await ana({ method: 'POST', url: '/api/me/embed', body: { mode: 'view', reportId: reports[0].id } })).json();
    const left = (Date.parse(embed.expiration) - Date.now()) / 60_000;
    assert.ok(left > minutes - 1 && left <= minutes, `${left.toFixed(1)} minutes left, expected ${minutes}`);
    assert.ok(embed.expiresInSeconds > (minutes - 1) * 60 && embed.expiresInSeconds <= minutes * 60, 'the browser counts from when the token arrives, whatever its own clock says');
    assert.equal(embed.tokenRequest, undefined, 'the browser never sees the token request');
  }
});

test('database connections are bounded: least recently used and idle ones close, in-memory demo data never does', async () => {
  const dir = tempDir('platform-pools-');
  let clock = Date.parse('2026-01-01T00:00:00Z');
  const fabric = createMockFabric();
  const service = createCrmService({ fabric, identities: null, sqliteDir: dir, maxOpen: 2, idleMinutes: 15, now: () => clock, closeGraceMs: 0 });
  const tenant = (id) => ({ id, fabric: {} });
  for (const id of ['t1', 't2', 't3']) {
    const repo = await service.forTenant(tenant(id));
    await repo.migrate();
  }
  assert.equal(service.stats().open, 2);
  assert.equal(service.stats().evicted, 1);
  clock += 16 * 60_000;
  service.evict();
  assert.equal(service.stats().open, 0, 'idle connections close');
  const reopened = await service.forTenant(tenant('t1'));
  assert.equal((await reopened.counts()).calendar, 0, 'a closed database opens again on the next request');
  await service.closeAll();

  const memory = createCrmService({ fabric, identities: null, maxOpen: 1, now: () => clock });
  await memory.forTenant(tenant('a'));
  await memory.forTenant(tenant('b'));
  assert.equal(memory.stats().open, 2);
  assert.equal(memory.stats().evictable, false);
  await memory.closeAll();
  await new Promise((resolve) => setTimeout(resolve, 20));
  rmSync(dir, { recursive: true, force: true });
});

test('storage: a failed write does not block later ones, and concurrent secret writes are all kept', async () => {
  const dir = tempDir('platform-io-');
  const file = path.join(dir, 'state.json');
  const write = createJsonWriter(file);
  mkdirSync(file);
  await assert.rejects(write({ version: 1 }));
  rmSync(file, { recursive: true });
  await write({ version: 2 });
  assert.deepEqual(JSON.parse(readFileSync(file, 'utf8')), { version: 2 });

  const secretsFile = path.join(dir, 'secrets.json');
  const store = createFileSecretStore({ file: secretsFile, key: 'correct horse battery staple' });
  await store.set('tenant-first-service-account', 'first');
  await Promise.all(Array.from({ length: 20 }, (_, i) => store.set(`tenant-${i}-service-account`, `secret-${i}`)));
  const reopened = createFileSecretStore({ file: secretsFile, key: 'correct horse battery staple' });
  assert.equal(await reopened.get('tenant-first-service-account'), 'first');
  for (let i = 0; i < 20; i += 1) assert.equal(await reopened.get(`tenant-${i}-service-account`), `secret-${i}`);
  rmSync(dir, { recursive: true, force: true });
});

test('scale: 20 customers provision side by side, each isolated in its own workspace', async () => {
  const kit = provisioningKit({ config: { provisioning: { maxConcurrent: 4 }, platformWorkspaceAccess: 'release' }, fabric: createMockFabric({ latencyMs: 1 }) });
  const started = Date.now();
  const tenants = await Promise.all(Array.from({ length: 20 }, (_, i) => kit.provisionNew({ name: `Customer ${String(i).padStart(2, '0')}` })));
  assert.ok(tenants.every((t) => t.status === 'ready'), tenants.filter((t) => t.status !== 'ready').map((t) => `${t.name}: ${t.error}`).join('; '));
  const { peak } = kit.provisioner.stats();
  assert.ok(peak <= 4, `peak ${peak}`);

  const state = kit.fabric.inspect();
  const workspaces = new Set(tenants.map((t) => t.fabric.workspaceId));
  assert.equal(workspaces.size, 20, 'one workspace each');
  for (const tenant of tenants) {
    const holders = Object.entries(state.roleAssignments).filter(([, list]) => list.some((a) => a.principal.id === tenant.identity.objectId));
    assert.deepEqual(holders.map(([ws]) => ws), [tenant.fabric.workspaceId], `${tenant.name}'s account is only in its own workspace`);
    assert.equal(tenant.fabric.platformReleased, true);
  }
  const platformWorkspaces = (await kit.fabric.listWorkspaces()).map((w) => w.id);
  assert.deepEqual(platformWorkspaces, [MOCK_TEMPLATE_ID], 'no standing platform access to any customer workspace');
  assert.ok(Date.now() - started < 60_000);
});
