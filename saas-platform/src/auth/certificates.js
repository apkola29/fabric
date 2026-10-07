import { X509Certificate, createHash, createPrivateKey, createPublicKey, generateKeyPairSync, randomBytes, sign } from 'node:crypto';

// Certificate credentials for service principals: Microsoft recommends them over client secrets.
// https://learn.microsoft.com/power-bi/developer/embedded/embed-service-principal
//
// A credential is a PEM bundle: the private key and the X.509 certificate whose public key Microsoft Entra ID holds.
// MSAL signs a short-lived client assertion with the private key (PS256, x5t#S256), so the key itself never leaves.

const PEM = /-----BEGIN ([A-Z ]+)-----\r?\n([A-Za-z0-9+/=\r\n]+?)\r?\n?-----END \1-----/g;

// Splits a PEM bundle (as written by "az ad app credential reset --create-cert", or by createSelfSignedCertificate)
// and checks that the key belongs to the certificate. Returns what MSAL needs, plus facts worth recording.
export function parseCertificateBundle(bundle) {
  const blocks = [...String(bundle || '').matchAll(PEM)].map(([text, label]) => ({ label, text }));
  const keyBlock = blocks.find((b) => /PRIVATE KEY$/.test(b.label));
  const certBlock = blocks.find((b) => b.label === 'CERTIFICATE');
  if (!keyBlock || !certBlock) throw new Error('The certificate file must hold a private key and a certificate, both in PEM.');
  if (/ENCRYPTED/.test(keyBlock.label)) throw new Error('The private key is encrypted. Export it without a password, or keep it in Key Vault.');
  let key;
  let certificate;
  try {
    key = createPrivateKey(keyBlock.text);
    certificate = new X509Certificate(certBlock.text);
  } catch (error) {
    throw new Error(`The certificate file can't be read: ${error.message}`);
  }
  const fromKey = createPublicKey(key).export({ type: 'spki', format: 'der' });
  const fromCertificate = certificate.publicKey.export({ type: 'spki', format: 'der' });
  if (!fromKey.equals(fromCertificate)) throw new Error("The private key doesn't belong to the certificate.");
  return {
    privateKey: key.export({ type: 'pkcs8', format: 'pem' }),
    certificate: certBlock.text.replace(/\r\n/g, '\n').trim() + '\n',
    thumbprintSha256: certificate.fingerprint256.replace(/:/g, '').toLowerCase(),
    notAfter: new Date(certificate.validTo).toISOString(),
    subject: certificate.subject,
  };
}

// --- A minimal DER encoder, enough for one self-signed X.509 v3 certificate. ---
function length(n) {
  if (n < 0x80) return Buffer.from([n]);
  const bytes = [];
  for (let v = n; v > 0; v >>= 8) bytes.unshift(v & 0xff);
  return Buffer.from([0x80 | bytes.length, ...bytes]);
}
const tlv = (tag, ...parts) => {
  const content = Buffer.concat(parts);
  return Buffer.concat([Buffer.from([tag]), length(content.length), content]);
};
const sequence = (...parts) => tlv(0x30, ...parts);
function oid(dotted) {
  const [a, b, ...rest] = dotted.split('.').map(Number);
  const bytes = [40 * a + b];
  for (const value of rest) {
    const chunk = [value & 0x7f];
    for (let v = value >> 7; v > 0; v >>= 7) chunk.unshift((v & 0x7f) | 0x80);
    bytes.push(...chunk);
  }
  return tlv(0x06, Buffer.from(bytes));
}
function integer(buffer) {
  let i = 0;
  while (i < buffer.length - 1 && buffer[i] === 0) i++;
  const trimmed = buffer.subarray(i);
  return tlv(0x02, trimmed[0] & 0x80 ? Buffer.concat([Buffer.from([0]), trimmed]) : trimmed);
}
function time(date) {
  const iso = date.toISOString().replace(/[-:T]/g, '').slice(0, 14);
  // UTCTime until 2049, GeneralizedTime after (RFC 5280, 4.1.2.5).
  return date.getUTCFullYear() < 2050 ? tlv(0x17, Buffer.from(`${iso.slice(2)}Z`)) : tlv(0x18, Buffer.from(`${iso}Z`));
}
const name = (commonName) => sequence(tlv(0x31, sequence(oid('2.5.4.3'), tlv(0x0c, Buffer.from(commonName, 'utf8')))));
const SHA256_WITH_RSA = sequence(oid('1.2.840.113549.1.1.11'), Buffer.from([0x05, 0x00]));

const toPem = (label, der) => `-----BEGIN ${label}-----\n${der.toString('base64').match(/.{1,64}/g).join('\n')}\n-----END ${label}-----\n`;

// A new RSA key and a self-signed certificate for it, as one PEM bundle. Microsoft Entra ID only needs the public
// certificate (uploaded to the app registration); the bundle stays with the platform's credential store.
export function createSelfSignedCertificate({ commonName, days = 365, now = new Date() } = {}) {
  if (!commonName) throw new Error('A certificate needs a common name.');
  const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const serial = randomBytes(16);
  serial[0] &= 0x7f;
  const notBefore = new Date(now.getTime() - 5 * 60_000);
  const notAfter = new Date(now.getTime() + days * 86_400_000);
  const tbs = sequence(
    tlv(0xa0, integer(Buffer.from([2]))),
    integer(serial),
    SHA256_WITH_RSA,
    name(commonName),
    sequence(time(notBefore), time(notAfter)),
    name(commonName),
    publicKey.export({ type: 'spki', format: 'der' }),
  );
  const der = sequence(tbs, SHA256_WITH_RSA, tlv(0x03, Buffer.from([0]), sign('sha256', tbs, privateKey)));
  const bundle = privateKey.export({ type: 'pkcs8', format: 'pem' }) + toPem('CERTIFICATE', der);
  return { bundle, certificateDer: der, thumbprintSha256: createHash('sha256').update(der).digest('hex'), notAfter: notAfter.toISOString() };
}
