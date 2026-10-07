import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ASSISTANT_MODEL_NAME, DIRECT_LAKE_EXPRESSION, MODEL_NAME } from '../src/crm/model.js';
import { FabricApiError } from '../src/fabric/client.js';
import { MOCK_TEMPLATE_ID, createMockFabric } from '../src/fabric/mock.js';
import { agentModelSource } from '../src/platform/agent.js';
import { entraDisplayName } from '../src/platform/identities.js';
import { LEGACY_ITEM_NAMES, LEGACY_PRODUCT_NAMES } from '../src/platform/legacy-names.js';
import { CORE_ITEMS } from '../src/platform/plans.js';
import { decodePayload, encodePayload } from '../src/util/definition.js';
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
  assert.ok(items['SQLDatabase:platform_app_db']);
  assert.equal(items[`SemanticModel:${MODEL_NAME}`], tenant.fabric.semanticModelId);
  assert.equal(items[`SemanticModel:${ASSISTANT_MODEL_NAME}`], tenant.fabric.assistantModelId);
  assert.ok(items['Report:Sales overview']);
  assert.equal(items['DataAgent:Platform app Assistant'], tenant.fabric.dataAgentId);

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
  assert.match(again.steps['crm-database'].detail, /platform_app_db exists/);
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
  assert.match(updated.steps['semantic-model'].detail, /Updated Platform app Insights/);
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

// A provisioned customer as an earlier version left it: items, connection and app registration under the earlier
// names, model and agent definitions that named the product too, and the IDs the registry recorded. Returns the
// connection's earlier name and a CRM account added before the upgrade.
async function rewindToEarlierNames(kit, tenant, client, { suffixed = false, database = LEGACY_ITEM_NAMES.crmDatabase[0], connection } = {}) {
  const ws = tenant.fabric.workspaceId;
  const [product] = LEGACY_PRODUCT_NAMES;
  const earlierText = (text) =>
    text
      .replaceAll(DIRECT_LAKE_EXPRESSION, `DirectLake - ${product}`)
      .replaceAll(ASSISTANT_MODEL_NAME, LEGACY_ITEM_NAMES.assistantModel[0])
      .replaceAll(MODEL_NAME, LEGACY_ITEM_NAMES.reportsModel[0]);
  for (const id of [tenant.fabric.semanticModelId, tenant.fabric.assistantModelId, tenant.fabric.dataAgentId]) {
    const { definition } = await client.getItemDefinition(ws, id);
    const parts = definition.parts.map((p) => ({ ...p, path: earlierText(p.path), payload: encodePayload(earlierText(decodePayload(p.payload))) }));
    await client.updateItemDefinition(ws, id, { parts });
  }
  const earlierNames = [
    [tenant.fabric.crmDatabaseId, database],
    [tenant.fabric.semanticModelId, LEGACY_ITEM_NAMES.reportsModel[0]],
    [tenant.fabric.assistantModelId, LEGACY_ITEM_NAMES.assistantModel[0]],
    [tenant.fabric.dataAgentId, LEGACY_ITEM_NAMES.dataAgent[0]],
  ];
  for (const [id, displayName] of earlierNames) await client.updateItem(ws, id, { displayName });
  connection ||= `${product} OneLake ${ws.slice(0, 8)}${suffixed ? ` ${tenant.identity.appId.slice(0, 8)}` : ''}`;
  await client.updateConnection(tenant.fabric.modelConnectionId, { connectivityType: 'ShareableCloud', displayName: connection });
  Object.assign(tenant.fabric, { semanticModelFingerprint: 'earlier', assistantModelFingerprint: 'earlier', dataAgentFingerprint: 'earlier' });
  tenant.identity.displayName = `${product} service account - ${tenant.name} (${tenant.identity.name})`;
  await kit.store.save(tenant);
  const marker = await (await kit.crm.forTenant(tenant)).scoped(null).createAccount({ name: `${tenant.name} account from before the rename` });
  return { database, connection, marker };
}

const connectionsOf = (kit, workspaceId) => Object.values(kit.fabric.inspect().connections).filter((c) => c.connectionDetails.path.includes(workspaceId));

test('customers deployed under the earlier names are renamed in place: same IDs, no duplicates, the report on the same model, the CRM data kept', async () => {
  // As in the live pilot, the platform has handed each workspace over to the customer's service account.
  const kit = provisioningKit({ config: { platformWorkspaceAccess: 'release' } });
  const cases = [
    // Everything under the earlier names, the connection with the account's app ID as in the pilot. The registry lost
    // some IDs, so those items and the connection are found by their earlier names.
    { name: 'Fabrikam', suffixed: true, forget: ['assistantModelId', 'dataAgentId', 'modelConnectionId', 'assistantConnectionId'] },
    // The database and connection renamed by hand to names no version gave them: found by the IDs the registry kept.
    { name: 'Contoso', suffixed: false, database: 'crm_archive', connection: (ws) => `${LEGACY_PRODUCT_NAMES[0]} OneLake ${ws.slice(0, 8)} 00000000`, forget: [] },
  ];
  for (const { name, suffixed, database, connection, forget } of cases) {
    const tenant = await kit.provisionNew({ name });
    assert.equal(tenant.status, 'ready', tenant.error);
    const ws = tenant.fabric.workspaceId;
    const account = kit.fabric.as(tenant.identity.objectId);
    const earlier = await rewindToEarlierNames(kit, tenant, account, { suffixed, database, connection: connection?.(ws) });
    const keys = ['crmDatabaseId', 'semanticModelId', 'assistantModelId', 'dataAgentId', 'starterReportId', 'modelConnectionId', 'assistantConnectionId'];
    const ids = Object.fromEntries(keys.map((key) => [key, tenant.fabric[key]]));
    for (const key of forget) delete tenant.fabric[key];
    const itemsBefore = (await account.listItems(ws)).map((i) => i.id).sort();
    const accountsBefore = (await (await kit.crm.forTenant(tenant)).counts()).accounts;

    const renamed = await kit.provisioner.provision(tenant.id);
    assert.equal(renamed.status, 'ready', renamed.error);
    assert.deepEqual(stepStatus(renamed).filter(([, status]) => !['done', 'skipped'].includes(status)), [], 'every step done');

    // The same items under the current names: nothing created, nothing removed.
    const items = await account.listItems(ws);
    assert.deepEqual(items.map((i) => i.id).sort(), itemsBefore);
    for (const key of keys) assert.equal(renamed.fabric[key], ids[key], `${key} is the one deployed before`);
    const nameOf = Object.fromEntries(items.map((i) => [i.id, i.displayName]));
    assert.equal(nameOf[ids.crmDatabaseId], CORE_ITEMS.sqlDatabase.name);
    assert.equal(nameOf[ids.semanticModelId], MODEL_NAME);
    assert.equal(nameOf[ids.assistantModelId], ASSISTANT_MODEL_NAME);
    assert.equal(nameOf[ids.dataAgentId], CORE_ITEMS.dataAgent.name);

    // The same connection under its current name, still bound to both models, and no other.
    const current = `${kit.config.productName} OneLake ${ws.slice(0, 8)}${suffixed ? ` ${tenant.identity.appId.slice(0, 8)}` : ''}`;
    assert.deepEqual(connectionsOf(kit, ws).map((c) => [c.id, c.displayName]), [[ids.modelConnectionId, current]]);
    const { bindings } = kit.fabric.inspect();
    for (const model of [ids.semanticModelId, ids.assistantModelId]) assert.equal(bindings[model].connectionId, ids.modelConnectionId);

    // The starter report still reads the same model, and the CRM still has every row, the newest included.
    const [report] = await account.pbiListReports(ws);
    assert.equal(report.id, ids.starterReportId);
    assert.equal(report.datasetId, ids.semanticModelId);
    const repo = await kit.crm.forTenant(renamed);
    assert.equal(renamed.fabric.crm.sqlDatabaseId, ids.crmDatabaseId);
    assert.equal((await repo.counts()).accounts, accountsBefore, 'no rows lost or loaded again');
    assert.equal((await repo.scoped(null).getAccount(earlier.marker.id))?.name, earlier.marker.name);

    // The definitions name the product as it is now.
    const model = (await account.getItemDefinition(ws, ids.semanticModelId)).definition;
    const expressions = decodePayload(model.parts.find((p) => p.path === 'definition/expressions.tmdl').payload);
    assert.ok(expressions.includes(DIRECT_LAKE_EXPRESSION) && !expressions.includes(LEGACY_PRODUCT_NAMES[0]), expressions);
    const source = agentModelSource((await account.getItemDefinition(ws, ids.dataAgentId)).definition);
    assert.deepEqual([source.displayName, source.artifactId], [ASSISTANT_MODEL_NAME, ids.assistantModelId]);
    assert.equal(renamed.identity.displayName, entraDisplayName(kit.config, renamed));

    // And the run says what it did.
    const detail = (key) => renamed.steps[key].detail;
    assert.equal(detail('crm-database'), `Renamed ${earlier.database} to ${CORE_ITEMS.sqlDatabase.name}`);
    assert.equal(detail('semantic-model'), `Renamed ${LEGACY_ITEM_NAMES.reportsModel[0]} to ${MODEL_NAME}; Updated ${MODEL_NAME} to the current version`);
    assert.equal(detail('model-connection'), `Renamed ${earlier.connection} to ${current}; framed on the latest data`);
    assert.ok(detail('assistant-model').startsWith(`Renamed ${LEGACY_ITEM_NAMES.assistantModel[0]} to ${ASSISTANT_MODEL_NAME}; Updated ${ASSISTANT_MODEL_NAME} to the current version; Uses ${current}`), detail('assistant-model'));
    assert.equal(detail('data-agent'), `Renamed ${LEGACY_ITEM_NAMES.dataAgent[0]} to ${CORE_ITEMS.dataAgent.name}; Updated ${CORE_ITEMS.dataAgent.name} to the current ${ASSISTANT_MODEL_NAME} and published it`);
    assert.ok(detail('service-account').endsWith(`renamed its app registration ${LEGACY_PRODUCT_NAMES[0]} service account - ${name} (${renamed.identity.name}) to ${renamed.identity.displayName}`), detail('service-account'));

    // A second run finds everything as it is.
    const again = await kit.provisioner.provision(tenant.id);
    assert.equal(again.status, 'ready', again.error);
    assert.equal(again.steps['crm-database'].detail, `${CORE_ITEMS.sqlDatabase.name} exists`);
    assert.match(again.steps['semantic-model'].detail, /up to date/);
    assert.match(again.steps['model-connection'].detail, /^Uses /);
    assert.match(again.steps['data-agent'].detail, /up to date/);
    assert.equal(connectionsOf(kit, ws).length, 1);
  }
});

test("when Fabric won't rename the CRM database or the connection, nothing is lost: the database keeps its earlier name and a new connection replaces the old one", async () => {
  const fabric = createMockFabric();
  const as = fabric.as;
  let refusing = false;
  const refuse = (what) => {
    throw new FabricApiError(`PATCH ${what} failed (HTTP 400, InvalidRequest): this can't be renamed.`, { upstreamStatus: 400, code: 'InvalidRequest' });
  };
  fabric.as = (principal) => {
    const client = as(principal);
    if (!refusing) return client;
    return {
      ...client,
      async updateItem(workspaceId, itemId, update) {
        const database = (await client.listItems(workspaceId, 'SQLDatabase')).some((i) => i.id === itemId);
        return database ? refuse('/items (SQL database)') : client.updateItem(workspaceId, itemId, update);
      },
      updateConnection: async () => refuse('/connections'),
    };
  };
  const kit = provisioningKit({ fabric });
  const tenant = await kit.provisionNew({ name: 'Fabrikam' });
  const ws = tenant.fabric.workspaceId;
  const earlier = await rewindToEarlierNames(kit, tenant, as(tenant.identity.objectId));
  const before = { database: tenant.fabric.crmDatabaseId, connection: tenant.fabric.modelConnectionId };

  refusing = true;
  const converged = await kit.provisioner.provision(tenant.id);
  assert.equal(converged.status, 'ready', converged.error);

  // The database: kept, with its data, under the name Fabric won't change.
  assert.equal(converged.steps['crm-database'].status, 'warning');
  assert.equal(converged.steps['crm-database'].detail, `Kept ${LEGACY_ITEM_NAMES.crmDatabase[0]}: Fabric didn't rename it to ${CORE_ITEMS.sqlDatabase.name} (HTTP 400, InvalidRequest)`);
  const account = as(tenant.identity.objectId);
  assert.deepEqual((await account.listItems(ws, 'SQLDatabase')).map((d) => [d.id, d.displayName]), [[before.database, LEGACY_ITEM_NAMES.crmDatabase[0]]], 'never a second database');
  assert.equal(converged.fabric.crm.sqlDatabaseId, before.database);
  assert.ok(await (await kit.crm.forTenant(converged)).scoped(null).getAccount(earlier.marker.id), 'the data is where it was');
  assert.equal((await account.listItems(ws, 'SemanticModel')).find((m) => m.id === converged.fabric.semanticModelId).displayName, MODEL_NAME, 'the rest is renamed');

  // The connection: a new one under the current name, both models bound to it, and the old one deleted.
  const current = `${kit.config.productName} OneLake ${ws.slice(0, 8)}`;
  assert.deepEqual(connectionsOf(kit, ws).map((c) => c.displayName), [current]);
  assert.notEqual(converged.fabric.modelConnectionId, before.connection);
  assert.equal(converged.fabric.assistantConnectionId, converged.fabric.modelConnectionId);
  const { bindings } = kit.fabric.inspect();
  for (const model of [converged.fabric.semanticModelId, converged.fabric.assistantModelId]) assert.equal(bindings[model].connectionId, converged.fabric.modelConnectionId);
  assert.equal(converged.fabric.replacedConnections, undefined, 'nothing left to delete');
  assert.ok(converged.steps['model-connection'].detail.includes(`replaces ${earlier.connection}, which Fabric didn't rename`), converged.steps['model-connection'].detail);

  const again = await kit.provisioner.provision(tenant.id);
  assert.equal(again.status, 'ready', again.error);
  assert.match(again.steps['model-connection'].detail, /^Uses /);
  assert.equal(connectionsOf(kit, ws).length, 1);
});

test("a connection Fabric won't rename is deleted only once no model is bound to it, even when the registry lost track of one", async () => {
  const fabric = createMockFabric();
  const as = fabric.as;
  const failing = new Set();
  let refusing = false;
  fabric.as = (principal) => {
    const client = as(principal);
    if (!refusing) return client;
    return {
      ...client,
      updateConnection: async () => {
        throw new FabricApiError("PATCH /connections failed (HTTP 400, InvalidRequest): this can't be renamed.", { upstreamStatus: 400, code: 'InvalidRequest' });
      },
      async updateItemDefinition(workspaceId, itemId, definition) {
        if (failing.has(itemId)) throw new FabricApiError('POST /updateDefinition failed (HTTP 500).', { upstreamStatus: 500 });
        return client.updateItemDefinition(workspaceId, itemId, definition);
      },
    };
  };
  const kit = provisioningKit({ fabric });
  const live = () => kit.fabric.inspect();
  const cases = [
    // The registry lost the assistant model's connection, and the edition no longer includes the assistant.
    { name: 'Fabrikam', plan: 'standard' },
    // The registry's connection for the assistant model is out of date, and it lost the model, which is still under its
    // earlier name. The assistant step then fails.
    { name: 'Contoso', staleConnection: true, earlierName: true, assistantFails: true },
  ];
  for (const { name, plan, staleConnection, earlierName, assistantFails } of cases) {
    refusing = false;
    const tenant = await kit.provisionNew({ name });
    assert.equal(tenant.status, 'ready', tenant.error);
    const ws = tenant.fabric.workspaceId;
    const account = as(tenant.identity.objectId);
    const { semanticModelId: reports, assistantModelId: assistant, modelConnectionId: old } = tenant.fabric;
    await account.updateConnection(old, { connectivityType: 'ShareableCloud', displayName: `${LEGACY_PRODUCT_NAMES[0]} OneLake ${ws.slice(0, 8)}` });
    if (staleConnection) tenant.fabric.assistantConnectionId = '00000000-0000-4000-8000-0000000000c1';
    else delete tenant.fabric.assistantConnectionId;
    if (earlierName) {
      await account.updateItem(ws, assistant, { displayName: LEGACY_ITEM_NAMES.assistantModel[0] });
      delete tenant.fabric.assistantModelId;
    }
    if (assistantFails) {
      tenant.fabric.assistantModelFingerprint = 'earlier';
      failing.add(assistant);
    }
    if (plan) tenant.plan = plan;
    await kit.store.save(tenant);

    // The reports model moves to a new connection; the old one stays while the assistant's model is bound to it.
    refusing = true;
    const first = await kit.provisioner.provision(tenant.id);
    assert.equal(first.status, assistantFails ? 'failed' : 'ready', first.error);
    assert.equal(first.steps['model-connection'].status, 'done');
    assert.equal(first.steps['assistant-model'].status, assistantFails ? 'failed' : 'retained');
    const replacement = first.fabric.modelConnectionId;
    assert.notEqual(replacement, old);
    assert.equal(live().bindings[reports].connectionId, replacement);
    assert.ok(live().connections[old], `${name}: not deleted while the assistant's model is bound to it`);
    assert.equal(live().bindings[assistant]?.connectionId, old);
    assert.deepEqual(first.fabric.replacedConnections, [old], 'left for a later run');

    // Once the assistant step has moved its model as well, the old connection goes.
    failing.clear();
    tenant.plan = 'enterprise';
    await kit.store.save(tenant);
    const second = await kit.provisioner.provision(tenant.id);
    assert.equal(second.status, 'ready', second.error);
    assert.equal(live().connections[old], undefined, `${name}: deleted once no model uses it`);
    assert.equal(second.fabric.replacedConnections, undefined);
    assert.deepEqual(connectionsOf(kit, ws).map((c) => c.id), [replacement]);
    for (const model of [reports, assistant]) assert.equal(live().bindings[model].connectionId, replacement);
    assert.equal(second.fabric.assistantConnectionId, replacement);
  }
});
