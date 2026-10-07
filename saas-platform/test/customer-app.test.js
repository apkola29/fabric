import assert from 'node:assert/strict';
import { test } from 'node:test';
import { WEB, makeApp } from './support.js';

async function makePlatform(options) {
  const platform = makeApp(options);
  const { app, call } = platform;
  async function addCustomer(name, plan, domain, extra = {}) {
    const created = await call({ method: 'POST', url: '/api/admin/tenants', headers: WEB, body: { name, plan, domains: [domain], ...extra } });
    assert.equal(created.status, 202, created.text);
    await app.provisioner.provision(created.json().id);
    return created.json().id;
  }
  async function signIn(email) {
    const res = await call({ method: 'POST', url: '/api/session', headers: WEB, body: { email } });
    assert.equal(res.status, 200, res.text);
    const cookie = res.headers['set-cookie'].split(';')[0];
    return (request) => call({ ...request, headers: { ...WEB, ...(request.headers || {}), cookie } });
  }
  return { ...platform, addCustomer, signIn };
}

test('users sign in with their work email and land in their own company', async () => {
  const { call, addCustomer, signIn } = await makePlatform();
  await addCustomer('Fabrikam', 'enterprise', 'fabrikam.com');
  assert.equal((await call({ url: '/api/me' })).status, 401);
  assert.equal((await call({ method: 'POST', url: '/api/session', headers: WEB, body: { email: 'ana@unknown.com' } })).status, 401);
  assert.equal((await call({ method: 'POST', url: '/api/session', headers: WEB, body: { email: 'not-an-email' } })).status, 400);

  const as = await signIn('Ana@Fabrikam.com');
  const me = (await as({ url: '/api/me' })).json();
  assert.equal(me.company, 'Fabrikam');
  assert.equal(me.email, 'ana@fabrikam.com');
  assert.equal(me.product, 'Platform app');
  assert.equal(me.status, 'ready');
  assert.deepEqual(me.features, { crm: true, reports: true, authoring: true, ask: true, data: false });
  const text = JSON.stringify(me).toLowerCase();
  for (const word of ['workspace', 'lakehouse', 'plan', 'fabric', 'capacity', 'semantic']) assert.ok(!text.includes(word), `/api/me mentions ${word}`);
});

test('a tampered session cookie is rejected', async () => {
  const { call, addCustomer } = await makePlatform();
  await addCustomer('Fabrikam', 'standard', 'fabrikam.com');
  const res = await call({ method: 'POST', url: '/api/session', headers: WEB, body: { email: 'ana@fabrikam.com' } });
  const [name, value] = res.headers['set-cookie'].split(';')[0].split('=');
  const [payload, signature] = value.split('.');
  const forged = Buffer.from(JSON.stringify({ ...JSON.parse(Buffer.from(payload, 'base64url')), t: 'someone-else' })).toString('base64url');
  assert.equal((await call({ url: '/api/me', headers: { cookie: `${name}=${forged}.${signature}` } })).status, 401);
  const signedOut = await call({ method: 'DELETE', url: '/api/session', headers: WEB });
  assert.match(signedOut.headers['set-cookie'], /Max-Age=0/);
});

test('the CRM: summary, lists, records and validation, all inside the signed-in company', async () => {
  const { addCustomer, signIn } = await makePlatform();
  await addCustomer('Fabrikam', 'standard', 'fabrikam.com');
  await addCustomer('Contoso', 'standard', 'contoso.com', { sampleData: false });
  const fab = await signIn('ana@fabrikam.com');
  const con = await signIn('li@contoso.com');

  const summary = (await fab({ url: '/api/me/crm/summary' })).json();
  assert.equal(summary.accounts, 120);
  assert.equal((await con({ url: '/api/me/crm/summary' })).json().accounts, 0, 'a customer without sample data starts empty');

  const options = (await fab({ url: '/api/me/crm/options' })).json();
  assert.equal(options.reps.length, 8);
  const accounts = (await fab({ url: '/api/me/crm/accounts?limit=5&sort=pipeline&direction=desc' })).json();
  assert.equal(accounts.rows.length, 5);
  assert.equal(accounts.total, 120);

  const created = await fab({ method: 'POST', url: '/api/me/crm/accounts', body: { name: 'Northwind Health', industry: 'Healthcare', ownerId: options.reps[0].id } });
  assert.equal(created.status, 201, created.text);
  const account = created.json();
  assert.equal((await fab({ method: 'POST', url: '/api/me/crm/accounts', body: { name: '' } })).status, 400);
  const deal = (await fab({ method: 'POST', url: '/api/me/crm/opportunities', body: { accountId: account.id, name: 'Clinic rollout', amount: 80000, closeDate: '2026-12-01' } })).json();
  const won = (await fab({ method: 'PATCH', url: `/api/me/crm/opportunities/${deal.id}`, body: { stage: 'Closed Won' } })).json();
  assert.equal(won.probability, 100);
  const activity = await fab({ method: 'POST', url: '/api/me/crm/activities', body: { accountId: account.id, opportunityId: deal.id, type: 'Meeting', subject: 'Kickoff', date: '2026-10-05' } });
  assert.equal(activity.status, 201, activity.text);
  const contact = await fab({ method: 'POST', url: '/api/me/crm/contacts', body: { accountId: account.id, firstName: 'Mia', lastName: 'Wong', email: 'mia@northwind.example' } });
  assert.equal(contact.status, 201, contact.text);
  const detail = (await fab({ url: `/api/me/crm/accounts/${account.id}` })).json();
  assert.deepEqual([detail.opportunities.length, detail.activities.length, detail.contacts.length], [1, 1, 1]);

  assert.equal((await con({ url: `/api/me/crm/accounts/${account.id}` })).status, 404, "another company can't open it");
  assert.equal((await fab({ url: '/api/me/crm/lookup/accounts?q=northwind' })).json()[0].name, 'Northwind Health');
});

test('reports and embed tokens stay inside the signed-in company', async () => {
  const { addCustomer, signIn } = await makePlatform();
  await addCustomer('Fabrikam', 'professional', 'fabrikam.com');
  await addCustomer('Contoso', 'professional', 'contoso.com');
  const fab = await signIn('ana@fabrikam.com');
  const con = await signIn('li@contoso.com');
  const listing = (await fab({ url: '/api/me/reports' })).json();
  assert.deepEqual(listing.reports.map((r) => r.name), ['Sales overview']);
  assert.equal(listing.models.length, 1);
  const view = await fab({ method: 'POST', url: '/api/me/embed', body: { mode: 'view', reportId: listing.reports[0].id } });
  assert.equal(view.status, 200, view.text);
  assert.equal(view.json().demo, true);
  assert.equal(view.json().tokenRequest, undefined, 'token requests stay on the server');
  const create = await fab({ method: 'POST', url: '/api/me/embed', body: { mode: 'create', datasetId: listing.models[0].id } });
  assert.equal(create.status, 200, create.text);
  assert.equal((await con({ method: 'POST', url: '/api/me/embed', body: { mode: 'view', reportId: listing.reports[0].id } })).status, 404);
  assert.equal((await con({ method: 'POST', url: '/api/me/embed', body: { mode: 'create', datasetId: listing.models[0].id } })).status, 404);
});

test('describe a chart returns the visual to build, with preview data in demo mode', async () => {
  const { addCustomer, signIn } = await makePlatform();
  await addCustomer('Fabrikam', 'professional', 'fabrikam.com');
  await addCustomer('Basic Co', 'standard', 'basic.com');
  const fab = await signIn('ana@fabrikam.com');
  const fields = (await fab({ url: '/api/me/reports/fields' })).json();
  assert.ok(fields.measures.some((m) => m.name === 'Win Rate'));
  const visual = (await fab({ method: 'POST', url: '/api/me/reports/describe', body: { text: 'pipeline by industry as a bar chart' } })).json();
  assert.equal(visual.ok, true);
  assert.equal(visual.visualType, 'clusteredBarChart');
  assert.deepEqual(visual.measure, { table: 'Opportunities', name: 'Pipeline Value' });
  assert.deepEqual(visual.dimension, { table: 'Accounts', column: 'Industry' });
  assert.ok(visual.preview.rows.length >= 5);
  assert.equal((await fab({ method: 'POST', url: '/api/me/reports/describe', body: { text: '' } })).status, 400);
  const basic = await signIn('bo@basic.com');
  assert.equal((await basic({ method: 'POST', url: '/api/me/reports/describe', body: { text: 'pipeline by stage' } })).status, 403);
});

test('the assistant answers from the CRM, offers examples when it cannot, and needs the Enterprise edition', async () => {
  const { addCustomer, signIn } = await makePlatform();
  await addCustomer('Fabrikam', 'enterprise', 'fabrikam.com');
  await addCustomer('Pro Co', 'professional', 'pro.com');
  const fab = await signIn('ana@fabrikam.com');
  const answer = (await fab({ method: 'POST', url: '/api/me/ask', body: { question: 'top 3 accounts by pipeline' } })).json();
  assert.equal(answer.source, 'quick');
  assert.match(answer.answer, /^Top 3 by Pipeline Value\. Highest: /);
  assert.equal(answer.rows.length, 3);
  const unknown = (await fab({ method: 'POST', url: '/api/me/ask', body: { question: 'tell me a joke' } })).json();
  assert.ok(unknown.suggestions.length >= 3);
  assert.equal((await fab({ method: 'POST', url: '/api/me/ask', body: { question: '' } })).status, 400);
  const pro = await signIn('pat@pro.com');
  assert.equal((await pro({ method: 'POST', url: '/api/me/ask', body: { question: 'pipeline' } })).status, 403);
});

test('data loading is only there with the data integration add-on', async () => {
  const { addCustomer, signIn } = await makePlatform();
  await addCustomer('Fabrikam', 'enterprise', 'fabrikam.com', { addons: ['integration'] });
  await addCustomer('Plain Co', 'enterprise', 'plain.com');
  const fab = await signIn('ana@fabrikam.com');
  assert.equal((await fab({ url: '/api/me' })).json().features.data, true);
  const upload = await fab({ method: 'POST', url: '/api/me/uploads?name=NPS%20survey', headers: { 'x-file-name': 'nps.csv' }, body: Buffer.from('score,comment\n9,great\n4,slow\n') });
  assert.equal(upload.status, 201, upload.text);
  assert.deepEqual((await fab({ url: '/api/me/data' })).json().map((d) => [d.name, d.rows]), [['NPS survey', 2]]);
  const plain = await signIn('al@plain.com');
  assert.equal((await plain({ url: '/api/me/data' })).status, 403);
});
