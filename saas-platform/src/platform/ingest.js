import dns from 'node:dns/promises';
import net from 'node:net';
import { HttpError } from '../http/router.js';
import { jsonToCsv, toCsv } from '../util/csv.js';
import { syncDataAgent } from './agent.js';
import { entitlements } from './plans.js';
import { addActivity } from './store.js';

// Everything lands the same way: write the file to the lakehouse Files area in OneLake, then call
// Load Table to turn it into a Delta table. Scheduled or large loads belong in Fabric pipelines instead.

export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const MAX_WEB_BYTES = 25 * 1024 * 1024;
const RESERVED_PREFIX = 'crm_';

const FORMATS = {
  csv: { kind: 'csv', delimiter: ',' },
  txt: { kind: 'csv', delimiter: ',' },
  tsv: { kind: 'csv', delimiter: '\t' },
  parquet: { kind: 'parquet' },
  json: { kind: 'json' },
  xlsx: { kind: 'excel' },
  xls: { kind: 'excel' },
};

export function sanitizeTableName(name) {
  let cleaned = String(name || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 100);
  if (!cleaned || /^[0-9_]+$/.test(cleaned)) cleaned = `t_${cleaned || 'data'}`;
  return cleaned;
}

export function sanitizeFileStem(fileName) {
  const stem = String(fileName || 'upload').replace(/\.[^.]*$/, '');
  const cleaned = stem
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^\p{L}\p{N}_-]+/gu, '_')
    .replace(/_+/g, '_')
    .replace(/^[_-]+|[_-]+$/g, '')
    .slice(0, 80);
  return cleaned || 'upload';
}

export function detectFormat(fileName) {
  const extension = (/\.([a-z0-9]+)$/i.exec(fileName || '')?.[1] || '').toLowerCase();
  const format = FORMATS[extension];
  if (!format) throw new HttpError(415, `Unsupported file type${extension ? ` ".${extension}"` : ''}. Use CSV, TSV, Parquet, JSON or Excel.`);
  if (format.kind === 'excel') throw new HttpError(415, 'Convert Excel workbooks to CSV first. The web console does this in the browser, one table per sheet.');
  return format;
}

export async function ingestBytes({ fabric, tenant, bytes, fileName, table, mode = 'Overwrite', source = 'File upload', allowReserved = false }) {
  const { workspaceId, lakehouseId } = tenant.fabric;
  if (!workspaceId || !lakehouseId) throw new HttpError(409, 'This customer has no lakehouse yet. Wait for provisioning to finish.');
  if (!['Overwrite', 'Append'].includes(mode)) throw new HttpError(400, 'mode must be Overwrite or Append.');
  if (!bytes?.length) throw new HttpError(400, 'The file is empty.');
  const format = detectFormat(fileName);
  const tableName = sanitizeTableName(table || String(fileName).replace(/\.[^.]*$/, ''));
  if (!allowReserved && tableName.startsWith(RESERVED_PREFIX)) {
    throw new HttpError(400, `Table names that start with ${RESERVED_PREFIX} are reserved for the CRM app's data. Pick another name.`);
  }

  let payload = bytes;
  let rows = null;
  if (format.kind === 'json') {
    let data;
    try {
      data = JSON.parse(bytes.toString('utf8'));
    } catch {
      throw new HttpError(400, 'The file is not valid JSON.');
    }
    try {
      const converted = jsonToCsv(data);
      payload = Buffer.from(converted.csv, 'utf8');
      rows = converted.rows;
    } catch (error) {
      throw new HttpError(400, error.message);
    }
  }
  const extension = format.kind === 'parquet' ? 'parquet' : 'csv';
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const relativePath = `Files/landing/${tableName}/${stamp}_${sanitizeFileStem(fileName)}.${extension}`;

  await fabric.uploadFile(workspaceId, lakehouseId, relativePath, payload);
  await fabric.loadTable(workspaceId, lakehouseId, tableName, {
    relativePath,
    pathType: 'File',
    mode,
    recursive: false,
    formatOptions: extension === 'parquet' ? { format: 'Parquet' } : { format: 'Csv', header: true, delimiter: format.delimiter || ',' },
  });

  const record = { at: new Date().toISOString(), source, table: tableName, mode, file: relativePath, bytes: payload.length, rows };
  tenant.ingestions.unshift(record);
  if (tenant.ingestions.length > 50) tenant.ingestions.length = 50;
  addActivity(tenant, `Loaded ${source === 'File upload' ? fileName : source} into ${tableName} (${mode.toLowerCase()})`);
  return record;
}

// New tables should be queryable by the data agent straight away. A failure here doesn't fail the load.
export async function refreshAgentAfterLoad({ fabric, tenant }) {
  if (!entitlements(tenant).features.agent || !tenant.fabric.dataAgentId) return null;
  try {
    const result = await syncDataAgent({ fabric, tenant });
    if (result.added?.length) addActivity(tenant, `The data agent can now query ${result.added.join(', ')}`);
    return result;
  } catch (error) {
    addActivity(tenant, `Couldn't update the data agent: ${error.message}`, 'warning');
    return { error: error.message };
  }
}

export function isPublicAddress(address) {
  if (net.isIPv4(address)) {
    const [a, b] = address.split('.').map(Number);
    if (a === 0 || a === 10 || a === 127 || a >= 224) return false;
    if (a === 169 && b === 254) return false;
    if (a === 172 && b >= 16 && b <= 31) return false;
    if (a === 192 && b === 168) return false;
    if (a === 100 && b >= 64 && b <= 127) return false;
    return true;
  }
  if (net.isIPv6(address)) {
    const lower = address.toLowerCase();
    const mapped = /^::ffff:(\d+\.\d+\.\d+\.\d+)$/.exec(lower);
    if (mapped) return isPublicAddress(mapped[1]);
    if (lower === '::' || lower === '::1') return false;
    if (/^(fc|fd|fe8|fe9|fea|feb|ff)/.test(lower)) return false;
    return true;
  }
  return false;
}

async function assertPublicUrl(raw, lookup) {
  let url;
  try {
    url = new URL(raw);
  } catch {
    throw new HttpError(400, 'Enter a valid URL.');
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') throw new HttpError(400, 'Only http and https URLs are supported.');
  if (url.username || url.password) {
    throw new HttpError(400, "URLs with credentials aren't supported. Authenticated sources need a Fabric connection and a pipeline.");
  }
  const host = url.hostname.replace(/^\[|\]$/g, '');
  let addresses;
  if (net.isIP(host)) addresses = [{ address: host }];
  else {
    try {
      addresses = await lookup(host, { all: true });
    } catch {
      throw new HttpError(400, `Couldn't resolve ${host}.`);
    }
  }
  if (!addresses.length || addresses.some((a) => !isPublicAddress(a.address))) {
    throw new HttpError(400, "That address is private or local, so the platform won't fetch it.");
  }
  return url;
}

// Blocks private and local addresses (including after redirects) so a customer can't make the platform call internal services.
export async function fetchFromWeb(rawUrl, { fetchImpl = fetch, lookup = dns.lookup, maxBytes = MAX_WEB_BYTES, timeoutMs = 30_000 } = {}) {
  let url = await assertPublicUrl(rawUrl, lookup);
  for (let hop = 0; hop < 4; hop++) {
    const res = await fetchImpl(url, {
      redirect: 'manual',
      signal: AbortSignal.timeout(timeoutMs),
      headers: { accept: 'text/csv, application/json;q=0.9, */*;q=0.5', 'user-agent': 'fabric-saas-platform/0.1' },
    });
    const location = res.headers.get('location');
    if (res.status >= 300 && res.status < 400 && location) {
      await res.body?.cancel().catch(() => {});
      url = await assertPublicUrl(new URL(location, url).toString(), lookup);
      continue;
    }
    if (!res.ok) {
      await res.body?.cancel().catch(() => {});
      throw new HttpError(502, `The source returned HTTP ${res.status}.`);
    }
    const tooBig = () => new HttpError(413, `The source is larger than ${Math.round(maxBytes / (1024 * 1024))} MB. Use a Fabric pipeline for large loads.`);
    if (Number(res.headers.get('content-length') || 0) > maxBytes) {
      await res.body?.cancel().catch(() => {});
      throw tooBig();
    }
    const chunks = [];
    let size = 0;
    for await (const chunk of res.body) {
      size += chunk.length;
      if (size > maxBytes) throw tooBig();
      chunks.push(chunk);
    }
    return { bytes: Buffer.concat(chunks), contentType: res.headers.get('content-type') || '', finalUrl: url.toString() };
  }
  throw new HttpError(400, 'The URL redirected too many times.');
}

export async function importFromWeb({ fabric, tenant, url, table, mode, fetchOptions }) {
  const { bytes, contentType, finalUrl } = await fetchFromWeb(url, fetchOptions);
  const { pathname, host } = new URL(finalUrl);
  let extension = /\.(csv|tsv|json|parquet)$/i.exec(pathname)?.[1]?.toLowerCase();
  if (!extension) {
    if (contentType.includes('json')) extension = 'json';
    else if (contentType.includes('csv') || contentType.includes('text/plain')) extension = 'csv';
    else if (contentType.includes('parquet')) extension = 'parquet';
  }
  if (!extension) throw new HttpError(415, `Can't tell the format of ${contentType || 'the response'}. Use a URL that returns CSV, JSON or Parquet.`);
  const stem = pathname.split('/').filter(Boolean).pop()?.replace(/\.[^.]*$/, '') || 'web_data';
  return ingestBytes({ fabric, tenant, bytes, fileName: `${stem}.${extension}`, table: table || stem, mode, source: `web (${host})` });
}

// Stand-in for the SaaS app's own data. Deterministic per tenant, so reloading gives the same rows.
export function sampleCrmData(seedText) {
  let seed = [...seedText].reduce((hash, char) => Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0, 2166136261);
  const random = () => {
    seed = (seed + 0x6d2b79f5) >>> 0;
    let t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const pick = (list) => list[Math.floor(random() * list.length)];
  const day = (offsetMax) => new Date(Date.UTC(2026, 0, 1) + Math.floor(random() * offsetMax) * 86_400_000).toISOString().slice(0, 10);
  const id = (prefix, n) => `${prefix}${String(n).padStart(4, '0')}`;

  const accounts = Array.from({ length: 60 }, (_, i) => ({
    account_id: id('A', i + 1),
    name: `${pick(['North', 'Blue', 'Summit', 'Harbor', 'Granite', 'Cedar', 'Bright', 'Iron', 'Silver', 'Prairie'])} ${pick(['Labs', 'Partners', 'Health', 'Foods', 'Logistics', 'Systems', 'Clinics', 'Supply', 'Works', 'Group'])}`,
    industry: pick(['Healthcare', 'Manufacturing', 'Retail', 'Financial services', 'Education', 'Logistics', 'Software']),
    country: pick(['United States', 'Canada', 'United Kingdom', 'Germany', 'Australia', 'India']),
    annual_revenue_usd: Math.round(500_000 + random() * 49_500_000),
    created_date: day(180),
  }));
  const owners = ['Avery Chen', 'Jordan Patel', 'Sam Rivera', 'Taylor Brooks', 'Morgan Lee'];
  const opportunities = Array.from({ length: 240 }, (_, i) => ({
    opportunity_id: id('O', i + 1),
    account_id: pick(accounts).account_id,
    stage: pick(['Prospecting', 'Qualified', 'Proposal', 'Negotiation', 'Closed won', 'Closed lost']),
    owner: pick(owners),
    amount_usd: Math.round(5_000 + random() * 245_000),
    close_date: day(365),
  }));
  const activities = Array.from({ length: 600 }, (_, i) => ({
    activity_id: id('E', i + 1),
    opportunity_id: pick(opportunities).opportunity_id,
    type: pick(['Call', 'Email', 'Meeting', 'Demo']),
    owner: pick(owners),
    activity_date: day(270),
    duration_minutes: 5 + Math.floor(random() * 85),
  }));
  return { crm_accounts: accounts, crm_opportunities: opportunities, crm_activities: activities };
}

export async function syncAppData({ fabric, tenant }) {
  const results = [];
  for (const [table, rows] of Object.entries(sampleCrmData(tenant.id))) {
    const csv = toCsv(rows, Object.keys(rows[0]));
    const record = await ingestBytes({ fabric, tenant, bytes: Buffer.from(csv, 'utf8'), fileName: `${table}.csv`, table, mode: 'Overwrite', source: 'CRM app', allowReserved: true });
    record.rows = rows.length;
    results.push(record);
  }
  return results;
}
