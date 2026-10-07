import { readFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { CREDENTIAL_TYPES, TOKEN_EXCHANGE_AUDIENCE, certificateCredential, managedIdentityAssertion, tokenFileAssertion } from './auth/credential-types.js';

const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TENANT = /^[0-9a-z.-]{3,253}$/i;
const AUTH_MODES = ['mock', 'cli', 'sp'];
const APP_ENVS = ['development', 'production'];
const IDENTITY_MODES = ['required', 'preferred', 'off'];
const PLATFORM_ACCESS = ['keep', 'release'];
const SECRET_PROVIDERS = ['file', 'keyvault', 'memory'];
const PRINCIPAL_TYPES = ['Group', 'User', 'ServicePrincipal'];
const LOOPBACK = new Set(['127.0.0.1', 'localhost', '::1']);
const HOSTNAME = /^(?=.{1,200}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$/;

// Requests per window ([count, milliseconds]). Shared capacity means one busy customer can slow everyone down, so
// the expensive calls are limited per customer and per user. Override with RATE_LIMITS='{"askPerTenant":[30,60000]}'.
export const DEFAULT_LIMITS = Object.freeze({
  signInPerIp: [20, 60_000],
  signInPerDomain: [60, 60_000],
  // Password guesses against one person's sign-in.
  signInPerAccount: [10, 15 * 60_000],
  operatorSignInPerIp: [5, 60_000],
  askPerUser: [10, 60_000],
  askPerTenant: [60, 60_000],
  describePerTenant: [60, 60_000],
  embedPerUser: [60, 60_000],
  // Report usage the browser records (views, saves, timings).
  usagePerUser: [60, 60_000],
  crmWritePerTenant: [300, 60_000],
  dataLoadPerTenant: [10, 60_000],
});

export const isGuid = (value) => typeof value === 'string' && GUID.test(value);
export const isLoopbackHost = (host) => LOOPBACK.has(String(host || '').toLowerCase());

function defaultDataDir() {
  const base = process.env.LOCALAPPDATA || path.join(os.homedir(), '.local', 'share');
  return path.join(base, 'fabric-saas-platform');
}

// Where the registry and the customers' stored credentials live (DATA_DIR), outside the project by default.
export const dataDirOf = (env = process.env) => (env.DATA_DIR || '').trim() || defaultDataDir();

const flag = (value) => /^(1|true|yes)$/i.test(String(value || '').trim());
const int = (value, fallback) => (value === undefined || value === '' ? fallback : Number(value));

function parseLimits(text, errors) {
  if (!text) return { ...DEFAULT_LIMITS };
  try {
    const overrides = JSON.parse(text);
    const limits = { ...DEFAULT_LIMITS };
    for (const [key, value] of Object.entries(overrides)) {
      if (!DEFAULT_LIMITS[key]) errors.push(`RATE_LIMITS has an unknown limit "${key}". Known: ${Object.keys(DEFAULT_LIMITS).join(', ')}.`);
      else if (!Array.isArray(value) || value.length !== 2 || !value.every((n) => Number.isInteger(n) && n > 0)) errors.push(`RATE_LIMITS.${key} must be [count, milliseconds].`);
      else limits[key] = value;
    }
    return limits;
  } catch {
    errors.push('RATE_LIMITS must be JSON, for example {"askPerTenant":[30,60000]}.');
    return { ...DEFAULT_LIMITS };
  }
}

export function loadConfig(env = process.env) {
  const errors = [];
  const authMode = (env.FABRIC_AUTH_MODE || 'mock').trim().toLowerCase();
  const live = authMode !== 'mock';
  const appEnv = (env.APP_ENV || 'development').trim().toLowerCase();
  const production = appEnv === 'production';
  const opsId = (env.FABRIC_OPS_PRINCIPAL_ID || '').trim();
  const publicOrigin = (env.PUBLIC_ORIGIN || '').trim().replace(/\/$/, '');
  const appDomain = (env.APP_DOMAIN || '').trim().toLowerCase().replace(/\.$/, '');

  const config = {
    appEnv,
    production,
    host: env.HOST || '127.0.0.1',
    port: Number(env.PORT || 3000),
    publicOrigin,
    // Each customer's own address: https://<customer>.<APP_DOMAIN> (locally http://fabrikam.localhost:3000). Empty:
    // one address for everyone, and the email domain picks the company at sign-in.
    appDomain,
    // Behind a reverse proxy, the client address comes from X-Forwarded-For; only trust it when told to.
    trustProxy: flag(env.TRUST_PROXY),
    authMode,
    tenantId: (env.AZURE_TENANT_ID || '').trim(),
    clientId: (env.AZURE_CLIENT_ID || '').trim(),
    clientSecret: env.AZURE_CLIENT_SECRET || '',
    capacityId: (env.FABRIC_CAPACITY_ID || '').trim() || (live ? '' : 'mock-capacity'),
    workspacePrefix: env.FABRIC_WORKSPACE_PREFIX ?? 'saas-',
    opsPrincipal: opsId ? { id: opsId, type: (env.FABRIC_OPS_PRINCIPAL_TYPE || 'Group').trim() } : null,
    templateWorkspaceId: (env.FABRIC_TEMPLATE_WORKSPACE_ID || '').trim(),
    dataDir: dataDirOf(env),
    productName: (env.PRODUCT_NAME || '').trim() || 'Platform app',
    sessionSecret: env.SESSION_SECRET || '',
    // Operator (back office) sign-in. Without it the back office only works on a loopback address.
    adminKey: env.ADMIN_KEY || '',
    secureCookies: production || publicOrigin.startsWith('https://'),
    allowDemoSignIn: !production || flag(env.ALLOW_DEMO_SIGNIN),
    // keep = the platform identity stays Admin of customer workspaces; release = it hands over and keeps nothing.
    platformWorkspaceAccess: (env.PLATFORM_WORKSPACE_ACCESS || (production ? 'release' : 'keep')).trim().toLowerCase(),
    embedTokenMinutes: int(env.EMBED_TOKEN_MINUTES, 30),
    // The data agent's code interpreter tool (preview; paid F2+ or P1+ capacity, not trials), which draws charts.
    dataAgentCodeInterpreter: flag(env.DATA_AGENT_CODE_INTERPRETER),
    // Customers building and editing their own reports (the next phase). Off: the standard reports, view only.
    reportAuthoring: flag(env.REPORT_AUTHORING),
    // "View as": sign in as one of a company's people without a password, to show what each one sees. For local demos
    // and testing only: never in production, and off behind a proxy (TRUST_PROXY or PUBLIC_ORIGIN), where any visitor
    // can look local. The routes also refuse anyone who isn't on this computer (routes/customer.js).
    personaSwitcher: env.PERSONA_SWITCHER ? flag(env.PERSONA_SWITCHER) : !production && !flag(env.TRUST_PROXY) && !publicOrigin,
    sampleDataDefault: env.SAMPLE_DATA_DEFAULT ? flag(env.SAMPLE_DATA_DEFAULT) : !production,
    limits: parseLimits(env.RATE_LIMITS, errors),
    provisioning: { maxConcurrent: int(env.PROVISIONING_CONCURRENCY, 4) },
    crmPools: { maxOpen: int(env.CRM_MAX_OPEN_DATABASES, 100), idleMinutes: int(env.CRM_IDLE_MINUTES, 15) },
    // Per-customer service accounts (see src/platform/identities.js).
    identity: {
      mode: (env.TENANT_IDENTITY_MODE || (production ? 'required' : 'preferred')).trim().toLowerCase(),
      autoCreate: flag(env.TENANT_IDENTITY_AUTO_CREATE),
      fabricGroupId: (env.FABRIC_SP_GROUP_ID || '').trim(),
      // The credential the platform gives the service accounts it creates: federated (trusts the app's managed
      // identity, nothing stored) or certificate. Accounts an admin registers bring their own.
      credential: (env.TENANT_CREDENTIAL || (env.MANAGED_IDENTITY_CLIENT_ID ? 'federated' : 'certificate')).trim().toLowerCase(),
    },
    // A user-assigned managed identity whose tokens stand in for app credentials (federated identity credentials).
    federated: {
      managedIdentityClientId: (env.MANAGED_IDENTITY_CLIENT_ID || '').trim(),
      managedIdentityObjectId: (env.MANAGED_IDENTITY_OBJECT_ID || '').trim(),
      tokenFile: (env.AZURE_FEDERATED_TOKEN_FILE || '').trim(),
      audience: (env.AZURE_FEDERATED_AUDIENCE || TOKEN_EXCHANGE_AUDIENCE).trim(),
      getAssertion: null,
    },
    // The platform identity's own credential, built below: federated, certificate or (development) secret.
    credential: null,
    secrets: {
      provider: (env.SECRETS_PROVIDER || (production ? 'keyvault' : live ? 'file' : 'memory')).trim().toLowerCase(),
      key: env.SECRETS_KEY || '',
      keyVaultUrl: (env.KEY_VAULT_URL || '').trim(),
      file: '',
    },
    endpoints: {
      fabric: env.FABRIC_API_BASE || 'https://api.fabric.microsoft.com/v1',
      powerbi: env.POWERBI_API_BASE || 'https://api.powerbi.com/v1.0/myorg',
      onelake: env.ONELAKE_DFS_BASE || 'https://onelake.dfs.fabric.microsoft.com',
      login: env.AZURE_AUTHORITY_HOST || 'https://login.microsoftonline.com',
      graph: env.GRAPH_API_BASE || 'https://graph.microsoft.com/v1.0',
    },
  };
  config.secrets.file = path.join(config.dataDir, 'secrets.json');

  // Federated credentials: the app's user-assigned managed identity (App Service, Container Apps, virtual machines),
  // or a workload identity token file (Kubernetes). One assertion source serves the platform identity and every
  // customer service account that trusts it.
  const { federated } = config;
  if (federated.tokenFile) federated.getAssertion = tokenFileAssertion(federated.tokenFile);
  else if (federated.managedIdentityClientId) {
    if (!isGuid(federated.managedIdentityClientId)) errors.push('MANAGED_IDENTITY_CLIENT_ID must be the client ID (GUID) of a user-assigned managed identity.');
    else federated.getAssertion = managedIdentityAssertion({ clientId: federated.managedIdentityClientId, audience: federated.audience });
  }
  if (federated.managedIdentityObjectId && !isGuid(federated.managedIdentityObjectId)) errors.push('MANAGED_IDENTITY_OBJECT_ID must be the object (principal) ID of the managed identity.');
  if (!CREDENTIAL_TYPES.includes(config.identity.credential) || config.identity.credential === 'secret') {
    errors.push('TENANT_CREDENTIAL must be federated or certificate: the credential the platform gives the service accounts it creates.');
  }
  if (config.identity.autoCreate && config.identity.credential === 'federated' && (!federated.getAssertion || !federated.managedIdentityObjectId)) {
    errors.push('TENANT_CREDENTIAL=federated needs MANAGED_IDENTITY_CLIENT_ID and MANAGED_IDENTITY_OBJECT_ID: the managed identity that new service accounts trust.');
  }

  // The platform identity's credential, best first.
  const certificatePath = (env.AZURE_CLIENT_CERTIFICATE_PATH || '').trim();
  if (authMode === 'sp') {
    if (federated.getAssertion) config.credential = { type: 'federated', source: federated.tokenFile ? 'token file' : 'managed identity', getAssertion: federated.getAssertion };
    else if (certificatePath) {
      try {
        config.credential = { ...certificateCredential(readFileSync(certificatePath, 'utf8')), source: certificatePath };
      } catch (error) {
        errors.push(`AZURE_CLIENT_CERTIFICATE_PATH: ${error.code === 'ENOENT' ? `no file at ${certificatePath}` : error.message}`);
      }
    } else if (config.clientSecret) config.credential = { type: 'secret', secret: config.clientSecret };
  }

  if (!APP_ENVS.includes(appEnv)) errors.push(`APP_ENV must be one of ${APP_ENVS.join(', ')}.`);
  if (!AUTH_MODES.includes(authMode)) errors.push(`FABRIC_AUTH_MODE must be one of ${AUTH_MODES.join(', ')}.`);
  if (!IDENTITY_MODES.includes(config.identity.mode)) errors.push(`TENANT_IDENTITY_MODE must be one of ${IDENTITY_MODES.join(', ')}.`);
  if (!PLATFORM_ACCESS.includes(config.platformWorkspaceAccess)) errors.push(`PLATFORM_WORKSPACE_ACCESS must be one of ${PLATFORM_ACCESS.join(', ')}.`);
  if (config.platformWorkspaceAccess === 'release' && config.identity.mode === 'off') errors.push('PLATFORM_WORKSPACE_ACCESS=release needs customer service accounts (TENANT_IDENTITY_MODE preferred or required).');
  if (!SECRET_PROVIDERS.includes(config.secrets.provider)) errors.push(`SECRETS_PROVIDER must be one of ${SECRET_PROVIDERS.join(', ')}.`);
  if (config.secrets.provider === 'keyvault' && !config.secrets.keyVaultUrl) errors.push('KEY_VAULT_URL is required when SECRETS_PROVIDER=keyvault.');
  if (config.secrets.key && config.secrets.key.length < 16) errors.push('SECRETS_KEY must be at least 16 characters.');
  if (config.identity.fabricGroupId && !isGuid(config.identity.fabricGroupId)) errors.push('FABRIC_SP_GROUP_ID must be a security group object ID.');
  if (!Number.isInteger(config.port) || config.port < 0 || config.port > 65535) errors.push('PORT must be a valid port number.');
  if (publicOrigin && !/^https?:\/\/[^/\s]+$/i.test(publicOrigin)) errors.push('PUBLIC_ORIGIN must look like https://platform.example.com (no path).');
  if (appDomain && (!HOSTNAME.test(appDomain) || /^\d+(\.\d+){3}$/.test(appDomain))) {
    errors.push('APP_DOMAIN must be a host name, such as localhost or platform.example.com (no scheme, port or IP address).');
  } else if (appDomain && /^https?:\/\/[^/\s]+$/i.test(publicOrigin) && new URL(publicOrigin).hostname !== appDomain) {
    errors.push(`PUBLIC_ORIGIN must be the address of APP_DOMAIN (https://${appDomain}): the back office runs there, and customers get https://<customer>.${appDomain}.`);
  }
  if (!Number.isInteger(config.embedTokenMinutes) || config.embedTokenMinutes < 5 || config.embedTokenMinutes > 60) errors.push('EMBED_TOKEN_MINUTES must be between 5 and 60.');
  if (!Number.isInteger(config.provisioning.maxConcurrent) || config.provisioning.maxConcurrent < 1 || config.provisioning.maxConcurrent > 50) errors.push('PROVISIONING_CONCURRENCY must be between 1 and 50.');
  if (!Number.isInteger(config.crmPools.maxOpen) || config.crmPools.maxOpen < 1) errors.push('CRM_MAX_OPEN_DATABASES must be a positive number.');
  if (!Number.isFinite(config.crmPools.idleMinutes) || config.crmPools.idleMinutes <= 0) errors.push('CRM_IDLE_MINUTES must be a positive number.');
  if (config.adminKey && config.adminKey.length < 24) errors.push('ADMIN_KEY must be at least 24 characters.');
  // Fail closed: the back office can create, change and delete customers.
  if (!isLoopbackHost(config.host) && !config.adminKey) errors.push(`HOST=${config.host} exposes the back office. Set ADMIN_KEY (24+ characters) or keep HOST on 127.0.0.1.`);
  // A reverse proxy in front of a loopback HOST still publishes the back office.
  else if ((config.trustProxy || publicOrigin) && !config.adminKey) errors.push('TRUST_PROXY or PUBLIC_ORIGIN means the app is reachable through a proxy. Set ADMIN_KEY (24+ characters) so the back office needs a sign-in.');
  if (production && config.personaSwitcher) errors.push('PERSONA_SWITCHER signs people in without a password; it is for local demos and testing only, not APP_ENV=production.');
  else if (config.personaSwitcher && (config.trustProxy || publicOrigin)) errors.push('PERSONA_SWITCHER signs people in without a password, so it only runs without TRUST_PROXY and PUBLIC_ORIGIN: behind a proxy, any visitor can look like this computer.');
  // The tenant ID is passed to the Azure CLI, so only allow GUIDs or domain names.
  if (config.tenantId && !TENANT.test(config.tenantId)) errors.push('AZURE_TENANT_ID must be a tenant GUID or domain name.');
  if (authMode === 'sp') {
    if (!config.tenantId) errors.push('AZURE_TENANT_ID is required when FABRIC_AUTH_MODE=sp.');
    if (!isGuid(config.clientId)) errors.push('AZURE_CLIENT_ID must be the app registration (client) ID when FABRIC_AUTH_MODE=sp.');
    if (!config.credential && !errors.some((e) => e.startsWith('AZURE_CLIENT_CERTIFICATE_PATH') || e.startsWith('MANAGED_IDENTITY_CLIENT_ID'))) {
      errors.push('FABRIC_AUTH_MODE=sp needs a credential for the platform identity: MANAGED_IDENTITY_CLIENT_ID (federated, nothing secret), AZURE_CLIENT_CERTIFICATE_PATH (a PEM certificate) or, for development, AZURE_CLIENT_SECRET. Run in a terminal to be asked for it.');
    }
  }
  if (live && config.capacityId && !isGuid(config.capacityId)) errors.push('FABRIC_CAPACITY_ID must be a capacity GUID.');
  if (live && config.templateWorkspaceId && !isGuid(config.templateWorkspaceId)) errors.push('FABRIC_TEMPLATE_WORKSPACE_ID must be a workspace GUID.');
  if (config.opsPrincipal) {
    if (!isGuid(config.opsPrincipal.id)) errors.push('FABRIC_OPS_PRINCIPAL_ID must be an Entra object ID.');
    if (!PRINCIPAL_TYPES.includes(config.opsPrincipal.type)) errors.push(`FABRIC_OPS_PRINCIPAL_TYPE must be one of ${PRINCIPAL_TYPES.join(', ')}.`);
  }

  // The production profile refuses settings that are fine on a laptop but unsafe for real customers.
  if (production) {
    if (authMode !== 'sp') errors.push('APP_ENV=production needs FABRIC_AUTH_MODE=sp: a dedicated platform identity, not a person.');
    // Microsoft recommends certificates over secrets for embedding back ends; a federated credential needs neither.
    if (config.credential?.type === 'secret') errors.push('APP_ENV=production needs a federated credential (MANAGED_IDENTITY_CLIENT_ID) or a certificate (AZURE_CLIENT_CERTIFICATE_PATH) for the platform identity. Client secrets are for development.');
    if (config.identity.mode !== 'required') errors.push('APP_ENV=production needs TENANT_IDENTITY_MODE=required, so no customer ever runs on the shared platform identity.');
    if (config.platformWorkspaceAccess !== 'release') errors.push('APP_ENV=production needs PLATFORM_WORKSPACE_ACCESS=release, so the platform keeps no standing access to customer workspaces.');
    if (config.secrets.provider !== 'keyvault') errors.push('APP_ENV=production needs SECRETS_PROVIDER=keyvault.');
    if (config.sessionSecret.length < 32) errors.push('APP_ENV=production needs SESSION_SECRET with 32+ characters.');
    if (config.adminKey.length < 32) errors.push('APP_ENV=production needs ADMIN_KEY with 32+ characters.');
    if (!publicOrigin.startsWith('https://')) errors.push('APP_ENV=production needs PUBLIC_ORIGIN=https://... (cookies are Secure, and HSTS is sent).');
    if (!config.allowDemoSignIn) errors.push('The email-only customer sign-in is a demo. Connect your identity provider, or set ALLOW_DEMO_SIGNIN=true for a staging environment.');
  }

  if (errors.length) {
    const error = new Error(`Invalid configuration:\n- ${errors.join('\n- ')}`);
    error.code = 'CONFIG';
    throw error;
  }

  config.warnings = [];
  if (live && !config.capacityId) config.warnings.push('FABRIC_CAPACITY_ID is not set, so new workspaces need a per-customer capacity or an adopted workspace.');
  if (live && config.identity.mode === 'preferred') config.warnings.push('TENANT_IDENTITY_MODE=preferred: customers without a service account use the shared platform identity. Use required in production.');
  if (live && config.platformWorkspaceAccess === 'keep') config.warnings.push('PLATFORM_WORKSPACE_ACCESS=keep: the platform identity stays Admin of every customer workspace (and an identity can be in at most 1,000 workspaces). Use release in production.');
  if (live && config.secrets.provider === 'file' && !config.secrets.key) config.warnings.push('SECRETS_KEY is not set, so customer service account secrets cannot be stored.');
  if (config.credential?.type === 'secret') config.warnings.push('The platform identity signs in with a client secret. Microsoft recommends a certificate (AZURE_CLIENT_CERTIFICATE_PATH) or a federated credential (MANAGED_IDENTITY_CLIENT_ID).');
  if (config.credential?.type === 'certificate' && Date.parse(config.credential.notAfter) < Date.now() + 30 * 86_400_000) {
    config.warnings.push(`The platform identity's certificate expires ${config.credential.notAfter.slice(0, 10)}. Upload a new one to the app registration and point AZURE_CLIENT_CERTIFICATE_PATH at it.`);
  }
  if (!config.adminKey) config.warnings.push('ADMIN_KEY is not set: the back office has no sign-in and only works because HOST is a loopback address.');
  if (!config.sessionSecret) config.warnings.push('SESSION_SECRET is not set, so customer sessions end when the server restarts.');
  if (live && config.personaSwitcher) config.warnings.push('PERSONA_SWITCHER is on: on this computer, "View as" signs in as any of a company\'s people without a password. Set PERSONA_SWITCHER=false to turn it off.');
  if (production && flag(env.ALLOW_DEMO_SIGNIN)) config.warnings.push('ALLOW_DEMO_SIGNIN=true: anyone who knows a customer email domain can sign in as that customer. Staging only.');
  if (production && !appDomain) config.warnings.push('APP_DOMAIN is not set, so every customer signs in at the same address. Give each customer its own: APP_DOMAIN=platform.example.com gives https://<customer>.platform.example.com.');
  return Object.freeze(config);
}
