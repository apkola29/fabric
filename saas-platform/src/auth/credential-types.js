import { readFile } from 'node:fs/promises';
import { parseCertificateBundle } from './certificates.js';

// How a service principal proves who it is, best first:
//
//   federated    A token from the app's own user-assigned managed identity (or a workload identity token file, as in
//                Kubernetes) stands in for the credential: nothing is stored, and nothing expires or needs rotating.
//                The app registration trusts the managed identity through a federated identity credential.
//                https://learn.microsoft.com/entra/workload-id/workload-identity-federation-config-app-trust-managed-identity
//   certificate  A PEM bundle (private key and certificate). MSAL signs a 10-minute assertion with the key (PS256,
//                x5t#S256); Microsoft recommends certificates over secrets for embedding back ends.
//                https://learn.microsoft.com/power-bi/developer/embedded/embed-service-principal
//   secret       A client secret. Development only.
//
// Credentials are objects: { type: 'federated', getAssertion, source } | { type: 'certificate', privateKey,
// thumbprintSha256, notAfter } | { type: 'secret', secret }. The credential store keeps certificates and secrets as
// JSON (storedCredential); a federated credential has nothing to store.

// The audience of the token that stands in for an app's credential (public cloud; see AZURE_FEDERATED_AUDIENCE).
export const TOKEN_EXCHANGE_AUDIENCE = 'api://AzureADTokenExchange';
export const CREDENTIAL_TYPES = Object.freeze(['federated', 'certificate', 'secret']);

export function credentialLabel(credential) {
  if (credential?.type === 'federated') return credential.source === 'token file' ? 'federated credential (workload identity token)' : 'federated credential (managed identity)';
  if (credential?.type === 'certificate') return 'certificate';
  if (credential?.type === 'secret') return 'client secret';
  return 'none';
}

// A token for the token-exchange audience from a user-assigned managed identity, through MSAL (which knows App
// Service, Container Apps, Functions, virtual machines and Azure Arc). MSAL caches it and renews it before it expires.
export function managedIdentityAssertion({ clientId, audience = TOKEN_EXCHANGE_AUDIENCE } = {}) {
  if (!clientId) throw new Error('A federated credential needs the client ID of a user-assigned managed identity.');
  let app = null;
  return async () => {
    if (!app) {
      const { ManagedIdentityApplication } = await import('@azure/msal-node');
      app = new ManagedIdentityApplication({ managedIdentityIdParams: { userAssignedClientId: clientId } });
    }
    return (await app.acquireToken({ resource: audience })).accessToken;
  };
}

// Workload identity in Kubernetes (and similar): the platform writes a fresh token to a file; read it on every use.
export function tokenFileAssertion(file) {
  return async () => (await readFile(file, 'utf8')).trim();
}

export function certificateCredential(bundle) {
  return { type: 'certificate', ...parseCertificateBundle(bundle) };
}

// What the credential store keeps for a customer's service principal. Secrets stored before credentials had types
// are plain strings, and still work.
export function storedCredential(credential) {
  if (credential.type === 'certificate') return JSON.stringify({ type: 'certificate', bundle: credential.privateKey + credential.certificate });
  if (credential.type === 'secret') return JSON.stringify({ type: 'secret', secret: credential.secret });
  throw new Error(`A ${credential.type} credential isn't stored.`);
}

export function credentialFromStore(value) {
  if (value === null || value === undefined || value === '') return null;
  const text = String(value);
  if (!text.startsWith('{')) return { type: 'secret', secret: text };
  const parsed = JSON.parse(text);
  if (parsed.type === 'certificate') return certificateCredential(parsed.bundle);
  if (parsed.type === 'secret' && parsed.secret) return { type: 'secret', secret: parsed.secret };
  throw new Error('The stored credential has an unknown type.');
}
