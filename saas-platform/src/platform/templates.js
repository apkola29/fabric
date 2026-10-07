import { decodePayload, encodePayload, isTextPart } from '../util/definition.js';

// "Golden template" stamping: copy items from a template workspace into a customer workspace, rewriting every
// reference (workspace ID, item IDs, SQL endpoint IDs and host names) so the copy points at the customer's own data.

// Items that other items reference are created first.
export const STAMP_ORDER = ['VariableLibrary', 'Environment', 'Notebook', 'SparkJobDefinition', 'Dataflow', 'DataPipeline', 'CopyJob', 'SemanticModel', 'Report', 'DataAgent'];
const DATA_ITEM_TYPES = ['Lakehouse', 'Warehouse', 'SQLDatabase'];

const escapeRegExp = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// One pass, longest match first, case-insensitive (GUIDs show up in either case), so replacements never chain.
export function buildReplacer(pairs) {
  const entries = pairs.filter(([from, to]) => from && to && String(from).toLowerCase() !== String(to).toLowerCase());
  if (entries.length === 0) return (text) => text;
  const lookup = new Map();
  for (const [from, to] of entries) if (!lookup.has(String(from).toLowerCase())) lookup.set(String(from).toLowerCase(), String(to));
  const pattern = new RegExp([...lookup.keys()].sort((a, b) => b.length - a.length).map(escapeRegExp).join('|'), 'gi');
  return (text) => text.replace(pattern, (match) => lookup.get(match.toLowerCase()) ?? match);
}

// The .platform part carries the template item's own metadata, so it's dropped; binary parts pass through untouched.
export function remapParts(parts, replace) {
  return parts
    .filter((part) => part.path !== '.platform')
    .map((part) => (isTextPart(part) ? { ...part, payload: encodePayload(replace(decodePayload(part.payload))) } : { ...part }));
}

async function connectionPairs(sourceFabric, targetFabric, type, from, to) {
  if (type === 'Lakehouse') {
    const [a, b] = await Promise.all([sourceFabric.getLakehouse(from.workspaceId, from.id), targetFabric.getLakehouse(to.workspaceId, to.id)]);
    const sa = a?.properties?.sqlEndpointProperties || {};
    const sb = b?.properties?.sqlEndpointProperties || {};
    return [[sa.id, sb.id], [sa.connectionString, sb.connectionString]];
  }
  if (type === 'Warehouse') {
    const [a, b] = await Promise.all([sourceFabric.getWarehouse(from.workspaceId, from.id), targetFabric.getWarehouse(to.workspaceId, to.id)]);
    return [[a?.properties?.connectionString, b?.properties?.connectionString]];
  }
  if (type === 'SQLDatabase') {
    const [a, b] = await Promise.all([sourceFabric.getSqlDatabase(from.workspaceId, from.id), targetFabric.getSqlDatabase(to.workspaceId, to.id)]);
    const host = (db) => db?.properties?.serverFqdn?.split(',')[0];
    return [[host(a), host(b)], [a?.properties?.databaseName, b?.properties?.databaseName]];
  }
  return [];
}

// Least privilege: the template workspace is read with the platform identity (`templateFabric`), and the copies are
// written with the customer's own identity (`fabric`), which has no access to the template or to other customers.
export async function stampTemplates({ fabric, templateFabric = fabric, templateWorkspaceId, target, allowedTypes }) {
  const [template, sourceItems, existing] = await Promise.all([
    templateFabric.getWorkspace(templateWorkspaceId),
    templateFabric.listItems(templateWorkspaceId),
    fabric.listItems(target.workspaceId),
  ]);
  const pairs = [[templateWorkspaceId, target.workspaceId]];
  // Power BI connection strings name the workspace: powerbi://api.powerbi.com/v1.0/myorg/<workspace name>
  if (template.displayName && target.workspaceName) {
    pairs.push([`myorg/${template.displayName}`, `myorg/${target.workspaceName}`]);
    pairs.push([`myorg/${encodeURIComponent(template.displayName)}`, `myorg/${encodeURIComponent(target.workspaceName)}`]);
  }

  const warnings = [];
  for (const source of sourceItems.filter((i) => DATA_ITEM_TYPES.includes(i.type))) {
    const match = existing.find((i) => i.type === source.type && i.displayName === source.displayName);
    if (!match) {
      warnings.push(`The template's ${source.type} "${source.displayName}" has no counterpart in this workspace, so references to it are left as they are.`);
      continue;
    }
    pairs.push([source.id, match.id]);
    try {
      pairs.push(...(await connectionPairs(templateFabric, fabric, source.type, { workspaceId: templateWorkspaceId, id: source.id }, { workspaceId: target.workspaceId, id: match.id })));
    } catch (error) {
      warnings.push(`Couldn't read connection details for ${source.displayName}: ${error.message}`);
    }
  }
  // Items the customer already has under the same name (such as the semantic model the platform published) stand in
  // for the template's copies, so copied reports point at the customer's own model.
  for (const source of sourceItems.filter((i) => !DATA_ITEM_TYPES.includes(i.type))) {
    const match = existing.find((i) => i.type === source.type && i.displayName === source.displayName);
    if (match) pairs.push([source.id, match.id]);
  }

  const candidates = sourceItems
    .filter((i) => allowedTypes.includes(i.type) && STAMP_ORDER.includes(i.type))
    .sort((a, b) => STAMP_ORDER.indexOf(a.type) - STAMP_ORDER.indexOf(b.type));
  const results = [];
  for (const source of candidates) {
    const present = existing.find((i) => i.type === source.type && i.displayName === source.displayName);
    if (present) {
      pairs.push([source.id, present.id]);
      results.push({ type: source.type, name: source.displayName, id: present.id, action: 'exists' });
      continue;
    }
    try {
      const { definition } = await templateFabric.getItemDefinition(templateWorkspaceId, source.id);
      const replace = buildReplacer(pairs);
      let created = await fabric.createItem(target.workspaceId, {
        displayName: source.displayName,
        type: source.type,
        description: source.description || undefined,
        definition: { ...(definition.format ? { format: definition.format } : {}), parts: remapParts(definition.parts, replace) },
      });
      if (!created?.id) {
        created = (await fabric.listItems(target.workspaceId, source.type)).find((i) => i.displayName === source.displayName);
      }
      pairs.push([source.id, created.id]);
      results.push({ type: source.type, name: source.displayName, id: created.id, action: 'created' });
    } catch (error) {
      results.push({ type: source.type, name: source.displayName, action: 'failed', error: error.message });
    }
  }
  return { results, warnings };
}
