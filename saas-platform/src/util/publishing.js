import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';

// Before publishing this project (or notes about a deployment of it), make sure nothing in it is a credential or
// identifies a real environment. `npm run check:publish` runs this over the project:
//   - credentials, always: client secrets, private keys, access tokens, storage keys, GitHub tokens;
//   - this deployment's identifiers, when its registry and settings are around: every GUID in DATA_DIR/tenants.json
//     and in the settings file (tenant, apps, workspaces, items, capacity), also as 8-character prefixes ("1a2b3c4d…").
// --fix replaces the identifiers with placeholders named after what they are (<fabrikam-workspace-id>). Credentials
// are never "fixed": remove them, then rotate them, because they were exposed.

const GUID = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi;
const IS_GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SKIP_DIRS = new Set(['node_modules', '.git', '.data']);
const TEXT = /\.(js|mjs|cjs|ts|json|md|ps1|psm1|sh|html|css|svg|tmdl|dax|pbir|txt|yml|yaml|example|env)$|^\.env|^\.gitignore$/i;
// Placeholder and documentation GUIDs that are fine anywhere (all zeros, test patterns, Microsoft's own app IDs).
const ALLOWED_GUIDS = /^(0{8}-0{4}-[0-9a-f]{4}-[0-9a-f]{4}-0{8}[0-9a-f]{4}|([0-9a-f])\2{7}-.*|00000003-0000-0000-c000-000000000000)$/i;

export const CREDENTIAL_PATTERNS = Object.freeze([
  // Microsoft Entra client secrets: three characters, a version digit and "Q~", then 31 to 34 more.
  { name: 'Microsoft Entra client secret', pattern: /(?<![A-Za-z0-9_~.-])[A-Za-z0-9_~.-]{3}\dQ~[A-Za-z0-9_~.-]{31,34}(?![A-Za-z0-9_~.-])/g },
  { name: 'private key', pattern: /-----BEGIN (?:RSA |EC |ENCRYPTED |OPENSSH )?PRIVATE KEY-----/g },
  { name: 'JSON Web Token (an access token)', pattern: /\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g },
  { name: 'storage account key or SAS signature', pattern: /AccountKey=[A-Za-z0-9+/=]{20,}|[?&]sig=[A-Za-z0-9%+/=]{20,}/g },
  { name: 'GitHub token', pattern: /\bgh[pousr]_[A-Za-z0-9]{30,}\b/g },
  { name: 'password in a connection string', pattern: /\b(?:Password|Pwd)=(?!\s*[;"'<{$]|\s*$)[^;"'\s]{6,}/gi },
]);

// The files a check covers: text files in the project, minus dependencies, git internals and local data.
export function projectFiles(root) {
  const files = [];
  (function walk(dir) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (SKIP_DIRS.has(entry.name)) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (TEXT.test(entry.name) && statSync(full).size < 5_000_000) files.push(full);
    }
  })(root);
  return files;
}

const kebab = (text) => String(text).replace(/Id$/, '').replace(/([a-z0-9])([A-Z])/g, '$1-$2').replace(/[^A-Za-z0-9]+/g, '-').toLowerCase().replace(/^-|-$/g, '');

// Names for a deployment's identifiers: from the tenant registry (by tenant and field) and a settings file (by name).
// The service account and the Fabric items name an ID first; IDs that only appear inside messages are just <id>.
export function identifierLabels({ registry = null, settings = '' } = {}) {
  const labels = new Map();
  const add = (guid, label) => {
    const key = guid.toLowerCase();
    if (!ALLOWED_GUIDS.test(key) && !labels.has(key)) labels.set(key, `<${label}>`);
  };
  const SETTING_NAMES = { AZURE_CLIENT_ID: 'platform-app-id', AZURE_TENANT_ID: 'tenant-id', FABRIC_CAPACITY_ID: 'capacity-id' };
  for (const line of String(settings).split(/\r?\n/)) {
    const match = /^\s*([A-Z0-9_]+)\s*=\s*(.*)$/.exec(line);
    if (!match) continue;
    for (const [guid] of match[2].matchAll(GUID)) add(guid, SETTING_NAMES[match[1]] || `${kebab(match[1].replace(/^AZURE_/, '').replace(/_ID$/, ''))}-id`);
  }
  for (const tenant of Object.values(registry?.tenants || {})) {
    const slug = kebab(tenant.slug || tenant.name || 'tenant');
    const visit = (value, keys) => {
      if (typeof value === 'string') {
        const named = keys.filter((k) => typeof k === 'string');
        const field = named.at(-1) || 'id';
        const parent = named.length > 1 ? named.at(-2) : '';
        const inText = !IS_GUID.test(value);
        for (const [guid] of value.matchAll(GUID)) {
          if (inText) continue;
          const owner = parent === 'identity' ? 'service-account' : parent && parent !== 'fabric' ? kebab(parent) : '';
          add(guid, `${[slug, owner, kebab(field)].filter(Boolean).join('-')}-id`);
        }
      } else if (Array.isArray(value)) value.forEach((v, i) => visit(v, [...keys, i]));
      else if (value && typeof value === 'object') for (const [k, v] of Object.entries(value)) visit(v, [...keys, k]);
    };
    // The most telling names first.
    if (tenant.identity) visit(tenant.identity, ['identity']);
    if (tenant.fabric) visit(tenant.fabric, ['fabric']);
    if (tenant.id && IS_GUID.test(tenant.id)) add(tenant.id, `${slug}-record-id`);
    visit(tenant, []);
  }
  // IDs that only appear inside messages (activity logs, notes): known, but with no field to name them by.
  for (const tenant of Object.values(registry?.tenants || {})) {
    for (const [guid] of JSON.stringify(tenant).matchAll(GUID)) add(guid, 'id');
  }
  return labels;
}

// Findings in one text: credentials (always), and identifiers from `labels` (full GUIDs and 8-character prefixes).
// `strict`: also any other GUID that doesn't look like a placeholder (for documentation, where IDs rarely belong).
export function scanText(text, labels = new Map(), { strict = false } = {}) {
  const findings = [];
  for (const { name, pattern } of CREDENTIAL_PATTERNS) {
    for (const match of text.matchAll(pattern)) findings.push({ kind: 'credential', what: name, at: match.index });
  }
  for (const match of text.matchAll(GUID)) {
    const label = labels.get(match[0].toLowerCase());
    if (label) findings.push({ kind: 'identifier', what: label, at: match.index });
    else if (strict && !ALLOWED_GUIDS.test(match[0]) && !/^[0-9a-f]{8}-0{4}-4000-8000-/i.test(match[0])) findings.push({ kind: 'identifier', what: 'a GUID that may identify an environment', at: match.index });
  }
  const prefixes = prefixPattern(labels);
  if (prefixes) for (const match of text.matchAll(prefixes)) findings.push({ kind: 'identifier', what: `${labelOfPrefix(labels, match[1])} (prefix)`, at: match.index });
  return findings;
}

// Replaces identifiers with their placeholders. Credentials are left for a person to remove.
export function replaceIdentifiers(text, labels) {
  let out = text.replace(GUID, (guid) => labels.get(guid.toLowerCase()) || guid);
  const prefixes = prefixPattern(labels);
  if (prefixes) out = out.replace(prefixes, (_, prefix) => labelOfPrefix(labels, prefix));
  return out;
}

function prefixPattern(labels) {
  const prefixes = [...new Set([...labels.keys()].map((g) => g.slice(0, 8)))];
  // An 8-character prefix on its own, optionally followed by an ellipsis ("1a2b3c4d…", "1a2b3c4d-…", "1a2b3c4d...").
  return prefixes.length ? new RegExp(`(?<![0-9a-zA-Z-])(${prefixes.join('|')})(?:-?(?:…|\\.\\.\\.))?(?![0-9a-zA-Z-])`, 'gi') : null;
}

function labelOfPrefix(labels, prefix) {
  const matches = [...labels.entries()].filter(([guid]) => guid.startsWith(prefix.toLowerCase())).map(([, label]) => label);
  return matches.length === 1 ? matches[0] : '<id>';
}

export function scanProject(root, labels, { strict = false } = {}) {
  const results = [];
  for (const file of projectFiles(root)) {
    const text = readFileSync(file, 'utf8');
    // Documentation is checked strictly: an ID in prose is usually a real one.
    const findings = scanText(text, labels, { strict: strict && /\.md$/i.test(file) });
    if (findings.length) {
      const lineOf = (at) => text.slice(0, at).split('\n').length;
      results.push({ file: path.relative(root, file), findings: findings.map((f) => ({ ...f, line: lineOf(f.at) })) });
    }
  }
  return results;
}
