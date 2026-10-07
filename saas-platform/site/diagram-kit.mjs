// Shared drawing helpers for the diagrams on the static page: colors, text, shapes, arrows and the simple
// drawings used where there is no official icon.
export const C = {
  ink: '#1F2328', muted: '#57606A', line: '#7D8590', soft: '#D0D7DE', white: '#FFFFFF',
  platform: '#1F5AA6', platformFill: '#E7F0FA', platformPanel: '#F6FAFE',
  fab: '#C55A11', fabFill: '#FDECE0', fabPanel: '#FFF8F2',
  con: '#2E7D32', conFill: '#E7F4EA', conPanel: '#F4FAF5',
  ms: '#5F5F5F', entra: '#0078D4', pbi1: '#F2C811', pbi2: '#E8A200', pbi3: '#C27A00',
  entraKey: '#1F5AA6', embedKey: '#0B8A8A', sql: '#0F6CBD', lake: '#0E8A6A', red: '#C62828', zone: '#EEF3F9', zoneText: '#8FA9CF',
};
export const FONT = `font-family="'Segoe UI', 'Helvetica Neue', Arial, sans-serif"`;
export const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// Text: one string or an array of lines.
export function text(x, y, value, { size = 13, weight = 400, fill = C.ink, anchor = 'start', lh = 1.3, italic = false } = {}) {
  const lines = Array.isArray(value) ? value : [value];
  const tspans = lines.map((line, i) => `<tspan x="${x}" dy="${i ? size * lh : 0}">${esc(line)}</tspan>`).join('');
  return `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}"${italic ? ' font-style="italic"' : ''}>${tspans}</text>`;
}
export const width = (s, size) => s.length * size * 0.56;
// A label on a light background, so it stays readable over lines.
export function label(x, y, value, { size = 12, fill = C.ink, weight = 400, anchor = 'middle', bg = C.white, pad = 4 } = {}) {
  const lines = Array.isArray(value) ? value : [value];
  const w = Math.max(...lines.map((l) => width(l, size))) + pad * 2;
  const h = lines.length * size * 1.3 + pad * 1.2;
  const left = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x - pad;
  return `<rect x="${left.toFixed(1)}" y="${(y - size - pad * 0.2).toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="4" fill="${bg}" opacity="0.94"/>` + text(x, y, lines, { size, fill, weight, anchor });
}
export const rect = (x, y, w, h, { rx = 10, fill = 'none', stroke = 'none', sw = 1, dash = null } = {}) =>
  `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"${dash ? ` stroke-dasharray="${dash}"` : ''}/>`;
export const pill = (x, y, value, { fill, stroke, color, size = 11 }) => {
  const w = width(value, size) + 16;
  return rect(x, y, w, size + 9, { rx: (size + 9) / 2, fill, stroke }) + text(x + 8, y + size + 2, value, { size, fill: color, weight: 600 });
};
export const badge = (x, y, n, color = C.platform) => `<circle cx="${x}" cy="${y}" r="12" fill="${color}"/>` + text(x, y + 4.5, String(n), { size: 13, weight: 700, fill: C.white, anchor: 'middle' });

// Arrows: a path with an arrowhead marker, solid or dashed.
export const MARKERS = (ids) =>
  ids.map(([id, color]) => `<marker id="${id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="${color}"/></marker>`).join('');
export const arrow = (d, { color = C.line, marker = 'a-gray', sw = 2, dash = null, both = false } = {}) =>
  `<path d="${d}" fill="none" stroke="${color}" stroke-width="${sw}"${dash ? ` stroke-dasharray="${dash}"` : ''} marker-end="url(#${marker})"${both ? ` marker-start="url(#${marker})"` : ''}/>`;

// ---------- Icons (simple, original drawings) ----------
export const person = (cx, cy, color, s = 1) =>
  `<g transform="translate(${cx} ${cy}) scale(${s})"><circle cx="0" cy="-11" r="8.5" fill="${color}"/><path d="M-15,17 C-15,4 -8,0 0,0 C8,0 15,4 15,17 Z" fill="${color}"/></g>`;
export const browser = (cx, cy, color = C.platform, w = 52, h = 38) => {
  const x = cx - w / 2, y = cy - h / 2;
  return `<g>${rect(x, y, w, h, { rx: 5, fill: C.white, stroke: color, sw: 2 })}<path d="M${x},${y + 9} H${x + w}" stroke="${color}" stroke-width="2"/>`
    + [0, 1, 2].map((i) => `<circle cx="${x + 6 + i * 6}" cy="${y + 4.6}" r="1.6" fill="${color}"/>`).join('')
    + `<rect x="${x + 6}" y="${y + 14}" width="${w * 0.45}" height="5" rx="2" fill="${color}" opacity="0.45"/><rect x="${x + 6}" y="${y + 23}" width="${w - 12}" height="4" rx="2" fill="${color}" opacity="0.25"/><rect x="${x + 6}" y="${y + 30}" width="${w * 0.6}" height="4" rx="2" fill="${color}" opacity="0.25"/></g>`;
};
// The web app: a window with a grid, as in Microsoft's embedding diagram.
export const webapp = (cx, cy, color = C.platform, w = 70, h = 52) => {
  const x = cx - w / 2, y = cy - h / 2;
  return `<g>${rect(x, y, w, h, { rx: 6, fill: color, stroke: color })}${rect(x + 6, y + 6, w - 12, h - 12, { rx: 2, fill: C.white })}`
    + `<path d="M${x + 6},${y + h / 2} H${x + w - 6} M${x + w / 2.2},${y + 6} V${y + h - 6} M${x + w / 2.2},${y + h / 2 - 9} H${x + w - 6}" stroke="${color}" stroke-width="2.5"/>`
    + [0, 1, 2].map((i) => `<circle cx="${x + w - 3}" cy="${y + 12 + i * 6}" r="1.4" fill="${C.white}"/>`).join('') + '</g>';
};
export const entra = (cx, cy, s = 1) =>
  `<g transform="translate(${cx} ${cy}) scale(${s})"><path d="M0,-30 L26,8 L0,30 L-26,8 Z" fill="#9BD0F5"/><path d="M0,-30 L26,8 L0,14 Z" fill="#46A3E6"/><path d="M0,-30 L-26,8 L0,14 Z" fill="#7BC0EE"/><path d="M-26,8 L0,30 L0,14 Z" fill="${C.entra}"/><path d="M26,8 L0,30 L0,14 Z" fill="#005A9E"/></g>`;
export const cloud = (cx, cy, fill, s = 1) =>
  `<g transform="translate(${cx} ${cy}) scale(${s})"><path d="M-30,14 C-42,14 -42,-6 -28,-6 C-28,-22 -6,-26 0,-12 C6,-24 28,-20 26,-4 C40,-4 40,14 28,14 Z" fill="${fill}"/></g>`;
// A service principal: a cloud with a certificate seal.
export const sp = (cx, cy, s = 1) =>
  `<g transform="translate(${cx} ${cy}) scale(${s})">${cloud(0, 0, '#3AA0E8')}<circle cx="0" cy="2" r="10" fill="#FFD43B" stroke="#E0A800" stroke-width="2"/><circle cx="0" cy="2" r="5" fill="#FFF3B0"/><path d="M-6,10 L-10,24 L-3,20 L0,26 L2,12 Z M6,10 L10,24 L3,20 L0,26 L-2,12 Z" fill="#2BB5A0"/></g>`;
export const key = (cx, cy, color, s = 1) =>
  `<g transform="translate(${cx} ${cy}) scale(${s})"><circle cx="0" cy="-12" r="9" fill="${color}"/><circle cx="0" cy="-14" r="3" fill="${C.white}"/><rect x="-3" y="-4" width="6" height="26" rx="2" fill="${color}"/><rect x="3" y="8" width="7" height="4" fill="${color}"/><rect x="3" y="15" width="5" height="4" fill="${color}"/></g>`;
export const powerbi = (cx, cy, s = 1) =>
  `<g transform="translate(${cx} ${cy}) scale(${s})"><rect x="-22" y="-2" width="13" height="26" rx="2" fill="${C.pbi1}"/><rect x="-6" y="-14" width="13" height="38" rx="2" fill="${C.pbi2}"/><rect x="10" y="-26" width="13" height="50" rx="2" fill="${C.pbi3}"/></g>`;
export const cylinder = (cx, cy, color, { w = 34, h = 36, wave = false } = {}) => {
  const x = cx - w / 2, y = cy - h / 2, ry = 6;
  return `<g><path d="M${x},${y + ry} V${y + h - ry} A${w / 2},${ry} 0 0 0 ${x + w},${y + h - ry} V${y + ry}" fill="${color}"/><ellipse cx="${cx}" cy="${y + ry}" rx="${w / 2}" ry="${ry}" fill="${C.white}" stroke="${color}" stroke-width="2"/>`
    + (wave ? `<path d="M${x + 5},${cy + 4} q${w / 8},-5 ${w / 4},0 t${w / 4},0 t${w / 4},0" fill="none" stroke="${C.white}" stroke-width="2"/>` : `<path d="M${x},${cy} A${w / 2},${ry} 0 0 0 ${x + w},${cy}" fill="none" stroke="${C.white}" stroke-width="1.5" opacity="0.7"/>`) + '</g>';
};
export const model = (cx, cy, color = C.platform) =>
  `<g><path d="M${cx},${cy - 13} L${cx - 14},${cy + 10} L${cx + 14},${cy + 10} Z" fill="none" stroke="${color}" stroke-width="2"/>`
  + [[0, -13], [-14, 10], [14, 10]].map(([dx, dy]) => `<circle cx="${cx + dx}" cy="${cy + dy}" r="6" fill="${color}"/>`).join('') + '</g>';
export const report = (cx, cy, color = C.platform) =>
  `<g>${rect(cx - 16, cy - 20, 32, 40, { rx: 3, fill: C.white, stroke: color, sw: 2 })}<rect x="${cx - 10}" y="${cy + 2}" width="5" height="12" fill="${C.pbi2}"/><rect x="${cx - 3}" y="${cy - 6}" width="5" height="20" fill="${C.pbi3}"/><rect x="${cx + 4}" y="${cy - 1}" width="5" height="15" fill="${C.pbi1}"/><rect x="${cx - 10}" y="${cy - 14}" width="20" height="3" rx="1" fill="${color}" opacity="0.5"/></g>`;
export const agent = (cx, cy, color = C.platform) =>
  `<g><path d="M${cx - 18},${cy - 14} h36 a4,4 0 0 1 4,4 v18 a4,4 0 0 1 -4,4 h-22 l-8,8 v-8 h-6 a4,4 0 0 1 -4,-4 v-18 a4,4 0 0 1 4,-4 z" fill="${color}"/><path d="M${cx},${cy - 9} l2.5,6 6,2 -6,2 -2.5,6 -2.5,-6 -6,-2 6,-2 z" fill="${C.white}"/></g>`;
export const noEntry = (cx, cy) => `<g><circle cx="${cx}" cy="${cy}" r="11" fill="${C.red}"/><rect x="${cx - 6.5}" y="${cy - 2}" width="13" height="4" fill="${C.white}"/></g>`;
export const lock = (cx, cy, color = C.lake) =>
  `<g><path d="M${cx - 6},${cy - 3} v-5 a6,6 0 0 1 12,0 v5" fill="none" stroke="${color}" stroke-width="2.4"/><rect x="${cx - 9}" y="${cy - 3}" width="18" height="14" rx="2" fill="${color}"/></g>`;
export const logoSquare = (x, y, letter, color) => rect(x, y, 30, 30, { rx: 7, fill: color }) + text(x + 15, y + 21, letter, { size: 17, weight: 700, fill: C.white, anchor: 'middle' });

// The SVG document. defs: extra definitions, such as the Fabric icon symbols; notice: a comment kept in the file,
// such as the icons' license.
export const svg = (w, h, title, desc, body, { defs = '', notice = '' } = {}) =>
  `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-labelledby="t d" ${FONT}>\n`
  + (notice ? `${notice}\n` : '')
  + `<title id="t">${esc(title)}</title>\n<desc id="d">${esc(desc)}</desc>\n`
  + `<defs>${MARKERS([['a-gray', C.line], ['a-blue', C.platform], ['a-teal', C.embedKey], ['a-fab', C.fab], ['a-con', C.con], ['a-red', C.red]])}`
  + `<pattern id="hatch" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="9" height="9" fill="#F7F9FC"/><line x1="0" y1="0" x2="0" y2="9" stroke="#E6ECF4" stroke-width="3"/></pattern>${defs}</defs>\n`
  + `<rect width="${w}" height="${h}" fill="${C.white}"/>\n${body}\n</svg>\n`;
