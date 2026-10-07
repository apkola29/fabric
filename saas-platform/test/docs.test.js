import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

// The documentation: shared diagrams stay identical, diagrams color owners consistently and keep to what Mermaid
// parses, every link between the documents resolves, and old names don't come back.

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const DOCS = readdirSync(ROOT).filter((f) => f.endsWith('.md'));
const read = (file) => readFileSync(path.join(ROOT, file), 'utf8').replace(/\r\n/g, '\n');
const diagrams = (file) => [...read(file).matchAll(/```mermaid\n([\s\S]*?)```/g)].map((m) => m[1]);
const withoutFences = (text) => text.replace(/^```[\s\S]*?^```/gm, '');

test('the README and ARCHITECTURE.md show the same who-owns-what and end-to-end diagrams', () => {
  for (const marker of ['%% Who owns what.', "%% One customer's data, end to end"]) {
    const [readme, architecture] = ['README.md', 'ARCHITECTURE.md'].map((f) => diagrams(f).filter((d) => d.includes(marker)));
    assert.equal(readme.length, 1, `README.md has one diagram marked "${marker}"`);
    assert.equal(architecture.length, 1, `ARCHITECTURE.md has one diagram marked "${marker}"`);
    assert.equal(readme[0], architecture[0], `the "${marker}" diagram differs between README.md and ARCHITECTURE.md`);
  }
});

test('the data integration add-on is documented, with its diagram, and linked from the README', () => {
  const addon = diagrams('DATA-INTEGRATION.md');
  assert.equal(addon.length, 1);
  for (const part of ['Data Factory pipeline', 'Spark notebooks', 'bronze', 'silver', 'gold', 'fabrikamsa']) assert.match(addon[0], new RegExp(part));
  assert.match(read('README.md'), /\[DATA-INTEGRATION\.md\]\(DATA-INTEGRATION\.md\)/);
});

test('IDENTITIES.md maps every identity across Entra tenants, and the other documents point at it', () => {
  const doc = read('IDENTITIES.md');
  const map = diagrams('IDENTITIES.md').filter((d) => d.includes('%% Where each identity lives.'));
  assert.equal(map.length, 1, 'one map of where each identity lives');
  for (const tenant of ["THE PLATFORM'S ENTRA TENANT", "FABRIKAM'S ENTRA TENANT", "CONTOSO'S ENTRA TENANT"]) assert.ok(map[0].includes(tenant), tenant);
  for (const identity of ['fabrikamsa', 'contososa', 'Workspace identity', 'Platform identity', 'sign-in app', 'fabrikamreader', 'contosoreader']) assert.ok(map[0].includes(identity), identity);
  assert.equal(diagrams('IDENTITIES.md').filter((d) => /^\s*sequenceDiagram/.test(d)).length, 3, 'work-account sign-in, calls to Fabric, the add-on');
  assert.match(doc, /## 8\. Checked, and to test/);
  // Connections: who owns each one, and who it signs in as, with each credential type as Fabric names it.
  const connections = diagrams('IDENTITIES.md').filter((d) => d.includes('%% Connections: who owns each one'));
  assert.equal(connections.length, 1, 'one diagram of the connections');
  for (const part of ['fabrikamsa', 'fabrikamreader', "Fabrikam's workspace identity", '"Workspace identity"', '"Service principal"', '"OAuth"', '"Basic or Windows"']) assert.ok(connections[0].includes(part), part);
  const section = doc.slice(doc.indexOf('## 4. Connections'), doc.indexOf('## 5.'));
  assert.match(section, /\| The semantic models' OneLake connection \(Direct Lake\) \| Built \| `fabrikamsa`/);
  // The reader is an identity, not a Fabric connector: the old names mustn't come back, before or after the rename.
  for (const file of DOCS) assert.doesNotMatch(read(file), /connector for (Fabrikam|Contoso)|(Customer|HiCRM|platform( app)?) connector/i, file);
  for (const file of ['README.md', 'DATA-INTEGRATION.md', 'REQUIREMENTS.md', 'FRAMEWORK.md', 'ARCHITECTURE.md']) assert.match(read(file), /\]\(IDENTITIES\.md(#[\w-]+)?\)/, `${file} links IDENTITIES.md`);
  // Each company has its own Entra tenant: no document may say otherwise again.
  for (const file of DOCS) assert.doesNotMatch(read(file), /only (one )?Entra tenant|one Entra tenant, the provider/i, file);
});

test('no document uses the old name HiCRM, except the PLAN.md finding that records the rename (F74)', () => {
  const problems = [];
  for (const file of DOCS) {
    read(file).split('\n').forEach((line, i) => {
      const at = line.search(/hicrm/i);
      if (at >= 0 && !(file === 'PLAN.md' && line.includes('F74'))) problems.push(`${file}:${i + 1}: ${line.slice(Math.max(0, at - 50), at + 50).trim()}`);
    });
  }
  assert.deepEqual(problems, []);
});

test('diagrams color each owner the same way everywhere and style every box they draw', () => {
  const palette = {};
  const problems = [];
  for (const file of DOCS) {
    for (const d of diagrams(file)) {
      for (const [, owner, style] of d.matchAll(/^\s*classDef (fabrikam|contoso|platform|microsoft) (.+)$/gm)) {
        palette[owner] ??= style;
        if (style !== palette[owner]) problems.push(`${file}: classDef ${owner} ${style}`);
      }
      // Without a style, a box falls back to Mermaid's default yellow, which reads as a fourth owner.
      if (/^\s*classDef (fabrikam|contoso|platform|customer) /m.test(d)) {
        const styled = new Set([...d.matchAll(/^\s*style (\w+) /gm)].map((m) => m[1]));
        for (const [, box] of d.matchAll(/^\s*subgraph (\w+)/gm)) if (!styled.has(box)) problems.push(`${file}: subgraph ${box} has no style`);
      }
    }
  }
  assert.deepEqual(problems, []);
  assert.deepEqual(Object.keys(palette).sort(), ['contoso', 'fabrikam', 'microsoft', 'platform']);
});

test('sequence diagram messages avoid the characters Mermaid misreads', () => {
  const problems = [];
  for (const file of DOCS) {
    for (const d of diagrams(file).filter((code) => /^\s*sequenceDiagram/.test(code))) {
      for (const line of d.split('\n')) {
        if (!/^\s*(Note\b|\w+\s*-{1,2}(>>|>|x|\))[+-]?\s*\w+\s*:)/.test(line)) continue;
        const message = line.slice(line.indexOf(':') + 1);
        if (message.includes(';') || /<(?!br\s*\/?>)/.test(message)) problems.push(`${file}: ${line.trim()}`);
      }
    }
  }
  assert.deepEqual(problems, []);
});

// GitHub's heading anchors: lower case, punctuation dropped, spaces to hyphens, repeats numbered.
function anchors(file) {
  const seen = new Map();
  const out = new Set();
  for (const [, heading] of withoutFences(read(file)).matchAll(/^#{1,6}\s+(.+)$/gm)) {
    const base = heading.trim().toLowerCase().replace(/[^\p{L}\p{N}\p{M}\s_-]/gu, '').replace(/\s/g, '-');
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    out.add(n ? `${base}-${n}` : base);
  }
  return out;
}

test('links between the documents point at files and headings that exist', () => {
  const problems = [];
  for (const file of DOCS) {
    for (const [, target] of withoutFences(read(file)).matchAll(/\]\(([^)\s]+)\)/g)) {
      if (/^(https?:|mailto:|\.\.\/)/.test(target)) continue;
      const [rel, anchor] = target.split('#');
      const linked = rel ? path.normalize(rel) : file;
      if (!existsSync(path.join(ROOT, linked))) { problems.push(`${file}: ${target} (no such file)`); continue; }
      if (anchor && linked.endsWith('.md') && !anchors(linked).has(anchor)) problems.push(`${file}: ${target} (no such heading)`);
    }
  }
  assert.deepEqual(problems, []);
});
