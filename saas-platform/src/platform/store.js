import { randomUUID } from 'node:crypto';
import { createJsonWriter, readJsonFile } from '../util/files.js';

// Tenant registry: maps each SaaS customer to its Fabric workspace and items. A JSON file is enough for a local MVP;
// in production this lives in the SaaS app's own database.

export function createTenantStore({ file = null } = {}) {
  const state = file ? readJsonFile(file, { tenants: {} }) : { tenants: {} };
  state.tenants ||= {};
  const write = file ? createJsonWriter(file) : null;
  const persist = () => (write ? write(state) : Promise.resolve());

  return {
    list: () => Object.values(state.tenants).sort((a, b) => a.createdAt.localeCompare(b.createdAt)),
    get: (id) => state.tenants[id] || null,
    async save(tenant) {
      tenant.updatedAt = new Date().toISOString();
      state.tenants[tenant.id] = tenant;
      await persist();
      return tenant;
    },
    async remove(id) {
      delete state.tenants[id];
      await persist();
    },
  };
}

export function slugify(name) {
  return (
    name
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40) || 'customer'
  );
}

export function newTenantRecord({ name, plan, workspaceId = null, domains = [], addons = [], sampleData = true, capacityId = null, subdomain = null }) {
  const now = new Date().toISOString();
  return {
    id: randomUUID(),
    name,
    slug: slugify(name),
    // The customer's own address: https://<subdomain>.<APP_DOMAIN> (see tenancy.js). Empty: the slug.
    subdomain,
    // Logo and accent color (see branding.js).
    branding: null,
    // The assistant's most recent questions (see assistant.js).
    questions: [],
    plan,
    addons,
    // Demo customers start with fabricated CRM data; real customers start empty.
    sampleData,
    // Email domains whose users sign in to the app as this customer.
    domains,
    // Named sign-ins (see users.js). While there are none, anyone at a sign-in domain can use the demo sign-in.
    users: [],
    // A dedicated Fabric capacity for this customer (noisy-neighbour isolation, data residency). Empty: the default.
    capacityId,
    status: 'pending',
    error: null,
    createdAt: now,
    updatedAt: now,
    // An adopted workspace was created by an admin and shared with the platform identity; the platform never recreates it.
    fabric: workspaceId ? { workspaceId, adopted: true } : {},
    // The customer's own service account (see identities.js); never holds the secret itself.
    identity: null,
    steps: {},
    activity: [],
    ingestions: [],
  };
}

export function addActivity(tenant, message, level = 'info') {
  tenant.activity.unshift({ at: new Date().toISOString(), level, message });
  if (tenant.activity.length > 60) tenant.activity.length = 60;
}
