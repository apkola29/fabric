import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ASSISTANT_MODEL_NAME, MODEL_NAME } from '../src/crm/model.js';
import { MOCK_TEMPLATE_ID } from '../src/fabric/mock.js';
import { agentModelSource } from '../src/platform/agent.js';
import { decodePayload } from '../src/util/definition.js';
import { provisioningKit } from './support.js';

const OPS = { id: '11111111-2222-4333-8444-555555555555', type: 'Group' };
const stepStatus = (tenant) => Object.entries(tenant.steps).map(([key, s]) => [key, s.status]);

test('Enterprise: the platform hands the workspace to the customer service account, which builds the CRM, model and assistant', async () => {
  const kit = provisioningKit({ config: { templateWorkspaceId: MOCK_TEMPLATE_ID, opsPrincipal: OPS } });
  const tenant = await kit.provisionNew();
  assert.equal(tenant.status, 'ready', tenant.error);
  assert.deepEqual(stepStatus(tenant), [
    ['workspace', 'done'],
    ['capacity', 'done'],
    ['service-account', 'done'],
    ['ops-access', 'done'],
    ['crm-database', 'done'],
    ['crm-schema', 'done'],
    ['crm-sample-data', 'done'],
    ['lakehouse', 'skipped'],
    ['workspace-identity', 'done'],
    ['semantic-model', 'done'],
    ['model-connection', 'done'],
    ['starter-report', 'skipped'],
    ['templates', 'done'],
    ['assistant-model', 'done'],
    ['data-agent', 'done'],
    ['platform-access', 'skipped'],
  ]);

  const ws = tenant.fabric.workspaceId;
  const roles = Object.fromEntries((await kit.fabric.listRoleAssignments(ws)).map((r) => [r.principal.id, r.role]));
  assert.equal(tenant.identity.name, 'fabrikamsa');
  assert.equal(roles[tenant.identity.objectId], 'Admin', 'the service account is Admin of this one workspace');
  assert.equal(roles[OPS.id], 'Viewer', 'support gets read access, not Admin');
  assert.equal(roles[tenant.fabric.workspaceIdentity.servicePrincipalId], 'Contributor', 'the workspace identity can read the OneLake replica');

  const items = Object.fromEntries((await kit.fabric.listItems(ws)).map((i) => [`${i.type}:${i.displayName}`, i.id]));
  assert.ok(items['SQLDatabase:hicrm_db']);
  assert.equal(items[`SemanticModel:${MODEL_NAME}`], tenant.fabric.semanticModelId);
  assert.equal(items[`SemanticModel:${ASSISTANT_MODEL_NAME}`], tenant.fabric.assistantModelId);
  assert.ok(items['Report:Sales overview']);
  assert.equal(items['DataAgent:HiCRM Assistant'], tenant.fabric.dataAgentId);

  const model = await kit.fabric.getItemDefinition(ws, tenant.fabric.semanticModelId);
  const expression = decodePayload(model.definition.parts.find((p) => p.path === 'definition/expressions.tmdl').payload);
  assert.ok(expression.includes(`https://onelake.dfs.fabric.microsoft.com/${ws}/${tenant.fabric.crm.sqlDatabaseId}`), 'Direct Lake reads the CRM database replica');
  // Reports get the model with row-level security; the assistant's twin has no roles (service principals can't query
  // models with roles), and only reads the same OneLake tables.
  const roleParts = (definition) => definition.parts.filter((p) => p.path.startsWith('definition/roles/')).length;
  assert.equal(roleParts(model.definition), 4);
  const twin = await kit.fabric.getItemDefinition(ws, tenant.fabric.assistantModelId);
  assert.equal(roleParts(twin.definition), 0);
  assert.equal(decodePayload(twin.definition.parts.find((p) => p.path === 'definition/expressions.tmdl').payload), expression);

  const [reference] = await kit.fabric.listItemConnections(ws, tenant.fabric.semanticModelId);
  assert.equal(reference.connectivityType, 'ShareableCloud');
  assert.equal(reference.id, tenant.fabric.modelConnectionId);
  assert.equal(tenant.fabric.assistantConnectionId, tenant.fabric.modelConnectionId, 'both models share one connection');
  assert.equal((await kit.fabric.listConnections()).length, 0, "the platform identity doesn't own the customer's connection");
  const [connection] = await kit.fabric.as(tenant.identity.objectId).listConnections();
  assert.deepEqual(connection.credentialDetails, { credentialType: 'WorkspaceIdentity', singleSignOnType: 'None' });
  assert.equal((await kit.fabric.pbiListRefreshes(ws, tenant.fabric.semanticModelId))[0].status, 'Completed');
  assert.equal((await kit.fabric.pbiListRefreshes(ws, tenant.fabric.assistantModelId))[0].status, 'Completed');

  const [report] = await kit.fabric.pbiListReports(ws);
  assert.equal(report.datasetId, tenant.fabric.semanticModelId, "the template report points at the customer's own model");

  const agent = agentModelSource((await kit.fabric.getItemDefinition(ws, tenant.fabric.dataAgentId)).definition);
  assert.equal(agent.type, 'semantic_model');
  assert.equal(agent.artifactId, tenant.fabric.assistantModelId, "the agent reads the assistant's model");
  const opportunities = agent.elements.find((e) => e.display_name === 'Opportunities');
  assert.ok(opportunities.children.some((c) => c.type === 'semantic_model.measure' && c.display_name === 'Pipeline Value'));
  assert.ok(!opportunities.children.some((c) => c.display_name === 'Opportunity ID'), 'hidden keys stay out of the agent');

  const counts = await (await kit.crm.forTenant(tenant)).counts();
  assert.equal(counts.accounts, 120);
  assert.ok(counts.opportunities > 200);
});

test('a second run changes nothing and says what already exists', async () => {
  const kit = provisioningKit({ config: { templateWorkspaceId: MOCK_TEMPLATE_ID } });
  const first = await kit.provisionNew();
  const itemsBefore = (await kit.fabric.listItems(first.fabric.workspaceId)).length;
  const again = await kit.provisioner.provision(first.id);
  assert.equal(again.status, 'ready', again.error);
  assert.match(again.steps['crm-database'].detail, /hicrm_db exists/);
  assert.match(again.steps['crm-sample-data'].detail, /Already has data/);
  assert.match(again.steps['semantic-model'].detail, /up to date/);
  assert.match(again.steps['model-connection'].detail, /^Uses /);
  assert.match(again.steps.templates.detail, /0 created, 1 already present/);
  assert.match(again.steps['data-agent'].detail, /up to date/);
  assert.equal((await kit.fabric.listItems(first.fabric.workspaceId)).length, itemsBefore);
  assert.equal((await kit.fabric.as(first.identity.objectId).listConnections()).length, 1, 'no second connection');
});

test('a new model version reaches existing customers on the next run', async () => {
  const kit = provisioningKit();
  const tenant = await kit.provisionNew();
  tenant.fabric.semanticModelFingerprint = 'an-older-version';
  await kit.store.save(tenant);
  const updated = await kit.provisioner.provision(tenant.id);
  assert.match(updated.steps['semantic-model'].detail, /Updated HiCRM Insights/);
  assert.equal(updated.steps['model-connection'].status, 'done');
});

test('Standard skips the assistant; an upgrade adds it and a downgrade keeps it', async () => {
  const kit = provisioningKit();
  const tenant = await kit.provisionNew({ plan: 'standard' });
  assert.equal(tenant.steps['data-agent'].status, 'skipped');
  assert.equal((await kit.fabric.listItems(tenant.fabric.workspaceId, 'DataAgent')).length, 0);
  tenant.plan = 'enterprise';
  await kit.store.save(tenant);
  assert.equal((await kit.provisioner.provision(tenant.id)).steps['data-agent'].status, 'done');
  tenant.plan = 'standard';
  await kit.store.save(tenant);
  assert.equal((await kit.provisioner.provision(tenant.id)).steps['data-agent'].status, 'retained');
});

test('the data integration add-on adds a lakehouse; an empty CRM still gets its calendar', async () => {
  const kit = provisioningKit();
  const tenant = await kit.provisionNew({ plan: 'professional', addons: ['integration'], sampleData: false });
  assert.equal(tenant.steps.lakehouse.status, 'done');
  assert.ok(tenant.fabric.lakehouseId);
  assert.equal(tenant.steps['crm-sample-data'].status, 'skipped');
  const counts = await (await kit.crm.forTenant(tenant)).counts();
  assert.equal(counts.accounts, 0);
  assert.equal(counts.calendar, 1461);
});

test('adopts a workspace an admin created and keeps its capacity', async () => {
  const kit = provisioningKit();
  const ws = await kit.fabric.createWorkspace({ displayName: 'made-by-admin', capacityId: 'admin-capacity' });
  const tenant = await kit.provisionNew({ workspaceId: ws.id });
  assert.equal(tenant.status, 'ready', tenant.error);
  assert.equal(tenant.fabric.workspaceId, ws.id);
  assert.match(tenant.steps.capacity.detail, /Uses the workspace's capacity/);
});

test('removing a customer deletes the workspace and its connection unless asked to keep the workspace', async () => {
  const kit = provisioningKit();
  const gone = await kit.provisionNew({ name: 'Gone Co' });
  const connections = () => Object.keys(kit.fabric.inspect().connections).length;
  assert.equal(connections(), 1);
  await kit.provisioner.deprovision(gone.id);
  assert.equal(kit.store.get(gone.id), null);
  await assert.rejects(kit.fabric.getWorkspace(gone.fabric.workspaceId), (error) => error.upstreamStatus === 404);
  assert.equal(connections(), 0, 'connections live outside the workspace and are removed too');

  const kept = await kit.provisionNew({ name: 'Kept Co' });
  await kit.provisioner.deprovision(kept.id, { keepWorkspace: true });
  assert.ok(await kit.fabric.getWorkspace(kept.fabric.workspaceId));
});

test('without a service account, required mode stops and preferred mode carries on with a warning', async () => {
  const base = provisioningKit().config;
  const live = (mode) => ({ ...base, authMode: 'sp', identity: { mode, autoCreate: false, fabricGroupId: '' } });

  const strict = provisioningKit({ identityConfig: live('required') });
  const stopped = await strict.provisionNew();
  assert.equal(stopped.status, 'failed');
  assert.equal(stopped.steps['service-account'].status, 'failed');
  assert.match(stopped.error, /no service account yet.*bootstrap-identities/);
  assert.equal(stopped.steps['crm-database'].status, 'pending', 'nothing is built with the shared identity');

  const relaxed = provisioningKit({ identityConfig: live('preferred') });
  const carried = await relaxed.provisionNew();
  assert.equal(carried.status, 'ready', carried.error);
  assert.equal(carried.steps['service-account'].status, 'warning');
  assert.match(carried.steps['service-account'].detail, /shared platform identity/);
});
