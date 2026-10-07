import { createHash } from 'node:crypto';

// Each customer's logo and accent color, shown on its own sign-in page, in the app's header and as the browser tab's
// icon, so people always know which company they're in. Logos are small (64 KB at most) and stored with the customer.
//
// An SVG is a document: it can run scripts and load other files. A logo is only accepted when it's plain drawing:
// listed drawing elements only, no event handlers, links only to its own parts, no styles or URLs that load
// anything. On top of that, the app only shows logos through <img> (which never runs scripts) and serves them with
// a sandbox policy, in case someone opens one directly.

export const LOGO_MAX_BYTES = 64 * 1024;
const COLOR = /^#[0-9a-f]{6}$/;
// The app's page background (--paper in public/app.css): the accent colors text on it.
const PAGE_BACKGROUND = '#f5f2ea';
const SVG_ELEMENTS = new Set([
  'svg', 'g', 'defs', 'symbol', 'use', 'title', 'desc', 'metadata',
  'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'text', 'tspan',
  'lineargradient', 'radialgradient', 'stop', 'clippath', 'mask', 'pattern',
  'filter', 'fegaussianblur', 'feoffset', 'feblend', 'fecolormatrix', 'feflood', 'fecomposite', 'femerge', 'femergenode', 'fedropshadow',
]);
// Editors (Inkscape, Illustrator) add their own namespaced elements; browsers ignore them.
const EDITOR_PREFIXES = new Set(['sodipodi', 'inkscape', 'rdf', 'cc', 'dc', 'i', 'x']);
export const SERVE_HEADERS = Object.freeze({
  'content-security-policy': "default-src 'none'; style-src 'unsafe-inline'; sandbox",
  'x-content-type-options': 'nosniff',
  'content-disposition': 'inline; filename="logo"',
});

function svgProblems(text) {
  const problems = [];
  if (!/^\s*(?:<\?xml[^>]*\?>\s*|<!--[\s\S]*?-->\s*|<!DOCTYPE[^[>]*(?:\[[\s\S]*?\])?\s*>\s*)*<svg[\s>]/i.test(text)) return ['it isn\'t an SVG document'];
  if (/<!DOCTYPE|<!ENTITY|<\?xml-stylesheet|<!\[CDATA\[/i.test(text)) problems.push('document type, entity or CDATA declarations');
  const elements = new Set();
  for (const [, name] of text.matchAll(/<([a-zA-Z][\w.:-]*)/g)) {
    const lower = name.toLowerCase();
    const prefix = lower.includes(':') ? lower.slice(0, lower.indexOf(':')) : null;
    if (prefix ? !EDITOR_PREFIXES.has(prefix) : !SVG_ELEMENTS.has(lower)) elements.add(`<${name}>`);
  }
  if (elements.size) problems.push(`elements a logo doesn't need: ${[...elements].slice(0, 5).join(', ')}`);
  if (/\son[a-z]+\s*=/i.test(text)) problems.push('event handlers (on... attributes)');
  const links = [...text.matchAll(/\b(?:xlink:)?href\s*=\s*(["']?)([^"'\s>]*)\1/gi)];
  if (links.some(([, quote, target]) => !quote || !target.startsWith('#'))) problems.push('links to other files (href)');
  if (/url\(\s*(?!["']?#)/i.test(text)) problems.push('url() references to other files');
  if (/javascript:|vbscript:|\bdata:|@import|expression\s*\(/i.test(text)) problems.push('script, data or import references');
  return problems;
}

// PNG, JPEG or WebP from the first bytes; null for anything else. SVG is never a raster: it can carry script.
export function rasterType(bytes) {
  if (bytes.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) return 'image/png';
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return 'image/jpeg';
  if (bytes.subarray(0, 4).toString('latin1') === 'RIFF' && bytes.subarray(8, 12).toString('latin1') === 'WEBP') return 'image/webp';
  return null;
}

// Bytes → a stored logo: { contentType, data (base64), sha256, bytes }. Throws a message an operator can act on.
export function parseLogo(input) {
  const bytes = Buffer.isBuffer(input) ? input : Buffer.from(input || '');
  if (!bytes.length) throw new Error('The logo file is empty.');
  if (bytes.length > LOGO_MAX_BYTES) throw new Error(`The logo is ${Math.ceil(bytes.length / 1024)} KB; logos can be at most ${LOGO_MAX_BYTES / 1024} KB.`);
  let contentType = rasterType(bytes);
  if (!contentType) {
    const text = bytes.toString('utf8').replace(/^\uFEFF/, '');
    const problems = svgProblems(text);
    if (problems.length) {
      throw new Error(problems[0] === 'it isn\'t an SVG document'
        ? 'Use an SVG, PNG, JPEG or WebP image as the logo.'
        : `This SVG can't be used as a logo because it has ${problems.join('; ')}. Export it as plain SVG (for example with SVGO) and try again.`);
    }
    contentType = 'image/svg+xml';
  }
  return { contentType, data: bytes.toString('base64'), sha256: createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length };
}

const channel = (hex, i) => {
  const c = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
};
const luminance = (hex) => 0.2126 * channel(hex, 0) + 0.7152 * channel(hex, 1) + 0.0722 * channel(hex, 2);
// WCAG 2 contrast ratio between two colors.
export function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}
const mix = (hex, other, amount) =>
  `#${[0, 1, 2].map((i) => Math.round(parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) * (1 - amount) + parseInt(other.slice(1 + i * 2, 3 + i * 2), 16) * amount).toString(16).padStart(2, '0')).join('')}`;

// '#RRGGBB' → lowercase, or null to clear. The accent colors links and button text on the page, so it must have at
// least 4.5:1 contrast with the page background (WCAG AA for text).
export function parseColor(value) {
  if (value === null || value === undefined || String(value).trim() === '') return null;
  const color = String(value).trim().toLowerCase();
  if (!COLOR.test(color)) throw new Error('Write the color as #RRGGBB, for example #3b3a98.');
  const ratio = contrast(color, PAGE_BACKGROUND);
  if (ratio < 4.5) throw new Error(`${color} is too light for links and buttons: it needs at least 4.5:1 contrast with the page, and has ${ratio.toFixed(1)}:1. Pick a darker shade.`);
  return color;
}

// The CSS custom properties that theme the app with a customer's color (see public/app.css).
export function themeOf(color) {
  if (!color) return null;
  let soft = mix(color, '#ffffff', 0.88);
  // Text in the accent sits on the soft shade too (hover, selected), so keep that readable as well.
  for (let amount = 0.9; contrast(color, soft) < 4.5 && amount < 0.98; amount += 0.02) soft = mix(color, '#ffffff', amount);
  return { '--accent': color, '--accent-hover': mix(color, '#000000', 0.18), '--accent-soft': soft };
}

// What anyone may know about a customer's branding: never the image bytes.
export function brandOf(tenant) {
  const branding = tenant.branding || {};
  const logo = branding.logo;
  return {
    color: branding.color || null,
    logo: logo ? { contentType: logo.contentType, bytes: logo.bytes, sha256: logo.sha256, updatedAt: logo.updatedAt || null } : null,
  };
}

// A versioned URL, so a new logo shows at once while an unchanged one stays cached.
export const logoUrl = (tenant, path) => (tenant.branding?.logo ? `${path}?v=${tenant.branding.logo.sha256.slice(0, 12)}` : null);

export function setLogo(tenant, bytes) {
  const logo = parseLogo(bytes);
  tenant.branding = { ...(tenant.branding || {}), logo: { ...logo, updatedAt: new Date().toISOString() } };
  return logo;
}

export function sendLogo(res, tenant) {
  const logo = tenant?.branding?.logo;
  if (!logo) return false;
  const body = Buffer.from(logo.data, 'base64');
  res.writeHead(200, {
    ...SERVE_HEADERS,
    'content-type': logo.contentType,
    'content-length': body.length,
    'cache-control': 'public, max-age=300',
    etag: `"${logo.sha256.slice(0, 32)}"`,
  });
  res.end(body);
  return true;
}
