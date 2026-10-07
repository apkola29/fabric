import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { browserArgs, findBrowser, parseExportedRows } from '../src/platform/browser.js';
import { assessTenantSettings, CONTROLS, countResults, createEmulatedPlatform, formatScorecard, probePeople, refused, toMarkdown, validatePlatform } from '../src/platform/validation.js';

// The framework itself: its boundary with the sample application, its controls, and the validator that checks them.

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const CORE = ['src/auth', 'src/fabric', 'src/http', 'src/platform', 'src/util'];
const byId = (results) => Object.fromEntries(results.map((r) => [r.id, r]));

test('the framework core reaches the sample application only through its workload contract', () => {
  const offenders = [];
  for (const dir of CORE) {
    for (const file of readdirSync(path.join(ROOT, dir)).filter((f) => f.endsWith('.js'))) {
      const source = readFileSync(path.join(ROOT, dir, file), 'utf8');
      for (const [, target] of source.matchAll(/from '(\.\.\/crm\/[^']+)'/g)) if (target !== '../crm/workload.js') offenders.push(`${dir}/${file} imports ${target}`);
    }
  }
  assert.deepEqual(offenders, [], 'import from src/crm/workload.js instead');
});

test('FRAMEWORK.md lists the same controls as the validator, checked the same ways, and every named test exists', () => {
  const doc = readFileSync(path.join(ROOT, 'FRAMEWORK.md'), 'utf8');
  const section = doc.slice(doc.indexOf('## 6. Controls'), doc.indexOf('## 7.'));
  const rows = [...section.matchAll(/^\| ([A-Z]{2,3}-\d{2}) \| [^|]+ \| ([^|]+) \|/gm)].map(([, id, checkedBy]) => ({ id, checkedBy: checkedBy.trim() }));
  assert.deepEqual(rows.map((r) => r.id), CONTROLS.map((c) => c.id), 'same controls, same order');
  for (const control of CONTROLS) {
    const { checkedBy } = rows.find((r) => r.id === control.id);
    assert.equal(/validator/.test(checkedBy), control.how.includes('auto'), `${control.id}: "validator" in FRAMEWORK.md`);
    assert.equal(/browser/.test(checkedBy), control.how.includes('browser'), `${control.id}: "browser" in FRAMEWORK.md`);
    assert.equal(/tests/.test(checkedBy), control.tests.length > 0, `${control.id}: "tests" in FRAMEWORK.md`);
    for (const file of control.tests) assert.ok(existsSync(path.join(ROOT, file)), `${control.id} names ${file}, which doesn't exist`);
  }
  assert.equal(new Set(CONTROLS.map((c) => c.id)).size, CONTROLS.length, 'control IDs are unique');
});

test('the validator checks every person\'s reports: the manager and a rep per territory, or stand-ins', () => {
  const users = [
    { email: 'rep.ga@fabrikam.com', role: 'rep', territories: ['Georgia'] },
    { email: 'boss@fabrikam.com', role: 'manager' },
    { email: 'rep.tx@fabrikam.com', role: 'rep', territories: ['Texas'] },
    { email: 'second.tx@fabrikam.com', role: 'rep', territories: ['Texas'] },
    { email: 'rep.nm@fabrikam.com', role: 'rep', territories: ['New Mexico'] },
  ];
  assert.deepEqual(Object.entries(probePeople({ domains: ['fabrikam.com'], users })).map(([kind, p]) => [kind, p.email]), [
    ['manager', 'boss@fabrikam.com'],
    ['Texas rep', 'rep.tx@fabrikam.com'],
    ['New Mexico rep', 'rep.nm@fabrikam.com'],
    ['Georgia rep', 'rep.ga@fabrikam.com'],
  ]);
  assert.deepEqual(Object.entries(probePeople({ domains: ['contoso.com'] })).map(([kind, p]) => [kind, p.email, p.territories]), [
    ['manager', 'validator.manager@contoso.com', null],
    ['Texas rep', 'validator.rep@contoso.com', ['Texas']],
  ]);
});

test('the validator passes the emulated platform: two tenants with their own service principals, the platform released', async () => {
  const platform = await createEmulatedPlatform();
  try {
    const results = byId(await validatePlatform(platform));
    const failing = Object.values(results).filter((r) => r.status === 'fail' || r.status === 'warn');
    assert.deepEqual(failing.map((r) => `${r.id}: ${r.details.map((d) => d.detail).join(' | ')}`), []);
    assert.equal(results['DAT-01'].status, 'skip', 'SQL database in Fabric needs --live');
    assert.equal(results['RLS-03'].status, 'skip', 'the rendered report needs --live --browser');
    for (const control of CONTROLS.filter((c) => c.how.length === 1 && c.how[0] === 'tests')) assert.equal(results[control.id].status, 'tests', control.id);
    for (const control of CONTROLS.filter((c) => c.how.includes('auto') && c.id !== 'DAT-01')) assert.equal(results[control.id].status, 'pass', control.id);
    assert.equal(results['ISO-02'].details.length, 2, 'each tenant tried against the other');
    assert.match(results['RLS-01'].details.map((d) => d.detail).join('\n'), /rep validator\.rep@fabrikam\.com: effective identity with role Texas/);
  } finally {
    await platform.close();
  }
});

test('a check that stops for one tenant leaves its controls to review, not passed on the other tenant alone', async () => {
  const platform = await createEmulatedPlatform();
  try {
    const forTenant = platform.crm.forTenant.bind(platform.crm);
    platform.crm.forTenant = async (tenant) => {
      if (tenant.name === 'Contoso') throw new Error('Connection lost - read ECONNRESET');
      return forTenant(tenant);
    };
    const results = byId(await validatePlatform(platform));
    assert.match(results['OPS-02'].details.map((d) => d.detail).join('\n'), /Contoso: checkEmbedding stopped: Connection lost/);
    for (const id of ['EMB-01', 'EMB-02', 'RLS-01', 'RLS-02', 'RLS-04']) {
      assert.equal(results[id].status, 'warn', id);
      assert.ok(results[id].details.some((d) => d.status === 'pass' && d.detail.startsWith('Fabrikam')), `${id}: Fabrikam was still checked`);
      assert.ok(results[id].details.some((d) => d.status === 'warn' && /^Contoso: not fully checked, because checkEmbedding stopped/.test(d.detail)), id);
    }
    assert.equal(results['ISO-01'].status, 'pass', 'controls the stopped check does not cover are unaffected');
  } finally {
    await platform.close();
  }
});

test('the validator catches a leak: one tenant given a role in another tenant\'s workspace', async () => {
  const platform = await createEmulatedPlatform();
  try {
    const [fabrikam, contoso] = platform.tenants;
    await platform.fabric.as(fabrikam.identity.objectId).addRoleAssignment(fabrikam.fabric.workspaceId, { id: contoso.identity.objectId, type: 'ServicePrincipal' }, 'Viewer');
    const results = byId(await validatePlatform(platform));
    assert.equal(results['IDN-01'].status, 'fail');
    assert.match(results['IDN-01'].details.find((d) => d.status === 'fail').detail, /contososa can see 1 other workspace/);
    assert.equal(results['ISO-02'].status, 'fail');
    assert.match(results['ISO-02'].details.find((d) => d.status === 'fail').detail, /Contoso's identity could open its workspace, list its items/);
    assert.equal(countResults(Object.values(results)).fail >= 2, true);
    assert.match(formatScorecard(Object.values(results), { heading: 'h' }), /IDN-01 FAIL/);
    assert.match(toMarkdown(Object.values(results), { heading: 'h' }), /\| IDN-01 \| .* \| \*\*FAIL\*\* \|/);
  } finally {
    await platform.close();
  }
});

test('the tenant settings check finds service principals that may change the tenant or read every workspace', () => {
  const group = (name) => [{ graphId: `id-${name}`, name }];
  const settings = ({ apis = [], read, write }) => [
    { settingName: 'ServicePrincipalAccessPermissionAPIs', title: 'Fabric APIs', enabled: true, enabledSecurityGroups: apis },
    { settingName: 'ServicePrincipalAccessGlobalAPIs', title: 'Create workspaces', enabled: true, enabledSecurityGroups: apis },
    ...(read ? [{ settingName: 'AllowServicePrincipalsUseReadAdminAPIs', title: 'Read-only admin APIs', ...read }] : []),
    ...(write ? [{ settingName: 'AllowServicePrincipalsUseWriteAdminAPIs', title: 'Admin APIs used for updates', ...write }] : []),
  ];
  const statuses = (notes) => notes.map((n) => n.status);
  const text = (notes) => notes.map((n) => n.detail).join('\n');

  // The pilot tenant: the service principal settings for everyone; both admin API settings for one shared group.
  const pilot = assessTenantSettings(settings({ read: { enabled: true, enabledSecurityGroups: group('Admin API apps') }, write: { enabled: true, enabledSecurityGroups: group('Admin API apps') } }));
  assert.deepEqual(statuses(pilot), ['warn', 'warn', 'pass', 'warn']);
  assert.match(text(pilot), /"Fabric APIs" applies to the entire organization/);
  assert.match(text(pilot), /The platform identity reads these settings through Admin API apps, so it can also call the Fabric admin APIs that make changes/);

  // As designed: one group for the service principals, the platform's own group for read-only admin, no admin updates.
  const designed = assessTenantSettings(settings({ apis: group('HiCRM service principals'), read: { enabled: true, enabledSecurityGroups: group('HiCRM platform') }, write: { enabled: false } }));
  assert.deepEqual(statuses(designed), ['pass', 'pass', 'pass', 'pass']);

  // Admin updates for everyone, or through the tenants' group.
  assert.match(text(assessTenantSettings(settings({ apis: group('sps'), write: { enabled: true } }))), /every service principal, the platform's and the tenants', can call the Fabric admin APIs that make changes/);
  const viaTenants = assessTenantSettings(settings({ apis: group('sps'), read: { enabled: true, enabledSecurityGroups: group('sps') }, write: { enabled: true, enabledSecurityGroups: group('sps') } }));
  assert.match(text(viaTenants), /the tenants' service principals may read every workspace's users, items and metadata/);
  assert.match(text(viaTenants), /the tenants' service principals may call the Fabric admin APIs that make changes/);

  // Read-only admin access for everyone; and a person (cli mode) reading the settings proves nothing about groups.
  assert.match(text(assessTenantSettings(settings({ apis: group('sps'), read: { enabled: true } }))), /every service principal, the tenants' included, can read every workspace's users/);
  const person = assessTenantSettings(settings({ apis: group('sps'), read: { enabled: true, enabledSecurityGroups: group('admins') }, write: { enabled: true, enabledSecurityGroups: group('admins') } }), { platformIsServicePrincipal: false });
  assert.deepEqual(statuses(person), ['pass', 'pass', 'pass']);
  assert.match(text(person), /applies only to admins\. Keep the platform's service principals out of it/);

  assert.deepEqual(statuses(assessTenantSettings([{ settingName: 'ServicePrincipalAccessPermissionAPIs', title: 'Fabric APIs', enabled: false }])), ['fail', 'warn']);
});

test('a refusal is told apart from a capacity that is let in but cannot run the agent', () => {
  assert.equal(refused(Object.assign(new Error('GET /workspaces/x failed (HTTP 403)'), { upstreamStatus: 403 })), true);
  assert.equal(refused(new Error('MCP initialize error -32600: User is not authorized')), true);
  assert.equal(refused(new Error("Login failed for user '<token-identified principal>'.")), true);
  assert.equal(refused(new Error('MCP initialize error -32003: FT1 SKU Not Supported')), false, 'the caller got in');
  assert.equal(refused(new Error('socket hang up')), false);
});

test('the browser check reads exported visual data, finds Edge or Chrome, and keeps Edge in its own process', () => {
  assert.deepEqual(parseExportedRows('State,Pipeline Value\r\nGeorgia,$2828500\r\nTexas,$2229000\r\n"Santa Fe, NM",$455000'), [
    { label: 'Georgia', value: 2828500 },
    { label: 'Texas', value: 2229000 },
    { label: 'Santa Fe, NM', value: 455000 },
  ]);
  assert.deepEqual(parseExportedRows(''), []);
  assert.equal(findBrowser({ env: { BROWSER_PATH: 'C:\\edge.exe' }, exists: (p) => p === 'C:\\edge.exe' }), 'C:\\edge.exe');
  assert.equal(findBrowser({ env: { BROWSER_PATH: 'C:\\missing.exe' }, exists: () => false }), null, 'an explicit path that is missing is not replaced');
  assert.equal(findBrowser({ env: {}, platform: 'linux', exists: (p) => p === '/usr/bin/google-chrome' }), '/usr/bin/google-chrome');
  const args = browserArgs('C:\\profile');
  assert.ok(args.includes('--user-data-dir=C:\\profile') && args.includes('--remote-debugging-port=0'), 'its own profile and a DevTools port');
  assert.ok(args.includes('--edge-skip-compat-layer-relaunch'), 'Edge does not relaunch itself under a compatibility layer');
  assert.ok(args.includes('--disable-features=AutoDeElevate'), 'Edge does not relaunch itself when elevated');
});
