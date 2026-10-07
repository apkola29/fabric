import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
// The one place that names what earlier versions deployed, so provisioning can find it and rename it.
const LEGACY_MODULE = 'src/platform/legacy-names.js';

const filesUnder = (dir) =>
  readdirSync(path.join(ROOT, dir), { withFileTypes: true }).flatMap((entry) => {
    const relative = `${dir}/${entry.name}`;
    return entry.isDirectory() ? filesUnder(relative) : [relative];
  });

test('the earlier product name is gone from the code, the UI and the deployment scripts, except the list of legacy names', () => {
  const files = [...filesUnder('src'), ...filesUnder('public'), ...filesUnder('scripts'), 'server.js', '.env.example'];
  assert.ok(files.includes(LEGACY_MODULE) && files.length > 50, 'the scan covers the source tree');
  const found = [];
  for (const file of files.filter((f) => f !== LEGACY_MODULE)) {
    if (/hicrm/i.test(file)) found.push(file);
    readFileSync(path.join(ROOT, file), 'latin1')
      .split('\n')
      .forEach((line, index) => /hicrm/i.test(line) && found.push(`${file}:${index + 1}: ${line.trim().slice(0, 120)}`));
  }
  assert.deepEqual(found, []);
  assert.match(readFileSync(path.join(ROOT, LEGACY_MODULE), 'utf8'), /hicrm/i, 'the legacy names are still there to find');
});
