import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createMockFabric } from '../src/fabric/mock.js';
import { selectedTables } from '../src/platform/agent.js';
import {
  detectFormat,
  fetchFromWeb,
  importFromWeb,
  ingestBytes,
  isPublicAddress,
  refreshAgentAfterLoad,
  sanitizeFileStem,
  sanitizeTableName,
  syncAppData,
} from '../src/platform/ingest.js';
import { createProvisioner } from '../src/platform/provisioner.js';
import { createTenantStore, newTenantRecord } from '../src/platform/store.js';
import { provisioningKit } from './support.js';

// Loading files needs the data integration add-on, which brings the lakehouse.
async function readyTenant(plan = 'enterprise') {
  const kit = provisioningKit();
  const tenant = await kit.provisionNew({ name: 'Northwind Clinics', plan, addons: ['integration'], sampleData: false });
  return { fabric: kit.fabric, tenant };
}

const publicLookup = async () => [{ address: '93.184.216.34', family: 4 }];

test('table and file names are made safe for Fabric', () => {
  assert.equal(sanitizeTableName('Q3 Sales (EU)'), 'q3_sales_eu');
  assert.equal(sanitizeTableName('2026'), 't_2026');
  assert.equal(sanitizeTableName(''), 't_data');
  assert.equal(sanitizeFileStem('../../etc/pass wd.csv'), 'etc_pass_wd');
  assert.equal(sanitizeFileStem('Résumé final.xlsx'), 'Resume_final');
});

test('Excel must be converted first; unknown types are rejected', () => {
  assert.throws(() => detectFormat('book.xlsx'), (error) => error.status === 415);
  assert.throws(() => detectFormat('notes.docx'), (error) => error.status === 415);
  assert.equal(detectFormat('data.tsv').delimiter, '\t');
});

test('CSV and JSON land in OneLake and load as tables; the data agent picks them up', async () => {
  const { fabric, tenant } = await readyTenant();
  const csv = await ingestBytes({ fabric, tenant, bytes: Buffer.from('id,amount\n1,10\n2,20\n'), fileName: 'Q3 Sales.csv' });
  assert.equal(csv.table, 'q3_sales');
  assert.match(csv.file, /^Files\/landing\/q3_sales\/.+_Q3_Sales\.csv$/);

  const fromJson = await ingestBytes({ fabric, tenant, bytes: Buffer.from(JSON.stringify([{ a: 1, b: { c: 2 } }])), fileName: 'events.json', mode: 'Append' });
  assert.equal(fromJson.rows, 1);
  assert.match(fromJson.file, /\.csv$/);

  const agent = await refreshAgentAfterLoad({ fabric, tenant });
  assert.deepEqual(agent.added.sort(), ['events', 'q3_sales']);
  const { definition } = await fabric.getItemDefinition(tenant.fabric.workspaceId, tenant.fabric.dataAgentId);
  assert.deepEqual(selectedTables(definition).sort(), ['events', 'q3_sales']);
  const answer = await fabric.askDataAgent(tenant.fabric.workspaceId, tenant.fabric.dataAgentId, 'How many rows are in q3_sales?');
  assert.equal(answer.answer, 'Q3 sales: 2 rows.');
});

test('the crm_ prefix is reserved for the app', async () => {
  const { fabric, tenant } = await readyTenant('analytics');
  await assert.rejects(ingestBytes({ fabric, tenant, bytes: Buffer.from('a\n1\n'), fileName: 'x.csv', table: 'crm_accounts' }), (error) => error.status === 400);
  const loaded = await syncAppData({ fabric, tenant });
  assert.deepEqual(loaded.map((r) => [r.table, r.rows]), [
    ['crm_accounts', 60],
    ['crm_opportunities', 240],
    ['crm_activities', 600],
  ]);
  assert.equal((await fabric.countTableRows(tenant.fabric.workspaceId, tenant.fabric.lakehouseId, 'crm_opportunities')).rows, 240);
});

test('private and local addresses are never fetched', async () => {
  for (const address of ['127.0.0.1', '10.1.2.3', '172.20.0.1', '192.168.1.1', '169.254.169.254', '100.64.0.1', '::1', 'fd00::1', 'fe80::1', '::ffff:10.0.0.1']) {
    assert.equal(isPublicAddress(address), false, address);
  }
  assert.equal(isPublicAddress('20.42.0.1'), true);
  await assert.rejects(fetchFromWeb('http://169.254.169.254/metadata', { lookup: publicLookup }), (error) => error.status === 400);
  await assert.rejects(fetchFromWeb('file:///etc/passwd'), (error) => error.status === 400);
  await assert.rejects(fetchFromWeb('https://user:pw@example.com/a.csv', { lookup: publicLookup }), (error) => error.status === 400);
  await assert.rejects(fetchFromWeb('https://internal.example/a.csv', { lookup: async () => [{ address: '10.0.0.5', family: 4 }] }), /private or local/);
});

test('redirects to private addresses are blocked, and size limits apply', async () => {
  const redirect = async () => new Response(null, { status: 302, headers: { location: 'http://127.0.0.1:8080/admin' } });
  await assert.rejects(fetchFromWeb('https://example.com/data.csv', { fetchImpl: redirect, lookup: publicLookup }), /private or local/);
  const big = async () => new Response('x'.repeat(2048), { status: 200, headers: { 'content-type': 'text/csv' } });
  await assert.rejects(fetchFromWeb('https://example.com/data.csv', { fetchImpl: big, lookup: publicLookup, maxBytes: 1024 }), (error) => error.status === 413);
});

test('a JSON API becomes a table named after the URL', async () => {
  const { fabric, tenant } = await readyTenant('analytics');
  const api = async () => new Response(JSON.stringify([{ id: 1, address: { city: 'Lima' } }, { id: 2, address: { city: 'Oslo' } }]), { status: 200, headers: { 'content-type': 'application/json; charset=utf-8' } });
  const record = await importFromWeb({ fabric, tenant, url: 'https://example.com/api/users', mode: 'Overwrite', fetchOptions: { fetchImpl: api, lookup: publicLookup } });
  assert.equal(record.table, 'users');
  assert.equal(record.rows, 2);
  assert.match(record.source, /example\.com/);
});
