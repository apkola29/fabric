import { ALL_TERRITORIES_ROLE, ASSISTANT_MODEL_NAME, DIMENSIONS, MEASURES, MODEL_NAME, daxColumn, daxTable, modelColumn, modelTableName } from './model.js';
import { STARTER_REPORT_NAME, buildStarterReportDefinition } from './report.js';
import { CRM_RELATIONSHIPS, CRM_TABLES, TERRITORIES, tableByName } from './schema.js';

// The model's two layers as files for people and AI tools that build reports (`node scripts/report-assets.js`): the
// measures' DAX for the semantic layer, and the field list and example in the report creation prompt for the
// visualization layer. The checks keep both on the model's names, so a rename fails a test instead of a deployment.
export const MEASURES_FILE = new URL('./report-assets/HiCRM-Insights.measures.dax', import.meta.url);
export const PROMPT_FILE = new URL('./report-assets/report-creation-prompt.md', import.meta.url);

const COUNT_FORMAT = '#,##0';
const COLUMN_KINDS = { id: 'ID', text: 'Text', money: 'Currency', int: 'Whole number', date: 'Date', datetime: 'Date and time', bool: 'True or false' };
const PLACEHOLDER_MODEL_ID = '00000000-0000-0000-0000-000000000000';

const inModel = (table) => table.columns.filter((c) => c.inModel !== false);
const field = (table, name) => `${table}[${name}]`;
const code = (text) => `\`${text}\``;
const cell = (text) => String(text).replace(/\|/g, '\\|');
const list = (items) => (items.length < 2 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items.at(-1)}`);
const daxName = (name) => `[${name.replace(/]/g, ']]')}]`;
const measureKind = (m) => (m.format.includes('%') ? 'Percent' : m.format.includes('$') ? 'Currency' : m.format === COUNT_FORMAT ? 'Count' : 'Number');
const alsoCalled = (name, synonyms = []) => synonyms.filter((s) => s !== name.toLowerCase()).slice(0, 5).join(', ');

function wrap(text, width) {
  const lines = [];
  let line = '';
  for (const word of text.split(' ')) {
    if (line && line.length + word.length + 1 > width) {
      lines.push(line);
      line = word;
    } else line = line ? `${line} ${word}` : word;
  }
  return line ? [...lines, line] : lines;
}

// The semantic layer: every measure as a DAX query that DAX query view or DAX Studio can run against the model.
export function measuresDax() {
  const lines = [
    `// ${MODEL_NAME}: every measure (the semantic layer).`,
    '//',
    '// Generated from MEASURES in src/crm/model.js by `node scripts/report-assets.js`: change model.js, not this file.',
    '// Reports bind to these measures by name and carry no DAX (see report-creation-prompt.md).',
    '//',
    '// Naming conventions (test/report-assets.test.js checks the names, references, prefixes and variables):',
    "// - Model names only: 'Opportunities'[Close Date], never the database's opportunities.close_date.",
    "// - Tables are quoted and columns always table-qualified: 'Opportunities'[Amount]. Measures never are: [Total Amount].",
    '// - Measure names are unique, in Title Case, and live on the table they describe. Counts start with "# ",',
    '//   time intelligence ends in "(ytd)" or "(ly)", and variables start with "_".',
    '// - Column filters use KEEPFILTERS (time intelligence replaces the date filter on purpose); ratios use DIVIDE.',
    '// - Every measure has a display folder, a format string and a description.',
    '//',
    "// To try it, run it in DAX query view or DAX Studio: DEFINE MEASURE overrides the model's measure of the same name",
    '// for this query only, and EVALUATE lists every measure by territory.',
    '//',
    '// Tables and columns, as model name <- database column. Hidden columns are for measures, not for report visuals.',
  ];
  for (const table of CRM_TABLES) {
    const columns = inModel(table);
    const width = Math.max(...columns.map((c) => daxName(c.model).length));
    lines.push('//', `// ${daxTable(table.model)} <- dbo.${table.name}`);
    for (const c of columns) lines.push(`//     ${daxName(c.model).padEnd(width)}  <- ${c.name}${c.hidden ? ' (hidden)' : ''}`);
  }
  lines.push('', 'DEFINE');
  for (const table of CRM_TABLES) {
    const measures = MEASURES.filter((m) => m.table === table.name);
    if (!measures.length) continue;
    lines.push(`    // ---- ${table.model} ----`, '');
    for (const m of measures) {
      lines.push(...wrap(m.description, 104).map((line) => `    // ${line}`), `    // Folder: ${m.folder}. Format: ${m.format}`);
      lines.push(`    MEASURE ${daxTable(table.model)}${daxName(m.name)} =`, ...m.expression.split('\n').map((line) => `        ${line}`), '');
    }
  }
  const territory = daxColumn('accounts', 'state');
  lines.push('EVALUATE', '    SUMMARIZECOLUMNS(', `        ${territory},`);
  MEASURES.forEach((m, i) => lines.push(`        "${m.name.replace(/"/g, '""')}", ${daxName(m.name)}${i < MEASURES.length - 1 ? ',' : ''}`));
  lines.push('    )', `ORDER BY ${territory}`, '');
  return lines.join('\n');
}

// Tables a filter on `tableName` reaches: filters flow from the one side to the many side of active relationships.
function reachedFrom(tableName) {
  const reached = new Set([tableName]);
  for (let grew = true; grew; ) {
    grew = false;
    for (const r of CRM_RELATIONSHIPS) {
      if (r.active !== false && reached.has(r.to[0]) && !reached.has(r.from[0])) {
        reached.add(r.from[0]);
        grew = true;
      }
    }
  }
  return CRM_TABLES.filter((t) => t.name !== tableName && reached.has(t.name));
}

function filterFlow() {
  const lines = [];
  for (const target of CRM_TABLES) {
    const into = CRM_RELATIONSHIPS.filter((r) => r.to[0] === target.name);
    const active = into
      .filter((r) => r.active !== false)
      .map(({ from: [table, column] }) => (modelColumn(table, column).hidden ? code(modelTableName(table)) : `${code(modelTableName(table))} by ${code(modelColumn(table, column).model)}`));
    if (active.length) lines.push(`- ${code(target.model)} filters ${list(active)}.`);
    for (const r of into.filter((r) => r.active === false)) {
      const users = MEASURES.filter((m) => m.expression.includes(daxColumn(...r.from))).map((m) => code(field(modelTableName(m.table), m.name)));
      lines.push(`- ${code(target.model)} to ${code(modelTableName(r.from[0]))} is inactive${users.length ? `: only ${list(users)} use${users.length === 1 ? 's' : ''} it` : ''}.`);
    }
  }
  return lines;
}

// The visualization layer's view of the model: names, meanings and filter behaviour, without any DAX.
export function fieldReference() {
  const reached = reachedFrom('accounts');
  const unsecured = CRM_TABLES.filter((t) => t.name !== 'accounts' && !reached.includes(t));
  const synonymsOf = (table, column) => DIMENSIONS.find((d) => d.table === table && d.column === column)?.synonyms;
  const folders = [...new Set(MEASURES.map((m) => m.folder))];
  return [
    `**Model:** ${MODEL_NAME}. Never bind to ${ASSISTANT_MODEL_NAME}: it has no row-level security and serves only the data agent.`,
    '',
    `**Security:** the role ${code(ALL_TERRITORIES_ROLE)} is for sales managers, and each territory (${list(TERRITORIES)}) has a role for its reps. ` +
      `A territory role keeps ${code(field(modelTableName('accounts'), modelColumn('accounts', 'state').model))} to that state, and the filter reaches ${list(reached.map((t) => code(t.model)))}. ` +
      `${list(unsecured.map((t) => code(t.model)))} aren't filtered by territory.`,
    '',
    '**How filters flow:**',
    '',
    ...filterFlow(),
    '',
    '**Tables:**',
    '',
    ...CRM_TABLES.map((t) => `- ${code(t.model)}: ${t.description}`),
    '',
    '**Measures** (the only source of numbers):',
    '',
    '| Field | Folder | Kind | Meaning | Also called |',
    '|---|---|---|---|---|',
    ...folders.flatMap((folder) =>
      MEASURES.filter((m) => m.folder === folder).map(
        (m) => `| ${code(field(modelTableName(m.table), m.name))} | ${folder} | ${measureKind(m)} | ${cell(m.description)} | ${cell(alsoCalled(m.name, m.synonyms))} |`,
      ),
    ),
    '',
    '**Columns** (categories, axes, slicers and table rows):',
    '',
    '| Field | Kind | Meaning | Also called |',
    '|---|---|---|---|',
    ...CRM_TABLES.flatMap((t) =>
      t.columns
        .filter((c) => c.inModel !== false && !c.hidden)
        .map((c) => `| ${code(field(t.model, c.model))} | ${COLUMN_KINDS[c.type]}${c.category ? ` (${c.category})` : ''} | ${cell(c.description || '')} | ${cell(alsoCalled(c.model, synonymsOf(t.name, c.name)))} |`),
    ),
    ...CRM_TABLES.filter((t) => t.hierarchy).flatMap((t) => [
      '',
      `${code(t.model)} also has the hierarchy ${code(t.hierarchy.name)}: ${t.hierarchy.levels.map((level) => modelColumn(t.name, level).model).join(' > ')}.`,
    ]),
  ].join('\n');
}

const fieldOf = (projected) => {
  const ref = projected.Measure || projected.Column;
  return field(ref.Expression.SourceRef.Entity, ref.Property);
};
const literalText = (value) => value?.expr?.Literal?.Value?.replace(/^'([\s\S]*)'$/, '$1').replace(/''/g, "'");

function visualSpec({ position: { x, y, width, height }, visual }) {
  const title = literalText(visual.visualContainerObjects?.title?.[0]?.properties?.text);
  const sort = visual.query.sortDefinition?.sort?.[0];
  const roles = Object.fromEntries(
    Object.entries(visual.query.queryState).map(([role, { projections }]) => [role, projections.map((p) => ({ field: fieldOf(p.field), ...(p.displayName ? { label: p.displayName } : {}) }))]),
  );
  return { type: visual.visualType, ...(title ? { title } : {}), position: [x, y, width, height], roles, ...(sort ? { sort: { field: fieldOf(sort.field), direction: sort.direction } } : {}) };
}

// "Sales overview" in the prompt's output format, read back from the PBIR the platform deploys.
export function starterReportSpec() {
  const { files } = buildStarterReportDefinition({ semanticModelId: PLACEHOLDER_MODEL_ID });
  return {
    report: STARTER_REPORT_NAME,
    model: MODEL_NAME,
    theme: files['definition/report.json'].themeCollection.baseTheme.name,
    pages: files['definition/pages/pages.json'].pageOrder.map((name) => {
      const page = files[`definition/pages/${name}/page.json`];
      const visuals = Object.entries(files)
        .filter(([path]) => path.startsWith(`definition/pages/${name}/visuals/`))
        .map(([, visual]) => visual)
        .sort((a, b) => a.position.z - b.position.z);
      return { name: page.displayName, width: page.width, height: page.height, visuals: visuals.map(visualSpec) };
    }),
  };
}

// JSON with flat objects and arrays of plain values on one line, so the example reads like a layout.
function compactJson(value, indent = '') {
  const flat = (v) => v === null || typeof v !== 'object';
  const inner = `${indent}  `;
  if (Array.isArray(value)) {
    if (value.every(flat)) return `[${value.map((v) => JSON.stringify(v)).join(', ')}]`;
    return `[\n${value.map((v) => inner + compactJson(v, inner)).join(',\n')}\n${indent}]`;
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value);
    if (entries.every(([, v]) => flat(v))) return `{ ${entries.map(([k, v]) => `${JSON.stringify(k)}: ${JSON.stringify(v)}`).join(', ')} }`;
    return `{\n${entries.map(([k, v]) => `${inner}${JSON.stringify(k)}: ${compactJson(v, inner)}`).join(',\n')}\n${indent}}`;
  }
  return JSON.stringify(value);
}

const SECTIONS = {
  fields: fieldReference,
  example: () => ['```json', compactJson({ ...starterReportSpec(), semanticLayerRequests: [], notes: [] }), '```'].join('\n'),
};

// Rewrites only the prompt's generated sections; the hand-written rules stay as they are.
export function refreshPrompt(text) {
  return Object.entries(SECTIONS).reduce((result, [name, render]) => {
    const start = `<!-- generated:${name} -->`;
    const end = `<!-- /generated:${name} -->`;
    const from = result.indexOf(start);
    const to = from < 0 ? -1 : result.indexOf(end, from);
    if (to < 0) throw new Error(`report-creation-prompt.md has lost its ${start} and ${end} markers.`);
    return `${result.slice(0, from + start.length)}\n${render()}\n${result.slice(to)}`;
  }, text);
}

const QUALIFIED = /'((?:[^']|'')+)'\[([^\]]+)\]/g;
const QUOTED_TABLE = /'((?:[^']|'')+)'/g;

// Naming problems in the measures' DAX: references to tables, columns or measures that don't exist, and broken conventions.
export function daxProblems(measures = MEASURES) {
  const problems = [];
  const tables = new Map(CRM_TABLES.map((t) => [t.model, t]));
  const measureNames = new Set([...MEASURES, ...measures].map((m) => m.name));
  const columnNames = new Set(CRM_TABLES.flatMap((t) => inModel(t).map((c) => c.model.toLowerCase())));
  const seen = new Set();
  for (const m of measures) {
    const say = (problem) => problems.push(`${m.name}: ${problem}`);
    if (!tableByName(m.table)) say(`its table ${m.table} isn't in the schema`);
    if (seen.has(m.name.toLowerCase())) say('another measure has the same name (names ignore case)');
    if (columnNames.has(m.name.toLowerCase())) say('a column has the same name');
    seen.add(m.name.toLowerCase());
    if (m.format === COUNT_FORMAT && !m.name.startsWith('# ')) say('count measures start with "# "');
    if (m.folder === 'Time intelligence' && !/\((ytd|ly)\)$/.test(m.name)) say('time intelligence measures end in "(ytd)" or "(ly)"');
    let rest = m.expression.replace(/"(?:[^"]|"")*"/g, '""');
    for (const [, quoted, name] of rest.matchAll(QUALIFIED)) {
      const table = tables.get(quoted.replace(/''/g, "'"));
      if (!table) say(`'${quoted}' isn't a table in the model`);
      else if (!inModel(table).some((c) => c.model === name)) say(`'${quoted}'[${name}] isn't a column of ${table.model}${measureNames.has(name) ? '; refer to measures without a table' : ''}`);
    }
    rest = rest.replace(QUALIFIED, ' ');
    for (const [, quoted] of rest.matchAll(QUOTED_TABLE)) if (!tables.has(quoted.replace(/''/g, "'"))) say(`'${quoted}' isn't a table in the model`);
    rest = rest.replace(QUOTED_TABLE, ' ');
    if (/\w\[/.test(rest)) say("write table names in quotes: 'Table'[Column]");
    for (const [, name] of rest.matchAll(/\[([^\]]+)\]/g)) if (!measureNames.has(name)) say(`[${name}] isn't a measure; columns need their table: 'Table'[Column]`);
    for (const [, variable] of rest.matchAll(/\bVAR\s+(\w+)/g)) if (!variable.startsWith('_')) say(`variable ${variable} should start with "_"`);
  }
  return problems;
}

const DAX_IN_PROMPT =
  /\b(?:CALCULATE|CALCULATETABLE|SUMX?|AVERAGEX?|COUNTROWS|DISTINCTCOUNT|DIVIDE|FILTER|KEEPFILTERS|USERELATIONSHIP|SUMMARIZECOLUMNS|DATESBETWEEN|SAMEPERIODLASTYEAR|TOTALYTD)\s*\(|\b(?:DEFINE|EVALUATE|MEASURE|VAR|RETURN)\b/;

// Naming problems in the prompt: every `Table[Field]` it names must be a visible column or a measure on that table.
export function promptProblems(text) {
  const problems = [];
  const refs = [...text.matchAll(/`([A-Za-z][^`[\]<>]*)\[([^\]`]+)\]`/g), ...text.matchAll(/"field": "([A-Za-z][^"[\]<>]*)\[([^\]"]+)\]"/g)];
  for (const [, tableName, name] of refs) {
    const table = CRM_TABLES.find((t) => t.model === tableName);
    const column = table && inModel(table).find((c) => c.model === name);
    const measure = MEASURES.find((m) => m.name === name);
    if (!table) problems.push(`${tableName}[${name}]: ${tableName} isn't a table in the model`);
    else if (column?.hidden) problems.push(`${tableName}[${name}] is hidden from report builders`);
    else if (!column && !measure) problems.push(`${tableName}[${name}] isn't a column or measure of ${tableName}`);
    else if (!column && measure.table !== table.name) problems.push(`${tableName}[${name}]: that measure lives on ${modelTableName(measure.table)}`);
  }
  const dax = text.match(DAX_IN_PROMPT);
  if (dax) problems.push(`the prompt contains DAX ("${dax[0]}"); DAX belongs in the semantic layer`);
  return problems;
}
