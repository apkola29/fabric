import { randomUUID } from 'node:crypto';
import { quickAnswer } from './insights.js';
import { ACTIVITY_TYPES, CRM_SCHEMA_VERSION, INDUSTRIES, OPEN_STAGES, STAGE_PROBABILITY, STAGES, TERRITORIES, indexStatement, schemaStatements } from './schema.js';
import { checkScope, scopeSql } from './scope.js';
import { calendarRows, defaultCalendarRange, fabricateCrm } from './seed.js';

// Everything the CRM screens do with the database. The SQL is shared by Fabric SQL and SQLite except for paging.
//
// Territory scope: the screens call `repo.scoped(territories)`. `null` means every account (sales managers); a list
// limits every read and write to accounts in those states, and to the contacts, deals and activities of those
// accounts (sales reps). Records outside the scope answer "not found", as if they didn't exist.

export class CrmValidationError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.name = 'CrmValidationError';
    this.status = status;
  }
}

const OPEN_LIST = OPEN_STAGES.map((s) => `'${s}'`).join(', ');
const nowIso = () => new Date().toISOString();
const newId = (prefix) => `${prefix}-${randomUUID().slice(0, 8)}`;
const search = (term) => (term && String(term).trim() ? `%${String(term).trim().replace(/[%_[\]]/g, '').slice(0, 100)}%` : null);
const bool = (value) => value === true || value === 1 || value === '1';
const num = (value) => (value === null || value === undefined ? null : Number(value));

function text(value, field, { required = false, max = 200 } = {}) {
  const trimmed = value === undefined || value === null ? '' : String(value).trim();
  if (required && !trimmed) throw new CrmValidationError(`${field} is required.`);
  if (trimmed.length > max) throw new CrmValidationError(`${field} can be at most ${max} characters.`);
  return trimmed || null;
}

function oneOf(value, list, field, { required = false } = {}) {
  if (value === undefined || value === null || value === '') {
    if (required) throw new CrmValidationError(`${field} is required.`);
    return null;
  }
  if (!list.includes(value)) throw new CrmValidationError(`${field} must be one of: ${list.join(', ')}.`);
  return value;
}

function amount(value, field) {
  if (value === undefined || value === null || value === '') return null;
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0 || n > 1e12) throw new CrmValidationError(`${field} must be a positive number.`);
  return Math.round(n * 100) / 100;
}

function dateOnly(value, field) {
  if (value === undefined || value === null || value === '') return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value)) || Number.isNaN(Date.parse(`${value}T00:00:00Z`))) throw new CrmValidationError(`${field} must be a date (YYYY-MM-DD).`);
  return String(value);
}

function pageArgs({ limit = 25, offset = 0 } = {}) {
  return { limit: Math.min(Math.max(Number(limit) || 25, 1), 200), offset: Math.max(Number(offset) || 0, 0) };
}

const notFound = (label) => Object.assign(new Error(`${label} not found.`), { status: 404 });

// The territory of a new or edited account. Reps can only use their own territories; managers can also leave it empty.
function territoryFor(value, scope, { creating }) {
  const territory = oneOf(value, TERRITORIES, 'State');
  if (scope === null) return territory;
  if (!territory) {
    if (creating && scope.length === 1) return scope[0];
    throw new CrmValidationError(`Choose the account's state: ${scope.join(' or ')}.`);
  }
  if (!scope.includes(territory)) throw new CrmValidationError(`You can only add or move accounts to your territories (${scope.join(', ')}).`, 403);
  return territory;
}

const mapAccount = (r) => ({
  id: r.account_id,
  name: r.name,
  industry: r.industry,
  country: r.country,
  city: r.city,
  state: r.state ?? null,
  annualRevenue: num(r.annual_revenue),
  employees: num(r.employees),
  ownerId: r.owner_id,
  ownerName: r.owner_name ?? null,
  openOpportunities: num(r.open_opportunities) ?? undefined,
  pipelineValue: num(r.pipeline_value) ?? undefined,
  updatedAt: r.updated_at,
});
const mapOpportunity = (r) => ({
  id: r.opportunity_id,
  accountId: r.account_id,
  accountName: r.account_name ?? null,
  name: r.name,
  stage: r.stage,
  amount: num(r.amount),
  probability: num(r.probability),
  closeDate: r.close_date,
  ownerId: r.owner_id,
  ownerName: r.owner_name ?? null,
  updatedAt: r.updated_at,
});
const mapActivity = (r) => ({
  id: r.activity_id,
  accountId: r.account_id,
  accountName: r.account_name ?? null,
  opportunityId: r.opportunity_id,
  opportunityName: r.opportunity_name ?? null,
  type: r.type,
  subject: r.subject,
  date: r.activity_date,
  durationMinutes: num(r.duration_minutes),
  completed: bool(r.completed),
  ownerId: r.owner_id,
  ownerName: r.owner_name ?? null,
});
const mapContact = (r) => ({
  id: r.contact_id,
  accountId: r.account_id,
  accountName: r.account_name ?? null,
  firstName: r.first_name,
  lastName: r.last_name,
  email: r.email,
  phone: r.phone,
  title: r.title,
});

export function createCrmRepository(store) {
  const page = (sqlText) => (store.dialect === 'mssql' ? `${sqlText} OFFSET @offset ROWS FETCH NEXT @limit ROWS ONLY` : `${sqlText} LIMIT @limit OFFSET @offset`);
  const one = async (sqlText, params) => (await store.query(sqlText, params))[0] || null;
  const count = async (sqlText, params) => Number((await one(sqlText, params))?.n || 0);
  const direction = (value) => (value === 'desc' ? 'DESC' : 'ASC');

  async function repExists(ownerId) {
    if (ownerId && !(await one('SELECT rep_id FROM sales_reps WHERE rep_id = @id', { id: ownerId }))) throw new CrmValidationError('Owner is not a known sales rep.');
    return ownerId || null;
  }

  // Updates only the fields that were sent, and always stamps updated_at.
  async function updateRow(table, key, id, fields) {
    const changes = Object.entries(fields).filter(([, value]) => value !== undefined);
    const assignments = [...changes.map(([column]) => `${column} = @${column}`), 'updated_at = @updated_at'];
    await store.execute(`UPDATE ${table} SET ${assignments.join(', ')} WHERE ${key} = @id`, { ...Object.fromEntries(changes), updated_at: nowIso(), id });
  }

  async function addColumn(table, column, { mssql, sqlite }) {
    const exists =
      store.dialect === 'mssql'
        ? Boolean((await one(`SELECT COL_LENGTH('dbo.${table}', '${column}') AS n`))?.n)
        : (await store.query(`SELECT name FROM pragma_table_info('${table}') WHERE name = '${column}'`)).length > 0;
    if (!exists) await store.exec(store.dialect === 'mssql' ? `ALTER TABLE dbo.${table} ADD ${column} ${mssql} NULL;` : `ALTER TABLE ${table} ADD COLUMN ${column} ${sqlite};`);
  }

  // Adds the days the calendar is missing at either end, so every date in the CRM has its calendar row.
  async function ensureCalendar({ from, to } = defaultCalendarRange()) {
    const bounds = await one('SELECT COUNT(*) AS n, MIN(date) AS first, MAX(date) AS last FROM calendar');
    if (!Number(bounds?.n)) return store.bulkInsert('calendar', calendarRows(from, to));
    const first = String(bounds.first).slice(0, 10);
    const last = String(bounds.last).slice(0, 10);
    const shift = (date, days) => new Date(Date.parse(`${date}T00:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10);
    let added = 0;
    if (from < first) added += await store.bulkInsert('calendar', calendarRows(from, shift(first, -1)));
    if (to > last) added += await store.bulkInsert('calendar', calendarRows(shift(last, 1), to));
    return added;
  }

  async function seed(seedText, options) {
    const data = fabricateCrm(seedText, options);
    const loaded = {};
    const hasAccounts = await count('SELECT COUNT(*) AS n FROM accounts');
    // The calendar covers the sample data; a CRM that already has records keeps the calendar it has.
    const added = await ensureCalendar(hasAccounts ? undefined : { from: data.calendar[0].date, to: data.calendar.at(-1).date });
    if (added) loaded.calendar = added;
    if (hasAccounts) return loaded;
    for (const table of ['sales_reps', 'accounts', 'contacts', 'opportunities', 'activities']) {
      if (table === 'sales_reps' && (await count('SELECT COUNT(*) AS n FROM sales_reps'))) continue;
      loaded[table] = await store.bulkInsert(table, data[table]);
    }
    return loaded;
  }

  // The customer-facing CRM, limited to a territory scope (see the top of this file).
  function scoped(scope) {
    const territories = checkScope(scope);
    const inScope = (params, column) => scopeSql(territories, params, column);

    async function visible(kind, id, label) {
      const params = { id };
      const from = {
        account: 'SELECT a.account_id AS id FROM accounts a WHERE a.account_id = @id',
        opportunity: 'SELECT o.opportunity_id AS id FROM opportunities o JOIN accounts a ON a.account_id = o.account_id WHERE o.opportunity_id = @id',
        activity: 'SELECT t.activity_id AS id FROM activities t JOIN accounts a ON a.account_id = t.account_id WHERE t.activity_id = @id',
      }[kind];
      if (!(await one(`${from} AND ${inScope(params)}`, params))) throw notFound(label);
    }

    async function getAccount(id) {
      const params = { id };
      const account = await one(
        `SELECT a.account_id, a.name, a.industry, a.country, a.city, a.state, a.annual_revenue, a.employees, a.owner_id, a.updated_at, r.name AS owner_name
         FROM accounts a LEFT JOIN sales_reps r ON r.rep_id = a.owner_id WHERE a.account_id = @id AND ${inScope(params)}`,
        params,
      );
      if (!account) return null;
      const contacts = await store.query('SELECT * FROM contacts WHERE account_id = @id ORDER BY last_name, first_name', { id });
      const opportunities = await store.query(
        'SELECT o.*, r.name AS owner_name FROM opportunities o LEFT JOIN sales_reps r ON r.rep_id = o.owner_id WHERE o.account_id = @id ORDER BY o.close_date DESC',
        { id },
      );
      const activities = await store.query(
        page(`SELECT t.*, r.name AS owner_name, o.name AS opportunity_name FROM activities t
              LEFT JOIN sales_reps r ON r.rep_id = t.owner_id LEFT JOIN opportunities o ON o.opportunity_id = t.opportunity_id
              WHERE t.account_id = @id ORDER BY t.activity_date DESC, t.activity_id`),
        { id, limit: 50, offset: 0 },
      );
      return { ...mapAccount(account), contacts: contacts.map(mapContact), opportunities: opportunities.map(mapOpportunity), activities: activities.map(mapActivity) };
    }

    async function getOpportunity(id) {
      const params = { id };
      const row = await one(
        `SELECT o.*, a.name AS account_name, r.name AS owner_name FROM opportunities o JOIN accounts a ON a.account_id = o.account_id
         LEFT JOIN sales_reps r ON r.rep_id = o.owner_id WHERE o.opportunity_id = @id AND ${inScope(params)}`,
        params,
      );
      return row ? mapOpportunity(row) : null;
    }

    async function getActivity(id) {
      const [row] = await store.query(
        `SELECT t.*, a.name AS account_name, r.name AS owner_name FROM activities t JOIN accounts a ON a.account_id = t.account_id
         LEFT JOIN sales_reps r ON r.rep_id = t.owner_id WHERE t.activity_id = @id`,
        { id },
      );
      return mapActivity(row);
    }

    return {
      territories,

      async options() {
        const params = {};
        const reps = await store.query(`SELECT rep_id, name, region FROM sales_reps r WHERE ${inScope(params, 'r.region')} ORDER BY name`, params);
        return {
          stages: STAGES,
          openStages: OPEN_STAGES,
          industries: INDUSTRIES,
          activityTypes: ACTIVITY_TYPES,
          territories: territories || TERRITORIES,
          reps: reps.map((r) => ({ id: r.rep_id, name: r.name, region: r.region })),
        };
      },

      async summary() {
        const year = String(new Date().getUTCFullYear());
        const params = { from: `${year}-01-01` };
        const deals = `FROM opportunities o JOIN accounts a ON a.account_id = o.account_id WHERE ${inScope(params)}`;
        const pipeline = await one(`SELECT COUNT(*) AS n, COALESCE(SUM(o.amount), 0) AS value ${deals} AND o.stage IN (${OPEN_LIST})`, params);
        const won = await one(`SELECT COUNT(*) AS n, COALESCE(SUM(o.amount), 0) AS value ${deals} AND o.stage = 'Closed Won' AND o.close_date >= @from`, params);
        const lost = await count(`SELECT COUNT(*) AS n ${deals} AND o.stage = 'Closed Lost' AND o.close_date >= @from`, params);
        const accounts = await count(`SELECT COUNT(*) AS n FROM accounts a WHERE ${inScope(params)}`, params);
        const wonCount = Number(won.n);
        return {
          accounts,
          openOpportunities: Number(pipeline.n),
          pipelineValue: num(pipeline.value),
          wonThisYear: num(won.value),
          winRateThisYear: wonCount + lost ? Math.round((wonCount / (wonCount + lost)) * 1000) / 10 : null,
        };
      },

      async lookupAccounts(term) {
        const params = { search: search(term), limit: 20, offset: 0 };
        const rows = await store.query(page(`SELECT a.account_id, a.name FROM accounts a WHERE ${inScope(params)} AND (@search IS NULL OR a.name LIKE @search) ORDER BY a.name, a.account_id`), params);
        return rows.map((r) => ({ id: r.account_id, name: r.name }));
      },

      async listAccounts(filters = {}) {
        const sorts = { name: 'a.name', industry: 'a.industry', state: 'a.state', country: 'a.country', revenue: 'a.annual_revenue', pipeline: 'pipeline_value', owner: 'owner_name' };
        const params = { search: search(filters.search), industry: filters.industry || null, owner: filters.ownerId || null, state: filters.state || null, ...pageArgs(filters) };
        const where = `WHERE ${inScope(params)} AND (@search IS NULL OR a.name LIKE @search OR a.city LIKE @search OR a.state LIKE @search OR a.country LIKE @search)
          AND (@industry IS NULL OR a.industry = @industry) AND (@owner IS NULL OR a.owner_id = @owner) AND (@state IS NULL OR a.state = @state)`;
        const rows = await store.query(
          page(`SELECT a.account_id, a.name, a.industry, a.country, a.city, a.state, a.annual_revenue, a.employees, a.owner_id, a.updated_at, r.name AS owner_name,
                  COALESCE(p.open_count, 0) AS open_opportunities, COALESCE(p.pipeline, 0) AS pipeline_value
                FROM accounts a
                LEFT JOIN sales_reps r ON r.rep_id = a.owner_id
                LEFT JOIN (SELECT account_id, COUNT(*) AS open_count, SUM(amount) AS pipeline FROM opportunities WHERE stage IN (${OPEN_LIST}) GROUP BY account_id) p ON p.account_id = a.account_id
                ${where}
                ORDER BY ${sorts[filters.sort] || 'a.name'} ${direction(filters.direction)}, a.account_id`),
          params,
        );
        return { rows: rows.map(mapAccount), total: await count(`SELECT COUNT(*) AS n FROM accounts a ${where}`, params) };
      },

      getAccount,

      async createAccount(input) {
        const id = newId('acc');
        const at = nowIso();
        const state = territoryFor(input.state, territories, { creating: true });
        await store.execute(
          `INSERT INTO accounts (account_id, name, industry, country, city, state, annual_revenue, employees, owner_id, created_at, updated_at)
           VALUES (@id, @name, @industry, @country, @city, @state, @revenue, @employees, @owner, @at, @at)`,
          {
            id,
            name: text(input.name, 'Account name', { required: true }),
            industry: oneOf(input.industry, INDUSTRIES, 'Industry'),
            country: text(input.country, 'Country', { max: 50 }) || (state ? 'United States' : null),
            city: text(input.city, 'City', { max: 100 }),
            state,
            revenue: amount(input.annualRevenue, 'Annual revenue'),
            employees: input.employees === undefined || input.employees === '' ? null : Math.max(0, Math.round(Number(input.employees)) || 0),
            owner: await repExists(input.ownerId),
            at,
          },
        );
        return getAccount(id);
      },

      async updateAccount(id, input) {
        await visible('account', id, 'Account');
        await updateRow('accounts', 'account_id', id, {
          name: input.name !== undefined ? text(input.name, 'Account name', { required: true }) : undefined,
          industry: input.industry !== undefined ? oneOf(input.industry, INDUSTRIES, 'Industry') : undefined,
          country: input.country !== undefined ? text(input.country, 'Country', { max: 50 }) : undefined,
          city: input.city !== undefined ? text(input.city, 'City', { max: 100 }) : undefined,
          state: input.state !== undefined ? territoryFor(input.state, territories, { creating: false }) : undefined,
          annual_revenue: input.annualRevenue !== undefined ? amount(input.annualRevenue, 'Annual revenue') : undefined,
          owner_id: input.ownerId !== undefined ? await repExists(input.ownerId) : undefined,
        });
        return getAccount(id);
      },

      async listOpportunities(filters = {}) {
        const sorts = { close: 'o.close_date', amount: 'o.amount', name: 'o.name', stage: 'o.stage', account: 'a.name', owner: 'r.name' };
        const statusSql = { open: `o.stage IN (${OPEN_LIST})`, won: "o.stage = 'Closed Won'", lost: "o.stage = 'Closed Lost'" }[filters.status] || '1 = 1';
        const closeFrom = /^\d{4}-\d{2}-\d{2}$/.test(String(filters.closeFrom || '')) ? filters.closeFrom : null;
        const params = { search: search(filters.search), stage: filters.stage || null, owner: filters.ownerId || null, closeFrom, ...pageArgs(filters) };
        const where = `WHERE ${statusSql} AND ${inScope(params)} AND (@search IS NULL OR o.name LIKE @search OR a.name LIKE @search) AND (@stage IS NULL OR o.stage = @stage)
          AND (@owner IS NULL OR o.owner_id = @owner) AND (@closeFrom IS NULL OR o.close_date >= @closeFrom)`;
        const from = 'FROM opportunities o JOIN accounts a ON a.account_id = o.account_id LEFT JOIN sales_reps r ON r.rep_id = o.owner_id';
        const rows = await store.query(
          page(`SELECT o.*, a.name AS account_name, r.name AS owner_name ${from} ${where} ORDER BY ${sorts[filters.sort] || 'o.close_date'} ${direction(filters.direction)}, o.opportunity_id`),
          params,
        );
        return { rows: rows.map(mapOpportunity), total: await count(`SELECT COUNT(*) AS n ${from} ${where}`, params) };
      },

      getOpportunity,

      async createOpportunity(input) {
        const accountId = text(input.accountId, 'Account', { required: true, max: 36 });
        await visible('account', accountId, 'Account');
        const stage = oneOf(input.stage || 'Prospecting', STAGES, 'Stage', { required: true });
        const id = newId('opp');
        const at = nowIso();
        await store.execute(
          `INSERT INTO opportunities (opportunity_id, account_id, name, stage, amount, probability, close_date, owner_id, created_at, updated_at)
           VALUES (@id, @account, @name, @stage, @amount, @probability, @close, @owner, @at, @at)`,
          {
            id,
            account: accountId,
            name: text(input.name, 'Opportunity name', { required: true }),
            stage,
            amount: amount(input.amount, 'Amount'),
            probability: input.probability !== undefined && input.probability !== '' ? Math.min(100, Math.max(0, Math.round(Number(input.probability)))) : STAGE_PROBABILITY[stage],
            close: dateOnly(input.closeDate, 'Close date'),
            owner: await repExists(input.ownerId),
            at,
          },
        );
        return getOpportunity(id);
      },

      async updateOpportunity(id, input) {
        await visible('opportunity', id, 'Opportunity');
        const stage = input.stage !== undefined ? oneOf(input.stage, STAGES, 'Stage', { required: true }) : undefined;
        let probability;
        if (input.probability !== undefined && input.probability !== '') probability = Math.min(100, Math.max(0, Math.round(Number(input.probability))));
        else if (stage) probability = STAGE_PROBABILITY[stage];
        await updateRow('opportunities', 'opportunity_id', id, {
          name: input.name !== undefined ? text(input.name, 'Opportunity name', { required: true }) : undefined,
          stage,
          probability,
          amount: input.amount !== undefined ? amount(input.amount, 'Amount') : undefined,
          close_date: input.closeDate !== undefined ? dateOnly(input.closeDate, 'Close date') : undefined,
          owner_id: input.ownerId !== undefined ? await repExists(input.ownerId) : undefined,
        });
        return getOpportunity(id);
      },

      async listActivities(filters = {}) {
        const statusSql = { open: 't.completed = 0', done: 't.completed = 1' }[filters.status] || '1 = 1';
        const params = { search: search(filters.search), type: filters.type || null, owner: filters.ownerId || null, ...pageArgs(filters) };
        const where = `WHERE ${statusSql} AND ${inScope(params)} AND (@search IS NULL OR t.subject LIKE @search OR a.name LIKE @search) AND (@type IS NULL OR t.type = @type)
          AND (@owner IS NULL OR t.owner_id = @owner)`;
        const from = `FROM activities t JOIN accounts a ON a.account_id = t.account_id LEFT JOIN opportunities o ON o.opportunity_id = t.opportunity_id
                      LEFT JOIN sales_reps r ON r.rep_id = t.owner_id`;
        const rows = await store.query(
          page(`SELECT t.*, a.name AS account_name, o.name AS opportunity_name, r.name AS owner_name ${from} ${where} ORDER BY t.activity_date ${direction(filters.direction || 'desc')}, t.activity_id`),
          params,
        );
        return { rows: rows.map(mapActivity), total: await count(`SELECT COUNT(*) AS n ${from} ${where}`, params) };
      },

      async createActivity(input) {
        const accountId = text(input.accountId, 'Account', { required: true, max: 36 });
        await visible('account', accountId, 'Account');
        const opportunityId = text(input.opportunityId, 'Opportunity', { max: 36 });
        if (opportunityId) {
          const opportunity = await one('SELECT account_id FROM opportunities WHERE opportunity_id = @id', { id: opportunityId });
          if (!opportunity || opportunity.account_id !== accountId) throw new CrmValidationError('The opportunity must belong to the same account.');
        }
        const id = newId('act');
        const at = nowIso();
        const date = dateOnly(input.date, 'Date') || at.slice(0, 10);
        await store.execute(
          `INSERT INTO activities (activity_id, account_id, opportunity_id, type, subject, activity_date, duration_minutes, completed, owner_id, created_at, updated_at)
           VALUES (@id, @account, @opportunity, @type, @subject, @date, @duration, @completed, @owner, @at, @at)`,
          {
            id,
            account: accountId,
            opportunity: opportunityId,
            type: oneOf(input.type, ACTIVITY_TYPES, 'Type', { required: true }),
            subject: text(input.subject, 'Subject', { required: true }),
            date,
            duration: input.durationMinutes === undefined || input.durationMinutes === '' ? null : Math.max(0, Math.round(Number(input.durationMinutes)) || 0),
            completed: input.completed === undefined ? date <= at.slice(0, 10) : bool(input.completed),
            owner: await repExists(input.ownerId),
            at,
          },
        );
        return getActivity(id);
      },

      async updateActivity(id, input) {
        await visible('activity', id, 'Activity');
        await updateRow('activities', 'activity_id', id, {
          completed: input.completed !== undefined ? bool(input.completed) : undefined,
          subject: input.subject !== undefined ? text(input.subject, 'Subject', { required: true }) : undefined,
          activity_date: input.date !== undefined ? dateOnly(input.date, 'Date') : undefined,
        });
        return getActivity(id);
      },

      async listContacts(filters = {}) {
        const params = { search: search(filters.search), account: filters.accountId || null, ...pageArgs(filters) };
        const where = `WHERE ${inScope(params)} AND (@search IS NULL OR c.first_name LIKE @search OR c.last_name LIKE @search OR c.email LIKE @search OR a.name LIKE @search)
          AND (@account IS NULL OR c.account_id = @account)`;
        const from = 'FROM contacts c JOIN accounts a ON a.account_id = c.account_id';
        const rows = await store.query(page(`SELECT c.*, a.name AS account_name ${from} ${where} ORDER BY c.last_name, c.first_name, c.contact_id`), params);
        return { rows: rows.map(mapContact), total: await count(`SELECT COUNT(*) AS n ${from} ${where}`, params) };
      },

      async createContact(input) {
        const accountId = text(input.accountId, 'Account', { required: true, max: 36 });
        await visible('account', accountId, 'Account');
        const email = text(input.email, 'Email');
        if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) throw new CrmValidationError('Email is not valid.');
        const id = newId('con');
        const at = nowIso();
        await store.execute(
          `INSERT INTO contacts (contact_id, account_id, first_name, last_name, email, phone, title, created_at, updated_at)
           VALUES (@id, @account, @first, @last, @email, @phone, @title, @at, @at)`,
          {
            id,
            account: accountId,
            first: text(input.firstName, 'First name', { max: 100 }),
            last: text(input.lastName, 'Last name', { required: true, max: 100 }),
            email,
            phone: text(input.phone, 'Phone', { max: 50 }),
            title: text(input.title, 'Job title', { max: 100 }),
            at,
          },
        );
        const [row] = await store.query('SELECT c.*, a.name AS account_name FROM contacts c JOIN accounts a ON a.account_id = c.account_id WHERE c.contact_id = @id', { id });
        return mapContact(row);
      },

      // Read-only answers computed from the CRM tables (the assistant's fallback when the data agent isn't available,
      // and the only assistant for people limited to some territories).
      async quickAnswer(question, options = {}) {
        return quickAnswer({ dialect: store.dialect, run: (sqlText, params) => store.query(sqlText, params) }, question, { ...options, scope: territories });
      },
    };
  }

  return {
    dialect: store.dialect,
    scoped,

    async migrate() {
      for (const statement of schemaStatements(store.dialect)) await store.exec(statement);
      // v2: a date-typed month column, so monthly trends plot in time order.
      await addColumn('calendar', 'month_start', { mssql: 'DATE', sqlite: 'TEXT' });
      await store.execute(
        store.dialect === 'mssql'
          ? 'UPDATE dbo.calendar SET month_start = DATEFROMPARTS(year, month, 1) WHERE month_start IS NULL'
          : "UPDATE calendar SET month_start = substr(date, 1, 8) || '01' WHERE month_start IS NULL",
      );
      // v3: the account's state, which is its sales territory. Accounts from earlier versions stay unassigned (managers
      // see them, reps don't) until someone sets their state.
      await addColumn('accounts', 'state', { mssql: 'NVARCHAR(50)', sqlite: 'TEXT' });
      await store.exec(indexStatement('accounts', 'state', store.dialect));
      if (!(await count('SELECT COUNT(*) AS n FROM schema_version WHERE version = @version', { version: CRM_SCHEMA_VERSION }))) {
        await store.execute('INSERT INTO schema_version (version, applied_at) VALUES (@version, @at)', { version: CRM_SCHEMA_VERSION, at: nowIso() });
      }
      return CRM_SCHEMA_VERSION;
    },

    async counts() {
      const out = {};
      for (const table of ['sales_reps', 'accounts', 'contacts', 'opportunities', 'activities', 'calendar']) out[table] = await count(`SELECT COUNT(*) AS n FROM ${table}`);
      return out;
    },

    // Reference data the reports need even when a customer starts with an empty CRM.
    ensureCalendar,

    // Loads fabricated data into empty tables only, so it never overwrites real records.
    seed,

    // Deletes every CRM record (not the calendar) and loads the sample data again. Only for demo customers: the
    // command line asks for confirmation.
    async replaceWithSampleData(seedText, options) {
      const tables = ['activities', 'opportunities', 'contacts', 'accounts', 'sales_reps'];
      const prefix = store.dialect === 'mssql' ? 'dbo.' : '';
      await store.exec(`BEGIN TRANSACTION; ${tables.map((t) => `DELETE FROM ${prefix}${t};`).join(' ')} COMMIT;`);
      return seed(seedText, options);
    },

    async close() {
      await store.close?.();
    },
  };
}
