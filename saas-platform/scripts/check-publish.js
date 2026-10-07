#!/usr/bin/env node
// Checks the project before it's published: no credentials anywhere, and none of this deployment's identifiers.
//
//   npm run check:publish                      credentials, plus identifiers from DATA_DIR/tenants.json and .env
//   npm run check:publish -- --fix             replace those identifiers with placeholders (<fabrikam-workspace-id>)
//   npm run check:publish -- --settings <file> another settings file to take identifiers from (repeatable)
//   npm run check:publish -- --strict          also flag any GUID in documentation that isn't a placeholder
//
// Exit code 1 when something is found (after --fix: when credentials remain), so it can gate a commit or a pipeline.
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { dataDirOf } from '../src/config.js';
import { identifierLabels, projectFiles, replaceIdentifiers, scanProject } from '../src/util/publishing.js';

const { values: options } = parseArgs({ options: { fix: { type: 'boolean', default: false }, strict: { type: 'boolean', default: false }, settings: { type: 'string', multiple: true }, help: { type: 'boolean', short: 'h' } } });
if (options.help) {
  console.log('Usage: npm run check:publish [-- --fix] [--strict] [--settings <file>]...');
  process.exit(0);
}

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const registryFile = path.join(dataDirOf(process.env), 'tenants.json');
const local = path.join(root, '.data', 'tenants.json');
const registries = [registryFile, local].filter((f, i, all) => existsSync(f) && all.indexOf(f) === i);
const settingsFiles = [path.join(root, '.env'), ...(options.settings || [])].filter((f) => existsSync(f));

const labels = new Map();
for (const file of registries) for (const [k, v] of identifierLabels({ registry: JSON.parse(readFileSync(file, 'utf8')) })) labels.set(k, v);
for (const file of settingsFiles) for (const [k, v] of identifierLabels({ settings: readFileSync(file, 'utf8') })) if (!labels.has(k)) labels.set(k, v);
console.log(`Checking ${projectFiles(root).length} files for credentials${labels.size ? ` and ${labels.size} identifiers of this deployment (from ${[...registries, ...settingsFiles].map((f) => path.basename(f)).join(', ')})` : ''}.`);

if (options.fix && labels.size) {
  let changed = 0;
  for (const file of projectFiles(root)) {
    const text = readFileSync(file, 'utf8');
    const fixed = replaceIdentifiers(text, labels);
    if (fixed !== text) {
      writeFileSync(file, fixed);
      changed += 1;
      console.log(`  replaced identifiers in ${path.relative(root, file)}`);
    }
  }
  console.log(`${changed} file(s) changed.`);
}

const results = scanProject(root, labels, { strict: options.strict });
for (const { file, findings } of results) {
  for (const f of findings) console.log(`  ${f.kind === 'credential' ? 'CREDENTIAL' : 'identifier'}  ${file}:${f.line}  ${f.what}`);
}
const credentials = results.flatMap((r) => r.findings).filter((f) => f.kind === 'credential').length;
const identifiers = results.flatMap((r) => r.findings).filter((f) => f.kind === 'identifier').length;
if (credentials) console.log(`\n${credentials} credential(s) found. Remove them, and rotate each one: it has been exposed.`);
if (identifiers) console.log(`${identifiers} identifier(s) of this deployment found. Run with --fix to replace them with placeholders.`);
if (!credentials && !identifiers) console.log('Nothing found: ready to publish.');
process.exitCode = credentials || identifiers ? 1 : 0;
