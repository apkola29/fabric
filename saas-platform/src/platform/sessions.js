import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto';

// Customer sessions. The company (tenant) is resolved on the server, from the company's own address (APP_DOMAIN) and the
// user's email domain, and carried in a signed cookie, so the browser can never choose which customer's data it sees.
// This local MVP has no passwords: in production, plug in the SaaS app's real sign-in and keep the tenant lookup.

const COOKIE = 'fsp_session';
const DOMAIN = /^(?=.{3,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/;

export function parseCookies(header = '') {
  const cookies = {};
  for (const part of String(header).split(';')) {
    const index = part.indexOf('=');
    if (index < 1) continue;
    cookies[part.slice(0, index).trim()] = part.slice(index + 1).trim();
  }
  return cookies;
}

export function emailDomain(email) {
  const match = /^[^@\s]+@([^@\s]+)$/.exec(String(email || '').trim().toLowerCase());
  return match && DOMAIN.test(match[1]) ? match[1] : null;
}

// Accepts an array or a comma/space separated string. Throws on anything that isn't a plain domain name.
export function parseDomains(input) {
  const values = (Array.isArray(input) ? input : String(input || '').split(/[\s,;]+/))
    .map((d) => String(d).trim().toLowerCase().replace(/^@/, ''))
    .filter(Boolean);
  const invalid = values.filter((d) => !DOMAIN.test(d));
  if (invalid.length) throw new Error(`Not a valid email domain: ${invalid.join(', ')}`);
  return [...new Set(values)];
}

export function createSessions({ secret, maxAgeSeconds = 8 * 60 * 60, secure = false } = {}) {
  // Without SESSION_SECRET, a random key is used, so sessions end when the server restarts.
  const key = secret ? Buffer.from(String(secret)) : randomBytes(32);
  const sign = (payload) => createHmac('sha256', key).update(payload).digest('base64url');
  // Over HTTPS the __Host- prefix makes browsers refuse the cookie unless it's Secure, host-only and for the whole
  // path, so another customer's subdomain can never set or widen it.
  const cookie = secure ? `__Host-${COOKIE}` : COOKIE;
  const attributes = `HttpOnly; SameSite=Lax; Path=/${secure ? '; Secure' : ''}`;

  return {
    // sv is the person's session version: a password reset or removal bumps it, ending earlier sessions.
    issue({ tenantId, email, sv }) {
      const payload = Buffer.from(JSON.stringify({ t: tenantId, e: email, ...(sv ? { sv } : {}), exp: Math.floor(Date.now() / 1000) + maxAgeSeconds })).toString('base64url');
      return `${cookie}=${payload}.${sign(payload)}; ${attributes}; Max-Age=${maxAgeSeconds}`;
    },
    clear: () => `${cookie}=; ${attributes}; Max-Age=0`,
    read(cookieHeader) {
      const value = parseCookies(cookieHeader)[cookie];
      if (!value) return null;
      const [payload, signature] = value.split('.');
      if (!payload || !signature) return null;
      const expected = Buffer.from(sign(payload));
      const actual = Buffer.from(signature);
      if (expected.length !== actual.length || !timingSafeEqual(expected, actual)) return null;
      let data;
      try {
        data = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
      } catch {
        return null;
      }
      if (!data?.t || !data?.e || data.exp < Date.now() / 1000) return null;
      return { tenantId: data.t, email: data.e, sv: data.sv || null };
    },
  };
}
