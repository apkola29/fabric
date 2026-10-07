import { CRM_SCHEMA_VERSION } from '../crm/workload.js';
import { entitlements } from './plans.js';

// Least-privilege and drift audit for one customer. Compares what Fabric actually has with what the platform expects
// and flags access that is broader than needed. Read-only, so it's safe to run at any time (CLI: audit <customer>).
//
// Expected access to a customer workspace:
//   customer service account   Admin        runs everything for this customer, and nothing for anyone else
//   platform identity          Admin (keep) or none (release): the control plane only
//   workspace identity         Contributor  Direct Lake on OneLake needs Read + ReadAll; Viewer has no ReadAll
//   support group (optional)   Viewer       read-only troubleshooting
//   anyone else                flagged

const RANK = { Viewer: 1, Contributor: 2, Member: 3, Admin: 4 };
const DAY_MS = 86_400_000;
const sameId = (a, b) => Boolean(a && b) && String(a).toLowerCase() === String(b).toLowerCase();
const short = (id) => String(id || '').slice(0, 8);
const IGNORED_ITEM_TYPES = new Set(['Report', 'SQLEndpoint', 'Dashboard']);

export async function auditTenant({ tenant, fabric, identities, config, now = () => Date.now() }) {
  const checks = [];
  const add = (key, status, title, detail) => checks.push({ key, status, title, detail });
  const { resources } = entitlements(tenant);
  const releaseMode = config.platformWorkspaceAccess === 'release';
  const workspaceId = tenant.fabric?.workspaceId;
  const identity = tenant.identity;
  const shared = identities.usesPlatformIdentity(tenant);

  // The customer's own service account
  if (identities.mode === 'off') {
    add('service-account', 'warn', 'Customer service account', 'TENANT_IDENTITY_MODE=off: every call for this customer runs as the shared platform identity.');
  } else if (!identity?.appId) {
    add('service-account', identities.mode === 'required' ? 'fail' : 'warn', 'Customer service account', `None yet, so calls for ${tenant.name} use the shared platform identity. Create ${identities.describe(tenant).name} to isolate this customer.`);
  } else if (shared) {
    add('service-account', 'warn', 'Customer service account', `${identity.name} exists, but calls fall back to the shared platform identity (its credential is missing or it's disabled).`);
  } else {
    const type = identity.credentialType || 'secret';
    const label = { federated: 'federated credential', certificate: 'certificate', secret: 'client secret' }[type] || type;
    const until = identity.credentialExpiresAt || identity.secretExpiresAt || null;
    const expires = until ? Date.parse(until) : null;
    if (expires && expires < now()) add('service-account', 'fail', 'Customer service account', `${identity.name}'s ${label} expired on ${until.slice(0, 10)}. ${type === 'certificate' ? 'Register a new certificate' : 'Rotate it'}.`);
    else if (expires && expires - now() < 30 * DAY_MS) add('service-account', 'warn', 'Customer service account', `${identity.name}'s ${label} expires on ${until.slice(0, 10)}. ${type === 'certificate' ? 'Register a new certificate' : 'Rotate it'}.`);
    // Microsoft recommends certificates over client secrets; a federated credential has nothing to steal or rotate.
    else if (type === 'secret') add('service-account', 'warn', 'Customer service account', `${identity.name} signs in for ${tenant.name} only, with a client secret${expires ? ` valid until ${until.slice(0, 10)}` : ''}. Switch it to a certificate or a federated credential (scripts/bootstrap-identities.ps1 -Credential Certificate).`);
    else add('service-account', 'pass', 'Customer service account', `${identity.name} signs in for ${tenant.name} only, with a ${label}${expires ? ` valid until ${until.slice(0, 10)}` : ''}.`);
  }

  if (!workspaceId) {
    add('workspace', 'fail', 'Workspace', 'This customer has no workspace yet. Run provisioning.');
    return finish();
  }

  // Reads run as the customer's service account, the same identity the app uses.
  const reader = await identities.fabricFor(tenant);
  const who = shared ? 'The platform identity' : identity.name;

  let roles = null;
  try {
    roles = await reader.listRoleAssignments(workspaceId);
  } catch (error) {
    add('roles', 'fail', 'Workspace roles', `${who} can't read the workspace's roles: ${error.message}`);
  }
  if (roles) await auditRoles(roles);

  let items = null;
  try {
    items = await reader.listItems(workspaceId);
  } catch (error) {
    add('items', 'fail', 'Workspace items', `${who} can't list the workspace's items: ${error.message}`);
  }
  if (items) auditItems(items);

  if (resources.semanticModel && tenant.fabric.semanticModelId) await auditModelConnection();

  try {
    const ws = await reader.getWorkspace(workspaceId);
    const target = tenant.capacityId || config.capacityId;
    if (!ws.capacityId) add('capacity', 'fail', 'Capacity', 'The workspace has no Fabric capacity.');
    else if (target && !sameId(ws.capacityId, target)) add('capacity', 'warn', 'Capacity', `On capacity ${short(ws.capacityId)}; expected ${short(target)}. Run provisioning to move it.`);
    else add('capacity', 'pass', 'Capacity', `${tenant.capacityId ? 'Dedicated' : 'Shared'} capacity ${short(ws.capacityId)}`);
  } catch (error) {
    add('capacity', 'fail', 'Capacity', `${who} can't read the workspace: ${error.message}`);
  }

  if (resources.crm) {
    const version = tenant.fabric.crmSchemaVersion;
    if (version === CRM_SCHEMA_VERSION) add('crm-schema', 'pass', 'CRM schema', `Version ${version} (current)`);
    else add('crm-schema', 'warn', 'CRM schema', `${version ? `Version ${version}` : 'Not recorded'}; version ${CRM_SCHEMA_VERSION} is current. Run provisioning to upgrade.`);
  }

  return finish();

  async function auditRoles(assignments) {
    const platformId = await Promise.resolve(fabric.principalId?.()).catch(() => null);
    const handedOver = !shared && identity?.workspaceRole === 'Admin';
    const expected = [];
    if (identity?.objectId && identities.mode !== 'off') expected.push({ id: identity.objectId, label: `Service account ${identity.name}`, role: 'Admin', missing: 'fail' });
    if (platformId) {
      expected.push(
        releaseMode && handedOver
          ? { id: platformId, label: 'Platform identity', role: null, missing: 'pass' }
          : { id: platformId, label: 'Platform identity', role: 'Admin', missing: shared ? 'fail' : 'warn' },
      );
    }
    const workspaceIdentity = tenant.fabric.workspaceIdentity?.servicePrincipalId;
    if (workspaceIdentity) expected.push({ id: workspaceIdentity, label: 'Workspace identity', role: 'Contributor', missing: 'fail' });
    if (config.opsPrincipal?.id) expected.push({ id: config.opsPrincipal.id, label: 'Support group', role: 'Viewer', missing: 'warn' });

    for (const want of expected) {
      const key = `role:${want.label.split(' ')[0].toLowerCase()}`;
      const found = assignments.find((a) => sameId(a.principal?.id, want.id));
      if (!found) {
        const why = {
          'Platform identity': want.role ? 'the control plane can no longer manage this workspace' : 'released: the platform holds no standing access',
          'Workspace identity': "the model's connection can't read the CRM data",
          'Support group': "support can't see this workspace",
        }[want.label] || "it can't run this customer's work";
        add(key, want.missing, want.label, want.missing === 'pass' ? `No role (${why})` : `No role: ${why}.`);
      } else if (want.role === null) {
        add(key, 'warn', want.label, `Still ${found.role}. PLATFORM_WORKSPACE_ACCESS=release: the next provisioning run hands the workspace over to the service account.`);
      } else if (RANK[found.role] > RANK[want.role]) {
        add(key, 'warn', want.label, `${found.role}, more than it needs: ${want.role} is enough.`);
      } else if (RANK[found.role] < RANK[want.role]) {
        add(key, 'fail', want.label, `${found.role}, but it needs ${want.role}.`);
      } else {
        add(key, want.label === 'Platform identity' ? 'info' : 'pass', want.label, want.label === 'Platform identity' ? `${found.role} (standing access; PLATFORM_WORKSPACE_ACCESS=release removes it)` : found.role);
      }
    }
    const others = assignments.filter((a) => !expected.some((want) => sameId(a.principal?.id, want.id)));
    for (const other of others) {
      const name = other.principal?.displayName || other.principal?.userDetails?.userPrincipalName || short(other.principal?.id);
      add(`role:other:${other.principal?.id}`, 'warn', 'Unmanaged access', `${name} (${other.principal?.type || 'principal'}) has ${other.role}. Remove it unless it's deliberate break-glass access.`);
    }
  }

  function auditItems(list) {
    const managed = [
      ['crmDatabaseId', 'CRM database', resources.crm],
      ['lakehouseId', 'Lakehouse', resources.lakehouse],
      ['semanticModelId', 'Semantic model', resources.semanticModel],
      ['dataAgentId', 'Assistant (data agent)', resources.dataAgent],
      // Kept from an earlier edition: known to the platform, but not part of this one.
      ['warehouseId', 'Warehouse', false],
    ];
    for (const [key, label, wanted] of managed) {
      if (!wanted) continue;
      const id = tenant.fabric[key];
      const found = id && list.find((i) => sameId(i.id, id));
      if (found) add(`item:${key}`, 'pass', label, found.displayName);
      else add(`item:${key}`, 'fail', label, id ? `${short(id)} is no longer in the workspace. Run provisioning to recreate it.` : 'Not created yet. Run provisioning.');
    }
    const managedIds = managed.map(([key]) => tenant.fabric[key]).filter(Boolean);
    const unmanaged = list.filter((i) => !IGNORED_ITEM_TYPES.has(i.type) && !managedIds.some((id) => sameId(id, i.id)));
    if (unmanaged.length) add('items:unmanaged', 'info', 'Items the platform doesn\'t manage', unmanaged.map((i) => `${i.displayName} (${i.type})`).join(', '));
  }

  async function auditModelConnection() {
    const title = "Model's data connection";
    try {
      const references = await reader.listItemConnections(workspaceId, tenant.fabric.semanticModelId);
      const bound = references.find((r) => sameId(r.id, tenant.fabric.modelConnectionId));
      if (!bound) {
        add('model-connection', 'fail', title, "The model isn't bound to the connection the platform created. Run provisioning.");
        return;
      }
      const connection = (await reader.listConnections()).find((c) => sameId(c.id, bound.id));
      const credentials = connection?.credentialDetails || {};
      if (!connection) add('model-connection', 'warn', title, `Bound to ${bound.displayName || short(bound.id)}, but ${who} can't read the connection's settings.`);
      else if (credentials.credentialType !== 'WorkspaceIdentity') add('model-connection', 'warn', title, `Signs in with ${credentials.credentialType || 'unknown credentials'}; the workspace identity needs no stored secret.`);
      else if (credentials.singleSignOnType && credentials.singleSignOnType !== 'None') add('model-connection', 'warn', title, `Single sign-on (${credentials.singleSignOnType}) is on; the platform expects it off.`);
      else add('model-connection', 'pass', title, `${connection.displayName}: workspace identity, no single sign-on, no stored secret`);
    } catch (error) {
      add('model-connection', 'fail', title, `${who} can't read the model's connection: ${error.message}`);
    }
  }

  function finish() {
    const counts = { pass: 0, info: 0, warn: 0, fail: 0 };
    for (const check of checks) counts[check.status] += 1;
    return {
      tenantId: tenant.id,
      tenant: tenant.name,
      at: new Date(now()).toISOString(),
      settings: { identityMode: identities.mode, platformWorkspaceAccess: releaseMode ? 'release' : 'keep' },
      ok: counts.fail === 0,
      counts,
      checks,
    };
  }
}
