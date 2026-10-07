import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { jsonPart, textPart } from '../util/definition.js';
import { modelColumn, modelTableName } from './model.js';

// "Sales overview": the report every customer starts with when the platform has no template workspace. It's PBIR, in
// the shape Power BI itself saves for these visuals (schemas, query roles, sort and title objects, the base theme),
// bound to the customer's Platform app Insights model. Like any report on that model, it shows each viewer only the
// territories their embed token's row-level security roles allow.

export const STARTER_REPORT_NAME = 'Sales overview';
const SCHEMAS = 'https://developer.microsoft.com/json-schemas/fabric/item/report';
const BASE_THEME = 'Fluent2-CY26SU09';
const THEME_JSON = readFileSync(new URL(`./report-assets/${BASE_THEME}.json`, import.meta.url), 'utf8');
const PAGE = 'a1f3c5e7090b2d4f6a8c';

const literal = (value) => ({ expr: { Literal: { Value: value } } });
const quoted = (text) => literal(`'${text.replace(/'/g, "''")}'`);
const source = (table) => ({ Expression: { SourceRef: { Entity: modelTableName(table) } } });
const measure = (table, name) => ({ Measure: { ...source(table), Property: name } });
const column = (table, name) => ({ Column: { ...source(table), Property: modelColumn(table, name).model } });
const property = (field) => (field.Measure || field.Column).Property;
const projection = (field, extra = {}) => ({ field, queryRef: `${(field.Measure || field.Column).Expression.SourceRef.Entity}.${property(field)}`, nativeQueryRef: property(field), ...extra });

const PIPELINE = measure('opportunities', 'Pipeline Value');

// One 1280 x 720 page: the headline numbers, three pipeline breakdowns, the won-revenue trend and the accounts list.
// position: [x, y, width, height]. The headline row is one multi-value card, sized with the compact card recipe for a
// 720 px canvas (value 20 pt, label 11 pt, 82 px high).
const VISUALS = [
  {
    type: 'cardVisual',
    title: 'Headline numbers',
    data: [
      [PIPELINE, 'Pipeline'],
      [measure('opportunities', 'Won Revenue (ytd)'), 'Won this year'],
      [measure('opportunities', 'Win Rate'), 'Win rate'],
      [measure('opportunities', '# Open Opportunities'), 'Open deals'],
    ],
    position: [20, 20, 1240, 82],
  },
  { type: 'clusteredBarChart', title: 'Pipeline by state', category: column('accounts', 'state'), y: PIPELINE, position: [20, 122, 400, 280] },
  { type: 'clusteredBarChart', title: 'Pipeline by stage', category: column('opportunities', 'stage'), y: PIPELINE, position: [440, 122, 400, 280] },
  { type: 'clusteredBarChart', title: 'Pipeline by sales rep', category: column('sales_reps', 'name'), y: PIPELINE, position: [860, 122, 400, 280] },
  { type: 'lineChart', title: 'Won revenue by month', category: column('calendar', 'month_start'), y: measure('opportunities', 'Won Revenue'), timeline: true, position: [20, 422, 720, 278] },
  {
    type: 'tableEx',
    title: 'Accounts by pipeline',
    values: [column('accounts', 'name'), column('accounts', 'state'), [PIPELINE, 'Pipeline']],
    sortBy: PIPELINE,
    position: [760, 422, 500, 278],
  },
];

const CARD = { valueFont: 20, labelFont: 11, padding: 8 };
const idSelector = (properties) => [{ properties, selector: { id: 'default' } }];

// Stable 20-hex visual names, so the same report comes out every time.
const visualName = (title) => createHash('sha256').update(`${STARTER_REPORT_NAME}|${title}`).digest('hex').slice(0, 20);

// The headline card: one cardVisual with a callout per measure (role Data), each with a readable label.
function cardJson(spec) {
  return {
    visualType: 'cardVisual',
    query: { queryState: { Data: { projections: spec.data.map(([field, label]) => projection(field, { displayName: label })) } } },
    objects: {
      value: idSelector({ fontSize: literal(`${CARD.valueFont}D`) }),
      label: idSelector({ fontSize: literal(`${CARD.labelFont}D`) }),
      padding: idSelector({ paddingUniform: literal('8D') }),
      layout: idSelector({ paddingUniform: literal('0D') }),
    },
    visualContainerObjects: {
      padding: idSelector({ top: literal(`${CARD.padding}D`), bottom: literal(`${CARD.padding}D`), left: literal(`${CARD.padding}D`), right: literal(`${CARD.padding}D`) }),
      spacing: idSelector({ customizeSpacing: literal('true'), verticalSpacing: literal('2D') }),
    },
  };
}

function visualJson(spec, index) {
  const [x, y, width, height] = spec.position;
  const z = (index + 1) * 1000;
  const container = { $schema: `${SCHEMAS}/definition/visualContainer/2.13.0/schema.json`, name: visualName(spec.title), position: { x, y, z, height, width, tabOrder: z } };
  if (spec.type === 'cardVisual') return { ...container, visual: cardJson(spec) };
  // A value is a field, or [field, label] to show a shorter header.
  const valueProjection = (value) => (Array.isArray(value) ? projection(value[0], { displayName: value[1] }) : projection(value));
  const queryState = spec.category
    ? { Category: { projections: [projection(spec.category, { active: true })] }, Y: { projections: [projection(spec.y)] } }
    : { Values: { projections: spec.values.map(valueProjection) } };
  // Time runs left to right; everything else is ranked by its value, largest first.
  const sortField = spec.timeline ? spec.category : spec.sortBy || spec.y;
  const visual = {
    visualType: spec.type,
    query: { queryState, sortDefinition: { sort: [{ field: sortField, direction: spec.timeline ? 'Ascending' : 'Descending' }], isDefaultSort: true } },
    // The title says what the chart answers; Power BI's automatic subtitle would only repeat the field names.
    visualContainerObjects: { title: [{ properties: { show: literal('true'), text: quoted(spec.title) } }], subTitle: [{ properties: { show: literal('false') } }] },
    drillFilterOtherVisuals: true,
  };
  if (spec.type === 'tableEx') {
    visual.objects = { columnHeaders: [{ properties: { columnAdjustment: quoted('growToFit'), autoSizeColumnWidth: literal('true') } }] };
  }
  return { ...container, visual };
}

// The Fabric item definition (PBIR parts) for a customer's model. The binding is the API form: the model's ID only.
export function buildStarterReportDefinition({ semanticModelId }) {
  if (!semanticModelId) throw new Error('The starter report needs the semantic model ID.');
  const files = {
    'definition.pbir': {
      $schema: `${SCHEMAS}/definitionProperties/2.0.0/schema.json`,
      version: '4.0',
      datasetReference: { byConnection: { connectionString: `semanticmodelid=${semanticModelId}` } },
    },
    'definition/version.json': { $schema: `${SCHEMAS}/definition/versionMetadata/1.0.0/schema.json`, version: '2.0.0' },
    'definition/report.json': {
      $schema: `${SCHEMAS}/definition/report/3.3.0/schema.json`,
      themeCollection: { baseTheme: { name: BASE_THEME, reportVersionAtImport: { visual: '2.13.0', report: '3.4.0', page: '2.3.1' }, type: 'SharedResources' } },
      objects: { section: [{ properties: { verticalAlignment: quoted('Top') } }] },
      resourcePackages: [{ name: 'SharedResources', type: 'SharedResources', items: [{ name: BASE_THEME, path: `BaseThemes/${BASE_THEME}.json`, type: 'BaseTheme' }] }],
      settings: {
        useStylableVisualContainerHeader: true,
        exportDataMode: 'AllowSummarized',
        defaultDrillFilterOtherVisuals: true,
        allowChangeFilterTypes: true,
        useEnhancedTooltips: true,
        useDefaultAggregateDisplayName: true,
      },
    },
    'definition/pages/pages.json': { $schema: `${SCHEMAS}/definition/pagesMetadata/1.1.0/schema.json`, pageOrder: [PAGE], activePageName: PAGE },
    [`definition/pages/${PAGE}/page.json`]: { $schema: `${SCHEMAS}/definition/page/2.1.0/schema.json`, name: PAGE, displayName: 'Overview', displayOption: 'FitToPage', height: 720, width: 1280 },
  };
  VISUALS.forEach((spec, index) => {
    const visual = visualJson(spec, index);
    files[`definition/pages/${PAGE}/visuals/${visual.name}/visual.json`] = visual;
  });
  const parts = [...Object.entries(files).map(([path, value]) => jsonPart(path, value)), textPart(`StaticResources/SharedResources/BaseThemes/${BASE_THEME}.json`, THEME_JSON)];
  return { definition: { parts }, files };
}

// What the starter report shows, for docs and tests.
export const starterReportVisuals = () => VISUALS.map((v) => ({ type: v.type, title: v.title }));
