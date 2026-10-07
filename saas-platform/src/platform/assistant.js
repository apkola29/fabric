import { QUICK_EXAMPLES } from '../crm/workload.js';
import { rasterType } from './branding.js';
import { entitlements } from './plans.js';
import { addActivity } from './store.js';

// The assistant on the report page. With the Enterprise edition it asks the customer's data agent, which reads the
// HiCRM Insights semantic model. When the agent can't answer (no agent yet, or a capacity that doesn't run data agents,
// such as a trial), it falls back to quick answers computed from the CRM database with the same business rules.
//
// The data agent runs as the customer's service account, which sees every territory, so only people who see every
// territory (managers) get it. People limited to some territories always get quick answers, scoped to those territories.
//
// Charts follow the same rule: a breakdown ("pipeline by stage", "won revenue by month") comes with its rows and a
// chart type, computed from the CRM data the person may see. For managers that runs next to the agent, so the agent's
// answer comes with a chart of the same question. Charts the agent draws itself (its code interpreter tool) are shown
// too, as checked PNG, JPEG or WebP images.

const AGENT_COOL_DOWN_MS = 15 * 60 * 1000;
const MAX_IMAGES = 4;
const MAX_IMAGE_BYTES = 2 * 1024 * 1024;
// The question log keeps each customer's most recent questions and answers, so the platform team can see what people
// ask, what they were told, who answered (the data agent or a quick answer) and why the agent wasn't used when it wasn't.
export const QUESTION_LOG_SIZE = 200;
export const ANSWER_LOG_CHARS = 4000;

// An answer as it goes into the log: the text, cut to a bounded size. Charts are noted, not stored.
export const loggedAnswer = (text) => {
  const answer = String(text || '');
  return answer.length > ANSWER_LOG_CHARS ? { answer: `${answer.slice(0, ANSWER_LOG_CHARS)}…`, answerTruncated: true } : { answer };
};

// Only real raster images go to the browser: never SVG or HTML, nothing large.
export function safeImages(images) {
  return (images || []).slice(0, MAX_IMAGES).flatMap((image) => {
    const bytes = Buffer.from(String(image?.data || ''), 'base64');
    if (!bytes.length || bytes.length > MAX_IMAGE_BYTES) return [];
    const mimeType = rasterType(bytes);
    return mimeType ? [{ mimeType, data: bytes.toString('base64') }] : [];
  });
}

// The chart part of a quick answer: only breakdowns with more than one row make a chart.
const chartOf = (quick) =>
  quick?.chart && quick.rows?.length > 1 ? { rows: quick.rows, chart: quick.chart, measure: quick.measure, dimension: quick.dimension, chartSource: 'quick' } : {};

export function createAssistant({ store, identities, crm, mock = false }) {
  const pausedUntil = new Map();

  // { reply } when the agent answered; otherwise { status } saying why not, for the question log.
  async function askAgent(tenant, question, email) {
    const { features } = entitlements(tenant);
    if (mock) return { status: 'demo' };
    if (!features.agent) return { status: 'not in edition' };
    if (!tenant.fabric?.dataAgentId) return { status: 'no agent yet' };
    if (pausedUntil.get(tenant.id) > Date.now()) return { status: 'paused' };
    try {
      const client = await identities.fabricFor(tenant);
      const result = await client.askDataAgent(tenant.fabric.workspaceId, tenant.fabric.dataAgentId, question);
      if (!result?.answer) return { status: 'empty answer' };
      const images = safeImages(result.images);
      return { status: 'answered', reply: { answer: result.answer, source: 'assistant', ...(images.length ? { images } : {}) } };
    } catch (error) {
      // Don't retry a failing agent on every question; the platform team sees why in the back office.
      pausedUntil.set(tenant.id, Date.now() + AGENT_COOL_DOWN_MS);
      addActivity(tenant, `The data agent didn't answer ${email}, so quick answers are used for 15 minutes: ${error.message}`, 'warning');
      return { status: 'failed', error: String(error.message || error).slice(0, 300) };
    }
  }

  async function log(tenant, entry) {
    tenant.questions = [{ at: new Date().toISOString(), ...entry }, ...(tenant.questions || [])].slice(0, QUESTION_LOG_SIZE);
    await store.save(tenant);
  }

  return {
    // `territories`: null for every territory, or the list the person may see. Required, so a caller can't forget it.
    async ask(tenant, question, { email, territories } = {}) {
      if (territories !== null && !Array.isArray(territories)) throw new Error('The assistant needs the territories the person may see.');
      const started = Date.now();
      const quickAnswer = (async () => (await crm.forTenant(tenant)).scoped(territories).quickAnswer(question))().then(
        (value) => ({ value }),
        (error) => ({ error }),
      );
      // People limited to some territories never reach the agent: it runs as the service account and sees everything.
      const agent = territories === null ? await askAgent(tenant, question, email) : { status: 'territories limited' };
      const quick = await quickAnswer;
      let result;
      if (agent.reply) result = { ...agent.reply, ...chartOf(quick.value) };
      else if (quick.value) result = { ...quick.value, source: 'quick' };
      else if (!quick.error) {
        result = {
          answer: 'I can answer questions about pipeline, revenue, win rate, deals, accounts, contacts and activities. Try one of these:',
          suggestions: QUICK_EXAMPLES,
          source: 'quick',
        };
      }
      await log(tenant, {
        email,
        scope: territories === null ? 'All territories' : territories.join(', '),
        question: String(question).slice(0, 500),
        answeredBy: agent.reply ? 'data agent' : result?.rows?.length ? 'quick answer' : 'nobody',
        agent: agent.status,
        ...(agent.error ? { error: agent.error } : {}),
        ...(quick.error ? { quickError: String(quick.error.message || quick.error).slice(0, 300) } : {}),
        ...loggedAnswer(result?.answer),
        chart: Boolean(result?.chart && result.rows?.length > 1),
        images: result?.images?.length || 0,
        ms: Date.now() - started,
      });
      if (!result) throw quick.error;
      return result;
    },
    resume(tenantId) {
      pausedUntil.delete(tenantId);
    },
  };
}
