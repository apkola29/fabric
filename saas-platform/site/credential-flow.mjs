// Diagram 2: how credentials flow, from a person's sign-in to a report that shows only their rows.
// Shared drawing helpers come from diagram-kit.mjs and the official Fabric icons from fabric-icons.mjs.
// Run node site/diagrams.mjs to write the SVG files.
import { C, FONT, esc, text, width, label, rect, pill, badge, MARKERS, arrow, person, browser, webapp, entra, sp, key, model, report, agent, noEntry, logoSquare, svg } from './diagram-kit.mjs';
import { iconDefs, icon, ICONS_NOTICE } from './fabric-icons.mjs';

const ICON_NAMES = ['power-bi', 'onelake', 'lock', 'semantic-model'];
const PBI = 48; // both Power BI nodes
// The official lock glyph as a small badge on an icon's corner.
const lockBadge = (cx, cy, size, color) =>
  `<circle cx="${cx}" cy="${cy}" r="${size / 2}" fill="${C.white}"/><g color="${color}">${icon('lock', cx, cy, size)}</g>`;
// A label with a small official icon on its left, on one light background.
function iconLabel(x, y, concept, lines, { size = 11.5, iconSize = 22, gap = 6, pad = 4 } = {}) {
  const w = iconSize + gap + Math.max(...lines.map((l) => width(l, size)));
  const h = lines.length * size * 1.3 + pad * 1.2;
  const left = x - w / 2, top = y - size - pad * 0.2;
  return `<rect x="${(left - pad).toFixed(1)}" y="${top.toFixed(1)}" width="${(w + pad * 2).toFixed(1)}" height="${h.toFixed(1)}" rx="4" fill="${C.white}" opacity="0.94"/>`
    + icon(concept, left + iconSize / 2, top + h / 2, iconSize) + text(left + iconSize + gap, y, lines, { size, anchor: 'start' });
}

export function credentialFlow() {
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
  const S = { x: 640, y: 372 }; // the platform app's server
  parts.push(webapp(S.x, S.y));
  parts.push(text(S.x, S.y - 58, ['Platform app', 'server'], { size: 14, weight: 700, anchor: 'middle' }));
  const P = { x: 440, y: 212 }; // service principal
  parts.push(sp(P.x, P.y, 1.15));
  parts.push(text(P.x, P.y - 58, 'Service principal fabrikamsa', { size: 14, weight: 700, anchor: 'middle' }));
  parts.push(text(P.x, P.y - 41, 'certificate now · federation is also supported', { size: 11.5, fill: C.muted, anchor: 'middle' }));
  const E = { x: 168, y: 372 }; // Entra ID
  parts.push(entra(E.x, E.y));
  parts.push(text(E.x, E.y + 52, 'Microsoft Entra ID', { size: 14, weight: 700, anchor: 'middle' }));
  parts.push(text(E.x, E.y + 68, 'the platform\'s tenant', { size: 11.5, fill: C.muted, anchor: 'middle' }));
  const R = { x: 1110, y: 372 }; // Power BI REST API
  parts.push(icon('power-bi', R.x, R.y, PBI));
  parts.push(text(R.x, R.y + 46, 'Power BI REST API', { size: 14, weight: 700, anchor: 'middle' }));
  parts.push(text(R.x, R.y + 62, 'Generate Token V2', { size: 11.5, fill: C.muted, anchor: 'middle' }));
  const U = { x: 470, y: 700 }; // the person
  parts.push(person(U.x, U.y, C.fab, 1.5));
  parts.push(browser(U.x + 58, U.y + 4, C.fab, 44, 32));
  parts.push(text(U.x + 10, U.y + 52, 'Fabrikam\'s Texas rep', { size: 14, weight: 700, anchor: 'middle' }));
  parts.push(text(U.x + 10, U.y + 68, 'a browser, no Power BI user license needed', { size: 11.5, fill: C.muted, anchor: 'middle' }));
  const B = { x: 852, y: 700 }; // Power BI service
  parts.push(icon('power-bi', B.x, B.y - 6, PBI));
  parts.push(text(B.x, B.y + 44, 'Power BI service', { size: 14, weight: 700, anchor: 'middle' }));
  parts.push(text(B.x, B.y + 60, 'renders the report', { size: 11.5, fill: C.muted, anchor: 'middle' }));
  const O = { x: 1120, y: 700 }; // OneLake
  parts.push(icon('onelake', O.x, O.y - 6, 40));
  parts.push(lockBadge(O.x + 19, O.y + 9, 18, C.entra));
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
  parts.push(arrow(`M${S.x + 36},${S.y - 14} H${S.x + 60} V${S.y - 120} H${R.x + 10} V${R.y - 26}`, { color: C.line }));
  parts.push(badge(880, S.y - 120, 4));
  parts.push(label(896, S.y - 152, ['Generate Token V2: this report and model,', 'username drew.collins@fabrikam.com, role Texas'], { size: 11.5, anchor: 'start' }));
  // 5. The embed token
  parts.push(arrow(`M${R.x - 21},${R.y + 12} H${S.x + 40}`, { color: C.embedKey, marker: 'a-teal' }));
  parts.push(key(872, R.y + 10, C.embedKey, 1.1));
  parts.push(badge(980, R.y + 12, 5, C.embedKey));
  parts.push(label(872, R.y + 56, ['Embed token: report and model,', 'up to 30 min by default, role Texas'], { size: 11.5, fill: C.embedKey, weight: 600 }));
  // 6. To the browser
  parts.push(arrow(`M${S.x + 6},${S.y + 30} C${S.x + 20},${S.y + 150} ${U.x + 150},${U.y - 40} ${U.x + 86},${U.y - 16}`, { color: C.embedKey, marker: 'a-teal' }));
  parts.push(key(S.x + 32, S.y + 150, C.embedKey, 0.9));
  parts.push(badge(S.x + 4, S.y + 120, 6, C.embedKey));
  parts.push(label(S.x + 52, S.y + 154, ['Embed URL, embed token, metadata:', 'never the certificate or the Entra token'], { size: 11.5, anchor: 'start' }));
  // 7. The browser loads the report from Power BI
  parts.push(arrow(`M${U.x + 88},${U.y + 4} H${B.x - 21}`, { color: C.embedKey, marker: 'a-teal', both: true }));
  parts.push(badge(700, U.y + 4, 7, C.embedKey));
  parts.push(label(704, U.y - 30, ['powerbi-client loads the report', 'with the embed token'], { size: 11.5 }));
  // 8. Power BI reads OneLake
  parts.push(arrow(`M${B.x + 20},${B.y - 6} H${O.x - 23}`, { color: C.line }));
  parts.push(badge(986, B.y - 6, 8));
  parts.push(iconLabel(994, B.y - 40, 'semantic-model', ['Direct Lake: the Texas role', 'filters the rows']));

  // Below: the other calls made with the same sign-in
  parts.push(rect(24, H - 52, W - 48, 40, { rx: 8, fill: C.platformFill, stroke: C.platform }));
  parts.push(text(40, H - 27, 'Also as fabrikamsa, with tokens for other resources: the CRM pages read the SQL database (a SQL token), and managers\' questions go to the data agent over MCP (a Fabric token).', { size: 12.5 }));
  return svg(W, H, 'How credentials flow in the platform app', '1: the person signs in with a platform app password or local demo View as and gets a session cookie. 2: the server signs in to Entra ID as fabrikamsa with an assertion signed by its certificate; federation is also supported. 3: Entra ID returns an access token, kept on the server. 4: the server calls Generate Token V2 for one report and its model, with the person\'s email and RLS roles. 5: Power BI returns an embed token, requested for 30 minutes by default and capped by the Entra token\'s expiry. 6: the browser receives the embed URL, embed token and report metadata, never an app credential or Entra token. 7: the browser loads the report with that token. 8: Direct Lake reads OneLake through the fixed workspace-identity connection with SSO off; the model\'s roles filter the rows.', parts.join('\n'), { defs: iconDefs(ICON_NAMES), notice: ICONS_NOTICE });
}
