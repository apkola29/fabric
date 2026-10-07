import assert from 'node:assert/strict';
import { test } from 'node:test';
import { decodePayload } from '../src/util/definition.js';
import { buildSemanticModelAgentDefinition } from '../src/platform/agent.js';
import { ANSWER_LOG_CHARS, createAssistant, loggedAnswer, safeImages } from '../src/platform/assistant.js';

const PNG = Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.alloc(24, 1)]).toString('base64');
const SVG = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>').toString('base64');
const ROWS = { Texas: 2_229_000, Georgia: 2_828_500, 'New Mexico': 455_000 };

// A CRM whose quick answers follow the territories asked for, and a data agent that records who called it.
function fixtures({ agent = async () => ({ answer: 'Georgia leads with $2.8M of pipeline.', images: [PNG, SVG, 'not base64 at all'].map((data) => ({ mimeType: 'image/png', data })) }), quickError = null } = {}) {
  const calls = { agent: 0, scopes: [] };
  const crm = {
    forTenant: async () => ({
      scoped: (territories) => ({
        quickAnswer: async () => {
          calls.scopes.push(territories);
          if (quickError) throw quickError;
          const rows = Object.entries(ROWS)
            .filter(([state]) => territories === null || territories.includes(state))
            .map(([label, value]) => ({ label, value, display: `$${value}` }));
          return { answer: 'Pipeline Value by State.', rows, measure: 'Pipeline Value', dimension: 'State', chart: 'bar' };
        },
      }),
    }),
  };
  const identities = {
    fabricFor: async () => ({
      askDataAgent: async (...args) => {
        calls.agent++;
        return agent(...args);
      },
    }),
  };
  const store = { save: async () => {} };
  const tenant = { id: 't1', name: 'Fabrikam', plan: 'enterprise', addons: [], fabric: { workspaceId: 'ws', dataAgentId: 'agent' }, activity: [] };
  return { assistant: createAssistant({ store, identities, crm }), tenant, calls };
}

test("managers get the agent's answer with a chart of every territory, and only real raster images", async () => {
  const { assistant, tenant, calls } = fixtures();
  const result = await assistant.ask(tenant, 'pipeline by state', { email: 'leah@fabrikam.com', territories: null });
  assert.equal(result.source, 'assistant');
  assert.equal(result.answer, 'Georgia leads with $2.8M of pipeline.');
  assert.deepEqual(result.rows.map((r) => r.label), ['Texas', 'Georgia', 'New Mexico']);
  assert.deepEqual([result.chart, result.chartSource], ['bar', 'quick']);
  assert.deepEqual(result.images, [{ mimeType: 'image/png', data: PNG }], 'the SVG and the garbage are dropped');
  assert.equal(calls.agent, 1);
  const [logged] = tenant.questions;
  assert.deepEqual([logged.email, logged.scope, logged.question, logged.answeredBy, logged.agent, logged.chart, logged.images], ['leah@fabrikam.com', 'All territories', 'pipeline by state', 'data agent', 'answered', true, 1]);
  assert.equal(logged.answer, 'Georgia leads with $2.8M of pipeline.', "the agent's answer is kept with the question");
});

test('long answers are kept in part, so the log stays bounded', async () => {
  const long = 'x'.repeat(ANSWER_LOG_CHARS + 50);
  const { assistant, tenant } = fixtures({ agent: async () => ({ answer: long }) });
  await assistant.ask(tenant, 'pipeline by state', { email: 'leah@fabrikam.com', territories: null });
  const [logged] = tenant.questions;
  assert.equal(logged.answer.length, ANSWER_LOG_CHARS + 1);
  assert.equal(logged.answerTruncated, true);
  assert.deepEqual(loggedAnswer('short'), { answer: 'short' });
});

test('reps never reach the agent, and their charts only cover their territories', async () => {
  const { assistant, tenant, calls } = fixtures();
  const result = await assistant.ask(tenant, 'pipeline by state', { email: 'drew@fabrikam.com', territories: ['Texas', 'Georgia'] });
  assert.equal(calls.agent, 0);
  assert.equal(result.source, 'quick');
  assert.deepEqual(result.rows.map((r) => r.label), ['Texas', 'Georgia']);
  assert.equal(result.chart, 'bar');
  assert.equal(result.images, undefined);
  assert.deepEqual(calls.scopes, [['Texas', 'Georgia']]);
  assert.deepEqual([tenant.questions[0].scope, tenant.questions[0].answeredBy, tenant.questions[0].agent], ['Texas, Georgia', 'quick answer', 'territories limited']);
  await assert.rejects(assistant.ask(tenant, 'pipeline', { email: 'x@fabrikam.com' }), /territories/, 'the scope is never optional');
});

test('when the agent fails, managers get the quick answer and chart, and the agent rests for a while', async () => {
  const { assistant, tenant, calls } = fixtures({ agent: async () => Promise.reject(new Error('FT1 SKU Not Supported')) });
  const first = await assistant.ask(tenant, 'pipeline by state', { email: 'leah@fabrikam.com', territories: null });
  assert.deepEqual([first.source, first.chart, first.rows.length], ['quick', 'bar', 3]);
  assert.match(tenant.activity[0].message, /FT1 SKU Not Supported/);
  await assistant.ask(tenant, 'pipeline by state', { email: 'leah@fabrikam.com', territories: null });
  assert.equal(calls.agent, 1, 'no second call during the cool-down');
  assert.deepEqual(tenant.questions.map((q) => [q.answeredBy, q.agent]), [['quick answer', 'paused'], ['quick answer', 'failed']]);
  assert.match(tenant.questions[1].error, /FT1 SKU Not Supported/, 'the log says why the agent was not used');
});

test('when nothing can answer, the question fails and the log says why both ways failed', async () => {
  const { assistant, tenant } = fixtures({
    agent: async () => Promise.reject(new Error('FT1 SKU Not Supported')),
    quickError: Object.assign(new Error('Failed to connect to the CRM database in 30000ms'), { name: 'ConnectionError', code: 'ETIMEOUT' }),
  });
  await assert.rejects(assistant.ask(tenant, 'pipeline by state', { email: 'leah@fabrikam.com', territories: null }), /Failed to connect/);
  const [logged] = tenant.questions;
  assert.deepEqual([logged.answeredBy, logged.agent, logged.answer], ['nobody', 'failed', ''], 'an empty answer, not a missing one: answers are being kept');
  assert.match(logged.error, /FT1 SKU Not Supported/);
  assert.match(logged.quickError, /Failed to connect/);
});

test('images: PNG, JPEG and WebP only, at most four, nothing large', () => {
  const jpeg = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 1, 2]).toString('base64');
  const webp = Buffer.concat([Buffer.from('RIFF'), Buffer.alloc(4), Buffer.from('WEBPVP8 ')]).toString('base64');
  assert.deepEqual(safeImages([{ data: jpeg }, { data: webp }]).map((i) => i.mimeType), ['image/jpeg', 'image/webp']);
  assert.equal(safeImages(Array.from({ length: 6 }, () => ({ data: PNG }))).length, 4);
  assert.equal(safeImages([{ data: Buffer.concat([Buffer.from(PNG, 'base64'), Buffer.alloc(2 * 1024 * 1024)]).toString('base64') }]).length, 0);
  assert.deepEqual(safeImages([{ data: SVG, mimeType: 'image/svg+xml' }, { data: Buffer.from('<html>').toString('base64'), mimeType: 'image/png' }]), []);
  assert.deepEqual(safeImages(undefined), []);
});

test("the agent's code interpreter is off unless asked for, and then it's in both stages", () => {
  const args = { workspaceId: 'ws', semanticModelId: 'm', semanticModelName: 'Platform app Insights - Assistant', tables: [], instructions: 'x', description: 'y' };
  const stages = (definition) => definition.parts.filter((p) => p.path.endsWith('stage_config.json')).map((p) => JSON.parse(decodePayload(p.payload)));
  assert.ok(stages(buildSemanticModelAgentDefinition(args)).every((s) => s.experimental === undefined));
  const on = stages(buildSemanticModelAgentDefinition({ ...args, codeInterpreter: true }));
  assert.equal(on.length, 2);
  assert.ok(on.every((s) => s.experimental?.codeInterpreterEnabled === true));
});
