import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createFabricClient, embedTokenValidityMs } from '../src/fabric/client.js';
import { json, scriptedFetch, staticTokens } from './helpers.js';

const endpoints = {
  fabric: 'https://fabric.test/v1',
  powerbi: 'https://pbi.test/v1.0/myorg',
  onelake: 'https://onelake.test',
  login: 'https://login.test',
};
const client = (fetchImpl) => createFabricClient({ tokens: staticTokens, endpoints, fetchImpl, pollIntervalMs: 1, baseBackoffMs: 1 });

test('retries 429 responses after Retry-After and then succeeds', async () => {
  const { fetchImpl, calls } = scriptedFetch([
    { match: '/workspaces/ws-1', respond: [json(429, { errorCode: 'RequestBlocked' }, { 'retry-after': '0' }), json(200, { id: 'ws-1', displayName: 'A' })] },
  ]);
  const ws = await client(fetchImpl).getWorkspace('ws-1');
  assert.equal(ws.displayName, 'A');
  assert.equal(calls.length, 2);
  assert.equal(calls[0].headers.authorization, 'Bearer token-for-https://api.fabric.microsoft.com/.default');
});

test('follows a long-running operation to its result', async () => {
  const { fetchImpl, calls } = scriptedFetch([
    { match: /\/workspaces\/ws\/items$/, method: 'POST', respond: json(202, undefined, { location: 'https://fabric.test/v1/operations/op-1', 'retry-after': '0' }) },
    { match: /\/operations\/op-1\/result$/, respond: json(200, { id: 'item-9', type: 'Lakehouse' }) },
    {
      match: /\/operations\/op-1$/,
      respond: [json(200, { status: 'Running' }), json(200, { status: 'Succeeded' }, { location: 'https://fabric.test/v1/operations/op-1/result' })],
    },
  ]);
  const item = await client(fetchImpl).createItem('ws', { displayName: 'lh', type: 'Lakehouse' });
  assert.deepEqual(item, { id: 'item-9', type: 'Lakehouse' });
  assert.deepEqual(calls.map((c) => `${c.method} ${new URL(c.url).pathname}`), [
    'POST /v1/workspaces/ws/items',
    'GET /v1/operations/op-1',
    'GET /v1/operations/op-1',
    'GET /v1/operations/op-1/result',
  ]);
  assert.deepEqual(JSON.parse(calls[0].body), { displayName: 'lh', type: 'Lakehouse' });
});

test('reports a failed long-running operation with its error code', async () => {
  const { fetchImpl } = scriptedFetch([
    { match: '/load', respond: json(202, undefined, { location: 'https://fabric.test/v1/operations/op-2', 'retry-after': '0' }) },
    { match: '/operations/op-2', respond: json(200, { status: 'Failed', error: { errorCode: 'BadFile', message: 'Bad CSV' } }) },
  ]);
  await assert.rejects(client(fetchImpl).loadTable('ws', 'lh', 'sales', {}), (error) => error.code === 'BadFile' && /Bad CSV/.test(error.message));
});

test('pages through continuation URIs', async () => {
  const { fetchImpl } = scriptedFetch([
    { match: 'continuationToken=abc', respond: json(200, { value: [{ id: 2 }] }) },
    { match: /\/workspaces$/, respond: json(200, { value: [{ id: 1 }], continuationUri: 'https://fabric.test/v1/workspaces?continuationToken=abc' }) },
  ]);
  assert.deepEqual(await client(fetchImpl).listWorkspaces(), [{ id: 1 }, { id: 2 }]);
});

test('turns Fabric error bodies into readable errors', async () => {
  const { fetchImpl } = scriptedFetch([
    { match: '/workspaces/missing', respond: json(404, { errorCode: 'WorkspaceNotFound', message: 'No such workspace', requestId: 'req-1' }) },
  ]);
  await assert.rejects(client(fetchImpl).getWorkspace('missing'), (error) => {
    assert.equal(error.upstreamStatus, 404);
    assert.equal(error.code, 'WorkspaceNotFound');
    assert.equal(error.requestId, 'req-1');
    assert.match(error.message, /HTTP 404, WorkspaceNotFound/);
    return true;
  });
});

test('uploads to OneLake with create, append and flush', async () => {
  const { fetchImpl, calls } = scriptedFetch([
    { match: 'resource=file', method: 'PUT', respond: new Response(null, { status: 201 }) },
    { match: 'action=append', method: 'PATCH', respond: () => new Response(null, { status: 202 }) },
    { match: 'action=flush', method: 'PATCH', respond: new Response(null, { status: 200 }) },
  ]);
  const bytes = Buffer.alloc(9 * 1024 * 1024, 7);
  await client(fetchImpl).uploadFile('ws', 'lh', 'Files/landing/sales/a file.csv', bytes);
  const urls = calls.map((c) => `${c.method} ${c.url.replace('https://onelake.test/ws/lh/Files/landing/sales/a%20file.csv', '')}`);
  assert.deepEqual(urls, ['PUT ?resource=file', 'PATCH ?action=append&position=0', 'PATCH ?action=append&position=4194304', 'PATCH ?action=append&position=8388608', 'PATCH ?action=flush&position=9437184']);
  assert.equal(calls[0].headers.authorization, 'Bearer token-for-https://storage.azure.com/.default');
  assert.equal(calls[0].headers['x-ms-version'], '2023-11-03');
});

test('starts a job and reads the job ID from the Location header', async () => {
  const { fetchImpl, calls } = scriptedFetch([
    { match: 'jobType=Pipeline', method: 'POST', respond: new Response(null, { status: 202, headers: { location: 'https://fabric.test/v1/workspaces/ws/items/p1/jobs/instances/job-7' } }) },
  ]);
  const job = await client(fetchImpl).runItemJob('ws', 'p1', 'Pipeline');
  assert.equal(job.jobInstanceId, 'job-7');
  assert.equal(calls[0].body, undefined);
});

test('counts rows by replaying the Delta log', async () => {
  const log = (n) => `lh/Tables/sales/_delta_log/${String(n).padStart(20, '0')}.json`;
  const commit0 = [
    JSON.stringify({ metaData: { id: 'm' } }),
    JSON.stringify({ add: { path: 'part-0.parquet', stats: JSON.stringify({ numRecords: 60 }) } }),
  ].join('\n');
  const commit1 = [
    JSON.stringify({ remove: { path: 'part-0.parquet' } }),
    JSON.stringify({ add: { path: 'part-1.parquet', stats: JSON.stringify({ numRecords: 40 }) } }),
    JSON.stringify({ add: { path: 'part-2.parquet', stats: JSON.stringify({ numRecords: 2 }) } }),
  ].join('\n');
  const { fetchImpl } = scriptedFetch([
    { match: 'resource=filesystem', respond: json(200, { paths: [{ name: log(1) }, { name: log(0) }, { name: 'lh/Tables/sales/_delta_log/_tmp' }] }) },
    { match: log(0), respond: new Response(commit0) },
    { match: log(1), respond: new Response(commit1) },
  ]);
  assert.deepEqual(await client(fetchImpl).countTableRows('ws', 'lh', 'sales'), { rows: 42, files: 2, version: 1 });
});

test('requests embed tokens with the Power BI scope', async () => {
  const { fetchImpl, calls } = scriptedFetch([{ match: '/GenerateToken', method: 'POST', respond: json(200, { token: 't', expiration: '2030-01-01T00:00:00Z' }) }]);
  await client(fetchImpl).pbiGenerateToken({ reports: [{ id: 'r' }] });
  assert.equal(calls[0].url, 'https://pbi.test/v1.0/myorg/GenerateToken');
  assert.equal(calls[0].headers.authorization, 'Bearer token-for-https://analysis.windows.net/powerbi/api/.default');
});

test('embed tokens are created with a Microsoft Entra token that outlives them', async () => {
  const asked = [];
  const tokens = { getToken: async (scope, options) => (asked.push([scope, options?.minValidityMs]), 'tok') };
  const { fetchImpl } = scriptedFetch([{ match: '/GenerateToken', method: 'POST', respond: json(200, { token: 't', expiration: '2030-01-01T00:00:00Z' }) }]);
  await createFabricClient({ tokens, endpoints, fetchImpl }).pbiGenerateToken({ reports: [{ id: 'r' }], lifetimeInMinutes: 30 });
  assert.deepEqual(asked, [['https://analysis.windows.net/powerbi/api/.default', 35 * 60_000]]);
  assert.equal(embedTokenValidityMs({}), 55 * 60_000, 'an hour-long embed token asks for no more than a fresh token gives');
});