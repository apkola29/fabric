import { createHash } from 'node:crypto';
import { textPart } from '../util/definition.js';
import { CLOSED_STAGES, CRM_RELATIONSHIPS, CRM_TABLES, TERRITORIES, tableByName } from './schema.js';

// "Platform app Insights": the semantic model every customer gets. It's generated from the CRM schema, so a new CRM
// column reaches the reports and the assistant without hand-editing TMDL.
//
// Storage mode is Direct Lake on OneLake: Fabric replicates the customer's SQL database to OneLake as Delta tables
// (<workspace>/<sqlDatabaseId>/Tables/dbo/<table>) and the model reads those directly. No copy job, no refresh schedule.

export const MODEL_NAME = 'Platform app Insights';
// The same model without row-level security roles, for the data agent only. Power BI doesn't let service principals
// query models that have roles (they can only embed them with an effective identity), and only people who see every
// territory get the agent. Never embed it for customers.
export const ASSISTANT_MODEL_NAME = 'Platform app Insights - Assistant';
export const DIRECT_LAKE_EXPRESSION = 'DirectLake - Platform app';
export const ONELAKE_DFS = 'https://onelake.dfs.fabric.microsoft.com';

const DATA_TYPES = { id: 'string', text: 'string', money: 'decimal', int: 'int64', date: 'dateTime', datetime: 'dateTime', bool: 'boolean' };
const MONEY = '\\$#,##0';
const COUNT = '#,##0';
const COLUMN_FORMATS = { money: MONEY, int: COUNT, date: 'yyyy-mm-dd', datetime: 'yyyy-mm-dd' };
const CLOSED = `{${CLOSED_STAGES.map((s) => `"${s}"`).join(', ')}}`;

const openOnly = (inner) => `VAR _closedStages = ${CLOSED}\nRETURN\n    CALCULATE(\n        ${inner},\n        KEEPFILTERS(NOT 'Opportunities'[Stage] IN _closedStages)\n    )`;

// Measures live on the table they describe. Synonyms feed the describe-a-chart box and the assistant's quick answers.
export const MEASURES = [
  {
    table: 'opportunities', name: 'Total Amount', folder: 'Pipeline', format: MONEY,
    expression: "SUM('Opportunities'[Amount])",
    description: 'Sum of deal amounts in every stage, open and closed. Use Pipeline Value for open deals and Won Revenue for won deals.',
    synonyms: ['total amount', 'deal amount', 'amount', 'total value', 'value of opportunities', 'value of deals', 'value of all deals'],
  },
  {
    table: 'opportunities', name: 'Pipeline Value', folder: 'Pipeline', format: MONEY,
    expression: openOnly('[Total Amount]'),
    description: 'Total amount of open deals: every stage except Closed Won and Closed Lost.',
    synonyms: ['pipeline value', 'open pipeline', 'pipeline', 'open deal value', 'open value', 'value of open opportunities', 'value of open deals', 'open opportunity value', 'amount of open opportunities', 'amount of open deals'],
  },
  {
    table: 'opportunities', name: 'Weighted Pipeline', folder: 'Pipeline', format: MONEY,
    expression: openOnly("SUMX('Opportunities', 'Opportunities'[Amount] * 'Opportunities'[Probability] / 100)"),
    description: "Open deal amounts multiplied by each deal's win probability: the share of the pipeline you can expect to win.",
    synonyms: ['weighted pipeline', 'weighted', 'forecast', 'expected revenue'],
  },
  {
    table: 'opportunities', name: 'Won Revenue', folder: 'Results', format: MONEY,
    expression: "CALCULATE(\n    [Total Amount],\n    KEEPFILTERS('Opportunities'[Stage] = \"Closed Won\")\n)",
    description: 'Total amount of won deals (stage Closed Won). Use Close Date or the Calendar to see revenue for a period.',
    synonyms: ['won revenue', 'revenue', 'sales', 'bookings', 'won amount', 'closed won', 'value of won deals', 'value of won opportunities'],
  },
  {
    table: 'opportunities', name: 'Lost Amount', folder: 'Results', format: MONEY,
    expression: "CALCULATE(\n    [Total Amount],\n    KEEPFILTERS('Opportunities'[Stage] = \"Closed Lost\")\n)",
    description: 'Total amount of lost deals (stage Closed Lost).',
    synonyms: ['lost amount', 'lost revenue', 'lost value', 'closed lost', 'value of lost deals', 'value of lost opportunities'],
  },
  {
    table: 'opportunities', name: '# Opportunities', folder: 'Counts', format: COUNT,
    expression: "COUNTROWS('Opportunities')",
    description: 'Number of deals in every stage, open and closed.',
    synonyms: ['number of opportunities', 'opportunity count', 'opportunities', 'number of deals', 'deal count', 'deals'],
  },
  {
    table: 'opportunities', name: '# Open Opportunities', folder: 'Counts', format: COUNT,
    expression: openOnly('[# Opportunities]'),
    description: 'Number of open deals: every stage except Closed Won and Closed Lost.',
    synonyms: ['open opportunities', 'open deals', 'number of open deals'],
  },
  {
    table: 'opportunities', name: '# Won Deals', folder: 'Counts', format: COUNT,
    expression: "CALCULATE(\n    [# Opportunities],\n    KEEPFILTERS('Opportunities'[Stage] = \"Closed Won\")\n)",
    description: 'Number of won deals (stage Closed Won).',
    synonyms: ['won deals', 'deals won', 'wins', 'number of wins'],
  },
  {
    table: 'opportunities', name: '# Lost Deals', folder: 'Counts', format: COUNT,
    expression: "CALCULATE(\n    [# Opportunities],\n    KEEPFILTERS('Opportunities'[Stage] = \"Closed Lost\")\n)",
    description: 'Number of lost deals (stage Closed Lost).',
    synonyms: ['lost deals', 'deals lost', 'losses', 'number of losses'],
  },
  {
    table: 'opportunities', name: 'Win Rate', folder: 'Results', format: '0.0%',
    expression: 'VAR _won = [# Won Deals]\nVAR _lost = [# Lost Deals]\nRETURN\n    DIVIDE(_won, _won + _lost)',
    description: 'Share of closed deals that were won: won deals divided by won plus lost deals. Open deals are not counted.',
    synonyms: ['win rate', 'win ratio', 'close rate', 'conversion rate', 'conversion'],
  },
  {
    table: 'opportunities', name: 'Average Deal Size', folder: 'Results', format: MONEY,
    expression: 'DIVIDE([Won Revenue], [# Won Deals])',
    description: 'Average amount of a won deal: Won Revenue divided by the number of won deals.',
    synonyms: ['average deal size', 'average deal', 'avg deal size', 'deal size'],
  },
  {
    table: 'opportunities', name: 'Won Revenue (ytd)', folder: 'Time intelligence', format: MONEY,
    // Year to date stops at today, so a won deal dated in the future, or a calendar that runs into next year, can't
    // inflate it or blank it; future periods are blank.
    expression:
      "VAR _first = MIN('Calendar'[Date])\nVAR _end = MIN(MAX('Calendar'[Date]), TODAY())\nRETURN\n" +
      "    IF(\n        NOT ISBLANK(_first) && _first <= TODAY(),\n        CALCULATE([Won Revenue], DATESBETWEEN('Calendar'[Date], DATE(YEAR(_end), 1, 1), _end))\n    )",
    description: 'Won revenue from January 1 of this year to today, by close date. For a past period, from January 1 of its year to the end of that period; blank for future periods.',
    synonyms: ['won revenue ytd', 'revenue ytd', 'year to date', 'ytd'],
  },
  {
    table: 'opportunities', name: 'Won Revenue (ly)', folder: 'Time intelligence', format: MONEY,
    expression: "CALCULATE(\n    [Won Revenue],\n    SAMEPERIODLASTYEAR('Calendar'[Date])\n)",
    description: 'Won revenue in the same period one year earlier, by close date. Needs a date from the Calendar.',
    synonyms: ['won revenue last year', 'revenue last year', 'last year', 'prior year'],
  },
  {
    table: 'accounts', name: '# Accounts', folder: 'Counts', format: COUNT,
    expression: "COUNTROWS('Accounts')",
    description: 'Number of customer accounts. Sales reps do not filter this measure; use # Accounts Owned per rep.',
    synonyms: ['number of accounts', 'account count', 'accounts', 'customers', 'companies'],
  },
  {
    table: 'accounts', name: '# Accounts Owned', folder: 'Counts', format: COUNT,
    // TREATAS, not USERELATIONSHIP: USERELATIONSHIP returns an error for viewers whose roles filter Accounts.
    // https://learn.microsoft.com/dax/userelationship-function-dax#remarks
    expression:
      "IF(\n    ISCROSSFILTERED('Sales Reps'),\n    CALCULATE(\n        [# Accounts],\n        TREATAS(VALUES('Sales Reps'[Rep ID]), 'Accounts'[Account Owner ID])\n    ),\n    [# Accounts]\n)",
    description: 'Number of accounts each sales rep owns. Use it with Sales Rep or Region.',
    synonyms: ['accounts owned', 'owned accounts', 'book of business', 'accounts per rep'],
  },
  {
    table: 'accounts', name: '# Accounts With Open Deals', folder: 'Counts', format: COUNT,
    expression: openOnly("DISTINCTCOUNT('Opportunities'[Opportunity Account ID])"),
    description: 'Number of accounts that have at least one open deal.',
    synonyms: ['accounts with open deals', 'active accounts', 'accounts with pipeline'],
  },
  {
    table: 'contacts', name: '# Contacts', folder: 'Counts', format: COUNT,
    expression: "COUNTROWS('Contacts')",
    description: 'Number of people at customer accounts.',
    synonyms: ['number of contacts', 'contact count', 'contacts', 'people'],
  },
  {
    table: 'activities', name: '# Activities', folder: 'Counts', format: COUNT,
    expression: "COUNTROWS('Activities')",
    description: 'Number of calls, emails, meetings and demos, completed and planned.',
    synonyms: ['number of activities', 'activity count', 'activities', 'touches', 'interactions'],
  },
  {
    table: 'activities', name: '# Completed Activities', folder: 'Counts', format: COUNT,
    expression: "CALCULATE(\n    [# Activities],\n    KEEPFILTERS('Activities'[Completed] = TRUE())\n)",
    description: 'Number of activities that are done.',
    synonyms: ['completed activities', 'done activities', 'finished activities'],
  },
  {
    table: 'activities', name: '# Planned Activities', folder: 'Counts', format: COUNT,
    expression: "CALCULATE(\n    [# Activities],\n    KEEPFILTERS('Activities'[Completed] = FALSE())\n)",
    description: 'Number of activities that are scheduled but not done yet.',
    synonyms: ['planned activities', 'upcoming activities', 'open activities', 'scheduled activities'],
  },
  {
    table: 'activities', name: 'Activity Hours', folder: 'Effort', format: '#,##0.0',
    expression: "DIVIDE(SUM('Activities'[Duration (Minutes)]), 60)",
    description: 'Total time spent on activities, in hours.',
    synonyms: ['activity hours', 'hours', 'time spent', 'effort'],
  },
  {
    table: 'activities', name: '# Opportunities Touched', folder: 'Counts', format: COUNT,
    expression: "DISTINCTCOUNTNOBLANK('Activities'[Activity Opportunity ID])",
    description: 'Number of different deals that had at least one activity.',
    synonyms: ['opportunities touched', 'deals touched', 'deals with activity'],
  },
  // Report measures (REPORT-SPEC.md). Measures that say "right now" ignore the dates selected, because open deals are
  // dated by their expected close date and a date slicer would otherwise hide pipeline that closes later.
  // No synonyms: describe-a-chart and quick answers work from the measures above.
  {
    table: 'opportunities', name: 'Current Pipeline', folder: 'Pipeline', format: MONEY,
    expression: "CALCULATE(\n    [Pipeline Value],\n    REMOVEFILTERS('Calendar')\n)",
    description: 'Open pipeline right now, whatever dates are selected, including deals expected to close later. Pipeline Value follows the selected dates by expected close date.',
    synonyms: [],
  },
  {
    table: 'opportunities', name: 'Current Weighted Pipeline', folder: 'Pipeline', format: MONEY,
    expression: "CALCULATE(\n    [Weighted Pipeline],\n    REMOVEFILTERS('Calendar')\n)",
    description: 'Weighted pipeline right now, whatever dates are selected.',
    synonyms: [],
  },
  {
    table: 'opportunities', name: '# Current Open Deals', folder: 'Counts', format: COUNT,
    expression: "CALCULATE(\n    [# Open Opportunities],\n    REMOVEFILTERS('Calendar')\n)",
    description: 'Number of open deals right now, whatever dates are selected.',
    synonyms: [],
  },
  {
    table: 'opportunities', name: 'Past-Due Pipeline', folder: 'Pipeline', format: MONEY,
    expression: "CALCULATE(\n    [Pipeline Value],\n    REMOVEFILTERS('Calendar'),\n    KEEPFILTERS('Opportunities'[Close Date] < TODAY())\n)",
    description: 'Open deals whose expected close date has passed: pipeline that needs a new date or a decision.',
    synonyms: [],
  },
  {
    table: 'opportunities', name: '# Past-Due Deals', folder: 'Counts', format: COUNT,
    expression: "CALCULATE(\n    [# Open Opportunities],\n    REMOVEFILTERS('Calendar'),\n    KEEPFILTERS('Opportunities'[Close Date] < TODAY())\n)",
    description: 'Number of open deals whose expected close date has passed.',
    synonyms: [],
  },
  {
    table: 'opportunities', name: '# Deals Created', folder: 'Counts', format: COUNT,
    expression:
      "VAR _dates = VALUES('Calendar'[Date])\nRETURN\n    CALCULATE(\n        [# Opportunities],\n        REMOVEFILTERS('Calendar'),\n" +
      "        FILTER(\n            ALL('Opportunities'[Opportunity Created]),\n" +
      "            DATE(YEAR('Opportunities'[Opportunity Created]), MONTH('Opportunities'[Opportunity Created]), DAY('Opportunities'[Opportunity Created])) IN _dates\n" +
      '        )\n    )',
    description: 'Number of deals created in the selected period, by the day they were created rather than their close date.',
    synonyms: [],
  },
  {
    table: 'opportunities', name: 'Win Rate (value)', folder: 'Results', format: '0.0%',
    expression: 'DIVIDE([Won Revenue], [Won Revenue] + [Lost Amount])',
    description: 'Share of closed deal value that was won: won revenue divided by won plus lost amounts. Win Rate counts deals instead.',
    synonyms: [],
  },
  {
    table: 'opportunities', name: 'Sales Cycle (days)', folder: 'Results', format: '#,##0.0',
    expression:
      "AVERAGEX(\n    FILTER(\n        'Opportunities',\n        'Opportunities'[Stage] = \"Closed Won\"\n" +
      "            && INT('Opportunities'[Opportunity Created]) <= INT('Opportunities'[Close Date])\n    ),\n" +
      "    INT('Opportunities'[Close Date]) - INT('Opportunities'[Opportunity Created])\n)",
    description: 'Average number of days from creating a deal to winning it, for won deals.',
    synonyms: [],
  },
  {
    table: 'opportunities', name: 'Pipeline Velocity (per day)', folder: 'Pipeline', format: MONEY,
    expression: 'DIVIDE([# Current Open Deals] * [Win Rate] * [Average Deal Size], [Sales Cycle (days)])',
    description: 'Expected won revenue per day from the open pipeline: open deals times win rate times average deal size, divided by the sales cycle in days.',
    synonyms: [],
  },
  {
    table: 'opportunities', name: 'Won Revenue Last Year (ytd)', folder: 'Time intelligence', format: MONEY,
    expression:
      "VAR _first = MIN('Calendar'[Date])\nVAR _end = EDATE(MIN(MAX('Calendar'[Date]), TODAY()), -12)\nRETURN\n" +
      "    IF(\n        NOT ISBLANK(_first) && _first <= TODAY(),\n        CALCULATE([Won Revenue], DATESBETWEEN('Calendar'[Date], DATE(YEAR(_end), 1, 1), _end))\n    )",
    description: 'Won Revenue (ytd) for the same span one year earlier: from January 1 to the same day last year.',
    synonyms: [],
  },
  {
    table: 'opportunities', name: 'Won Revenue Growth (ytd)', folder: 'Time intelligence', format: '+0.0%;-0.0%;0.0%',
    expression: 'VAR _lastYear = [Won Revenue Last Year (ytd)]\nRETURN\n    IF(NOT ISBLANK(_lastYear), DIVIDE([Won Revenue (ytd)] - _lastYear, _lastYear))',
    description: 'Growth of Won Revenue (ytd) over Won Revenue Last Year (ytd), the same span one year earlier.',
    synonyms: [],
  },
  {
    table: 'opportunities', name: '# Stale Open Deals (30d)', folder: 'Engagement', format: COUNT,
    expression:
      "VAR _openDeals =\n    CALCULATETABLE(\n        SUMMARIZE('Opportunities', 'Opportunities'[Opportunity ID], 'Opportunities'[Opportunity Created]),\n" +
      "        REMOVEFILTERS('Calendar'),\n" +
      `        KEEPFILTERS(NOT 'Opportunities'[Stage] IN ${CLOSED})\n    )\nRETURN\n    COUNTROWS(\n        FILTER(\n            _openDeals,\n` +
      "            VAR _id = 'Opportunities'[Opportunity ID]\n            VAR _last =\n                CALCULATE(\n" +
      "                    MAX('Activities'[Activity Date]),\n                    REMOVEFILTERS('Calendar'),\n                    REMOVEFILTERS('Sales Reps'),\n" +
      "                    'Activities'[Completed] = TRUE(),\n                    'Activities'[Activity Opportunity ID] = _id\n                )\n" +
      "            VAR _since = IF(ISBLANK(_last), 'Opportunities'[Opportunity Created], _last)\n" +
      '            RETURN\n                NOT ISBLANK(_since) && INT(_since) < INT(TODAY()) - 30\n        )\n    )',
    description:
      'Open deals that have gone more than 30 days without a completed activity, counting from the day they were created if they have had none, whatever dates are selected: the deals whose Days Since Last Touch is over 30.',
    synonyms: [],
  },
  {
    table: 'opportunities', name: 'Days Since Last Touch', folder: 'Engagement', format: '0',
    expression:
      "VAR _last =\n    CALCULATE(\n        MAX('Activities'[Activity Date]),\n        REMOVEFILTERS('Calendar'),\n        REMOVEFILTERS('Sales Reps'),\n" +
      "        'Activities'[Completed] = TRUE(),\n        TREATAS(VALUES('Opportunities'[Opportunity ID]), 'Activities'[Activity Opportunity ID])\n    )\n" +
      "VAR _since = IF(ISBLANK(_last), MAX('Opportunities'[Opportunity Created]), _last)\nRETURN\n" +
      "    IF(\n        HASONEVALUE('Opportunities'[Opportunity ID])\n" +
      `            && NOT SELECTEDVALUE('Opportunities'[Stage]) IN ${CLOSED}\n` +
      "            && NOT ISBLANK(_since),\n        INT(TODAY()) - INT(_since)\n    )",
    description:
      'For one open deal: days since its last completed activity, or since it was created if it has had none. Blank for closed deals. Use it in a table of deals that includes Opportunity ID.',
    synonyms: [],
  },
  {
    table: 'accounts', name: '# Active Accounts (90d)', folder: 'Counts', format: COUNT,
    expression:
      "CALCULATE(\n    DISTINCTCOUNT('Activities'[Activity Account ID]),\n    REMOVEFILTERS('Calendar'),\n" +
      "    KEEPFILTERS('Activities'[Completed] = TRUE()),\n    KEEPFILTERS('Activities'[Activity Date] > TODAY() - 90)\n)",
    description: 'Number of accounts with at least one completed activity in the last 90 days.',
    synonyms: [],
  },
  {
    table: 'accounts', name: '# Won Customers', folder: 'Counts', format: COUNT,
    expression: "CALCULATE(\n    DISTINCTCOUNT('Opportunities'[Opportunity Account ID]),\n    KEEPFILTERS('Opportunities'[Stage] = \"Closed Won\")\n)",
    description: 'Number of accounts with at least one won deal.',
    synonyms: [],
  },
  {
    table: 'accounts', name: 'Won Revenue per Customer', folder: 'Results', format: MONEY,
    expression: 'DIVIDE([Won Revenue], [# Won Customers])',
    description: 'Average won revenue per account that has won deals.',
    synonyms: [],
  },
  {
    table: 'accounts', name: 'Average Employees', folder: 'Company size', format: '#,##0.0',
    expression: "AVERAGE('Accounts'[Employees])",
    description: 'Average number of employees at the accounts.',
    synonyms: [],
  },
  {
    table: 'activities', name: 'Completed Activity Hours', folder: 'Effort', format: '#,##0.0',
    expression: "CALCULATE(\n    [Activity Hours],\n    KEEPFILTERS('Activities'[Completed] = TRUE())\n)",
    description: 'Time spent on completed activities, in hours.',
    synonyms: [],
  },
  {
    table: 'activities', name: 'Touches per Deal', folder: 'Effort', format: '#,##0.0',
    expression:
      "VAR _touches = CALCULATE([# Completed Activities], KEEPFILTERS(NOT ISBLANK('Activities'[Activity Opportunity ID])))\n" +
      "VAR _deals = CALCULATE(DISTINCTCOUNTNOBLANK('Activities'[Activity Opportunity ID]), KEEPFILTERS('Activities'[Completed] = TRUE()))\n" +
      'RETURN\n    DIVIDE(_touches, _deals)',
    description: 'Average number of completed activities per deal, for deals that had any.',
    synonyms: [],
  },
  {
    table: 'activities', name: '# Planned Next 14 Days', folder: 'Counts', format: COUNT,
    expression:
      "CALCULATE(\n    [# Planned Activities],\n    REMOVEFILTERS('Calendar'),\n" +
      "    KEEPFILTERS('Activities'[Activity Date] >= TODAY()),\n    KEEPFILTERS('Activities'[Activity Date] < TODAY() + 14)\n)",
    description: 'Number of planned activities in the next 14 days, whatever dates are selected.',
    synonyms: [],
  },
];

// Columns people slice by. Order matters: earlier entries win when two synonyms match the same words.
export const DIMENSIONS = [
  { table: 'calendar', column: 'month_start', label: 'Month', synonyms: ['over time', 'trend', 'by month', 'monthly', 'month', 'per month'], timeline: true },
  { table: 'calendar', column: 'year_month', synonyms: ['year-month', 'year month'], timeline: true },
  { table: 'calendar', column: 'quarter', synonyms: ['by quarter', 'quarterly', 'quarter'], timeline: true },
  { table: 'calendar', column: 'year', synonyms: ['by year', 'yearly', 'annual', 'year'], timeline: true },
  { table: 'calendar', column: 'week_start', synonyms: ['by week', 'weekly', 'week'], timeline: true },
  { table: 'sales_reps', column: 'name', synonyms: ['sales rep', 'salesperson', 'seller', 'rep', 'owner', 'by owner'] },
  { table: 'sales_reps', column: 'region', synonyms: ['region', 'rep region'] },
  { table: 'accounts', column: 'state', synonyms: ['state', 'territory', 'sales territory'] },
  { table: 'accounts', column: 'industry', synonyms: ['industry', 'vertical', 'sector'] },
  { table: 'accounts', column: 'country', synonyms: ['country', 'countries', 'geography'] },
  { table: 'accounts', column: 'city', synonyms: ['city', 'cities'] },
  { table: 'accounts', column: 'name', synonyms: ['account', 'customer', 'company'] },
  { table: 'opportunities', column: 'stage', synonyms: ['stage', 'sales stage', 'pipeline stage', 'funnel'] },
  { table: 'opportunities', column: 'name', synonyms: ['opportunity', 'deal'] },
  { table: 'activities', column: 'type', synonyms: ['activity type', 'type of activity', 'channel', 'type'] },
  { table: 'contacts', column: 'title', synonyms: ['job title', 'title', 'role'] },
];

export const modelTableName = (tableName) => tableByName(tableName).model;
export const modelColumn = (tableName, columnName) => tableByName(tableName).columns.find((c) => c.name === columnName);
export const daxTable = (name) => `'${name.replace(/'/g, "''")}'`;
export const daxColumn = (tableName, columnName) => `${daxTable(modelTableName(tableName))}[${modelColumn(tableName, columnName).model}]`;

// TMDL names need single quotes unless they're plain identifiers.
export function tmdlName(name) {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(name) ? name : `'${name.replace(/'/g, "''")}'`;
}

const TAB = '\t';
const indent = (level) => TAB.repeat(level);
const description = (text, level) => (text ? `${indent(level)}/// ${text}\n` : '');

function expressionBlock(expression, level) {
  if (!expression.includes('\n')) return ` ${expression}`;
  const body = expression.split('\n').map((line) => `${indent(level + 2)}${line}`);
  return ` \`\`\`\n${body.join('\n')}\n${indent(level + 2)}\`\`\``;
}

function measureTmdl(measure) {
  return (
    description(measure.description, 1) +
    `${indent(1)}measure ${tmdlName(measure.name)} =${expressionBlock(measure.expression, 1)}\n` +
    `${indent(2)}formatString: ${measure.format}\n` +
    `${indent(2)}displayFolder: ${measure.folder}\n`
  );
}

function columnTmdl(table, column) {
  const lines = [`${indent(1)}column ${tmdlName(column.model)}`, `${indent(2)}dataType: ${DATA_TYPES[column.type]}`];
  if (table.dateTable && column.name === table.key) lines.push(`${indent(2)}isKey`);
  if (column.hidden) {
    lines.push(`${indent(2)}isHidden`);
    // Hidden columns don't need an MDX hierarchy unless another column sorts by them.
    if (!column.sortTarget) lines.push(`${indent(2)}isAvailableInMdx: false`);
  }
  const format = column.format || (column.type === 'id' ? null : COLUMN_FORMATS[column.type]);
  if (format) lines.push(`${indent(2)}formatString: ${format}`);
  if (column.category) lines.push(`${indent(2)}dataCategory: ${column.category}`);
  lines.push(`${indent(2)}summarizeBy: none`);
  lines.push(`${indent(2)}sourceColumn: ${column.name}`);
  if (column.sortBy) lines.push(`${indent(2)}sortByColumn: ${tmdlName(modelColumn(table.name, column.sortBy).model)}`);
  return description(column.hidden ? null : column.description, 1) + lines.join('\n') + '\n';
}

function hierarchyTmdl(table) {
  if (!table.hierarchy) return '';
  const levels = table.hierarchy.levels.map((name) => {
    const model = modelColumn(table.name, name).model;
    return `\n${indent(2)}level ${tmdlName(model)}\n${indent(3)}column: ${tmdlName(model)}\n`;
  });
  return `${indent(1)}hierarchy ${tmdlName(table.hierarchy.name)}\n${levels.join('')}`;
}

function tableTmdl(table) {
  const blocks = [];
  const header = description(table.description, 0) + `table ${tmdlName(table.model)}\n` + (table.dateTable ? `${indent(1)}dataCategory: Time\n` : '');
  blocks.push(header);
  for (const measure of MEASURES.filter((m) => m.table === table.name)) blocks.push(measureTmdl(measure));
  for (const column of table.columns.filter((c) => c.inModel !== false)) blocks.push(columnTmdl(table, column));
  const hierarchy = hierarchyTmdl(table);
  if (hierarchy) blocks.push(hierarchy);
  blocks.push(
    `${indent(1)}partition ${tmdlName(table.model)} = entity\n` +
      `${indent(2)}mode: directLake\n` +
      `${indent(2)}source\n` +
      `${indent(3)}entityName: ${table.name}\n` +
      `${indent(3)}schemaName: dbo\n` +
      `${indent(3)}expressionSource: ${tmdlName(DIRECT_LAKE_EXPRESSION)}\n`,
  );
  return blocks.join('\n');
}

function relationshipsTmdl() {
  return CRM_RELATIONSHIPS.map((r) => {
    const [fromTable, fromColumn] = r.from;
    const [toTable, toColumn] = r.to;
    const ref = (t, c) => `${tmdlName(modelTableName(t))}.${tmdlName(modelColumn(t, c).model)}`;
    const name = `${modelTableName(fromTable)} ${modelColumn(fromTable, fromColumn).model} to ${modelTableName(toTable)}`;
    return (
      `relationship ${tmdlName(name)}\n` +
      (r.active === false ? `${indent(1)}isActive: false\n` : '') +
      `${indent(1)}fromColumn: ${ref(fromTable, fromColumn)}\n` +
      `${indent(1)}toColumn: ${ref(toTable, toColumn)}\n`
    );
  }).join('\n');
}

export function oneLakeLocation(workspaceId, sqlDatabaseId) {
  return `${ONELAKE_DFS}/${workspaceId}/${sqlDatabaseId}`;
}

// Row-level security for embedded reports. Each territory has a role that keeps Accounts to that state; the
// relationships carry the filter to the accounts' contacts, deals and activities. Managers get the role without a
// filter. Embed tokens name the viewer's roles, and Power BI shows the union of several roles.
export const ALL_TERRITORIES_ROLE = 'All territories';

export function rolesFor(territories) {
  if (territories === null) return [ALL_TERRITORIES_ROLE];
  return TERRITORIES.filter((t) => territories.includes(t));
}

function roleTmdl(name, filter) {
  return `role ${tmdlName(name)}\n${indent(1)}modelPermission: read\n` + (filter ? `\n${indent(1)}tablePermission ${tmdlName(modelTableName('accounts'))} = ${filter}\n` : '');
}

function roleFiles() {
  const files = { [`definition/roles/${ALL_TERRITORIES_ROLE}.tmdl`]: roleTmdl(ALL_TERRITORIES_ROLE, null) };
  for (const territory of TERRITORIES) files[`definition/roles/${territory}.tmdl`] = roleTmdl(territory, `${daxColumn('accounts', 'state')} = "${territory.replace(/"/g, '""')}"`);
  return files;
}

// Returns the Fabric item definition (TMDL parts) plus a fingerprint, so provisioning can tell when a customer's
// model is behind the current template and push the update. `rowLevelSecurity: false` builds the assistant's twin.
export function buildSemanticModelDefinition({ workspaceId, sqlDatabaseId, rowLevelSecurity = true }) {
  if (!workspaceId || !sqlDatabaseId) throw new Error('The semantic model needs the workspace and SQL database IDs.');
  const files = {
    'definition.pbism': JSON.stringify(
      {
        $schema: 'https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json',
        version: '4.2',
        settings: { qnaEnabled: true },
      },
      null,
      2,
    ),
    'definition/database.tmdl': `database\n${indent(1)}compatibilityLevel: 1702\n${indent(1)}compatibilityMode: powerBI\n`,
    'definition/model.tmdl':
      'model Model\n' +
      `${indent(1)}culture: en-US\n` +
      `${indent(1)}defaultPowerBIDataSourceVersion: powerBI_V3\n` +
      `${indent(1)}discourageImplicitMeasures\n` +
      `${indent(1)}sourceQueryCulture: en-US\n\n` +
      CRM_TABLES.map((t) => `ref table ${tmdlName(t.model)}`).join('\n') +
      '\n',
    'definition/expressions.tmdl':
      "/// The customer's CRM database as replicated to OneLake (Delta tables under Tables/dbo).\n" +
      `expression ${tmdlName(DIRECT_LAKE_EXPRESSION)} =\n` +
      `${indent(2)}let\n` +
      `${indent(2)}    Source = AzureStorage.DataLake("${oneLakeLocation(workspaceId, sqlDatabaseId)}", [HierarchicalNavigation=true])\n` +
      `${indent(2)}in\n` +
      `${indent(2)}    Source\n`,
    'definition/relationships.tmdl': relationshipsTmdl(),
  };
  for (const table of CRM_TABLES) files[`definition/tables/${table.model}.tmdl`] = tableTmdl(table);
  if (rowLevelSecurity) Object.assign(files, roleFiles());
  const fingerprint = createHash('sha256')
    .update(JSON.stringify(Object.entries(files).sort()))
    .digest('hex')
    .slice(0, 16);
  return { definition: { parts: Object.entries(files).map(([path, text]) => textPart(path, text)) }, fingerprint, files };
}

// What the data agent gets to see: visible columns and measures, with their descriptions. IDs are left out: they help
// report tables keep rows apart, but they're noise for questions.
export function agentTables() {
  return CRM_TABLES.map((table) => ({
    name: table.model,
    description: table.description,
    columns: table.columns.filter((c) => c.inModel !== false && !c.hidden && c.type !== 'id').map((c) => ({ name: c.model, description: c.description || '' })),
    measures: MEASURES.filter((m) => m.table === table.name).map((m) => ({ name: m.name, description: m.description })),
  }));
}

// The field list the browser needs to build visuals with the report authoring API.
export function fieldCatalog() {
  return {
    measures: MEASURES.map((m) => ({ table: modelTableName(m.table), name: m.name, folder: m.folder, description: m.description, synonyms: m.synonyms })),
    dimensions: DIMENSIONS.map((d) => {
      const column = modelColumn(d.table, d.column);
      return { table: modelTableName(d.table), column: column.model, description: column.description || '', synonyms: d.synonyms, timeline: Boolean(d.timeline) };
    }),
  };
}
