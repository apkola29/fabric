import { rm } from 'node:fs/promises';
import path from 'node:path';
import { createCrmRepository } from './repository.js';
import { createFabricSqlStore, createSqliteStore } from './stores.js';

// Hands out one CRM repository per customer: their Fabric SQL database in live mode (signed in as the customer's
// own service account), a SQLite file in demo mode.
//
// Each open repository holds a connection pool, so the number open at once is bounded: the least recently used one
// is closed when there are more than `maxOpen`, and any left idle for `idleMinutes`. In-memory demo databases only
// exist inside their connection, so those are never closed early.

const CLOSE_GRACE_MS = 30_000;

export function createCrmService({ fabric, identities, sqliteDir = null, maxOpen = 100, idleMinutes = 15, now = () => Date.now(), closeGraceMs = CLOSE_GRACE_MS }) {
  // A Map keeps insertion order; moving an entry to the end on every use makes it least-recently-used first.
  const repositories = new Map();
  const evictable = fabric.kind === 'live' || Boolean(sqliteDir);
  let evicted = 0;

  function sqliteFile(tenantId) {
    return sqliteDir ? path.join(sqliteDir, `crm-${tenantId}.sqlite`) : ':memory:';
  }

  // Which identity and database a cached repository was opened with, so a change opens a fresh connection pool.
  const keyFor = (tenant) => `${tenant.identity?.appId || 'platform'}|${tenant.fabric?.crm?.server || ''}|${tenant.fabric?.crm?.database || ''}`;

  async function open(tenant) {
    if (fabric.kind === 'live') {
      const crm = tenant.fabric?.crm;
      if (!crm?.server || !crm?.database) throw Object.assign(new Error("This customer's CRM database isn't set up yet."), { status: 409 });
      const tokens = await identities.tokensFor(tenant);
      // Retries are expected after a quiet spell (the database resumes); the server log shows each one.
      const onRetry = ({ error, attempt, delayMs }) =>
        console.warn(`CRM database of ${tenant.name}: attempt ${attempt} failed (${error.code || error.number || error.name}: ${error.message}); retrying in ${delayMs / 1000} s`);
      return createFabricSqlStore({ server: crm.server, database: crm.database, tokens, onRetry }).then(createCrmRepository);
    }
    return createCrmRepository(createSqliteStore({ file: sqliteFile(tenant.id) }));
  }

  async function forget(tenantId, { deleteData = false } = {}) {
    const entry = repositories.get(tenantId);
    repositories.delete(tenantId);
    if (entry) await entry.pending.then((repo) => repo.close()).catch(() => {});
    if (deleteData && sqliteDir) await rm(sqliteFile(tenantId), { force: true }).catch(() => {});
  }

  // Evicted pools close after a grace period, so a request that already holds the repository can finish.
  function evict() {
    if (!evictable) return;
    const idleBefore = now() - idleMinutes * 60_000;
    let excess = repositories.size - maxOpen;
    const victims = [];
    for (const [tenantId, entry] of repositories) {
      if (excess <= 0 && entry.usedAt >= idleBefore) break;
      victims.push([tenantId, entry]);
      excess -= 1;
    }
    for (const [tenantId, entry] of victims) {
      repositories.delete(tenantId);
      evicted += 1;
      const timer = setTimeout(() => entry.pending.then((repo) => repo.close()).catch(() => {}), closeGraceMs);
      timer.unref?.();
    }
  }

  const sweeper = evictable ? setInterval(evict, 60_000) : null;
  sweeper?.unref?.();

  return {
    async forTenant(tenant) {
      const key = keyFor(tenant);
      let entry = repositories.get(tenant.id);
      if (entry && entry.key !== key) {
        await forget(tenant.id);
        entry = null;
      }
      if (!entry) {
        const pending = open(tenant);
        entry = { key, pending, usedAt: now() };
        const created = entry;
        pending.catch(() => {
          if (repositories.get(tenant.id) === created) repositories.delete(tenant.id);
        });
      }
      entry.usedAt = now();
      repositories.delete(tenant.id);
      repositories.set(tenant.id, entry);
      evict();
      return entry.pending;
    },
    forget,
    evict,
    stats: () => ({ open: repositories.size, maxOpen, idleMinutes, evicted, evictable }),
    async closeAll() {
      if (sweeper) clearInterval(sweeper);
      await Promise.all([...repositories.keys()].map((id) => forget(id)));
    },
  };
}
