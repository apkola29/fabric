import { readFileSync } from 'node:fs';
import { TERRITORIES, pilotPersonas, sampleSeedOf } from '../crm/workload.js';
import { parseColor, setLogo } from './branding.js';
import { addActivity, newTenantRecord } from './store.js';
import { uniqueSubdomain } from './tenancy.js';
import { ROLES, addUser, findUser, verifyPassword } from './users.js';

// The pilot: demo customers, each with its own Fabric workspace, CRM database with sample data, semantic model with
// row-level security, starter report and assistant, plus four people: the sales manager, who sees every territory,
// and one sales rep per territory, who sees only that territory. Each has its own address, logo and color. Safe to
// run again: existing customers are provisioned again (idempotent) and only missing people are added.

const logo = (file) => readFileSync(new URL(`./pilot-logos/${file}`, import.meta.url));

export const PILOT_CUSTOMERS = Object.freeze([
  Object.freeze({ name: 'Fabrikam', domain: 'fabrikam.com', brand: Object.freeze({ logo: 'fabrikam.svg', color: '#a8431c' }) }),
  Object.freeze({ name: 'Contoso', domain: 'contoso.com', brand: Object.freeze({ logo: 'contoso.svg', color: '#3b3a98' }) }),
]);

// "Fabrikam:fabrikam.com"
export function parseCustomer(text) {
  const [name, domain] = String(text || '').split(':').map((s) => s.trim());
  if (!name || !/^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$/i.test(domain || '')) {
    throw new Error(`Write a customer as Name:domain, for example Fabrikam:fabrikam.com (got "${text}").`);
  }
  return { name, domain: domain.toLowerCase() };
}

export const describeAccess = (person) => (person.role === 'manager' ? 'every territory' : person.territories.join(', '));

// The pilot's people a customer already has. Only password hashes are stored, so the passwords aren't known here.
export const pilotPeopleOf = (tenant, domain = tenant.domains[0]) =>
  pilotPersonas(sampleSeedOf(tenant), domain)
    .filter((persona) => findUser(tenant, persona.email))
    .map((persona) => ({ ...persona, password: null }));

export async function setUpPilot({ store, provisioner, crm, customers = PILOT_CUSTOMERS, plan = 'enterprise', workspaces = {}, reseed = false, log = () => {} }) {
  const results = [];
  for (const customer of customers) {
    let tenant = store.list().find((t) => t.name.toLowerCase() === customer.name.toLowerCase());
    if (tenant && !(tenant.domains || []).includes(customer.domain)) {
      throw new Error(`${tenant.name} already exists with the sign-in domain ${(tenant.domains || []).join(', ') || '(none)'}, not ${customer.domain}.`);
    }
    const other = store.list().find((t) => t.id !== tenant?.id && (t.domains || []).includes(customer.domain));
    if (other) throw new Error(`${customer.domain} already signs in as ${other.name}.`);
    if (!tenant) {
      tenant = newTenantRecord({
        name: customer.name,
        plan,
        domains: [customer.domain],
        sampleData: true,
        workspaceId: workspaces[customer.name] || null,
        subdomain: uniqueSubdomain(customer.name, store.list()),
      });
      tenant.pilot = true;
      addActivity(tenant, `Customer added by the pilot setup with the ${plan} edition`);
      await store.save(tenant);
      log(`${customer.name}: added. Provisioning (a few minutes in Fabric)...`);
    } else {
      log(`${customer.name}: already here. Provisioning again to bring it up to date...`);
    }
    // The pilot's logo and color, unless an operator has already chosen some.
    if (customer.brand && !tenant.branding?.logo && !tenant.branding?.color) {
      setLogo(tenant, logo(customer.brand.logo));
      tenant.branding.color = parseColor(customer.brand.color);
      addActivity(tenant, 'The pilot setup set the logo and accent color');
      await store.save(tenant);
    }

    const provisioned = (await provisioner.provision(tenant.id)) || store.get(tenant.id);
    if (provisioned.status !== 'ready') {
      log(`${customer.name}: provisioning stopped: ${provisioned.error}`);
      // People who already sign in stay listed, so the sign-ins file doesn't drop their passwords.
      results.push({ tenant: provisioned, people: pilotPeopleOf(provisioned, customer.domain), error: provisioned.error });
      continue;
    }

    // Accounts from before territories have no state, and reps only see accounts in their territories.
    const repo = await crm.forTenant(provisioned);
    const total = (await repo.counts()).accounts;
    const inTerritories = (await repo.scoped([...TERRITORIES]).listAccounts({ limit: 1 })).total;
    let note = null;
    if (total > inTerritories) {
      if (reseed) {
        await repo.replaceWithSampleData(sampleSeedOf(provisioned), { companyDomain: customer.domain });
        addActivity(provisioned, 'The pilot setup replaced the CRM data with the territory sample data', 'warning');
        log(`${customer.name}: replaced the sample data with the territory version.`);
      } else {
        note = `${total - inTerritories} of ${total} accounts have no territory, so reps won't see them. Load the territory sample data with: npm run cli -- reseed ${provisioned.name} --confirm`;
      }
    }

    const people = [];
    for (const persona of pilotPersonas(sampleSeedOf(provisioned), customer.domain)) {
      if (findUser(provisioned, persona.email)) {
        people.push({ ...persona, password: null });
        continue;
      }
      const { password } = await addUser({ store, tenant: provisioned, email: persona.email, name: persona.name, role: persona.role, territories: persona.territories });
      addActivity(provisioned, `The pilot setup added a sign-in for ${persona.email} (${ROLES[persona.role]}, ${describeAccess(persona)})`, 'audit');
      people.push({ ...persona, password });
    }
    await store.save(provisioned);
    log(`${customer.name}: ready, with ${people.length} people.`);
    results.push({ tenant: provisioned, people, note });
  }
  return results;
}

// Removes only the customers the pilot setup created, with their workspaces, unless asked to keep them.
export async function removePilot({ store, provisioner, keepWorkspaces = false, log = () => {} }) {
  const removed = [];
  for (const tenant of store.list().filter((t) => t.pilot)) {
    log(`${tenant.name}: removing${keepWorkspaces ? ' (keeping its workspace)' : ' with its workspace'}...`);
    await provisioner.deprovision(tenant.id, { keepWorkspace: keepWorkspaces });
    removed.push(tenant.name);
  }
  return removed;
}

// The sign-ins, for the person running the pilot. Passwords appear here and in the setup output only.
// `urlOf(tenant)` is where that customer's people sign in.
export function loginsMarkdown(results, { urlOf, adminUrl, generatedAt = new Date() }) {
  const lines = [
    '# HiCRM pilot sign-ins',
    '',
    `Created ${generatedAt.toISOString().slice(0, 16).replace('T', ' ')} UTC by \`npm run setup\`. Passwords are stored only as hashes in the app,`,
    'so this file is the only copy: keep them somewhere safe, then delete this file.',
    '',
    `- Back office: ${adminUrl} (operator key: ADMIN_KEY in .env)`,
    '',
  ];
  for (const { tenant, people, note, error } of results) {
    lines.push(`## ${tenant.name} (@${tenant.domains[0]})`, '', `Sign in at ${urlOf(tenant)}`, '');
    if (error) lines.push(`Provisioning stopped: ${error}`, '');
    if (people.length) {
      lines.push('| Person | Role | Sees | Email | Password |', '| --- | --- | --- | --- | --- |');
      for (const p of people) {
        lines.push(`| ${p.name} | ${ROLES[p.role]} | ${describeAccess(p)} | ${p.email} | ${p.password ? `\`${p.password}\`` : '(already set; reset with `npm run cli -- user-reset`)'} |`);
      }
      lines.push('');
    }
    if (note) lines.push(`Note: ${note}`, '');
  }
  return lines.join('\n');
}

// The passwords in an earlier sign-ins file, by email.
const passwordsIn = (markdown) =>
  new Map([...String(markdown || '').matchAll(/\|\s*([^|\s]+@[^|\s]+)\s*\|\s*`([^`]+)`\s*\|/g)].map((m) => [m[1].toLowerCase(), m[2]]));

// The sign-ins file is the only copy of the passwords, so running the setup again, for some customers only, or with
// provisioning stopping part way must not lose them: people who already sign in get their password from the earlier
// file, if it still works. A password reset since then is left out rather than shown wrong.
export async function carryOverPasswords(results, earlierMarkdown) {
  const earlier = passwordsIn(earlierMarkdown);
  for (const { tenant, people } of results) {
    for (const person of people) {
      const password = earlier.get(person.email.toLowerCase());
      if (person.password || !password) continue;
      const user = findUser(tenant, person.email);
      if (user && (await verifyPassword(password, user.passwordHash))) person.password = password;
    }
  }
  return results;
}
