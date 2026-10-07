import { HttpError } from './router.js';

// Token buckets kept in memory: fine for one server process. With several instances behind a load balancer, keep the
// buckets in a shared store (for example Azure Cache for Redis) so limits hold across instances.

export function createRateLimiter({ now = () => Date.now(), maxKeys = 50_000 } = {}) {
  const buckets = new Map();

  function prune(at) {
    for (const [key, bucket] of buckets) if (at - bucket.at > bucket.perMs) buckets.delete(key);
    // Still full of active clients (a flood of new keys): drop the oldest buckets instead of growing without bound.
    for (const key of buckets.keys()) {
      if (buckets.size < maxKeys * 0.9) break;
      buckets.delete(key);
    }
  }

  function take(key, [limit, perMs]) {
    const at = now();
    let bucket = buckets.get(key);
    if (!bucket) {
      if (buckets.size >= maxKeys) prune(at);
      bucket = { tokens: limit, at, perMs };
      buckets.set(key, bucket);
    }
    bucket.tokens = Math.min(limit, bucket.tokens + ((at - bucket.at) / perMs) * limit);
    bucket.at = at;
    if (bucket.tokens >= 1) {
      bucket.tokens -= 1;
      return { ok: true };
    }
    return { ok: false, retryAfterSeconds: Math.max(1, Math.ceil((((1 - bucket.tokens) / limit) * perMs) / 1000)) };
  }

  // Takes one token from every bucket that applies; the first empty one answers with 429 and a Retry-After.
  function enforce(rules) {
    for (const { key, limit, message } of rules) {
      if (!limit) continue;
      const result = take(key, limit);
      if (!result.ok) throw new HttpError(429, message || 'Too many requests. Please wait a moment and try again.', { retryAfter: result.retryAfterSeconds });
    }
  }

  return { take, enforce, size: () => buckets.size };
}

// The address the request came from. X-Forwarded-For is only trusted behind a known proxy (TRUST_PROXY=true).
export function clientAddress(req, { trustProxy = false } = {}) {
  if (trustProxy) {
    const forwarded = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim();
    if (forwarded) return forwarded;
  }
  return req.socket?.remoteAddress || 'unknown';
}
