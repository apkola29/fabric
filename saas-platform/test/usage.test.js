import assert from 'node:assert/strict';
import { test } from 'node:test';
import { USAGE_LOG_SIZE, recordUsage, summarizeUsage, usageEntry } from '../src/platform/usage.js';
import { makePlatform } from './support.js';

// Report usage, as in Microsoft's App-Owns-Data Starter Kit: the app's own log of who opened and saved which reports,
// and how fast they loaded and rendered. Power BI's activity log names the service principal, not the person.

const ID = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

test('usage entries are checked: known events, IDs, bounded timings, and saves only by people allowed to make them', () => {
  const who = { email: 'ana@fabrikam.com', scope: 'Texas', rights: { edit: false, create: false }, now: () => Date.parse('2026-10-06T12:00:00Z') };
  const view = usageEntry({ event: 'view', reportId: ID(1).toUpperCase(), reportName: '  Sales   overview ', loadMs: 812, renderMs: 2310, correlationId: ID(2), tokenId: ID(3), email: 'mallory@contoso.com' }, who);
  assert.deepEqual(view, { at: '2026-10-06T12:00:00.000Z', email: 'ana@fabrikam.com', scope: 'Texas', event: 'view', reportId: ID(1), reportName: 'Sales overview', loadMs: 812, renderMs: 2310, correlationId: ID(2), tokenId: ID(3) }, 'who it was comes from the session, never the request');
  for (const bad of [
    { event: 'delete', reportId: ID(1) },
    { event: 'view' },
    { event: 'view', reportId: 'x' },
    { event: 'view', reportId: ID(1), loadMs: -1 },
    { event: 'view', reportId: ID(1), renderMs: 1.5 },
    { event: 'view', reportId: ID(1), renderMs: 11 * 60_000 },
    { event: 'view', reportId: ID(1), correlationId: '<script>' },
  ]) {
    assert.throws(() => usageEntry(bad, who), (e) => e.status === 400, JSON.stringify(bad));
  }
  assert.throws(() => usageEntry({ event: 'save', reportId: ID(1) }, who), (e) => e.status === 403, 'saving needs the edit permission');
  assert.throws(() => usageEntry({ event: 'copy', reportId: ID(4) }, { ...who, rights: { edit: true, create: false } }), (e) => e.status === 403, 'a copy needs the create permission');
  assert.equal(usageEntry({ event: 'copy', reportId: ID(4), originalReportId: ID(1) }, { ...who, rights: { edit: true, create: true } }).originalReportId, ID(1));
});

test('the usage log is bounded, newest first, and summarized per report with median timings', () => {
  const tenant = {};
  for (let i = 0; i < USAGE_LOG_SIZE + 5; i += 1) recordUsage(tenant, { event: 'view', reportId: ID(1), email: `p${i % 3}@fabrikam.com`, loadMs: i, renderMs: 2 * i });
  assert.equal(tenant.reportUsage.length, USAGE_LOG_SIZE);
  assert.equal(tenant.reportUsage[0].loadMs, USAGE_LOG_SIZE + 4);

  const summary = summarizeUsage([
    { event: 'view', reportId: ID(1), reportName: 'Sales overview', email: 'a@x.com', loadMs: 800, renderMs: 2000 },
    { event: 'view', reportId: ID(1), reportName: 'Sales overview', email: 'b@x.com', loadMs: 1000, renderMs: 3000 },
    { event: 'view', reportId: ID(1), reportName: 'Sales overview', email: 'a@x.com', loadMs: 5000, renderMs: 9000 },
    { event: 'save', reportId: ID(2), reportName: 'Mine', email: 'a@x.com' },
  ]);
  assert.deepEqual(summary, [
    { reportId: ID(1), reportName: 'Sales overview', views: 3, saves: 0, people: 2, medianLoadMs: 1000, medianRenderMs: 3000 },
    { reportId: ID(2), reportName: 'Mine', views: 0, saves: 1, people: 1, medianLoadMs: null, medianRenderMs: null },
  ]);
});

test("the browser reports usage for the signed-in person only; operators read it, and reading it is audited", async () => {
  const { addCustomer, signIn, admin } = makePlatform();
  const fabrikamId = await addCustomer('Fabrikam', 'enterprise', 'fabrikam.com');
  const ana = await signIn('ana@fabrikam.com');
  const { reports } = (await ana({ url: '/api/me/reports' })).json();
  const embed = (await ana({ method: 'POST', url: '/api/me/embed', body: { reportId: reports[0].id } })).json();
  assert.match(embed.tokenId, GUID, "the embed token's ID comes with it");

  const body = { event: 'view', reportId: reports[0].id, reportName: reports[0].name, loadMs: 900, renderMs: 2400, correlationId: ID(9), tokenId: embed.tokenId, email: 'someone@contoso.com' };
  const posted = await ana({ method: 'POST', url: '/api/me/reports/usage', body });
  assert.equal(posted.status, 202, posted.text);
  assert.equal((await ana({ method: 'POST', url: '/api/me/reports/usage', body: { event: 'view', reportId: 'nope' } })).status, 400);

  const usage = (await admin({ url: `/api/admin/tenants/${fabrikamId}/usage` })).json();
  assert.deepEqual(usage.entries.map((u) => [u.email, u.event, u.reportName, u.loadMs, u.renderMs, u.tokenId]), [['ana@fabrikam.com', 'view', 'Sales overview', 900, 2400, embed.tokenId]]);
  assert.deepEqual([usage.reports[0].views, usage.reports[0].people, usage.reports[0].medianRenderMs], [1, 1, 2400]);
  const activity = (await admin({ url: `/api/admin/tenants/${fabrikamId}` })).json().activity.map((a) => a.message);
  assert.ok(activity.some((m) => m.includes('viewed report usage')), 'looking at usage is recorded');
});
