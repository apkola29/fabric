// One description of HiCRM's tables. It generates the database schema (Fabric SQL and SQLite) and the semantic model,
// so the CRM, the reports and the assistant always agree on names, types and relationships.

export const CRM_SCHEMA_VERSION = 3;

// Sales territories, one per US state. Reps see the accounts in their territories and managers see every account.
// The semantic model gets a security role per territory, so a new territory here reaches the reports on the next
// provisioning run.
export const TERRITORIES = ['Texas', 'New Mexico', 'Georgia'];

// Column types: id | text | money | int | date | datetime | bool.
// Model metadata: `model` is the name shown in reports, `hidden` hides it from report builders, `inModel: false` keeps a
// technical column out of the semantic model, `description` helps people and the assistant, `category` is the
// Power BI data category and `sortBy` names the column that orders this one.
export const CRM_TABLES = [
  {
    name: 'sales_reps',
    model: 'Sales Reps',
    key: 'rep_id',
    description: 'The sales team. Each rep owns accounts, opportunities and activities. One row per rep.',
    columns: [
      { name: 'rep_id', type: 'id', model: 'Rep ID', hidden: true },
      { name: 'name', type: 'text', size: 100, required: true, model: 'Sales Rep', description: 'Full name of the sales rep.' },
      { name: 'email', type: 'text', size: 200, model: 'Rep Email', description: 'Work email address of the sales rep.' },
      { name: 'region', type: 'text', size: 50, model: 'Region', description: 'Sales territory the rep covers: Texas, New Mexico or Georgia.' },
    ],
  },
  {
    name: 'accounts',
    model: 'Accounts',
    key: 'account_id',
    description: 'Customer companies. One row per company.',
    columns: [
      { name: 'account_id', type: 'id', model: 'Account ID', hidden: true },
      { name: 'name', type: 'text', size: 200, required: true, model: 'Account', description: 'Company name of the customer account.' },
      { name: 'industry', type: 'text', size: 50, model: 'Industry', description: 'Industry of the customer, such as Healthcare or Retail.' },
      { name: 'country', type: 'text', size: 50, model: 'Country', category: 'Country', description: 'Country where the customer is headquartered.' },
      { name: 'city', type: 'text', size: 100, model: 'City', category: 'City', description: 'City where the customer is headquartered.' },
      {
        name: 'state',
        type: 'text',
        size: 50,
        model: 'State',
        category: 'StateOrProvince',
        description: 'US state of the customer. Each state is a sales territory: Texas, New Mexico or Georgia.',
      },
      { name: 'annual_revenue', type: 'money', model: 'Annual Revenue', description: "The customer's own yearly revenue in US dollars (company size), not revenue from deals." },
      { name: 'employees', type: 'int', model: 'Employees', description: 'Number of employees at the customer (company size).' },
      { name: 'owner_id', type: 'id', references: 'sales_reps', model: 'Account Owner ID', hidden: true },
      { name: 'created_at', type: 'datetime', model: 'Account Created', description: 'When the account was added to the CRM.' },
      { name: 'updated_at', type: 'datetime', model: 'Account Updated', inModel: false },
    ],
  },
  {
    name: 'contacts',
    model: 'Contacts',
    key: 'contact_id',
    description: 'People who work at customer accounts. One row per person.',
    columns: [
      { name: 'contact_id', type: 'id', model: 'Contact ID', hidden: true },
      { name: 'account_id', type: 'id', references: 'accounts', required: true, model: 'Contact Account ID', hidden: true },
      { name: 'first_name', type: 'text', size: 100, model: 'First Name', description: 'First name of the contact.' },
      { name: 'last_name', type: 'text', size: 100, required: true, model: 'Last Name', description: 'Last name of the contact.' },
      { name: 'email', type: 'text', size: 200, model: 'Contact Email', description: 'Email address of the contact.' },
      { name: 'phone', type: 'text', size: 50, model: 'Phone', description: 'Phone number of the contact.' },
      { name: 'title', type: 'text', size: 100, model: 'Job Title', description: 'Job title of the contact, such as CFO or IT Director.' },
      { name: 'created_at', type: 'datetime', model: 'Contact Created', inModel: false },
      { name: 'updated_at', type: 'datetime', model: 'Contact Updated', inModel: false },
    ],
  },
  {
    name: 'opportunities',
    model: 'Opportunities',
    key: 'opportunity_id',
    description:
      'Deals in the sales pipeline. One row per deal. Stage "Closed Won" means won and "Closed Lost" means lost; every other stage is open pipeline.',
    columns: [
      { name: 'opportunity_id', type: 'id', model: 'Opportunity ID', description: 'Unique ID of the deal. Add it to a table of deals so two deals with the same name stay on separate rows.' },
      { name: 'account_id', type: 'id', references: 'accounts', required: true, model: 'Opportunity Account ID', hidden: true },
      { name: 'name', type: 'text', size: 200, required: true, model: 'Opportunity', description: 'Name of the deal.' },
      {
        name: 'stage',
        type: 'text',
        size: 30,
        required: true,
        model: 'Stage',
        description: 'Sales stage: Prospecting, Qualification, Proposal, Negotiation (open), Closed Won or Closed Lost (closed).',
      },
      { name: 'amount', type: 'money', model: 'Amount', hidden: true },
      { name: 'probability', type: 'int', model: 'Probability', description: 'Chance of winning the deal, in percent from 0 to 100. Set by the stage.' },
      { name: 'close_date', type: 'date', model: 'Close Date', description: 'Date the deal closed, or the expected close date for open deals.' },
      { name: 'owner_id', type: 'id', references: 'sales_reps', model: 'Opportunity Owner ID', hidden: true },
      { name: 'created_at', type: 'datetime', model: 'Opportunity Created', description: 'When the deal was added to the CRM.' },
      { name: 'updated_at', type: 'datetime', model: 'Opportunity Updated', inModel: false },
    ],
  },
  {
    name: 'activities',
    model: 'Activities',
    key: 'activity_id',
    description: 'Calls, emails, meetings and demos with customers. One row per activity; future dates are planned activities.',
    columns: [
      { name: 'activity_id', type: 'id', model: 'Activity ID', hidden: true },
      { name: 'account_id', type: 'id', references: 'accounts', required: true, model: 'Activity Account ID', hidden: true },
      { name: 'opportunity_id', type: 'id', references: 'opportunities', model: 'Activity Opportunity ID', hidden: true },
      { name: 'type', type: 'text', size: 20, required: true, model: 'Activity Type', description: 'Kind of activity: Call, Email, Meeting or Demo.' },
      { name: 'subject', type: 'text', size: 200, model: 'Subject', description: 'Short subject line of the activity.' },
      { name: 'activity_date', type: 'date', model: 'Activity Date', description: 'Date the activity happened or is planned for.' },
      { name: 'duration_minutes', type: 'int', model: 'Duration (Minutes)', hidden: true },
      { name: 'completed', type: 'bool', model: 'Completed', description: 'True when the activity is done, false when it is still planned.' },
      { name: 'owner_id', type: 'id', references: 'sales_reps', model: 'Activity Owner ID', hidden: true },
      { name: 'created_at', type: 'datetime', model: 'Activity Created', inModel: false },
      { name: 'updated_at', type: 'datetime', model: 'Activity Updated', inModel: false },
    ],
  },
  {
    name: 'calendar',
    model: 'Calendar',
    key: 'date',
    dateTable: true,
    description: 'One row per day, covering every date in the CRM through the end of next year. Use it to report by year, quarter, month or week.',
    columns: [
      { name: 'date', type: 'date', model: 'Date', description: 'The calendar day.' },
      { name: 'year', type: 'int', model: 'Year', format: '0', description: 'Calendar year, such as 2026.' },
      { name: 'quarter', type: 'text', size: 2, model: 'Quarter', description: 'Calendar quarter: Q1, Q2, Q3 or Q4.' },
      { name: 'month', type: 'int', model: 'Month Number', format: '0', hidden: true, sortTarget: true },
      { name: 'month_name', type: 'text', size: 10, model: 'Month', sortBy: 'month', description: 'Month name, such as January. Sorted by month number.' },
      { name: 'year_month', type: 'text', size: 7, model: 'Year-Month', description: 'Year and month as YYYY-MM, such as 2026-10.' },
      { name: 'month_start', type: 'date', model: 'Month Start', format: 'mmm yyyy', description: 'The first day of the month. Use it for monthly trends: charts keep the months in time order.' },
      { name: 'week_start', type: 'date', model: 'Week Start', description: 'The Monday that starts the week.' },
    ],
    hierarchy: { name: 'Calendar Hierarchy', levels: ['year', 'quarter', 'month_name', 'date'] },
  },
];

// Relationships for the semantic model, all one-to-many and single direction (filters flow from `to` to `from`).
// Accounts -> Sales Reps is inactive: Sales Reps already filter opportunities and activities directly, so an active
// path through Accounts would be ambiguous. "# Accounts Owned" filters by owner with TREATAS instead of turning it on:
// USERELATIONSHIP fails for viewers whose row-level security roles filter Accounts.
export const CRM_RELATIONSHIPS = [
  { from: ['contacts', 'account_id'], to: ['accounts', 'account_id'] },
  { from: ['opportunities', 'account_id'], to: ['accounts', 'account_id'] },
  { from: ['activities', 'account_id'], to: ['accounts', 'account_id'] },
  { from: ['opportunities', 'owner_id'], to: ['sales_reps', 'rep_id'] },
  { from: ['activities', 'owner_id'], to: ['sales_reps', 'rep_id'] },
  { from: ['opportunities', 'close_date'], to: ['calendar', 'date'] },
  { from: ['activities', 'activity_date'], to: ['calendar', 'date'] },
  { from: ['accounts', 'owner_id'], to: ['sales_reps', 'rep_id'], active: false },
];

export const STAGES = ['Prospecting', 'Qualification', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost'];
export const OPEN_STAGES = STAGES.slice(0, 4);
export const CLOSED_STAGES = STAGES.slice(4);
export const STAGE_PROBABILITY = { Prospecting: 10, Qualification: 25, Proposal: 50, Negotiation: 75, 'Closed Won': 100, 'Closed Lost': 0 };
export const INDUSTRIES = ['Healthcare', 'Manufacturing', 'Retail', 'Financial Services', 'Education', 'Logistics', 'Software', 'Energy'];
export const ACTIVITY_TYPES = ['Call', 'Email', 'Meeting', 'Demo'];

export const tableByName = (name) => CRM_TABLES.find((t) => t.name === name);

const SQL_TYPES = {
  mssql: { id: () => 'NVARCHAR(36)', text: (c) => `NVARCHAR(${c.size || 200})`, money: () => 'DECIMAL(18,2)', int: () => 'INT', date: () => 'DATE', datetime: () => 'DATETIME2(6)', bool: () => 'BIT' },
  sqlite: { id: () => 'TEXT', text: () => 'TEXT', money: () => 'REAL', int: () => 'INTEGER', date: () => 'TEXT', datetime: () => 'TEXT', bool: () => 'INTEGER' },
};

function createTableSql(table, dialect) {
  const lines = table.columns.map((c) => `${c.name} ${SQL_TYPES[dialect][c.type](c)} ${c.name === table.key || c.required ? 'NOT NULL' : 'NULL'}`);
  // Fabric only replicates tables with a primary key to OneLake, and the semantic model reads the replica.
  lines.push(`CONSTRAINT pk_${table.name} PRIMARY KEY (${table.key})`);
  for (const column of table.columns.filter((c) => c.references)) {
    lines.push(`CONSTRAINT fk_${table.name}_${column.name} FOREIGN KEY (${column.name}) REFERENCES ${dialect === 'mssql' ? 'dbo.' : ''}${column.references} (${tableByName(column.references).key})`);
  }
  const body = `(\n  ${lines.join(',\n  ')}\n)`;
  return dialect === 'mssql'
    ? `IF OBJECT_ID(N'dbo.${table.name}', N'U') IS NULL CREATE TABLE dbo.${table.name} ${body};`
    : `CREATE TABLE IF NOT EXISTS ${table.name} ${body};`;
}

export function indexStatement(tableName, columnName, dialect) {
  const name = `ix_${tableName}_${columnName}`;
  return dialect === 'mssql'
    ? `IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'${name}') CREATE INDEX ${name} ON dbo.${tableName} (${columnName});`
    : `CREATE INDEX IF NOT EXISTS ${name} ON ${tableName} (${columnName});`;
}

// Idempotent: safe to run on every provisioning pass. Indexes on columns added by later versions (accounts.state) are
// created by the migration, after the column exists.
export function schemaStatements(dialect) {
  const statements = CRM_TABLES.map((t) => createTableSql(t, dialect));
  for (const table of CRM_TABLES) {
    for (const column of table.columns.filter((c) => c.references || ['stage', 'activity_date', 'close_date'].includes(c.name))) {
      statements.push(indexStatement(table.name, column.name, dialect));
    }
  }
  statements.push(
    dialect === 'mssql'
      ? "IF OBJECT_ID(N'dbo.schema_version', N'U') IS NULL CREATE TABLE dbo.schema_version (version INT NOT NULL CONSTRAINT pk_schema_version PRIMARY KEY, applied_at DATETIME2(6) NOT NULL);"
      : 'CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL PRIMARY KEY, applied_at TEXT NOT NULL);',
  );
  return statements;
}
