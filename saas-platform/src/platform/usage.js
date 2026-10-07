import { HttpError } from '../http/router.js';

// Report usage: what people open and save in the embedded reports, and how fast the reports load and render.
//
// As in Microsoft's App-Owns-Data Starter Kit, the app keeps its own log. Power BI's activity log records the service
// principal that created the embed token, not the person, so it can't say who looked at what. Each entry keeps the
// embed token's ID and the report's correlation ID, which tie it to Power BI's own records when support needs them.
// The browser reports the timings; who and which customer always come from the session.

export const USAGE_LOG_SIZE = 500;
export const USAGE_EVENTS = Object.freeze({ view: 'Viewed', save: 'Saved', copy: 'Saved a copy of', create: 'Created' });
// Which report permission each event needs (users.js): saving changes needs edit; a copy or a new report needs create.
const NEEDS = { save: 'edit', copy: 'create', create: 'create' };
const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_MS = 10 * 60_000;

function optionalGuid(value, name) {
  if (value === undefined || value === null || value === '') return null;
  if (typeof value !== 'string' || !GUID.test(value)) throw new HttpError(400, `${name} must be an ID.`);
  return value.toLowerCase();
}

function optionalMs(value, name) {
  if (value === undefined || value === null) return null;
  if (!Number.isInteger(value) || value < 0 || value > MAX_MS) throw new HttpError(400, `${name} must be a whole number of milliseconds, at most ${MAX_MS}.`);
  return value;
}

// A log entry from what the browser sent, checked. `rights` are the person's report permissions.
export function usageEntry(body, { email, scope, rights, now = () => Date.now() }) {
  const event = String(body?.event || '');
  if (!Object.hasOwn(USAGE_EVENTS, event)) throw new HttpError(400, `event must be one of ${Object.keys(USAGE_EVENTS).join(', ')}.`);
  if (NEEDS[event] && !rights?.[NEEDS[event]]) throw new HttpError(403, "That isn't something you can do with reports.");
  const reportId = optionalGuid(body.reportId, 'reportId');
  if (!reportId) throw new HttpError(400, 'reportId is required.');
  return {
    at: new Date(now()).toISOString(),
    email,
    scope,
    event,
    reportId,
    reportName: String(body.reportName || '').replace(/\s+/g, ' ').trim().slice(0, 120),
    ...(event === 'copy' ? { originalReportId: optionalGuid(body.originalReportId, 'originalReportId') } : {}),
    loadMs: optionalMs(body.loadMs, 'loadMs'),
    renderMs: optionalMs(body.renderMs, 'renderMs'),
    correlationId: optionalGuid(body.correlationId, 'correlationId'),
    tokenId: optionalGuid(body.tokenId, 'tokenId'),
  };
}

export function recordUsage(tenant, entry) {
  tenant.reportUsage = [entry, ...(tenant.reportUsage || [])].slice(0, USAGE_LOG_SIZE);
}

const median = (values) => {
  const sorted = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : Math.round((sorted[middle - 1] + sorted[middle]) / 2);
};

// Per report: views, distinct people, and median load and render times; slow reports stand out here.
export function summarizeUsage(entries = []) {
  const reports = new Map();
  for (const e of entries) {
    const r = reports.get(e.reportId) || { reportId: e.reportId, reportName: e.reportName, views: 0, saves: 0, people: new Set(), load: [], render: [] };
    if (!r.reportName && e.reportName) r.reportName = e.reportName;
    if (e.event === 'view') {
      r.views += 1;
      r.load.push(e.loadMs);
      r.render.push(e.renderMs);
    } else r.saves += 1;
    r.people.add(e.email);
    reports.set(e.reportId, r);
  }
  return [...reports.values()]
    .map((r) => ({ reportId: r.reportId, reportName: r.reportName, views: r.views, saves: r.saves, people: r.people.size, medianLoadMs: median(r.load), medianRenderMs: median(r.render) }))
    .sort((a, b) => b.views - a.views);
}
