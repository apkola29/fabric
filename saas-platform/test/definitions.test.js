import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildDataAgentDefinition, mergeTableElements, selectedTables } from '../src/platform/agent.js';
import { buildReplacer, remapParts } from '../src/platform/templates.js';
import { decodePayload, encodePayload, isTextPart, textPart } from '../src/util/definition.js';

const A = 'AAAAAAAA-0000-4000-8000-000000000001';
const B = 'bbbbbbbb-0000-4000-8000-000000000002';

test('buildReplacer swaps GUIDs regardless of case, in one pass', () => {
  const replace = buildReplacer([
    [A, B],
    [B, 'should-not-chain'],
    ['myorg/Template', 'myorg/saas-fabrikam'],
  ]);
  assert.equal(replace(`id=${A.toLowerCase()} other=${A}`), `id=${B} other=${B}`);
  assert.equal(replace(`ref ${B}`), 'ref should-not-chain');
  assert.equal(replace('powerbi://api.powerbi.com/v1.0/myorg/Template'), 'powerbi://api.powerbi.com/v1.0/myorg/saas-fabrikam');
});

test('buildReplacer prefers the longest match', () => {
  const replace = buildReplacer([
    ['host.example.com', 'new.example.com'],
    ['host.example.com,1433', 'other.example.com,1433'],
  ]);
  assert.equal(replace('Server=host.example.com,1433'), 'Server=other.example.com,1433');
});

test('remapParts rewrites text parts, keeps binary parts and drops .platform', () => {
  const binary = { path: 'StaticResources/logo.png', payload: Buffer.from([0x89, 0x50, 0x00, 0xff]).toString('base64'), payloadType: 'InlineBase64' };
  const parts = [textPart('definition.pbir', `semanticmodelid=${A}`), textPart('.platform', '{"metadata":{}}'), binary];
  const result = remapParts(parts, buildReplacer([[A, B]]));
  assert.equal(result.length, 2);
  assert.equal(decodePayload(result[0].payload), `semanticmodelid=${B}`);
  assert.equal(result[1].payload, binary.payload);
});

test('isTextPart sniffs content for unknown extensions', () => {
  assert.equal(isTextPart({ path: 'notes', payload: encodePayload('hello') }), true);
  assert.equal(isTextPart({ path: 'blob', payload: Buffer.from([0, 1, 2]).toString('base64') }), false);
});

test('buildDataAgentDefinition writes draft and published parts', () => {
  const definition = buildDataAgentDefinition({ workspaceId: 'ws', lakehouseId: 'lh', lakehouseName: 'lh_customer', tables: ['crm_accounts'], instructions: 'Be exact.', description: 'Agent' });
  const paths = definition.parts.map((p) => p.path);
  assert.ok(paths.includes('Files/Config/data_agent.json'));
  assert.ok(paths.includes('Files/Config/draft/lakehouse_tables-lh_customer/datasource.json'));
  assert.ok(paths.includes('Files/Config/published/lakehouse_tables-lh_customer/datasource.json'));
  assert.ok(paths.includes('Files/Config/publish_info.json'));
  const datasource = JSON.parse(decodePayload(definition.parts.find((p) => p.path.endsWith('published/lakehouse_tables-lh_customer/datasource.json')).payload));
  assert.equal(datasource.artifactId, 'lh');
  assert.equal(datasource.type, 'lakehouse_tables');
  assert.deepEqual(selectedTables(definition), ['crm_accounts']);
});

test('mergeTableElements adds new tables under dbo and keeps existing ones', () => {
  const existing = [
    { display_name: 'dbo', type: 'lakehouse_tables.schema', is_selected: true, children: [{ display_name: 'crm_accounts', type: 'lakehouse_tables.table', is_selected: true, description: 'kept' }] },
  ];
  const { elements, added } = mergeTableElements(existing, ['CRM_ACCOUNTS', 'sales']);
  assert.deepEqual(added, ['sales']);
  assert.equal(elements[0].children.length, 2);
  assert.equal(elements[0].children[0].description, 'kept');
  assert.equal(existing[0].children.length, 1, 'input is not mutated');
});

test('mergeTableElements handles flat and empty element lists', () => {
  const flat = mergeTableElements([{ display_name: 'a', type: 'lakehouse_tables.table', is_selected: true }], ['a', 'b']);
  assert.deepEqual(flat.elements.map((e) => e.display_name), ['a', 'b']);
  const empty = mergeTableElements(undefined, ['x']);
  assert.equal(empty.elements[0].type, 'lakehouse_tables.schema');
  assert.equal(empty.elements[0].children[0].display_name, 'x');
});
