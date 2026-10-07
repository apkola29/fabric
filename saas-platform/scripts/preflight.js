// Checks that the configured identity can do what the platform needs. Never prints tokens or secrets.
// Usage: node --env-file-if-exists=.env scripts/preflight.js [--check-create]
//   --check-create  also creates and deletes a temporary workspace, to prove the identity may create workspaces.

import { SCOPES, createTokenProvider } from '../src/auth/tokens.js';
import { loadConfig } from '../src/config.js';
import { createFabricClient } from '../src/fabric/client.js';

const LABEL = { ok: 'OK  ', warn: 'WARN', fail: 'FAIL', skip: 'SKIP' };
const results = [];
function report(status, title, detail = '') {
  results.push(status);
  console.log(`${LABEL[status]}  ${title}${detail ? `: ${detail}` : ''}`);
}

function readClaims(token) {
  const payload = token.split('.')[1] || '';
  return JSON.parse(Buffer.from(payload.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'));
}

const accessHint = (error) =>
  error.upstreamStatus === 401 || error.upstreamStatus === 403
    ? ' Check the tenant setting "Service principals can call Fabric public APIs" and that this app is in the allowed security group.'
    : '';

let config;
try {
  config = loadConfig();
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
if (config.authMode === 'mock') {
  console.log('FABRIC_AUTH_MODE is mock, so there is nothing to check. Set it to sp or cli.');
  process.exit(0);
}

const tokens = createTokenProvider(config);
const fabric = createFabricClient({ tokens, endpoints: config.endpoints, maxRetries: 2 });

// 1. Tokens for every API the platform calls.
let claims = null;
for (const [name, scope] of Object.entries(SCOPES)) {
  try {
    const token = await tokens.getToken(scope);
    const tokenClaims = readClaims(token);
    if (name === 'fabric') claims = tokenClaims;
    report('ok', `Token for ${name}`, `valid until ${new Date(tokenClaims.exp * 1000).toISOString()}`);
  } catch (error) {
    report('fail', `Token for ${name}`, error.message);
  }
}
if (claims) {
  const isApp = claims.idtyp === 'app' || (!claims.upn && !claims.unique_name);
  report(
    'ok',
    'Identity',
    isApp
      ? `service principal for app ${claims.appid || claims.azp}, object ID ${claims.oid}, tenant ${claims.tid}`
      : `user ${claims.upn || claims.unique_name}, tenant ${claims.tid}`,
  );
  if (claims.roles?.length) {
    report('warn', 'Application permissions in the token', `${claims.roles.join(', ')}. Fabric authorizes service principals through tenant settings and workspace roles, not these.`);
  }
}

// 2. Fabric API access.
let fabricOk = false;
try {
  const workspaces = await fabric.listWorkspaces();
  fabricOk = true;
  report('ok', 'Fabric API access', `the identity is a member of ${workspaces.length} workspace(s)`);
} catch (error) {
  report('fail', 'Fabric API access', `${error.message}${accessHint(error)}`);
}

// 3. Capacities the identity can assign workspaces to.
let capacities = [];
if (fabricOk) {
  try {
    capacities = await fabric.listCapacities();
    if (!capacities.length) report('warn', 'Capacities', 'none visible. Make the identity a Contributor or Admin on a Fabric capacity.');
    for (const c of capacities) report(c.state === 'Active' ? 'ok' : 'warn', `Capacity ${c.displayName}`, `${c.sku}, ${c.region}, ${c.state}, ID ${c.id}`);
  } catch (error) {
    report('fail', 'Capacities', error.message);
  }
}
if (config.capacityId) {
  const match = capacities.find((c) => c.id.toLowerCase() === config.capacityId.toLowerCase());
  if (!match) report('fail', 'FABRIC_CAPACITY_ID', "the identity can't see this capacity. Add it as a capacity Contributor.");
  else report(match.state === 'Active' ? 'ok' : 'warn', 'FABRIC_CAPACITY_ID', `${match.displayName} is ${match.state}`);
} else report('warn', 'FABRIC_CAPACITY_ID', 'not set');

// 4. Template workspace (read definitions needs Contributor or higher).
if (config.templateWorkspaceId && fabricOk) {
  try {
    const ws = await fabric.getWorkspace(config.templateWorkspaceId);
    const items = await fabric.listItems(ws.id);
    report('ok', 'Template workspace', `${ws.displayName} has ${items.length} item(s)`);
  } catch (error) {
    report('fail', 'Template workspace', `${error.message} Add the identity to the template workspace as Contributor.`);
  }
} else report('skip', 'Template workspace', 'FABRIC_TEMPLATE_WORKSPACE_ID is not set');

// 5. Workspace creation (tenant setting "Service principals can create workspaces, connections, and deployment pipelines").
if (process.argv.includes('--check-create') && fabricOk) {
  const name = `${config.workspacePrefix}preflight-${Date.now().toString(36)}`;
  try {
    const ws = await fabric.createWorkspace({
      displayName: name,
      description: 'Temporary workspace created by the platform preflight check. Safe to delete.',
      capacityId: config.capacityId || undefined,
    });
    report('ok', 'Create a workspace', `created ${name}${config.capacityId ? ' on the capacity' : ''}`);
    try {
      await fabric.deleteWorkspace(ws.id);
      report('ok', 'Delete a workspace', `deleted ${name}`);
    } catch (error) {
      report('warn', 'Delete a workspace', `${error.message} Delete ${name} by hand.`);
    }
  } catch (error) {
    const hint =
      error.upstreamStatus === 401 || error.upstreamStatus === 403
        ? ' Check the tenant setting "Service principals can create workspaces, connections, and deployment pipelines", and capacity Contributor rights.'
        : '';
    report('fail', 'Create a workspace', `${error.message}${hint}`);
  }
} else report('skip', 'Create a workspace', 'run with --check-create to try it (creates and deletes a temporary workspace)');

const failures = results.filter((s) => s === 'fail').length;
console.log(failures ? `\n${failures} check(s) failed.` : '\nAll required checks passed.');
process.exit(failures ? 1 : 0);
