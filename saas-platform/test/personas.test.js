import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ALL_TERRITORIES_ROLE } from '../src/crm/model.js';
import { TERRITORIES } from '../src/crm/schema.js';
import { pilotPersonas } from '../src/crm/seed.js';
import { createEmbedConfig } from '../src/platform/reporting.js';
import { WEB, makePlatform } from './support.js';

// The pilot: two customers, each with a sales manager who sees every territory and a rep per territory who sees only
// theirs, in the CRM, the embedded reports (row-level security roles in the embed token) and the assistant.

async function pilot() {
  const platform = makePlatform();
  const { admin, addCustomer, call, store } = platform;
  const customers = {};
  for (const [name, domain] of [['Fabrikam', 'fabrikam.com'], ['Contoso', 'contoso.com']]) {
    const id = await addCustomer(name, 'enterprise', domain);
    const people = {};
    for (const persona of pilotPersonas(store.get(id).slug, domain)) {
      const res = await admin({ method: 'POST', url: `/api/admin/tenants/${id}/users`, body: { email: persona.email, name: persona.name, role: persona.role, territories: persona.territories } });
      assert.equal(res.status, 201, res.text);
      people[persona.role === 'manager' ? 'manager' : persona.territories[0]] = { ...persona, id: res.json().user.id, password: res.json().password };
    }
    customers[name] = { id, people };
  }
  async function signIn({ email, password }) {
    const res = await call({ method: 'POST', url: '/api/session', headers: WEB, body: { email, password } });
    assert.equal(res.status, 200, res.text);
    const cookie = res.headers['set-cookie'].split(';')[0];
    return (request) => call({ ...request, headers: { ...WEB, ...(request.headers || {}), cookie } });
  }
  return { ...platform, customers, signIn };
}

const allAccounts = async (as) => (await as({ url: '/api/me/crm/accounts?limit=200' })).json();

test('the manager sees every territory and each rep only theirs: CRM, reports and assistant', async () => {
  const { customers, signIn, fabric, admin } = await pilot();
  const { people } = customers.Fabrikam;
  const manager = await signIn(people.manager);
  const me = (await manager({ url: '/api/me' })).json();
  assert.deepEqual([me.role, me.roleName, me.territories, me.name], ['manager', 'Sales manager', null, people.manager.name]);
  const everything = await allAccounts(manager);
  assert.equal(everything.total, 120);
  assert.deepEqual([...new Set(everything.rows.map((a) => a.state))].sort(), [...TERRITORIES].sort());

  const report = (await manager({ url: '/api/me/reports' })).json().reports[0];
  assert.ok(report, 'the customer has a report to open');
  const tokenFor = async (as, body) => {
    const res = await as({ method: 'POST', url: '/api/me/embed', body });
    assert.equal(res.status, 200, res.text);
    return fabric.embedTokens().at(-1).request;
  };
  const managerToken = await tokenFor(manager, { reportId: report.id });
  assert.deepEqual(managerToken.identities, [{ username: people.manager.email, roles: [ALL_TERRITORIES_ROLE], datasets: [managerToken.datasets[0].id] }]);
  const managerAnswer = (await manager({ method: 'POST', url: '/api/me/ask', body: { question: 'pipeline by state' } })).json();
  assert.deepEqual(managerAnswer.rows.map((r) => r.label).sort(), [...TERRITORIES].sort());

  let repTotal = 0;
  for (const territory of TERRITORIES) {
    const person = people[territory];
    const rep = await signIn(person);
    const profile = (await rep({ url: '/api/me' })).json();
    assert.deepEqual([profile.role, profile.territories], ['rep', [territory]]);
    assert.equal(profile.features.data, false, 'loading data is for managers');
    assert.equal((await rep({ url: '/api/me/data' })).status, 403);

    const mine = await allAccounts(rep);
    assert.ok(mine.total > 0 && mine.rows.every((a) => a.state === territory), `${person.name} sees only ${territory}`);
    assert.ok(mine.rows.some((a) => a.ownerName === person.name), `${person.name} owns some of the accounts they see`);
    repTotal += mine.total;
    const elsewhere = everything.rows.find((a) => a.state !== territory);
    assert.equal((await rep({ url: `/api/me/crm/accounts/${elsewhere.id}` })).status, 404, "another territory's account doesn't exist for the rep");
    assert.equal((await rep({ method: 'PATCH', url: `/api/me/crm/accounts/${elsewhere.id}`, body: { name: 'Taken over' } })).status, 404);
    assert.equal((await rep({ method: 'POST', url: '/api/me/crm/opportunities', body: { accountId: elsewhere.id, name: 'Poached' } })).status, 404);
    assert.equal((await rep({ method: 'POST', url: '/api/me/crm/accounts', body: { name: 'Moved in', state: elsewhere.state } })).status, 403);
    const summary = (await rep({ url: '/api/me/crm/summary' })).json();
    assert.equal(summary.accounts, mine.total);

    const token = await tokenFor(rep, { reportId: report.id });
    assert.deepEqual(token.identities.map((i) => [i.username, i.roles]), [[person.email, [territory]]], 'the embed token carries only their territory');
    // Editing and creating reports are granted per person, as in Microsoft's App-Owns-Data Starter Kit.
    assert.deepEqual(profile.reportPermissions, { view: true, edit: false, create: false });
    assert.equal((await rep({ method: 'POST', url: '/api/me/embed', body: { reportId: report.id, mode: 'edit' } })).status, 403);
    assert.equal((await rep({ method: 'POST', url: '/api/me/embed', body: { mode: 'create', datasetId: token.datasets[0].id } })).status, 403);
    assert.deepEqual((await rep({ url: '/api/me/reports' })).json().models, [], 'no models to build on without the create permission');
    const granted = await admin({ method: 'PATCH', url: `/api/admin/tenants/${customers.Fabrikam.id}/users/${person.id}`, body: { canEdit: true, canCreate: true } });
    assert.equal(granted.json().signedOut, true, 'new permissions take effect at the next sign-in');
    const author = await signIn(person);
    const editToken = await tokenFor(author, { reportId: report.id, mode: 'edit' });
    assert.deepEqual(editToken.identities[0].roles, [territory], 'editing keeps row-level security');
    const createToken = await tokenFor(author, { mode: 'create', datasetId: token.datasets[0].id });
    assert.deepEqual(createToken.identities[0].roles, [territory], 'so does building a new report');

    const answer = (await author({ method: 'POST', url: '/api/me/ask', body: { question: 'pipeline by state' } })).json();
    assert.deepEqual(answer.rows.map((r) => r.label), [territory], 'the assistant answers for their territory only');
    const sneaky = (await author({ method: 'POST', url: '/api/me/ask', body: { question: `pipeline in ${TERRITORIES.find((t) => t !== territory)}` } })).json();
    assert.equal(sneaky.rows[0].value, null, "naming another territory doesn't reveal it");
    assert.equal((await rep({ url: '/api/me' })).status, 401, 'the session from before the new permissions has ended');
  }
  assert.equal(repTotal, everything.total, 'the three territories cover every account');
});

test('report permissions shape the embed token: Save with edit; Save as and New report only with create', async () => {
  const { customers, signIn, admin, fabric, store } = await pilot();
  const { id, people } = customers.Fabrikam;
  const person = people.Georgia;
  await admin({ method: 'PATCH', url: `/api/admin/tenants/${id}/users/${person.id}`, body: { canEdit: true } });
  const editor = await signIn(person);
  assert.deepEqual((await editor({ url: '/api/me' })).json().reportPermissions, { view: true, edit: true, create: false });
  const { reports, models } = (await editor({ url: '/api/me/reports' })).json();
  assert.deepEqual(models, []);
  assert.equal((await editor({ method: 'POST', url: '/api/me/embed', body: { reportId: reports[0].id, mode: 'edit' } })).status, 200);
  const editOnly = fabric.embedTokens().at(-1).request;
  assert.deepEqual([editOnly.reports[0].allowEdit, editOnly.targetWorkspaces], [true, undefined], 'Save, but no Save as: the token names no workspace');
  assert.equal((await editor({ method: 'POST', url: '/api/me/embed', body: { mode: 'create', datasetId: editOnly.datasets[0].id } })).status, 403);

  await admin({ method: 'PATCH', url: `/api/admin/tenants/${id}/users/${person.id}`, body: { canCreate: true } });
  const author = await signIn(person);
  assert.equal((await author({ method: 'POST', url: '/api/me/embed', body: { reportId: reports[0].id, mode: 'edit' } })).status, 200);
  assert.deepEqual(fabric.embedTokens().at(-1).request.targetWorkspaces, [{ id: store.get(id).fabric.workspaceId }], 'Save as needs the workspace in the token');
  assert.equal((await admin({ method: 'PATCH', url: `/api/admin/tenants/${id}/users/${person.id}`, body: { canEdit: 'yes' } })).status, 400);
  const listed = (await admin({ url: `/api/admin/tenants/${id}/users` })).json().find((u) => u.id === person.id);
  assert.deepEqual([listed.canEdit, listed.canCreate], [true, true]);
});

test('an operator moving a rep to another territory signs them out, and the new territory applies at once', async () => {
  const { customers, signIn, admin } = await pilot();
  const { id, people } = customers.Fabrikam;
  const texas = people.Texas;
  const before = await signIn(texas);
  assert.ok((await allAccounts(before)).rows.every((a) => a.state === 'Texas'));

  const moved = await admin({ method: 'PATCH', url: `/api/admin/tenants/${id}/users/${texas.id}`, body: { role: 'rep', territories: ['Georgia'] } });
  assert.equal(moved.status, 200, moved.text);
  assert.deepEqual([moved.json().user.territories, moved.json().signedOut], [['Georgia'], true]);
  assert.equal((await before({ url: '/api/me/crm/accounts' })).status, 401, 'the old session, with the old access, has ended');
  const after = await signIn(texas);
  assert.ok((await allAccounts(after)).rows.every((a) => a.state === 'Georgia'));

  const again = (await admin({ method: 'PATCH', url: `/api/admin/tenants/${id}/users/${texas.id}`, body: { role: 'rep', territories: ['Georgia'] } })).json();
  assert.equal(again.signedOut, false, 'saving the same access keeps people signed in');
  assert.equal((await after({ url: '/api/me' })).status, 200);
  assert.equal((await admin({ method: 'PATCH', url: `/api/admin/tenants/${id}/users/${texas.id}`, body: { role: 'rep', territories: [] } })).status, 400);

  await admin({ method: 'PATCH', url: `/api/admin/tenants/${id}/users/${texas.id}`, body: { role: 'manager' } });
  assert.equal((await allAccounts(await signIn(texas))).total, 120, 'a manager sees every territory');
  const activity = (await admin({ url: `/api/admin/tenants/${id}` })).json().activity.map((a) => a.message);
  assert.ok(activity.some((m) => m.includes(`updated the sign-in of ${texas.email} (rep, Georgia); their sessions ended`)));
});

test('two customers, eight people: each company has its own team and data, whatever the territory', async () => {
  const { customers, signIn } = await pilot();
  const fabrikam = customers.Fabrikam.people;
  const contoso = customers.Contoso.people;
  assert.notEqual(fabrikam.manager.name, contoso.manager.name, 'each company has its own sales manager');
  const teams = await Promise.all([fabrikam.manager, contoso.manager].map(async (p) => (await (await signIn(p))({ url: '/api/me/crm/options' })).json().reps.map((r) => r.name).sort()));
  assert.notDeepEqual(teams[0], teams[1], 'each company has its own sales team');
  const texasBooks = await Promise.all([fabrikam.Texas, contoso.Texas].map(async (p) => (await allAccounts(await signIn(p))).rows.map((a) => `${a.name}|${a.city}`).sort()));
  assert.notDeepEqual(texasBooks[0], texasBooks[1], 'two Texas reps at two companies see two different books');
  // Both companies use the same sample record IDs (acc-0001 and on), but each person reads their own company's database.
  const fabrikamFirst = (await allAccounts(await signIn(fabrikam.manager))).rows[0];
  const sameId = await (await signIn(contoso.manager))({ url: `/api/me/crm/accounts/${fabrikamFirst.id}` });
  assert.equal(sameId.status, 200);
  const record = sameId.json();
  assert.notDeepEqual([record.name, record.city, record.ownerName], [fabrikamFirst.name, fabrikamFirst.city, fabrikamFirst.ownerName], "the record comes from Contoso's own CRM");
  assert.ok(teams[1].includes(record.ownerName));
});

test("the assistant's model has no roles, so it never reaches people limited to territories", async () => {
  const { customers, signIn, store, fabric, admin } = await pilot();
  const tenant = store.get(customers.Fabrikam.id);
  const twin = tenant.fabric.assistantModelId;
  assert.ok(twin && twin !== tenant.fabric.semanticModelId);
  // Both may build reports, so the model is the only thing in the way.
  for (const person of [customers.Fabrikam.people.manager, customers.Fabrikam.people.Texas]) {
    const granted = await admin({ method: 'PATCH', url: `/api/admin/tenants/${tenant.id}/users/${person.id}`, body: { canCreate: true } });
    assert.equal(granted.status, 200, granted.text);
  }
  const manager = await signIn(customers.Fabrikam.people.manager);
  const rep = await signIn(customers.Fabrikam.people.Texas);
  const listed = (await manager({ url: '/api/me/reports' })).json();
  assert.deepEqual(listed.models.map((m) => m.id), [tenant.fabric.semanticModelId], 'new reports are built on the model with row-level security only');
  for (const as of [manager, rep]) assert.equal((await as({ method: 'POST', url: '/api/me/embed', body: { mode: 'create', datasetId: twin } })).status, 404);

  // Even a report put on the twin by mistake doesn't open for a rep; a manager sees every territory anyway.
  const { buildStarterReportDefinition } = await import('../src/crm/report.js');
  const misplaced = await fabric.createItem(tenant.fabric.workspaceId, { displayName: 'Misplaced', type: 'Report', definition: buildStarterReportDefinition({ semanticModelId: twin }).definition });
  const opened = await rep({ method: 'POST', url: '/api/me/embed', body: { reportId: misplaced.id } });
  assert.equal(opened.status, 403);
  assert.match(opened.text, /isn't available for your territories/);
  assert.equal((await manager({ method: 'POST', url: '/api/me/embed', body: { reportId: misplaced.id } })).status, 200);
});

test("embed tokens follow Power BI's row-level security rules, and operators see every territory", async () => {
  const { customers, admin, fabric, store } = await pilot();
  const tenant = store.get(customers.Fabrikam.id);
  const client = fabric;
  const [report] = await client.pbiListReports(tenant.fabric.workspaceId);
  const secured = (await client.pbiListDatasets(tenant.fabric.workspaceId)).find((d) => d.id === report.datasetId);
  assert.deepEqual([secured.isEffectiveIdentityRequired, secured.isEffectiveIdentityRolesRequired], [true, true]);

  const embed = (identity) => createEmbedConfig({ fabric: client, tenant, reportId: report.id, identity });
  await assert.rejects(embed(null), (error) => error.status === 403, 'no identity, no token');
  await assert.rejects(embed({ username: 'x@fabrikam.com', roles: [] }), /sales territory yet/);
  await assert.rejects(client.pbiGenerateToken({ reports: [{ id: report.id }], datasets: [{ id: report.datasetId }] }), /requires effective identity/);
  await assert.rejects(
    client.pbiGenerateToken({ reports: [{ id: report.id }], datasets: [{ id: report.datasetId }], identities: [{ username: 'x', roles: ['Ohio'], datasets: [report.datasetId] }] }),
    /no role named Ohio/,
  );
  const two = await embed({ username: 'x@fabrikam.com', roles: ['Texas', 'Georgia'] });
  assert.deepEqual(two.tokenRequest.identities[0].roles, ['Texas', 'Georgia'], 'several territories are a union of roles');

  const operator = await admin({ method: 'POST', url: `/api/admin/tenants/${tenant.id}/embed`, body: { reportId: report.id } });
  assert.equal(operator.status, 200, operator.text);
  assert.deepEqual(operator.json().tokenRequest.identities[0].roles, [ALL_TERRITORIES_ROLE]);
});
