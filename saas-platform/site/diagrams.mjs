// Draws the diagrams on the static page (site/index.html) as standalone SVG files: original drawings, with no
// external assets. Edit a diagram here, then run: node site/diagrams.mjs
import { writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const OUT = process.argv[2] || path.dirname(fileURLToPath(import.meta.url));
const C = {
  ink: '#1F2328', muted: '#57606A', line: '#7D8590', soft: '#D0D7DE', white: '#FFFFFF',
  hicrm: '#1F5AA6', hicrmFill: '#E7F0FA', hicrmPanel: '#F6FAFE',
  fab: '#C55A11', fabFill: '#FDECE0', fabPanel: '#FFF8F2',
  con: '#2E7D32', conFill: '#E7F4EA', conPanel: '#F4FAF5',
  ms: '#5F5F5F', entra: '#0078D4', pbi1: '#F2C811', pbi2: '#E8A200', pbi3: '#C27A00',
  entraKey: '#1F5AA6', embedKey: '#0B8A8A', sql: '#0F6CBD', lake: '#0E8A6A', red: '#C62828', zone: '#EEF3F9', zoneText: '#8FA9CF',
};
const FONT = `font-family="'Segoe UI', 'Helvetica Neue', Arial, sans-serif"`;
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// Text: one string or an array of lines.
function text(x, y, value, { size = 13, weight = 400, fill = C.ink, anchor = 'start', lh = 1.3, italic = false } = {}) {
  const lines = Array.isArray(value) ? value : [value];
  const tspans = lines.map((line, i) => `<tspan x="${x}" dy="${i ? size * lh : 0}">${esc(line)}</tspan>`).join('');
  return `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}"${italic ? ' font-style="italic"' : ''}>${tspans}</text>`;
}
const width = (s, size) => s.length * size * 0.56;
// A label on a light background, so it stays readable over lines.
function label(x, y, value, { size = 12, fill = C.ink, weight = 400, anchor = 'middle', bg = C.white, pad = 4 } = {}) {
  const lines = Array.isArray(value) ? value : [value];
  const w = Math.max(...lines.map((l) => width(l, size))) + pad * 2;
  const h = lines.length * size * 1.3 + pad * 1.2;
  const left = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x - pad;
  return `<rect x="${left.toFixed(1)}" y="${(y - size - pad * 0.2).toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="4" fill="${bg}" opacity="0.94"/>` + text(x, y, lines, { size, fill, weight, anchor });
}
const rect = (x, y, w, h, { rx = 10, fill = 'none', stroke = 'none', sw = 1, dash = null } = {}) =>
  `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"${dash ? ` stroke-dasharray="${dash}"` : ''}/>`;
const pill = (x, y, value, { fill, stroke, color, size = 11 }) => {
  const w = width(value, size) + 16;
  return rect(x, y, w, size + 9, { rx: (size + 9) / 2, fill, stroke }) + text(x + 8, y + size + 2, value, { size, fill: color, weight: 600 });
};
const badge = (x, y, n, color = C.hicrm) => `<circle cx="${x}" cy="${y}" r="12" fill="${color}"/>` + text(x, y + 4.5, String(n), { size: 13, weight: 700, fill: C.white, anchor: 'middle' });

// Arrows: a path with an arrowhead marker, solid or dashed.
const MARKERS = (ids) =>
  ids.map(([id, color]) => `<marker id="${id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="${color}"/></marker>`).join('');
const arrow = (d, { color = C.line, marker = 'a-gray', sw = 2, dash = null, both = false } = {}) =>
  `<path d="${d}" fill="none" stroke="${color}" stroke-width="${sw}"${dash ? ` stroke-dasharray="${dash}"` : ''} marker-end="url(#${marker})"${both ? ` marker-start="url(#${marker})"` : ''}/>`;

// ---------- Icons (simple, original drawings) ----------
const person = (cx, cy, color, s = 1) =>
  `<g transform="translate(${cx} ${cy}) scale(${s})"><circle cx="0" cy="-11" r="8.5" fill="${color}"/><path d="M-15,17 C-15,4 -8,0 0,0 C8,0 15,4 15,17 Z" fill="${color}"/></g>`;
const browser = (cx, cy, color = C.hicrm, w = 52, h = 38) => {
  const x = cx - w / 2, y = cy - h / 2;
  return `<g>${rect(x, y, w, h, { rx: 5, fill: C.white, stroke: color, sw: 2 })}<path d="M${x},${y + 9} H${x + w}" stroke="${color}" stroke-width="2"/>`
    + [0, 1, 2].map((i) => `<circle cx="${x + 6 + i * 6}" cy="${y + 4.6}" r="1.6" fill="${color}"/>`).join('')
    + `<rect x="${x + 6}" y="${y + 14}" width="${w * 0.45}" height="5" rx="2" fill="${color}" opacity="0.45"/><rect x="${x + 6}" y="${y + 23}" width="${w - 12}" height="4" rx="2" fill="${color}" opacity="0.25"/><rect x="${x + 6}" y="${y + 30}" width="${w * 0.6}" height="4" rx="2" fill="${color}" opacity="0.25"/></g>`;
};
// The web app: a window with a grid, as in Microsoft's embedding diagram.
const webapp = (cx, cy, color = C.hicrm, w = 70, h = 52) => {
  const x = cx - w / 2, y = cy - h / 2;
  return `<g>${rect(x, y, w, h, { rx: 6, fill: color, stroke: color })}${rect(x + 6, y + 6, w - 12, h - 12, { rx: 2, fill: C.white })}`
    + `<path d="M${x + 6},${y + h / 2} H${x + w - 6} M${x + w / 2.2},${y + 6} V${y + h - 6} M${x + w / 2.2},${y + h / 2 - 9} H${x + w - 6}" stroke="${color}" stroke-width="2.5"/>`
    + [0, 1, 2].map((i) => `<circle cx="${x + w - 3}" cy="${y + 12 + i * 6}" r="1.4" fill="${C.white}"/>`).join('') + '</g>';
};
const entra = (cx, cy, s = 1) =>
  `<g transform="translate(${cx} ${cy}) scale(${s})"><path d="M0,-30 L26,8 L0,30 L-26,8 Z" fill="#9BD0F5"/><path d="M0,-30 L26,8 L0,14 Z" fill="#46A3E6"/><path d="M0,-30 L-26,8 L0,14 Z" fill="#7BC0EE"/><path d="M-26,8 L0,30 L0,14 Z" fill="${C.entra}"/><path d="M26,8 L0,30 L0,14 Z" fill="#005A9E"/></g>`;
const cloud = (cx, cy, fill, s = 1) =>
  `<g transform="translate(${cx} ${cy}) scale(${s})"><path d="M-30,14 C-42,14 -42,-6 -28,-6 C-28,-22 -6,-26 0,-12 C6,-24 28,-20 26,-4 C40,-4 40,14 28,14 Z" fill="${fill}"/></g>`;
// A service principal: a cloud with a certificate seal.
const sp = (cx, cy, s = 1) =>
  `<g transform="translate(${cx} ${cy}) scale(${s})">${cloud(0, 0, '#3AA0E8')}<circle cx="0" cy="2" r="10" fill="#FFD43B" stroke="#E0A800" stroke-width="2"/><circle cx="0" cy="2" r="5" fill="#FFF3B0"/><path d="M-6,10 L-10,24 L-3,20 L0,26 L2,12 Z M6,10 L10,24 L3,20 L0,26 L-2,12 Z" fill="#2BB5A0"/></g>`;
const key = (cx, cy, color, s = 1) =>
  `<g transform="translate(${cx} ${cy}) scale(${s})"><circle cx="0" cy="-12" r="9" fill="${color}"/><circle cx="0" cy="-14" r="3" fill="${C.white}"/><rect x="-3" y="-4" width="6" height="26" rx="2" fill="${color}"/><rect x="3" y="8" width="7" height="4" fill="${color}"/><rect x="3" y="15" width="5" height="4" fill="${color}"/></g>`;
const powerbi = (cx, cy, s = 1) =>
  `<g transform="translate(${cx} ${cy}) scale(${s})"><rect x="-22" y="-2" width="13" height="26" rx="2" fill="${C.pbi1}"/><rect x="-6" y="-14" width="13" height="38" rx="2" fill="${C.pbi2}"/><rect x="10" y="-26" width="13" height="50" rx="2" fill="${C.pbi3}"/></g>`;
const cylinder = (cx, cy, color, { w = 34, h = 36, wave = false } = {}) => {
  const x = cx - w / 2, y = cy - h / 2, ry = 6;
  return `<g><path d="M${x},${y + ry} V${y + h - ry} A${w / 2},${ry} 0 0 0 ${x + w},${y + h - ry} V${y + ry}" fill="${color}"/><ellipse cx="${cx}" cy="${y + ry}" rx="${w / 2}" ry="${ry}" fill="${C.white}" stroke="${color}" stroke-width="2"/>`
    + (wave ? `<path d="M${x + 5},${cy + 4} q${w / 8},-5 ${w / 4},0 t${w / 4},0 t${w / 4},0" fill="none" stroke="${C.white}" stroke-width="2"/>` : `<path d="M${x},${cy} A${w / 2},${ry} 0 0 0 ${x + w},${cy}" fill="none" stroke="${C.white}" stroke-width="1.5" opacity="0.7"/>`) + '</g>';
};
const model = (cx, cy, color = C.hicrm) =>
  `<g><path d="M${cx},${cy - 13} L${cx - 14},${cy + 10} L${cx + 14},${cy + 10} Z" fill="none" stroke="${color}" stroke-width="2"/>`
  + [[0, -13], [-14, 10], [14, 10]].map(([dx, dy]) => `<circle cx="${cx + dx}" cy="${cy + dy}" r="6" fill="${color}"/>`).join('') + '</g>';
const report = (cx, cy, color = C.hicrm) =>
  `<g>${rect(cx - 16, cy - 20, 32, 40, { rx: 3, fill: C.white, stroke: color, sw: 2 })}<rect x="${cx - 10}" y="${cy + 2}" width="5" height="12" fill="${C.pbi2}"/><rect x="${cx - 3}" y="${cy - 6}" width="5" height="20" fill="${C.pbi3}"/><rect x="${cx + 4}" y="${cy - 1}" width="5" height="15" fill="${C.pbi1}"/><rect x="${cx - 10}" y="${cy - 14}" width="20" height="3" rx="1" fill="${color}" opacity="0.5"/></g>`;
const agent = (cx, cy, color = C.hicrm) =>
  `<g><path d="M${cx - 18},${cy - 14} h36 a4,4 0 0 1 4,4 v18 a4,4 0 0 1 -4,4 h-22 l-8,8 v-8 h-6 a4,4 0 0 1 -4,-4 v-18 a4,4 0 0 1 4,-4 z" fill="${color}"/><path d="M${cx},${cy - 9} l2.5,6 6,2 -6,2 -2.5,6 -2.5,-6 -6,-2 6,-2 z" fill="${C.white}"/></g>`;
const noEntry = (cx, cy) => `<g><circle cx="${cx}" cy="${cy}" r="11" fill="${C.red}"/><rect x="${cx - 6.5}" y="${cy - 2}" width="13" height="4" fill="${C.white}"/></g>`;
const lock = (cx, cy, color = C.lake) =>
  `<g><path d="M${cx - 6},${cy - 3} v-5 a6,6 0 0 1 12,0 v5" fill="none" stroke="${color}" stroke-width="2.4"/><rect x="${cx - 9}" y="${cy - 3}" width="18" height="14" rx="2" fill="${color}"/></g>`;
const logoSquare = (x, y, letter, color) => rect(x, y, 30, 30, { rx: 7, fill: color }) + text(x + 15, y + 21, letter, { size: 17, weight: 700, fill: C.white, anchor: 'middle' });

const svg = (w, h, title, desc, body) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-labelledby="t d" ${FONT}>\n`
  + `<title id="t">${esc(title)}</title>\n<desc id="d">${esc(desc)}</desc>\n`
  + `<defs>${MARKERS([['a-gray', C.line], ['a-blue', C.hicrm], ['a-teal', C.embedKey], ['a-fab', C.fab], ['a-con', C.con], ['a-red', C.red]])}`
  + `<pattern id="hatch" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="9" height="9" fill="#F7F9FC"/><line x1="0" y1="0" x2="0" y2="9" stroke="#E6ECF4" stroke-width="3"/></pattern></defs>\n`
  + `<rect width="${w}" height="${h}" fill="${C.white}"/>\n${body}\n</svg>\n`;

// ---------- Diagram 1: who sees what ----------
function whoSeesWhat() {
  const W = 1280, H = 990;
  const parts = [];
  parts.push(text(24, 40, 'Who sees what: each company\'s people, its own workspace, and the data behind it', { size: 21, weight: 700 }));
  parts.push(text(24, 64, 'Isolated pilot: people sign in at their company\'s address. HiCRM\'s customer-facing calls use that company\'s service principal, and each person sees only their rows.', { size: 13.5, fill: C.muted }));

  const companies = [
    {
      key: 'fab', name: 'Fabrikam', letter: 'F', domain: 'fabrikam.com', sa: 'fabrikamsa', top: 150, color: C.fab, fill: C.fabFill, panel: C.fabPanel,
      people: [['Leah Thompson', 'Sales manager · every state', 'All territories'], ['Drew Collins', 'Sales rep · Texas', 'Texas'], ['Arjun Mehta', 'Sales rep · New Mexico', 'New Mexico'], ['Amara Okoye', 'Sales rep · Georgia', 'Georgia']],
    },
    {
      key: 'con', name: 'Contoso', letter: 'C', domain: 'contoso.com', sa: 'contososa', top: 590, color: C.con, fill: C.conFill, panel: C.conPanel,
      people: [['Maria Alvarez', 'Sales manager · every state', 'All territories'], ['Sam Rivera', 'Sales rep · Texas', 'Texas'], ['Priya Nair', 'Sales rep · New Mexico', 'New Mexico'], ['Grace Kim', 'Sales rep · Georgia', 'Georgia']],
    },
  ];

  // Column headings
  parts.push(text(24, 116, 'The companies\' people', { size: 15, weight: 700 }));
  parts.push(text(24, 134, 'No account in HiCRM\'s tenant, no Power BI license', { size: 12, fill: C.muted }));
  parts.push(rect(392, 92, 290, 860, { rx: 14, fill: C.hicrmPanel, stroke: C.hicrm, sw: 1.5 }));
  parts.push(webapp(426, 120, C.hicrm, 40, 30));
  parts.push(text(456, 116, 'HiCRM web app', { size: 15, weight: 700, fill: C.hicrm }));
  parts.push(text(456, 134, 'one deployment for every company', { size: 12, fill: C.muted }));
  parts.push(rect(708, 92, 556, 860, { rx: 14, fill: C.hicrmPanel, stroke: C.hicrm, sw: 1.5 }));
  parts.push(text(728, 116, 'HiCRM\'s Microsoft Fabric', { size: 15, weight: 700, fill: C.hicrm }));
  parts.push(text(728, 134, 'in HiCRM\'s Entra tenant · one workspace per company, owned by HiCRM', { size: 12, fill: C.muted }));

  for (const co of companies) {
    const top = co.top;
    const marker = co.key === 'fab' ? 'a-fab' : 'a-con';
    // People
    parts.push(rect(24, top, 330, 350, { rx: 12, fill: co.panel, stroke: co.color, sw: 1.5 }));
    parts.push(logoSquare(40, top + 14, co.letter, co.color));
    parts.push(text(80, top + 27, co.name, { size: 16, weight: 700, fill: co.color }));
    parts.push(text(80, top + 43, `a customer · @${co.domain}`, { size: 12, fill: C.muted }));
    co.people.forEach(([name, role, rls], i) => {
      const y = top + 70 + i * 64;
      parts.push(person(58, y + 22, co.color, 0.9));
      parts.push(text(86, y + 14, name, { size: 14, weight: 600 }));
      parts.push(text(86, y + 31, role, { size: 12, fill: C.muted }));
      parts.push(pill(86, y + 38, `role: ${rls}`, { fill: co.fill, stroke: co.color, color: co.color, size: 10.5 }));
    });
    // People to the app
    parts.push(arrow(`M354,${top + 34} H404`, { color: co.color, marker }));
    parts.push(label(379, top + 26, 'sign in', { size: 11, fill: co.color, weight: 600 }));

    // The app, for this company
    parts.push(rect(408, top, 258, 350, { rx: 10, fill: C.white, stroke: C.hicrm, sw: 1 }));
    parts.push(browser(436, top + 28, co.color, 40, 30));
    parts.push(text(466, top + 24, `${co.name}'s address`, { size: 13, weight: 700 }));
    parts.push(text(466, top + 40, `${co.key === 'fab' ? 'fabrikam' : 'contoso'}.hicrm… · its logo, its people`, { size: 11.5, fill: C.muted }));
    const rows = [['CRM pages', 'SQL, scoped to their states'], ['Reports', 'embed token with their role'], ['Assistant', 'chat with the data agent']];
    rows.forEach(([name, how], i) => {
      const y = top + [84, 184, 284][i];
      parts.push(rect(422, y - 22, 230, 44, { rx: 8, fill: C.hicrmFill, stroke: C.hicrm, sw: 1 }));
      parts.push(text(434, y - 4, name, { size: 13, weight: 700, fill: C.hicrm }));
      parts.push(text(434, y + 12, how, { size: 11.5, fill: C.ink }));
    });
    parts.push(sp(436, top + 134, 0.5));
    parts.push(text(458, top + 122, ['server: person, role, states', `app calls use ${co.sa},`, `${co.name}'s service principal`], { size: 11.5, fill: C.ink }));

    // The workspace
    const wx = 724, wy = top, ww = 524, wh = 350;
    parts.push(rect(wx, wy, ww, wh, { rx: 10, fill: C.white, stroke: C.hicrm, sw: 1.5 }));
    parts.push(text(wx + 14, wy + 26, `${co.name}'s workspace`, { size: 14, weight: 700 }));
    parts.push(pill(wx + 14 + width(`${co.name}'s workspace`, 14) + 12, wy + 11, `${co.name}'s data`, { fill: co.fill, stroke: co.color, color: co.color, size: 10.5 }));
    const admin = [`service principal ${co.sa}`, 'Admin of this workspace only'];
    parts.push(text(wx + ww - 14, wy + 20, admin, { size: 11.5, weight: 600, fill: C.hicrm, anchor: 'end', lh: 1.25 }));
    parts.push(sp(wx + ww - 14 - Math.max(...admin.map((l) => width(l, 11.5))) - 18, wy + 24, 0.45));
    const A = wx + 70, B = wx + 290; // the app's items on the left, what feeds them on the right
    const r1 = wy + 84, r2 = wy + 184, r3 = wy + 284;
    const M = { x: B - 30, y: r2 }; // the semantic model
    const under = (x, y, title, lines) => text(x, y + 36, title, { size: 13, weight: 600, anchor: 'middle' }) + text(x, y + 51, lines, { size: 11.5, fill: C.muted, anchor: 'middle', lh: 1.25 });
    parts.push(cylinder(A, r1, C.sql));
    parts.push(under(A, r1, 'SQL database', 'CRM records'));
    parts.push(report(A, r2));
    parts.push(under(A, r2, 'Report', 'Sales overview'));
    parts.push(agent(A, r3));
    parts.push(under(A, r3, 'Data agent', 'the app\'s Assistant'));
    parts.push(cylinder(B, r1, C.lake, { wave: true }));
    parts.push(text(B + 26, r1 - 4, 'OneLake', { size: 13, weight: 600 }));
    parts.push(text(B + 26, r1 + 12, ['Delta tables, read with', 'workspace identity; SSO off'], { size: 11.5, fill: C.muted, lh: 1.25 }));
    parts.push(model(M.x, M.y));
    parts.push(text(M.x, M.y + 36, 'Semantic model', { size: 13, weight: 600, anchor: 'middle' }));
    parts.push(text(M.x, M.y + 51, ['roles: Texas,', 'New Mexico, Georgia,', 'All territories'], { size: 11, fill: C.hicrm, weight: 600, anchor: 'middle', lh: 1.25 }));
    // Inside the workspace
    parts.push(arrow(`M${A + 22},${r1} H${B - 24}`, { color: C.line }));
    parts.push(label((A + B) / 2, r1 - 9, 'mirrors tables, near real time', { size: 11, fill: C.muted }));
    parts.push(arrow(`M${B - 8},${r1 + 22} L${M.x + 4},${M.y - 20}`, { color: C.line }));
    parts.push(label(B - 30, (r1 + r2) / 2 + 2, 'Direct Lake', { size: 11, fill: C.muted, anchor: 'end' }));
    parts.push(arrow(`M${M.x - 22},${r2} H${A + 24}`, { color: C.hicrm, marker: 'a-blue' }));
    parts.push(label((A + M.x) / 2, r2 - 22, ['the person\'s role', 'filters the rows'], { size: 11, fill: C.hicrm, weight: 600 }));
    parts.push(arrow(`M${M.x - 22},${M.y + 12} C${M.x - 60},${M.y + 18} ${A + 76},${r2 + 60} ${A + 28},${r3 - 8}`, { color: C.line }));
    parts.push(label(A + 74, r2 + 66, 'answers questions', { size: 11, fill: C.muted }));
    // App to workspace
    [r1, r2, r3].forEach((y) => parts.push(arrow(`M652,${y} H${A - 26}`, { color: C.hicrm, marker: 'a-blue' })));
  }

  // Isolation between the companies
  parts.push(noEntry(744, 545));
  parts.push(text(764, 541, 'Each company\'s service principal has no role in the other company\'s workspace.', { size: 11.5, weight: 600, fill: C.red }));
  parts.push(text(764, 558, 'A call that mixes up the companies is refused by Fabric.', { size: 11.5, fill: C.ink }));
  parts.push(text(408, 540, ['A session works only at its', 'own company\'s address.'], { size: 12, fill: C.muted }));

  // Legend
  const lg = H - 14;
  parts.push(rect(24, lg - 11, 12, 12, { rx: 2, fill: C.fabFill, stroke: C.fab }) + text(42, lg, 'Fabrikam, a customer', { size: 12 }));
  parts.push(rect(190, lg - 11, 12, 12, { rx: 2, fill: C.conFill, stroke: C.con }) + text(208, lg, 'Contoso, a customer', { size: 12 }));
  parts.push(rect(352, lg - 11, 12, 12, { rx: 2, fill: C.hicrmFill, stroke: C.hicrm }) + text(370, lg, 'HiCRM, the SaaS provider: owns the app, the identities, the capacity and every workspace', { size: 12 }));
  return svg(W, H, 'Who sees what in HiCRM', 'In the isolated pilot, Fabrikam\'s and Contoso\'s people sign in to HiCRM at their company\'s address. Customer-facing HiCRM calls use that company\'s service principal, fabrikamsa or contososa, each Admin of its own workspace only. Fabric mirrors supported SQL tables to OneLake near real time; the semantic model reads through a workspace-identity connection with SSO off, and static territory roles filter the report. The data agent answers questions from the semantic model and appears in the app as the Assistant. Each rep sees their own state, each manager every state.', parts.join('\n'));
}

// ---------- Diagram 2: how credentials flow ----------
function credentialFlow() {
  const W = 1280, H = 840;
  const parts = [];
  parts.push(text(24, 40, 'How credentials flow: from a person\'s sign-in to a report that shows only their rows', { size: 21, weight: 700 }));
  parts.push(text(24, 64, 'Fabrikam\'s Texas rep opens Sales overview. Contoso\'s people go through the same steps, as contososa, in Contoso\'s workspace.', { size: 13.5, fill: C.muted }));

  // The two zones of Microsoft's embedding diagram
  parts.push(`<circle cx="360" cy="372" r="248" fill="url(#hatch)"/>`);
  parts.push(`<circle cx="922" cy="372" r="248" fill="url(#hatch)"/>`);
  parts.push(text(360, 112, 'Getting a Microsoft Entra token', { size: 24, fill: C.zoneText, anchor: 'middle' }));
  parts.push(text(922, 112, 'Generating an embed token', { size: 24, fill: C.zoneText, anchor: 'middle' }));

  // Nodes
  const S = { x: 640, y: 372 }; // HiCRM server
  parts.push(webapp(S.x, S.y));
  parts.push(text(S.x, S.y - 40, 'HiCRM server', { size: 14, weight: 700, anchor: 'middle' }));
  const P = { x: 440, y: 212 }; // service principal
  parts.push(sp(P.x, P.y, 1.15));
  parts.push(text(P.x, P.y - 58, 'Service principal fabrikamsa', { size: 14, weight: 700, anchor: 'middle' }));
  parts.push(text(P.x, P.y - 41, 'certificate now · federation is also supported', { size: 11.5, fill: C.muted, anchor: 'middle' }));
  const E = { x: 168, y: 372 }; // Entra ID
  parts.push(entra(E.x, E.y));
  parts.push(text(E.x, E.y + 52, 'Microsoft Entra ID', { size: 14, weight: 700, anchor: 'middle' }));
  parts.push(text(E.x, E.y + 68, 'HiCRM\'s tenant', { size: 11.5, fill: C.muted, anchor: 'middle' }));
  const R = { x: 1110, y: 372 }; // Power BI REST API
  parts.push(cloud(R.x, R.y, '#3AA0E8', 1.15));
  parts.push(`<circle cx="${R.x + 2}" cy="${R.y + 4}" r="7" fill="#6B3FA0"/><circle cx="${R.x + 2}" cy="${R.y + 4}" r="3" fill="${C.white}"/>`);
  parts.push(text(R.x, R.y + 46, 'Power BI REST API', { size: 14, weight: 700, anchor: 'middle' }));
  parts.push(text(R.x, R.y + 62, 'Generate Token V2', { size: 11.5, fill: C.muted, anchor: 'middle' }));
  const U = { x: 470, y: 700 }; // the person
  parts.push(person(U.x, U.y, C.fab, 1.5));
  parts.push(browser(U.x + 58, U.y + 4, C.fab, 44, 32));
  parts.push(text(U.x + 10, U.y + 52, 'Fabrikam\'s Texas rep', { size: 14, weight: 700, anchor: 'middle' }));
  parts.push(text(U.x + 10, U.y + 68, 'a browser, no Power BI user license needed', { size: 11.5, fill: C.muted, anchor: 'middle' }));
  const B = { x: 852, y: 700 }; // Power BI service
  parts.push(powerbi(B.x, B.y - 6));
  parts.push(text(B.x, B.y + 44, 'Power BI service', { size: 14, weight: 700, anchor: 'middle' }));
  parts.push(text(B.x, B.y + 60, 'renders the report', { size: 11.5, fill: C.muted, anchor: 'middle' }));
  const O = { x: 1120, y: 700 }; // OneLake
  parts.push(cylinder(O.x, O.y - 6, C.lake, { w: 44, h: 46, wave: true }));
  parts.push(lock(O.x + 26, O.y + 12));
  parts.push(text(O.x, O.y + 44, 'OneLake', { size: 14, weight: 700, anchor: 'middle' }));
  parts.push(text(O.x, O.y + 60, ['workspace identity connection', 'fixed identity; SSO is off'], { size: 11.5, fill: C.muted, anchor: 'middle' }));

  // 1. Sign in
  parts.push(arrow(`M500,660 C530,560 550,452 ${S.x - 22},${S.y + 30}`, { color: C.line }));
  parts.push(badge(545, 512, 1));
  parts.push(label(528, 500, ['Signs in at Fabrikam\'s address:', 'a session cookie'], { size: 11.5, anchor: 'end' }));
  // 2. Client credentials, through the service principal to Entra ID
  parts.push(arrow(`M${S.x - 36},${S.y - 14} C${S.x - 90},${S.y - 60} ${P.x + 90},${P.y + 20} ${P.x + 42},${P.y + 4}`, { color: C.line }));
  parts.push(badge(538, 278, 2));
  parts.push(arrow(`M${P.x - 40},${P.y} C${P.x - 140},${P.y} ${E.x + 10},${E.y - 110} ${E.x + 4},${E.y - 38}`, { color: C.line }));
  parts.push(badge(P.x - 150, P.y + 18, 2));
  parts.push(label(P.x - 168, P.y + 56, ['MSAL: an assertion signed with', 'fabrikamsa\'s certificate'], { size: 11.5, anchor: 'middle' }));
  // 3. The Entra token, to the server only
  parts.push(arrow(`M${E.x + 30},${E.y} H${S.x - 40}`, { color: C.entraKey, marker: 'a-blue' }));
  parts.push(key(388, E.y - 2, C.entraKey, 1.1));
  parts.push(badge(290, E.y, 3));
  parts.push(label(388, E.y + 42, ['Entra token', 'stays on the server'], { size: 11.5, fill: C.entraKey, weight: 600 }));
  // 4. Generate Token V2, with the person's effective identity
  parts.push(arrow(`M${S.x + 36},${S.y - 14} H${S.x + 60} V${S.y - 120} H${R.x} V${R.y - 30}`, { color: C.line }));
  parts.push(badge(880, S.y - 120, 4));
  parts.push(label(896, S.y - 152, ['Generate Token V2: this report and model,', 'username drew.collins@fabrikam.com, role Texas'], { size: 11.5, anchor: 'start' }));
  // 5. The embed token
  parts.push(arrow(`M${R.x - 40},${R.y + 12} H${S.x + 40}`, { color: C.embedKey, marker: 'a-teal' }));
  parts.push(key(872, R.y + 10, C.embedKey, 1.1));
  parts.push(badge(980, R.y + 12, 5, C.embedKey));
  parts.push(label(872, R.y + 56, ['Embed token: report and model,', 'up to 30 min by default, role Texas'], { size: 11.5, fill: C.embedKey, weight: 600 }));
  // 6. To the browser
  parts.push(arrow(`M${S.x + 6},${S.y + 30} C${S.x + 20},${S.y + 150} ${U.x + 150},${U.y - 40} ${U.x + 86},${U.y - 16}`, { color: C.embedKey, marker: 'a-teal' }));
  parts.push(key(S.x + 32, S.y + 150, C.embedKey, 0.9));
  parts.push(badge(S.x + 4, S.y + 120, 6, C.embedKey));
  parts.push(label(S.x + 52, S.y + 154, ['Embed URL, embed token, metadata:', 'never the certificate or the Entra token'], { size: 11.5, anchor: 'start' }));
  // 7. The browser loads the report from Power BI
  parts.push(arrow(`M${U.x + 88},${U.y + 4} H${B.x - 36}`, { color: C.embedKey, marker: 'a-teal', both: true }));
  parts.push(badge(690, U.y + 4, 7, C.embedKey));
  parts.push(label(690, U.y - 30, ['powerbi-client loads the report', 'with the embed token'], { size: 11.5 }));
  // 8. Power BI reads OneLake
  parts.push(arrow(`M${B.x + 34},${B.y - 6} H${O.x - 30}`, { color: C.line }));
  parts.push(badge(986, B.y - 6, 8));
  parts.push(label(986, B.y - 40, ['Direct Lake: the Texas role', 'filters the rows'], { size: 11.5 }));

  // Below: the other calls made with the same sign-in
  parts.push(rect(24, H - 52, W - 48, 40, { rx: 8, fill: C.hicrmFill, stroke: C.hicrm }));
  parts.push(text(40, H - 27, 'Also as fabrikamsa, with tokens for other resources: the CRM pages read the SQL database (a SQL token), and managers\' questions go to the data agent over MCP (a Fabric token).', { size: 12.5 }));
  return svg(W, H, 'How credentials flow in HiCRM', '1: the person signs in with a HiCRM password or local demo View as and gets a session cookie. 2: the server signs in to Entra ID as fabrikamsa with an assertion signed by its certificate; federation is also supported. 3: Entra ID returns an access token, kept on the server. 4: the server calls Generate Token V2 for one report and its model, with the person\'s email and RLS roles. 5: Power BI returns an embed token, requested for 30 minutes by default and capped by the Entra token\'s expiry. 6: the browser receives the embed URL, embed token and report metadata, never an app credential or Entra token. 7: the browser loads the report with that token. 8: Direct Lake reads OneLake through the fixed workspace-identity connection with SSO off; the model\'s roles filter the rows.', parts.join('\n'));
}

// ---------- Diagram 3: all in one, Contoso runs its own Fabric ----------
const F = { df: '#0078D4', mirror: '#0F6CBD', short: '#0E8A6A', wh: '#2B5797', nb: '#7A4FB0', agent: '#0F6CBD', model: '#1F5AA6', band: '#EAF6F2', sp: '#03787C', api: '#6E56CF' };

const folderIcon = (cx, cy, color) =>
  `<path d="M${cx - 17},${cy - 12} h11 l4,4 h19 a2,2 0 0 1 2,2 v18 a2,2 0 0 1 -2,2 h-34 a2,2 0 0 1 -2,-2 v-22 a2,2 0 0 1 2,-2 z" fill="${color}"/>`;
const pagesIcon = (cx, cy, color) =>
  rect(cx - 9, cy - 17, 24, 30, { rx: 3, fill: C.white, stroke: color, sw: 2 })
  + rect(cx - 15, cy - 11, 24, 30, { rx: 3, fill: color })
  + `<path d="M${cx - 10},${cy - 3} h14 M${cx - 10},${cy + 3} h14 M${cx - 10},${cy + 9} h9" stroke="${C.white}" stroke-width="2"/>`;
const apiIcon = (cx, cy, color) => cloud(cx + 1, cy + 3, color, 0.7) + text(cx, cy + 6, '</>', { size: 11, weight: 700, fill: C.white, anchor: 'middle' });
const gatewayIcon = (cx, cy, color) =>
  rect(cx - 16, cy - 14, 32, 28, { rx: 6, fill: color })
  + `<path d="M${cx - 8},${cy - 5} h15 m-4,-4 l4,4 l-4,4 M${cx + 8},${cy + 5} h-15 m4,-4 l-4,4 l4,4" fill="none" stroke="${C.white}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`;
const pipelineIcon = (cx, cy, color) =>
  [-16, 0, 16].map((dx) => rect(cx + dx - 6, cy - 9, 12, 18, { rx: 3, fill: color })).join('')
  + `<path d="M${cx - 10},${cy} h4 M${cx + 6},${cy} h4" stroke="${color}" stroke-width="3"/>`;
const ghostCylinder = (cx, cy, color, w, h) => {
  const x = cx - w / 2, y = cy - h / 2, ry = 4;
  return `<path d="M${x},${y + ry} V${y + h - ry} A${w / 2},${ry} 0 0 0 ${x + w},${y + h - ry} V${y + ry}" fill="${C.white}" stroke="${color}" stroke-width="2" stroke-dasharray="3 2"/>`
    + `<ellipse cx="${cx}" cy="${y + ry}" rx="${w / 2}" ry="${ry}" fill="${C.white}" stroke="${color}" stroke-width="2" stroke-dasharray="3 2"/>`;
};
const mirrorIcon = (cx, cy, color) =>
  cylinder(cx - 13, cy + 3, color, { w: 20, h: 28 }) + ghostCylinder(cx + 13, cy + 3, color, 20, 28)
  + `<path d="M${cx - 9},${cy - 15} q9,-8 18,0" fill="none" stroke="${color}" stroke-width="2"/><path d="M${cx + 5},${cy - 19} l5,5 l-7,1 z" fill="${color}"/>`;
const shortcutIcon = (cx, cy, color) =>
  rect(cx - 16, cy - 16, 32, 32, { rx: 7, fill: C.white, stroke: color, sw: 2 })
  + `<path d="M${cx - 7},${cy + 9} C${cx - 7},${cy - 1} ${cx - 2},${cy - 5} ${cx + 5},${cy - 5}" fill="none" stroke="${color}" stroke-width="2.6" stroke-linecap="round"/>`
  + `<path d="M${cx + 2},${cy - 11} L${cx + 9},${cy - 5} L${cx + 2},${cy + 1} Z" fill="${color}"/>`;
const lakehouseIcon = (cx, cy, color) =>
  `<path d="M${cx - 19},${cy - 3} L${cx},${cy - 19} L${cx + 19},${cy - 3} V${cy + 16} H${cx - 19} Z" fill="${color}"/>`
  + `<path d="M${cx - 12},${cy + 6} q3,-4 6,0 t6,0 t6,0 t6,0" fill="none" stroke="${C.white}" stroke-width="2"/>`;
const warehouseIcon = (cx, cy, color) =>
  `<path d="M${cx - 19},${cy - 6} L${cx},${cy - 18} L${cx + 19},${cy - 6} V${cy + 16} H${cx - 19} Z" fill="${color}"/>`
  + [0, 1, 2].map((i) => `<rect x="${cx - 11}" y="${cy - 2 + i * 6}" width="22" height="3.5" rx="1" fill="${C.white}" opacity="0.85"/>`).join('');
const notebookIcon = (cx, cy, color) =>
  rect(cx - 13, cy - 18, 30, 36, { rx: 3, fill: color })
  + [0, 1, 2, 3].map((i) => `<rect x="${cx - 18}" y="${cy - 14 + i * 8}" width="9" height="3.5" rx="1.75" fill="${C.white}" stroke="${color}" stroke-width="1.2"/>`).join('')
  + `<path d="M${cx - 5},${cy - 8} h16 M${cx - 5},${cy - 2} h16 M${cx - 5},${cy + 4} h11" stroke="${C.white}" stroke-width="2"/>`;
const procIcon = (cx, cy, color) =>
  rect(cx - 15, cy - 18, 30, 36, { rx: 3, fill: C.white, stroke: color, sw: 2 }) + text(cx, cy + 5, '{ }', { size: 14, weight: 700, fill: color, anchor: 'middle' });

// A Fabric item: the icon, its name and a line or two about it, centered under the icon.
const item = (cx, cy, icon, title, sub = []) =>
  icon + text(cx, cy + 36, title, { size: 12.5, weight: 700, anchor: 'middle' })
  + (sub.length ? text(cx, cy + 51, sub, { size: 11, fill: C.muted, anchor: 'middle', lh: 1.25 }) : '');
// A data source: the icon on the left, its name and a line about it on the right.
const source = (x, cy, icon, title, sub) => icon + text(x, cy - 2, title, { size: 12.5, weight: 600 }) + text(x, cy + 13, sub, { size: 11, fill: C.muted });

function allInOne() {
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
  p.push(source(92, 250, webapp(62, 250, C.con, 40, 30), 'CRM app', 'HiCRM, for example'));
  p.push(arrow('M62,270 V314', { both: true }));
  p.push(text(72, 296, 'reads and writes', { size: 10.5, fill: C.muted }));
  p.push(source(92, 336, cylinder(62, 336, C.sql, { w: 30, h: 32 }), 'Azure SQL Database', 'in Contoso\'s Azure'));

  p.push(group(392, 140, 'On Contoso\'s network'));
  p.push(source(92, 448, cylinder(62, 448, C.ms, { w: 28, h: 30 }), 'SQL Server', 'on-premises databases'));
  p.push(source(92, 500, folderIcon(62, 500, C.ms), 'File shares', 'on-premises files'));

  p.push(group(548, 216, 'Cloud services'));
  p.push(source(92, 604, apiIcon(62, 602, F.api), 'SaaS apps and REST APIs', 'third-party services'));
  p.push(source(92, 660, pagesIcon(62, 660, F.sp), 'SharePoint and OneDrive', 'lists, files and folders'));
  p.push(source(92, 716, folderIcon(62, 716, C.sql), 'Azure Data Lake, Amazon S3', 'files in cloud storage'));

  // Into the gateway, drawn later on top of the workspace's edge.
  p.push(arrow('M228,448 C262,448 268,468 286,470'));
  p.push(arrow('M204,500 C252,500 268,480 286,478'));
  // Contoso's Fabric workspace.
  p.push(rect(320, 150, 928, 646, { rx: 14, fill: C.white, stroke: C.con, sw: 1.5 }));
  p.push(text(340, 174, 'Contoso\'s Fabric workspace', { size: 15, weight: 700, fill: C.con }));
  p.push(text(340, 192, 'Microsoft Fabric on Contoso\'s capacity: the data is stored once, in OneLake', { size: 12, fill: C.muted }));
  const A = 414, B = 594, Cx = 760, D = 905, E = 1050;
  [[A, '1. Bring it in'], [B, '2. Store once, in OneLake'], [Cx, '3. Shape'], [D, '4. Model'], [1110, '5. Use']]
    .forEach(([x, t]) => p.push(text(x, 228, t, { size: 12.5, weight: 700, anchor: 'middle' })));
  p.push(rect(516, 240, 156, 540, { rx: 12, fill: F.band, stroke: C.lake, sw: 1.2, dash: '5 4' }));
  p.push(text(B, 752, 'all as Delta tables', { size: 10.5, fill: C.muted, anchor: 'middle' }));

  p.push(gatewayIcon(306, 474, C.ms));
  p.push(label(306, 508, 'data gateway', { size: 10.5, fill: C.muted }));

  // 1. Sources into Fabric.
  p.push(arrow('M226,334 C300,334 330,296 386,296'));
  p.push(arrow('M322,470 C352,470 352,306 386,306'));
  p.push(arrow('M322,478 C352,478 358,444 386,444'));
  p.push(arrow('M262,600 C330,600 344,452 386,452'));
  p.push(arrow('M262,658 C330,658 344,596 386,596'));
  p.push(arrow('M282,714 C340,714 352,606 386,606'));
  p.push(arrow('M214,250 H594 V278', { dash: '6 4' }));
  p.push(label(420, 254, 'or a SQL database in Fabric', { size: 10.5, fill: C.muted }));
  p.push(item(A, 300, mirrorIcon(A, 300, F.mirror), 'Mirroring', ['Azure SQL, SQL Server', 'and more, near real time']));
  p.push(item(A, 450, pipelineIcon(A, 450, F.df), 'Data Factory', ['pipelines, copy jobs', 'and Dataflow Gen2']));
  p.push(item(A, 600, shortcutIcon(A, 600, F.short), 'Shortcuts', ['SharePoint, OneDrive,', 'ADLS, S3: no copy']));

  // 2. Stored once, in OneLake.
  p.push(arrow('M440,300 H566'));
  p.push(arrow('M440,446 H566'));
  p.push(arrow('M440,456 C500,456 516,592 566,592'));
  p.push(arrow('M440,606 H566'));
  p.push(item(B, 300, cylinder(B, 300, C.sql, { w: 34, h: 36 }), 'Operational data', ['SQL database in Fabric,', 'mirrored databases']));
  p.push(item(B, 450, warehouseIcon(B, 450, F.wh), 'Warehouse', ['T-SQL tables']));
  p.push(item(B, 600, lakehouseIcon(B, 600, C.lake), 'Lakehouse', ['raw, cleaned and', 'business tables']));

  // 3. Shaped into business tables, 4. modeled, 5. used.
  p.push(arrow('M674,450 H736', { both: true }));
  p.push(arrow('M674,600 H736', { both: true }));
  p.push(arrow('M618,306 C684,306 704,428 740,438'));
  p.push(item(Cx, 450, procIcon(Cx, 450, F.wh), 'Stored procedures', ['T-SQL in the warehouse']));
  p.push(item(Cx, 600, notebookIcon(Cx, 600, F.nb), 'Notebooks', ['Spark: clean, join', 'and shape']));
  p.push(text(Cx, 700, ['Data Factory pipelines', 'run them on a schedule'], { size: 10.5, fill: C.muted, anchor: 'middle', italic: true }));
  p.push(arrow('M786,450 C840,450 852,518 881,518'));
  p.push(arrow('M786,600 C840,600 852,532 881,532'));
  p.push(label(D, 490, 'business tables', { size: 10.5, fill: C.muted }));
  p.push(item(D, 525, model(D, 525, F.model), 'Semantic model', ['Direct Lake on the', 'business tables, with', 'row-level security']));
  p.push(arrow('M927,518 C980,518 992,452 1028,452'));
  p.push(arrow('M927,532 C980,532 992,598 1028,598'));
  p.push(item(E, 450, report(E, 450, F.model), 'Reports', ['Power BI']));
  p.push(item(E, 600, agent(E, 600, F.agent), 'Data agents', ['questions in', 'plain language']));
  p.push(arrow('M1074,452 C1120,452 1132,512 1150,512'));
  p.push(arrow('M1076,598 C1120,598 1132,530 1150,530'));
  p.push(person(1176, 520, C.con, 1.15));
  p.push(text(1176, 561, 'Contoso\'s people', { size: 12.5, weight: 700, anchor: 'middle' }));
  p.push(text(1176, 576, ['in Power BI, Teams,', 'Copilot or the CRM app'], { size: 11, fill: C.muted, anchor: 'middle', lh: 1.25 }));

  // Who runs it.
  p.push(text(32, 824, 'Contoso manages:', { size: 12.5, weight: 700, fill: C.con }));
  let x = 150;
  for (const value of ['its Entra tenant and sign-ins', 'Fabric capacity', 'workspace roles', 'gateway and connections', 'schedules and monitoring', 'row-level security']) {
    p.push(pill(x, 809, value, { fill: C.white, stroke: C.con, color: C.con, size: 11 }));
    x += width(value, 11) + 24;
  }
  p.push(text(24, 882, 'Compare the isolated pilot: there, HiCRM runs one workspace per company in HiCRM\'s tenant. Here, Contoso runs everything in its own.', { size: 12.5, fill: C.muted }));

  return svg(W, H, 'All in one: Contoso runs its own Fabric',
    'Contoso\'s environment, managed by Contoso. Sources: a CRM app with its Azure SQL Database, or a SQL database in Fabric; SQL Server and file shares on Contoso\'s network, through an on-premises data gateway; SaaS apps and REST APIs, SharePoint and OneDrive, and cloud storage. In Contoso\'s Fabric workspace, mirroring, Data Factory and shortcuts bring the data into OneLake: operational and mirrored databases, a warehouse and a lakehouse, all as Delta tables. Stored procedures and notebooks shape it into business tables. A semantic model with row-level security reads them with Direct Lake and serves reports and data agents to Contoso\'s people.',
    p.join('\n'));
}

writeFileSync(path.join(OUT, 'who-sees-what.svg'), whoSeesWhat());
writeFileSync(path.join(OUT, 'credential-flow.svg'), credentialFlow());
writeFileSync(path.join(OUT, 'all-in-one.svg'), allInOne());
console.log('wrote who-sees-what.svg, credential-flow.svg and all-in-one.svg');
