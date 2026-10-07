import assert from 'node:assert/strict';
import { X509Certificate, createPublicKey, constants, verify } from 'node:crypto';
import { test } from 'node:test';
import { createSelfSignedCertificate, parseCertificateBundle } from '../src/auth/certificates.js';
import { certificateCredential, credentialFromStore, credentialLabel, storedCredential } from '../src/auth/credential-types.js';
import { createTokenProvider } from '../src/auth/tokens.js';
import { json, scriptedFetch } from './helpers.js';

// Service principal credentials, best first: federated (no secret anywhere), certificate, client secret.

const CONFIG = { authMode: 'sp', tenantId: 'contoso.onmicrosoft.com', clientId: '11111111-2222-4333-8444-555555555555', endpoints: { login: 'https://login.test' } };
const decode = (part) => JSON.parse(Buffer.from(part, 'base64url').toString('utf8'));

test('a self-signed certificate made here is a valid X.509 certificate whose key signs it', () => {
  const made = createSelfSignedCertificate({ commonName: 'HiCRM fabrikamsa', days: 365 });
  const certificate = new X509Certificate(made.bundle.slice(made.bundle.indexOf('-----BEGIN CERTIFICATE-----')));
  assert.equal(certificate.subject, 'CN=HiCRM fabrikamsa');
  assert.equal(certificate.verify(certificate.publicKey), true, 'self-signed');
  const parsed = parseCertificateBundle(made.bundle);
  assert.equal(parsed.thumbprintSha256, made.thumbprintSha256);
  assert.ok(Date.parse(parsed.notAfter) > Date.now() + 360 * 86_400_000);

  const other = createSelfSignedCertificate({ commonName: 'other' });
  const wrongKey = other.bundle.slice(0, other.bundle.indexOf('-----BEGIN CERTIFICATE-----')) + made.bundle.slice(made.bundle.indexOf('-----BEGIN CERTIFICATE-----'));
  assert.throws(() => parseCertificateBundle(wrongKey), /doesn't belong to the certificate/);
  assert.throws(() => parseCertificateBundle(made.bundle.slice(made.bundle.indexOf('-----BEGIN CERTIFICATE-----'))), /private key and a certificate/);
  // An encrypted key (its PEM label is built here, so no key header sits in the source).
  const encrypted = ['ENCRYPTED', 'PRIVATE', 'KEY'].join(' ');
  assert.throws(() => parseCertificateBundle(`-----BEGIN ${encrypted}-----\nAAAA\n-----END ${encrypted}-----\n` + made.bundle.slice(made.bundle.indexOf('-----BEGIN CERTIFICATE-----'))), /encrypted/);
});

test('a certificate signs a short client assertion (PS256, x5t#S256) and no secret is sent', async () => {
  const made = createSelfSignedCertificate({ commonName: 'HiCRM test' });
  const { fetchImpl, calls } = scriptedFetch([{ match: '/oauth2/v2.0/token', respond: json(200, { access_token: 'cert-token', expires_in: 3600, token_type: 'Bearer' }) }]);
  const tokens = createTokenProvider(CONFIG, { fetchImpl, credential: certificateCredential(made.bundle) });
  assert.equal(await tokens.getToken('https://analysis.windows.net/powerbi/api/.default'), 'cert-token');
  assert.equal(tokens.describe().credential, 'certificate');

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /^https:\/\/login\.test\/contoso\.onmicrosoft\.com\/oauth2\/v2\.0\/token/);
  const form = new URLSearchParams(String(calls[0].body));
  assert.equal(form.get('client_secret'), null);
  assert.equal(form.get('client_assertion_type'), 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer');
  const [header, payload, signature] = form.get('client_assertion').split('.');
  assert.equal(decode(header).alg, 'PS256');
  assert.equal(decode(header)['x5t#S256'], Buffer.from(made.thumbprintSha256, 'hex').toString('base64url'));
  const claims = decode(payload);
  assert.equal(claims.aud, 'https://login.test/contoso.onmicrosoft.com/oauth2/v2.0/token');
  assert.equal(claims.iss, CONFIG.clientId);
  assert.equal(claims.sub, CONFIG.clientId);
  assert.ok(claims.jti);
  assert.ok(claims.exp - claims.nbf <= 600, 'an assertion lives 10 minutes at most');
  const publicKey = createPublicKey(made.bundle.slice(made.bundle.indexOf('-----BEGIN CERTIFICATE-----')));
  assert.equal(
    verify('sha256', Buffer.from(`${header}.${payload}`), { key: publicKey, padding: constants.RSA_PKCS1_PSS_PADDING, saltLength: constants.RSA_PSS_SALTLEN_DIGEST }, Buffer.from(signature, 'base64url')),
    true,
    'signed with the certificate key',
  );
});

test('a federated credential sends the managed identity token as the assertion, fresh for each request', async () => {
  let asked = 0;
  const credential = { type: 'federated', source: 'managed identity', getAssertion: async () => `mi-token-${++asked}` };
  const { fetchImpl, calls } = scriptedFetch([{ match: '/oauth2/v2.0/token', respond: json(200, { access_token: 'fic-token', expires_in: 3600, token_type: 'Bearer' }) }]);
  const tokens = createTokenProvider(CONFIG, { fetchImpl, credential });
  assert.equal(await tokens.getToken('scope-a'), 'fic-token');
  assert.equal(await tokens.getToken('scope-b'), 'fic-token');
  const forms = calls.map((c) => new URLSearchParams(String(c.body)));
  assert.deepEqual(forms.map((f) => f.get('client_assertion')), ['mi-token-1', 'mi-token-2']);
  assert.ok(forms.every((f) => f.get('client_secret') === null));
  assert.equal(tokens.describe().credential, 'federated credential (managed identity)');
});

test('the credential store keeps typed credentials, reads older plain secrets, and a missing credential says what to do', async () => {
  const made = createSelfSignedCertificate({ commonName: 'stored' });
  const stored = storedCredential(certificateCredential(made.bundle));
  const back = credentialFromStore(stored);
  assert.equal(back.type, 'certificate');
  assert.equal(back.thumbprintSha256, made.thumbprintSha256);
  assert.deepEqual(credentialFromStore('plain-old-secret'), { type: 'secret', secret: 'plain-old-secret' });
  assert.deepEqual(credentialFromStore(storedCredential({ type: 'secret', secret: 's' })), { type: 'secret', secret: 's' });
  assert.equal(credentialFromStore(null), null);
  assert.throws(() => storedCredential({ type: 'federated' }), /isn't stored/);
  assert.equal(credentialLabel({ type: 'federated', source: 'token file' }), 'federated credential (workload identity token)');

  const tokens = createTokenProvider(CONFIG, { fetchImpl: async () => assert.fail('no request without a credential') });
  await assert.rejects(tokens.getToken('scope'), /no credential: give it a federated credential, a certificate or a client secret/);
});
