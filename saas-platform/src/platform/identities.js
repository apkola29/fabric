import { createHash } from 'node:crypto';
import { createSelfSignedCertificate } from '../auth/certificates.js';
import { certificateCredential, credentialFromStore, credentialLabel, storedCredential } from '../auth/credential-types.js';
import { createTokenProvider } from '../auth/tokens.js';
import { createFabricClient } from '../fabric/client.js';
import { LEGACY_PRODUCT_NAMES, legacyTenantTags } from './legacy-names.js';

// One service account per customer. The platform identity is the control plane: it creates the customer's workspace
// and makes the customer's service account Admin of that workspace, and nothing else. Every customer-facing call
// (CRM database, embed tokens, the assistant) runs as that customer's service account, so a bug that mixes up
// customers can't reach another customer's data: the token itself has no access there.
//
// The service account is a service principal (app registration) named "<customer>sa", for example "fabrikamsa".
// The platform creates it through Microsoft Graph when it holds Application.ReadWrite.OwnedBy (it can then only manage
// the apps it created), or an Entra admin creates it with scripts/bootstrap-identities.ps1 and registers it.
//
// Modes (TENANT_IDENTITY_MODE): required = never fall back to the platform identity (production);
// preferred = fall back with a visible warning (development); off = always use the platform identity.
//
// Credentials (src/auth/credential-types.js), best first: federated (the account trusts the platform's managed identity,
// so nothing is stored), certificate (kept in the credential store, encrypted or in Key Vault), client secret
// (development, and accounts registered before certificates).

const GRAPH_SCOPE = 'https://graph.microsoft.com/.default';
const SECRET_LIFETIME_DAYS = 180;
const CERTIFICATE_LIFETIME_DAYS = 365;
const FEDERATED_CREDENTIAL_NAME = 'platform-managed-identity';
const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export class IdentityError extends Error {
  constructor(message) {
    super(message);
    this.name = 'IdentityError';
    this.status = 503;
  }
}

export const serviceAccountName = (tenant) => `${String(tenant.slug || tenant.name).toLowerCase().replace(/[^a-z0-9]/g, '')}sa`;
export const secretNameFor = (tenant) => `tenant-${tenant.id}-service-account`;
// How Microsoft Entra ID shows a customer's app registration and service principal.
export const entraDisplayName = (config, tenant) => `${config.productName} service principal - ${tenant.name} (${serviceAccountName(tenant)})`;
// Graph tags on the apps the platform creates: one keys the customer (it's also the app's uniqueName), one marks them all.
const tenantTag = (tenant) => `platform-tenant-${tenant.id}`;
const SERVICE_ACCOUNT_TAG = 'platform-service-account';
const sameTags = (a = [], b = []) => a.length === b.length && b.every((tag) => a.includes(tag));

function fakeGuid(seed) {
  const h = createHash('sha256').update(seed).digest('hex');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-4${h.slice(13, 16)}-a${h.slice(17, 20)}-${h.slice(20, 32)}`;
}

export function createIdentityBroker({ config, platformTokens, platformFabric, secrets, fetchImpl = fetch, clientOptions = {}, propagationWaitMs = 10_000, tokenRetryDelaysMs }) {
  const mock = config.authMode === 'mock';
  const settings = config.identity;
  const graphBase = config.endpoints.graph.replace(/\/$/, '');
  const clients = new Map();
  // Customers whose last call fell back to the platform identity (preferred mode, secret missing).
  const fallbacks = new Set();

  async function graph(method, path, body, extraHeaders = {}) {
    const res = await fetchImpl(`${graphBase}${path}`, {
      method,
      headers: { authorization: `Bearer ${await platformTokens.getToken(GRAPH_SCOPE)}`, ...(body ? { 'content-type': 'application/json' } : {}), ...extraHeaders },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 204) return null;
    const json = await res.json().catch(() => null);
    if (!res.ok) {
      const error = new Error(`Microsoft Graph ${method} ${path.split('?')[0]} failed (HTTP ${res.status}): ${json?.error?.message || res.statusText}`);
      error.upstreamStatus = res.status;
      throw error;
    }
    return json;
  }

  // The app registration that carries one of these tags, trying them in order. Listing apps works with
  // Application.ReadWrite.OwnedBy (https://learn.microsoft.com/graph/api/application-list).
  async function findApp(tags) {
    for (const tag of tags) {
      const filter = encodeURIComponent(`tags/any(t:t eq '${tag}')`);
      const found = (await graph('GET', `/applications?$filter=${filter}&$select=id,appId,displayName,tags`))?.value?.[0];
      if (found) return found;
    }
    return null;
  }

  // `retryDelaysMs`: how long to wait between token requests that fail because Entra ID hasn't replicated a new
  // credential yet (see auth/tokens.js).
  function identityTokens(identity, credential, retryDelaysMs = tokenRetryDelaysMs) {
    return createTokenProvider(
      { authMode: 'sp', tenantId: config.tenantId, clientId: identity.appId, endpoints: config.endpoints },
      { fetchImpl, credential, ...(retryDelaysMs ? { retryDelaysMs } : {}) },
    );
  }

  // The platform's managed identity (or workload identity token), which federated service accounts trust.
  function federatedCredential() {
    const { getAssertion, tokenFile } = config.federated;
    if (!getAssertion) throw new IdentityError('This service account trusts the platform\'s managed identity: set MANAGED_IDENTITY_CLIENT_ID (or AZURE_FEDERATED_TOKEN_FILE).');
    return { type: 'federated', source: tokenFile ? 'token file' : 'managed identity', getAssertion };
  }

  // The credential a service account signs in with, or null when it has none here.
  async function credentialOf(identity) {
    if (identity.credentialType === 'federated') return federatedCredential();
    return credentialFromStore(await secrets.get(identity.secretName));
  }

  // New credentials take a little while to work everywhere in Entra ID. This loop does its own waiting, so its token
  // requests don't retry on their own.
  async function waitUntilUsable(identity, credential) {
    const tokens = identityTokens(identity, credential, []);
    for (let attempt = 1; ; attempt++) {
      try {
        await tokens.getToken('https://api.fabric.microsoft.com/.default');
        return;
      } catch (error) {
        if (attempt >= 12) throw new IdentityError(`The service account ${identity.name} can't sign in yet: ${error.message}`);
        await sleep(propagationWaitMs);
      }
    }
  }

  // Gives an app registration the platform's default credential type, replacing whatever certificate it had.
  // federated: trust the managed identity (https://learn.microsoft.com/graph/api/application-post-federatedidentitycredentials)
  // certificate: a new self-signed certificate; Entra ID keeps only its public part (keyCredentials).
  async function issueCredential(app, name) {
    if (settings.credential === 'federated') {
      const body = {
        name: FEDERATED_CREDENTIAL_NAME,
        issuer: `${config.endpoints.login.replace(/\/$/, '')}/${config.tenantId}/v2.0`,
        subject: config.federated.managedIdentityObjectId,
        audiences: [config.federated.audience],
        description: `${config.productName} runtime (managed identity)`,
      };
      await graph('POST', `/applications/${app.id}/federatedIdentityCredentials`, body).catch((error) => {
        if (error.upstreamStatus !== 409 && !/already exist/i.test(error.message)) throw error;
      });
      return { credential: federatedCredential(), record: { credentialType: 'federated', credentialExpiresAt: null } };
    }
    const made = createSelfSignedCertificate({ commonName: `${config.productName} ${name}`, days: CERTIFICATE_LIFETIME_DAYS });
    await graph('PATCH', `/applications/${app.id}`, {
      keyCredentials: [{ type: 'AsymmetricX509Cert', usage: 'Verify', key: made.certificateDer.toString('base64'), displayName: `${config.productName} credential` }],
    });
    const credential = certificateCredential(made.bundle);
    return {
      credential,
      stored: storedCredential(credential),
      record: { credentialType: 'certificate', credentialExpiresAt: credential.notAfter, certificateThumbprint: credential.thumbprintSha256 },
    };
  }

  async function createWithGraph(tenant) {
    const name = serviceAccountName(tenant);
    const tag = tenantTag(tenant);
    const tags = [tag, SERVICE_ACCOUNT_TAG];
    const displayName = entraDisplayName(config, tenant);
    const notes = `Service account for ${tenant.name}: Admin of one Fabric workspace only. Managed by ${config.productName}; don't change it by hand.`;
    // Upserts keyed on the customer: the same request creates the app, or updates the one an interrupted run already
    // created, so a retry never leaves a second app behind. Both need only Application.ReadWrite.OwnedBy.
    // https://learn.microsoft.com/graph/api/application-upsert
    // https://learn.microsoft.com/graph/api/serviceprincipal-upsert
    const createIfMissing = { prefer: 'create-if-missing' };
    // An app an earlier version created is keyed on its earlier tag, and a uniqueName can't change: it's found by its tag
    // (this version's or an earlier one's) and renamed in place instead of upserted under a new key.
    let app = await findApp([tag, ...legacyTenantTags(tenant.id)]);
    if (app) {
      if (app.displayName !== displayName || !sameTags(app.tags, tags)) await graph('PATCH', `/applications/${app.id}`, { displayName, tags, notes });
    } else {
      app = await graph('PATCH', `/applications(uniqueName='${tag}')`, { displayName, signInAudience: 'AzureADMyOrg', tags, notes }, createIfMissing);
      // 204: it already existed, and Graph doesn't return it. uniqueName can't be filtered on; the tag can.
      app ||= await findApp([tag]);
    }
    if (!app?.appId) throw new IdentityError(`The app for ${name} was created but can't be read back yet. Run provisioning again in a minute.`);
    let sp = await graph('PATCH', `/servicePrincipals(appId='${app.appId}')`, { displayName, tags }, createIfMissing);
    sp ||= await graph('GET', `/servicePrincipals(appId='${app.appId}')?$select=id,appId`);
    const issued = await issueCredential(app, name);
    const identity = {
      kind: 'servicePrincipal',
      name,
      displayName,
      appId: app.appId,
      objectId: sp.id,
      applicationObjectId: app.id,
      secretName: secretNameFor(tenant),
      ...issued.record,
      createdBy: 'platform',
      createdAt: new Date().toISOString(),
    };
    if (issued.stored) await secrets.set(identity.secretName, issued.stored, { expiresOn: identity.credentialExpiresAt });
    if (settings.fabricGroupId) {
      // Tenants that limit "Service principals can use Fabric APIs" to a group need the new account in that group.
      await graph('POST', `/groups/${settings.fabricGroupId}/members/$ref`, { '@odata.id': `${graphBase}/directoryObjects/${sp.id}` }).catch((error) => {
        if (!/already exist/i.test(error.message)) throw error;
      });
    }
    await waitUntilUsable(identity, issued.credential);
    return identity;
  }

  function simulate(tenant) {
    const name = serviceAccountName(tenant);
    return {
      kind: 'servicePrincipal',
      name,
      displayName: entraDisplayName(config, tenant),
      appId: fakeGuid(`app:${tenant.id}`),
      objectId: fakeGuid(`sp:${tenant.id}`),
      secretName: secretNameFor(tenant),
      credentialType: settings.credential,
      createdBy: 'platform',
      createdAt: new Date().toISOString(),
      simulated: true,
    };
  }

  async function tokensFor(tenant) {
    if (mock || settings.mode === 'off') return platformTokens;
    const identity = tenant.identity;
    if (identity?.appId && !identity.disabled) {
      const key = `${identity.appId}:${identity.credentialType || 'secret'}:${identity.certificateThumbprint || identity.secretKeyId || identity.registeredAt || ''}`;
      const cached = clients.get(tenant.id);
      if (cached?.key === key) return cached.tokens;
      const credential = await credentialOf(identity);
      if (credential) {
        const tokens = identityTokens(identity, credential);
        clients.set(tenant.id, { key, tokens, fabric: null });
        fallbacks.delete(tenant.id);
        return tokens;
      }
      if (settings.mode === 'required') throw new IdentityError(`The credential for ${identity.name} isn't in the credential store.`);
    } else if (settings.mode === 'required') {
      throw new IdentityError(`${tenant.name} doesn't have a service account yet.`);
    }
    fallbacks.add(tenant.id);
    return platformTokens;
  }

  // Whether a service account can sign in here: it trusts the managed identity, or its credential is stored.
  async function hasCredential(identity) {
    if (identity.credentialType === 'federated') return Boolean(config.federated.getAssertion);
    return Boolean(await secrets.get(identity.secretName));
  }

  return {
    mode: settings.mode,
    canCreate: () => mock || (settings.mode !== 'off' && settings.autoCreate),

    // Returns the customer's service account, creating it when the platform is allowed to. Null means "not yet".
    async ensure(tenant) {
      if (settings.mode === 'off') return null;
      if (tenant.identity?.appId) {
        if (mock || (await hasCredential(tenant.identity))) return tenant.identity;
        if (tenant.identity.createdBy !== 'platform' || !settings.autoCreate) return null;
      }
      if (mock) tenant.identity = simulate(tenant);
      else if (settings.autoCreate) tenant.identity = await createWithGraph(tenant);
      else return null;
      clients.delete(tenant.id);
      return tenant.identity;
    },

    // Gives an account an earlier version named its current display name and tags, in place, and returns what changed.
    // The platform renames the accounts it created; an Entra admin renames the others with
    // scripts/bootstrap-identities.ps1, which registers the new name.
    async rename(tenant) {
      const identity = tenant.identity;
      const displayName = entraDisplayName(config, tenant);
      if (!identity?.appId || identity.createdBy !== 'platform' || identity.displayName === displayName) return null;
      if (!mock) {
        if (!settings.autoCreate || !identity.applicationObjectId) return null;
        const tags = [tenantTag(tenant), SERVICE_ACCOUNT_TAG];
        await graph('PATCH', `/applications/${identity.applicationObjectId}`, { displayName, tags });
        await graph('PATCH', `/servicePrincipals(appId='${identity.appId}')`, { displayName, tags });
      }
      const from = identity.displayName;
      identity.displayName = displayName;
      return { from, to: displayName };
    },

    // For accounts an Entra admin created with scripts/bootstrap-identities.ps1. Exactly one credential: `certificate`
    // (a PEM bundle with the private key), `federated: true` (the app trusts the platform's managed identity) or
    // `secret` (development).
    async register(tenant, { appId, objectId, secret, certificate, federated, displayName }) {
      if (!GUID.test(appId || '') || !GUID.test(objectId || '')) throw new Error('appId and objectId must be GUIDs (application ID and service principal object ID).');
      if ([secret, certificate, federated].filter(Boolean).length !== 1) throw new Error('Give exactly one credential: a certificate, a federated credential or a client secret.');
      const credential = federated ? (mock ? { type: 'federated' } : federatedCredential()) : certificate ? certificateCredential(certificate) : { type: 'secret', secret };
      // Registering the same app again changes its credential only: what provisioning recorded (its workspace role)
      // stays, and the old credential's details go.
      const previous = tenant.identity?.appId === appId ? tenant.identity : null;
      const { secretKeyId, secretExpiresAt, credentialType, credentialExpiresAt, certificateThumbprint, disabled, ...kept } = previous || {};
      // Names registration recorded before the rename ("<product> service account - <customer>") give way to the
      // current one; a name of the admin's own stays.
      const earlier = [...LEGACY_PRODUCT_NAMES, config.productName].some((product) => String(previous?.displayName).startsWith(`${product} service account - `));
      const identity = {
        ...kept,
        kind: 'servicePrincipal',
        name: serviceAccountName(tenant),
        displayName: displayName || (earlier ? null : previous?.displayName) || entraDisplayName(config, tenant),
        appId,
        objectId,
        secretName: secretNameFor(tenant),
        credentialType: credential.type,
        credentialExpiresAt: credential.notAfter || null,
        ...(credential.thumbprintSha256 ? { certificateThumbprint: credential.thumbprintSha256 } : {}),
        createdBy: previous?.createdBy || 'admin',
        registeredAt: new Date().toISOString(),
      };
      if (!mock) await waitUntilUsable(identity, credential);
      if (credential.type === 'federated') await secrets.delete(identity.secretName).catch(() => {});
      else await secrets.set(identity.secretName, storedCredential(credential), { expiresOn: identity.credentialExpiresAt || undefined });
      tenant.identity = identity;
      clients.delete(tenant.id);
      return identity;
    },

    async rotate(tenant) {
      const identity = tenant.identity;
      if (mock || identity?.createdBy !== 'platform' || !settings.autoCreate) throw new Error('Only service accounts the platform created can be rotated by the platform.');
      if (identity.credentialType === 'federated') throw new Error(`${identity.name} trusts the platform's managed identity: there's no secret or certificate to rotate.`);
      if (identity.credentialType === 'certificate') {
        // A new certificate replaces the old one in Entra ID at once; tokens already issued keep working until they expire.
        const issued = await issueCredential({ id: identity.applicationObjectId }, identity.name);
        await waitUntilUsable(identity, issued.credential);
        await secrets.set(identity.secretName, issued.stored, { expiresOn: issued.record.credentialExpiresAt });
        Object.assign(identity, issued.record, { rotatedAt: new Date().toISOString() });
        clients.delete(tenant.id);
        return identity;
      }
      const endDateTime = new Date(Date.now() + SECRET_LIFETIME_DAYS * 86_400_000).toISOString();
      const password = await graph('POST', `/applications/${identity.applicationObjectId}/addPassword`, { passwordCredential: { displayName: `${config.productName} credential`, endDateTime } });
      const credential = { type: 'secret', secret: password.secretText };
      await waitUntilUsable(identity, credential);
      await secrets.set(identity.secretName, storedCredential(credential), { expiresOn: password.endDateTime || endDateTime });
      if (identity.secretKeyId) await graph('POST', `/applications/${identity.applicationObjectId}/removePassword`, { keyId: identity.secretKeyId });
      Object.assign(identity, { credentialType: 'secret', secretKeyId: password.keyId, secretExpiresAt: password.endDateTime || endDateTime, credentialExpiresAt: password.endDateTime || endDateTime, rotatedAt: new Date().toISOString() });
      clients.delete(tenant.id);
      return identity;
    },

    async remove(tenant) {
      const identity = tenant.identity;
      if (!identity) return { removed: false };
      clients.delete(tenant.id);
      if (!mock) await secrets.delete(identity.secretName).catch(() => {});
      if (!mock && identity.createdBy === 'platform' && settings.autoCreate && identity.applicationObjectId) {
        await graph('DELETE', `/applications/${identity.applicationObjectId}`);
        return { removed: true };
      }
      return { removed: mock, note: mock ? undefined : `Delete app ${identity.appId} in Microsoft Entra ID; an admin created it.` };
    },

    tokensFor,

    async fabricFor(tenant) {
      // Demo mode: the emulator gives each service account its own view, held to its workspace roles.
      if (mock) {
        const id = tenant.identity;
        if (settings.mode !== 'off' && id?.objectId && !id.disabled && typeof platformFabric.as === 'function') return platformFabric.as(id.objectId);
        return platformFabric;
      }
      const tokens = await tokensFor(tenant);
      if (tokens === platformTokens) return platformFabric;
      const cached = clients.get(tenant.id);
      if (!cached.fabric) cached.fabric = createFabricClient({ tokens, endpoints: config.endpoints, ...clientOptions });
      return cached.fabric;
    },

    // True when this customer's work would run as the shared platform identity.
    usesPlatformIdentity(tenant) {
      return settings.mode === 'off' || !tenant.identity?.appId || Boolean(tenant.identity?.disabled) || fallbacks.has(tenant.id);
    },

    describe(tenant) {
      const identity = tenant.identity;
      return {
        mode: settings.mode,
        name: identity?.name || serviceAccountName(tenant),
        displayName: identity?.displayName || null,
        appId: identity?.appId || null,
        objectId: identity?.objectId || null,
        createdBy: identity?.createdBy || null,
        credentialType: identity?.appId ? identity.credentialType || 'secret' : null,
        credential: identity?.appId ? credentialLabel({ type: identity.credentialType || 'secret', source: config.federated.tokenFile ? 'token file' : 'managed identity' }) : null,
        credentialExpiresAt: identity?.credentialExpiresAt || identity?.secretExpiresAt || null,
        secretExpiresAt: identity?.secretExpiresAt || null,
        workspaceRole: identity?.workspaceRole || null,
        simulated: Boolean(identity?.simulated),
        status: settings.mode === 'off' ? 'off' : identity?.appId ? (identity.workspaceRole ? 'active' : 'created') : 'missing',
      };
    },

    forget(tenantId) {
      clients.delete(tenantId);
      fallbacks.delete(tenantId);
    },
  };
}
