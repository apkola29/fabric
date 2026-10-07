import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { TERRITORIES } from '../src/crm/schema.js';
import { PILOT_CUSTOMERS, carryOverPasswords, loginsMarkdown, parseCustomer, removePilot, setUpPilot } from '../src/platform/pilot.js';
import { findUser, resetPassword, verifyPassword } from '../src/platform/users.js';
import { provisioningKit } from './support.js';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

test('the pilot creates two customers, each with its own data and four people, and is safe to run again', async () => {
  const kit = provisioningKit();
  const results = await setUpPilot({ store: kit.store, provisioner: kit.provisioner, crm: kit.crm });
  assert.deepEqual(results.map((r) => r.tenant.name), PILOT_CUSTOMERS.map((c) => c.name));
  for (const { tenant, people, note, error } of results) {
    assert.equal(error, undefined);
    assert.equal(note, null, 'fresh sample data has every account in a territory');
    assert.equal(tenant.status, 'ready');
    assert.equal(tenant.pilot, true);
    assert.deepEqual(people.map((p) => [p.role, p.territories.join()]), [['manager', ''], ...TERRITORIES.map((t) => ['rep', t])]);
    for (const person of people) {
      assert.ok(person.email.endsWith(`@${tenant.domains[0]}`));
      const user = tenant.users.find((u) => u.email === person.email);
      assert.ok(await verifyPassword(person.password, user.passwordHash), 'the password shown is the one that works');
    }
    const repo = await kit.crm.forTenant(tenant);
    const rep = people.find((p) => p.role === 'rep');
    const owned = (await repo.scoped(rep.territories).listAccounts({ limit: 200 })).rows.filter((a) => a.ownerName === rep.name);
    assert.ok(owned.length, `${rep.name} owns accounts in ${rep.territories[0]}`);
  }
  const [fabrikam, contoso] = results;
  assert.notEqual(fabrikam.tenant.fabric.workspaceId, contoso.tenant.fabric.workspaceId);
  assert.notDeepEqual(fabrikam.people.map((p) => p.name), contoso.people.map((p) => p.name));
  assert.deepEqual([fabrikam.tenant.subdomain, contoso.tenant.subdomain], ['fabrikam', 'contoso'], 'each customer has its own address');
  for (const { tenant } of results) assert.ok(tenant.branding?.logo?.data && tenant.branding.color, `${tenant.name} has a logo and an accent color`);
  assert.notEqual(fabrikam.tenant.branding.logo.sha256, contoso.tenant.branding.logo.sha256, 'and the logos differ');
  assert.notEqual(fabrikam.tenant.branding.color, contoso.tenant.branding.color);

  // An operator's own branding survives running the setup again.
  kit.store.get(contoso.tenant.id).branding.color = '#204060';
  const again = await setUpPilot({ store: kit.store, provisioner: kit.provisioner, crm: kit.crm });
  assert.ok(again.every((r) => r.people.every((p) => p.password === null)), 'people already there keep their passwords');
  assert.equal(kit.store.get(fabrikam.tenant.id).users.length, 4);
  assert.equal(kit.store.get(contoso.tenant.id).branding.color, '#204060');
  assert.equal(kit.store.list().length, 2);

  const markdown = loginsMarkdown(results, { urlOf: (t) => `http://${t.subdomain}.localhost:3000/`, adminUrl: 'http://localhost:3000/admin' });
  for (const person of [...fabrikam.people, ...contoso.people]) assert.ok(markdown.includes(person.password) && markdown.includes(person.email));
  assert.match(markdown, /\| Sales manager \| every territory \|/);
  assert.match(markdown, /## Fabrikam[^#]*Sign in at http:\/\/fabrikam\.localhost:3000\//);
  assert.match(markdown, /## Contoso[^#]*Sign in at http:\/\/contoso\.localhost:3000\//);

  assert.deepEqual(await removePilot({ store: kit.store, provisioner: kit.provisioner }), ['Fabrikam', 'Contoso']);
  assert.equal(kit.store.list().length, 0);
});

test('the sign-ins file keeps earlier passwords that still work, also when provisioning stops part way', async () => {
  const kit = provisioningKit();
  const urls = { urlOf: (t) => `http://${t.subdomain}.localhost:3000/`, adminUrl: 'http://localhost:3000/admin' };
  const [fabrikam] = await setUpPilot({ store: kit.store, provisioner: kit.provisioner, crm: kit.crm, customers: [PILOT_CUSTOMERS[0]] });
  const earlier = loginsMarkdown([fabrikam], urls);
  const tenant = kit.store.get(fabrikam.tenant.id);
  const reset = fabrikam.people[1];
  await resetPassword({ tenant, userId: findUser(tenant, reset.email).id });
  await kit.store.save(tenant);

  const stopped = {
    provision: async (id) => {
      const t = kit.store.get(id);
      Object.assign(t, { status: 'failed', error: 'Fabric said no' });
      await kit.store.save(t);
      return t;
    },
  };
  const [again] = await setUpPilot({ store: kit.store, provisioner: stopped, crm: kit.crm, customers: [PILOT_CUSTOMERS[0]] });
  assert.equal(again.error, 'Fabric said no');
  assert.deepEqual(again.people.map((p) => p.email), fabrikam.people.map((p) => p.email), 'people who already sign in stay listed');
  assert.ok(again.people.every((p) => p.password === null));

  await carryOverPasswords([again], earlier);
  for (const [i, person] of again.people.entries()) {
    assert.equal(person.password, person.email === reset.email ? null : fabrikam.people[i].password, 'a password reset since then is not carried over');
  }
  const markdown = loginsMarkdown([again], urls);
  assert.match(markdown, /Provisioning stopped: Fabric said no/);
  assert.equal((markdown.match(/`[A-Za-z0-9_-]{20}`/g) || []).length, 3);
  assert.ok(markdown.includes(`| ${reset.email} | (already set`));
});

test('customers from earlier versions: the pilot says when sample data has no territories, and replaces it only when asked', async () => {
  const kit = provisioningKit();
  const [first] = await setUpPilot({ store: kit.store, provisioner: kit.provisioner, crm: kit.crm, customers: [{ name: 'Fabrikam', domain: 'fabrikam.com' }] });
  const repo = await kit.crm.forTenant(first.tenant);
  // Simulate version 2 sample data: accounts without a state.
  await repo.scoped(null).updateAccount((await repo.scoped(['Texas']).listAccounts({ limit: 1 })).rows[0].id, { state: '' });
  const [noted] = await setUpPilot({ store: kit.store, provisioner: kit.provisioner, crm: kit.crm, customers: [{ name: 'Fabrikam', domain: 'fabrikam.com' }] });
  assert.match(noted.note, /1 of 120 accounts have no territory.*reseed Fabrikam --confirm/);
  const [reseeded] = await setUpPilot({ store: kit.store, provisioner: kit.provisioner, crm: kit.crm, customers: [{ name: 'Fabrikam', domain: 'fabrikam.com' }], reseed: true });
  assert.equal(reseeded.note, null);
  assert.equal((await repo.scoped([...TERRITORIES]).listAccounts()).total, 120);

  assert.deepEqual(parseCustomer('Northwind: northwind.example'), { name: 'Northwind', domain: 'northwind.example' });
  assert.throws(() => parseCustomer('Northwind'), /Name:domain/);
  await assert.rejects(setUpPilot({ store: kit.store, provisioner: kit.provisioner, crm: kit.crm, customers: [{ name: 'Fabrikam', domain: 'other.com' }] }), /already exists with the sign-in domain fabrikam\.com/);
  await assert.rejects(setUpPilot({ store: kit.store, provisioner: kit.provisioner, crm: kit.crm, customers: [{ name: 'Other', domain: 'fabrikam.com' }] }), /already signs in as Fabrikam/);
});

test('npm run setup in demo mode: writes .env and the sign-ins, runs again safely, and removes what it created', async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'hicrm-setup-'));
  const envFile = path.join(dir, '.env');
  const env = { ...process.env, DATA_DIR: path.join(dir, 'data') };
  for (const key of ['FABRIC_AUTH_MODE', 'AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET', 'FABRIC_CAPACITY_ID', 'ADMIN_KEY', 'SESSION_SECRET', 'FABRIC_TEMPLATE_WORKSPACE_ID', 'APP_DOMAIN', 'SECRETS_KEY']) delete env[key];
  const run = (...args) =>
    new Promise((resolve) => {
      execFile(process.execPath, [`--env-file-if-exists=${envFile}`, path.join(ROOT, 'scripts', 'setup.js'), '--settings-file', envFile, ...args], { cwd: ROOT, env, timeout: 120_000 }, (error, stdout, stderr) =>
        resolve({ code: error ? error.code : 0, stdout, stderr }),
      );
    });
  try {
    const refused = await run('--mode', 'demo');
    assert.notEqual(refused.code, 0, 'without a terminal, nothing happens unless --yes says so');
    assert.match(refused.stderr, /add --yes/);

    const first = await run('--mode', 'demo', '--yes');
    assert.equal(first.code, 0, first.stderr || first.stdout);
    const written = await readFile(envFile, 'utf8');
    assert.match(written, /^FABRIC_AUTH_MODE=mock$/m);
    // No credentials in the settings file: they're asked for when the app starts.
    for (const name of ['ADMIN_KEY', 'SESSION_SECRET', 'SECRETS_KEY', 'AZURE_CLIENT_SECRET']) assert.doesNotMatch(written, new RegExp(`^${name}=`, 'm'), `${name} isn't written`);
    assert.match(written, /No credentials are kept here/);
    assert.match(written, /^APP_DOMAIN=localhost$/m, 'each customer gets its own address');
    const logins = await readFile(path.join(dir, 'data', 'pilot-logins.md'), 'utf8');
    assert.equal((logins.match(/`[A-Za-z0-9_-]{20}`/g) || []).length, 8, 'eight people, eight passwords');
    assert.match(logins, /Sign in at http:\/\/fabrikam\.localhost:3000\//);
    assert.match(logins, /Sign in at http:\/\/contoso\.localhost:3000\//);
    assert.match(first.stdout, /Fabrikam: ready, with 4 people/);
    assert.match(first.stdout, /Contoso: ready, with 4 people/);
    assert.match(first.stdout, /Contoso at http:\/\/contoso\.localhost:3000\//);

    const second = await run('--yes');
    assert.equal(second.code, 0, second.stderr || second.stdout);
    assert.match(second.stdout, /already here/);
    assert.match(second.stdout, /\(unchanged\)/);
    assert.equal(await readFile(envFile, 'utf8'), written, 'existing settings are kept');
    assert.deepEqual(
      (await readFile(path.join(dir, 'data', 'pilot-logins.md'), 'utf8')).match(/`[A-Za-z0-9_-]{20}`/g),
      logins.match(/`[A-Za-z0-9_-]{20}`/g),
      'running again keeps the passwords in the sign-ins file',
    );

    const one = await run('--customer', 'Contoso:contoso.com', '--yes');
    assert.equal(one.code, 0, one.stderr || one.stdout);
    const afterOne = await readFile(path.join(dir, 'data', 'pilot-logins.md'), 'utf8');
    assert.deepEqual(afterOne.match(/`[A-Za-z0-9_-]{20}`/g), logins.match(/`[A-Za-z0-9_-]{20}`/g), 'a run for one customer keeps the others in the file');
    assert.match(afterOne, /## Fabrikam[\s\S]*## Contoso/);

    const removed = await run('--remove', '--yes');
    assert.equal(removed.code, 0, removed.stderr || removed.stdout);
    assert.match(removed.stdout, /Removed Fabrikam, Contoso/);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
