import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import { test } from 'node:test';
import { askForSecrets } from '../src/auth/runtime-secrets.js';
import { loadConfig } from '../src/config.js';

// Whoever runs the app is asked for credentials; nothing secret comes from (or goes to) a file in the project.

function terminal(answers) {
  const input = new PassThrough();
  input.end(answers.map((a) => `${a}\n`).join(''));
  const output = new PassThrough();
  let text = '';
  output.on('data', (chunk) => (text += chunk));
  return { input, output, interactive: true, shown: () => text };
}

const freshDataDir = () => mkdtempSync(path.join(os.tmpdir(), 'platform-prompt-'));
const SP = { FABRIC_AUTH_MODE: 'sp', AZURE_TENANT_ID: 'contoso.onmicrosoft.com', AZURE_CLIENT_ID: '11111111-2222-4333-8444-555555555555' };

test('demo mode asks nothing; without a terminal nothing is asked and the configuration says what is missing', async () => {
  const demo = terminal([]);
  assert.deepEqual(await askForSecrets({ FABRIC_AUTH_MODE: 'mock' }, demo), { FABRIC_AUTH_MODE: 'mock' });
  assert.equal(demo.shown(), '');

  const env = { ...SP, DATA_DIR: freshDataDir() };
  const unattended = await askForSecrets(env, { input: new PassThrough(), output: new PassThrough(), interactive: false });
  assert.deepEqual(unattended, { ...env, SESSION_SECRET: unattended.SESSION_SECRET });
  assert.throws(() => loadConfig(unattended), /needs a credential for the platform identity: MANAGED_IDENTITY_CLIENT_ID .*AZURE_CLIENT_CERTIFICATE_PATH .*AZURE_CLIENT_SECRET/);
});

test('the server asks for the platform credential, chooses a credential-store key, and makes a back-office key', async () => {
  const dataDir = freshDataDir();
  const io = terminal(['2', 'the-client-secret-value', 'too-short', 'a-long-enough-store-key', 'a-long-enough-store-key', '']);
  const env = await askForSecrets({ ...SP, DATA_DIR: dataDir }, { ...io, purpose: 'server' });
  assert.equal(env.AZURE_CLIENT_SECRET, 'the-client-secret-value');
  assert.equal(env.SECRETS_KEY, 'a-long-enough-store-key');
  assert.ok(env.ADMIN_KEY.length >= 32, 'a back-office key is made for the run');
  assert.ok(env.SESSION_SECRET.length >= 32);
  const shown = io.shown();
  assert.match(shown, /How does it sign in\?\n {2}1\. A certificate/);
  assert.match(shown, /It must be at least 16 characters/);
  assert.match(shown, new RegExp(`Back-office key for this run \\(shown once\\): ${env.ADMIN_KEY}`));
  assert.doesNotMatch(shown, /the-client-secret-value|a-long-enough-store-key/, 'what was typed is never echoed');
  const config = loadConfig(env);
  assert.equal(config.credential.type, 'secret');
  assert.equal(config.adminKey, env.ADMIN_KEY);
});

test('a certificate path can be given instead, and a stored key is asked for once, without confirming', async () => {
  const dataDir = freshDataDir();
  writeFileSync(path.join(dataDir, 'secrets.json'), '{"version":1,"salt":"AAAA","secrets":{}}');
  const io = terminal(['1', 'C:\\certs\\platform.pem', 'the-existing-store-key']);
  const env = await askForSecrets({ ...SP, DATA_DIR: dataDir, ADMIN_KEY: 'x'.repeat(32) }, { ...io, purpose: 'cli' });
  assert.equal(env.AZURE_CLIENT_CERTIFICATE_PATH, 'C:\\certs\\platform.pem');
  assert.equal(env.AZURE_CLIENT_SECRET, undefined);
  assert.equal(env.SECRETS_KEY, 'the-existing-store-key');
  assert.equal(env.SESSION_SECRET, undefined, 'the CLI makes no session key');
  assert.doesNotMatch(io.shown(), /Type it again/);
  assert.throws(() => loadConfig(env), /AZURE_CLIENT_CERTIFICATE_PATH: no file at/);
});

test('mismatched keys change nothing, settings from the environment are never asked for, and production makes no session key', async () => {
  const io = terminal(['2', 'secret', 'first-key-1234567890', 'second-key-123456789']);
  await assert.rejects(askForSecrets({ ...SP, DATA_DIR: freshDataDir() }, { ...io, purpose: 'cli' }), /don't match/);

  const quiet = terminal([]);
  const given = { ...SP, AZURE_CLIENT_SECRET: 's', SECRETS_KEY: 'k'.repeat(16), ADMIN_KEY: 'a'.repeat(32), SESSION_SECRET: 'b'.repeat(36), DATA_DIR: freshDataDir() };
  assert.deepEqual(await askForSecrets(given, quiet), given);
  assert.equal(quiet.shown(), '');

  const production = await askForSecrets({ ...given, APP_ENV: 'production', SESSION_SECRET: undefined, SECRETS_PROVIDER: 'keyvault' }, terminal([]));
  assert.equal(production.SESSION_SECRET, undefined, 'production needs a SESSION_SECRET shared by every instance');
});
