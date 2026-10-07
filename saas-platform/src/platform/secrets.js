import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from 'node:crypto';
import { readJsonFile, writeFileAtomic } from '../util/files.js';

// Where the customer service accounts' credentials live.
//   keyvault  production: Azure Key Vault, read with the platform's own identity (ideally a managed identity)
//   file      development: one AES-256-GCM encrypted file, keyed by SECRETS_KEY (never stored next to it)
//   memory    tests
// Secret values never go into tenants.json, logs or API responses.

const KEY_VAULT_API = '7.4';
const KEY_VAULT_SCOPE = 'https://vault.azure.net/.default';
const NAME = /^[0-9a-zA-Z-]{1,127}$/;

function checkName(name) {
  if (!NAME.test(name)) throw new Error(`Invalid secret name "${name}".`);
  return name;
}

export function createMemorySecretStore(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    kind: 'memory',
    writable: true,
    async get(name) {
      return values.get(checkName(name)) ?? null;
    },
    async set(name, value) {
      values.set(checkName(name), String(value));
    },
    async delete(name) {
      values.delete(checkName(name));
    },
  };
}

export function createFileSecretStore({ file, key }) {
  const writable = Boolean(key && key.length >= 16);
  const empty = () => ({ version: 1, salt: randomBytes(16).toString('base64'), secrets: {} });
  let state = readJsonFile(file, null) || empty();
  let derived = null;
  // scrypt is deliberately slow; derive once per salt.
  const derive = () => {
    if (derived?.salt !== state.salt) derived = { salt: state.salt, key: scryptSync(key, Buffer.from(state.salt, 'base64'), 32) };
    return derived.key;
  };
  // Changes run one at a time and re-read the file first, so two customers registering at once can't drop a secret.
  let queue = Promise.resolve();
  const exclusive = (fn) => {
    const result = queue.catch(() => {}).then(fn);
    queue = result;
    return result;
  };

  async function persist() {
    await writeFileAtomic(file, JSON.stringify(state, null, 2));
  }

  return {
    kind: 'file',
    writable,
    async get(name) {
      const entry = state.secrets[checkName(name)];
      if (!entry || !writable) return null;
      const decipher = createDecipheriv('aes-256-gcm', derive(), Buffer.from(entry.iv, 'base64'));
      decipher.setAAD(Buffer.from(name));
      decipher.setAuthTag(Buffer.from(entry.tag, 'base64'));
      try {
        return Buffer.concat([decipher.update(Buffer.from(entry.data, 'base64')), decipher.final()]).toString('utf8');
      } catch {
        throw new Error(`Secret "${name}" can't be decrypted. SECRETS_KEY doesn't match the key it was stored with.`);
      }
    },
    async set(name, value) {
      checkName(name);
      if (!writable) throw new Error('Set SECRETS_KEY (16+ characters) so the platform can store service account secrets locally, or use SECRETS_PROVIDER=keyvault.');
      return exclusive(async () => {
        state = readJsonFile(file, null) || state;
        const iv = randomBytes(12);
        const cipher = createCipheriv('aes-256-gcm', derive(), iv);
        cipher.setAAD(Buffer.from(name));
        const data = Buffer.concat([cipher.update(String(value), 'utf8'), cipher.final()]);
        state.secrets[name] = { iv: iv.toString('base64'), tag: cipher.getAuthTag().toString('base64'), data: data.toString('base64'), at: new Date().toISOString() };
        await persist();
      });
    },
    async delete(name) {
      checkName(name);
      return exclusive(async () => {
        state = readJsonFile(file, null) || state;
        if (!state.secrets[name]) return;
        delete state.secrets[name];
        await persist();
      });
    },
  };
}

export function createKeyVaultSecretStore({ vaultUrl, tokens, fetchImpl = fetch }) {
  const base = String(vaultUrl || '').replace(/\/$/, '');
  if (!/^https:\/\/[a-z0-9-]+\.vault\.(azure\.net|azure\.cn|usgovcloudapi\.net)$/i.test(base)) throw new Error('KEY_VAULT_URL must look like https://<name>.vault.azure.net');

  async function call(method, name, body) {
    const res = await fetchImpl(`${base}/secrets/${checkName(name)}?api-version=${KEY_VAULT_API}`, {
      method,
      headers: { authorization: `Bearer ${await tokens.getToken(KEY_VAULT_SCOPE)}`, ...(body ? { 'content-type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 404) return null;
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(`Key Vault ${method} ${name} failed (HTTP ${res.status}): ${json?.error?.message || res.statusText}`);
    return json;
  }

  return {
    kind: 'keyvault',
    writable: true,
    async get(name) {
      return (await call('GET', name))?.value ?? null;
    },
    async set(name, value, { expiresOn } = {}) {
      await call('PUT', name, { value: String(value), contentType: 'hicrm/service-account-secret', ...(expiresOn ? { attributes: { exp: Math.floor(Date.parse(expiresOn) / 1000) } } : {}) });
    },
    async delete(name) {
      await call('DELETE', name);
    },
  };
}

export function createSecretStore(config, { tokens, fetchImpl } = {}) {
  const { provider, file, key, keyVaultUrl } = config.secrets;
  if (provider === 'memory') return createMemorySecretStore();
  if (provider === 'keyvault') return createKeyVaultSecretStore({ vaultUrl: keyVaultUrl, tokens, fetchImpl });
  return createFileSecretStore({ file, key });
}
