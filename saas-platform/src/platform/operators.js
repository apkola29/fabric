import { createHash, createHmac, randomBytes, timingSafeEqual } from 'node:crypto';
import { parseCookies } from './sessions.js';

// Operator (back office) sign-in. The back office can create, change and delete every customer, so it never shares
// the customer session: operators prove they hold ADMIN_KEY once and get a short, strictly scoped cookie.
// In production, put the back office behind your workforce identity provider (for example Entra ID with Conditional
// Access) as well; this key is the minimum.

const COOKIE = 'fsp_operator';
const digest = (text) => createHash('sha256').update(String(text)).digest();

export function createOperatorAuth({ key = '', secure = false, maxAgeSeconds = 4 * 60 * 60 } = {}) {
  // Derived from the key, so rotating ADMIN_KEY signs every operator out.
  const signingKey = key ? createHmac('sha256', 'platform-app-operator').update(key).digest() : randomBytes(32);
  const sign = (payload) => createHmac('sha256', signingKey).update(payload).digest('base64url');
  const attributes = `HttpOnly; SameSite=Strict; Path=/api/admin${secure ? '; Secure' : ''}`;

  return {
    required: Boolean(key),
    verifyKey(candidate) {
      if (!key || typeof candidate !== 'string' || !candidate) return false;
      return timingSafeEqual(digest(candidate), digest(key));
    },
    // The name is self-declared (the key is shared), so it gives the audit trail context, not proof of who it was.
    issue({ name = '' } = {}) {
      const label = String(name).replace(/[^\p{L}\p{N} ._@-]/gu, '').trim().slice(0, 40) || 'operator';
      const payload = Buffer.from(JSON.stringify({ r: 'operator', n: label, exp: Math.floor(Date.now() / 1000) + maxAgeSeconds })).toString('base64url');
      return `${COOKIE}=${payload}.${sign(payload)}; ${attributes}; Max-Age=${maxAgeSeconds}`;
    },
    clear: () => `${COOKIE}=; ${attributes}; Max-Age=0`,
    read(cookieHeader) {
      const value = parseCookies(cookieHeader)[COOKIE];
      if (!value) return null;
      const [payload, signature] = value.split('.');
      if (!payload || !signature) return null;
      const expected = Buffer.from(sign(payload));
      const actual = Buffer.from(signature);
      if (expected.length !== actual.length || !timingSafeEqual(expected, actual)) return null;
      try {
        const data = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
        return data?.r === 'operator' && data.exp > Date.now() / 1000 ? { name: data.n || 'operator' } : null;
      } catch {
        return null;
      }
    },
  };
}
