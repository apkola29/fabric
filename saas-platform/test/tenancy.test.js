import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { loadConfig } from '../src/config.js';
import { LOGO_MAX_BYTES, contrast, parseColor, parseLogo, themeOf } from '../src/platform/branding.js';
import { customerUrl, hostOf, platformUrl, resolveSite, uniqueSubdomain } from '../src/platform/tenancy.js';
import { WEB, makePlatform } from './support.js';

const ADMIN_KEY = 'k'.repeat(32);
const FABRIKAM = 'fabrikam.localhost:3000';
const CONTOSO = 'contoso.localhost:3000';
const APEX = 'localhost:3000';
const pilotLogo = (name) => readFileSync(new URL(`../src/platform/pilot-logos/${name}.svg`, import.meta.url));

// Two customers, each at its own address with its own logo and color.
async function twoCustomers(env = {}) {
  const platform = makePlatform({ env: { APP_DOMAIN: 'localhost', ADMIN_KEY, ...env } });
  await platform.operatorSignIn(ADMIN_KEY);
  const ids = {
    Fabrikam: await platform.addCustomer('Fabrikam', 'enterprise', 'fabrikam.com'),
    Contoso: await platform.addCustomer('Contoso', 'enterprise', 'contoso.com'),
  };
  for (const [name, color] of [['Fabrikam', '#a8431c'], ['Contoso', '#3b3a98']]) {
    const logo = await platform.admin({ method: 'PUT', url: `/api/admin/tenants/${ids[name]}/logo`, headers: { 'content-type': 'image/svg+xml' }, body: pilotLogo(name.toLowerCase()) });
    assert.equal(logo.status, 200, logo.text);
    assert.equal((await platform.admin({ method: 'PATCH', url: `/api/admin/tenants/${ids[name]}`, body: { color } })).status, 200);
  }
  const at = (host) => (request) => platform.call({ ...request, headers: { ...WEB, host, ...(request.headers || {}) } });
  async function signIn(host, email, password) {
    const res = await at(host)({ method: 'POST', url: '/api/session', body: { email, password } });
    assert.equal(res.status, 200, res.text);
    return res.headers['set-cookie'].split(';')[0];
  }
  return { ...platform, ids, at, signIn };
}

test("each customer's address shows its own name and logo, and only its own people sign in there", async () => {
  const { at, signIn, admin, ids } = await twoCustomers();
  const fabrikam = (await at(FABRIKAM)({ url: '/api/site' })).json();
  assert.deepEqual([fabrikam.mode, fabrikam.company, fabrikam.theme['--accent']], ['customer', 'Fabrikam', '#a8431c']);
  const contoso = (await at(CONTOSO)({ url: '/api/site' })).json();
  assert.deepEqual([contoso.mode, contoso.company, contoso.theme['--accent']], ['customer', 'Contoso', '#3b3a98']);

  const logo = await at(FABRIKAM)({ url: fabrikam.logoUrl });
  assert.equal(logo.status, 200);
  assert.equal(logo.headers['content-type'], 'image/svg+xml');
  assert.match(logo.headers['content-security-policy'], /sandbox/, 'a logo opened directly can never run script');
  assert.equal(logo.headers['x-content-type-options'], 'nosniff');
  assert.equal(logo.text, pilotLogo('fabrikam').toString('utf8'));
  assert.equal((await at(CONTOSO)({ url: '/api/site/logo' })).text, pilotLogo('contoso').toString('utf8'), "each address serves its own customer's logo");

  // The platform's own address only finds the company; it signs no one in.
  const platform = (await at(APEX)({ url: '/api/site' })).json();
  assert.deepEqual([platform.mode, platform.company, platform.logoUrl], ['platform', null, null]);
  const found = await at(APEX)({ method: 'POST', url: '/api/session', body: { email: 'ana@contoso.com' } });
  assert.deepEqual(found.json(), { signedIn: false, url: 'http://contoso.localhost:3000/' });
  assert.equal(found.headers['set-cookie'], undefined);
  assert.equal((await at(APEX)({ method: 'POST', url: '/api/session', body: { email: 'ana@unknown.example' } })).status, 401);

  // People from another company get the same answer as someone unknown.
  const wrongCompany = await at(FABRIKAM)({ method: 'POST', url: '/api/session', body: { email: 'ana@contoso.com' } });
  assert.equal(wrongCompany.status, 401);
  assert.equal(wrongCompany.json().error, "We couldn't find an account for that email address.");

  // A session only works at its own customer's address.
  const cookie = await signIn(FABRIKAM, 'ana@fabrikam.com');
  assert.equal((await at(FABRIKAM)({ url: '/api/me', headers: { cookie } })).json().company, 'Fabrikam');
  assert.equal((await at(CONTOSO)({ url: '/api/me', headers: { cookie } })).status, 401, "Fabrikam's session is refused at Contoso's address");
  assert.equal((await at(CONTOSO)({ url: '/api/me/crm/accounts', headers: { cookie } })).status, 401);
  assert.equal((await at(CONTOSO)({ method: 'POST', url: '/api/me/embed', headers: { cookie }, body: { mode: 'view' } })).status, 401);
  assert.equal((await at(APEX)({ url: '/api/me', headers: { cookie } })).status, 401, 'and at the platform address');

  // Named sign-ins: someone from another company gets the same answer as a wrong password.
  const added = await admin({ method: 'POST', url: `/api/admin/tenants/${ids.Fabrikam}/users`, body: { email: 'leah@fabrikam.com', role: 'manager' } });
  assert.equal(added.status, 201, added.text);
  const intruder = await at(FABRIKAM)({ method: 'POST', url: '/api/session', body: { email: 'maria@contoso.com', password: added.json().password } });
  assert.equal(intruder.status, 401);
  assert.equal(intruder.json().error, "That email and password don't match.");
  assert.ok(await signIn(FABRIKAM, 'leah@fabrikam.com', added.json().password));
});

test('the back office answers only on the platform address, and other host names are refused', async () => {
  const { at, admin, ids, operatorSignIn } = await twoCustomers();
  const operator = await operatorSignIn(ADMIN_KEY);
  assert.equal((await at(FABRIKAM)({ url: '/api/admin/tenants', headers: { cookie: operator } })).status, 404);
  assert.equal((await at(FABRIKAM)({ url: '/admin/' })).status, 404);
  assert.equal((await at(APEX)({ url: '/admin/' })).status, 200);
  assert.equal((await at('nobody.localhost:3000')({ url: '/api/site' })).status, 404);
  assert.equal((await at('nobody.localhost:3000')({ method: 'POST', url: '/api/session', body: { email: 'ana@fabrikam.com' } })).status, 404);
  assert.equal((await at('a.fabrikam.localhost:3000')({ url: '/api/site' })).status, 404, 'deeper names belong to no customer');
  assert.equal((await at('evil.example:3000')({ url: '/' })).status, 421, 'a DNS name pointed at this server is refused');
  assert.equal((await at('evil.example:3000')({ url: '/api/health' })).status, 200, 'except the health probe');

  // The detail shows the address and the branding, never the logo bytes.
  const detail = (await admin({ url: `/api/admin/tenants/${ids.Fabrikam}` })).json();
  assert.equal(detail.url, 'http://fabrikam.localhost:3000/');
  assert.deepEqual([detail.branding.color, detail.branding.logo.contentType], ['#a8431c', 'image/svg+xml']);
  assert.ok(!JSON.stringify(detail).includes(pilotLogo('fabrikam').toString('base64')));
  assert.equal((await admin({ url: detail.branding.logoUrl })).status, 200);
  assert.equal((await admin({ method: 'PATCH', url: `/api/admin/tenants/${ids.Fabrikam}`, body: { color: '#ffd400' } })).status, 400, 'too light for text');
  const bad = await admin({ method: 'PUT', url: `/api/admin/tenants/${ids.Fabrikam}/logo`, headers: { 'content-type': 'image/svg+xml' }, body: '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>' });
  assert.equal(bad.status, 400);
  assert.match(bad.json().error, /<script>/);
  assert.equal((await admin({ method: 'DELETE', url: `/api/admin/tenants/${ids.Fabrikam}/logo` })).json().branding.logo, null);
  assert.equal((await at(FABRIKAM)({ url: '/api/site/logo' })).status, 404);
});

test('behind a trusted proxy the forwarded host decides the customer; otherwise it is ignored', async () => {
  const direct = await twoCustomers();
  const spoofed = await direct.at(APEX)({ url: '/api/site', headers: { 'x-forwarded-host': FABRIKAM } });
  assert.equal(spoofed.json().mode, 'platform', 'a client cannot pick a customer with X-Forwarded-Host');
  const proxied = await twoCustomers({ TRUST_PROXY: 'true' });
  assert.equal((await proxied.at('10.0.0.5:3000')({ url: '/api/site', headers: { 'x-forwarded-host': CONTOSO } })).json().company, 'Contoso');
});

test('over HTTPS the session cookie is __Host- prefixed: Secure, host-only, whole path', async () => {
  const platform = makePlatform({ env: { APP_DOMAIN: 'hicrm.example.com', PUBLIC_ORIGIN: 'https://hicrm.example.com', ADMIN_KEY } });
  await platform.operatorSignIn(ADMIN_KEY);
  const id = await platform.addCustomer('Fabrikam', 'standard', 'fabrikam.com');
  const detail = (await platform.admin({ url: `/api/admin/tenants/${id}` })).json();
  assert.equal(detail.url, 'https://fabrikam.hicrm.example.com/');
  const res = await platform.call({ method: 'POST', url: '/api/session', headers: { ...WEB, host: 'fabrikam.hicrm.example.com' }, body: { email: 'ana@fabrikam.com' } });
  const cookie = res.headers['set-cookie'];
  assert.match(cookie, /^__Host-fsp_session=/);
  assert.match(cookie, /; Path=\/; Secure/);
  assert.doesNotMatch(cookie, /Domain=/i);
  assert.equal((await platform.call({ url: '/api/me', headers: { host: 'fabrikam.hicrm.example.com', cookie: cookie.split(';')[0] } })).status, 200);
});

test('addresses: unique, never reserved, checked at startup', () => {
  assert.equal(uniqueSubdomain('Fabrikam', []), 'fabrikam');
  assert.equal(uniqueSubdomain('Fabrikam', [{ slug: 'fabrikam' }]), 'fabrikam-2');
  assert.equal(uniqueSubdomain('Fabrikam!', [{ slug: 'fabrikam' }, { subdomain: 'fabrikam-2' }]), 'fabrikam-3');
  assert.equal(uniqueSubdomain('Admin', []), 'admin-crm');
  assert.equal(hostOf({ headers: { host: 'Fabrikam.LocalHost:3000' } }), 'fabrikam.localhost');
  assert.equal(hostOf({ headers: { host: '[::1]:3000' } }), '[::1]');
  const config = { appDomain: 'localhost', port: 3000 };
  const tenants = [{ slug: 'fabrikam' }, { slug: 'contoso', subdomain: 'contoso' }];
  assert.deepEqual(resolveSite('contoso.localhost', config, tenants), { kind: 'customer', tenant: tenants[1] });
  for (const [host, kind] of [['localhost', 'apex'], ['127.0.0.1', 'apex'], ['[::1]', 'apex'], ['', 'apex'], ['x.y.localhost', 'unknown'], ['example.com', 'foreign'], ['localhost.example.com', 'foreign']]) {
    assert.equal(resolveSite(host, config, tenants).kind, kind, host);
  }
  assert.equal(resolveSite('fabrikam.localhost', { appDomain: '' }, tenants).kind, 'single', 'without APP_DOMAIN, one address for everyone');
  assert.equal(resolveSite('fabrikam.localhost', config, [...tenants, { slug: 'x', subdomain: 'fabrikam' }]).kind, 'unknown', 'a shared address belongs to no one');

  const base = { FABRIC_AUTH_MODE: 'mock', DATA_DIR: 'unused', ADMIN_KEY };
  assert.throws(() => loadConfig({ ...base, APP_DOMAIN: 'https://hicrm.example.com' }), /APP_DOMAIN must be a host name/);
  assert.throws(() => loadConfig({ ...base, APP_DOMAIN: '10.0.0.1' }), /APP_DOMAIN must be a host name/);
  assert.throws(() => loadConfig({ ...base, APP_DOMAIN: 'hicrm.example.com', PUBLIC_ORIGIN: 'https://other.example.com' }), /PUBLIC_ORIGIN must be the address of APP_DOMAIN/);
  const live = loadConfig({ ...base, APP_DOMAIN: 'hicrm.example.com', PUBLIC_ORIGIN: 'https://hicrm.example.com' });
  assert.equal(customerUrl(live, { slug: 'fabrikam' }), 'https://fabrikam.hicrm.example.com/');
  assert.equal(platformUrl(live), 'https://hicrm.example.com/');
  assert.equal(customerUrl(loadConfig(base), { slug: 'fabrikam' }), null);
});

test('logos: plain drawings, small images, nothing that runs or loads', () => {
  for (const name of ['fabrikam', 'contoso']) assert.equal(parseLogo(pilotLogo(name)).contentType, 'image/svg+xml');
  const png = Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.alloc(32)]);
  assert.equal(parseLogo(png).contentType, 'image/png');
  assert.equal(parseLogo(Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0, 0])).contentType, 'image/jpeg');
  assert.equal(parseLogo('<svg xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="g"/></defs><rect fill="url(#g)"/><use href="#g"/></svg>').contentType, 'image/svg+xml');
  const svg = (inner, attrs = '') => `<svg xmlns="http://www.w3.org/2000/svg"${attrs}>${inner}</svg>`;
  const refused = {
    script: svg('<script>alert(1)</script>'),
    handler: svg('<rect/>', ' onload="alert(1)"'),
    external: svg('<image href="https://evil.example/x.png"/>'),
    link: svg('<a href="javascript:alert(1)"><rect/></a>'),
    html: svg('<foreignObject><div>hi</div></foreignObject>'),
    entity: `<!DOCTYPE svg [<!ENTITY x "y">]>${svg('<rect/>')}`,
    style: svg('<rect style="fill:url(https://evil.example/x)"/>'),
    use: svg('<use href="https://evil.example/s.svg#a"/>'),
    animation: svg('<set attributeName="href" to="#x"/>'),
    data: svg('<rect fill="url(data:image/png;base64,AAAA)"/>'),
  };
  for (const [kind, text] of Object.entries(refused)) assert.throws(() => parseLogo(text), /can't be used as a logo/, kind);
  assert.throws(() => parseLogo('hello'), /SVG, PNG, JPEG or WebP/);
  assert.throws(() => parseLogo(''), /empty/);
  assert.throws(() => parseLogo(Buffer.alloc(LOGO_MAX_BYTES + 1, 0x20)), /at most 64 KB/);
});

test('accent colors stay readable on the page, and the theme keeps text in the accent readable', () => {
  assert.equal(parseColor('#3B3A98'), '#3b3a98');
  assert.equal(parseColor(''), null);
  assert.throws(() => parseColor('blue'), /#RRGGBB/);
  assert.throws(() => parseColor('#ffd400'), /too light/);
  for (const color of ['#a8431c', '#3b3a98', '#1e5b4b', '#595959']) {
    const theme = themeOf(parseColor(color));
    assert.equal(theme['--accent'], color);
    assert.ok(contrast(color, theme['--accent-soft']) >= 4.5, `${color} on its soft shade`);
    assert.ok(contrast(color, '#f5f2ea') >= 4.5, `${color} on the page`);
  }
});
