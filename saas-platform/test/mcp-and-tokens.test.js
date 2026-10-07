import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createTokenProvider } from '../src/auth/tokens.js';
import { askDataAgentOverMcp } from '../src/fabric/mcp.js';
import { json, scriptedFetch } from './helpers.js';

const sse = (...messages) =>
  new Response(messages.map((m) => `event: message\r\ndata: ${JSON.stringify(m)}\r\n\r\n`).join(''), { status: 200, headers: { 'content-type': 'text/event-stream' } });

function mcpServer({ answer = 'There are 240 opportunities.', isError = false, initError = null, extra = [] } = {}) {
  const seen = [];
  const fetchImpl = async (url, init) => {
    const headers = init.headers;
    if (init.method === 'DELETE') {
      seen.push({ method: 'DELETE', session: headers['mcp-session-id'] });
      return new Response(null, { status: 200 });
    }
    const message = JSON.parse(init.body);
    seen.push({ method: message.method, session: headers['mcp-session-id'], version: headers['mcp-protocol-version'], auth: headers.authorization, accept: headers.accept });
    if (message.method === 'initialize') {
      if (initError) return json(200, { jsonrpc: '2.0', id: message.id, error: initError });
      return json(200, { jsonrpc: '2.0', id: message.id, result: { protocolVersion: '2025-03-26', capabilities: { tools: {} }, serverInfo: { name: 'agent' } } }, { 'mcp-session-id': 'sess-1' });
    }
    if (message.method === 'notifications/initialized') return new Response(null, { status: 202 });
    if (message.method === 'tools/list') {
      return sse({ jsonrpc: '2.0', id: message.id, result: { tools: [{ name: 'Sales_agent', inputSchema: { type: 'object', properties: { userQuestion: { type: 'string' } } } }] } });
    }
    if (message.method === 'tools/call') {
      assert.equal(message.params.name, 'Sales_agent');
      assert.equal(message.params.arguments.userQuestion, 'How many opportunities?');
      return sse(
        { jsonrpc: '2.0', method: 'notifications/progress', params: { progress: 1 } },
        { jsonrpc: '2.0', id: message.id, result: { content: [{ type: 'text', text: answer }, ...extra], isError } },
      );
    }
    throw new Error(`unexpected ${message.method}`);
  };
  return { fetchImpl, seen };
}

test('asks a data agent over MCP: handshake, tool discovery, SSE answer', async () => {
  const { fetchImpl, seen } = mcpServer();
  const result = await askDataAgentOverMcp({ url: 'https://fabric.test/v1/mcp/workspaces/ws/dataagents/a/agent', getToken: async () => 'tok', question: 'How many opportunities?', fetchImpl });
  assert.deepEqual(result, { answer: 'There are 240 opportunities.', tool: 'Sales_agent' });
  assert.deepEqual(seen.map((s) => s.method), ['initialize', 'notifications/initialized', 'tools/list', 'tools/call', 'DELETE']);
  assert.equal(seen[0].session, undefined);
  assert.equal(seen[2].session, 'sess-1');
  assert.equal(seen[2].version, '2025-03-26');
  assert.equal(seen[0].auth, 'Bearer tok');
  assert.match(seen[0].accept, /text\/event-stream/);
});

test('surfaces tool errors and initialize errors', async () => {
  const drawn = mcpServer({ answer: 'Here is the trend.', extra: [{ type: 'image', data: 'iVBORw0KGgo=', mimeType: 'image/png' }, { type: 'resource', resource: {} }] });
  const withChart = await askDataAgentOverMcp({ url: 'https://x', getToken: async () => 't', question: 'How many opportunities?', fetchImpl: drawn.fetchImpl });
  assert.deepEqual(withChart.images, [{ mimeType: 'image/png', data: 'iVBORw0KGgo=' }], "a chart the agent drew comes back with its answer");
  const failing = mcpServer({ answer: 'Table not found', isError: true });
  await assert.rejects(askDataAgentOverMcp({ url: 'https://x', getToken: async () => 't', question: 'How many opportunities?', fetchImpl: failing.fetchImpl }), /Table not found/);
  const trial = mcpServer({ initError: { code: -32003, message: 'FT1 SKU Not Supported' } });
  await assert.rejects(askDataAgentOverMcp({ url: 'https://x', getToken: async () => 't', question: 'q', fetchImpl: trial.fetchImpl }), /-32003: FT1 SKU Not Supported/);
});

test('service principal tokens are cached per scope and errors never echo the secret', async () => {
  const config = { authMode: 'sp', tenantId: 'contoso.onmicrosoft.com', clientId: 'app', clientSecret: 's3cr3t-value', endpoints: { login: 'https://login.test' } };
  const { fetchImpl, calls } = scriptedFetch([{ match: '/oauth2/v2.0/token', respond: json(200, { access_token: 'abc', expires_in: 3600 }) }]);
  const tokens = createTokenProvider(config, { fetchImpl });
  const [a, b] = await Promise.all([tokens.getToken('scope-1'), tokens.getToken('scope-1')]);
  assert.equal(a, 'abc');
  assert.equal(b, 'abc');
  await tokens.getToken('scope-1');
  assert.equal(calls.length, 1, 'concurrent and repeated requests share one token call');
  const form = new URLSearchParams(String(calls[0].body));
  assert.equal(form.get('grant_type'), 'client_credentials');
  assert.equal(form.get('scope'), 'scope-1');

  const failing = scriptedFetch([{ match: '/token', respond: json(401, { error: 'invalid_client', error_description: 'AADSTS7000215: Invalid client secret provided.\r\nTrace ID: x' }) }]);
  const bad = createTokenProvider(config, { fetchImpl: failing.fetchImpl, retryDelaysMs: [0, 0, 0] });
  await assert.rejects(bad.getToken('scope-1'), (error) => {
    assert.match(error.message, /AADSTS7000215/);
    assert.doesNotMatch(error.message, /s3cr3t-value/);
    assert.doesNotMatch(error.message, /Trace ID/);
    return true;
  });
  assert.equal(failing.calls.length, 4, 'a secret Entra ID may not have replicated yet is tried 3 more times, then given up');
});

test('a new credential that some Entra ID servers have not seen yet: the next request works', async () => {
  const config = { authMode: 'sp', tenantId: 'contoso.onmicrosoft.com', clientId: 'app', clientSecret: 'new-secret', endpoints: { login: 'https://login.test' } };
  const replicating = scriptedFetch([
    {
      match: '/token',
      respond: [
        json(401, { error: 'invalid_client', error_description: 'AADSTS7000215: Invalid client secret provided.' }),
        json(400, { error: 'unauthorized_client', error_description: "AADSTS700016: Application with identifier 'app' was not found in the directory." }),
        json(200, { access_token: 'fresh', expires_in: 3600 }),
      ],
    },
  ]);
  const tokens = createTokenProvider(config, { fetchImpl: replicating.fetchImpl, retryDelaysMs: [0, 0, 0] });
  assert.equal(await tokens.getToken('scope-1'), 'fresh');
  assert.equal(replicating.calls.length, 3);

  // Anything else fails at once: an expired secret won't start working.
  const expired = scriptedFetch([{ match: '/token', respond: json(401, { error: 'invalid_client', error_description: 'AADSTS7000222: The provided client secret keys are expired.' }) }]);
  await assert.rejects(createTokenProvider(config, { fetchImpl: expired.fetchImpl, retryDelaysMs: [0, 0, 0] }).getToken('scope-1'), /AADSTS7000222/);
  assert.equal(expired.calls.length, 1);
});

test('a caller can ask for a token that lasts longer, without a token request on every call', async () => {
  const config = { authMode: 'sp', tenantId: 'contoso.onmicrosoft.com', clientId: 'app', clientSecret: 's', endpoints: { login: 'https://login.test' } };
  const { fetchImpl, calls } = scriptedFetch([
    { match: '/token', respond: [json(200, { access_token: 'short', expires_in: 20 * 60 }), json(200, { access_token: 'still-short', expires_in: 20 * 60 }), json(200, { access_token: 'long', expires_in: 3600 })] },
  ]);
  let clock = 1_000_000;
  const tokens = createTokenProvider(config, { fetchImpl, now: () => clock });
  const embedding = { minValidityMs: 35 * 60_000 };
  assert.equal(await tokens.getToken('pbi'), 'short');
  clock += 2 * 60_000;
  assert.equal(await tokens.getToken('pbi'), 'short', '18 minutes left is enough for an ordinary call');
  assert.equal(await tokens.getToken('pbi', embedding), 'still-short', 'a 30-minute embed token needs 35 minutes: ask again');
  assert.equal(await tokens.getToken('pbi', embedding), 'still-short', 'a token fetched moments ago is used as it is');
  clock += 2 * 60_000;
  assert.equal(await tokens.getToken('pbi', embedding), 'long');
  assert.equal(calls.length, 3);
});

test('Azure CLI mode asks for the scope and pins the tenant', async () => {
  let args;
  const tokens = createTokenProvider(
    { authMode: 'cli', tenantId: 'dddddddd-1111-4222-8333-444444444444', endpoints: {} },
    { azureCli: async (a) => ((args = a), JSON.stringify({ accessToken: 'cli-token', expires_on: Math.floor(Date.now() / 1000) + 3600 })) },
  );
  assert.equal(await tokens.getToken('https://api.fabric.microsoft.com/.default'), 'cli-token');
  assert.deepEqual(args, ['account', 'get-access-token', '--scope', 'https://api.fabric.microsoft.com/.default', '--output', 'json', '--tenant', 'dddddddd-1111-4222-8333-444444444444']);
});
