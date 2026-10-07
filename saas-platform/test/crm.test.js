import assert from 'node:assert/strict';
import { test } from 'node:test';
import { QUICK_ANSWER_MEASURES, describeVisual, parseRequest } from '../src/crm/insights.js';
import { ALL_TERRITORIES_ROLE, MEASURES, agentTables, buildSemanticModelDefinition, fieldCatalog, rolesFor } from '../src/crm/model.js';
import { createCrmRepository } from '../src/crm/repository.js';
import { CRM_RELATIONSHIPS, CRM_SCHEMA_VERSION, CRM_TABLES, TERRITORIES, schemaStatements } from '../src/crm/schema.js';
import { fabricateCrm } from '../src/crm/seed.js';
import { SQL_RETRY_DELAYS_MS, createFabricSqlStore, createSqliteStore, sqlRetryable } from '../src/crm/stores.js';
import { buildSemanticModelAgentDefinition } from '../src/platform/agent.js';
import { decodePayload } from '../src/util/definition.js';

const TODAY = new Date('2026-10-01T12:00:00Z');

async function seededRepo() {
  const repo = createCrmRepository(createSqliteStore());
  await repo.migrate();
  await repo.seed('fabrikam', { companyDomain: 'fabrikam.com', today: '2026-10-01' });
  return repo;
}

// A stand-in for the mssql driver: connecting and each request follow a script of outcomes, the last one repeating.
function scriptedMssql({ connects = [], requests = [] } = {}) {
  const calls = { connect: 0, request: 0 };
  const next = async (script, i) => {
    const outcome = script[Math.min(i, script.length - 1)];
    if (outcome instanceof Error) throw outcome;
  };
  class ConnectionPool {
    async connect() {
      await next(connects, calls.connect++);
      return this;
    }
    request() {
      const respond = async () => {
        await next(requests, calls.request++);
        return { recordset: [{ n: 1 }], rowsAffected: [1] };
      };
      return { input() {}, query: respond, batch: respond };
    }
  }
  return { calls, sql: { ConnectionPool } };
}

const sqlError = (name, code, message, number) => Object.assign(new Error(message), { name, code, ...(number ? { number } : {}) });

test('SQL database in Fabric pauses when idle: connecting is retried until it resumes, reads retry transient errors, writes never run twice', async () => {
  const resuming = sqlError('ConnectionError', 'ELOGIN', "Database 'hicrm_db' on server 'x' is not currently available. Please retry the connection later.");
  const timedOut = sqlError('ConnectionError', 'ETIMEOUT', 'Failed to connect to x:1433 in 30000ms');
  const refused = sqlError('ConnectionError', 'ELOGIN', "Login failed for user '<token-identified principal>'.");
  const busy = sqlError('RequestError', 'EREQUEST', 'The service is currently busy.', 40501);
  const lost = sqlError('RequestError', 'ECONNRESET', 'Connection lost - read ECONNRESET');
  assert.deepEqual(
    [resuming, timedOut, refused, busy, lost, sqlError('RequestError', 'EREQUEST', "Invalid column name 'x'.", 207), sqlError('RequestError', 'ETIMEOUT', 'Timeout: Request failed to complete in 120000ms')].map(sqlRetryable),
    ['any', 'any', null, 'reads', 'reads', null, null],
  );
  assert.ok(SQL_RETRY_DELAYS_MS.reduce((sum, ms) => sum + ms) >= 60_000, 'retries cover the minute a database can take to resume');

  const open = (driver, onRetry = null) =>
    createFabricSqlStore({ server: 'x.database.fabric.microsoft.com,1433', database: 'hicrm_db', tokens: { getToken: async () => 't' }, sqlModule: driver.sql, retryDelaysMs: [0, 0, 0, 0, 0], onRetry });

  const retries = [];
  let driver = scriptedMssql({ connects: [timedOut, resuming, 'ok'] });
  assert.deepEqual(await (await open(driver, (retry) => retries.push(retry))).query('SELECT 1 AS n'), [{ n: 1 }]);
  assert.equal(driver.calls.connect, 3, 'the database resumed on the third attempt');
  assert.deepEqual(retries.map((r) => [r.attempt, r.error.code]), [[1, 'ETIMEOUT'], [2, 'ELOGIN']], 'each retry is reported, for the server log');

  driver = scriptedMssql({ connects: [resuming, 'ok'] });
  assert.deepEqual(await (await open(driver)).execute('UPDATE accounts SET name = name'), { rowsAffected: 1 }, 'a write that never reached the database is retried');

  driver = scriptedMssql({ connects: [refused] });
  await assert.rejects((await open(driver)).query('SELECT 1 AS n'), /Login failed/);
  assert.equal(driver.calls.connect, 1, 'a refused sign-in is not retried');

  driver = scriptedMssql({ requests: [busy, 'ok'] });
  assert.deepEqual(await (await open(driver)).query('SELECT 1 AS n'), [{ n: 1 }]);
  assert.equal(driver.calls.request, 2, 'a read runs again after a transient error');

  driver = scriptedMssql({ requests: [lost, 'ok'] });
  await assert.rejects((await open(driver)).execute('DELETE FROM activities'), /Connection lost/);
  assert.equal(driver.calls.request, 1, 'a write that may have been applied is not run again');

  driver = scriptedMssql({ connects: [timedOut] });
  await assert.rejects((await open(driver)).query('SELECT 1 AS n'), /Failed to connect/);
  assert.equal(driver.calls.connect, 6, 'retries stop when the delays run out');
});

test('the schema is idempotent, upgrades older databases, and every table has a primary key (Fabric only replicates those to OneLake)', async () => {
  for (const statement of schemaStatements('mssql').filter((s) => s.includes('CREATE TABLE'))) {
    assert.match(statement, /^IF OBJECT_ID\(/);
    assert.match(statement, /CONSTRAINT pk_\w+ PRIMARY KEY/);
  }
  const repo = createCrmRepository(createSqliteStore());
  assert.equal(await repo.migrate(), CRM_SCHEMA_VERSION);
  assert.equal(await repo.migrate(), CRM_SCHEMA_VERSION);

  // A version 1 database had no month_start on the calendar: the upgrade adds and fills it.
  const store = createSqliteStore();
  await store.exec('CREATE TABLE calendar (date TEXT NOT NULL PRIMARY KEY, year INTEGER, quarter TEXT, month INTEGER, month_name TEXT, year_month TEXT, week_start TEXT)');
  await store.exec("INSERT INTO calendar VALUES ('2026-10-15', 2026, 'Q4', 10, 'Oct', '2026-10', '2026-10-12')");
  await createCrmRepository(store).migrate();
  assert.equal((await store.query('SELECT month_start FROM calendar'))[0].month_start, '2026-10-01');

  // A version 2 database had no state on accounts: the upgrade adds it (indexed), and existing accounts stay unassigned,
  // so managers see them and reps don't until someone sets the state.
  const v2 = createSqliteStore();
  await v2.exec(
    'CREATE TABLE sales_reps (rep_id TEXT NOT NULL PRIMARY KEY, name TEXT NOT NULL, email TEXT, region TEXT);' +
      'CREATE TABLE accounts (account_id TEXT NOT NULL PRIMARY KEY, name TEXT NOT NULL, industry TEXT, country TEXT, city TEXT, annual_revenue REAL, employees INTEGER, owner_id TEXT, created_at TEXT, updated_at TEXT);' +
      "INSERT INTO accounts (account_id, name) VALUES ('acc-old', 'Old Account');",
  );
  const upgraded = createCrmRepository(v2);
  assert.equal(await upgraded.migrate(), 3);
  assert.equal((await v2.query("SELECT state FROM accounts WHERE account_id = 'acc-old'"))[0].state, null);
  assert.equal((await v2.query("SELECT name FROM pragma_index_list('accounts') WHERE name = 'ix_accounts_state'")).length, 1);
  assert.equal((await upgraded.scoped(null).listAccounts()).total, 1);
  assert.equal((await upgraded.scoped(['Texas']).listAccounts()).total, 0);
});

test('sample data loads once and never overwrites real records', async () => {
  const repo = await seededRepo();
  const counts = await repo.counts();
  assert.equal(counts.sales_reps, 8);
  assert.equal(counts.accounts, 120);
  assert.equal(counts.calendar, 1461);
  assert.ok(counts.opportunities > 250 && counts.activities > 1000);
  assert.deepEqual(await repo.seed('again', { today: '2026-10-01' }), {});
  assert.deepEqual(await repo.counts(), counts);
});

test('sample data is consistent and dated from the day it is loaded; the calendar grows to cover it', async () => {
  const closed = new Set(['Closed Won', 'Closed Lost']);
  for (const today of ['2026-10-01', '2027-02-10', '2031-06-30']) {
    const data = fabricateCrm('fabrikam', { companyDomain: 'fabrikam.com', today });
    const days = new Set(data.calendar.map((d) => d.date));
    for (const o of data.opportunities) {
      assert.ok(o.created_at.slice(0, 10) <= o.close_date, `${o.opportunity_id} is created before it closes`);
      assert.ok(o.created_at.slice(0, 10) < today, `${o.opportunity_id} isn't created in the future`);
      if (closed.has(o.stage)) assert.ok(o.close_date <= today, `${o.opportunity_id} was decided on a past date`);
      assert.ok(days.has(o.close_date));
    }
    for (const a of data.accounts) assert.ok(a.created_at.slice(0, 10) < today);
    for (const t of data.activities) {
      assert.ok(days.has(t.activity_date));
      assert.equal(Boolean(t.completed), t.activity_date <= today, 'past activities are done, future ones planned');
    }
    const open = data.opportunities.filter((o) => !closed.has(o.stage));
    assert.ok(open.some((o) => o.close_date > today) && open.some((o) => o.close_date < today), 'open pipeline includes past-due and future deals');
    assert.ok(data.opportunities.some((o) => o.stage === 'Closed Won' && o.close_date.slice(0, 4) === today.slice(0, 4)), 'there are wins this year');
  }
  assert.deepEqual(fabricateCrm('x', { today: '2026-10-01' }), fabricateCrm('x', { today: '2026-10-01' }), 'deterministic per seed and day');

  // A CRM loaded in 2026 and reloaded in 2028 gets the calendar days the new data needs; nothing is removed.
  const store = createSqliteStore();
  const repo = createCrmRepository(store);
  await repo.migrate();
  await repo.seed('fabrikam', { today: '2026-10-01' });
  await repo.replaceWithSampleData('fabrikam', { today: '2028-03-01' });
  const days = await repo.counts();
  const [{ first, last }] = await store.query('SELECT MIN(date) AS first, MAX(date) AS last FROM calendar');
  assert.deepEqual([first, last], ['2024-01-01', '2029-12-31']);
  assert.equal(days.calendar, (Date.parse('2029-12-31') - Date.parse('2024-01-01')) / 86_400_000 + 1);
  assert.equal(await repo.ensureCalendar({ from: '2024-01-01', to: '2029-12-31' }), 0, 'nothing to add the second time');
});

test('records are created, validated, updated and paged', async () => {
  const repo = (await seededRepo()).scoped(null);
  const account = await repo.createAccount({ name: 'Contoso Pharma', industry: 'Healthcare', ownerId: 'rep-01', country: 'United States' });
  assert.equal(account.name, 'Contoso Pharma');
  assert.equal(account.state, null, 'managers may leave the territory empty');
  await assert.rejects(repo.createAccount({ name: '' }), (error) => error.status === 400);
  await assert.rejects(repo.createAccount({ name: 'Elsewhere', state: 'Ohio' }), (error) => error.status === 400);
  await assert.rejects(repo.createOpportunity({ accountId: 'missing', name: 'x' }), (error) => error.status === 404);
  const deal = await repo.createOpportunity({ accountId: account.id, name: 'Pilot', amount: '50000', closeDate: '2026-12-15', ownerId: 'rep-01' });
  assert.equal(deal.stage, 'Prospecting');
  assert.equal(deal.probability, 10);
  const moved = await repo.updateOpportunity(deal.id, { stage: 'Negotiation' });
  assert.equal(moved.probability, 75, 'the stage sets the probability');
  const page1 = await repo.listAccounts({ limit: 10, offset: 0, sort: 'name' });
  const page2 = await repo.listAccounts({ limit: 10, offset: 10, sort: 'name' });
  assert.equal(page1.total, 121);
  assert.equal(page1.rows.length, 10);
  assert.notEqual(page1.rows[0].id, page2.rows[0].id);
  const detail = await repo.getAccount(account.id);
  assert.equal(detail.opportunities.length, 1);
});

test('territory scope: reps read and write only their territories, unions add up, and a missing scope fails closed', async () => {
  const base = await seededRepo();
  const all = base.scoped(null);
  const texas = base.scoped(['Texas']);
  const total = (await all.listAccounts({ limit: 200 })).total;
  const perTerritory = {};
  for (const territory of TERRITORIES) perTerritory[territory] = (await base.scoped([territory]).listAccounts({ limit: 200 })).total;
  assert.equal(Object.values(perTerritory).reduce((a, b) => a + b, 0), total, 'every sample account is in exactly one territory');
  assert.equal((await base.scoped(['Texas', 'Georgia']).listAccounts()).total, perTerritory.Texas + perTerritory.Georgia, 'several territories are a union');
  assert.equal((await base.scoped([]).listAccounts()).total, 0, 'no territories, no accounts');
  assert.throws(() => base.scoped(undefined), /territory scope is required/);
  assert.equal(base.listAccounts, undefined, 'the unscoped repository has no customer reads');

  const mine = (await texas.listAccounts({ limit: 200 })).rows;
  assert.ok(mine.length && mine.every((a) => a.state === 'Texas'));
  for (const list of [await texas.listOpportunities({ limit: 200 }), await texas.listActivities({ limit: 200 }), await texas.listContacts({ limit: 200 })]) {
    const ids = new Set(mine.map((a) => a.id));
    assert.ok(list.rows.length && list.rows.every((r) => ids.has(r.accountId)), 'deals, activities and contacts follow their account');
  }
  assert.ok((await texas.lookupAccounts('')).every((a) => mine.some((m) => m.id === a.id)));
  assert.ok((await texas.options()).reps.every((r) => r.region === 'Texas'));
  assert.deepEqual((await texas.options()).territories, ['Texas']);

  // Someone else's territory looks like it doesn't exist, for reads and writes alike.
  const georgia = (await base.scoped(['Georgia']).listAccounts({ limit: 1 })).rows[0];
  const georgiaDeal = (await base.scoped(['Georgia']).listOpportunities({ limit: 1 })).rows[0];
  const georgiaActivity = (await base.scoped(['Georgia']).listActivities({ limit: 1 })).rows[0];
  assert.equal(await texas.getAccount(georgia.id), null);
  assert.equal(await texas.getOpportunity(georgiaDeal.id), null);
  const notFound = (error) => error.status === 404;
  await assert.rejects(texas.updateAccount(georgia.id, { name: 'Mine now' }), notFound);
  await assert.rejects(texas.updateOpportunity(georgiaDeal.id, { stage: 'Closed Lost' }), notFound);
  await assert.rejects(texas.updateActivity(georgiaActivity.id, { completed: true }), notFound);
  await assert.rejects(texas.createOpportunity({ accountId: georgia.id, name: 'Sneaky' }), notFound);
  await assert.rejects(texas.createActivity({ accountId: georgia.id, type: 'Call', subject: 'Sneaky' }), notFound);
  await assert.rejects(texas.createContact({ accountId: georgia.id, lastName: 'Sneaky' }), notFound);
  assert.equal((await all.getAccount(georgia.id)).name, georgia.name, 'nothing changed');

  // New accounts land in the rep's territory; reps can't put or move accounts elsewhere.
  const created = await texas.createAccount({ name: 'Lone Star Labs' });
  assert.deepEqual([created.state, created.country], ['Texas', 'United States']);
  await assert.rejects(texas.createAccount({ name: 'Peach Labs', state: 'Georgia' }), (error) => error.status === 403);
  await assert.rejects(texas.updateAccount(created.id, { state: 'Georgia' }), (error) => error.status === 403);
  await assert.rejects(texas.updateAccount(created.id, { state: '' }), (error) => error.status === 400);
  await assert.rejects(base.scoped(['Texas', 'Georgia']).createAccount({ name: 'Which one' }), (error) => error.status === 400, 'with two territories the rep picks one');
  assert.equal((await all.updateAccount(created.id, { state: 'Georgia' })).state, 'Georgia', 'managers can move accounts');
  assert.equal(await texas.getAccount(created.id), null);

  // Headline numbers and quick answers are scoped the same way.
  const sum = (rows) => rows.reduce((s, r) => s + (r.value || 0), 0);
  const texasSummary = await texas.summary();
  assert.equal(texasSummary.accounts, perTerritory.Texas);
  const byState = await all.quickAnswer('pipeline by territory', { today: TODAY });
  assert.deepEqual(byState.rows.map((r) => r.label).sort(), [...TERRITORIES].sort());
  const texasByState = await texas.quickAnswer('pipeline by state', { today: TODAY });
  assert.deepEqual(texasByState.rows.map((r) => r.label), ['Texas']);
  assert.equal(texasByState.rows[0].value, byState.rows.find((r) => r.label === 'Texas').value);
  assert.equal(sum((await texas.quickAnswer('pipeline by stage', { today: TODAY })).rows), texasSummary.pipelineValue);
  const askingForGeorgia = await texas.quickAnswer('pipeline in georgia', { today: TODAY });
  assert.equal(askingForGeorgia.rows[0].value, null, "naming another territory doesn't widen the scope");
});

test('plain-language requests become a measure, a breakdown, filters and a period', () => {
  const spec = (text) => {
    const p = parseRequest(text, { today: TODAY });
    return [p.measure?.name || null, p.dimension ? `${p.dimension.table}.${p.dimension.column}` : null, p.filters.map((f) => f.value).join(','), p.period?.label || null, p.top];
  };
  assert.deepEqual(spec('pipeline by stage'), ['Pipeline Value', 'opportunities.stage', '', null, null]);
  assert.deepEqual(spec('top 5 accounts by won revenue this year'), ['Won Revenue', 'accounts.name', '', '2026', 5]);
  assert.deepEqual(spec('win rate by sales rep'), ['Win Rate', 'sales_reps.name', '', null, null]);
  assert.deepEqual(spec('pipeline in healthcare by region'), ['Pipeline Value', 'sales_reps.region', 'Healthcare', null, null]);
  assert.deepEqual(spec('won revenue in new mexico by territory'), ['Won Revenue', 'accounts.state', 'New Mexico', null, null]);
  assert.deepEqual(spec('accounts owned per rep'), ['# Accounts Owned', 'sales_reps.name', '', null, null]);
  assert.deepEqual(spec('how many accounts'), ['# Accounts', null, '', null, null]);
  assert.deepEqual(spec('activities by type last quarter'), ['# Activities', 'activities.type', '', 'last quarter', null]);
  // "Value" questions get money, not counts (found when the live data agent was unavailable on a trial capacity).
  assert.deepEqual(spec('What is the total value of open opportunities by stage?'), ['Pipeline Value', 'opportunities.stage', '', null, null]);
  assert.deepEqual(spec('how many open opportunities by stage'), ['# Open Opportunities', 'opportunities.stage', '', null, null]);
  assert.deepEqual(spec('value of won deals by industry'), ['Won Revenue', 'accounts.industry', '', null, null]);
  assert.deepEqual(spec('total value of all deals'), ['Total Amount', null, '', null, null]);
  assert.equal(parseRequest('what is the weather', { today: TODAY }).measure, null);
});

test('describe a chart picks a sensible visual and real model fields', () => {
  const trend = describeVisual('won revenue by month', { today: TODAY });
  assert.deepEqual([trend.visualType, trend.measure, trend.dimension, trend.sortByCategory], ['lineChart', { table: 'Opportunities', name: 'Won Revenue' }, { table: 'Calendar', column: 'Month Start' }, true]);
  assert.equal(describeVisual('pipeline by stage').visualType, 'funnel');
  assert.equal(describeVisual('pipeline by industry as a pie chart').visualType, 'pieChart');
  assert.equal(describeVisual('average deal size').visualType, 'card');
  assert.equal(describeVisual('make it pretty').ok, false);
  const catalog = fieldCatalog();
  const names = new Set(CRM_TABLES.flatMap((t) => t.columns.map((c) => `${t.model}|${c.model}`)));
  for (const d of catalog.dimensions) assert.ok(names.has(`${d.table}|${d.column}`), `${d.table}[${d.column}] exists in the model`);
});

test('quick answers compute the same business rules as the model measures', async () => {
  const repo = (await seededRepo()).scoped(null);
  const pipeline = await repo.quickAnswer('pipeline value', { today: TODAY });
  const summary = await repo.summary();
  assert.equal(pipeline.rows[0].value, summary.pipelineValue);
  const byStage = await repo.quickAnswer('pipeline by stage', { today: TODAY });
  assert.ok(byStage.rows.every((r) => !['Closed Won', 'Closed Lost'].includes(r.label)), 'closed deals are not pipeline');
  assert.equal(byStage.rows.reduce((sum, r) => sum + r.value, 0), summary.pipelineValue);
  const top = await repo.quickAnswer('top 3 accounts by won revenue', { today: TODAY });
  assert.equal(top.rows.length, 3);
  assert.ok(top.rows[0].value >= top.rows[1].value);
  const rate = await repo.quickAnswer('win rate', { today: TODAY });
  assert.match(rate.answer, /^Win Rate: \d+(\.\d)?%\.$/);
  assert.equal(await repo.quickAnswer('hello there', { today: TODAY }), null);
});

test('every measure quick answers can pick has a SQL version; report-only measures stay out', async () => {
  const withSynonyms = MEASURES.filter((m) => m.synonyms.length).map((m) => m.name);
  assert.deepEqual(withSynonyms.filter((name) => !QUICK_ANSWER_MEASURES.includes(name)), []);
  assert.ok(MEASURES.filter((m) => !m.synonyms.length).length >= 20, 'the report measures have no synonyms');
  const repo = (await seededRepo()).scoped(null);
  assert.ok(await repo.quickAnswer('pipeline value', { today: TODAY }));
});

test('the semantic model is generated from the schema: Direct Lake, hidden keys, relationships and formatted measures', () => {
  const { definition, files, fingerprint } = buildSemanticModelDefinition({ workspaceId: 'ws-1', sqlDatabaseId: 'db-1' });
  assert.deepEqual(definition.parts.map((p) => p.path).slice(0, 5), ['definition.pbism', 'definition/database.tmdl', 'definition/model.tmdl', 'definition/expressions.tmdl', 'definition/relationships.tmdl']);
  assert.match(files['definition/expressions.tmdl'], /AzureStorage\.DataLake\("https:\/\/onelake\.dfs\.fabric\.microsoft\.com\/ws-1\/db-1"/);
  assert.match(files['definition/model.tmdl'], /discourageImplicitMeasures/);
  for (const table of CRM_TABLES) {
    const tmdl = files[`definition/tables/${table.model}.tmdl`];
    assert.match(tmdl, /partition .+ = entity\n\t\tmode: directLake\n\t\tsource\n\t\t\tentityName: \w+\n\t\t\tschemaName: dbo/);
    for (const column of table.columns.filter((c) => c.references)) {
      assert.match(tmdl, new RegExp(`column '${column.model}'\\n\\t\\tdataType: string\\n\\t\\tisHidden`), `${table.model}.${column.model} is hidden`);
    }
    assert.ok(!tmdl.includes('updated_at'), 'technical timestamps stay out of the model');
  }
  assert.match(files['definition/tables/Calendar.tmdl'], /dataCategory: Time[\s\S]*column Date\n\t\tdataType: dateTime\n\t\tisKey/);
  assert.match(files['definition/tables/Calendar.tmdl'], /sortByColumn: 'Month Number'/);
  assert.equal((files['definition/relationships.tmdl'].match(/^relationship /gm) || []).length, CRM_RELATIONSHIPS.length);
  assert.equal((files['definition/relationships.tmdl'].match(/isActive: false/g) || []).length, 1);
  assert.ok(MEASURES.some((m) => m.expression.includes("'Accounts'[Account Owner ID]")), 'accounts per owner still have a measure, without the inactive relationship');
  for (const measure of MEASURES) assert.ok(measure.format && measure.description && measure.folder, `${measure.name} has a format, description and folder`);
  assert.equal(new Set(MEASURES.map((m) => m.name)).size, MEASURES.length, 'measure names are unique');
  // Every [measure] a measure refers to exists, so a typo can't publish a broken model.
  const names = new Set(MEASURES.map((m) => m.name));
  for (const measure of MEASURES) {
    for (const [, ref] of measure.expression.matchAll(/(?<!')\[([^\]]+)\]/g)) {
      const isColumn = CRM_TABLES.some((t) => t.columns.some((c) => c.model === ref));
      assert.ok(names.has(ref) || isColumn, `${measure.name} refers to [${ref}], which exists`);
    }
  }
  assert.match(files['definition/tables/Opportunities.tmdl'], /column 'Opportunity ID'\n\t\tdataType: string\n\t\tsummarizeBy: none/, 'deal tables can include the ID');
  assert.equal(buildSemanticModelDefinition({ workspaceId: 'ws-1', sqlDatabaseId: 'db-1' }).fingerprint, fingerprint, 'the fingerprint is stable');
  assert.notEqual(buildSemanticModelDefinition({ workspaceId: 'ws-2', sqlDatabaseId: 'db-1' }).fingerprint, fingerprint);

  // Row-level security: a role per territory filters Accounts by State; managers' role has no filter.
  assert.match(files['definition/tables/Accounts.tmdl'], /column State\n\t\tdataType: string\n\t\tdataCategory: StateOrProvince/);
  assert.equal(files[`definition/roles/${ALL_TERRITORIES_ROLE}.tmdl`], "role 'All territories'\n\tmodelPermission: read\n");
  for (const territory of TERRITORIES) {
    assert.match(files[`definition/roles/${territory}.tmdl`], new RegExp(`^role ('${territory}'|${territory})\\n\\tmodelPermission: read\\n\\n\\ttablePermission Accounts = 'Accounts'\\[State\\] = "${territory}"\\n$`));
  }
  assert.deepEqual(rolesFor(null), [ALL_TERRITORIES_ROLE]);
  assert.deepEqual(rolesFor(['Georgia', 'Texas', 'Ohio']), ['Texas', 'Georgia'], 'only roles the model has, in a stable order');

  // USERELATIONSHIP and CROSSFILTER return an error for viewers whose roles filter a table they touch, so no measure
  // in the model with roles may use them (https://learn.microsoft.com/dax/userelationship-function-dax#remarks).
  const relationshipFunctions = MEASURES.filter((m) => /\b(USERELATIONSHIP|CROSSFILTER)\s*\(/i.test(m.expression)).map((m) => m.name);
  assert.deepEqual(relationshipFunctions, [], 'measures that would fail under row-level security');
  assert.match(MEASURES.find((m) => m.name === '# Accounts Owned').expression, /TREATAS\(VALUES\('Sales Reps'\[Rep ID\]\), 'Accounts'\[Account Owner ID\]\)/);
});

test('the data agent sees the semantic model with measures and descriptions, but not hidden keys', () => {
  const { parts } = buildSemanticModelAgentDefinition({ workspaceId: 'ws', semanticModelId: 'model', semanticModelName: 'HiCRM Insights', tables: agentTables(), instructions: 'x', description: 'y' });
  const published = parts.find((p) => p.path === 'Files/Config/published/semantic_model-HiCRM Insights/datasource.json');
  const source = JSON.parse(decodePayload(published.payload));
  assert.equal(source.type, 'semantic_model');
  const opportunities = source.elements.find((e) => e.display_name === 'Opportunities');
  assert.ok(opportunities.children.find((c) => c.display_name === 'Win Rate').description.includes('won deals divided by'));
  assert.ok(!opportunities.children.some((c) => /ID$/.test(c.display_name)));
  assert.ok(source.elements.every((e) => /^[0-9a-f-]{36}$/.test(e.id)), 'elements carry stable IDs');
});
