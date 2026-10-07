import assert from 'node:assert/strict';
import { test } from 'node:test';
import { loadConfig } from '../src/config.js';
import { ALL_TERRITORIES_ROLE } from '../src/crm/model.js';
import { TERRITORIES } from '../src/crm/schema.js';
import { setUpPilot } from '../src/platform/pilot.js';
import { WEB, makePlatform } from './support.js';

// "View as": on this computer, pick any of a company's people and see the app, and its reports, the way they do. The
// two pilot companies, each at its own address with its own logo, a sales manager and a sales rep per territory.

const LOOPBACK = '127.0.0.1';
const at = (company) => ({ ...WEB, host: `${company}.localhost:3000` });

async function pilot(env = {}) {
  const platform = makePlatform({ env: { APP_DOMAIN: 'localhost', ...env } });
  const setup = await setUpPilot({ store: platform.store, provisioner: platform.app.provisioner, crm: platform.app.crm });
  for (const result of setup) if (result.error) throw new Error(result.error);
  const local = (company, request) => platform.call({ remoteAddress: LOOPBACK, ...request, headers: { ...at(company), ...(request.headers || {}) } });
  const viewAs = async (company, email) => {
    const res = await local(company, { method: 'POST', url: '/api/persona', body: { email } });
    assert.equal(res.status, 200, res.text);
    const cookie = res.headers['set-cookie'].split(';')[0];
    return (request) => local(company, { ...request, headers: { ...(request.headers || {}), cookie } });
  };
  return { ...platform, setup, local, viewAs };
}

test('"View as" lists the company\'s people at its own address, the manager first, and links to the other companies', async () => {
  const { local, viewAs, call } = await pilot();
  for (const [company, domain, other] of [['fabrikam', 'fabrikam.com', 'Contoso'], ['contoso', 'contoso.com', 'Fabrikam']]) {
    const listed = await local(company, { url: '/api/personas' });
    assert.equal(listed.status, 200, listed.text);
    const { current, companies } = listed.json();
    assert.equal(current, null, 'nobody is signed in yet');
    const [here, elsewhere] = companies;
    assert.equal(here.here, true);
    assert.equal(here.url, `http://${company}.localhost:3000/`);
    assert.deepEqual(here.personas.map((p) => [p.role, p.roleName, p.territories]), [
      ['manager', 'Sales manager', null],
      ...TERRITORIES.map((t) => ['rep', 'Sales rep', [t]]),
    ]);
    assert.ok(here.personas.every((p) => p.name && p.email.endsWith(`@${domain}`)), 'only this company\'s people');
    assert.deepEqual([elsewhere.company, elsewhere.here, elsewhere.personas], [other, false, []], 'another company is a link to its own address, not its people');
    assert.equal(elsewhere.url, `http://${other.toLowerCase()}.localhost:3000/`);
    assert.ok(!/password|hash|sessionVersion/i.test(listed.text), 'nothing secret is listed');

    const rep = here.personas.find((p) => p.territories?.[0] === 'Georgia');
    const asRep = await viewAs(company, rep.email);
    assert.equal((await asRep({ url: '/api/personas' })).json().current, rep.email);
    const me = (await asRep({ url: '/api/me' })).json();
    assert.deepEqual([me.email, me.role, me.territories, me.company, me.personaSwitcher], [rep.email, 'rep', ['Georgia'], here.company, true]);
  }
  // The platform's own address finds the companies; it signs nobody in.
  const apex = await call({ url: '/api/personas', headers: { ...WEB, host: 'localhost:3000' }, remoteAddress: LOOPBACK });
  assert.deepEqual(apex.json().companies.map((c) => [c.company, c.here, c.personas.length]), [['Contoso', false, 0], ['Fabrikam', false, 0]]);
  const fabrikamManager = (await local('fabrikam', { url: '/api/personas' })).json().companies[0].personas[0];
  assert.equal((await call({ method: 'POST', url: '/api/persona', headers: { ...WEB, host: 'localhost:3000' }, remoteAddress: LOOPBACK, body: { email: fabrikamManager.email } })).status, 404);
});

test('each person gets an embed token with their own identity and row-level security role, from their company\'s model', async () => {
  const { local, viewAs, fabric, store } = await pilot();
  for (const company of ['fabrikam', 'contoso']) {
    const tenant = store.list().find((t) => t.name.toLowerCase() === company);
    const site = (await local(company, { url: '/api/site' })).json();
    assert.deepEqual([site.company, site.mode, Boolean(site.logoUrl)], [tenant.name, 'customer', true], 'each company shows its own name and logo');
    const { personas } = (await local(company, { url: '/api/personas' })).json().companies[0];
    const seen = {};
    for (const person of personas) {
      const as = await viewAs(company, person.email);
      const report = (await as({ url: '/api/me/reports' })).json().reports[0];
      assert.ok(report, `${person.name} has a report to open`);
      const opened = await as({ method: 'POST', url: '/api/me/embed', body: { reportId: report.id } });
      assert.equal(opened.status, 200, opened.text);
      assert.ok(!('tokenRequest' in opened.json()), 'the token request stays on the server');
      const request = fabric.embedTokens().at(-1).request;
      const roles = person.role === 'manager' ? [ALL_TERRITORIES_ROLE] : person.territories;
      assert.deepEqual(request.identities, [{ username: person.email, roles, datasets: [tenant.fabric.semanticModelId] }], `${person.email}: their email, their role, their company's model`);
      assert.deepEqual(request.reports.map((r) => r.id), [report.id]);
      // The app's own pages apply the same scope as the report.
      const accounts = (await as({ url: '/api/me/crm/accounts?limit=200' })).json();
      seen[person.role === 'manager' ? 'manager' : person.territories[0]] = new Set(accounts.rows.map((a) => a.state));
    }
    assert.deepEqual([...seen.manager].sort(), [...TERRITORIES].sort(), 'the manager sees every state');
    for (const territory of TERRITORIES) assert.deepEqual([...seen[territory]], [territory], `the ${territory} rep sees ${territory} only`);
  }
});

test('"View as" never crosses companies, and a session works only at its own company\'s address', async () => {
  const { local, viewAs } = await pilot();
  const contosoRep = (await local('contoso', { url: '/api/personas' })).json().companies[0].personas[1];
  assert.equal((await local('fabrikam', { method: 'POST', url: '/api/persona', body: { email: contosoRep.email } })).status, 404, "Contoso's people aren't at Fabrikam's address");
  assert.equal((await local('fabrikam', { method: 'POST', url: '/api/persona', body: { email: 'nobody@fabrikam.com' } })).status, 404);
  const asContoso = await viewAs('contoso', contosoRep.email);
  const cookie = (await local('contoso', { method: 'POST', url: '/api/persona', body: { email: contosoRep.email } })).headers['set-cookie'].split(';')[0];
  assert.equal((await asContoso({ url: '/api/me' })).status, 200);
  assert.equal((await local('fabrikam', { url: '/api/me', headers: { cookie } })).status, 401, "a Contoso session doesn't work at Fabrikam's address");
});

test('"View as" works only on this computer, at a local address, with the app header, and never in production', async () => {
  const { call, local } = await pilot();
  const email = (await local('fabrikam', { url: '/api/personas' })).json().companies[0].personas[0].email;
  const refused = (res, why) => assert.equal(res.status, 404, `${why}: ${res.status} ${res.text}`);
  for (const remoteAddress of ['10.1.2.3', '192.168.1.20', '::ffff:10.0.0.7', '2001:db8::5']) {
    refused(await call({ url: '/api/personas', headers: at('fabrikam'), remoteAddress }), `from ${remoteAddress}`);
    refused(await call({ method: 'POST', url: '/api/persona', headers: at('fabrikam'), remoteAddress, body: { email } }), `signing in from ${remoteAddress}`);
  }
  refused(await call({ url: '/api/personas', headers: at('fabrikam') }), 'no known address');
  refused(await local('fabrikam', { url: '/api/personas', headers: { 'x-forwarded-for': '203.0.113.9' } }), 'relayed (X-Forwarded-For)');
  refused(await local('fabrikam', { url: '/api/personas', headers: { forwarded: 'for=203.0.113.9;proto=https' } }), 'relayed (Forwarded)');
  refused(await local('nobody', { url: '/api/personas' }), 'an address no company has');
  assert.equal((await call({ method: 'POST', url: '/api/persona', headers: { host: 'fabrikam.localhost:3000' }, remoteAddress: LOOPBACK, body: { email } })).status, 403, 'state changes need the app header');
  assert.equal((await call({ url: '/api/personas', headers: { ...WEB, host: '127.0.0.1:3000' }, remoteAddress: LOOPBACK })).status, 200, 'a loopback host name works');
  assert.equal((await call({ url: '/api/personas', headers: { ...WEB, host: '[::1]:3000' }, remoteAddress: '::1' })).status, 200, 'over IPv6 too');

  // A real domain: the company's address isn't local, so a page anywhere can't use it through DNS rebinding.
  const hosted = await pilot({ APP_DOMAIN: 'hicrm.example.com', ADMIN_KEY: 'k'.repeat(32) });
  refused(await hosted.call({ url: '/api/personas', headers: { ...WEB, host: 'fabrikam.hicrm.example.com' }, remoteAddress: LOOPBACK }), 'a public host name');

  const off = await pilot({ PERSONA_SWITCHER: 'false' });
  refused(await off.local('fabrikam', { url: '/api/personas' }), 'switched off');
  refused(await off.local('fabrikam', { method: 'POST', url: '/api/persona', body: { email } }), 'switched off, signing in');

  assert.equal(loadConfig({ FABRIC_AUTH_MODE: 'mock' }).personaSwitcher, true, 'on by default for local runs');
  assert.equal(loadConfig({ FABRIC_AUTH_MODE: 'mock', TRUST_PROXY: 'true', ADMIN_KEY: 'k'.repeat(24) }).personaSwitcher, false, 'off by default behind a proxy');
  assert.equal(loadConfig({ FABRIC_AUTH_MODE: 'mock', PUBLIC_ORIGIN: 'https://hicrm.example.com', ADMIN_KEY: 'k'.repeat(24) }).personaSwitcher, false, 'off by default at a public address');
  assert.throws(() => loadConfig({ FABRIC_AUTH_MODE: 'mock', TRUST_PROXY: 'true', ADMIN_KEY: 'k'.repeat(24), PERSONA_SWITCHER: 'true' }), /PERSONA_SWITCHER signs people in without a password, so it only runs without TRUST_PROXY/);
  assert.throws(() => loadConfig({ FABRIC_AUTH_MODE: 'mock', APP_ENV: 'production', PERSONA_SWITCHER: 'true' }), /PERSONA_SWITCHER signs people in without a password; it is for local demos and testing only/);
  assert.equal((await off.local('fabrikam', { method: 'POST', url: '/api/session', body: { email, password: 'wrong' } })).status, 401, 'password sign-in still works as before');
});
