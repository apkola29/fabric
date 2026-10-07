import assert from 'node:assert/strict';
import { test } from 'node:test';
import { TERRITORIES } from '../src/crm/schema.js';
import { fabricateCrm, pilotPersonas } from '../src/crm/seed.js';
import { checkPassword, generatePassword, hashPassword, verifyPassword } from '../src/platform/users.js';
import { WEB, makePlatform } from './support.js';

// Two customers, two named sign-ins each: every person lands in their own company, with their own data.

async function twoCustomersTwoSignInsEach(options) {
  const platform = makePlatform(options);
  const { admin, addCustomer, call } = platform;
  const fabrikamId = await addCustomer('Fabrikam', 'enterprise', 'fabrikam.com');
  const contosoId = await addCustomer('Contoso', 'enterprise', 'contoso.com');
  const people = [
    { tenantId: fabrikamId, email: 'ana@fabrikam.com', name: 'Ana Lopez', role: 'manager' },
    { tenantId: fabrikamId, email: 'ben@fabrikam.com', name: 'Ben Okafor', role: 'manager' },
    { tenantId: contosoId, email: 'li@contoso.com', name: 'Li Wei', role: 'manager' },
    { tenantId: contosoId, email: 'max@contoso.com', name: 'Max Berg', role: 'manager' },
  ];
  for (const person of people) {
    const added = await admin({ method: 'POST', url: `/api/admin/tenants/${person.tenantId}/users`, body: { email: person.email, name: person.name, role: person.role } });
    assert.equal(added.status, 201, added.text);
    person.password = added.json().password;
    assert.equal(person.password.length, 20, 'a generated password is returned once');
  }
  const signIn = async (email, password) => {
    const res = await call({ method: 'POST', url: '/api/session', headers: WEB, body: { email, password } });
    if (res.status !== 200) return { status: res.status, text: res.text };
    const cookie = res.headers['set-cookie'].split(';')[0];
    return { status: 200, as: (request) => call({ ...request, headers: { ...WEB, ...(request.headers || {}), cookie } }) };
  };
  return { ...platform, fabrikamId, contosoId, people, signIn };
}

test('passwords are hashed with scrypt, checked in constant time and need 15 or more characters', async () => {
  const stored = await hashPassword('correct horse battery staple');
  assert.match(stored, /^scrypt\$131072\$8\$1\$[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+$/);
  assert.notEqual(stored, await hashPassword('correct horse battery staple'), 'a new salt every time');
  assert.equal(await verifyPassword('correct horse battery staple', stored), true);
  assert.equal(await verifyPassword('correct horse battery stapl', stored), false);
  assert.equal(await verifyPassword('anything', 'not-a-hash'), false);
  assert.throws(() => checkPassword('too-short-12'), /at least 15 characters/);
  assert.equal(generatePassword().length, 20);
});

test('two customers with two sign-ins each: everyone lands in their own company and sees its own data', async () => {
  const { admin, signIn, people, fabrikamId } = await twoCustomersTwoSignInsEach();
  const seen = {};
  for (const person of people) {
    const session = await signIn(person.email, person.password);
    assert.equal(session.status, 200, session.text);
    const me = (await session.as({ url: '/api/me' })).json();
    assert.equal(me.company, person.email.endsWith('fabrikam.com') ? 'Fabrikam' : 'Contoso');
    assert.equal(me.name, person.name);
    const options = (await session.as({ url: '/api/me/crm/options' })).json();
    seen[person.email] = options.reps.map((r) => r.name).sort().join(', ');
  }
  assert.equal(seen['ana@fabrikam.com'], seen['ben@fabrikam.com'], 'colleagues see the same company data');
  assert.equal(seen['li@contoso.com'], seen['max@contoso.com']);
  assert.notEqual(seen['ana@fabrikam.com'], seen['li@contoso.com'], 'the two customers have different data');

  const detail = await admin({ url: `/api/admin/tenants/${fabrikamId}` });
  assert.deepEqual(detail.json().users.map((u) => u.email), ['ana@fabrikam.com', 'ben@fabrikam.com']);
  assert.ok(detail.json().users.every((u) => u.lastSignInAt), 'the back office sees when people last signed in');
  assert.doesNotMatch(detail.text, /scrypt|passwordHash/, 'password hashes never leave the server');
});

test('a wrong password and an unknown person get the same answer; the demo sign-in ends once named sign-ins exist', async () => {
  const platform = makePlatform();
  const { admin, addCustomer, call } = platform;
  const id = await addCustomer('Fabrikam', 'standard', 'fabrikam.com');
  const demo = await platform.signIn('anyone@fabrikam.com');
  assert.equal((await demo({ url: '/api/me' })).status, 200, 'without named sign-ins, the demo sign-in works');

  const added = (await admin({ method: 'POST', url: `/api/admin/tenants/${id}/users`, body: { email: 'ana@fabrikam.com', role: 'manager' } })).json();
  assert.equal((await demo({ url: '/api/me' })).status, 401, 'the demo session ended');

  const attempt = (email, password) => call({ method: 'POST', url: '/api/session', headers: WEB, body: { email, password } });
  const wrong = await attempt('ana@fabrikam.com', 'not the right password');
  const unknown = await attempt('nobody@fabrikam.com', 'not the right password');
  const empty = await attempt('anyone@fabrikam.com');
  assert.equal(wrong.status, 401);
  assert.equal(unknown.status, 401);
  assert.equal(empty.status, 401, 'no more email-only sign-in for this customer');
  assert.equal(wrong.json().error, unknown.json().error, "the response doesn't reveal who has a sign-in");
  assert.equal((await attempt('ana@fabrikam.com', added.password)).status, 200);
});

test('operators can only add people on the customer domains, once; a new password or removal signs them out', async () => {
  const { admin, signIn, people, fabrikamId, contosoId } = await twoCustomersTwoSignInsEach();
  const add = (tenantId, body) => admin({ method: 'POST', url: `/api/admin/tenants/${tenantId}/users`, body: { role: 'manager', ...body } });
  assert.equal((await add(fabrikamId, { email: 'li@contoso.com' })).status, 400, "Contoso's people can't be added to Fabrikam");
  assert.equal((await add(fabrikamId, { email: 'ana@fabrikam.com' })).status, 409);
  assert.equal((await add(fabrikamId, { email: 'cy@fabrikam.com', password: 'short' })).status, 400);
  assert.match((await add(fabrikamId, { email: 'cy@fabrikam.com', role: undefined })).text, /Choose a role/, 'the operator always chooses the access');
  assert.match((await add(fabrikamId, { email: 'cy@fabrikam.com', role: 'rep' })).text, /at least one territory/);
  assert.match((await add(fabrikamId, { email: 'cy@fabrikam.com', role: 'rep', territories: ['Ohio'] })).text, /Unknown territory: Ohio/);
  const chosen = await add(fabrikamId, { email: 'cy@fabrikam.com', password: 'a long chosen passphrase' });
  assert.equal(chosen.status, 201);
  assert.equal(chosen.json().password, null, 'a password the operator chose is never echoed back');

  const [ana] = people;
  const before = await signIn(ana.email, ana.password);
  const anaId = (await admin({ url: `/api/admin/tenants/${fabrikamId}/users` })).json().find((u) => u.email === ana.email).id;
  const reset = (await admin({ method: 'POST', url: `/api/admin/tenants/${fabrikamId}/users/${anaId}/password`, body: {} })).json();
  assert.equal((await before.as({ url: '/api/me' })).status, 401, 'a new password ends existing sessions');
  assert.equal((await signIn(ana.email, ana.password)).status, 401, 'the old password stops working');
  const after = await signIn(ana.email, reset.password);
  assert.equal(after.status, 200);

  assert.equal((await admin({ method: 'DELETE', url: `/api/admin/tenants/${fabrikamId}/users/${anaId}` })).status, 200);
  assert.equal((await after.as({ url: '/api/me' })).status, 401, 'removing a person ends their sessions');
  assert.equal((await signIn(ana.email, reset.password)).status, 401);

  const li = people.find((p) => p.email === 'li@contoso.com');
  assert.equal((await signIn('ben@fabrikam.com', li.password)).status, 401, "another customer's password opens nothing");
  const activity = (await admin({ url: `/api/admin/tenants/${fabrikamId}` })).json().activity.map((a) => a.message);
  assert.ok(activity.some((m) => /added a sign-in for cy@fabrikam\.com/.test(m)));
  assert.ok(activity.some((m) => /reset the password of ana@fabrikam\.com/.test(m)));
  assert.ok(activity.some((m) => /removed the sign-in of ana@fabrikam\.com/.test(m)));
  assert.equal((await admin({ url: `/api/admin/tenants/${contosoId}/users` })).json().length, 2, 'Contoso is untouched');
});

test('password guessing against one person is throttled', async () => {
  const { signIn } = await twoCustomersTwoSignInsEach({ env: { RATE_LIMITS: JSON.stringify({ signInPerAccount: [3, 60_000] }) } });
  for (let i = 0; i < 3; i += 1) assert.equal((await signIn('ana@fabrikam.com', `wrong password number ${i}`)).status, 401);
  assert.equal((await signIn('ana@fabrikam.com', 'wrong password number 4')).status, 429);
  assert.equal((await signIn('ben@fabrikam.com', 'wrong password number 1')).status, 401, 'other people are unaffected');
});

test('every customer gets its own sales team and industry mix, with the same structure', () => {
  const a = fabricateCrm('tenant-a', { companyDomain: 'fabrikam.com' });
  const b = fabricateCrm('tenant-b', { companyDomain: 'contoso.com' });
  assert.deepEqual(a.sales_reps.map((r) => r.rep_id), ['rep-01', 'rep-02', 'rep-03', 'rep-04', 'rep-05', 'rep-06', 'rep-07', 'rep-08']);
  assert.deepEqual(a.sales_reps.map((r) => r.region), ['Texas', 'Texas', 'Texas', 'Georgia', 'Georgia', 'Georgia', 'New Mexico', 'New Mexico']);
  assert.notDeepEqual(a.sales_reps.map((r) => r.name), b.sales_reps.map((r) => r.name));
  assert.equal(new Set(a.sales_reps.map((r) => r.name)).size, 8, 'no rep twice');
  assert.ok(a.sales_reps.every((r) => r.email.endsWith('@fabrikam.com')));
  const mix = (data) => Object.entries(Object.groupBy(data.accounts, (x) => x.industry)).map(([k, v]) => [k, v.length]).sort((x, y) => y[1] - x[1]);
  assert.notDeepEqual(mix(a).slice(0, 3).map(([k]) => k), mix(b).slice(0, 3).map(([k]) => k), 'different top industries');
  assert.deepEqual(fabricateCrm('tenant-a', { companyDomain: 'fabrikam.com' }).sales_reps, a.sales_reps, 'deterministic per customer');

  // Territories: every account is in one, and its owner (and the owner of each of its deals) covers it.
  const territoryOf = new Map(a.sales_reps.map((r) => [r.rep_id, r.region]));
  const stateOf = new Map(a.accounts.map((x) => [x.account_id, x.state]));
  assert.deepEqual([...new Set(a.accounts.map((x) => x.state))].sort(), [...TERRITORIES].sort());
  assert.ok(a.accounts.every((x) => territoryOf.get(x.owner_id) === x.state && x.country === 'United States'));
  assert.ok(a.opportunities.every((o) => territoryOf.get(o.owner_id) === stateOf.get(o.account_id)));

  // The pilot's people: the sales manager plus one rep per territory, matching the CRM's sales team.
  const personas = pilotPersonas('tenant-a', 'fabrikam.com');
  assert.deepEqual(personas.map((p) => [p.role, p.territories.join()]), [['manager', ''], ...TERRITORIES.map((t) => ['rep', t])]);
  for (const persona of personas.filter((p) => p.role === 'rep')) {
    assert.ok(a.sales_reps.some((r) => r.email === persona.email && r.name === persona.name && r.region === persona.territories[0]));
  }
  assert.ok(!a.sales_reps.some((r) => r.email === personas[0].email), 'the manager owns no accounts');
});
