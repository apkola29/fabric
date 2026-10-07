import { createHash } from 'node:crypto';
import { decodePayload, encodePayload, jsonPart } from '../util/definition.js';
import { CORE_ITEMS } from './plans.js';

// Data agent definition format: https://learn.microsoft.com/rest/api/fabric/articles/item-management/definitions/data-agent-definition
// Writing both the draft and published parts publishes the agent, which turns on its MCP endpoint.

const SCHEMA_BASE = 'https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition';
export const AGENT_SCHEMAS = Object.freeze({
  dataAgent: `${SCHEMA_BASE}/dataAgent/2.1.0/schema.json`,
  stage: `${SCHEMA_BASE}/stageConfiguration/1.0.0/schema.json`,
  dataSource: `${SCHEMA_BASE}/dataSource/1.0.0/schema.json`,
  fewShots: `${SCHEMA_BASE}/fewShots/1.0.0/schema.json`,
  publishInfo: `${SCHEMA_BASE}/publishInfo/1.0.0/schema.json`,
});

const TABLE = 'lakehouse_tables.table';
const SCHEMA = 'lakehouse_tables.schema';

export function agentInstructions(companyName, { charts = false } = {}) {
  return [
    `You are the Platform app assistant for ${companyName}. You answer questions about their CRM data: accounts, contacts, opportunities (deals), activities and sales reps.`,
    'Always use the measures in the Platform app Insights model instead of adding up columns yourself:',
    '- Pipeline Value and # Open Opportunities cover open deals only (every stage except Closed Won and Closed Lost).',
    '- Won Revenue and # Won Deals cover stage Closed Won. Lost Amount and # Lost Deals cover Closed Lost.',
    '- Win Rate is won deals divided by won plus lost deals. Average Deal Size is Won Revenue divided by # Won Deals.',
    '- Weighted Pipeline multiplies open deal amounts by their win probability.',
    '- For deals, dates mean the Close Date; for activities they mean the Activity Date. Use the Calendar table for periods.',
    '- # Accounts Owned is the number of accounts each sales rep owns.',
    'Amounts are US dollars. Give exact numbers, say which measures you used, and say so when the data cannot answer the question.',
    ...(charts ? ['When someone asks for a chart, a trend over time or a comparison, query the numbers first, then draw one clear chart with the code interpreter: a title, labeled axes, dollars formatted as money.'] : []),
  ].join('\n');
}

export function agentDescription(companyName) {
  return `Answers questions about ${companyName}'s CRM: pipeline, revenue, win rates, accounts, contacts and activities.`;
}

const elementId = (seed) => {
  const h = createHash('sha1').update(seed).digest('hex');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-5${h.slice(13, 16)}-8${h.slice(17, 20)}-${h.slice(20, 32)}`;
};

// A data agent over the semantic model: it sees the same tables, measures and descriptions as the reports.
// `codeInterpreter` adds the agent's Python tool (preview; paid F2+ or P1+ capacity), which can draw charts:
// https://learn.microsoft.com/fabric/data-science/data-agent-code-interpreter
export function buildSemanticModelAgentDefinition({ workspaceId, semanticModelId, semanticModelName, tables, instructions, description, codeInterpreter = false }) {
  const folder = `semantic_model-${semanticModelName}`;
  const datasource = {
    $schema: AGENT_SCHEMAS.dataSource,
    artifactId: semanticModelId,
    workspaceId,
    displayName: semanticModelName,
    type: 'semantic_model',
    userDescription: 'Platform app Insights: the CRM pipeline, revenue and activity model the reports use.',
    dataSourceInstructions: 'Prefer the model measures (Pipeline Value, Won Revenue, Win Rate and so on) over aggregating columns.',
    elements: tables.map((table) => ({
      id: elementId(`table:${table.name}`),
      display_name: table.name,
      type: 'semantic_model.table',
      is_selected: true,
      description: table.description,
      children: [
        ...table.columns.map((c) => ({ id: elementId(`column:${table.name}:${c.name}`), display_name: c.name, type: 'semantic_model.column', is_selected: true, description: c.description })),
        ...table.measures.map((m) => ({ id: elementId(`measure:${table.name}:${m.name}`), display_name: m.name, type: 'semantic_model.measure', is_selected: true, description: m.description })),
      ],
    })),
  };
  const stage = { $schema: AGENT_SCHEMAS.stage, aiInstructions: instructions, ...(codeInterpreter ? { experimental: { codeInterpreterEnabled: true } } : {}) };
  const parts = [jsonPart('Files/Config/data_agent.json', { $schema: AGENT_SCHEMAS.dataAgent })];
  for (const stageName of ['draft', 'published']) {
    parts.push(jsonPart(`Files/Config/${stageName}/stage_config.json`, stage));
    parts.push(jsonPart(`Files/Config/${stageName}/${folder}/datasource.json`, datasource));
  }
  parts.push(jsonPart('Files/Config/publish_info.json', { $schema: AGENT_SCHEMAS.publishInfo, description }));
  return { parts };
}

// The semantic model data source of an agent definition, if it has one.
export function agentModelSource(definition) {
  for (const part of definition?.parts || []) {
    if (!/\/published\/[^/]+\/datasource\.json$/i.test(part.path)) continue;
    const source = JSON.parse(decodePayload(part.payload));
    if (source.type === 'semantic_model') return source;
  }
  return null;
}

const tableElement = (name) => ({ display_name: name, type: TABLE, is_selected: true, children: [] });

export function buildDataAgentDefinition({ workspaceId, lakehouseId, lakehouseName, tables = [], instructions, description }) {
  const folder = `lakehouse_tables-${lakehouseName}`;
  const datasource = {
    $schema: AGENT_SCHEMAS.dataSource,
    artifactId: lakehouseId,
    workspaceId,
    displayName: lakehouseName,
    type: 'lakehouse_tables',
    userDescription: 'Customer lakehouse: the CRM app data plus everything the customer loaded.',
    elements: [{ display_name: 'dbo', type: SCHEMA, is_selected: true, children: tables.map(tableElement) }],
  };
  const stage = { $schema: AGENT_SCHEMAS.stage, aiInstructions: instructions };
  const fewShots = { $schema: AGENT_SCHEMAS.fewShots, fewShots: [] };
  const parts = [jsonPart('Files/Config/data_agent.json', { $schema: AGENT_SCHEMAS.dataAgent })];
  for (const stageName of ['draft', 'published']) {
    parts.push(jsonPart(`Files/Config/${stageName}/stage_config.json`, stage));
    parts.push(jsonPart(`Files/Config/${stageName}/${folder}/datasource.json`, datasource));
    parts.push(jsonPart(`Files/Config/${stageName}/${folder}/fewshots.json`, fewShots));
  }
  parts.push(jsonPart('Files/Config/publish_info.json', { $schema: AGENT_SCHEMAS.publishInfo, description }));
  return { parts };
}

// Adds tables the agent doesn't know about yet, keeping existing elements (and their descriptions) as they are.
export function mergeTableElements(elements, tableNames) {
  const result = Array.isArray(elements) ? structuredClone(elements) : [];
  let container = result.find((e) => e.type === SCHEMA && String(e.display_name).toLowerCase() === 'dbo') || result.find((e) => e.type === SCHEMA);
  let siblings;
  if (container) {
    container.children = container.children || [];
    siblings = container.children;
  } else if (result.some((e) => e.type === TABLE)) {
    siblings = result;
  } else {
    container = { display_name: 'dbo', type: SCHEMA, is_selected: true, children: [] };
    result.push(container);
    siblings = container.children;
  }
  const known = new Set(siblings.filter((e) => e.type === TABLE).map((e) => String(e.display_name).toLowerCase()));
  const added = [];
  for (const name of tableNames) {
    if (known.has(name.toLowerCase())) continue;
    siblings.push(tableElement(name));
    known.add(name.toLowerCase());
    added.push(name);
  }
  return { elements: result, added };
}

export function selectedTables(definition) {
  const names = new Set();
  const walk = (elements) => {
    for (const element of elements || []) {
      if (element.type === TABLE && element.is_selected !== false) names.add(element.display_name);
      walk(element.children);
    }
  };
  for (const part of definition?.parts || []) {
    if (!/\/published\/[^/]+\/datasource\.json$/i.test(part.path)) continue;
    walk(JSON.parse(decodePayload(part.payload)).elements);
  }
  return [...names];
}

// Keeps the agent in step with the lakehouse: every new table becomes queryable by the agent (draft and published).
export async function syncDataAgent({ fabric, tenant }) {
  const { workspaceId, lakehouseId, dataAgentId } = tenant.fabric;
  if (!workspaceId || !lakehouseId || !dataAgentId) return { added: [], skipped: true };
  const tables = (await fabric.listLakehouseTables(workspaceId, lakehouseId)).map((t) => t.name);
  const { definition } = await fabric.getItemDefinition(workspaceId, dataAgentId);
  const parts = definition.parts.filter((p) => p.path !== '.platform');
  const added = new Set();
  let matched = false;
  for (const part of parts) {
    if (!/\/datasource\.json$/i.test(part.path)) continue;
    const datasource = JSON.parse(decodePayload(part.payload));
    if (String(datasource.artifactId).toLowerCase() !== String(lakehouseId).toLowerCase()) continue;
    matched = true;
    const merged = mergeTableElements(datasource.elements, tables);
    merged.added.forEach((name) => added.add(name));
    datasource.elements = merged.elements;
    part.payload = encodePayload(JSON.stringify(datasource, null, 2));
  }
  if (!matched) {
    // The agent (for example one copied from a template) doesn't use this lakehouse yet: add it as a data source.
    const extra = buildDataAgentDefinition({ workspaceId, lakehouseId, lakehouseName: CORE_ITEMS.lakehouse.name, tables, instructions: '', description: '' });
    parts.push(...extra.parts.filter((p) => p.path.endsWith('/datasource.json') || p.path.endsWith('/fewshots.json')));
    tables.forEach((name) => added.add(name));
  }
  if (added.size === 0) return { added: [], tables: tables.length };
  await fabric.updateItemDefinition(workspaceId, dataAgentId, { parts });
  return { added: [...added], tables: tables.length };
}
