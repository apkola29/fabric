import { execFile } from 'node:child_process';
import { ConfidentialClientApplication, LogLevel } from '@azure/msal-node';
import { credentialLabel } from './credential-types.js';

export const SCOPES = Object.freeze({
  fabric: 'https://api.fabric.microsoft.com/.default',
  powerbi: 'https://analysis.windows.net/powerbi/api/.default',
  storage: 'https://storage.azure.com/.default',
});

// Refresh a little before expiry so long-running calls don't start with a nearly expired token.
const REFRESH_MARGIN_MS = 5 * 60 * 1000;
// A caller can ask for a token that stays valid longer (`minValidityMs`), for example to create an embed token, which
// never outlives the token used to create it. A token fetched within the last minute is used as it is, so a provider
// that issues short tokens can't cause a request on every call.
const RECENT_MS = 60 * 1000;
// Right after an app or a credential is created, some Microsoft Entra ID servers haven't seen it yet: one request
// fails and the next works (seen live minutes after creating a service account). Only these errors are retried:
// AADSTS7000215 invalid client secret, AADSTS700027 certificate not registered on the app (a new certificate),
// AADSTS700016 application not found, AADSTS7000229 no service principal yet.
const NOT_YET_REPLICATED = /AADSTS(7000215|700027|700016|7000229)\b/;
const DEFAULT_RETRY_DELAYS_MS = Object.freeze([2000, 5000, 10000]);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export class AuthError extends Error {
  constructor(message) {
    super(message);
    this.name = 'AuthError';
    this.status = 401;
  }
}

function runAzureCli(args) {
  return new Promise((resolve, reject) => {
    // az is a .cmd file on Windows, which Node only runs through a shell. Arguments are constants or validated config.
    execFile('az', args, { shell: process.platform === 'win32', timeout: 60_000, windowsHide: true, maxBuffer: 1024 * 1024 }, (error, stdout, stderr) => {
      if (error) {
        const hint = String(stderr || error.message).split(/\r?\n/).find((line) => line.trim()) || 'unknown error';
        reject(new AuthError(`Azure CLI token request failed: ${hint.trim()} (run "az login" first)`));
        return;
      }
      resolve(stdout);
    });
  });
}

export function createTokenProvider(config, { fetchImpl = fetch, azureCli = runAzureCli, retryDelaysMs = DEFAULT_RETRY_DELAYS_MS, now = Date.now, credential = null } = {}) {
  const cache = new Map();
  const signIn = credential || credentialFromConfig(config);
  let client = null;

  // Microsoft's library does the protocol (client assertions included); this provider decides when to ask.
  // https://learn.microsoft.com/entra/identity-platform/msal-overview
  function confidentialClient() {
    client ||= new ConfidentialClientApplication({
      auth: { clientId: config.clientId, ...authorityOptions(config.endpoints.login, config.tenantId), ...msalCredential(signIn) },
      system: { networkClient: fetchNetworkClient(fetchImpl), loggerOptions: { logLevel: LogLevel.Error, piiLoggingEnabled: false, loggerCallback: () => {} } },
    });
    return client;
  }

  async function requestToken(scope) {
    let result;
    try {
      // This provider keeps its own cache (getToken below), so MSAL always asks Microsoft Entra ID.
      result = await confidentialClient().acquireTokenByClientCredential({ scopes: [scope], skipCache: true });
    } catch (error) {
      throw new AuthError(`Service principal token request failed: ${reasonOf(error)}`);
    }
    if (!result?.accessToken) throw new AuthError('Service principal token request failed: no access token came back.');
    // MSAL dates the token by this machine's clock; count what's left of it from `now`.
    const left = result.expiresOn instanceof Date ? result.expiresOn.getTime() - Date.now() : 3600 * 1000;
    return { token: result.accessToken, expiresOn: now() + left };
  }

  async function clientCredentials(scope) {
    for (let attempt = 0; ; attempt++) {
      try {
        return await requestToken(scope);
      } catch (error) {
        if (!NOT_YET_REPLICATED.test(error.message) || attempt >= retryDelaysMs.length) throw error;
        await sleep(retryDelaysMs[attempt]);
      }
    }
  }

  async function azureCliToken(scope) {
    const args = ['account', 'get-access-token', '--scope', scope, '--output', 'json'];
    if (config.tenantId) args.push('--tenant', config.tenantId);
    const stdout = await azureCli(args);
    let json;
    try {
      json = JSON.parse(stdout);
    } catch {
      throw new AuthError('The Azure CLI returned an unreadable token response.');
    }
    const expiresOn = json.expires_on ? Number(json.expires_on) * 1000 : Date.parse(json.expiresOn);
    return { token: json.accessToken, expiresOn: Number.isFinite(expiresOn) ? expiresOn : now() + 30 * 60 * 1000 };
  }

  function acquire(scope) {
    if (config.authMode === 'sp') return clientCredentials(scope);
    if (config.authMode === 'cli') return azureCliToken(scope);
    return Promise.reject(new AuthError(`Auth mode "${config.authMode}" doesn't issue tokens.`));
  }

  async function getToken(scope, { minValidityMs = 0 } = {}) {
    const entry = cache.get(scope);
    const left = entry?.value ? entry.value.expiresOn - now() : 0;
    if (left > REFRESH_MARGIN_MS && (left > minValidityMs || now() - entry.value.acquiredAt < RECENT_MS)) return entry.value.token;
    if (entry?.pending) return (await entry.pending).token;
    const pending = acquire(scope).then((value) => ({ ...value, acquiredAt: now() }));
    cache.set(scope, { value: entry?.value, pending });
    try {
      const value = await pending;
      cache.set(scope, { value, pending: null });
      return value.token;
    } catch (error) {
      cache.delete(scope);
      throw error;
    }
  }

  function describe() {
    if (config.authMode === 'sp') return { mode: 'sp', label: 'Service principal', tenantId: config.tenantId, clientId: config.clientId, credential: credentialLabel(signIn) };
    if (config.authMode === 'cli') return { mode: 'cli', label: 'Your Azure CLI sign-in', tenantId: config.tenantId || null };
    return { mode: config.authMode, label: 'Mock' };
  }

  return { getToken, describe };
}

// The platform identity's credential, as config.js built it (config.credential), or a secret given directly.
export function credentialFromConfig(config) {
  if (config.credential) return config.credential;
  if (config.clientSecret) return { type: 'secret', secret: config.clientSecret };
  return null;
}

function msalCredential(credential) {
  if (credential?.type === 'federated') return { clientAssertion: async () => credential.getAssertion() };
  if (credential?.type === 'certificate') return { clientCertificate: { thumbprintSha256: credential.thumbprintSha256, privateKey: credential.privateKey } };
  if (credential?.type === 'secret' && credential.secret) return { clientSecret: credential.secret };
  throw new AuthError('The service principal has no credential: give it a federated credential, a certificate or a client secret.');
}

// The first line of what Microsoft Entra ID said (it adds trace and correlation IDs on later lines). MSAL never puts
// the secret or the assertion in its errors.
function reasonOf(error) {
  return String(error?.errorMessage || error?.message || error).split(/\r?\n/)[0].trim() || 'unknown error';
}

// MSAL knows the public, US Government and China clouds' endpoints. Spelling them out for AZURE_AUTHORITY_HOST keeps
// a token request to one call, with no discovery, in any cloud (and in tests).
function authorityOptions(login, tenant) {
  const host = new URL(login).host;
  const base = `https://${host}/${tenant}`;
  return {
    authority: base,
    cloudDiscoveryMetadata: JSON.stringify({
      tenant_discovery_endpoint: `${base}/v2.0/.well-known/openid-configuration`,
      'api-version': '1.1',
      metadata: [{ preferred_network: host, preferred_cache: host, aliases: [host] }],
    }),
    authorityMetadata: JSON.stringify({
      token_endpoint: `${base}/oauth2/v2.0/token`,
      authorization_endpoint: `${base}/oauth2/v2.0/authorize`,
      end_session_endpoint: `${base}/oauth2/v2.0/logout`,
      issuer: `${base}/v2.0`,
      jwks_uri: `${base}/discovery/v2.0/keys`,
    }),
  };
}

// MSAL's requests go through fetch, like every other call the platform makes (and tests can answer them).
export function fetchNetworkClient(fetchImpl) {
  async function send(method, url, options = {}) {
    let res;
    try {
      res = await fetchImpl(url, { method, headers: options.headers, body: options.body });
    } catch (error) {
      throw new AuthError(`Could not reach Microsoft Entra ID: ${error.message}`);
    }
    const headers = {};
    res.headers?.forEach?.((value, key) => {
      headers[key] = value;
    });
    const text = typeof res.text === 'function' ? await res.text() : JSON.stringify(await res.json());
    let body = {};
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = { error: 'invalid_response', error_description: `HTTP ${res.status}` };
      }
    }
    return { headers, body, status: res.status };
  }
  return {
    sendGetRequestAsync: (url, options) => send('GET', url, options),
    sendPostRequestAsync: (url, options) => send('POST', url, options),
  };
}
