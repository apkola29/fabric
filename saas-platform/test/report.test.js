import assert from 'node:assert/strict';
import { test } from 'node:test';
import { MEASURES } from '../src/crm/model.js';
import { STARTER_REPORT_NAME, buildStarterReportDefinition, starterReportVisuals } from '../src/crm/report.js';
import { CRM_TABLES } from '../src/crm/schema.js';
import { MOCK_TEMPLATE_ID } from '../src/fabric/mock.js';
import { createEmbedConfig } from '../src/platform/reporting.js';
import { decodePayload } from '../src/util/definition.js';
import { provisioningKit } from './support.js';

const MODEL_ID = '0b1d2c3e-0000-4000-8000-0000000000aa';

// Every field a visual uses, as Entity|Property.
function fieldsOf(value, found = []) {
  if (Array.isArray(value)) value.forEach((v) => fieldsOf(v, found));
  else if (value && typeof value === 'object') {
    for (const kind of ['Column', 'Measure']) {
      const ref = value[kind];
      if (ref?.Expression?.SourceRef?.Entity && ref.Property) found.push({ kind, name: `${ref.Expression.SourceRef.Entity}|${ref.Property}` });
    }
    Object.values(value).forEach((v) => fieldsOf(v, found));
  }
  return found;
}

test('the starter report is PBIR bound to the customer model, and every field it uses exists in the model', () => {
  const { definition, files } = buildStarterReportDefinition({ semanticModelId: MODEL_ID });
  const paths = definition.parts.map((p) => p.path);
  assert.ok(paths.includes('definition.pbir') && paths.includes('definition/report.json') && paths.includes('definition/version.json'));
  assert.ok(paths.includes('StaticResources/SharedResources/BaseThemes/Fluent2-CY26SU09.json'), 'the base theme report.json names is included');
  for (const part of definition.parts) assert.doesNotThrow(() => JSON.parse(decodePayload(part.payload)), `${part.path} is JSON`);
  assert.equal(files['definition.pbir'].datasetReference.byConnection.connectionString, `semanticmodelid=${MODEL_ID}`, 'the Fabric API binding form');

  const [page] = files['definition/pages/pages.json'].pageOrder;
  assert.equal(files[`definition/pages/${page}/page.json`].name, page);
  const visuals = Object.entries(files).filter(([path]) => path.startsWith(`definition/pages/${page}/visuals/`));
  assert.equal(visuals.length, starterReportVisuals().length);
  assert.equal(new Set(visuals.map(([, v]) => v.name)).size, visuals.length, 'visual names are unique');
  for (const [path, visual] of visuals) {
    assert.equal(path, `definition/pages/${page}/visuals/${visual.name}/visual.json`);
    assert.match(visual.name, /^[0-9a-f]{20}$/);
    const { x, y, width, height } = visual.position;
    assert.ok(x >= 0 && y >= 0 && x + width <= 1280 && y + height <= 720, `${visual.name} fits the 1280 x 720 page`);
    assert.ok(Object.keys(visual.visual.query.queryState).length, 'roles live under queryState');
  }

  const columns = new Set(CRM_TABLES.flatMap((t) => t.columns.filter((c) => c.inModel !== false).map((c) => `${t.model}|${c.model}`)));
  const measures = new Set(MEASURES.map((m) => `${CRM_TABLES.find((t) => t.name === m.table).model}|${m.name}`));
  const used = fieldsOf(visuals.map(([, v]) => v));
  assert.ok(used.length > 15);
  for (const field of used) assert.ok((field.kind === 'Column' ? columns : measures).has(field.name), `${field.kind} ${field.name} exists in the model`);
  assert.ok(used.some((f) => f.name === 'Accounts|State'), 'the report shows the territory split');
  assert.deepEqual(buildStarterReportDefinition({ semanticModelId: MODEL_ID }).files, files, 'the same report every time');
});

test('without a template workspace, provisioning creates the starter report once and never overwrites it', async () => {
  const kit = provisioningKit();
  const tenant = await kit.provisionNew({ name: 'Fabrikam' });
  assert.equal(tenant.status, 'ready', tenant.error);
  assert.equal(tenant.steps['starter-report'].status, 'done');
  assert.equal(tenant.steps.templates.status, 'skipped');
  const client = await kit.identities.fabricFor(tenant);
  const reports = await client.pbiListReports(tenant.fabric.workspaceId);
  assert.deepEqual(reports.map((r) => [r.name, r.datasetId]), [[STARTER_REPORT_NAME, tenant.fabric.semanticModelId]]);
  assert.equal(tenant.fabric.starterReportId, reports[0].id);

  await kit.provisioner.provision(tenant.id);
  const again = kit.store.get(tenant.id);
  assert.match(again.steps['starter-report'].detail, /is in place/);
  assert.equal((await client.pbiListReports(tenant.fabric.workspaceId)).length, 1, 'no second copy');

  // The report is on the model with row-level security, so it opens only with the viewer's territories.
  const embed = await createEmbedConfig({ fabric: client, tenant: again, reportId: reports[0].id, identity: { username: 'rep@fabrikam.com', roles: ['Texas'] } });
  assert.deepEqual(embed.tokenRequest.identities, [{ username: 'rep@fabrikam.com', roles: ['Texas'], datasets: [tenant.fabric.semanticModelId] }]);
});

test('with a template workspace, the template provides the reports instead', async () => {
  const kit = provisioningKit({ config: { templateWorkspaceId: MOCK_TEMPLATE_ID } });
  const tenant = await kit.provisionNew({ name: 'Contoso' });
  assert.equal(tenant.status, 'ready', tenant.error);
  assert.deepEqual([tenant.steps['starter-report'].status, tenant.steps.templates.status], ['skipped', 'done']);
});
