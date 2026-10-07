import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { MEASURES_FILE, PROMPT_FILE, daxProblems, measuresDax, promptProblems, refreshPrompt, starterReportSpec } from '../src/crm/assets.js';
import { MEASURES } from '../src/crm/model.js';
import { starterReportVisuals } from '../src/crm/report.js';

const read = (file) => readFileSync(file, 'utf8').replace(/\r\n/g, '\n');
const STALE = 'is stale: run `node scripts/report-assets.js` after changing model.js, schema.js or report.js';

test('the report assets match the model and the starter report', () => {
  assert.equal(read(MEASURES_FILE), measuresDax(), `Platform-app-Insights.measures.dax ${STALE}`);
  const prompt = read(PROMPT_FILE);
  assert.equal(prompt, refreshPrompt(prompt), `report-creation-prompt.md ${STALE}`);
  assert.equal((measuresDax().match(/^ {4}MEASURE '/gm) || []).length, MEASURES.length, 'every measure is defined once');
});

test("the measures' DAX uses the model's names and conventions", () => {
  assert.deepEqual(daxProblems(), []);
  const broken = (name, expression, extra = {}) => ({ table: 'opportunities', name, folder: 'Results', format: '\\$#,##0', expression, ...extra });
  const problems = daxProblems([
    broken('Database Name', "SUM('opportunities'[amount])"),
    broken('Bare Column', 'SUM([Amount])'),
    broken('Unquoted Table', 'SUM(Opportunities[Amount])'),
    broken('Qualified Measure', "'Opportunities'[Total Amount] * 2"),
    broken('Wrong Table', "SUM('Accounts'[Amount])"),
    broken('Stage', "COUNTROWS('Opportunities')"),
    broken('Open Count', "COUNTROWS('Opportunities')", { format: '#,##0' }),
    broken('Won Revenue Ytd', '[Won Revenue]', { folder: 'Time intelligence' }),
    broken('Variable', 'VAR total = [Won Revenue]\nRETURN total'),
    broken('database name', '[Won Revenue]'),
  ]);
  for (const expected of [
    /^Database Name: 'opportunities' isn't a table/,
    /^Bare Column: \[Amount\] isn't a measure/,
    /^Unquoted Table: write table names in quotes/,
    /^Qualified Measure: 'Opportunities'\[Total Amount\] isn't a column of Opportunities; refer to measures without a table/,
    /^Wrong Table: 'Accounts'\[Amount\] isn't a column of Accounts/,
    /^Stage: a column has the same name/,
    /^Open Count: count measures start with "# "/,
    /^Won Revenue Ytd: time intelligence measures end in/,
    /^Variable: variable total should start with "_"/,
    /^database name: another measure has the same name/,
  ]) {
    assert.ok(problems.some((p) => expected.test(p)), `caught ${expected}`);
  }
});

test('the prompt names only fields a visual can use, and no DAX', () => {
  assert.deepEqual(promptProblems(read(PROMPT_FILE)), []);
  const problems = promptProblems(
    [
      'Use `accounts[state]` and `Opportunities[Amount]`, `Accounts[Pipeline Value]`, `Sales Reps[name]`.',
      '{ "field": "Calendar[month_start]" }',
      'Pipeline = CALCULATE([Total Amount])',
    ].join('\n'),
  );
  for (const expected of [
    /^accounts\[state\]: accounts isn't a table/,
    /^Opportunities\[Amount\] is hidden/,
    /^Accounts\[Pipeline Value\]: that measure lives on Opportunities/,
    /^Sales Reps\[name\] isn't a column or measure/,
    /^Calendar\[month_start\] isn't a column or measure/,
    /contains DAX \("CALCULATE\("\)/,
  ]) {
    assert.ok(problems.some((p) => expected.test(p)), `caught ${expected}`);
  }
});

test("the prompt's example is the starter report as deployed", () => {
  const spec = starterReportSpec();
  const visuals = spec.pages.flatMap((page) => page.visuals);
  const deployed = starterReportVisuals();
  assert.deepEqual(visuals.map((v) => v.type), deployed.map((v) => v.type));
  assert.deepEqual(visuals.filter((v) => v.title).map((v) => v.title), deployed.filter((v) => v.type !== 'cardVisual').map((v) => v.title));
  for (const visual of visuals) {
    const [x, y, width, height] = visual.position;
    assert.ok(x >= 0 && y >= 0 && x + width <= spec.pages[0].width && y + height <= spec.pages[0].height, `${visual.title || visual.type} fits the page`);
  }
});
