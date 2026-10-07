import assert from 'node:assert/strict';
import { test } from 'node:test';
import { FabricApiError } from '../src/fabric/client.js';
import { MOCK_TEMPLATE_ID } from '../src/fabric/mock.js';
import { auditTenant } from '../src/platform/audit.js';
import { IdentityError, createIdentityBroker } from '../src/platform/identities.js';
import { createProvisioner } from '../src/platform/provisioner.js';
import { createEmbedConfig, listReporting } from '../src/platform/reporting.js';
import { createMemorySecretStore } from '../src/platform/secrets.js';
import { FAST, makePlatform, provisioningKit } from './support.js';

// Tenant isolation. The Fabric emulator holds every identity to its workspace roles, so these tests fail if any
// customer's work could reach another customer's workspace, or if the platform kept more access than it needs.

const GUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const OPS = { id: '11111111-2222-4333-8444-555555555555', type: 'Group' };
const denied = (error) => [403, 404].includes(error.upstreamStatus);

async function twoCustomers(config = {}) {
  const kit = provisioningKit({ config: { templateWorkspaceId: MOCK_TEMPLATE_ID, ...config } });
  const fabrikam = await kit.provisionNew({ name: 'Fabrikam' });
  const contoso = await kit.provisionNew({ name: 'Contoso' });
  assert.equal(fabrikam.status, 'ready', fabrikam.error);
  assert.equal(contoso.status, 'ready', contoso.error);
  return { kit, fabrikam, contoso };
}

test("each customer's service account is Admin of its own workspace only and can't reach another customer's", async () => {
  const { kit, fabrikam, contoso } = await twoCustomers();
  const { roleAssignments } = kit.fabric.inspect();
  for (const [me, other] of [
    [fabrikam, contoso],
    [contoso, fabrikam],
  ]) {
    const account = me.identity.objectId;
    const memberships = Object.entries(roleAssignments).flatMap(([workspaceId, list]) => list.filter((a) => a.principal.id === account).map((a) => [workspaceId, a.role]));
    assert.deepEqual(memberships, [[me.fabric.workspaceId, 'Admin']], `${me.identity.name} has exactly one role, in its own workspace`);

    const client = kit.fabric.as(account);
    const theirs = other.fabric;
    assert.deepEqual((await client.listWorkspaces()).map((w) => w.id), [me.fabric.workspaceId]);
    await assert.rejects(client.getWorkspace(theirs.workspaceId), denied);
    await assert.rejects(client.listItems(theirs.workspaceId), denied);
    await assert.rejects(client.getItemDefinition(theirs.workspaceId, theirs.semanticModelId), denied);
    await assert.rejects(client.askDataAgent(theirs.workspaceId, theirs.dataAgentId, 'How many accounts are there?'), denied);
    await assert.rejects(client.pbiGenerateToken({ datasets: [{ id: theirs.semanticModelId }] }), denied);
    await assert.rejects(client.addRoleAssignment(theirs.workspaceId, { id: account, type: 'ServicePrincipal' }, 'Viewer'), denied);
    await assert.rejects(client.deleteWorkspace(theirs.workspaceId), denied);
    await assert.rejects(client.getWorkspace(MOCK_TEMPLATE_ID), denied, 'the template workspace stays with the platform');
    assert.deepEqual((await client.listConnections()).map((c) => c.id), [me.fabric.modelConnectionId], 'it sees its own connection only');
    await assert.rejects(client.updateItem(theirs.workspaceId, theirs.semanticModelId, { displayName: 'renamed' }), denied);
    await assert.rejects(client.updateConnection(theirs.modelConnectionId, { connectivityType: 'ShareableCloud', displayName: 'renamed' }), denied);
  }
});

test('renaming takes write access: a Viewer cannot rename an item, and only its owner can rename a connection', async () => {
  const kit = provisioningKit({ config: { opsPrincipal: OPS } });
  const tenant = await kit.provisionNew();
  const ws = tenant.fabric.workspaceId;
  const owner = kit.fabric.as(tenant.identity.objectId);
  await assert.rejects(kit.fabric.as(OPS.id).updateItem(ws, tenant.fabric.semanticModelId, { displayName: 'renamed' }), (error) => error.upstreamStatus === 403);
  await assert.rejects(kit.fabric.updateConnection(tenant.fabric.modelConnectionId, { connectivityType: 'ShareableCloud', displayName: 'renamed' }), (error) => error.upstreamStatus === 404);
  await assert.rejects(owner.updateConnection(tenant.fabric.modelConnectionId, { displayName: 'renamed' }), (error) => error.upstreamStatus === 400, 'the request names the connectivity type');
  const [twin] = (await owner.listItems(ws, 'SemanticModel')).filter((m) => m.id === tenant.fabric.assistantModelId);
  await assert.rejects(owner.updateItem(ws, tenant.fabric.semanticModelId, { displayName: twin.displayName }), (error) => error.upstreamStatus === 409, 'names are unique per item type');
  assert.equal((await owner.updateItem(ws, tenant.fabric.semanticModelId, { displayName: 'renamed' })).id, tenant.fabric.semanticModelId);
  assert.equal((await owner.updateConnection(tenant.fabric.modelConnectionId, { connectivityType: 'ShareableCloud', displayName: 'renamed' })).displayName, 'renamed');
});

test("defence in depth: if the registry mixed up two customers' accounts, Fabric refuses instead of leaking", async () => {
  const { kit, fabrikam, contoso } = await twoCustomers();
  const confused = { ...fabrikam, identity: contoso.identity };
  const client = await kit.identities.fabricFor(confused);
  const [report] = await kit.fabric.pbiListReports(fabrikam.fabric.workspaceId);
  await assert.rejects(listReporting({ fabric: client, tenant: confused }), denied);
  await assert.rejects(createEmbedConfig({ fabric: client, tenant: confused, mode: 'view', reportId: report.id }), denied);
});

test("a customer's requests run as that customer's own service account, inside its own workspace", async () => {
  const { fabric, admin, addCustomer, signIn } = makePlatform();
  const fabrikamId = await addCustomer('Fabrikam', 'enterprise', 'fabrikam.com');
  await addCustomer('Contoso', 'enterprise', 'contoso.com');
  const detail = (await admin({ url: `/api/admin/tenants/${fabrikamId}` })).json();
  const ana = await signIn('ana@fabrikam.com');

  fabric.clearCallLog();
  const { reports, models } = (await ana({ url: '/api/me/reports' })).json();
  assert.equal((await ana({ method: 'POST', url: '/api/me/embed', body: { mode: 'view', reportId: reports[0].id } })).status, 200);
  assert.equal((await ana({ method: 'POST', url: '/api/me/embed', body: { mode: 'edit', reportId: reports[0].id } })).status, 200);
  assert.equal((await ana({ method: 'POST', url: '/api/me/embed', body: { mode: 'create', datasetId: models[0].id } })).status, 200);
  assert.equal((await ana({ method: 'POST', url: '/api/me/ask', body: { question: 'How many open opportunities are there?' } })).status, 200);

  const log = fabric.callLog();
  assert.ok(log.length >= 6, `expected Fabric calls, got ${log.length}`);
  for (const entry of log) {
    assert.equal(entry.principal, detail.identity.objectId, `"${entry.op}" ran as ${entry.principal}`);
    assert.equal(entry.workspaceId, detail.fabric.workspaceId, `"${entry.op}" stayed in Fabrikam's workspace`);
    assert.ok(entry.allowed, `"${entry.op}" was allowed`);
  }
});

test("another customer's report and model IDs are refused, even from a signed-in user", async () => {
  const { admin, addCustomer, signIn } = makePlatform();
  await addCustomer('Fabrikam', 'enterprise', 'fabrikam.com');
  const contosoId = await addCustomer('Contoso', 'enterprise', 'contoso.com');
  const theirs = (await admin({ url: `/api/admin/tenants/${contosoId}/reports` })).json();
  const ana = await signIn('ana@fabrikam.com');
  assert.equal((await ana({ method: 'POST', url: '/api/me/embed', body: { mode: 'view', reportId: theirs.reports[0].id } })).status, 404);
  assert.equal((await ana({ method: 'POST', url: '/api/me/embed', body: { mode: 'edit', reportId: theirs.reports[0].id } })).status, 404);
  assert.equal((await ana({ method: 'POST', url: '/api/me/embed', body: { mode: 'create', datasetId: theirs.datasets[0].id } })).status, 404);
});

test('moving or removing a sign-in domain ends existing sessions at once', async () => {
  const { admin, addCustomer, signIn } = makePlatform();
  const fabrikamId = await addCustomer('Fabrikam', 'standard', 'fabrikam.com');
  const contosoId = await addCustomer('Contoso', 'standard', 'contoso.com');
  const ana = await signIn('ana@fabrikam.com');
  assert.equal((await ana({ url: '/api/me' })).json().company, 'Fabrikam');

  assert.equal((await admin({ method: 'PATCH', url: `/api/admin/tenants/${fabrikamId}`, body: { domains: [] } })).status, 200);
  assert.equal((await ana({ url: '/api/me' })).status, 401, 'the session ends when its domain is removed');
  assert.equal((await ana({ url: '/api/me/crm/summary' })).status, 401);

  assert.equal((await admin({ method: 'PATCH', url: `/api/admin/tenants/${contosoId}`, body: { domains: ['contoso.com', 'fabrikam.com'] } })).status, 200);
  assert.equal((await ana({ url: '/api/me' })).status, 401, "the old cookie names Fabrikam, which doesn't own the domain anymore");
  const again = await signIn('ana@fabrikam.com');
  assert.equal((await again({ url: '/api/me' })).json().company, 'Contoso');
});

test('customers never see Fabric errors, IDs or account names; operators get the details', async () => {
  const { app, admin, addCustomer, signIn } = makePlatform();
  const id = await addCustomer('Fabrikam', 'enterprise', 'fabrikam.com', { addons: ['integration'] });
  const ana = await signIn('ana@fabrikam.com');
  const leaky = new FabricApiError('Workspace 1a2b3c4d-1111-4222-8333-444444444444: item 5e6f7a8b-1111-4222-8333-444444444444 is not accessible to fabrikamsa', {
    upstreamStatus: 500,
    code: 'InternalError',
  });
  const realFabricFor = app.identities.fabricFor;
  const logged = [];
  const consoleError = console.error;
  console.error = (...args) => logged.push(args.map((a) => (a instanceof Error ? a.message : String(a))).join(' '));
  try {
    app.identities.fabricFor = async () => {
      throw leaky;
    };
    for (const request of [{ url: '/api/me/reports' }, { url: '/api/me/data' }, { method: 'POST', url: '/api/me/embed', body: { mode: 'view', reportId: 'r1' } }]) {
      const res = await ana(request);
      assert.equal(res.status, 503, `${request.url}: ${res.text}`);
      assert.doesNotMatch(res.text, GUID, `${request.url} leaks an ID`);
      assert.doesNotMatch(res.text, /fabrikamsa|workspace|fabric|InternalError/i, `${request.url} leaks platform details`);
    }
    app.identities.fabricFor = async () => {
      throw new IdentityError("The secret for fabrikamsa isn't in the secret store.");
    };
    const missingSecret = await ana({ url: '/api/me/data' });
    assert.equal(missingSecret.status, 503);
    assert.doesNotMatch(missingSecret.text, /fabrikamsa|secret/i);
    assert.match(missingSecret.json().ref, /^[0-9a-f]{8}$/, 'a reference support can find in the server log');
    assert.ok(logged.some((line) => line.includes(missingSecret.json().ref) && line.includes('/api/me/data')));

    app.identities.fabricFor = async () => {
      throw leaky;
    };
    const operatorView = await admin({ url: `/api/admin/tenants/${id}/reports` });
    assert.equal(operatorView.status, 502);
    assert.match(operatorView.json().error, /not accessible to fabrikamsa/);
  } finally {
    app.identities.fabricFor = realFabricFor;
    console.error = consoleError;
  }
});

test('release mode: the platform hands over, keeps no standing access, and later runs still work', async () => {
  const { kit, fabrikam, contoso } = await twoCustomers({ platformWorkspaceAccess: 'release' });
  for (const tenant of [fabrikam, contoso]) {
    assert.equal(tenant.steps['platform-access'].status, 'done', tenant.steps['platform-access'].detail);
    assert.equal(tenant.fabric.platformReleased, true);
    await assert.rejects(kit.fabric.getWorkspace(tenant.fabric.workspaceId), denied, 'the platform has no access');
    const roles = Object.fromEntries(kit.fabric.inspect().roleAssignments[tenant.fabric.workspaceId].map((a) => [a.principal.id, a.role]));
    assert.deepEqual(roles, { [tenant.identity.objectId]: 'Admin', [tenant.fabric.workspaceIdentity.servicePrincipalId]: 'Contributor' });
  }
  assert.deepEqual((await kit.fabric.listWorkspaces()).map((w) => w.id), [MOCK_TEMPLATE_ID], 'the platform keeps only the template');

  // A re-run (a new model version, a retry) works through the service account and changes nothing.
  const itemsBefore = Object.keys(kit.fabric.inspect().items).length;
  const again = await kit.provisioner.provision(fabrikam.id);
  assert.equal(again.status, 'ready', again.error);
  assert.equal(Object.keys(kit.fabric.inspect().items).length, itemsBefore);
  await assert.rejects(kit.fabric.getWorkspace(fabrikam.fabric.workspaceId), denied);

  // Moving to a dedicated capacity needs the platform's capacity rights: it gets access for that run only.
  again.capacityId = 'dedicated-capacity';
  await kit.store.save(again);
  await assert.rejects(kit.fabric.as(fabrikam.identity.objectId).assignToCapacity(fabrikam.fabric.workspaceId, 'dedicated-capacity'), denied, 'service accounts hold no capacity rights');
  const moved = await kit.provisioner.provision(fabrikam.id);
  assert.equal(moved.status, 'ready', moved.error);
  assert.equal(kit.fabric.inspect().workspaces[fabrikam.fabric.workspaceId].capacityId, 'dedicated-capacity');
  assert.ok(moved.activity.some((a) => a.level === 'audit' && /temporary access to move the workspace/.test(a.message)), 'the temporary access is logged');
  await assert.rejects(kit.fabric.getWorkspace(fabrikam.fabric.workspaceId), denied, 'released again at the end of the run');

  const audit = await auditTenant({ tenant: moved, fabric: kit.fabric, identities: kit.identities, config: kit.config });
  assert.ok(audit.ok, JSON.stringify(audit.checks.filter((c) => c.status !== 'pass')));
  assert.equal(audit.checks.find((c) => c.key === 'role:platform').status, 'pass');

  // A kept workspace goes back to the control plane; deleting one needs no platform access at all.
  await kit.provisioner.deprovision(contoso.id, { keepWorkspace: true });
  assert.ok(await kit.fabric.getWorkspace(contoso.fabric.workspaceId));
  await kit.provisioner.deprovision(fabrikam.id);
  const after = kit.fabric.inspect();
  assert.equal(after.workspaces[fabrikam.fabric.workspaceId], undefined);
  assert.equal(after.connections[fabrikam.fabric.modelConnectionId], undefined);
});

test('a customer the platform built before it had a service account is handed over: own connection, own models, nothing left behind', async () => {
  // As in the live pilot before an Entra admin acted: no service accounts, so the platform identity built everything.
  const before = provisioningKit({ config: { templateWorkspaceId: MOCK_TEMPLATE_ID, identity: { mode: 'off', autoCreate: false, fabricGroupId: '' } } });
  const built = await before.provisionNew({ name: 'Fabrikam' });
  assert.equal(built.status, 'ready', built.error);
  const oldConnection = built.fabric.modelConnectionId;
  assert.equal(built.fabric.assistantConnectionId, oldConnection, 'both models share the platform-owned connection');

  // Then service accounts and release mode are turned on.
  const config = { ...before.config, identity: { mode: 'preferred', autoCreate: false, fabricGroupId: '' }, platformWorkspaceAccess: 'release' };
  const identities = createIdentityBroker({ config, platformTokens: null, platformFabric: before.fabric, secrets: createMemorySecretStore() });
  const provisioner = createProvisioner({ fabric: before.fabric, store: before.store, config, identities, crm: before.crm, ...FAST });
  const handed = await provisioner.provision(built.id);
  assert.equal(handed.status, 'ready', handed.error);
  const account = handed.identity.objectId;
  const state = before.fabric.inspect();
  const newConnection = handed.fabric.modelConnectionId;
  assert.notEqual(newConnection, oldConnection);
  assert.equal(state.connections[newConnection].owner, account, "the service account's own connection");
  for (const model of [handed.fabric.semanticModelId, handed.fabric.assistantModelId]) {
    assert.equal(state.items[model].configuredBy, account, 'it owns both models');
    assert.equal(state.bindings[model].connectionId, newConnection, 'and both read through its connection');
  }
  assert.equal(state.connections[oldConnection], undefined, "the platform deleted the connection it no longer uses");
  assert.deepEqual(handed.fabric.retiredConnections, []);
  await assert.rejects(before.fabric.getWorkspace(handed.fabric.workspaceId), denied, 'and then gave up the workspace');

  const again = await provisioner.provision(built.id);
  assert.equal(again.status, 'ready', again.error);
  assert.equal(again.fabric.modelConnectionId, newConnection, 'a later run keeps the same connection');
});

test('the access check flags drift: unmanaged people, extra rights, missing roles and items', async () => {
  const kit = provisioningKit({ config: { opsPrincipal: OPS } });
  const tenant = await kit.provisionNew();
  const check = () => auditTenant({ tenant: kit.store.get(tenant.id), fabric: kit.fabric, identities: kit.identities, config: kit.config });
  const byKey = (report) => Object.fromEntries(report.checks.map((c) => [c.key, c]));

  const clean = await check();
  assert.ok(clean.ok, JSON.stringify(clean.checks.filter((c) => c.status === 'fail')));
  const cleanKeys = byKey(clean);
  for (const key of ['service-account', 'role:service', 'role:workspace', 'role:support', 'model-connection', 'capacity', 'crm-schema', 'item:dataAgentId']) {
    assert.equal(cleanKeys[key]?.status, 'pass', `${key}: ${cleanKeys[key]?.detail}`);
  }
  assert.equal(cleanKeys['role:platform'].status, 'info', 'keep mode reports the standing access');

  const ws = tenant.fabric.workspaceId;
  const workspaceIdentity = tenant.fabric.workspaceIdentity.servicePrincipalId;
  await kit.fabric.addRoleAssignment(ws, { id: 'aaaaaaaa-0000-4000-8000-000000000001', type: 'User', displayName: 'Pat Admin (break-glass)' }, 'Admin');
  const current = kit.fabric.inspect().roleAssignments[ws].find((a) => a.principal.id === workspaceIdentity);
  await kit.fabric.deleteRoleAssignment(ws, current.id);
  await kit.fabric.addRoleAssignment(ws, { id: workspaceIdentity, type: 'ServicePrincipal' }, 'Admin');
  await kit.fabric.deleteItem(ws, tenant.fabric.dataAgentId);

  const drifted = await check();
  const keys = byKey(drifted);
  assert.equal(drifted.ok, false);
  assert.equal(keys['role:workspace'].status, 'warn');
  assert.match(keys['role:workspace'].detail, /Admin, more than it needs: Contributor is enough/);
  assert.match(drifted.checks.find((c) => c.title === 'Unmanaged access').detail, /Pat Admin \(break-glass\) \(User\) has Admin/);
  assert.equal(keys['item:dataAgentId'].status, 'fail');

  const account = kit.fabric.inspect().roleAssignments[ws].find((a) => a.principal.id === tenant.identity.objectId);
  await kit.fabric.deleteRoleAssignment(ws, account.id);
  const locked = byKey(await check());
  assert.equal(locked.roles.status, 'fail', "the service account can't even read the roles");
});
