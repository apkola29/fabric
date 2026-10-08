import { randomUUID } from 'node:crypto';
import { FabricApiError } from './client.js';
import { parseCsv } from '../util/csv.js';
import { decodePayload, jsonPart } from '../util/definition.js';
import { createJsonWriter, readJsonFile } from '../util/files.js';
import { MODEL_NAME, buildSemanticModelDefinition } from '../crm/workload.js';
import { selectedTables } from '../platform/agent.js';
import { CORE_ITEMS } from '../platform/plans.js';

// In-memory stand-in for Fabric with the same interface as the live client.
//
// Every client acts as one principal (the platform identity by default; `as(principalId)` gives another principal's
// view of the same tenant) and is held to Fabric's workspace roles, so tests catch least-privilege mistakes:
//   Viewer: read workspace metadata, items and reports  Contributor: create and change items and data
//   Member: add Members and lower                        Admin: add or remove Admins, update or delete the workspace
// The creator of a workspace becomes its Admin. Connections are visible only to their owner. A semantic model's
// connection can only be bound by its owner (the identity that created it or took it over). Placing a workspace on a
// capacity also needs rights on that capacity, which only the platform identity has.

export const MOCK_TEMPLATE_ID = 'mock-template';
export const MOCK_PLATFORM_PRINCIPAL = '0a1b2c3d-0000-4000-8000-00000000a11a';
const TEMPLATE_NAME = 'Template - Platform app';
const STATE_VERSION = 2;
const ROLE_RANK = { Viewer: 1, Contributor: 2, Member: 3, Admin: 4 };

const T = Object.freeze({
  database: '0b1d2c3e-0000-4000-8000-000000000001',
  model: '0b1d2c3e-0000-4000-8000-000000000006',
  report: '0b1d2c3e-0000-4000-8000-000000000007',
});

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const sameId = (a, b) => String(a || '').toLowerCase() === String(b || '').toLowerCase();
const notFound = (what) => new FabricApiError(`${what} not found.`, { upstreamStatus: 404, code: 'EntityNotFound' });
const forbidden = (message) => new FabricApiError(message, { upstreamStatus: 403, code: 'InsufficientPrivileges' });
const conflict = (message, code) => new FabricApiError(message, { upstreamStatus: 409, code });
const badRequest = (message, code = 'BadRequest') => new FabricApiError(message, { upstreamStatus: 400, code });
const publicItem = ({ id, type, displayName, description, workspaceId }) => ({ id, type, displayName, description, workspaceId });

// A "golden template" workspace: the reports every customer gets, bound to the template's own copy of the model.
// Stamping copies the reports and re-points them at the customer's Platform app Insights model.
function templateItems() {
  const ws = MOCK_TEMPLATE_ID;
  const pbir = {
    version: '4.0',
    datasetReference: {
      byConnection: {
        connectionString: `Data Source="powerbi://api.powerbi.com/v1.0/myorg/${TEMPLATE_NAME}";initial catalog="${MODEL_NAME}";integrated security=ClaimsToken;semanticmodelid=${T.model}`,
      },
    },
  };
  const items = [
    {
      id: T.database,
      type: 'SQLDatabase',
      displayName: CORE_ITEMS.sqlDatabase.name,
      description: 'Template CRM database',
      properties: { serverFqdn: 'template-mock.database.fabric.microsoft.com,1433', databaseName: `${CORE_ITEMS.sqlDatabase.name}-${T.database}` },
    },
    { id: T.model, type: 'SemanticModel', displayName: MODEL_NAME, description: 'Template copy of the model', configuredBy: MOCK_PLATFORM_PRINCIPAL, definition: buildSemanticModelDefinition({ workspaceId: ws, sqlDatabaseId: T.database }).definition },
    {
      id: T.report,
      type: 'Report',
      displayName: 'Sales overview',
      description: 'Pipeline, revenue and activity overview',
      definition: { parts: [jsonPart('definition.pbir', pbir), jsonPart('report.json', { config: '{}', layoutOptimization: 0, sections: [{ name: 'Overview', displayName: 'Overview', visualContainers: [] }] })] },
    },
  ];
  return items.map(({ definition, ...rest }) => ({ item: { ...rest, workspaceId: ws }, definition }));
}

export function createMockFabric({ stateFile = null, latencyMs = 0, jobDurationMs = 2500, principal: defaultPrincipal = MOCK_PLATFORM_PRINCIPAL } = {}) {
  const state = {
    workspaces: {},
    items: {},
    definitions: {},
    roleAssignments: {},
    tables: {},
    jobs: {},
    connections: {},
    bindings: {},
    refreshes: {},
    ...(stateFile ? readJsonFile(stateFile, {}) : {}),
  };
  state.connections ||= {};
  state.bindings ||= {};
  state.refreshes ||= {};
  // Demo state saved before roles were enforced: give the platform identity the Admin role it had implicitly.
  if (state.version !== STATE_VERSION) {
    for (const id of Object.keys(state.workspaces)) {
      const list = (state.roleAssignments[id] ||= []);
      if (!list.some((a) => sameId(a.principal?.id, MOCK_PLATFORM_PRINCIPAL))) list.push(assignment({ id: MOCK_PLATFORM_PRINCIPAL, type: 'ServicePrincipal' }, 'Admin'));
    }
    for (const connection of Object.values(state.connections)) connection.owner ||= MOCK_PLATFORM_PRINCIPAL;
    for (const item of Object.values(state.items)) if (item.type === 'SemanticModel') item.configuredBy ||= MOCK_PLATFORM_PRINCIPAL;
    state.version = STATE_VERSION;
  }
  state.workspaces[MOCK_TEMPLATE_ID] = { id: MOCK_TEMPLATE_ID, displayName: TEMPLATE_NAME, description: 'Golden template (mock)', type: 'Workspace', capacityId: 'mock-capacity', capacityAssignmentProgress: 'Completed' };
  state.roleAssignments[MOCK_TEMPLATE_ID] = [assignment({ id: MOCK_PLATFORM_PRINCIPAL, type: 'ServicePrincipal' }, 'Admin')];
  for (const { item, definition } of templateItems()) {
    state.items[item.id] = item;
    if (definition) state.definitions[item.id] = definition;
  }

  const files = new Map();
  const calls = [];
  const tokens = [];
  const write = stateFile ? createJsonWriter(stateFile) : null;
  let saveTimer = null;
  const save = () => {
    if (!write) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => write(state).catch((error) => console.error(`Mock state not saved: ${error.message}`)), 50);
  };
  const pause = () => (latencyMs ? sleep(latencyMs * (0.5 + Math.random())) : Promise.resolve());
  const clone = (value) => (value === undefined ? undefined : structuredClone(value));

  function assignment(principal, role) {
    return { id: principal.id, principal: { id: principal.id, type: principal.type || 'ServicePrincipal', displayName: principal.displayName }, role };
  }

  const workspace = (id) => {
    const ws = state.workspaces[id];
    if (!ws) throw notFound(`Workspace ${id}`);
    return ws;
  };
  const itemIn = (workspaceId, id) => {
    const found = state.items[id];
    if (!found || found.workspaceId !== workspaceId) throw notFound(`Item ${id}`);
    return found;
  };
  const itemsIn = (workspaceId) => Object.values(state.items).filter((i) => i.workspaceId === workspaceId);
  const roleOf = (who, workspaceId) => (state.roleAssignments[workspaceId] || []).find((a) => sameId(a.principal?.id, who))?.role || null;

  function datasetIdOf(reportId) {
    const part = state.definitions[reportId]?.parts?.find((p) => p.path === 'definition.pbir');
    if (!part) return null;
    return /semanticmodelid=([0-9a-f-]{36})/i.exec(decodePayload(part.payload))?.[1] || null;
  }

  // Row-level security roles in a semantic model's definition: definition/roles/<name>.tmdl, starting "role <name>".
  function rolesOf(modelId) {
    return (state.definitions[modelId]?.parts || [])
      .filter((p) => p.path.startsWith('definition/roles/'))
      .map((p) => /^role\s+(?:'((?:[^']|'')*)'|(\S+))/m.exec(decodePayload(p.payload)))
      .filter(Boolean)
      .map((m) => (m[1] !== undefined ? m[1].replace(/''/g, "'") : m[2]));
  }

  // Like Power BI, a model with roles needs an effective identity with roles, and a model without roles refuses one.
  // Stricter than Power BI, which issues the token for a role name the model doesn't have (the query fails later):
  // here a typo fails at once.
  function checkIdentities(request) {
    const datasets = request.datasets || [];
    const identities = request.identities || [];
    for (const identity of identities) {
      for (const id of identity.datasets || []) if (!datasets.some((d) => sameId(d.id, id))) throw badRequest(`The effective identity names dataset ${id}, which isn't in the request.`, 'InvalidRequest');
    }
    for (const d of datasets) {
      const roles = rolesOf(d.id);
      const identity = identities.find((i) => (i.datasets || []).some((id) => sameId(id, d.id)));
      if (!roles.length) {
        if (identity) throw badRequest(`Creating embed token with effective identity is not supported for dataset ${d.id}, which has no row-level security.`, 'InvalidRequest');
        continue;
      }
      if (!identity) throw badRequest(`Creating embed token for accessing dataset ${d.id} requires effective identity to be provided.`, 'InvalidRequest');
      if (!identity.username) throw badRequest('The effective identity needs a username.', 'InvalidRequest');
      if (!identity.roles?.length) throw badRequest(`Creating embed token for accessing dataset ${d.id} requires roles to be included in the effective identity.`, 'InvalidRequest');
      const unknown = identity.roles.filter((r) => !roles.includes(r));
      if (unknown.length) throw badRequest(`Dataset ${d.id} has no role named ${unknown.join(', ')}.`, 'InvalidRequest');
    }
  }

  // A Direct Lake model's data source reference, as Fabric reports it: the OneLake location in its expression.
  function modelReference(modelId) {
    const part = state.definitions[modelId]?.parts?.find((p) => p.path === 'definition/expressions.tmdl');
    const url = part && /AzureStorage\.DataLake\("([^"]+)"/.exec(decodePayload(part.payload))?.[1];
    if (!url) return null;
    return { type: 'AzureDataLakeStorage', path: url.endsWith('/') ? url : `${url}/` };
  }

  // A semantic model's shared expressions (TMDL "expression <name> ="), and those its partitions read through.
  function expressionsOf(definition) {
    const tmdl = (definition?.parts || []).filter((p) => String(p.path || '').endsWith('.tmdl')).map((p) => decodePayload(p.payload || '')).join('\n');
    const names = (pattern) => [...tmdl.matchAll(pattern)].map(([, name]) => (/^'.*'$/.test(name) ? name.slice(1, -1).replace(/''/g, "'") : name));
    return { declared: names(/^expression\s+('(?:[^']|'')*'|[^\s=']+)\s*=/gm), read: names(/^\s*expressionSource:\s*(.+?)\s*$/gm) };
  }

  function buildGold(workspaceId) {
    const lakehouse = itemsIn(workspaceId).find((i) => i.type === 'Lakehouse');
    const accounts = lakehouse && state.tables[lakehouse.id]?.crm_accounts;
    if (!accounts) return;
    const counts = new Map();
    for (const row of accounts.sample) counts.set(row.industry || 'Unknown', (counts.get(row.industry || 'Unknown') || 0) + 1);
    state.tables[lakehouse.id].gold_account_summary = {
      name: 'gold_account_summary',
      columns: ['industry', 'accounts'],
      rowCount: counts.size,
      sample: [...counts].map(([industry, n]) => ({ industry, accounts: String(n) })),
    };
  }

  function answer(agentId, question) {
    const definition = state.definitions[agentId];
    const sources = (definition?.parts || []).filter((p) => /\/published\/[^/]+\/datasource\.json$/i.test(p.path)).map((p) => JSON.parse(decodePayload(p.payload)));
    const model = sources.find((s) => s.type === 'semantic_model');
    const lakehouseId = sources.find((s) => s.type !== 'semantic_model')?.artifactId || null;
    const tables = (lakehouseId && state.tables[lakehouseId]) || {};
    const known = selectedTables(definition).filter((name) => tables[name]);
    const friendly = (name) => {
      const words = name.replace(/^(crm|gold)_/, '').replace(/_/g, ' ');
      return words.charAt(0).toUpperCase() + words.slice(1);
    };
    const q = question.toLowerCase();
    const modelMessage = model
      ? `In demo mode I can see ${model.displayName} (${(model.elements || []).map((e) => e.display_name).join(', ')}), but I can't run queries. Connected to Fabric, I answer questions like this one.`
      : null;
    if (known.length === 0) return modelMessage || "I don't have any data to look at yet.";
    const mentioned = known.filter((name) => q.includes(name.toLowerCase()) || q.includes(friendly(name).toLowerCase()));
    if (mentioned.length && /how many|count|number of|rows/.test(q)) {
      return mentioned.map((name) => `${friendly(name)}: ${tables[name].rowCount.toLocaleString('en-US')} rows.`).join(' ');
    }
    if (mentioned.length) return mentioned.map((name) => `${friendly(name)} has the columns ${tables[name].columns.join(', ')}.`).join(' ');
    if (/table|data|what can|which|have|see/.test(q)) {
      return `I can see ${known.length} data sets: ${known.map((name) => `${friendly(name)} (${tables[name].rowCount.toLocaleString('en-US')} rows)`).join(', ')}.`;
    }
    return modelMessage || 'In this demo I can only count rows and list columns. Connected to your data, I answer questions like this one.';
  }

  function client(principal) {
    // Fabric hides workspaces a caller has no role in and refuses actions above its role.
    function authorize(workspaceId, minRole, op) {
      workspace(workspaceId);
      const role = roleOf(principal, workspaceId);
      calls.push({ principal, op, workspaceId, allowed: Boolean(role && ROLE_RANK[role] >= ROLE_RANK[minRole]) });
      if (!role) throw forbidden(`The caller has no role in workspace ${workspaceId}.`);
      if (ROLE_RANK[role] < ROLE_RANK[minRole]) throw forbidden(`The caller's ${role} role in workspace ${workspaceId} can't ${op}; it needs ${minRole}.`);
      return role;
    }
    const itemFor = (workspaceId, itemId, minRole, op) => {
      authorize(workspaceId, minRole, op);
      return itemIn(workspaceId, itemId);
    };
    const visibleConnection = (connectionId) => {
      const connection = state.connections[connectionId];
      if (!connection || !sameId(connection.owner, principal)) throw notFound(`Connection ${connectionId}`);
      return connection;
    };
    // Placing a workspace on a capacity also needs Contributor rights on that capacity. Only the platform identity
    // holds them; customer service accounts never do.
    function authorizeCapacity(capacityId) {
      const allowed = sameId(principal, MOCK_PLATFORM_PRINCIPAL) || (state.capacityContributors?.[capacityId] || []).some((p) => sameId(p, principal));
      calls.push({ principal, op: `use capacity ${capacityId}`, workspaceId: null, allowed });
      if (!allowed) throw forbidden(`The caller has no rights on capacity ${capacityId}.`);
    }

    return {
      kind: 'mock',
      principal,
      as: (other) => client(other),
      async principalId() {
        return principal;
      },

      async listCapacities() {
        await pause();
        return [{ id: 'mock-capacity', displayName: 'Mock capacity', sku: 'F2', region: 'Mock', state: 'Active' }];
      },
      // The tenant settings a well-set-up tenant has: the service principal settings limited to one security group, the
      // read-only admin APIs only to the platform identity's own group (so the validator can read these), no admin updates.
      async listTenantSettings() {
        await pause();
        const group = [{ graphId: '22222222-3333-4444-8555-666666666666', name: 'Platform app service principals' }];
        const platformOnly = [{ graphId: '33333333-4444-4555-8666-777777777777', name: 'Platform identity' }];
        return [
          { settingName: 'ServicePrincipalAccessPermissionAPIs', title: 'Service principals can call Fabric public APIs', enabled: true, enabledSecurityGroups: group },
          { settingName: 'ServicePrincipalAccessGlobalAPIs', title: 'Service principals can create workspaces, connections, and deployment pipelines', enabled: true, enabledSecurityGroups: group },
          { settingName: 'Embedding', title: 'Embed content in apps', enabled: true },
          { settingName: 'AllowServicePrincipalsUseReadAdminAPIs', title: 'Service principals can access read-only admin APIs', enabled: true, enabledSecurityGroups: platformOnly },
          { settingName: 'AllowServicePrincipalsUseWriteAdminAPIs', title: 'Service principals can access admin APIs used for updates', enabled: false },
        ];
      },
      async listWorkspaces() {
        await pause();
        return Object.values(state.workspaces).filter((w) => roleOf(principal, w.id)).map(clone);
      },
      async findWorkspaceByName(name) {
        await pause();
        return clone(Object.values(state.workspaces).find((w) => w.displayName === name && roleOf(principal, w.id)) || null);
      },
      async createWorkspace({ displayName, description, capacityId }) {
        await pause();
        // Workspace names are unique across the whole Fabric tenant, including workspaces the caller can't see.
        if (Object.values(state.workspaces).some((w) => w.displayName === displayName)) {
          throw conflict(`A workspace named ${displayName} already exists.`, 'WorkspaceNameAlreadyExists');
        }
        if (capacityId) authorizeCapacity(capacityId);
        const ws = { id: randomUUID(), displayName, description: description || '', type: 'Workspace' };
        if (capacityId) Object.assign(ws, { capacityId, capacityAssignmentProgress: 'Completed' });
        state.workspaces[ws.id] = ws;
        state.roleAssignments[ws.id] = [assignment({ id: principal, type: 'ServicePrincipal' }, 'Admin')];
        calls.push({ principal, op: 'create the workspace', workspaceId: ws.id, allowed: true });
        save();
        return clone(ws);
      },
      async getWorkspace(id) {
        await pause();
        authorize(id, 'Viewer', 'read the workspace');
        return clone(workspace(id));
      },
      async assignToCapacity(id, capacityId) {
        await pause();
        authorize(id, 'Admin', 'assign a capacity');
        authorizeCapacity(capacityId);
        Object.assign(workspace(id), { capacityId, capacityAssignmentProgress: 'Completed' });
        save();
        return null;
      },
      async deleteWorkspace(id) {
        await pause();
        if (id === MOCK_TEMPLATE_ID) throw badRequest('The template workspace is read-only in mock mode.');
        authorize(id, 'Admin', 'delete the workspace');
        for (const item of itemsIn(id)) {
          delete state.items[item.id];
          delete state.definitions[item.id];
          delete state.tables[item.id];
          delete state.bindings[item.id];
        }
        for (const [jobId, job] of Object.entries(state.jobs)) if (job.workspaceId === id) delete state.jobs[jobId];
        for (const key of files.keys()) if (key.startsWith(`${id}/`)) files.delete(key);
        delete state.workspaces[id];
        delete state.roleAssignments[id];
        save();
      },
      async listRoleAssignments(id) {
        await pause();
        authorize(id, 'Viewer', 'list role assignments');
        return clone(state.roleAssignments[id] || []);
      },
      async addRoleAssignment(id, member, role) {
        await pause();
        authorize(id, role === 'Admin' ? 'Admin' : 'Member', `add a ${role}`);
        if (!ROLE_RANK[role]) throw badRequest(`Unknown role ${role}.`);
        const list = (state.roleAssignments[id] ||= []);
        if (list.some((a) => sameId(a.principal.id, member.id))) {
          throw conflict('The principal already has a workspace role.', 'PrincipalAlreadyHasWorkspaceRolePermissions');
        }
        const created = assignment(member, role);
        list.push(created);
        save();
        return clone(created);
      },
      async deleteRoleAssignment(id, assignmentId) {
        await pause();
        authorize(id, 'Admin', 'remove a role assignment');
        const list = state.roleAssignments[id] || [];
        const target = list.find((a) => sameId(a.id, assignmentId));
        if (!target) throw notFound(`Role assignment ${assignmentId}`);
        if (target.role === 'Admin' && list.filter((a) => a.role === 'Admin').length === 1) {
          throw badRequest('A workspace needs at least one Admin.', 'LastAdminCannotBeRemoved');
        }
        state.roleAssignments[id] = list.filter((a) => a !== target);
        save();
      },
      async provisionWorkspaceIdentity(id) {
        await pause();
        authorize(id, 'Admin', 'provision the workspace identity');
        const ws = workspace(id);
        ws.workspaceIdentity ||= { applicationId: randomUUID(), servicePrincipalId: randomUUID() };
        save();
        return clone(ws.workspaceIdentity);
      },

      async listConnections() {
        await pause();
        return Object.values(state.connections).filter((c) => sameId(c.owner, principal)).map(({ owner, ...c }) => clone(c));
      },
      async createConnection(request) {
        await pause();
        // Connection names are unique in the Fabric tenant.
        if (Object.values(state.connections).some((c) => c.displayName === request.displayName)) {
          throw conflict(`A connection named ${request.displayName} already exists.`, 'DuplicateConnectionName');
        }
        const params = Object.fromEntries((request.connectionDetails?.parameters || []).map((p) => [p.name, p.value]));
        const connection = {
          id: randomUUID(),
          displayName: request.displayName,
          connectivityType: request.connectivityType,
          connectionDetails: { type: request.connectionDetails?.type, path: `${params.server || ''}${params.path || ''}` },
          privacyLevel: request.privacyLevel,
          credentialDetails: { credentialType: request.credentialDetails?.credentials?.credentialType, singleSignOnType: request.credentialDetails?.singleSignOnType },
          owner: principal,
        };
        state.connections[connection.id] = connection;
        save();
        const { owner, ...visible } = connection;
        return clone(visible);
      },
      // Only the owner can change a connection, and the request names the connectivity type it was created with.
      // https://learn.microsoft.com/rest/api/fabric/core/connections/update-connection
      async updateConnection(connectionId, request = {}) {
        await pause();
        const connection = visibleConnection(connectionId);
        if (request.connectivityType !== connection.connectivityType) throw badRequest(`connectivityType must be ${connection.connectivityType}.`, 'InvalidRequest');
        if (request.displayName !== undefined) {
          if (!request.displayName) throw badRequest('displayName must not be empty.', 'InvalidRequest');
          if (Object.values(state.connections).some((c) => c.id !== connectionId && c.displayName === request.displayName)) {
            throw conflict(`A connection named ${request.displayName} already exists.`, 'DuplicateConnectionName');
          }
          connection.displayName = request.displayName;
        }
        if (request.privacyLevel) connection.privacyLevel = request.privacyLevel;
        save();
        const { owner, ...visible } = connection;
        return clone(visible);
      },
      async deleteConnection(connectionId) {
        await pause();
        visibleConnection(connectionId);
        delete state.connections[connectionId];
        for (const [modelId, binding] of Object.entries(state.bindings)) if (binding.connectionId === connectionId) delete state.bindings[modelId];
        save();
      },
      async listItemConnections(workspaceId, itemId) {
        await pause();
        itemFor(workspaceId, itemId, 'Viewer', 'list item connections');
        const reference = modelReference(itemId);
        if (!reference) return [];
        const bound = state.connections[state.bindings[itemId]?.connectionId];
        return [bound ? { id: bound.id, displayName: bound.displayName, connectivityType: 'ShareableCloud', connectionDetails: reference } : { connectivityType: 'Automatic', connectionDetails: reference }];
      },
      async bindSemanticModelConnection(workspaceId, modelId, binding) {
        await pause();
        const model = itemFor(workspaceId, modelId, 'Contributor', 'bind a connection');
        if (model.type !== 'SemanticModel') throw notFound(`Semantic model ${modelId}`);
        if (!sameId(model.configuredBy, principal)) {
          // As live Fabric answers (2026-10-02): 400, not 403.
          throw badRequest('You cannot configure the data connection bindings because you are not the owner of the semantic model. Please contact the semantic model owner or take over ownership and try again.', 'BindNotModelOwner');
        }
        const reference = modelReference(modelId);
        if (!reference || reference.path !== binding.connectionDetails?.path || reference.type !== binding.connectionDetails?.type) {
          throw badRequest("connectionDetails don't match a data source of this model.", 'InvalidRequest');
        }
        const connection = visibleConnection(binding.id);
        if (connection.connectionDetails.path !== reference.path) throw badRequest("The connection doesn't point at this data source.", 'InvalidRequest');
        state.bindings[modelId] = { connectionId: binding.id };
        save();
      },

      async listItems(workspaceId, type) {
        await pause();
        authorize(workspaceId, 'Viewer', 'list items');
        return itemsIn(workspaceId).filter((i) => !type || i.type === type).map(publicItem);
      },
      async createItem(workspaceId, { displayName, type, description, definition }) {
        await pause();
        authorize(workspaceId, 'Contributor', `create a ${type}`);
        if (!displayName || !type) throw badRequest('displayName and type are required.');
        if (itemsIn(workspaceId).some((i) => i.type === type && i.displayName === displayName)) {
          throw conflict(`An item named ${displayName} already exists.`, 'ItemDisplayNameAlreadyInUse');
        }
        const created = { id: randomUUID(), type, displayName, description: description || '', workspaceId };
        const host = `${workspaceId.slice(0, 8)}-mock`;
        if (type === 'Lakehouse') {
          const sqlEndpointId = randomUUID();
          created.properties = { sqlEndpointId, sqlConnectionString: `${host}.datawarehouse.fabric.microsoft.com` };
          state.items[sqlEndpointId] = { id: sqlEndpointId, type: 'SQLEndpoint', displayName, description: '', workspaceId };
        }
        if (type === 'Warehouse') created.properties = { connectionString: `${host}.datawarehouse.fabric.microsoft.com` };
        if (type === 'SQLDatabase') created.properties = { serverFqdn: `${host}.database.fabric.microsoft.com,1433`, databaseName: `${displayName}-${created.id}` };
        if (type === 'SemanticModel') created.configuredBy = principal;
        state.items[created.id] = created;
        if (definition) state.definitions[created.id] = clone(definition);
        save();
        return publicItem(created);
      },
      // A new display name or description; the item keeps its ID, definition, data and everything bound to it.
      // https://learn.microsoft.com/rest/api/fabric/core/items/update-item
      async updateItem(workspaceId, itemId, { displayName, description } = {}) {
        await pause();
        const item = itemFor(workspaceId, itemId, 'Contributor', 'update an item');
        if (displayName !== undefined) {
          if (!displayName) throw badRequest('displayName must not be empty.', 'InvalidRequest');
          if (itemsIn(workspaceId).some((i) => i.id !== itemId && i.type === item.type && i.displayName === displayName)) {
            throw conflict(`An item named ${displayName} already exists.`, 'ItemDisplayNameAlreadyInUse');
          }
          item.displayName = displayName;
        }
        if (description !== undefined) item.description = description;
        save();
        return publicItem(item);
      },
      async getItemDefinition(workspaceId, itemId) {
        await pause();
        itemFor(workspaceId, itemId, 'Contributor', 'read an item definition');
        const definition = state.definitions[itemId];
        if (!definition) throw badRequest('This item type has no definition.', 'OperationNotSupportedForItem');
        return { definition: clone(definition) };
      },
      async updateItemDefinition(workspaceId, itemId, definition) {
        await pause();
        const item = itemFor(workspaceId, itemId, 'Contributor', 'update an item definition');
        // As live Fabric answers (2026-10-07): Analysis Services can't rename, or drop, an expression the model's
        // partitions read through in a definition update.
        if (item.type === 'SemanticModel') {
          const { declared } = expressionsOf(definition);
          if (expressionsOf(state.definitions[itemId]).read.some((name) => !declared.includes(name))) {
            throw new FabricApiError(
              `Long-running operation failed: Dataset Workload failed to import the dataset with dataset id ${itemId}. Analysis Services error. Failed to save modifications to the server. Error returned: 'An unexpected error occurred (file 'TMSavePoint.cpp', line 1303, function 'TMSavePoint::ThrowObjectNotFoundError').'.`,
              { code: null },
            );
          }
        }
        state.definitions[itemId] = clone(definition);
        save();
        return null;
      },
      async deleteItem(workspaceId, itemId) {
        await pause();
        itemFor(workspaceId, itemId, 'Contributor', 'delete an item');
        delete state.items[itemId];
        delete state.definitions[itemId];
        delete state.tables[itemId];
        delete state.bindings[itemId];
        save();
      },
      async getLakehouse(workspaceId, id) {
        await pause();
        const lakehouse = itemFor(workspaceId, id, 'Viewer', 'read a lakehouse');
        if (lakehouse.type !== 'Lakehouse') throw notFound(`Lakehouse ${id}`);
        return {
          ...publicItem(lakehouse),
          properties: {
            oneLakeTablesPath: `https://onelake.dfs.fabric.microsoft.com/${workspaceId}/${id}/Tables`,
            oneLakeFilesPath: `https://onelake.dfs.fabric.microsoft.com/${workspaceId}/${id}/Files`,
            sqlEndpointProperties: { id: lakehouse.properties?.sqlEndpointId, connectionString: lakehouse.properties?.sqlConnectionString, provisioningStatus: 'Success' },
          },
        };
      },
      async getWarehouse(workspaceId, id) {
        await pause();
        const warehouse = itemFor(workspaceId, id, 'Viewer', 'read a warehouse');
        if (warehouse.type !== 'Warehouse') throw notFound(`Warehouse ${id}`);
        return { ...publicItem(warehouse), properties: { connectionString: warehouse.properties?.connectionString } };
      },
      async getSqlDatabase(workspaceId, id) {
        await pause();
        const database = itemFor(workspaceId, id, 'Viewer', 'read a SQL database');
        if (database.type !== 'SQLDatabase') throw notFound(`SQL database ${id}`);
        return { ...publicItem(database), properties: { ...database.properties } };
      },

      async listLakehouseTables(workspaceId, lakehouseId) {
        await pause();
        itemFor(workspaceId, lakehouseId, 'Viewer', 'list lakehouse tables');
        return Object.values(state.tables[lakehouseId] || {}).map((t) => ({
          type: 'Managed',
          name: t.name,
          location: `abfss://${workspaceId}@onelake.dfs.fabric.microsoft.com/${lakehouseId}/Tables/${t.name}`,
          format: 'Delta',
        }));
      },
      async loadTable(workspaceId, lakehouseId, tableName, request) {
        await pause();
        itemFor(workspaceId, lakehouseId, 'Contributor', 'load a table');
        if (!/^(?=[0-9]*[a-zA-Z_])[a-zA-Z0-9_]{1,256}$/.test(tableName)) throw badRequest(`Invalid table name ${tableName}.`);
        const bytes = files.get(`${workspaceId}/${lakehouseId}/${request.relativePath}`);
        if (!bytes) throw badRequest(`File ${request.relativePath} was not found.`, 'FileNotFound');
        let columns = [];
        let rows = [];
        if ((request.formatOptions?.format || 'Csv') === 'Csv') {
          const parsed = parseCsv(bytes.toString('utf8'), request.formatOptions?.delimiter || ',');
          columns = request.formatOptions?.header === false ? (parsed[0] || []).map((_, i) => `_c${i}`) : parsed.shift() || [];
          rows = parsed.map((values) => Object.fromEntries(columns.map((c, i) => [c, values[i] ?? ''])));
        }
        const tables = (state.tables[lakehouseId] ||= {});
        const previous = request.mode === 'Append' ? tables[tableName] : null;
        tables[tableName] = {
          name: tableName,
          columns: previous?.columns?.length ? previous.columns : columns,
          rowCount: (previous?.rowCount || 0) + rows.length,
          sample: [...(previous?.sample || []), ...rows].slice(0, 500),
        };
        save();
        return null;
      },
      async uploadFile(workspaceId, itemId, relativePath, bytes) {
        await pause();
        itemFor(workspaceId, itemId, 'Contributor', 'write to OneLake');
        files.set(`${workspaceId}/${itemId}/${relativePath}`, Buffer.from(bytes));
        return { path: relativePath, bytes: bytes.length };
      },
      async countTableRows(workspaceId, lakehouseId, tableName) {
        await pause();
        // Reading Delta logs is OneLake data access, which Viewers don't have.
        itemFor(workspaceId, lakehouseId, 'Contributor', 'read OneLake data');
        const table = state.tables[lakehouseId]?.[tableName];
        if (!table) throw notFound(`Table ${tableName}`);
        return { rows: table.rowCount, files: 1, version: 0 };
      },

      async runItemJob(workspaceId, itemId, jobType) {
        await pause();
        const target = itemFor(workspaceId, itemId, 'Contributor', 'run a job');
        const expected = { Pipeline: 'DataPipeline', RunNotebook: 'Notebook' }[jobType];
        if (expected !== target.type) throw badRequest(`Job type ${jobType} doesn't apply to a ${target.type}.`, 'InvalidJobType');
        const job = { id: randomUUID(), itemId, workspaceId, jobType, invokeType: 'Manual', startedAt: Date.now() };
        state.jobs[job.id] = job;
        save();
        return { jobInstanceId: job.id, status: 'NotStarted' };
      },
      async getItemJob(workspaceId, itemId, jobInstanceId) {
        await pause();
        authorize(workspaceId, 'Viewer', 'read a job');
        const job = state.jobs[jobInstanceId];
        if (!job || job.itemId !== itemId || job.workspaceId !== workspaceId) throw notFound(`Job ${jobInstanceId}`);
        const elapsed = Date.now() - job.startedAt;
        const status = elapsed < jobDurationMs / 5 ? 'NotStarted' : elapsed < jobDurationMs ? 'InProgress' : 'Completed';
        if (status === 'Completed' && !job.completed) {
          job.completed = true;
          buildGold(workspaceId);
          save();
        }
        return {
          id: job.id,
          itemId,
          jobType: job.jobType,
          invokeType: job.invokeType,
          status,
          startTimeUtc: new Date(job.startedAt).toISOString(),
          endTimeUtc: status === 'Completed' ? new Date(job.startedAt + jobDurationMs).toISOString() : null,
          failureReason: null,
        };
      },

      async pbiListReports(workspaceId) {
        await pause();
        authorize(workspaceId, 'Viewer', 'list reports');
        return itemsIn(workspaceId)
          .filter((i) => i.type === 'Report')
          .map((r) => ({
            id: r.id,
            name: r.displayName,
            datasetId: datasetIdOf(r.id),
            reportType: 'PowerBIReport',
            embedUrl: `mock://app.powerbi.com/reportEmbed?reportId=${r.id}&groupId=${workspaceId}`,
          }));
      },
      async pbiListDatasets(workspaceId) {
        await pause();
        authorize(workspaceId, 'Viewer', 'list semantic models');
        return itemsIn(workspaceId)
          .filter((i) => i.type === 'SemanticModel')
          .map((d) => {
            const secured = rolesOf(d.id).length > 0;
            return {
              id: d.id,
              name: d.displayName,
              configuredBy: d.configuredBy || null,
              isEffectiveIdentityRequired: secured,
              isEffectiveIdentityRolesRequired: secured,
              createReportEmbedURL: `mock://app.powerbi.com/reportEmbed?config=create&groupId=${workspaceId}`,
            };
          });
      },
      // Like Power BI: the identity that embeds must be Admin or Member of the workspace that holds every item in the
      // token. https://learn.microsoft.com/power-bi/guidance/powerbi-implementation-planning-usage-scenario-embed-for-your-customers
      async pbiGenerateToken(request) {
        await pause();
        for (const r of request.reports || []) {
          const report = state.items[r.id];
          if (report?.type !== 'Report') throw notFound(`Report ${r.id}`);
          authorize(report.workspaceId, 'Member', r.allowEdit ? 'edit a report' : 'view a report');
        }
        for (const d of request.datasets || []) {
          const model = state.items[d.id];
          if (model?.type !== 'SemanticModel') throw notFound(`Semantic model ${d.id}`);
          authorize(model.workspaceId, 'Member', 'read a semantic model');
        }
        for (const w of request.targetWorkspaces || []) authorize(w.id, 'Member', 'save reports');
        checkIdentities(request);
        const minutes = Math.min(60, Number(request.lifetimeInMinutes) > 0 ? Number(request.lifetimeInMinutes) : 60);
        const issued = { token: `mock-embed-token.${randomUUID()}`, tokenId: randomUUID(), expiration: new Date(Date.now() + minutes * 60 * 1000).toISOString() };
        tokens.push({ principal, tokenId: issued.tokenId, request: clone(request) });
        return issued;
      },
      async pbiRefreshDataset(workspaceId, datasetId) {
        await pause();
        const model = itemFor(workspaceId, datasetId, 'Contributor', 'refresh a semantic model');
        if (model.type !== 'SemanticModel') throw notFound(`Semantic model ${datasetId}`);
        const at = new Date().toISOString();
        const refresh = { requestId: randomUUID(), refreshType: 'ViaEnhancedApi', status: 'Completed', startTime: at, endTime: at };
        (state.refreshes[datasetId] ||= []).unshift(refresh);
        save();
        return { requestId: refresh.requestId };
      },
      async pbiListRefreshes(workspaceId, datasetId, top = 5) {
        await pause();
        itemFor(workspaceId, datasetId, 'Viewer', 'list refreshes');
        return clone((state.refreshes[datasetId] || []).slice(0, top));
      },
      async pbiExecuteQuery() {
        throw new FabricApiError('DAX queries are not available in demo mode.', { upstreamStatus: 400, code: 'NotSupportedInDemo' });
      },
      async pbiTakeOverDataset(workspaceId, datasetId) {
        await pause();
        const model = itemFor(workspaceId, datasetId, 'Contributor', 'take over a semantic model');
        model.configuredBy = principal;
        save();
      },

      async askDataAgent(workspaceId, dataAgentId, question) {
        await pause();
        const agent = itemFor(workspaceId, dataAgentId, 'Viewer', 'query a data agent');
        if (agent.type !== 'DataAgent') throw notFound(`Data agent ${dataAgentId}`);
        return { answer: answer(dataAgentId, question), tool: 'mock_data_agent' };
      },

      // Test and support helpers: who called what, and a Fabric-administrator view of the whole tenant.
      callLog: () => calls.map((c) => ({ ...c })),
      clearCallLog: () => {
        calls.length = 0;
      },
      embedTokens: () => clone(tokens),
      inspect: () => clone({ workspaces: state.workspaces, roleAssignments: state.roleAssignments, items: state.items, connections: state.connections, bindings: state.bindings }),
    };
  }

  return client(defaultPrincipal);
}
