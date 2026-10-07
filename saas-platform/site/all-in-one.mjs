// Diagram 3: all in one. A customer runs its own Fabric, from its data sources to reports and data agents.
// Shared drawing helpers come from diagram-kit.mjs and the official Fabric icons from fabric-icons.mjs.
// Run node site/diagrams.mjs to write the SVG files.
import { C, text, width, label, rect, pill, arrow, person, webapp, logoSquare, svg } from './diagram-kit.mjs';
import { iconDefs, icon, ICONS_NOTICE } from './fabric-icons.mjs';

const BAND = '#EAF6F2';
// Icon sizes: Fabric items, data sources and logos next to a heading.
const ITEM = 40, SOURCE = 32, LOGO = 22;
const ICONS = ['fabric', 'onelake', 'mirrored-database', 'data-pipeline', 'copy-job', 'dataflow-gen2', 'shortcut', 'sql-database',
  'warehouse', 'lakehouse', 'stored-procedure', 'notebook', 'semantic-model', 'report', 'data-agent', 'sql-server',
  'on-premises-database', 'folder', 'web-api', 'file', 'bucket', 'data-gateway'];

// A monochrome glyph, tinted with color.
const glyph = (concept, cx, cy, size, color = C.muted) => `<g color="${color}">${icon(concept, cx, cy, size)}</g>`;
// A Fabric item: the icon, its name and a line or two about it, centered under the icon.
const item = (cx, cy, art, title, sub = []) =>
  art + text(cx, cy + 36, title, { size: 12.5, weight: 700, anchor: 'middle' })
  + (sub.length ? text(cx, cy + 51, sub, { size: 11, fill: C.muted, anchor: 'middle', lh: 1.25 }) : '');
// A data source: the icon on the left, its name and a line about it on the right.
const source = (x, cy, art, title, sub) => art + text(x, cy - 2, title, { size: 12.5, weight: 600 }) + text(x, cy + 13, sub, { size: 11, fill: C.muted });

export function allInOne() {
  const W = 1280, H = 900;
  const p = [];
  p.push(text(24, 40, 'All in one: Contoso runs its own Fabric, from its data sources to reports and data agents', { size: 21, weight: 700 }));
  p.push(text(24, 64, 'An example of the all-in-one state: the CRM\'s operational data, the data platform and the reports are all in Contoso\'s environment, managed by Contoso.', { size: 13.5, fill: C.muted }));

  // Contoso's environment: everything in this diagram is Contoso's.
  p.push(rect(16, 84, 1248, 768, { rx: 16, fill: C.conPanel, stroke: C.con, sw: 1.5 }));
  p.push(logoSquare(32, 98, 'C', C.con));
  p.push(text(72, 112, 'Contoso\'s environment', { size: 15, weight: 700, fill: C.con }));
  p.push(text(72, 130, 'its own Microsoft Entra tenant, Fabric capacity and workspace, run by Contoso\'s IT', { size: 12, fill: C.muted }));

  // Sources, top to bottom in the order their paths into Fabric run, so no two arrows cross.
  p.push(text(32, 178, 'Contoso\'s data sources', { size: 13.5, weight: 700 }));
  const group = (y, h, title) => rect(32, y, 260, h, { rx: 10, fill: C.white, stroke: C.con, sw: 1 }) + text(46, y + 20, title, { size: 12, weight: 700, fill: C.con });

  p.push(group(192, 184, 'Operational CRM data'));
  p.push(source(92, 250, webapp(62, 250, C.con, 40, 30), 'CRM app', 'the platform app, for example'));
  p.push(arrow('M62,270 V314', { both: true }));
  p.push(text(72, 296, 'reads and writes', { size: 10.5, fill: C.muted }));
  p.push(source(92, 336, glyph('sql-server', 62, 336, SOURCE), 'Azure SQL Database', 'in Contoso\'s Azure'));

  p.push(group(392, 140, 'On Contoso\'s network'));
  p.push(source(92, 448, glyph('on-premises-database', 62, 448, SOURCE), 'SQL Server', 'on-premises databases'));
  p.push(source(92, 500, icon('folder', 62, 500, SOURCE), 'File shares', 'on-premises files'));

  p.push(group(548, 216, 'Cloud services'));
  p.push(source(92, 604, glyph('web-api', 62, 604, SOURCE), 'SaaS apps and REST APIs', 'third-party services'));
  p.push(source(92, 660, glyph('file', 62, 660, SOURCE), 'SharePoint and OneDrive', 'lists, files and folders'));
  p.push(source(92, 716, glyph('bucket', 62, 716, SOURCE), 'Azure Data Lake, Amazon S3', 'files in cloud storage'));

  // Into the gateway, drawn later on top of the workspace's edge.
  p.push(arrow('M228,448 C262,448 266,466 282,466'));
  p.push(arrow('M204,500 C252,500 266,482 282,482'));
  // Contoso's Fabric workspace.
  p.push(rect(320, 150, 928, 646, { rx: 14, fill: C.white, stroke: C.con, sw: 1.5 }));
  p.push(icon('fabric', 351, 169, LOGO));
  p.push(text(368, 174, 'Contoso\'s Fabric workspace', { size: 15, weight: 700, fill: C.con }));
  p.push(text(368, 192, 'Microsoft Fabric on Contoso\'s capacity: the data is stored once, in OneLake', { size: 12, fill: C.muted }));
  // Columns: ingestion, storage, transform, model, consume. Rows: the three paths through the storage layer.
  const A = 414, B = 594, T = 760, M = 905, E = 1050;
  const R1 = 320, R2 = 470, R3 = 620, RM = 545;
  [[A, '1. Ingestion'], [B, '2. Storage layer'], [T, '3. Transform'], [M, '4. Model'], [1110, '5. Consume / visualize']]
    .forEach(([x, t]) => p.push(text(x, 228, t, { size: 12.5, weight: 700, anchor: 'middle' })));
  p.push(rect(516, 240, 156, 540, { rx: 12, fill: BAND, stroke: C.lake, sw: 1.2, dash: '5 4' }));
  const lakeX = B - (LOGO + 6 + width('OneLake', 12.5)) / 2;
  p.push(icon('onelake', lakeX + LOGO / 2, 260, LOGO));
  p.push(text(lakeX + LOGO + 6, 264.5, 'OneLake', { size: 12.5, weight: 700, fill: C.lake }));
  p.push(text(B, 752, 'all as Delta tables', { size: 10.5, fill: C.muted, anchor: 'middle' }));

  p.push(rect(286, 454, 40, 40, { rx: 8, fill: C.white, stroke: C.soft, sw: 1 }));
  p.push(glyph('data-gateway', 306, 474, SOURCE));
  p.push(label(306, 512, 'data gateway', { size: 10.5, fill: C.muted }));

  // 1. Ingestion.
  p.push(arrow('M226,334 C300,334 330,310 390,310'));
  p.push(arrow('M330,460 C338,460 338,452 338,440 V362 C338,340 356,330 390,330'));
  p.push(arrow('M330,468 H360'));
  p.push(arrow('M262,604 C340,604 346,484 360,484'));
  p.push(arrow('M262,658 C330,658 344,610 390,610'));
  p.push(arrow('M282,714 C340,714 352,630 390,630'));
  p.push(arrow('M248,250 H478 C508,250 510,305 540,305 H570', { dash: '6 4' }));
  p.push(label(404, 254, 'or a SQL database in Fabric', { size: 10.5, fill: C.muted }));
  p.push(item(A, R1, icon('mirrored-database', A, R1, ITEM), 'Mirroring', ['Azure SQL, SQL Server', 'and more, near real time']));
  // Data Factory: pipelines, copy jobs and Dataflow Gen2, smaller and side by side, bottoms in line with the other items.
  const DF = 30;
  p.push(item(A, R2, ['data-pipeline', 'copy-job', 'dataflow-gen2'].map((c, i) => icon(c, A + (i - 1) * (DF + 5), R2 + (ITEM - DF) / 2, DF)).join(''),
    'Data Factory', ['pipelines, copy jobs', 'and Dataflow Gen2']));
  p.push(item(A, R3, icon('shortcut', A, R3, ITEM), 'Shortcuts', ['SharePoint, OneDrive,', 'ADLS, S3: no copy']));

  // 2. Storage layer: stored once, in OneLake.
  p.push(arrow('M438,328 H570'));
  p.push(arrow('M468,470 H574'));
  p.push(arrow('M468,480 C510,480 522,606 574,606'));
  p.push(arrow('M438,628 H574'));
  p.push(item(B, R1, icon('sql-database', B, R1, ITEM), 'Operational data', ['SQL database in Fabric,', 'mirrored databases']));
  p.push(item(B, R2, icon('warehouse', B, R2, ITEM), 'Warehouse', ['T-SQL tables']));
  p.push(item(B, R3, icon('lakehouse', B, R3, ITEM), 'Lakehouse', ['medallion architecture:', 'bronze, silver, gold']));

  // 3. Transformed into business tables, 4. modeled, 5. consumed.
  p.push(arrow('M676,470 H739', { both: true }));
  p.push(arrow('M676,620 H741', { both: true }));
  p.push(arrow('M618,318 C700,318 760,370 760,446'));
  p.push(item(T, R2, glyph('stored-procedure', T, R2, ITEM), 'Stored procedures', ['T-SQL in the warehouse']));
  p.push(item(T, R3, icon('notebook', T, R3, ITEM), 'Notebooks', ['Spark: clean, join', 'and shape']));
  p.push(arrow('M781,470 C826,470 838,532 881,532'));
  p.push(arrow('M779,620 C824,620 838,554 881,554'));
  p.push(label(M, 510, 'business tables', { size: 10.5, fill: C.muted }));
  p.push(item(M, RM, icon('semantic-model', M, RM, ITEM), 'Semantic model', ['Direct Lake on the', 'business tables, with', 'row-level security']));
  p.push(arrow('M929,532 C980,532 992,472 1026,472'));
  p.push(arrow('M929,554 C980,554 992,618 1026,618'));
  p.push(item(E, R2, icon('report', E, R2, ITEM), 'Reports', ['Power BI']));
  p.push(item(E, R3, icon('data-agent', E, R3, ITEM), 'Data agents', ['questions in', 'plain language']));
  p.push(arrow('M1074,472 C1120,472 1132,532 1150,532'));
  p.push(arrow('M1074,618 C1104,618 1112,550 1150,550'));
  p.push(person(1176, 540, C.con, 1.15));
  p.push(text(1176, 581, 'Contoso\'s people', { size: 12.5, weight: 700, anchor: 'middle' }));
  p.push(text(1176, 596, ['in Power BI, Teams,', 'Copilot or the CRM app'], { size: 11, fill: C.muted, anchor: 'middle', lh: 1.25 }));

  // Who runs it.
  p.push(text(32, 824, 'Contoso manages:', { size: 12.5, weight: 700, fill: C.con }));
  let x = 150;
  for (const value of ['its Entra tenant and sign-ins', 'Fabric capacity', 'workspace roles', 'gateway and connections', 'schedules and monitoring', 'row-level security']) {
    p.push(pill(x, 809, value, { fill: C.white, stroke: C.con, color: C.con, size: 11 }));
    x += width(value, 11) + 24;
  }
  p.push(text(24, 882, 'Compare the isolated pilot: there, the platform runs one workspace per company in the platform\'s tenant. Here, Contoso runs everything in its own.', { size: 12.5, fill: C.muted }));

  return svg(W, H, 'All in one: Contoso runs its own Fabric',
    'Contoso\'s environment, managed by Contoso. Sources: a CRM app (the platform app, for example) with its Azure SQL Database, or a SQL database in Fabric; SQL Server and file shares on Contoso\'s network, through an on-premises data gateway; SaaS apps and REST APIs, SharePoint and OneDrive, and Azure Data Lake or Amazon S3. Contoso\'s Fabric workspace works in five steps. 1. Ingestion: mirroring, Data Factory (pipelines, copy jobs and Dataflow Gen2) and shortcuts bring the data in. 2. Storage layer: OneLake stores it once, as operational data (a SQL database in Fabric, mirrored databases), a warehouse and a lakehouse with a medallion architecture (bronze, silver and gold), all as Delta tables. 3. Transform: stored procedures and notebooks shape it into business tables. 4. Model: a semantic model reads the business tables with Direct Lake and applies row-level security. 5. Consume / visualize: reports and data agents serve Contoso\'s people in Power BI, Teams, Copilot or the CRM app.',
    p.join('\n'), { defs: iconDefs(ICONS), notice: ICONS_NOTICE });
}
