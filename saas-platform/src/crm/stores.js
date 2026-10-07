import { DatabaseSync } from 'node:sqlite';
import { tableByName } from './schema.js';

// Two interchangeable stores behind one small interface: query, execute, exec, bulkInsert, close.
// SQL text uses @name parameters, which both node:sqlite and mssql understand.

const ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

// SQL database in Fabric is serverless: after about 15 minutes without activity it releases its compute, and the next
// connection waits while it resumes. Meanwhile connections time out, or the login is refused with 40613 "not currently
// available". Pools here close after the same idle time, so the first question after a quiet spell often meets a paused
// database. Connecting is therefore retried, and so are reads that fail with an error Microsoft lists as transient for
// Azure SQL Database. A write that failed after it was sent isn't retried: it may have been applied.
const TRANSIENT_SQL_ERRORS = new Set([64, 233, 1205, 4060, 4221, 10053, 10054, 10060, 10928, 10929, 40143, 40197, 40501, 40540, 40613, 49918, 49919, 49920]);
// A refused login carries its message but not its number: these are 40613, 40501, 10929 and 40197.
const TRANSIENT_LOGIN = /not currently available|currently busy|too busy|try again/i;
const NO_CONNECTION_CODES = new Set(['ETIMEOUT', 'ESOCKET', 'ECONNRESET', 'ECONNCLOSED']);
const LOST_CONNECTION_CODES = new Set(['ESOCKET', 'ECONNRESET', 'ECONNCLOSED']);
export const SQL_RETRY_DELAYS_MS = Object.freeze([2000, 4000, 8000, 16000, 32000]);
const SQL_RETRY_BUDGET_MS = 90_000;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// How a failed statement may be retried: 'any' when it never reached the database (no connection could be made),
// 'reads' when only a read may safely run again, null when retrying won't help (a refused sign-in, bad SQL, a statement
// that ran too long).
export function sqlRetryable(error) {
  if (error?.name === 'ConnectionError') {
    return NO_CONNECTION_CODES.has(error.code) || (error.code === 'ELOGIN' && TRANSIENT_LOGIN.test(error.message)) ? 'any' : null;
  }
  if (error?.constructor?.name === 'TimeoutError') return 'any'; // the pool couldn't hand out a connection in time
  if (TRANSIENT_SQL_ERRORS.has(Number(error?.number))) return 'reads';
  if (error?.name === 'RequestError' && LOST_CONNECTION_CODES.has(error.code)) return 'reads';
  return null;
}

async function withRetries(operation, { read, delaysMs, onRetry }) {
  const started = Date.now();
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      const kind = sqlRetryable(error);
      const delay = delaysMs[attempt];
      const retry = kind === 'any' || (kind === 'reads' && read);
      if (!retry || delay === undefined || Date.now() - started + delay > SQL_RETRY_BUDGET_MS) throw error;
      onRetry?.({ error, attempt: attempt + 1, delayMs: delay });
      await sleep(delay);
    }
  }
}

function usedParams(sqlText, params) {
  const used = {};
  for (const [name, value] of Object.entries(params)) if (new RegExp(`@${name}\\b`).test(sqlText)) used[name] = value;
  return used;
}

function sqliteValue(value) {
  if (value === undefined) return null;
  if (typeof value === 'boolean') return value ? 1 : 0;
  if (value instanceof Date) return value.toISOString();
  return value;
}

// Demo mode and tests. A file path keeps the data between restarts; ':memory:' doesn't.
export function createSqliteStore({ file = ':memory:' } = {}) {
  const db = new DatabaseSync(file);
  db.exec('PRAGMA foreign_keys = ON;');
  const bind = (sqlText, params) => Object.fromEntries(Object.entries(usedParams(sqlText, params)).map(([k, v]) => [k, sqliteValue(v)]));

  return {
    dialect: 'sqlite',
    async query(sqlText, params = {}) {
      return db.prepare(sqlText).all(bind(sqlText, params));
    },
    async execute(sqlText, params = {}) {
      return { rowsAffected: Number(db.prepare(sqlText).run(bind(sqlText, params)).changes) };
    },
    async exec(sqlText) {
      db.exec(sqlText);
    },
    async bulkInsert(tableName, rows) {
      if (!rows.length) return 0;
      const columns = tableByName(tableName).columns.map((c) => c.name);
      const statement = db.prepare(`INSERT INTO ${tableName} (${columns.join(', ')}) VALUES (${columns.map((c) => `@${c}`).join(', ')})`);
      db.exec('BEGIN');
      try {
        for (const row of rows) statement.run(Object.fromEntries(columns.map((c) => [c, sqliteValue(row[c])])));
        db.exec('COMMIT');
      } catch (error) {
        db.exec('ROLLBACK');
        throw error;
      }
      return rows.length;
    },
    async close() {
      db.close();
    },
  };
}

// Live mode: the customer's SQL database in Fabric, signed in with Microsoft Entra only, as the customer's service
// account (or the platform identity for a customer without one). `onRetry` hears about each retry, for the server log;
// `sqlModule` stands in for the mssql driver in tests.
export async function createFabricSqlStore({ server, database, tokens, poolMax = 10, retryDelaysMs = SQL_RETRY_DELAYS_MS, onRetry = null, sqlModule = null }) {
  const sql = sqlModule || (await import('mssql')).default;
  // tedious asks for a token per new connection, so tokens refresh without recreating the pool.
  const credential = {
    getToken: async (scopes) => ({
      token: await tokens.getToken(Array.isArray(scopes) ? scopes[0] : scopes),
      expiresOnTimestamp: Date.now() + 30 * 60 * 1000,
    }),
  };
  const pool = new sql.ConnectionPool({
    server: server.split(',')[0],
    port: 1433,
    database,
    options: { encrypt: true, trustServerCertificate: false },
    authentication: { type: 'token-credential', options: { credential } },
    pool: { max: poolMax, min: 0, idleTimeoutMillis: 60_000 },
    connectionTimeout: 30_000,
    requestTimeout: 120_000,
  });
  let connecting = null;
  const ready = () => (connecting ||= pool.connect().catch((error) => {
    connecting = null;
    throw error;
  }));

  const COLUMN_TYPES = {
    id: () => sql.NVarChar(36),
    text: (c) => sql.NVarChar(c.size || 200),
    money: () => sql.Decimal(18, 2),
    int: () => sql.Int,
    date: () => sql.Date,
    datetime: () => sql.DateTime2(6),
    bool: () => sql.Bit,
  };

  function typed(value) {
    if (value === null || value === undefined) return [sql.NVarChar(4000), null];
    if (typeof value === 'boolean') return [sql.Bit, value];
    if (typeof value === 'number') return Number.isInteger(value) && Math.abs(value) < 2 ** 31 ? [sql.Int, value] : [sql.Decimal(18, 2), value];
    if (value instanceof Date) return [sql.DateTime2(6), value];
    if (ISO_DATETIME.test(value)) return [sql.DateTime2(6), new Date(value)];
    return [sql.NVarChar(value.length > 4000 ? sql.MAX : 4000), value];
  }

  function normalize(result) {
    const rows = result.recordset || [];
    const columns = rows.columns || result.recordset?.columns || {};
    const dateColumns = Object.values(columns).filter((c) => c.type === sql.Date).map((c) => c.name);
    return rows.map((row) => {
      const out = { ...row };
      for (const [key, value] of Object.entries(out)) {
        if (value instanceof Date) out[key] = dateColumns.includes(key) ? value.toISOString().slice(0, 10) : value.toISOString();
      }
      return out;
    });
  }

  async function run(sqlText, params) {
    await ready();
    const request = pool.request();
    for (const [name, value] of Object.entries(usedParams(sqlText, params))) {
      const [type, converted] = typed(value);
      request.input(name, type, converted);
    }
    return request.query(sqlText);
  }

  const reading = (operation) => withRetries(operation, { read: true, delaysMs: retryDelaysMs, onRetry });
  const writing = (operation) => withRetries(operation, { read: false, delaysMs: retryDelaysMs, onRetry });

  return {
    dialect: 'mssql',
    async query(sqlText, params = {}) {
      return normalize(await reading(() => run(sqlText, params)));
    },
    async execute(sqlText, params = {}) {
      const result = await writing(() => run(sqlText, params));
      return { rowsAffected: result.rowsAffected.reduce((sum, n) => sum + n, 0) };
    },
    async exec(sqlText) {
      await writing(async () => {
        await ready();
        await pool.request().batch(sqlText);
      });
    },
    async bulkInsert(tableName, rows) {
      if (!rows.length) return 0;
      const meta = tableByName(tableName);
      const table = new sql.Table(`dbo.${tableName}`);
      table.create = false;
      for (const c of meta.columns) table.columns.add(c.name, COLUMN_TYPES[c.type](c), { nullable: !(c.name === meta.key || c.required) });
      for (const row of rows) {
        table.rows.add(
          ...meta.columns.map((c) => {
            const value = row[c.name];
            if (value === null || value === undefined) return null;
            if (c.type === 'date') return new Date(`${value}T00:00:00Z`);
            if (c.type === 'datetime') return new Date(value);
            return value;
          }),
        );
      }
      const result = await writing(async () => {
        await ready();
        return pool.request().bulk(table);
      });
      return result.rowsAffected;
    },
    async close() {
      await pool.close();
    },
  };
}
