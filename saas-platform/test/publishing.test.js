import assert from 'node:assert/strict';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { identifierLabels, replaceIdentifiers, scanProject, scanText } from '../src/util/publishing.js';

// The project is meant to be published: it must hold no credentials, and its documentation no real environment's IDs.

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');

test('the project holds no credentials, and its documentation no IDs of a real environment', () => {
  const results = scanProject(ROOT, new Map(), { strict: true });
  assert.deepEqual(results.flatMap((r) => r.findings.map((f) => `${r.file}:${f.line} ${f.what}`)), []);
});

test('credentials are found wherever they are, and placeholders are left alone', () => {
  // Built here, so the source holds none of them.
  const secret = ['abc', '8Q~', 'x'.repeat(34)].join('');
  const key = ['-----BEGIN', 'PRIVATE', 'KEY-----'].join(' ');
  const jwt = ['eyJhbGciOiJSUzI1NiJ9', 'eyJhdWQiOiJodHRwczovL2V4YW1wbGUifQ', 'c2lnbmF0dXJlLXZhbHVlLXhvbw'].join('.');
  const github = ['ghp', '_', 'a'.repeat(36)].join('');
  const storage = `AccountKey=${'A'.repeat(40)}==`;
  const password = ['Password', '=', 'Sup3rS3cret!'].join('');
  const found = scanText([secret, key, jwt, github, storage, `Server=x;${password};`].join('\n')).map((f) => f.what);
  for (const what of ['Microsoft Entra client secret', 'private key', 'JSON Web Token (an access token)', 'GitHub token', 'storage account key or SAS signature', 'password in a connection string']) {
    assert.ok(found.includes(what), `finds a ${what}`);
  }
  assert.deepEqual(scanText('Password=<token>; AZURE_CLIENT_SECRET= ; client_secret: "" ; Pwd=$(secret)').map((f) => f.what), []);
});

test("a deployment's IDs become placeholders named after what they are, in full and as prefixes", () => {
  const registry = {
    tenants: {
      'aaaaaaaa-0000-4000-8000-000000000000': {
        id: '9f1c2d3e-4b5a-4c6d-8e7f-001122334455',
        name: 'Fabrikam',
        slug: 'fabrikam',
        identity: { appId: '1c2d3e4f-5a6b-4c7d-8e9f-112233445566', objectId: '2d3e4f5a-6b7c-4d8e-9fa0-223344556677' },
        fabric: { workspaceId: '3e4f5a6b-7c8d-4e9f-a0b1-334455667788', modelConnectionIdOwner: '1c2d3e4f-5a6b-4c7d-8e9f-112233445566' },
        activity: [{ message: 'Moved to capacity 4f5a6b7c-8d9e-4fa0-b1c2-445566778899' }],
      },
    },
  };
  const labels = identifierLabels({ registry, settings: 'AZURE_TENANT_ID=5a6b7c8d-9eaf-4b0c-91d2-556677889900\nAZURE_CLIENT_ID=6b7c8d9e-afb0-4c1d-a2e3-66778899aabb\n' });
  assert.equal(labels.get('1c2d3e4f-5a6b-4c7d-8e9f-112233445566'), '<fabrikam-service-account-app-id>', 'the service account names its app first');
  assert.equal(labels.get('3e4f5a6b-7c8d-4e9f-a0b1-334455667788'), '<fabrikam-workspace-id>');
  assert.equal(labels.get('4f5a6b7c-8d9e-4fa0-b1c2-445566778899'), '<id>', 'an ID only seen in a message');
  assert.equal(labels.get('5a6b7c8d-9eaf-4b0c-91d2-556677889900'), '<tenant-id>');
  assert.equal(labels.get('6b7c8d9e-afb0-4c1d-a2e3-66778899aabb'), '<platform-app-id>');

  const doc = 'Workspace `3e4f5a6b-7c8d-4e9f-a0b1-334455667788` (`3e4f5a6b…`), app 1c2d3e4f-…, tenant 5a6b7c8d..., hash 3e4f5a6bff stays.';
  assert.equal(scanText(doc, labels).length, 4);
  assert.equal(
    replaceIdentifiers(doc, labels),
    'Workspace `<fabrikam-workspace-id>` (`<fabrikam-workspace-id>`), app <fabrikam-service-account-app-id>, tenant <tenant-id>, hash 3e4f5a6bff stays.',
  );
  assert.equal(scanText(doc.replace(/`3e4f5a6b-7c8d-4e9f-a0b1-334455667788`/, 'none'), new Map(), { strict: true }).length, 0, 'prefixes alone are only known with labels');
  assert.equal(scanText('id 7c8d9eaf-b0c1-4d2e-b3f4-778899aabbcc', new Map(), { strict: true }).length, 1, 'strict mode flags any other GUID');
});
