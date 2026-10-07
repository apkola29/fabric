import assert from 'node:assert/strict';
import { test } from 'node:test';
import { WEB, createReadyTenant, makeApp } from './support.js';

test('serves the back office at /admin and the customer app at /, with a strict content security policy', async () => {
  const { call } = makeApp();
  const admin = await call({ url: '/admin/' });
  assert.equal(admin.status, 200);
  assert.match(admin.headers['content-type'], /text\/html/);
  assert.equal((await call({ url: '/admin' })).status, 200);
  const customer = await call({ url: '/' });
  assert.match(customer.text, /Work email/);
  assert.doesNotMatch(customer.text, /workspace|lakehouse|Fabric|semantic model/i, 'the customer app never mentions the platform');
  assert.match(customer.headers['content-security-policy'], /frame-ancestors 'none'/);
  assert.equal((await call({ url: '/../package.json' })).status, 404);
  assert.equal((await call({ url: '/%2e%2e/package.json' })).status, 404);
});

test('config describes the mode, editions and service accounts without secrets', async () => {
  const { call } = makeApp();
  const config = (await call({ url: '/api/admin/config' })).json();
  assert.equal(config.mode, 'mock');
  assert.equal(config.live, false);
  assert.equal(config.productName, 'HiCRM');
  assert.deepEqual(config.plans.map((p) => p.id), ['standard', 'professional', 'enterprise']);
  assert.deepEqual(config.addons.map((a) => a.id), ['integration']);
  assert.deepEqual(config.serviceAccounts, { mode: 'preferred', autoCreate: true });
  assert.ok(!JSON.stringify(config).includes('clientSecret'));
});

test('state-changing calls need the console header', async () => {
  const { call } = makeApp();
  const blocked = await call({ method: 'POST', url: '/api/admin/tenants', body: { name: 'X', plan: 'standard' } });
  assert.equal(blocked.status, 403);
});

test('validates new customers; earlier plan names still work', async () => {
  const { call, app } = makeApp();
  assert.equal((await call({ method: 'POST', url: '/api/admin/tenants', headers: WEB, body: { name: 'A', plan: 'standard' } })).status, 400);
  assert.equal((await call({ method: 'POST', url: '/api/admin/tenants', headers: WEB, body: { name: 'Acme', plan: 'gold' } })).status, 400);
  assert.equal((await call({ method: 'POST', url: '/api/admin/tenants', headers: WEB, body: { name: 'Acme', plan: 'standard', addons: ['rocket'] } })).status, 400);
  assert.equal((await call({ method: 'POST', url: '/api/admin/tenants', headers: WEB, body: 'not json' })).status, 415);
  const legacy = await createReadyTenant(call, app, { name: 'Acme', plan: 'analytics-ai' });
  assert.equal(legacy.planName, 'Enterprise');
  assert.equal((await call({ method: 'POST', url: '/api/admin/tenants', headers: WEB, body: { name: 'acme', plan: 'standard' } })).status, 409);
});

test('end to end: provision with a service account, check the CRM, embed reports, ask, remove', async () => {
  const { call, app } = makeApp();
  const tenant = await createReadyTenant(call, app);
  const base = `/api/admin/tenants/${tenant.id}`;
  assert.equal(tenant.identity.name, 'fabrikamsa');
  assert.equal(tenant.identity.status, 'active');
  assert.equal(tenant.serviceAccount, 'active');
  assert.ok(tenant.steps.every((s) => ['done', 'skipped'].includes(s.status)), JSON.stringify(tenant.steps));

  const crm = (await call({ url: `${base}/crm` })).json();
  assert.equal(crm.counts.accounts, 120);
  assert.ok(crm.summary.pipelineValue > 0);

  const items = (await call({ url: `${base}/items` })).json().map((i) => `${i.type}:${i.displayName}`);
  for (const expected of ['SQLDatabase:hicrm_db', 'SemanticModel:HiCRM Insights', 'Report:Sales overview', 'DataAgent:HiCRM Assistant']) assert.ok(items.includes(expected), expected);

  const { reports, datasets } = (await call({ url: `${base}/reports` })).json();
  assert.equal(reports[0].datasetId, datasets[0].id);
  const view = (await call({ method: 'POST', url: `${base}/embed`, headers: WEB, body: { mode: 'view', reportId: reports[0].id } })).json();
  // The model has row-level security, so operators embed with the role that sees every territory.
  const operator = [{ username: 'operator', roles: ['All territories'], datasets: [datasets[0].id] }];
  assert.deepEqual(view.tokenRequest, { reports: [{ id: reports[0].id }], datasets: [{ id: datasets[0].id }], identities: operator, lifetimeInMinutes: 30 });
  const create = (await call({ method: 'POST', url: `${base}/embed`, headers: WEB, body: { mode: 'create', datasetId: datasets[0].id } })).json();
  assert.deepEqual(create.tokenRequest, { datasets: [{ id: datasets[0].id }], targetWorkspaces: [{ id: tenant.fabric.workspaceId }], identities: operator, lifetimeInMinutes: 30 });

  const answer = (await call({ method: 'POST', url: `${base}/agent/ask`, headers: WEB, body: { question: 'What is the pipeline?' } })).json();
  assert.match(answer.answer, /HiCRM Insights - Assistant \(Sales Reps, Accounts, Contacts, Opportunities, Activities, Calendar\)/);

  assert.equal((await call({ method: 'DELETE', url: `${base}?confirm=wrong`, headers: WEB })).status, 400);
  assert.equal((await call({ method: 'DELETE', url: `${base}?confirm=Fabrikam`, headers: WEB })).status, 200);
  assert.equal((await call({ url: base })).status, 404);
});

test('the data integration add-on loads files next to the CRM and the assistant picks them up', async () => {
  const { call, app } = makeApp();
  const tenant = await createReadyTenant(call, app, { name: 'Loader Co', addons: ['integration'] });
  const base = `/api/admin/tenants/${tenant.id}`;
  const upload = await call({
    method: 'POST',
    url: `${base}/uploads?table=Store%20Visits&mode=Overwrite`,
    headers: { ...WEB, 'x-file-name': encodeURIComponent('visits é.csv') },
    body: Buffer.from('store,visits\nLima,12\nOslo,7\n'),
  });
  assert.equal(upload.status, 201, upload.text);
  assert.equal(upload.json().table, 'store_visits');
  assert.deepEqual(upload.json().agent.added, ['store_visits']);
  assert.deepEqual((await call({ url: `${base}/tables` })).json().map((t) => t.name), ['store_visits']);

  const plain = await createReadyTenant(call, app, { name: 'No Addon Co' });
  const refused = await call({ method: 'POST', url: `/api/admin/tenants/${plain.id}/uploads`, headers: { ...WEB, 'x-file-name': 'a.csv' }, body: Buffer.from('a\n1\n') });
  assert.equal(refused.status, 403);
});

test("one customer can't reach another customer's items", async () => {
  const { call, app } = makeApp();
  const a = await createReadyTenant(call, app, { name: 'Tenant A' });
  const b = await createReadyTenant(call, app, { name: 'Tenant B' });
  assert.notEqual(a.identity.appId, b.identity.appId, 'each customer has its own service account');
  const bReports = (await call({ url: `/api/admin/tenants/${b.id}/reports` })).json().reports;
  const crossed = await call({ method: 'POST', url: `/api/admin/tenants/${a.id}/embed`, headers: WEB, body: { mode: 'view', reportId: bReports[0].id } });
  assert.equal(crossed.status, 404);
  const run = await call({ method: 'POST', url: `/api/admin/tenants/${a.id}/items/${b.fabric.semanticModelId}/jobs`, headers: WEB, body: {} });
  assert.equal(run.status, 404);
});

test('edition features are enforced on the server', async () => {
  const { call, app } = makeApp();
  const tenant = await createReadyTenant(call, app, { name: 'Basic Co', plan: 'standard' });
  const ask = await call({ method: 'POST', url: `/api/admin/tenants/${tenant.id}/agent/ask`, headers: WEB, body: { question: 'hi' } });
  assert.equal(ask.status, 403);
  const { reports } = (await call({ url: `/api/admin/tenants/${tenant.id}/reports` })).json();
  const edit = await call({ method: 'POST', url: `/api/admin/tenants/${tenant.id}/embed`, headers: WEB, body: { mode: 'edit', reportId: reports[0].id } });
  assert.equal(edit.status, 403);
  const upgraded = await call({ method: 'PATCH', url: `/api/admin/tenants/${tenant.id}`, headers: WEB, body: { plan: 'enterprise', addons: ['integration'] } });
  assert.equal(upgraded.status, 202);
  await app.provisioner.provision(tenant.id);
  const detail = (await call({ url: `/api/admin/tenants/${tenant.id}` })).json();
  assert.deepEqual([detail.plan, detail.addons, detail.features.agent, detail.features.ingestion], ['enterprise', ['integration'], true, true]);
});

test('adopting a workspace that another customer uses is refused', async () => {
  const { call, app } = makeApp();
  const first = await createReadyTenant(call, app, { name: 'Owner' });
  const clash = await call({ method: 'POST', url: '/api/admin/tenants', headers: WEB, body: { name: 'Other', plan: 'standard', workspaceId: first.fabric.workspaceId } });
  assert.equal(clash.status, 409);
});
