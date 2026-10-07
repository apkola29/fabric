import { SCOPES } from '../auth/tokens.js';
import { askDataAgentOverMcp } from './mcp.js';

// Thin client over the Fabric REST API, OneLake (ADLS Gen2 DFS API) and the Power BI REST API.
// Handles throttling (429 + Retry-After), long-running operations (202 + Location) and paging.

export class FabricApiError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'FabricApiError';
    Object.assign(this, details);
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const RETRYABLE = new Set([429, 502, 503, 504]);
const ONELAKE_API_VERSION = '2023-11-03';
const UPLOAD_CHUNK_BYTES = 4 * 1024 * 1024;

function retryAfterMs(res) {
  const value = res.headers.get('retry-after');
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.min(Math.max(seconds, 0), 60) * 1000;
  const date = Date.parse(value);
  return Number.isFinite(date) ? Math.min(Math.max(date - Date.now(), 0), 60_000) : null;
}

function shortPath(url) {
  try {
    const u = new URL(url);
    return u.pathname;
  } catch {
    return url;
  }
}

function encodePath(relativePath) {
  return relativePath.split('/').map(encodeURIComponent).join('/');
}

export function createFabricClient({
  tokens,
  endpoints,
  fetchImpl = fetch,
  maxRetries = 5,
  pollIntervalMs = 2000,
  maxPollMs = 15 * 60 * 1000,
  baseBackoffMs = 500,
  // Extra headers for api.fabric.microsoft.com calls only (for example tooling telemetry); never sent to other hosts.
  fabricHeaders = {},
}) {
  const fabricBase = endpoints.fabric.replace(/\/$/, '');
  const powerbiBase = endpoints.powerbi.replace(/\/$/, '');
  const onelakeBase = endpoints.onelake.replace(/\/$/, '');
  const fabricOrigin = new URL(fabricBase).origin;
  const toUrl = (pathOrUrl) => (/^https?:\/\//i.test(pathOrUrl) ? pathOrUrl : `${fabricBase}${pathOrUrl}`);
  const backoff = (attempt) => Math.min(30_000, baseBackoffMs * 2 ** attempt) + Math.floor(Math.random() * baseBackoffMs);

  async function send(method, url, { scope = SCOPES.fabric, body, rawBody, headers = {}, minTokenValidityMs = 0 } = {}) {
    for (let attempt = 0; ; attempt++) {
      const requestHeaders = { ...(url.startsWith(fabricOrigin) ? fabricHeaders : {}), authorization: `Bearer ${await tokens.getToken(scope, { minValidityMs: minTokenValidityMs })}`, ...headers };
      let payload;
      if (rawBody !== undefined) payload = rawBody;
      else if (body !== undefined) {
        payload = JSON.stringify(body);
        requestHeaders['content-type'] = 'application/json';
      }
      let res;
      try {
        res = await fetchImpl(url, { method, headers: requestHeaders, body: payload });
      } catch (error) {
        if (attempt < maxRetries) {
          await sleep(backoff(attempt));
          continue;
        }
        throw new FabricApiError(`Network error on ${method} ${shortPath(url)}: ${error.message}`, { method, path: shortPath(url) });
      }
      if (RETRYABLE.has(res.status) && attempt < maxRetries) {
        const wait = retryAfterMs(res) ?? backoff(attempt);
        await res.arrayBuffer().catch(() => {});
        await sleep(wait);
        continue;
      }
      return res;
    }
  }

  async function ensureOk(res, method, url) {
    if (res.ok) return res;
    const text = await res.text().catch(() => '');
    let parsed = null;
    try {
      parsed = JSON.parse(text);
    } catch {
      // Not JSON; use the raw text below.
    }
    const code = parsed?.errorCode || parsed?.error?.code || null;
    const message = parsed?.message || parsed?.error?.message || text.slice(0, 300) || res.statusText;
    throw new FabricApiError(`${method} ${shortPath(url)} failed (HTTP ${res.status}${code ? `, ${code}` : ''}): ${message}`, {
      upstreamStatus: res.status,
      code,
      requestId: parsed?.requestId || res.headers.get('requestid') || res.headers.get('x-ms-request-id') || null,
      method,
      path: shortPath(url),
      moreDetails: parsed?.moreDetails,
    });
  }

  async function call(method, pathOrUrl, options = {}) {
    const url = toUrl(pathOrUrl);
    const res = await send(method, url, options);
    return ensureOk(res, method, url);
  }

  async function readJsonBody(res) {
    if (res.status === 204) return null;
    const text = await res.text();
    return text ? JSON.parse(text) : null;
  }

  async function json(method, pathOrUrl, options) {
    return readJsonBody(await call(method, pathOrUrl, options));
  }

  async function drain(res) {
    await res.arrayBuffer().catch(() => {});
  }

  // https://learn.microsoft.com/rest/api/fabric/articles/long-running-operation
  async function longRunning(method, pathOrUrl, { body, scope, withResult = true } = {}) {
    const res = await call(method, pathOrUrl, { body, scope });
    if (res.status !== 202) return readJsonBody(res);
    await drain(res);
    const operationId = res.headers.get('x-ms-operation-id');
    const location = res.headers.get('location') || (operationId ? `${fabricBase}/operations/${operationId}` : null);
    if (!location) return null;
    let wait = retryAfterMs(res) ?? pollIntervalMs;
    const deadline = Date.now() + maxPollMs;
    for (;;) {
      await sleep(wait);
      const poll = await call('GET', location, { scope });
      const state = await readJsonBody(poll);
      const status = state?.status;
      if (status === 'Succeeded') {
        if (!withResult) return null;
        const resultUrl = poll.headers.get('location') || `${location.replace(/\/$/, '')}/result`;
        return json('GET', resultUrl, { scope });
      }
      if (status === 'Failed' || status === 'Cancelled') {
        throw new FabricApiError(`Long-running operation ${status.toLowerCase()}: ${state?.error?.message || 'no details'}`, {
          code: state?.error?.errorCode || null,
          path: shortPath(location),
        });
      }
      if (Date.now() > deadline) throw new FabricApiError(`Timed out waiting for operation ${shortPath(location)}.`, { path: shortPath(location) });
      wait = retryAfterMs(poll) ?? pollIntervalMs;
    }
  }

  async function listAll(pathOrUrl, { scope, key } = {}) {
    const results = [];
    const seen = new Set();
    let url = toUrl(pathOrUrl);
    while (url && !seen.has(url)) {
      seen.add(url);
      const page = await json('GET', url, { scope });
      results.push(...(page?.[key || 'value'] || page?.value || page?.data || []));
      if (page?.continuationUri) url = page.continuationUri;
      else if (page?.continuationToken) {
        const next = new URL(url);
        next.searchParams.set('continuationToken', page.continuationToken);
        url = next.toString();
      } else url = null;
    }
    return results;
  }

  const onelakeHeaders = { 'x-ms-version': ONELAKE_API_VERSION };

  async function listOneLakePaths(workspaceId, directory) {
    const paths = [];
    let continuation = null;
    do {
      const url = new URL(`${onelakeBase}/${workspaceId}`);
      url.searchParams.set('resource', 'filesystem');
      url.searchParams.set('recursive', 'false');
      url.searchParams.set('directory', directory);
      if (continuation) url.searchParams.set('continuation', continuation);
      const res = await call('GET', url.toString(), { scope: SCOPES.storage, headers: onelakeHeaders });
      paths.push(...((await readJsonBody(res))?.paths || []));
      continuation = res.headers.get('x-ms-continuation');
    } while (continuation);
    return paths;
  }

  async function readOneLakeText(workspaceId, path) {
    const res = await call('GET', `${onelakeBase}/${workspaceId}/${encodePath(path)}`, { scope: SCOPES.storage, headers: onelakeHeaders });
    return res.text();
  }

  return {
    kind: 'live',

    // The object ID of the identity this client signs in as (the `oid` claim of its Fabric token).
    async principalId() {
      const token = await tokens.getToken(SCOPES.fabric);
      try {
        return JSON.parse(Buffer.from(String(token).split('.')[1] || '', 'base64url').toString('utf8')).oid || null;
      } catch {
        return null;
      }
    },

    // Workspaces
    listCapacities: () => listAll('/capacities'),
    // Tenant settings (admin API: needs a Fabric administrator, or a service principal allowed the read-only admin APIs).
    listTenantSettings: async () => (await json('GET', '/admin/tenantsettings'))?.tenantSettings || [],
    listWorkspaces: () => listAll('/workspaces'),
    async findWorkspaceByName(name) {
      return (await listAll('/workspaces')).find((w) => w.displayName === name) || null;
    },
    createWorkspace: ({ displayName, description, capacityId }) =>
      json('POST', '/workspaces', { body: { displayName, description, ...(capacityId ? { capacityId } : {}) } }),
    getWorkspace: (workspaceId) => json('GET', `/workspaces/${workspaceId}`),
    assignToCapacity: (workspaceId, capacityId) =>
      longRunning('POST', `/workspaces/${workspaceId}/assignToCapacity`, { body: { capacityId }, withResult: false }),
    deleteWorkspace: async (workspaceId) => drain(await call('DELETE', `/workspaces/${workspaceId}`)),
    listRoleAssignments: (workspaceId) => listAll(`/workspaces/${workspaceId}/roleAssignments`),
    addRoleAssignment: (workspaceId, principal, role) =>
      json('POST', `/workspaces/${workspaceId}/roleAssignments`, { body: { principal, role } }),
    deleteRoleAssignment: async (workspaceId, assignmentId) =>
      drain(await call('DELETE', `/workspaces/${workspaceId}/roleAssignments/${assignmentId}`)),
    // Workspace identity: a Fabric-managed service principal per workspace, used for connections without secrets.
    provisionWorkspaceIdentity: (workspaceId) => longRunning('POST', `/workspaces/${workspaceId}/provisionIdentity`),

    // Items
    listItems: (workspaceId, type) =>
      listAll(`/workspaces/${workspaceId}/items${type ? `?type=${encodeURIComponent(type)}` : ''}`),
    createItem: (workspaceId, item) => longRunning('POST', `/workspaces/${workspaceId}/items`, { body: item }),
    // A new display name or description; the item keeps its ID, definition and data. SQL databases go through this
    // generic endpoint too: their own (PATCH .../sqlDatabases/{id}) takes only a description.
    // https://learn.microsoft.com/rest/api/fabric/core/items/update-item
    updateItem: (workspaceId, itemId, { displayName, description } = {}) =>
      json('PATCH', `/workspaces/${workspaceId}/items/${itemId}`, { body: { displayName, description } }),
    getItemDefinition: (workspaceId, itemId) => longRunning('POST', `/workspaces/${workspaceId}/items/${itemId}/getDefinition`),
    updateItemDefinition: (workspaceId, itemId, definition) =>
      longRunning('POST', `/workspaces/${workspaceId}/items/${itemId}/updateDefinition`, { body: { definition }, withResult: false }),
    deleteItem: async (workspaceId, itemId) => drain(await call('DELETE', `/workspaces/${workspaceId}/items/${itemId}`)),
    getLakehouse: (workspaceId, id) => json('GET', `/workspaces/${workspaceId}/lakehouses/${id}`),
    getWarehouse: (workspaceId, id) => json('GET', `/workspaces/${workspaceId}/warehouses/${id}`),
    getSqlDatabase: (workspaceId, id) => json('GET', `/workspaces/${workspaceId}/sqlDatabases/${id}`),

    // Connections. A semantic model's data source reference is bound to a cloud connection with a fixed identity, so
    // embedded viewers (who have no Fabric identity) can query it.
    listConnections: () => listAll('/connections'),
    createConnection: (request) => json('POST', '/connections', { body: request }),
    // Renames a connection in place, so what's bound to it stays bound. The request names its connectivity type.
    // https://learn.microsoft.com/rest/api/fabric/core/connections/update-connection
    updateConnection: (connectionId, request) => json('PATCH', `/connections/${connectionId}`, { body: request }),
    deleteConnection: async (connectionId) => drain(await call('DELETE', `/connections/${connectionId}`)),
    listItemConnections: (workspaceId, itemId) => listAll(`/workspaces/${workspaceId}/items/${itemId}/connections`),
    bindSemanticModelConnection: async (workspaceId, semanticModelId, connectionBinding) =>
      drain(await call('POST', `/workspaces/${workspaceId}/semanticModels/${semanticModelId}/bindConnection`, { body: { connectionBinding } })),

    // Lakehouse tables (non-schema lakehouses; schema-enabled ones need the schema-scoped endpoints)
    listLakehouseTables: (workspaceId, lakehouseId) =>
      listAll(`/workspaces/${workspaceId}/lakehouses/${lakehouseId}/tables`, { key: 'data' }),
    loadTable: (workspaceId, lakehouseId, tableName, request) =>
      longRunning('POST', `/workspaces/${workspaceId}/lakehouses/${lakehouseId}/tables/${encodeURIComponent(tableName)}/load`, {
        body: request,
        withResult: false,
      }),

    // OneLake speaks the ADLS Gen2 DFS API: create the file, append chunks, then flush.
    async uploadFile(workspaceId, itemId, relativePath, bytes) {
      const url = `${onelakeBase}/${workspaceId}/${itemId}/${encodePath(relativePath)}`;
      const scope = SCOPES.storage;
      await drain(await call('PUT', `${url}?resource=file`, { scope, headers: onelakeHeaders, rawBody: '' }));
      let position = 0;
      while (position < bytes.length) {
        const chunk = bytes.subarray(position, Math.min(position + UPLOAD_CHUNK_BYTES, bytes.length));
        await drain(
          await call('PATCH', `${url}?action=append&position=${position}`, {
            scope,
            headers: { ...onelakeHeaders, 'content-type': 'application/octet-stream' },
            rawBody: chunk,
          }),
        );
        position += chunk.length;
      }
      await drain(await call('PATCH', `${url}?action=flush&position=${position}`, { scope, headers: onelakeHeaders, rawBody: '' }));
      return { path: relativePath, bytes: bytes.length };
    },

    // Row count read back from the Delta transaction log (add/remove actions carry numRecords), so no SQL driver is needed.
    async countTableRows(workspaceId, lakehouseId, tableName) {
      const commits = (await listOneLakePaths(workspaceId, `${lakehouseId}/Tables/${tableName}/_delta_log`))
        .map((p) => p.name)
        .filter((name) => /\/\d{20}\.json$/.test(name))
        .sort();
      if (!commits.length || !commits[0].endsWith('00000000000000000000.json')) return { rows: null, reason: 'the log was cleaned up or checkpointed' };
      const active = new Map();
      for (const commit of commits) {
        for (const line of (await readOneLakeText(workspaceId, commit)).split('\n')) {
          if (!line.trim()) continue;
          const action = JSON.parse(line);
          if (action.add) active.set(action.add.path, JSON.parse(action.add.stats || '{}').numRecords ?? null);
          if (action.remove) active.delete(action.remove.path);
        }
      }
      const counts = [...active.values()];
      if (counts.some((n) => n === null)) return { rows: null, reason: 'some files have no statistics' };
      return { rows: counts.reduce((sum, n) => sum + n, 0), files: active.size, version: commits.length - 1 };
    },

    // Job scheduler: pipelines (jobType=Pipeline) and notebooks (jobType=RunNotebook)
    async runItemJob(workspaceId, itemId, jobType, executionData) {
      const res = await call('POST', `/workspaces/${workspaceId}/items/${itemId}/jobs/instances?jobType=${encodeURIComponent(jobType)}`, {
        body: executionData ? { executionData } : undefined,
      });
      await drain(res);
      const location = res.headers.get('location') || '';
      const jobInstanceId = location.split('/').filter(Boolean).pop() || null;
      return { jobInstanceId, status: 'NotStarted' };
    },
    getItemJob: (workspaceId, itemId, jobInstanceId) =>
      json('GET', `/workspaces/${workspaceId}/items/${itemId}/jobs/instances/${jobInstanceId}`),

    // Power BI REST API (embedding, refresh and DAX queries)
    pbiListReports: (workspaceId) => listAll(`${powerbiBase}/groups/${workspaceId}/reports`, { scope: SCOPES.powerbi }),
    pbiListDatasets: (workspaceId) => listAll(`${powerbiBase}/groups/${workspaceId}/datasets`, { scope: SCOPES.powerbi }),
    pbiGenerateToken: (request) => json('POST', `${powerbiBase}/GenerateToken`, { scope: SCOPES.powerbi, body: request, minTokenValidityMs: embedTokenValidityMs(request) }),
    // For Direct Lake a refresh is "framing": it points the model at the latest Delta table versions. No data is copied.
    async pbiRefreshDataset(workspaceId, datasetId, body = { type: 'full', commitMode: 'transactional', retryCount: 1 }) {
      const res = await call('POST', `${powerbiBase}/groups/${workspaceId}/datasets/${datasetId}/refreshes`, { scope: SCOPES.powerbi, body });
      await drain(res);
      const location = res.headers.get('location') || '';
      return { requestId: location.split('/').filter(Boolean).pop() || res.headers.get('requestid') || null };
    },
    pbiListRefreshes: async (workspaceId, datasetId, top = 5) =>
      (await json('GET', `${powerbiBase}/groups/${workspaceId}/datasets/${datasetId}/refreshes?$top=${top}`, { scope: SCOPES.powerbi }))?.value || [],
    async pbiExecuteQuery(workspaceId, datasetId, query) {
      const result = await json('POST', `${powerbiBase}/groups/${workspaceId}/datasets/${datasetId}/executeQueries`, {
        scope: SCOPES.powerbi,
        body: { queries: [{ query }], serializerSettings: { includeNulls: true } },
      });
      const error = result?.results?.[0]?.error || result?.error;
      if (error) throw new FabricApiError(`DAX query failed: ${error.message || error.code || JSON.stringify(error).slice(0, 300)}`, { code: error.code || 'DaxError' });
      return result?.results?.[0]?.tables?.[0]?.rows || [];
    },
    pbiTakeOverDataset: async (workspaceId, datasetId) =>
      drain(await call('POST', `${powerbiBase}/groups/${workspaceId}/datasets/${datasetId}/Default.TakeOver`, { scope: SCOPES.powerbi })),

    // Data agent MCP endpoint (available after the agent is published)
    askDataAgent: (workspaceId, dataAgentId, question) =>
      askDataAgentOverMcp({
        url: dataAgentMcpUrl(fabricBase, workspaceId, dataAgentId),
        getToken: () => tokens.getToken(SCOPES.fabric),
        question,
        fetchImpl,
      }),
  };
}

// An embed token lives no longer than the Microsoft Entra token used to create it, so GenerateToken gets an Entra token
// with the embed token's lifetime left, plus 5 minutes (at most 55, since a fresh token usually lasts about an hour).
// https://learn.microsoft.com/power-bi/developer/embedded/generate-embed-token#considerations-and-limitations
export const embedTokenValidityMs = (request) => Math.min(55, (Number(request?.lifetimeInMinutes) || 60) + 5) * 60_000;

// A published data agent's MCP server: https://learn.microsoft.com/fabric/data-science/data-agent-mcp-server
export const dataAgentMcpUrl = (fabricBase, workspaceId, dataAgentId) => `${String(fabricBase).replace(/\/$/, '')}/mcp/workspaces/${workspaceId}/dataagents/${dataAgentId}/agent`;
