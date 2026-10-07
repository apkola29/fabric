import assert from 'node:assert/strict';
import { test } from 'node:test';
import { makePlatform } from './support.js';

test('customers see the standard report, view only, until report authoring is turned on', async () => {
  const platform = makePlatform({ env: { REPORT_AUTHORING: '' }, template: false });
  const id = await platform.addCustomer('Fabrikam', 'enterprise', 'fabrikam.com');
  const tenant = platform.store.get(id);
  // A report someone made in the workspace (for example while testing) isn't one of the standard reports.
  await platform.fabric.createItem(tenant.fabric.workspaceId, { displayName: 'Pipeline check', type: 'Report' });
  const ana = await platform.signIn('ana@fabrikam.com');

  assert.equal((await ana({ url: '/api/me' })).json().features.authoring, false, 'the edition includes authoring, but it is the next phase');
  const listing = (await ana({ url: '/api/me/reports' })).json();
  assert.deepEqual(listing.reports.map((r) => r.name), ['Sales overview']);
  assert.deepEqual(listing.models, [], 'nothing to build new reports on');

  const [standard] = listing.reports;
  const view = await ana({ method: 'POST', url: '/api/me/embed', body: { mode: 'view', reportId: standard.id } });
  assert.equal(view.status, 200, view.text);
  assert.equal(view.json().mode, 'view');
  const { request, principal } = platform.fabric.embedTokens().at(-1);
  assert.deepEqual(request.reports, [{ id: standard.id }], 'one report, no allowEdit');
  assert.equal(request.targetWorkspaces, undefined, 'no workspace to save into');
  assert.equal(principal, tenant.identity.objectId, "issued by the customer's own service account");

  const other = (await platform.fabric.pbiListReports(tenant.fabric.workspaceId)).find((r) => r.name === 'Pipeline check');
  assert.equal((await ana({ method: 'POST', url: '/api/me/embed', body: { mode: 'view', reportId: other.id } })).status, 404, "another report can't be opened by ID");
  assert.equal((await ana({ method: 'POST', url: '/api/me/embed', body: { mode: 'edit', reportId: standard.id } })).status, 403);
  assert.equal((await ana({ method: 'POST', url: '/api/me/embed', body: { mode: 'create', datasetId: tenant.fabric.semanticModelId } })).status, 403);
  assert.equal((await ana({ method: 'POST', url: '/api/me/reports/describe', body: { text: 'pipeline by stage' } })).status, 403);

  // Template reports count as standard too.
  const templated = makePlatform({ env: { REPORT_AUTHORING: '' } });
  await templated.addCustomer('Contoso', 'standard', 'contoso.com');
  const maria = await templated.signIn('maria@contoso.com');
  const names = (await maria({ url: '/api/me/reports' })).json().reports.map((r) => r.name);
  assert.ok(names.length > 0 && !names.includes('Pipeline check'), `the template's reports: ${names.join(', ')}`);
});

test('the question log records who asked what, what they were told, and who answered; reading it is audited', async () => {
  const ADMIN_KEY = 'k'.repeat(32);
  const platform = makePlatform({ env: { ADMIN_KEY } });
  await platform.operatorSignIn(ADMIN_KEY);
  const id = await platform.addCustomer('Fabrikam', 'enterprise', 'fabrikam.com');
  const ana = await platform.signIn('ana@fabrikam.com');
  assert.equal((await ana({ method: 'POST', url: '/api/me/ask', body: { question: 'pipeline by stage' } })).status, 200);
  assert.equal((await ana({ method: 'POST', url: '/api/me/ask', body: { question: 'what is the meaning of life' } })).status, 200);

  const { questions } = (await platform.admin({ url: `/api/admin/tenants/${id}/questions` })).json();
  assert.deepEqual(
    questions.map((q) => [q.email, q.scope, q.question, q.answeredBy, q.chart]),
    [
      ['ana@fabrikam.com', 'All territories', 'what is the meaning of life', 'nobody', false],
      ['ana@fabrikam.com', 'All territories', 'pipeline by stage', 'quick answer', true],
    ],
  );
  assert.equal(questions[1].agent, 'demo', 'demo mode never calls a data agent, and the log says so');
  assert.match(questions[1].answer, /Pipeline Value by Stage/, 'the answer is kept with the question');
  assert.match(questions[0].answer, /I can answer questions about/, 'so is the reply to a question nobody could answer');
  const detail = (await platform.admin({ url: `/api/admin/tenants/${id}` })).json();
  assert.match(detail.activity[0].message, /viewed the questions people asked the assistant/);
  assert.match(detail.assistant.mcpUrl, /\/mcp\/workspaces\/[^/]+\/dataagents\/[^/]+\/agent$/, 'the MCP endpoint the app calls');
  assert.equal(detail.assistant.questions, 2);
});
