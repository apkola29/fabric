import { DIMENSIONS, MEASURES, modelColumn, modelTableName } from './model.js';
import { ACTIVITY_TYPES, CLOSED_STAGES, INDUSTRIES, STAGES, TERRITORIES, tableByName } from './schema.js';
import { checkScope, scopeSql } from './scope.js';

// Plain-language requests ("pipeline by stage", "top 5 accounts by won revenue this year") turned into a small spec:
// one measure, at most one dimension, optional filters, period and top-N. The describe-a-chart box turns the spec into
// a Power BI visual; the assistant's quick answers turn it into SQL over the CRM database.

const CLOSED_SQL = CLOSED_STAGES.map((s) => `'${s}'`).join(', ');

// SQL versions of the model's measures (same business rules as the DAX in model.js).
const MEASURE_SQL = {
  'Total Amount': { base: 'opportunities', sql: 'SUM(o.amount)' },
  'Pipeline Value': { base: 'opportunities', sql: `SUM(CASE WHEN o.stage NOT IN (${CLOSED_SQL}) THEN o.amount END)` },
  'Weighted Pipeline': { base: 'opportunities', sql: `SUM(CASE WHEN o.stage NOT IN (${CLOSED_SQL}) THEN o.amount * o.probability / 100.0 END)` },
  'Won Revenue': { base: 'opportunities', sql: "SUM(CASE WHEN o.stage = 'Closed Won' THEN o.amount END)" },
  'Lost Amount': { base: 'opportunities', sql: "SUM(CASE WHEN o.stage = 'Closed Lost' THEN o.amount END)" },
  '# Opportunities': { base: 'opportunities', sql: 'COUNT(*)' },
  '# Open Opportunities': { base: 'opportunities', sql: `SUM(CASE WHEN o.stage NOT IN (${CLOSED_SQL}) THEN 1 END)` },
  '# Won Deals': { base: 'opportunities', sql: "SUM(CASE WHEN o.stage = 'Closed Won' THEN 1 END)" },
  '# Lost Deals': { base: 'opportunities', sql: "SUM(CASE WHEN o.stage = 'Closed Lost' THEN 1 END)" },
  'Win Rate': {
    base: 'opportunities',
    sql: `SUM(CASE WHEN o.stage = 'Closed Won' THEN 1 ELSE 0 END) * 1.0 / NULLIF(SUM(CASE WHEN o.stage IN (${CLOSED_SQL}) THEN 1 ELSE 0 END), 0)`,
  },
  'Average Deal Size': {
    base: 'opportunities',
    sql: "SUM(CASE WHEN o.stage = 'Closed Won' THEN o.amount END) * 1.0 / NULLIF(SUM(CASE WHEN o.stage = 'Closed Won' THEN 1 ELSE 0 END), 0)",
  },
  'Won Revenue (ytd)': { base: 'opportunities', sql: "SUM(CASE WHEN o.stage = 'Closed Won' THEN o.amount END)", period: 'ytd' },
  'Won Revenue (ly)': { base: 'opportunities', sql: "SUM(CASE WHEN o.stage = 'Closed Won' THEN o.amount END)", period: 'last-year' },
  '# Accounts': { base: 'accounts', sql: 'COUNT(*)' },
  '# Accounts Owned': { base: 'accounts', sql: 'COUNT(*)' },
  '# Accounts With Open Deals': { base: 'opportunities', sql: `COUNT(DISTINCT CASE WHEN o.stage NOT IN (${CLOSED_SQL}) THEN o.account_id END)` },
  '# Contacts': { base: 'contacts', sql: 'COUNT(*)' },
  '# Activities': { base: 'activities', sql: 'COUNT(*)' },
  '# Completed Activities': { base: 'activities', sql: 'SUM(CASE WHEN t.completed = 1 THEN 1 END)' },
  '# Planned Activities': { base: 'activities', sql: 'SUM(CASE WHEN t.completed = 0 THEN 1 END)' },
  'Activity Hours': { base: 'activities', sql: 'SUM(t.duration_minutes) / 60.0' },
  '# Opportunities Touched': { base: 'activities', sql: 'COUNT(DISTINCT t.opportunity_id)' },
};

const BASES = {
  opportunities: { alias: 'o', from: 'opportunities o', date: 'o.close_date', dateLabel: 'close date' },
  activities: { alias: 't', from: 'activities t', date: 't.activity_date', dateLabel: 'activity date' },
  accounts: { alias: 'a', from: 'accounts a', date: null },
  contacts: { alias: 'c', from: 'contacts c', date: null },
};

// How each base table reaches the tables people slice by.
const JOINS = {
  opportunities: {
    opportunities: null,
    accounts: 'JOIN accounts a ON a.account_id = o.account_id',
    sales_reps: 'JOIN sales_reps r ON r.rep_id = o.owner_id',
    calendar: 'JOIN calendar d ON d.date = o.close_date',
  },
  activities: {
    activities: null,
    accounts: 'JOIN accounts a ON a.account_id = t.account_id',
    sales_reps: 'JOIN sales_reps r ON r.rep_id = t.owner_id',
    calendar: 'JOIN calendar d ON d.date = t.activity_date',
  },
  accounts: { accounts: null, sales_reps: 'JOIN sales_reps r ON r.rep_id = a.owner_id' },
  contacts: { contacts: null, accounts: 'JOIN accounts a ON a.account_id = c.account_id' },
};
const ALIASES = { opportunities: 'o', activities: 't', accounts: 'a', contacts: 'c', sales_reps: 'r', calendar: 'd' };

// Known values become filters: "pipeline in healthcare", "won deals in negotiation", "demos this month".
const VALUE_FILTERS = [
  ...INDUSTRIES.map((value) => ({ table: 'accounts', column: 'industry', value })),
  ...TERRITORIES.map((value) => ({ table: 'accounts', column: 'state', value })),
  ...STAGES.map((value) => ({ table: 'opportunities', column: 'stage', value })),
  ...ACTIVITY_TYPES.map((value) => ({ table: 'activities', column: 'type', value })),
];

const CHARTS = [
  { type: 'card', words: ['card', 'kpi', 'single number', 'big number'] },
  { type: 'tableEx', words: ['table', 'list', 'grid'] },
  { type: 'lineChart', words: ['line chart', 'line', 'trend line'] },
  { type: 'areaChart', words: ['area chart', 'area'] },
  { type: 'pieChart', words: ['pie chart', 'pie'] },
  { type: 'donutChart', words: ['donut chart', 'donut', 'doughnut'] },
  { type: 'funnel', words: ['funnel chart'] },
  { type: 'treemap', words: ['treemap', 'tree map'] },
  { type: 'clusteredColumnChart', words: ['column chart', 'columns', 'column', 'vertical bar'] },
  { type: 'clusteredBarChart', words: ['bar chart', 'bars', 'bar', 'ranking'] },
];

const normalize = (text) => ` ${String(text || '').toLowerCase().replace(/[^a-z0-9#%$]+/g, ' ').replace(/\s+/g, ' ').trim()} `;
const variants = (phrase) => {
  const base = normalize(phrase).trim();
  return [...new Set([base, `${base}s`, base.endsWith('y') ? `${base.slice(0, -1)}ies` : null].filter(Boolean))];
};

function findAll(text, entries) {
  const hits = [];
  for (const entry of entries) {
    for (const phrase of entry.phrases) {
      let from = 0;
      for (;;) {
        const index = text.indexOf(` ${phrase} `, from);
        if (index < 0) break;
        hits.push({ entry, start: index + 1, end: index + 1 + phrase.length, phrase });
        from = index + 1;
      }
    }
  }
  // Longest match first, then drop overlaps.
  hits.sort((a, b) => b.end - b.start - (a.end - a.start) || a.start - b.start);
  const kept = [];
  for (const hit of hits) if (!kept.some((k) => hit.start < k.end && k.start < hit.end)) kept.push(hit);
  return kept.sort((a, b) => a.start - b.start);
}

const MEASURE_ENTRIES = MEASURES.map((m) => ({ kind: 'measure', measure: m, phrases: m.synonyms.flatMap(variants) }));
const DIMENSION_ENTRIES = DIMENSIONS.map((d) => ({ kind: 'dimension', dimension: d, phrases: d.synonyms.flatMap(variants) }));
const FILTER_ENTRIES = VALUE_FILTERS.map((f) => ({ kind: 'filter', filter: f, phrases: variants(f.value) }));

function periodFor(text, today) {
  const year = today.getUTCFullYear();
  const month = today.getUTCMonth();
  const iso = (d) => d.toISOString().slice(0, 10);
  const day = (y, m, d) => new Date(Date.UTC(y, m, d));
  const quarterStart = Math.floor(month / 3) * 3;
  const explicitYear = /\b(?:in|for|during)? ?(20\d\d)\b/.exec(text);
  if (/ (ytd|year to date) /.test(text)) return { key: 'ytd', label: `${year} year to date`, from: `${year}-01-01`, to: iso(today) };
  if (/ (last|previous|prior) year /.test(text)) return { key: 'last-year', label: String(year - 1), from: `${year - 1}-01-01`, to: `${year - 1}-12-31` };
  if (/ (this|current) year /.test(text)) return { key: 'this-year', label: String(year), from: `${year}-01-01`, to: `${year}-12-31` };
  if (/ (last|previous|prior) quarter /.test(text)) {
    const start = day(year, quarterStart - 3, 1);
    return { key: 'last-quarter', label: 'last quarter', from: iso(start), to: iso(day(year, quarterStart, 0)) };
  }
  if (/ (this|current) quarter /.test(text)) return { key: 'this-quarter', label: 'this quarter', from: iso(day(year, quarterStart, 1)), to: iso(day(year, quarterStart + 3, 0)) };
  if (/ (last|previous|prior) month /.test(text)) return { key: 'last-month', label: 'last month', from: iso(day(year, month - 1, 1)), to: iso(day(year, month, 0)) };
  if (/ (this|current) month /.test(text)) return { key: 'this-month', label: 'this month', from: iso(day(year, month, 1)), to: iso(day(year, month + 1, 0)) };
  if (explicitYear) return { key: `year-${explicitYear[1]}`, label: explicitYear[1], from: `${explicitYear[1]}-01-01`, to: `${explicitYear[1]}-12-31` };
  return null;
}

const PERIOD_WORDS = / (?:ytd|year to date|(?:this|current|last|previous|prior) (?:year|quarter|month)|(?:(?:in|for|during) )?20\d\d)(?= )/g;

export function parseRequest(input, { today = new Date() } = {}) {
  const full = normalize(input);
  // Dates are handled by the period, so "this year" must not also become a "by year" breakdown.
  const text = full.replace(PERIOD_WORDS, ' ').replace(/ {2,}/g, ' ');
  let measures = findAll(text, MEASURE_ENTRIES);
  let dimensions = findAll(text, DIMENSION_ENTRIES);
  const filters = findAll(text, FILTER_ENTRIES);
  const overlaps = (a, b) => a.start < b.end && b.start < a.end;
  const length = (h) => h.end - h.start;
  // A longer phrase of another kind wins: "sales rep" is a dimension, not the measure "sales".
  const shadowed = (hit, others) => others.some((o) => overlaps(o, hit) && length(o) > length(hit));
  const all = [...measures, ...dimensions, ...filters];
  measures = measures.filter((h) => !shadowed(h, all));
  dimensions = dimensions.filter((h) => !shadowed(h, all));
  const precededBy = (hit, words) => words.some((w) => text.slice(0, hit.start).endsWith(` ${w} `));
  const afterRank = (hit) => / (?:top|bottom|best|worst|biggest|largest|smallest|lowest|first) \d{1,2} $/.test(text.slice(0, hit.start));

  // "top 5 accounts by won revenue": the measure follows "by"; otherwise take the first measure mentioned.
  let measureHit = measures.find((h) => precededBy(h, ['by', 'in terms of', 'ranked by', 'sorted by'])) || null;
  const dimensionCandidates = dimensions.filter((d) => !filters.some((f) => overlaps(f, d)));
  if (!measureHit) {
    // A word like "accounts" can be both; it's a dimension when another measure is present or it follows "by".
    measureHit = measures.find((m) => !dimensionCandidates.some((d) => overlaps(d, m) && precededBy(d, ['by', 'per', 'each', 'across']))) || null;
    if (measureHit && measures.length > 1 && dimensionCandidates.some((d) => overlaps(d, measureHit))) {
      measureHit = measures.find((m) => !dimensionCandidates.some((d) => overlaps(d, m))) || measureHit;
    }
  }
  const freeDimensions = dimensionCandidates.filter((d) => !measureHit || !overlaps(d, measureHit));
  const dimensionHit =
    freeDimensions.find((d) => precededBy(d, ['by', 'per', 'each', 'across', 'split by', 'broken down by', 'for each', 'over'])) ||
    freeDimensions.find(afterRank) ||
    freeDimensions[0] ||
    null;

  const top = /\b(?:top|best|biggest|largest|first) (\d{1,2})\b/.exec(text) || /\b(\d{1,2}) (?:biggest|largest|best|top)\b/.exec(text);
  const bottom = /\b(?:bottom|worst|smallest|lowest) (\d{1,2})\b/.exec(text);
  const chart = CHARTS.find((c) => c.words.some((w) => text.includes(` ${w} `)));
  return {
    measure: measureHit?.entry.measure || null,
    dimension: dimensionHit?.entry.dimension || null,
    filters: filters.map((f) => f.entry.filter),
    period: periodFor(full, today),
    top: bottom ? Number(bottom[1]) : top ? Number(top[1]) : null,
    order: bottom ? 'asc' : 'desc',
    chart: chart?.type || null,
  };
}

const measureRef = (m) => ({ table: modelTableName(m.table), name: m.name });
const dimensionRef = (d) => ({ table: modelTableName(d.table), column: modelColumn(d.table, d.column).model });

function chooseVisual(spec) {
  if (!spec.dimension) return 'card';
  if (spec.chart && spec.chart !== 'card') return spec.chart;
  if (spec.dimension.timeline) return 'lineChart';
  if (spec.dimension.table === 'opportunities' && spec.dimension.column === 'stage') return 'funnel';
  return 'clusteredBarChart';
}

// "Describe a chart": the visual the browser should build with the Power BI report authoring API.
export function describeVisual(text, options) {
  const spec = parseRequest(text, options);
  if (!spec.measure) {
    return { ok: false, message: 'Say what to measure, for example "pipeline by stage" or "won revenue by month".' };
  }
  const visualType = chooseVisual(spec);
  const measure = measureRef(spec.measure);
  const dimension = spec.dimension ? dimensionRef(spec.dimension) : null;
  const title = dimension ? `${measure.name} by ${spec.dimension.label || dimension.column}` : measure.name;
  const notes = [];
  if (spec.filters.length || spec.period) notes.push('Filters and dates in the request are not applied to the visual yet; use the filter pane.');
  // Time runs left to right; anything else is ranked by the measure (Power BI's default).
  return { ok: true, visualType, title, measure, dimension, top: spec.top, sortByCategory: Boolean(spec.dimension?.timeline), notes };
}

// `scope` limits the rows to accounts in some territories (see scope.js). Every base table reaches Accounts, so the
// scope always applies.
function insightSql(spec, dialect, scope) {
  const definition = MEASURE_SQL[spec.measure.name];
  const base = BASES[definition.base];
  const joins = new Set();
  const params = {};
  const where = [];
  let label = null;
  const territories = checkScope(scope);
  if (territories !== null) {
    const join = JOINS[definition.base].accounts;
    if (join === undefined) throw new Error(`${spec.measure.name} can't be limited to territories.`);
    if (join) joins.add(join);
    where.push(scopeSql(territories, params));
  }
  if (spec.dimension) {
    const join = JOINS[definition.base][spec.dimension.table];
    if (join === undefined) return null;
    if (join) joins.add(join);
    label = `${ALIASES[spec.dimension.table]}.${spec.dimension.column}`;
  }
  spec.filters.forEach((filter, i) => {
    const join = JOINS[definition.base][filter.table];
    if (join === undefined) return;
    if (join) joins.add(join);
    where.push(`${ALIASES[filter.table]}.${filter.column} = @f${i}`);
    params[`f${i}`] = filter.value;
  });
  const period = spec.period || (definition.period ? periodFor(` ${definition.period === 'ytd' ? 'ytd' : 'last year'} `, spec.today) : null);
  if (period && base.date) {
    where.push(`${base.date} >= @from AND ${base.date} <= @to`);
    Object.assign(params, { from: period.from, to: period.to });
  }
  const whereSql = where.length ? ` WHERE ${where.join(' AND ')}` : '';
  const from = `FROM ${base.from} ${[...joins].join(' ')}`.trim();
  if (!label) return { sql: `SELECT ${definition.sql} AS value ${from}${whereSql}`, params, period: base.date ? period : null };
  const limit = spec.top || 50;
  const timeline = spec.dimension.timeline;
  const order = timeline ? `${label} ASC` : `value ${spec.order === 'asc' ? 'ASC' : 'DESC'}`;
  params.top = limit;
  const select = `${definition.sql} AS value, ${label} AS label`;
  // Groups where the measure is empty (BLANK in the model) are left out, as in a Power BI visual.
  const grouped = `${from}${whereSql} GROUP BY ${label} HAVING ${definition.sql} IS NOT NULL ORDER BY ${order}`;
  const sql = dialect === 'mssql' ? `SELECT TOP (@top) ${select} ${grouped}` : `SELECT ${select} ${grouped} LIMIT @top`;
  return { sql, params, period: base.date ? period : null };
}

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const integer = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });

export function formatMeasure(measure, value) {
  if (value === null || value === undefined) return 'no data';
  const n = Number(value);
  if (measure.format === '0.0%') return `${decimal.format(n * 100)}%`;
  if (measure.format.includes('$')) return money.format(n);
  if (measure.format === '#,##0.0') return decimal.format(n);
  return integer.format(n);
}

const labelText = (value) => (value === null || value === undefined || value === '' ? '(none)' : String(value));
const monthLabel = (value) => new Date(`${String(value).slice(0, 10)}T00:00:00Z`).toLocaleString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });

// Quick answers: runs the spec as SQL against the customer's CRM database and words the result. `scope` is required:
// null for every territory, or the territories the person may see.
export async function quickAnswer(query, input, { today = new Date(), scope } = {}) {
  checkScope(scope);
  const spec = { ...parseRequest(input, { today }), today };
  if (!spec.measure) return null;
  const measure = spec.measure;
  // Report-only measures (no SQL version) aren't answered here; the data agent knows them.
  if (!MEASURE_SQL[measure.name]) return { answer: `I can't work out ${measure.name} here. Try pipeline, revenue, win rate, deals, accounts or activities.`, rows: [] };
  const built = insightSql(spec, query.dialect, scope);
  if (!built) {
    const dimension = modelColumn(spec.dimension.table, spec.dimension.column).model;
    return { answer: `I can't split ${measure.name} by ${dimension}. Try another breakdown, such as by month or by sales rep.`, rows: [] };
  }
  const rows = await query.run(built.sql, built.params);
  const when = built.period ? ` (${built.period.label})` : '';
  const filterText = spec.filters.length ? ` for ${spec.filters.map((f) => f.value).join(', ')}` : '';
  if (!spec.dimension) {
    const value = rows[0]?.value ?? (measure.format === '#,##0' ? 0 : null);
    return { answer: `${measure.name}${filterText}${when}: ${formatMeasure(measure, value)}.`, rows: [{ label: measure.name, value, display: formatMeasure(measure, value) }], measure: measure.name };
  }
  const dimension = modelColumn(spec.dimension.table, spec.dimension.column).model;
  const dimensionLabel = spec.dimension.label || dimension;
  const asLabel = spec.dimension.column === 'month_start' ? (v) => (v ? monthLabel(v) : '(none)') : labelText;
  const shaped = rows.map((r) => ({ label: asLabel(r.label), value: r.value === null ? null : Number(r.value), display: formatMeasure(measure, r.value) }));
  if (!shaped.length) return { answer: `There's no ${measure.name}${filterText}${when} to show by ${dimensionLabel}.`, rows: [] };
  const leaders = shaped.slice(0, 3).map((r) => `${r.label} ${r.display}`).join(', ');
  const heading = spec.top ? `${spec.order === 'asc' ? 'Bottom' : 'Top'} ${shaped.length} by ${measure.name}` : `${measure.name} by ${dimensionLabel}`;
  const lead = spec.dimension.timeline ? `${shaped.length} periods` : `Highest: ${leaders}`;
  return { answer: `${heading}${filterText}${when}. ${lead}.`, rows: shaped, measure: measure.name, dimension: dimensionLabel, chart: spec.dimension.timeline ? 'line' : 'bar' };
}

export const QUICK_EXAMPLES = ['Pipeline by stage', 'Top 5 accounts by won revenue this year', 'Win rate by sales rep', 'Activities by type this quarter'];
export const QUICK_ANSWER_MEASURES = Object.keys(MEASURE_SQL);
export const tableModelName = (name) => tableByName(name).model;
