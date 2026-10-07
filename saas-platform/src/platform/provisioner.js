import { createHash } from 'node:crypto';
import { ASSISTANT_MODEL_NAME, MODEL_NAME, STARTER_REPORT_NAME, agentTables, buildSemanticModelDefinition, buildStarterReportDefinition, sampleSeedOf } from '../crm/workload.js';
import { agentDescription, agentInstructions, agentModelSource, buildSemanticModelAgentDefinition, syncDataAgent } from './agent.js';
import { CORE_ITEMS, entitlements } from './plans.js';
import { addActivity } from './store.js';
import { stampTemplates } from './templates.js';

// Provisioning is a list of idempotent steps. Each step reads the current state back from Fabric, so a re-run
// (after a failure, a crash, an edition change or a new model version) only does the work that's missing.
//
// Two identities take part. The platform identity (control plane) creates the workspace, assigns the capacity and
// makes the customer's service account Admin of that workspace. Every later step runs as the customer's service
// account, so the items (database, model, connection, assistant) belong to it and it needs no access anywhere else.
// With PLATFORM_WORKSPACE_ACCESS=release the platform then removes its own role: it keeps no standing access to any
// customer workspace (and isn't held to the 1,000-workspaces-per-identity limit). When it needs to act again (moving
// the workspace to another capacity), the service account re-adds it for that run only.

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const now = () => new Date().toISOString();
const short = (id) => String(id).slice(0, 8);
const sameId = (a, b) => String(a || '').toLowerCase() === String(b || '').toLowerCase();

export function workspaceNameFor(config, tenant) {
  return `${config.workspacePrefix}${tenant.slug}-${tenant.id.slice(0, 4)}`;
}

const SKIP_REASONS = {
  'ops-access': 'FABRIC_OPS_PRINCIPAL_ID is not set',
  'starter-report': 'The template workspace provides the reports',
  templates: 'No template workspace is configured',
  'crm-sample-data': 'This customer starts with an empty CRM',
  'platform-access': 'PLATFORM_WORKSPACE_ACCESS=keep: the platform identity keeps its Admin role',
};

// Runs at most `max` jobs at once; the rest wait in order.
export function createLimiter(max) {
  const queue = [];
  let active = 0;
  let peak = 0;
  const next = () => {
    while (active < max && queue.length) {
      const { fn, resolve, reject } = queue.shift();
      active++;
      peak = Math.max(peak, active);
      Promise.resolve()
        .then(fn)
        .then(resolve, reject)
        .finally(() => {
          active--;
          next();
        });
    }
  };
  return {
    run: (fn) =>
      new Promise((resolve, reject) => {
        queue.push({ fn, resolve, reject });
        next();
      }),
    stats: () => ({ active, queued: queue.length, peak, max }),
  };
}

export function createProvisioner({
  fabric,
  store,
  config,
  identities,
  crm,
  capacityPollMs = 2000,
  capacityPollAttempts = 45,
  waitMs = 10_000,
  refreshPollMs = 5000,
  maxConcurrent = config.provisioning?.maxConcurrent || 4,
}) {
  const running = new Map();
  const limiter = createLimiter(maxConcurrent);
  const releaseMode = config.platformWorkspaceAccess === 'release';
  let platformId = null;

  async function retry(fn, attempts, label) {
    for (let attempt = 1; ; attempt++) {
      try {
        return await fn();
      } catch (error) {
        if (attempt >= attempts) throw new Error(`${label}: ${error.message}`);
        await sleep(waitMs);
      }
    }
  }

  async function platformPrincipalId() {
    platformId ||= await fabric.principalId();
    if (!platformId) throw new Error("Can't tell the platform identity's object ID from its token.");
    return platformId;
  }

  // Who manages the workspace itself: the platform until it has handed over, then the customer's service account.
  async function workspaceClient(tenant) {
    return tenant.fabric.platformReleased ? identities.fabricFor(tenant) : fabric;
  }

  // Just-in-time access: the customer's service account (Admin) re-adds the platform identity for this run.
  async function reattachPlatform(tenant, reason) {
    const workspaceId = tenant.fabric.workspaceId;
    const scoped = await identities.fabricFor(tenant);
    const me = await platformPrincipalId();
    const roles = await scoped.listRoleAssignments(workspaceId);
    if (!roles.some((r) => sameId(r.principal?.id, me))) {
      await scoped.addRoleAssignment(workspaceId, { id: me, type: 'ServicePrincipal' }, 'Admin');
    }
    await retry(() => fabric.getWorkspace(workspaceId), 6, "The platform identity can't open the workspace yet");
    tenant.fabric.platformReleased = false;
    addActivity(tenant, `The platform identity was given temporary access to ${reason}${releaseMode ? '; it is released again at the end of this run' : ''}`, 'audit');
  }

  async function ensureWorkspace(tenant) {
    const name = tenant.fabric.workspaceName || workspaceNameFor(config, tenant);
    if (tenant.fabric.workspaceId) {
      // Keep mode after an earlier release: take the standing access back.
      if (tenant.fabric.platformReleased && !releaseMode) await reattachPlatform(tenant, 'manage the workspace (PLATFORM_WORKSPACE_ACCESS=keep)');
      const client = await workspaceClient(tenant);
      try {
        const ws = await client.getWorkspace(tenant.fabric.workspaceId);
        tenant.fabric.workspaceName = ws.displayName;
        return tenant.fabric.adopted ? `Using ${ws.displayName}, created by an admin` : `${ws.displayName} exists`;
      } catch (error) {
        if (![401, 403, 404].includes(error.upstreamStatus)) throw error;
        // Never replace a known workspace on our own: it may hold customer data that an admin can still restore.
        const who = tenant.fabric.platformReleased ? `The service account ${tenant.identity?.name || ''}`.trim() : 'The platform identity';
        const fix = tenant.fabric.adopted && !tenant.fabric.platformReleased
          ? 'Add the platform identity to the workspace as Admin.'
          : 'If it was deleted on purpose, remove the customer and add it again; otherwise a Fabric administrator restores the workspace or its access.';
        throw new Error(`${who} can't open workspace ${tenant.fabric.workspaceId} (HTTP ${error.upstreamStatus}). ${fix}`);
      }
    }
    const found = await fabric.findWorkspaceByName(name);
    if (found) {
      Object.assign(tenant.fabric, { workspaceId: found.id, workspaceName: found.displayName });
      return `Found ${found.displayName}`;
    }
    const capacityId = tenant.capacityId || config.capacityId;
    if (fabric.kind === 'live' && !capacityId) {
      throw new Error('Set FABRIC_CAPACITY_ID (or a capacity for this customer). Customer workspaces need a Fabric capacity (F SKU).');
    }
    const ws = await fabric.createWorkspace({
      displayName: name,
      description: `${config.productName} for ${tenant.name}. Managed by ${config.productName} (customer ${tenant.id}); don't change it by hand.`,
      capacityId: capacityId || undefined,
    });
    Object.assign(tenant.fabric, { workspaceId: ws.id, workspaceName: ws.displayName });
    return `Created ${ws.displayName}`;
  }

  async function ensureCapacity(tenant) {
    // A capacity chosen for this customer (dedicated or regional) wins over the platform default.
    const target = tenant.capacityId || config.capacityId;
    const client = await workspaceClient(tenant);
    let ws = await client.getWorkspace(tenant.fabric.workspaceId);
    // An admin chose the capacity for an adopted workspace, and the platform identity may have no rights to move it.
    if (tenant.fabric.adopted && ws.capacityId && !tenant.capacityId) {
      tenant.fabric.capacityId = ws.capacityId;
      return `Uses the workspace's capacity ${short(ws.capacityId)}`;
    }
    if (!target) {
      if (!ws.capacityId) throw new Error('Set FABRIC_CAPACITY_ID. Customer workspaces need a Fabric capacity (F SKU).');
      tenant.fabric.capacityId = ws.capacityId;
      return `Already on capacity ${short(ws.capacityId)}`;
    }
    const onTarget = (w) => sameId(w.capacityId, target);
    if (onTarget(ws) && (!ws.capacityAssignmentProgress || ws.capacityAssignmentProgress === 'Completed')) {
      tenant.fabric.capacityId = ws.capacityId;
      return `On capacity ${short(target)}`;
    }
    // Moving a workspace needs rights on the capacity, which only the platform identity holds.
    if (tenant.fabric.platformReleased) await reattachPlatform(tenant, `move the workspace to capacity ${short(target)}`);
    if (!onTarget(ws)) await fabric.assignToCapacity(ws.id, target);
    for (let attempt = 0; attempt < capacityPollAttempts; attempt++) {
      ws = await fabric.getWorkspace(ws.id);
      if (ws.capacityAssignmentProgress === 'Failed') {
        throw new Error('Fabric reports that the capacity assignment failed. The identity needs Contributor rights on the capacity, and the capacity must be in the same region.');
      }
      if (onTarget(ws) && (!ws.capacityAssignmentProgress || ws.capacityAssignmentProgress === 'Completed')) {
        tenant.fabric.capacityId = ws.capacityId;
        return `On capacity ${short(target)}`;
      }
      await sleep(capacityPollMs);
    }
    throw new Error('The capacity assignment did not finish in time. Run provisioning again.');
  }

  // The customer's own identity: Admin of this workspace and nothing else.
  async function ensureServiceAccount(tenant) {
    const identity = await identities.ensure(tenant);
    if (!identity) {
      if (identities.mode === 'off') return { status: 'skipped', detail: 'Turned off (TENANT_IDENTITY_MODE=off): the platform identity does everything' };
      const how = 'An Entra admin runs scripts/bootstrap-identities.ps1, or grants the platform Application.ReadWrite.OwnedBy';
      if (identities.mode === 'required') throw new Error(`${tenant.name} has no service account yet. ${how}, then provisioning continues.`);
      return { status: 'warning', detail: `No service account yet, so the shared platform identity is used. ${how} to isolate ${tenant.name}.` };
    }
    const workspaceId = tenant.fabric.workspaceId;
    const control = await workspaceClient(tenant);
    const roles = await control.listRoleAssignments(workspaceId);
    const existing = roles.find((r) => sameId(r.principal?.id, identity.objectId));
    if (!existing) {
      if (tenant.fabric.platformReleased) throw new Error(`${identity.name} has no role in the workspace and the platform holds no access to restore it. A Fabric administrator adds ${identity.name} back as Admin.`);
      await fabric.addRoleAssignment(workspaceId, { id: identity.objectId, type: 'ServicePrincipal' }, 'Admin');
    } else if (existing.role !== 'Admin' && !tenant.fabric.platformReleased) {
      throw new Error(`${identity.name} has the ${existing.role} role; it needs Admin. Change its role in the workspace, then provision again.`);
    }
    identity.workspaceRole = existing?.role || 'Admin';
    // Role assignments take a moment to apply; prove the account can open the workspace before relying on it.
    const scoped = await identities.fabricFor(tenant);
    await retry(() => scoped.getWorkspace(workspaceId), 6, `${identity.name} can't open the workspace yet`);
    return `${identity.name} is ${identity.workspaceRole} of this workspace${existing ? '' : ' (just added)'}`;
  }

  async function ensureOpsAccess(tenant) {
    const principal = config.opsPrincipal;
    const control = await workspaceClient(tenant);
    const assignments = await control.listRoleAssignments(tenant.fabric.workspaceId);
    const existing = assignments.find((a) => sameId(a.principal?.id, principal.id));
    if (existing) return `The support ${principal.type.toLowerCase()} already has the ${existing.role} role`;
    await control.addRoleAssignment(tenant.fabric.workspaceId, { id: principal.id, type: principal.type }, 'Viewer');
    return `Added the support ${principal.type.toLowerCase()} as Viewer`;
  }

  // Found by ID and name, so an old item that happens to sit under the same key is never reused by mistake.
  async function ensureItem(tenant, client, { type, name }, key) {
    const workspaceId = tenant.fabric.workspaceId;
    const items = await client.listItems(workspaceId, type);
    if (tenant.fabric[key] && items.some((i) => i.id === tenant.fabric[key] && i.displayName === name)) return `${name} exists`;
    const byName = items.find((i) => i.displayName === name);
    if (byName) {
      tenant.fabric[key] = byName.id;
      return `Found ${name}`;
    }
    const created = await client.createItem(workspaceId, { displayName: name, type, description: `Managed by ${config.productName} for ${tenant.name}` });
    tenant.fabric[key] = created?.id || (await client.listItems(workspaceId, type)).find((i) => i.displayName === name)?.id;
    if (!tenant.fabric[key]) throw new Error(`${type} ${name} was created but can't be found.`);
    return `Created ${name}`;
  }

  async function ensureCrmDatabase(tenant, client) {
    const detail = await ensureItem(tenant, client, CORE_ITEMS.sqlDatabase, 'crmDatabaseId');
    const workspaceId = tenant.fabric.workspaceId;
    let properties = null;
    for (let attempt = 0; attempt < 30 && !properties?.serverFqdn; attempt++) {
      properties = (await client.getSqlDatabase(workspaceId, tenant.fabric.crmDatabaseId))?.properties;
      if (!properties?.serverFqdn) await sleep(waitMs / 2);
    }
    if (!properties?.serverFqdn || !properties?.databaseName) throw new Error('The SQL database has no connection details yet. Run provisioning again in a minute.');
    const next = { sqlDatabaseId: tenant.fabric.crmDatabaseId, server: properties.serverFqdn, database: properties.databaseName };
    if (JSON.stringify(next) !== JSON.stringify(tenant.fabric.crm)) await crm.forget(tenant.id);
    tenant.fabric.crm = next;
    return detail;
  }

  async function ensureCrmSchema(tenant) {
    const version = await retry(
      async () => {
        try {
          const repo = await crm.forTenant(tenant);
          const applied = await repo.migrate();
          await repo.ensureCalendar();
          return applied;
        } catch (error) {
          await crm.forget(tenant.id);
          throw error;
        }
      },
      6,
      'The CRM database is not reachable',
    );
    // Remembered so the app keeps serving the CRM while later runs (upgrades) are in progress or fail.
    tenant.fabric.crmSchemaVersion = version;
    return `Schema version ${version}, calendar loaded`;
  }

  async function seedCrm(tenant) {
    const repo = await crm.forTenant(tenant);
    const loaded = await repo.seed(sampleSeedOf(tenant), { companyDomain: tenant.domains?.[0] });
    const counts = await repo.counts();
    const summary = `${counts.accounts} accounts, ${counts.opportunities} opportunities, ${counts.activities} activities`;
    return loaded.accounts ? `Loaded ${summary}` : `Already has data (${summary})`;
  }

  // A Fabric-managed identity for this workspace. The model's connection signs in with it, so no secret is stored.
  async function ensureWorkspaceIdentity(tenant, client) {
    const workspaceId = tenant.fabric.workspaceId;
    let identity = (await client.getWorkspace(workspaceId)).workspaceIdentity;
    if (!identity) identity = (await client.provisionWorkspaceIdentity(workspaceId)) || (await client.getWorkspace(workspaceId)).workspaceIdentity;
    if (!identity?.servicePrincipalId) throw new Error('Fabric did not return the workspace identity.');
    tenant.fabric.workspaceIdentity = { applicationId: identity.applicationId, servicePrincipalId: identity.servicePrincipalId };
    // Direct Lake on OneLake needs Read and ReadAll on the database; Viewer doesn't include ReadAll.
    const roles = await client.listRoleAssignments(workspaceId);
    if (!roles.some((r) => sameId(r.principal?.id, identity.servicePrincipalId))) {
      await client.addRoleAssignment(workspaceId, { id: identity.servicePrincipalId, type: 'ServicePrincipal' }, 'Contributor');
      return 'Created; Contributor on this workspace only';
    }
    return 'Ready';
  }

  // Two Direct Lake models over the same OneLake tables (no data is copied): HiCRM Insights, with row-level security,
  // for every report; and its twin without roles for the data agent, because Power BI doesn't let service principals
  // query models with roles. Only people who see every territory reach the agent.
  const MODELS = {
    reports: { name: MODEL_NAME, rowLevelSecurity: true, id: 'semanticModelId', fingerprint: 'semanticModelFingerprint', connection: 'modelConnectionId', purpose: 'pipeline, revenue and activity analytics' },
    assistant: {
      name: ASSISTANT_MODEL_NAME,
      rowLevelSecurity: false,
      id: 'assistantModelId',
      fingerprint: 'assistantModelFingerprint',
      connection: 'assistantConnectionId',
      purpose: "the assistant's view of the CRM data, for sales managers only. Don't build reports on it",
    },
  };

  async function ensureSemanticModel(tenant, client, kind = 'reports') {
    const spec = MODELS[kind];
    const workspaceId = tenant.fabric.workspaceId;
    const { definition, fingerprint } = buildSemanticModelDefinition({ workspaceId, sqlDatabaseId: tenant.fabric.crm.sqlDatabaseId, rowLevelSecurity: spec.rowLevelSecurity });
    const named = async () => (await client.listItems(workspaceId, 'SemanticModel')).filter((i) => i.displayName === spec.name);
    const models = await named();
    // A retried create makes a second model with the same name; never guess which one the reports use.
    if (models.length > 1) throw new Error(`There are ${models.length} models named "${spec.name}". Delete the extras, then run provisioning again.`);
    if (!models.length) {
      const created = await client.createItem(workspaceId, { displayName: spec.name, type: 'SemanticModel', description: `${spec.name}: ${spec.purpose} for ${tenant.name}.`, definition });
      tenant.fabric[spec.id] = created?.id || (await named())[0]?.id;
      Object.assign(tenant.fabric, { [spec.fingerprint]: fingerprint, [spec.connection]: null });
      return `Published ${spec.name}`;
    }
    tenant.fabric[spec.id] = models[0].id;
    if (tenant.fabric[spec.fingerprint] === fingerprint) return `${spec.name} is up to date`;
    await client.updateItemDefinition(workspaceId, models[0].id, definition);
    tenant.fabric[spec.fingerprint] = fingerprint;
    return `Updated ${spec.name} to the current version`;
  }

  // Who a customer's work runs as, and so who owns the connections it creates: its own service account, or the
  // platform identity standing in until the account exists.
  const connectionOwner = (tenant) => (identities.usesPlatformIdentity(tenant) ? 'platform' : tenant.identity.appId);
  // Binding a model someone else owns: live Fabric answers 400 BindNotModelOwner.
  const notModelOwner = (error) =>
    error?.code === 'BindNotModelOwner' || /not the owner of the semantic model/i.test(error?.message || '') || [401, 403].includes(error?.upstreamStatus);

  async function ensureConnection(tenant, client, details) {
    const location = new URL(details.path);
    const base = `${config.productName} OneLake ${short(tenant.fabric.workspaceId)}`;
    const names = [base, `${base} ${short(tenant.identity?.appId || config.clientId || 'platform')}`];
    const visible = await client.listConnections();
    const existing = visible.find((c) => names.includes(c.displayName) && c.connectionDetails?.path === details.path);
    if (existing) return existing;
    const request = (displayName) => ({
      connectivityType: 'ShareableCloud',
      displayName,
      connectionDetails: {
        type: details.type,
        creationMethod: details.type,
        parameters: [
          { dataType: 'Text', name: 'server', value: location.origin },
          { dataType: 'Text', name: 'path', value: location.pathname },
        ],
      },
      privacyLevel: 'Organizational',
      credentialDetails: { singleSignOnType: 'None', connectionEncryption: 'NotEncrypted', skipTestConnection: false, credentials: { credentialType: 'WorkspaceIdentity' } },
    });
    let name = names[0];
    if (visible.some((c) => c.displayName === name)) name = names[1];
    const mine = (list) => list.find((c) => names.includes(c.displayName) && c.connectionDetails?.path === details.path);
    // The connection test runs as the workspace identity, whose new role can take a minute to apply.
    for (let attempt = 1; ; attempt++) {
      try {
        return await client.createConnection(request(name));
      } catch (error) {
        // A create whose response was lost may still have worked: look again before retrying, so a retry never
        // leaves a second connection behind.
        const created = mine(await client.listConnections().catch(() => []));
        if (created) return created;
        // Connection names are unique in the Fabric tenant, and a connection another identity owns doesn't show up in
        // the caller's list, so a clash only shows up as this error. The second name carries the caller's app ID.
        if (name === names[0] && (error.upstreamStatus === 409 || /already ?exists|duplicate|in use/i.test(`${error.code || ''} ${error.message}`))) {
          name = names[1];
          continue;
        }
        if (attempt >= 5) throw error;
        await sleep(waitMs);
      }
    }
  }

  // Direct Lake "refresh" is framing: the model starts reading the latest Delta versions. No data is copied.
  // Right after a schema upgrade the replica can lag the database for a minute, so a failed framing is retried.
  async function frame(client, workspaceId, modelId) {
    for (let round = 1; ; round++) {
      const { requestId } = await client.pbiRefreshDataset(workspaceId, modelId);
      let failure = null;
      for (let attempt = 0; attempt < 60; attempt++) {
        await sleep(refreshPollMs);
        const [latest] = await client.pbiListRefreshes(workspaceId, modelId, 1);
        if (!latest || (requestId && latest.requestId && latest.requestId !== requestId)) continue;
        if (latest.status === 'Completed') return round > 1 ? `framed on the latest data (after ${round} tries)` : 'framed on the latest data';
        if (latest.status === 'Failed') {
          failure = latest.serviceExceptionJson || 'no details';
          break;
        }
      }
      if (!failure) return 'framing is still running';
      if (round >= 4) throw new Error(`Framing failed: ${failure}`);
      await sleep(waitMs * 3);
    }
  }

  async function ensureModelConnection(tenant, client, kind = 'reports') {
    const spec = MODELS[kind];
    const workspaceId = tenant.fabric.workspaceId;
    const modelId = tenant.fabric[spec.id];
    const references = await client.listItemConnections(workspaceId, modelId);
    const reference = references.find((r) => r.connectionDetails?.type === 'AzureDataLakeStorage') || references[0];
    if (!reference) throw new Error('The model has no data source to connect yet.');
    // A connection belongs to whoever created it. When a customer's work moves from the platform identity to its own
    // service account, the account binds the model to a connection of its own, so nothing depends on the platform.
    const ownerKey = `${spec.connection}Owner`;
    const owner = connectionOwner(tenant);
    const previous = tenant.fabric[spec.connection];
    const previousOwner = tenant.fabric[ownerKey] || 'platform';
    const bound = reference.connectivityType === 'ShareableCloud' && reference.id && sameId(reference.id, previous);
    let detail;
    if (bound && previousOwner === owner) {
      detail = `Uses ${reference.displayName || 'its connection'}`;
    } else {
      const connection = await ensureConnection(tenant, client, reference.connectionDetails);
      const binding = { id: connection.id, connectivityType: 'ShareableCloud', connectionDetails: { type: reference.connectionDetails.type, path: reference.connectionDetails.path } };
      try {
        await client.bindSemanticModelConnection(workspaceId, modelId, binding);
      } catch (error) {
        // Only the model's owner can bind it (Fabric answers 400 BindNotModelOwner); the service account takes it over
        // (it is workspace Admin) and retries.
        if (!notModelOwner(error)) throw error;
        await client.pbiTakeOverDataset(workspaceId, modelId);
        await client.bindSemanticModelConnection(workspaceId, modelId, binding);
      }
      // The platform identity deletes the connection it no longer uses before it gives up the workspace. It's the one
      // recorded here, which Fabric may not even show to the service account.
      const handedOver = previous && previousOwner === 'platform' && owner !== 'platform' && !sameId(previous, connection.id);
      if (handedOver) tenant.fabric.retiredConnections = [...new Set([...(tenant.fabric.retiredConnections || []), previous])];
      tenant.fabric[spec.connection] = connection.id;
      tenant.fabric[ownerKey] = owner;
      detail = `Bound to ${connection.displayName} (workspace identity, no single sign-on${handedOver ? `; taken over by ${tenant.identity?.name || 'the service account'}` : ''})`;
    }
    return `${detail}; ${await frame(client, workspaceId, modelId)}`;
  }

  // Connections the service account replaced, deleted by the platform identity that owns them.
  async function deleteRetiredConnections(tenant) {
    const inUse = new Set([tenant.fabric.modelConnectionId, tenant.fabric.assistantConnectionId].filter(Boolean).map((id) => id.toLowerCase()));
    const left = [];
    for (const id of tenant.fabric.retiredConnections || []) {
      if (inUse.has(id.toLowerCase())) continue;
      try {
        await fabric.deleteConnection(id);
      } catch (error) {
        if (error.upstreamStatus !== 404) left.push(id);
      }
    }
    tenant.fabric.retiredConnections = left;
    return left;
  }

  // Least privilege for the control plane: once the customer's service account runs everything, the platform
  // identity gives up its own role in the workspace.
  async function releasePlatformAccess(tenant) {
    if (identities.usesPlatformIdentity(tenant) || tenant.identity?.workspaceRole !== 'Admin') {
      return { status: 'warning', detail: 'Kept: the platform can only hand over to a customer service account that is Admin, and there is none yet' };
    }
    const workspaceId = tenant.fabric.workspaceId;
    const scoped = await identities.fabricFor(tenant);
    const roles = await scoped.listRoleAssignments(workspaceId);
    const own = roles.find((r) => sameId(r.principal?.id, tenant.identity.objectId));
    if (own?.role !== 'Admin') throw new Error(`${tenant.identity.name} isn't Admin of the workspace, so the platform keeps its access.`);
    const left = await deleteRetiredConnections(tenant);
    if (left.length) throw new Error(`The platform identity couldn't delete the connection(s) it no longer uses (${left.join(', ')}), so it keeps its access. Run provisioning again.`);
    const me = await platformPrincipalId();
    const platformRole = roles.find((r) => sameId(r.principal?.id, me));
    if (platformRole) await scoped.deleteRoleAssignment(workspaceId, platformRole.id);
    tenant.fabric.platformReleased = true;
    return platformRole
      ? `Released: the platform identity no longer has a role here; ${tenant.identity.name} manages the workspace`
      : `The platform identity has no standing access; ${tenant.identity.name} manages the workspace`;
  }

  async function stamp(tenant, client, plan) {
    const { results, warnings } = await stampTemplates({
      fabric: client,
      templateFabric: fabric,
      templateWorkspaceId: config.templateWorkspaceId,
      target: { workspaceId: tenant.fabric.workspaceId, workspaceName: tenant.fabric.workspaceName },
      allowedTypes: plan.templateTypes,
    });
    tenant.fabric.templateItems = results.filter((r) => r.id).map(({ type, name, id }) => ({ type, name, id }));
    for (const warning of warnings) addActivity(tenant, warning, 'warning');
    const failed = results.filter((r) => r.action === 'failed');
    if (failed.length) throw new Error(failed.map((f) => `${f.type} "${f.name}": ${f.error}`).join('; '));
    const created = results.filter((r) => r.action === 'created').length;
    return `${created} created, ${results.length - created} already present`;
  }

  // Without a template workspace, every customer starts with the generated "Sales overview" report on their own model.
  // It's created once and never overwritten afterwards, because the customer may have edited it.
  async function ensureStarterReport(tenant, client) {
    const workspaceId = tenant.fabric.workspaceId;
    const named = async () => (await client.listItems(workspaceId, 'Report')).filter((i) => i.displayName === STARTER_REPORT_NAME);
    const existing = await named();
    if (existing.length) {
      tenant.fabric.starterReportId = existing[0].id;
      return `${STARTER_REPORT_NAME} is in place`;
    }
    const { definition } = buildStarterReportDefinition({ semanticModelId: tenant.fabric.semanticModelId });
    const created = await client.createItem(workspaceId, {
      displayName: STARTER_REPORT_NAME,
      type: 'Report',
      description: `Pipeline, revenue and accounts for ${tenant.name}. Each person sees the territories they cover.`,
      definition,
    });
    tenant.fabric.starterReportId = created?.id || (await named())[0]?.id;
    return `Created ${STARTER_REPORT_NAME}`;
  }

  async function ensureDataAgent(tenant, client) {
    const workspaceId = tenant.fabric.workspaceId;
    const definition = buildSemanticModelAgentDefinition({
      workspaceId,
      semanticModelId: tenant.fabric.assistantModelId,
      semanticModelName: ASSISTANT_MODEL_NAME,
      tables: agentTables(),
      instructions: agentInstructions(tenant.name, { charts: config.dataAgentCodeInterpreter }),
      description: agentDescription(tenant.name),
      codeInterpreter: config.dataAgentCodeInterpreter,
    });
    const agents = await client.listItems(workspaceId, CORE_ITEMS.dataAgent.type);
    let agent = agents.find((a) => a.displayName === CORE_ITEMS.dataAgent.name);
    const fingerprint = createHash('sha256').update(JSON.stringify(definition.parts)).digest('hex').slice(0, 16);
    let detail;
    if (!agent) {
      agent = await client.createItem(workspaceId, { displayName: CORE_ITEMS.dataAgent.name, type: CORE_ITEMS.dataAgent.type, description: agentDescription(tenant.name), definition });
      agent ||= (await client.listItems(workspaceId, CORE_ITEMS.dataAgent.type)).find((a) => a.displayName === CORE_ITEMS.dataAgent.name);
      detail = `Created and published ${CORE_ITEMS.dataAgent.name} over ${ASSISTANT_MODEL_NAME}`;
    } else {
      const source = agentModelSource((await client.getItemDefinition(workspaceId, agent.id))?.definition);
      // A new model version (new columns, measures or descriptions) is pushed to the agent as well.
      if (!sameId(source?.artifactId, tenant.fabric.assistantModelId) || tenant.fabric.dataAgentFingerprint !== fingerprint) {
        await client.updateItemDefinition(workspaceId, agent.id, definition);
        detail = `Updated ${CORE_ITEMS.dataAgent.name} to the current ${ASSISTANT_MODEL_NAME} and published it`;
      } else detail = `${CORE_ITEMS.dataAgent.name} is up to date`;
    }
    tenant.fabric.dataAgentId = agent.id;
    tenant.fabric.dataAgentFingerprint = fingerprint;
    // With the data integration add-on, the customer's own tables become a second source.
    if (entitlements(tenant).resources.lakehouse && tenant.fabric.lakehouseId) {
      const sync = await syncDataAgent({ fabric: client, tenant });
      if (sync.added?.length) detail += `; added ${sync.added.length} loaded table(s)`;
    }
    return detail;
  }

  function stepsFor(tenant) {
    const { plan, resources } = entitlements(tenant);
    return [
      { key: 'workspace', title: 'Create the workspace', run: ensureWorkspace },
      { key: 'capacity', title: 'Assign the Fabric capacity', run: ensureCapacity },
      { key: 'service-account', title: 'Set up the customer service account', run: ensureServiceAccount },
      { key: 'ops-access', title: 'Give the support team read access', enabled: Boolean(config.opsPrincipal), run: ensureOpsAccess },
      { key: 'crm-database', title: 'Create the CRM database', enabled: resources.crm, scoped: true, run: ensureCrmDatabase },
      { key: 'crm-schema', title: 'Create or upgrade the CRM tables', enabled: resources.crm, run: ensureCrmSchema },
      { key: 'crm-sample-data', title: 'Load sample CRM data', enabled: resources.crm && tenant.sampleData !== false, run: seedCrm },
      { key: 'lakehouse', title: 'Create the lakehouse (data integration)', enabled: Boolean(resources.lakehouse), scoped: true, run: (t, c) => ensureItem(t, c, CORE_ITEMS.lakehouse, 'lakehouseId') },
      { key: 'workspace-identity', title: 'Set up the workspace identity', enabled: resources.semanticModel, scoped: true, run: ensureWorkspaceIdentity },
      { key: 'semantic-model', title: `Publish the ${MODEL_NAME} model`, enabled: resources.semanticModel, scoped: true, run: (t, c) => ensureSemanticModel(t, c, 'reports') },
      { key: 'model-connection', title: 'Connect the model to the CRM data', enabled: resources.semanticModel, scoped: true, run: (t, c) => ensureModelConnection(t, c, 'reports') },
      { key: 'starter-report', title: 'Create the starter report', enabled: resources.semanticModel && !config.templateWorkspaceId, scoped: true, run: ensureStarterReport },
      { key: 'templates', title: 'Copy the template reports', enabled: Boolean(config.templateWorkspaceId), scoped: true, run: (t, c) => stamp(t, c, plan) },
      {
        key: 'assistant-model',
        title: "Publish the assistant's model",
        enabled: Boolean(resources.dataAgent),
        scoped: true,
        run: async (t, c) => `${await ensureSemanticModel(t, c, 'assistant')}; ${await ensureModelConnection(t, c, 'assistant')}`,
      },
      { key: 'data-agent', title: 'Set up the assistant', enabled: resources.dataAgent, scoped: true, run: ensureDataAgent },
      { key: 'platform-access', title: 'Release the platform identity', enabled: releaseMode, noRetain: true, run: releasePlatformAccess },
    ];
  }

  async function run(tenantId) {
    const tenant = store.get(tenantId);
    if (!tenant) throw new Error(`Unknown tenant ${tenantId}`);
    const { plan } = entitlements(tenant);
    const steps = stepsFor(tenant);
    tenant.status = 'provisioning';
    tenant.error = null;
    // Steps from earlier versions of the platform no longer apply; the rest are listed in the order they run.
    const previousSteps = tenant.steps || {};
    tenant.steps = Object.fromEntries(steps.map((s) => [s.key, previousSteps[s.key] || { status: 'pending', title: s.title }]));
    addActivity(tenant, `Provisioning started for the ${plan.name} edition`);
    await store.save(tenant);
    for (const step of steps) {
      const previous = tenant.steps[step.key];
      if (step.enabled === false) {
        tenant.steps[step.key] =
          !step.noRetain && (previous?.status === 'done' || previous?.status === 'retained')
            ? { status: 'retained', title: step.title, at: now(), detail: 'Kept from an earlier edition; not part of this one' }
            : { status: 'skipped', title: step.title, at: now(), detail: SKIP_REASONS[step.key] || 'Not part of this edition' };
        continue;
      }
      tenant.steps[step.key] = { status: 'running', title: step.title, at: now() };
      await store.save(tenant);
      try {
        const client = step.scoped ? await identities.fabricFor(tenant) : fabric;
        const result = await step.run(tenant, client);
        const { status = 'done', detail } = typeof result === 'object' && result ? result : { detail: result };
        tenant.steps[step.key] = { status, title: step.title, at: now(), detail };
        addActivity(tenant, `${step.title}: ${detail}`, status === 'warning' ? 'warning' : 'info');
      } catch (error) {
        const message = error?.message || String(error);
        tenant.steps[step.key] = { status: 'failed', title: step.title, at: now(), error: message };
        tenant.status = 'failed';
        tenant.error = `${step.title} failed: ${message}`;
        addActivity(tenant, tenant.error, 'error');
        await store.save(tenant);
        return tenant;
      }
      await store.save(tenant);
    }
    tenant.status = 'ready';
    tenant.provisionedAt = now();
    addActivity(tenant, `${tenant.name} is ready`);
    await store.save(tenant);
    return tenant;
  }

  // One run per customer at a time, and at most `maxConcurrent` customers at once, so onboarding many customers
  // doesn't turn into a throttling storm against the Fabric APIs.
  function provision(tenantId) {
    if (running.has(tenantId)) return running.get(tenantId);
    const promise = limiter
      .run(() => run(tenantId))
      .catch(async (error) => {
        const tenant = store.get(tenantId);
        if (tenant) {
          tenant.status = 'failed';
          tenant.error = `Provisioning stopped: ${error.message}`;
          addActivity(tenant, tenant.error, 'error');
          await store.save(tenant).catch(() => {});
        }
        return tenant;
      })
      .finally(() => running.delete(tenantId));
    running.set(tenantId, promise);
    return promise;
  }

  async function deprovision(tenantId, { keepWorkspace = false, keepIdentity = keepWorkspace } = {}) {
    await running.get(tenantId);
    const tenant = store.get(tenantId);
    if (!tenant) return;
    const client = await identities.fabricFor(tenant).catch(() => fabric);
    // A workspace that stays behind must stay reachable by the control plane, not only by the customer's account.
    if (keepWorkspace && tenant.fabric.workspaceId && tenant.fabric.platformReleased) {
      await reattachPlatform(tenant, 'keep the workspace after the customer was removed');
    }
    if (!keepWorkspace && tenant.fabric.workspaceId) {
      tenant.status = 'deprovisioning';
      addActivity(tenant, 'Deleting the workspace');
      await store.save(tenant);
      // Connections live outside the workspace, so they'd outlive it. Both models normally share one; connections the
      // service account replaced belong to the platform identity.
      for (const id of new Set([tenant.fabric.modelConnectionId, tenant.fabric.assistantConnectionId].filter(Boolean))) await client.deleteConnection(id).catch(() => {});
      for (const id of tenant.fabric.retiredConnections || []) await fabric.deleteConnection(id).catch(() => {});
      try {
        await client.deleteWorkspace(tenant.fabric.workspaceId);
      } catch (error) {
        let failure = error;
        if ([401, 403].includes(error.upstreamStatus) && client !== fabric) failure = await fabric.deleteWorkspace(tenant.fabric.workspaceId).then(() => null, (e) => e);
        if (failure && failure.upstreamStatus !== 404) {
          tenant.status = 'failed';
          tenant.error = `Deleting the workspace failed: ${failure.message}`;
          addActivity(tenant, tenant.error, 'error');
          await store.save(tenant);
          throw failure;
        }
      }
    }
    await crm.forget(tenant.id, { deleteData: !keepWorkspace });
    if (!keepIdentity) await identities.remove(tenant).catch(() => {});
    identities.forget(tenant.id);
    await store.remove(tenantId);
  }

  return { provision, deprovision, isBusy: (tenantId) => running.has(tenantId), stats: () => ({ ...limiter.stats(), running: running.size }) };
}
