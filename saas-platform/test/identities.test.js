import assert from 'node:assert/strict';
import { X509Certificate } from 'node:crypto';
import { mkdtempSync, readFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { createSelfSignedCertificate } from '../src/auth/certificates.js';
import { credentialFromStore } from '../src/auth/credential-types.js';
import { createIdentityBroker } from '../src/platform/identities.js';
import { createFileSecretStore, createKeyVaultSecretStore, createMemorySecretStore } from '../src/platform/secrets.js';
import { newTenantRecord } from '../src/platform/store.js';
import { json, scriptedFetch, staticTokens } from './helpers.js';

const APP_ID = 'aaaaaaaa-1111-4222-8333-444444444444';
const SP_ID = 'bbbbbbbb-1111-4222-8333-444444444444';
const PLATFORM_APP = 'cccccccc-1111-4222-8333-444444444444';
const TENANT_ID = 'dddddddd-1111-4222-8333-444444444444';
const MANAGED_IDENTITY = 'eeeeeeee-1111-4222-8333-444444444444';

function liveConfig(identity, federated = {}) {
  return {
    authMode: 'sp',
    tenantId: TENANT_ID,
    clientId: PLATFORM_APP,
    productName: 'HiCRM',
    identity: { mode: 'required', autoCreate: false, fabricGroupId: '', credential: 'certificate', ...identity },
    federated: { managedIdentityClientId: '', managedIdentityObjectId: '', tokenFile: '', audience: 'api://AzureADTokenExchange', getAssertion: null, ...federated },
    endpoints: { login: 'https://login.test', graph: 'https://graph.test/v1.0', fabric: 'https://api.fabric.test/v1', powerbi: 'https://api.powerbi.test/v1.0/myorg', onelake: 'https://onelake.test' },
  };
}

const fabrikam = () => newTenantRecord({ name: 'Fabrikam', plan: 'enterprise', domains: ['fabrikam.com'] });
const tokenOk = () => json(200, { access_token: 'sa-token', expires_in: 3600 });

test('the file secret store encrypts at rest and needs its key', async () => {
  const file = path.join(mkdtempSync(path.join(os.tmpdir(), 'hicrm-secrets-')), 'secrets.json');
  const store = createFileSecretStore({ file, key: 'correct horse battery staple' });
  await store.set('tenant-1-service-account', 'p@ss-Value!');
  assert.equal(await store.get('tenant-1-service-account'), 'p@ss-Value!');
  assert.ok(!readFileSync(file, 'utf8').includes('p@ss-Value!'), 'the value is not stored in clear text');
  await assert.rejects(createFileSecretStore({ file, key: 'a different key entirely' }).get('tenant-1-service-account'), /SECRETS_KEY doesn't match/);
  const keyless = createFileSecretStore({ file, key: '' });
  assert.equal(keyless.writable, false);
  assert.equal(await keyless.get('tenant-1-service-account'), null);
  await assert.rejects(keyless.set('x', 'y'), /Set SECRETS_KEY/);
  await assert.rejects(store.set('../escape', 'y'), /Invalid secret name/);
});

test('Key Vault secrets are read and written with the platform identity', async () => {
  const { fetchImpl, calls } = scriptedFetch([
    { match: '/secrets/tenant-1-service-account', method: 'PUT', respond: json(200, { value: 'v1' }) },
    { match: '/secrets/tenant-1-service-account', method: 'GET', respond: json(200, { value: 'v1' }) },
    { match: '/secrets/missing', method: 'GET', respond: json(404, { error: { code: 'SecretNotFound' } }) },
  ]);
  const vault = createKeyVaultSecretStore({ vaultUrl: 'https://hicrm-kv.vault.azure.net', tokens: staticTokens, fetchImpl });
  await vault.set('tenant-1-service-account', 'v1', { expiresOn: '2027-01-01T00:00:00Z' });
  assert.equal(await vault.get('tenant-1-service-account'), 'v1');
  assert.equal(await vault.get('missing'), null);
  assert.equal(calls[0].headers.authorization, 'Bearer token-for-https://vault.azure.net/.default');
  assert.deepEqual(JSON.parse(calls[0].body).attributes, { exp: 1798761600 });
  assert.throws(() => createKeyVaultSecretStore({ vaultUrl: 'https://evil.example.com', tokens: staticTokens }), /KEY_VAULT_URL/);
});

test('the platform creates "fabrikamsa" through Graph with a certificate, keeps the key in the vault, and signs in as it', async () => {
  const { fetchImpl, calls } = scriptedFetch([
    { match: "/applications(uniqueName='hicrm-tenant-", method: 'PATCH', respond: json(201, { id: 'app-object', appId: APP_ID }) },
    { match: `/servicePrincipals(appId='${APP_ID}')`, method: 'PATCH', respond: json(201, { id: SP_ID, appId: APP_ID }) },
    { match: 'graph.test/v1.0/applications/app-object', method: 'PATCH', respond: new Response(null, { status: 204 }) },
    { match: 'graph.test/v1.0/applications/app-object', method: 'DELETE', respond: new Response(null, { status: 204 }) },
    { match: 'login.test', method: 'POST', respond: tokenOk },
  ]);
  const secrets = createMemorySecretStore();
  const broker = createIdentityBroker({ config: liveConfig({ autoCreate: true }), platformTokens: staticTokens, platformFabric: {}, secrets, fetchImpl, propagationWaitMs: 0 });
  const tenant = fabrikam();
  const identity = await broker.ensure(tenant);
  assert.equal(identity.name, 'fabrikamsa');
  assert.equal(identity.appId, APP_ID);
  assert.equal(identity.objectId, SP_ID);
  assert.equal(identity.createdBy, 'platform');
  assert.equal(identity.credentialType, 'certificate');
  assert.ok(Date.parse(identity.credentialExpiresAt) > Date.now() + 360 * 86_400_000, 'a certificate for a year');
  const stored = credentialFromStore(await secrets.get(identity.secretName));
  assert.equal(stored.type, 'certificate');
  assert.equal(stored.thumbprintSha256, identity.certificateThumbprint);
  assert.ok(!JSON.stringify(tenant).includes('PRIVATE KEY'), 'the registry never holds the key');
  // Entra ID gets the public certificate only, and it's the one whose key the vault holds.
  const keyCredentials = JSON.parse(calls.find((c) => c.method === 'PATCH' && c.url.endsWith('/applications/app-object')).body).keyCredentials;
  assert.equal(keyCredentials.length, 1);
  assert.equal(keyCredentials[0].type, 'AsymmetricX509Cert');
  assert.equal(keyCredentials[0].usage, 'Verify');
  const uploaded = new X509Certificate(Buffer.from(keyCredentials[0].key, 'base64'));
  assert.equal(uploaded.fingerprint256.replace(/:/g, '').toLowerCase(), identity.certificateThumbprint);
  assert.ok(!calls.some((c) => c.url.includes('addPassword')), 'no client secret is created');

  const upsert = calls.find((c) => c.method === 'PATCH' && c.url.includes('/applications(uniqueName='));
  assert.ok(upsert.url.endsWith(`/applications(uniqueName='hicrm-tenant-${tenant.id}')`), 'keyed on the customer, so retries are idempotent');
  assert.equal(upsert.headers.prefer, 'create-if-missing');
  const created = JSON.parse(upsert.body);
  assert.equal(created.signInAudience, 'AzureADMyOrg');
  assert.ok(created.tags.includes(`hicrm-tenant-${tenant.id}`));
  assert.ok(!calls.some((c) => c.url.includes('ownedObjects')), 'no directory-wide listing is needed');

  const tokens = await broker.tokensFor(tenant);
  assert.equal(await tokens.getToken('https://api.fabric.microsoft.com/.default'), 'sa-token');
  const signIn = new URLSearchParams(calls.filter((c) => c.url.includes('login.test')).at(-1).body);
  assert.equal(signIn.get('client_id'), APP_ID);
  assert.equal(signIn.get('client_secret'), null);
  assert.equal(signIn.get('client_assertion_type'), 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer');

  const graphCalls = calls.filter((c) => c.url.includes('graph.test')).length;
  assert.equal(await broker.ensure(tenant), identity);
  assert.equal(calls.filter((c) => c.url.includes('graph.test')).length, graphCalls, 'an existing account is reused');

  await broker.remove(tenant);
  assert.ok(calls.some((c) => c.method === 'DELETE' && c.url.endsWith('/applications/app-object')));
  assert.equal(await secrets.get(identity.secretName), null);
});

test('a retry after an interrupted run reuses the app Graph already has (upsert answers 204)', async () => {
  const { fetchImpl, calls } = scriptedFetch([
    { match: "/applications(uniqueName='hicrm-tenant-", method: 'PATCH', respond: new Response(null, { status: 204 }) },
    { match: '/applications?$filter=', method: 'GET', respond: json(200, { value: [{ id: 'app-object', appId: APP_ID }] }) },
    { match: `/servicePrincipals(appId='${APP_ID}')`, method: 'PATCH', respond: new Response(null, { status: 204 }) },
    { match: `/servicePrincipals(appId='${APP_ID}')`, method: 'GET', respond: json(200, { id: SP_ID, appId: APP_ID }) },
    { match: 'graph.test/v1.0/applications/app-object', method: 'PATCH', respond: new Response(null, { status: 204 }) },
    { match: 'login.test', method: 'POST', respond: tokenOk },
  ]);
  const broker = createIdentityBroker({ config: liveConfig({ autoCreate: true }), platformTokens: staticTokens, platformFabric: {}, secrets: createMemorySecretStore(), fetchImpl, propagationWaitMs: 0 });
  const tenant = fabrikam();
  const identity = await broker.ensure(tenant);
  assert.equal(identity.appId, APP_ID);
  assert.equal(identity.objectId, SP_ID);
  const lookup = calls.find((c) => c.url.includes('/applications?$filter='));
  assert.ok(decodeURIComponent(lookup.url).includes(`tags/any(t:t eq 'hicrm-tenant-${tenant.id}')`));
  assert.ok(!calls.some((c) => c.method === 'POST' && /\/(applications|servicePrincipals)$/.test(c.url)), 'nothing is created twice');
});

test('an admin-created service account is checked before it is stored', async () => {
  let accept = false;
  const { fetchImpl } = scriptedFetch([
    { match: 'login.test', method: 'POST', respond: () => (accept ? tokenOk() : json(401, { error: 'invalid_client', error_description: 'AADSTS7000215: Invalid client secret provided.' })) },
  ]);
  const secrets = createMemorySecretStore();
  const broker = createIdentityBroker({ config: liveConfig(), platformTokens: staticTokens, platformFabric: {}, secrets, fetchImpl, propagationWaitMs: 0 });
  const tenant = fabrikam();
  await assert.rejects(broker.register(tenant, { appId: 'nope', objectId: SP_ID, secret: 'x' }), /must be GUIDs/);
  await assert.rejects(broker.register(tenant, { appId: APP_ID, objectId: SP_ID, secret: 'wrong' }), /can't sign in yet.*Invalid client secret/);
  assert.equal(tenant.identity, null);
  accept = true;
  const identity = await broker.register(tenant, { appId: APP_ID, objectId: SP_ID, secret: 'right' });
  assert.equal(identity.createdBy, 'admin');
  assert.deepEqual(credentialFromStore(await secrets.get(identity.secretName)), { type: 'secret', secret: 'right' });
  assert.equal(broker.describe(tenant).status, 'created');
  assert.equal(broker.describe(tenant).credential, 'client secret');
  await assert.rejects(broker.register(tenant, { appId: APP_ID, objectId: SP_ID, secret: 'x', certificate: 'y' }), /exactly one credential/);

  // An admin-made certificate (scripts/bootstrap-identities.ps1 -Credential Certificate) replaces the secret, and
  // keeps what provisioning recorded about the account.
  tenant.identity.workspaceRole = 'Admin';
  const made = createSelfSignedCertificate({ commonName: 'HiCRM fabrikamsa' });
  const withCertificate = await broker.register(tenant, { appId: APP_ID, objectId: SP_ID, certificate: made.bundle });
  assert.equal(withCertificate.credentialType, 'certificate');
  assert.equal(withCertificate.certificateThumbprint, made.thumbprintSha256);
  assert.equal(withCertificate.workspaceRole, 'Admin', 'a new credential keeps the workspace role');
  assert.equal(credentialFromStore(await secrets.get(identity.secretName)).thumbprintSha256, made.thumbprintSha256);
  assert.equal(broker.describe(tenant).credential, 'certificate');
  await assert.rejects(broker.register(tenant, { appId: APP_ID, objectId: SP_ID, certificate: made.bundle.slice(made.bundle.indexOf('-----BEGIN CERTIFICATE-----')) }), /private key and a certificate/);
});

test('required mode never falls back to the platform identity; preferred mode does', async () => {
  const tenant = fabrikam();
  const strict = createIdentityBroker({ config: liveConfig({ mode: 'required' }), platformTokens: staticTokens, platformFabric: {}, secrets: createMemorySecretStore() });
  await assert.rejects(strict.tokensFor(tenant), (error) => error.name === 'IdentityError' && /doesn't have a service account/.test(error.message));
  tenant.identity = { appId: APP_ID, objectId: SP_ID, name: 'fabrikamsa', secretName: 'tenant-x-service-account' };
  await assert.rejects(strict.tokensFor(tenant), /isn't in the credential store/);

  const platformFabric = { kind: 'live' };
  const relaxed = createIdentityBroker({ config: liveConfig({ mode: 'preferred' }), platformTokens: staticTokens, platformFabric, secrets: createMemorySecretStore() });
  assert.equal(await relaxed.tokensFor(fabrikam()), staticTokens);
  assert.equal(await relaxed.fabricFor(fabrikam()), platformFabric);
  assert.equal(relaxed.usesPlatformIdentity(fabrikam()), true);
});

test('with a managed identity, new service accounts trust it and nothing secret is stored anywhere', async () => {
  const { fetchImpl, calls } = scriptedFetch([
    { match: "/applications(uniqueName='hicrm-tenant-", method: 'PATCH', respond: json(201, { id: 'app-object', appId: APP_ID }) },
    { match: `/servicePrincipals(appId='${APP_ID}')`, method: 'PATCH', respond: json(201, { id: SP_ID, appId: APP_ID }) },
    { match: '/applications/app-object/federatedIdentityCredentials', method: 'POST', respond: json(201, { id: 'fic-1' }) },
    { match: 'login.test', method: 'POST', respond: tokenOk },
  ]);
  const secrets = createMemorySecretStore();
  const config = liveConfig({ autoCreate: true, credential: 'federated' }, { managedIdentityObjectId: MANAGED_IDENTITY, getAssertion: async () => 'managed-identity-assertion' });
  const broker = createIdentityBroker({ config, platformTokens: staticTokens, platformFabric: {}, secrets, fetchImpl, propagationWaitMs: 0 });
  const tenant = fabrikam();
  const identity = await broker.ensure(tenant);
  assert.equal(identity.credentialType, 'federated');
  assert.equal(await secrets.get(identity.secretName), null, 'nothing to store');
  const trust = JSON.parse(calls.find((c) => c.url.endsWith('/federatedIdentityCredentials')).body);
  assert.equal(trust.issuer, `https://login.test/${TENANT_ID}/v2.0`);
  assert.equal(trust.subject, MANAGED_IDENTITY);
  assert.deepEqual(trust.audiences, ['api://AzureADTokenExchange']);
  await (await broker.tokensFor(tenant)).getToken('https://analysis.windows.net/powerbi/api/.default');
  const signIn = new URLSearchParams(calls.filter((c) => c.url.includes('login.test')).at(-1).body);
  assert.equal(signIn.get('client_assertion'), 'managed-identity-assertion');
  assert.equal(signIn.get('client_secret'), null);
  assert.equal(broker.describe(tenant).credential, 'federated credential (managed identity)');
  await assert.rejects(broker.rotate(tenant), /nothing|no secret or certificate to rotate/);

  // An account that trusts the managed identity can't sign in on a host that has none.
  const elsewhere = createIdentityBroker({ config: liveConfig({ mode: 'required' }), platformTokens: staticTokens, platformFabric: {}, secrets, fetchImpl });
  await assert.rejects(elsewhere.tokensFor(tenant), /MANAGED_IDENTITY_CLIENT_ID/);
});
