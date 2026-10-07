import { isLoopbackHost } from '../config.js';
import { slugify } from './store.js';

// Each customer has its own address. With APP_DOMAIN=localhost, Fabrikam is http://fabrikam.localhost:3000 and Contoso
// http://contoso.localhost:3000 (browsers send *.localhost to this computer); with APP_DOMAIN=platform.example.com,
// they're https://fabrikam.platform.example.com and https://contoso.platform.example.com.
//
// - A customer's address shows that customer's name and logo, and signs in only that customer's people.
// - A session works only at the address that issued it: the browser keeps each address's cookie to itself, and the
//   server also checks that the session's customer is the address's customer.
// - The apex (APP_DOMAIN itself, or a loopback address) serves the back office and a "find your company" step that
//   sends people to their company's address. Customers never sign in there.
// - Any other host name is refused, so a DNS name pointed at this server can't serve it (DNS rebinding).
//
// Without APP_DOMAIN, everyone uses one address and the email domain picks the company at sign-in.

// Names that look like the platform's own addresses are never given to a customer.
export const RESERVED_SUBDOMAINS = new Set(['www', 'admin', 'api', 'app', 'apps', 'auth', 'login', 'signin', 'sso', 'mail', 'static', 'cdn', 'assets', 'status', 'support', 'help', 'docs']);
const LABEL = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

export const subdomainOf = (tenant) => tenant.subdomain || tenant.slug;

// A new customer's subdomain, from its name: unique, and never a reserved name.
export function uniqueSubdomain(name, tenants) {
  let base = slugify(name);
  if (RESERVED_SUBDOMAINS.has(base)) base = `${base}-crm`;
  const taken = new Set(tenants.map(subdomainOf));
  let candidate = base;
  for (let n = 2; taken.has(candidate) || RESERVED_SUBDOMAINS.has(candidate); n++) candidate = `${base}-${n}`;
  return candidate;
}

// The host name the browser used, without the port. Behind a trusted proxy, the host it forwarded.
export function hostOf(req, { trustProxy = false } = {}) {
  const forwarded = trustProxy ? String(req.headers['x-forwarded-host'] || '').split(',')[0] : '';
  const value = (forwarded || String(req.headers.host || '')).trim().toLowerCase();
  if (value.startsWith('[')) return value.slice(0, value.indexOf(']') + 1);
  return value.replace(/:\d+$/, '').replace(/\.$/, '');
}

// What a request's address is: 'single' (no APP_DOMAIN), 'apex', 'customer' (with its tenant), 'unknown' (a
// subdomain no customer has) or 'foreign' (not this platform's name at all).
export function resolveSite(host, config, tenants) {
  const domain = config.appDomain;
  if (!domain) return { kind: 'single' };
  if (!host || host === domain || isLoopbackHost(host) || host === '[::1]') return { kind: 'apex' };
  if (!host.endsWith(`.${domain}`)) return { kind: 'foreign' };
  const label = host.slice(0, -(domain.length + 1));
  if (!LABEL.test(label)) return { kind: 'unknown' };
  const matches = tenants.filter((t) => subdomainOf(t) === label);
  // Two customers can't share an address; if a hand edit ever made them, neither gets it.
  return matches.length === 1 ? { kind: 'customer', tenant: matches[0] } : { kind: 'unknown' };
}

function origin(config, host) {
  if (config.publicOrigin) {
    const url = new URL(config.publicOrigin);
    url.hostname = host;
    return url.origin;
  }
  return `http://${host}${config.port && config.port !== 80 ? `:${config.port}` : ''}`;
}

// Where a customer's people sign in. Null without APP_DOMAIN: everyone uses the platform's address.
export const customerUrl = (config, tenant) => (config.appDomain ? `${origin(config, `${subdomainOf(tenant)}.${config.appDomain}`)}/` : null);

// The platform's own address: the back office, and without APP_DOMAIN the app itself.
export function platformUrl(config) {
  if (config.appDomain) return `${origin(config, config.appDomain)}/`;
  if (config.publicOrigin) return `${config.publicOrigin}/`;
  return `http://${['0.0.0.0', '::'].includes(config.host) ? 'localhost' : config.host}:${config.port}/`;
}

// Where a person signs in: their company's address, or the shared one.
export const signInUrl = (config, tenant) => customerUrl(config, tenant) || platformUrl(config);
