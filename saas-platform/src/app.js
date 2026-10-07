import { randomBytes } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createCrmService } from './crm/index.js';
import { createRateLimiter } from './http/limits.js';
import { HttpError, createRouter, sendJson, serveStatic } from './http/router.js';
import { createAssistant } from './platform/assistant.js';
import { createIdentityBroker } from './platform/identities.js';
import { createOperatorAuth } from './platform/operators.js';
import { createProvisioner } from './platform/provisioner.js';
import { createSecretStore } from './platform/secrets.js';
import { createSessions } from './platform/sessions.js';
import { hostOf, resolveSite } from './platform/tenancy.js';
import { registerAdminRoutes } from './routes/admin.js';
import { registerCustomerRoutes } from './routes/customer.js';

// Two front ends on one server:
//   /        the end customer's app (signs in, sees their data, reports and answers)
//   /admin   the platform team's back office (customers, plans, provisioning), behind operator sign-in
// With APP_DOMAIN, each customer has its own address and the back office only answers on the platform's own
// (see platform/tenancy.js).

const PUBLIC_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'public');
const MUTATING = new Set(['POST', 'PATCH', 'PUT', 'DELETE']);
// Reachable without operator sign-in: the sign-in itself.
const OPERATOR_OPEN = new Set(['/api/admin/session']);
const BACK_OFFICE = /^\/(admin|api\/admin)(\/|$)/;

const CSP = [
  "default-src 'self'",
  "script-src 'self' https://cdn.jsdelivr.net https://cdn.sheetjs.com",
  // powerbi-client writes its iframe with an inline style attribute.
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "connect-src 'self'",
  'frame-src https://app.powerbi.com https://*.powerbi.com https://*.fabric.microsoft.com https://*.analysis.windows.net',
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ');

// Fullscreen and clipboard stay available: the embedded reports use them.
const PERMISSIONS_POLICY = 'camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=(), bluetooth=()';

export function createApp({
  config,
  fabric,
  store,
  tokens = null,
  fetchOptions,
  sessions,
  log = console.log,
  secrets = null,
  identities = null,
  crm = null,
  crmDir = null,
  provisionerOptions = {},
  operators = null,
  limiter = null,
}) {
  secrets ||= createSecretStore(config, { tokens });
  identities ||= createIdentityBroker({ config, platformTokens: tokens, platformFabric: fabric, secrets });
  crm ||= createCrmService({ fabric, identities, sqliteDir: crmDir, ...(config.crmPools || {}) });
  operators ||= createOperatorAuth({ key: config.adminKey, secure: config.secureCookies });
  limiter ||= createRateLimiter();
  const assistant = createAssistant({ store, identities, crm, mock: fabric.kind === 'mock' });
  const provisioner = createProvisioner({ fabric, store, config, identities, crm, ...provisionerOptions });
  const router = createRouter();
  const context = {
    config,
    fabric,
    store,
    tokens,
    provisioner,
    identities,
    crm,
    assistant,
    fetchOptions,
    operators,
    limiter,
    sessions: sessions || createSessions({ secret: config.sessionSecret, secure: config.secureCookies }),
  };
  registerAdminRoutes(router, context);
  registerCustomerRoutes(router, context);
  router.get('/api/health', ({ res }) => sendJson(res, 200, { ok: true }));

  function handleError(res, error, pathname) {
    const backOffice = pathname.startsWith('/api/admin');
    let status = 500;
    let body = { error: error?.message || 'Unexpected error.' };
    if (error instanceof HttpError) {
      status = error.status;
      if (error.retryAfter) res.setHeader('retry-after', String(error.retryAfter));
    } else if (error?.name === 'FabricApiError' || error?.name === 'McpError') {
      status = [400, 404, 409].includes(error.upstreamStatus) ? error.upstreamStatus : 502;
      body = { error: error.message, code: error.code || undefined, requestId: error.requestId || undefined, upstreamStatus: error.upstreamStatus || undefined };
    } else if (error?.name === 'AuthError') status = 502;
    else if (error?.name === 'IdentityError') status = 503;
    // Customers get a plain message and a reference; Fabric details, IDs and identity names stay in the server log.
    if (!backOffice && !(error instanceof HttpError)) {
      const ref = randomBytes(4).toString('hex');
      console.error(`[${ref}] ${pathname}:`, error);
      status = status === 500 ? 500 : 503;
      body = { error: 'Something went wrong on our side. Please try again in a moment.', ref };
    } else if (status === 500) console.error(error);
    if (res.headersSent) {
      res.destroy();
      return;
    }
    sendJson(res, status, body);
  }

  async function handler(req, res) {
    const started = Date.now();
    res.setHeader('content-security-policy', CSP);
    res.setHeader('x-content-type-options', 'nosniff');
    res.setHeader('referrer-policy', 'no-referrer');
    res.setHeader('x-frame-options', 'DENY');
    res.setHeader('cross-origin-opener-policy', 'same-origin');
    res.setHeader('cross-origin-resource-policy', 'same-origin');
    res.setHeader('permissions-policy', PERMISSIONS_POLICY);
    if (config.secureCookies) res.setHeader('strict-transport-security', 'max-age=31536000; includeSubDomains');
    let pathname = req.url;
    try {
      const url = new URL(req.url, 'http://localhost');
      pathname = url.pathname;
      req.site = resolveSite(hostOf(req, config), config, store.list());
      if (req.site.kind === 'foreign' && pathname !== '/api/health') throw new HttpError(421, "This server doesn't answer to that address.");
      if (BACK_OFFICE.test(pathname) && (req.site.kind === 'customer' || req.site.kind === 'unknown')) throw new HttpError(404, 'Not found.');
      if (pathname.startsWith('/api/')) {
        // Browsers only send a custom header cross-site after a CORS preflight, which this server never approves.
        if (MUTATING.has(req.method) && req.headers['x-platform-client'] !== 'web') throw new HttpError(403, 'Missing the x-platform-client header.');
        if (pathname.startsWith('/api/admin/') && !OPERATOR_OPEN.has(pathname.replace(/\/$/, ''))) {
          req.operator = operators.read(req.headers.cookie);
          if (operators.required && !req.operator) throw new HttpError(401, 'Operator sign-in required.');
        }
        const match = router.match(req.method, pathname);
        if (!match) throw new HttpError(404, 'Not found.');
        if (match.methodNotAllowed) throw new HttpError(405, 'Method not allowed.');
        await match.handler({ req, res, url, params: match.params });
      } else {
        if (req.method !== 'GET' && req.method !== 'HEAD') throw new HttpError(405, 'Method not allowed.');
        if (!(await serveStatic(req, res, PUBLIC_DIR, pathname))) throw new HttpError(404, 'Not found.');
      }
    } catch (error) {
      handleError(res, error, String(pathname || ''));
    } finally {
      if (log && String(pathname).startsWith('/api/')) log(`${req.method} ${pathname} ${res.statusCode} ${Date.now() - started}ms`);
    }
  }

  // Picks up provisioning runs that were cut off when the server stopped.
  function resumeInterrupted() {
    const interrupted = store.list().filter((t) => t.status === 'provisioning' || t.status === 'pending');
    for (const tenant of interrupted) provisioner.provision(tenant.id);
    return interrupted.length;
  }

  return { handler, provisioner, resumeInterrupted, identities, crm, operators, limiter, close: () => crm.closeAll() };
}
