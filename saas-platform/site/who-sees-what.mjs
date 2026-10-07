// Diagram 1: who sees what. Each company's people, its own workspace, and the data behind it.
// Shared drawing helpers come from diagram-kit.mjs, the official Fabric icons from fabric-icons.mjs.
// Run node site/diagrams.mjs to write the SVG files.
import { C, FONT, esc, text, width, label, rect, pill, badge, MARKERS, arrow, person, browser, webapp, sp, noEntry, logoSquare, svg } from './diagram-kit.mjs';
import { icon, iconDefs, ICONS_NOTICE } from './fabric-icons.mjs';

const ICONS = ['fabric', 'workspace', 'sql-database', 'onelake', 'semantic-model', 'report', 'data-agent'];

export function whoSeesWhat() {
  const W = 1280, H = 990;
  const parts = [];
  parts.push(text(24, 40, 'Who sees what: each company\'s people, its own workspace, and the data behind it', { size: 21, weight: 700 }));
  parts.push(text(24, 64, 'Isolated pilot: people sign in at their company\'s address. The platform app\'s customer-facing calls use that company\'s service principal, and each person sees only their rows.', { size: 13.5, fill: C.muted }));

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
  parts.push(text(24, 134, 'No account in the platform\'s tenant, no Power BI license', { size: 12, fill: C.muted }));
  parts.push(rect(392, 92, 290, 860, { rx: 14, fill: C.platformPanel, stroke: C.platform, sw: 1.5 }));
  parts.push(webapp(426, 120, C.platform, 40, 30));
  parts.push(text(456, 116, 'Platform app', { size: 15, weight: 700, fill: C.platform }));
  parts.push(text(456, 134, 'one deployment for every company', { size: 12, fill: C.muted }));
  parts.push(rect(708, 92, 556, 860, { rx: 14, fill: C.platformPanel, stroke: C.platform, sw: 1.5 }));
  parts.push(icon('fabric', 739, 111, 22));
  parts.push(text(758, 116, 'The platform\'s Microsoft Fabric', { size: 15, weight: 700, fill: C.platform }));
  parts.push(text(758, 134, 'in the platform\'s Entra tenant · one workspace per company, owned by the platform', { size: 12, fill: C.muted }));

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
    parts.push(label(379, top + 26, 'sign in', { size: 11, fill: co.color, weight: 600 }));
    parts.push(arrow(`M354,${top + 34} H404`, { color: co.color, marker }));

    // The app, for this company
    parts.push(rect(408, top, 258, 350, { rx: 10, fill: C.white, stroke: C.platform, sw: 1 }));
    parts.push(browser(436, top + 28, co.color, 40, 30));
    parts.push(text(466, top + 24, `${co.name}'s address`, { size: 13, weight: 700 }));
    parts.push(text(466, top + 40, `${co.key === 'fab' ? 'fabrikam' : 'contoso'}.platform… · logo and people`, { size: 11.5, fill: C.muted }));
    const rows = [['CRM pages', 'SQL, scoped to their states'], ['Reports', 'embed token with their role'], ['Assistant', 'chat with the data agent']];
    rows.forEach(([name, how], i) => {
      const y = top + [84, 184, 284][i];
      parts.push(rect(422, y - 22, 230, 44, { rx: 8, fill: C.platformFill, stroke: C.platform, sw: 1 }));
      parts.push(text(434, y - 4, name, { size: 13, weight: 700, fill: C.platform }));
      parts.push(text(434, y + 12, how, { size: 11.5, fill: C.ink }));
    });
    parts.push(sp(436, top + 134, 0.5));
    parts.push(text(458, top + 122, ['server: person, role, states', `app calls use ${co.sa},`, `${co.name}'s service principal`], { size: 11.5, fill: C.ink }));

    // The workspace
    const wx = 724, wy = top, ww = 524, wh = 350;
    parts.push(rect(wx, wy, ww, wh, { rx: 10, fill: C.white, stroke: C.platform, sw: 1.5 }));
    // Title with the workspace icon; the data pill sits under the title, clear of the service principal on the right.
    parts.push(icon('workspace', wx + 25, wy + 20, 22));
    parts.push(text(wx + 44, wy + 25, `${co.name}'s workspace`, { size: 14, weight: 700 }));
    parts.push(pill(wx + 44, wy + 34, `${co.name}'s data`, { fill: co.fill, stroke: co.color, color: co.color, size: 10.5 }));
    const admin = [`service principal ${co.sa}`, 'Admin of this workspace only'];
    parts.push(text(wx + ww - 14, wy + 20, admin, { size: 11.5, weight: 600, fill: C.platform, anchor: 'end', lh: 1.25 }));
    parts.push(sp(wx + ww - 14 - Math.max(...admin.map((l) => width(l, 11.5))) - 18, wy + 24, 0.45));
    const A = wx + 70, B = wx + 290; // the app's items on the left, what feeds them on the right
    const r1 = wy + 84, r2 = wy + 184, r3 = wy + 284;
    const M = { x: B - 30, y: r2 }; // the semantic model
    const under = (x, y, title, lines) => text(x, y + 36, title, { size: 13, weight: 600, anchor: 'middle' }) + text(x, y + 51, lines, { size: 11.5, fill: C.muted, anchor: 'middle', lh: 1.25 });
    // Inside the workspace: arrows stop a few px short of the 40px icons. Labels that sit beside an arrow are drawn
    // before it, and the icons after every label, so a label's background never covers an arrowhead or an icon.
    parts.push(label((A + B) / 2, r1 - 9, 'mirrors tables, near real time', { size: 11, fill: C.muted }));
    parts.push(arrow(`M${A + 24},${r1} H${B - 25}`, { color: C.line }));
    parts.push(arrow(`M${B - 8},${r1 + 24} L${M.x + 4},${M.y - 25}`, { color: C.line }));
    parts.push(label(B - 30, (r1 + r2) / 2 + 2, 'Direct Lake', { size: 11, fill: C.muted, anchor: 'end' }));
    parts.push(label((A + M.x) / 2, r2 - 22, ['the person\'s role', 'filters the rows'], { size: 11, fill: C.platform, weight: 600 }));
    parts.push(arrow(`M${M.x - 24},${r2} H${A + 25}`, { color: C.platform, marker: 'a-blue' }));
    parts.push(arrow(`M${M.x - 24},${M.y + 12} C${M.x - 60},${M.y + 18} ${A + 76},${r2 + 60} ${A + 28},${r3 - 8}`, { color: C.line }));
    parts.push(label(A + 74, r2 + 66, 'answers questions', { size: 11, fill: C.muted }));
    parts.push(icon('sql-database', A, r1, 40));
    parts.push(under(A, r1, 'SQL database', 'CRM records'));
    parts.push(icon('report', A, r2, 40));
    parts.push(under(A, r2, 'Report', 'Sales overview'));
    parts.push(icon('data-agent', A, r3, 40));
    parts.push(under(A, r3, 'Data agent', 'the app\'s Assistant'));
    parts.push(icon('onelake', B, r1, 40));
    parts.push(text(B + 28, r1 - 4, 'OneLake', { size: 13, weight: 600 }));
    parts.push(text(B + 28, r1 + 12, ['Delta tables, read with', 'workspace identity; SSO off'], { size: 11.5, fill: C.muted, lh: 1.25 }));
    parts.push(icon('semantic-model', M.x, M.y, 40));
    parts.push(text(M.x, M.y + 36, 'Semantic model', { size: 13, weight: 600, anchor: 'middle' }));
    parts.push(text(M.x, M.y + 51, ['roles: Texas,', 'New Mexico, Georgia,', 'All territories'], { size: 11, fill: C.platform, weight: 600, anchor: 'middle', lh: 1.25 }));
    // App to workspace
    [r1, r2, r3].forEach((y) => parts.push(arrow(`M652,${y} H${A - 25}`, { color: C.platform, marker: 'a-blue' })));
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
  parts.push(rect(352, lg - 11, 12, 12, { rx: 2, fill: C.platformFill, stroke: C.platform }) + text(370, lg, 'The platform, the SaaS provider: owns the platform app, the identities, the capacity and every workspace', { size: 12 }));
  return svg(W, H, 'Who sees what in the platform app', 'In the isolated pilot, Fabrikam\'s and Contoso\'s people sign in to the platform app at their company\'s address. Customer-facing platform app calls use that company\'s service principal, fabrikamsa or contososa, each Admin of its own workspace only. Fabric mirrors supported SQL tables to OneLake near real time; the semantic model reads through a workspace-identity connection with SSO off, and static territory roles filter the report. The data agent answers questions from the semantic model and appears in the app as the Assistant. Each rep sees their own state, each manager every state.', parts.join('\n'), { defs: iconDefs(ICONS), notice: ICONS_NOTICE });
}
