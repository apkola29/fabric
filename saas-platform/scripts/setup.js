#!/usr/bin/env node
// Pilot setup: asks how to reach Microsoft Fabric, then creates the demo customers, their data and their people.
//
//   npm run setup                         guided
//   npm run setup -- --yes                accept the defaults (non-interactive; reads the settings below or .env)
//   npm run setup -- --mode demo          everything on this computer, no Azure needed
//   npm run pilot:remove                  remove the customers the setup created, with their workspaces
//
// Options: --mode fabric|demo  --auth cli|sp  --tenant <id>  --client-id <guid>  --capacity <guid>
//          --customer Name:domain (repeatable)  --workspace Name=<workspace-guid> (repeatable; adopt a workspace an
//          admin created)  --plan enterprise|professional|standard  --reseed  --settings-file <path> (default .env)  --keep-workspaces
// Credentials are asked for when needed and never written to disk: the platform identity's certificate (or, for
// development, its client secret) and the key that encrypts the customers' credentials (SECRETS_KEY). Unattended
// (--yes), they come from the environment: AZURE_CLIENT_CERTIFICATE_PATH or AZURE_CLIENT_SECRET, and SECRETS_KEY.

import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { chmod, copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import readline from 'node:readline/promises';
import { parseArgs } from 'node:util';
import { PromptCancelled, askForSecrets } from '../src/auth/runtime-secrets.js';
import { createTokenProvider } from '../src/auth/tokens.js';
import { isGuid, loadConfig } from '../src/config.js';
import { createCrmService } from '../src/crm/index.js';
import { createFabricClient } from '../src/fabric/client.js';
import { createMockFabric } from '../src/fabric/mock.js';
import { createIdentityBroker } from '../src/platform/identities.js';
import { PILOT_CUSTOMERS, carryOverPasswords, describeAccess, loginsMarkdown, parseCustomer, pilotPeopleOf, removePilot, setUpPilot } from '../src/platform/pilot.js';
import { getPlan } from '../src/platform/plans.js';
import { createProvisioner } from '../src/platform/provisioner.js';
import { createSecretStore } from '../src/platform/secrets.js';
import { createTenantStore } from '../src/platform/store.js';
import { platformUrl, signInUrl } from '../src/platform/tenancy.js';
import { ROLES } from '../src/platform/users.js';

const { values: options } = parseArgs({
  options: {
    yes: { type: 'boolean', short: 'y', default: false },
    mode: { type: 'string' },
    auth: { type: 'string' },
    tenant: { type: 'string' },
    'client-id': { type: 'string' },
    capacity: { type: 'string' },
    customer: { type: 'string', multiple: true },
    workspace: { type: 'string', multiple: true },
    plan: { type: 'string', default: 'enterprise' },
    reseed: { type: 'boolean', default: false },
    remove: { type: 'boolean', default: false },
    'keep-workspaces': { type: 'boolean', default: false },
    'settings-file': { type: 'string', default: '.env' },
    help: { type: 'boolean', short: 'h' },
  },
});
if (options.help) {
  const header = (await readFile(new URL(import.meta.url), 'utf8')).split('\n').filter((l) => l.startsWith('//')).map((l) => l.replace(/^\/\/ ?/, ''));
  console.log(header.join('\n'));
  process.exit(0);
}

const envFile = path.resolve(options['settings-file']);
const interactive = !options.yes && process.stdin.isTTY;
let io = interactive ? readline.createInterface({ input: process.stdin, output: process.stdout }) : null;
const say = (text = '') => console.log(text);
class SetupError extends Error {}
const stop = (message) => {
  throw new SetupError(message);
};

async function ask(question, fallback = '') {
  if (!io) return fallback;
  const answer = (await io.question(`${question}${fallback ? ` [${fallback}]` : ''}: `)).trim();
  return answer || fallback;
}

async function choose(question, choices, fallback = 0) {
  if (!io) return fallback;
  say(question);
  choices.forEach((choice, i) => say(`  ${i + 1}. ${choice}`));
  for (;;) {
    const answer = await ask('Choose', String(fallback + 1));
    const index = Number(answer) - 1;
    if (Number.isInteger(index) && index >= 0 && index < choices.length) return index;
    say(`Type a number from 1 to ${choices.length}.`);
  }
}

const yes = async (question, fallback = true) => /^y/i.test(await ask(`${question} (y/n)`, fallback ? 'y' : 'n'));

function azure(args) {
  return new Promise((resolve, reject) => {
    execFile('az', args, { shell: process.platform === 'win32', timeout: 60_000, windowsHide: true }, (error, stdout, stderr) =>
      error ? reject(new Error(String(stderr || error.message).split(/\r?\n/).find((l) => l.trim()) || error.message)) : resolve(stdout),
    );
  });
}

function parseEnv(text) {
  const values = {};
  for (const line of text.split(/\r?\n/)) {
    const match = /^\s*([A-Z0-9_]+)\s*=\s*(.*)$/.exec(line);
    if (match) values[match[1]] = match[2].trim().replace(/^"(.*)"$/, '$1');
  }
  return values;
}

// Everything the server needs, built the same way server.js and the platform CLI build it.
function createPlatform(config) {
  const mock = config.authMode === 'mock';
  const tokens = mock ? null : createTokenProvider(config);
  const fabric = mock ? createMockFabric({ stateFile: path.join(config.dataDir, 'mock-fabric.json') }) : createFabricClient({ tokens, endpoints: config.endpoints });
  const store = createTenantStore({ file: path.join(config.dataDir, mock ? 'tenants.mock.json' : 'tenants.json') });
  const secrets = createSecretStore(config, { tokens });
  const identities = createIdentityBroker({ config, platformTokens: tokens, platformFabric: fabric, secrets });
  const crm = createCrmService({ fabric, identities, sqliteDir: mock ? config.dataDir : null, ...config.crmPools });
  // Demo mode answers at once, so there's nothing to wait for between polls.
  const provisioner = createProvisioner({ fabric, store, config, identities, crm, ...(mock ? { waitMs: 0, refreshPollMs: 0, capacityPollMs: 0 } : {}) });
  return { mock, tokens, fabric, store, crm, provisioner };
}

// 1. Settings: from .env when it exists, otherwise from a few questions.
async function settings() {
  const existing = existsSync(envFile) ? parseEnv(await readFile(envFile, 'utf8')) : null;
  if (existing && !options.mode && (!interactive || (await yes(`Use the settings in ${path.basename(envFile)} (${existing.FABRIC_AUTH_MODE || 'mock'} mode)?`)))) {
    return { values: existing, write: false };
  }
  const values = {};
  if (options.mode && !['demo', 'fabric'].includes(options.mode)) stop('--mode must be fabric or demo.');
  const demoChosen = options.mode ? options.mode === 'demo' : (await choose('Where should the customers\' data live?', ['Microsoft Fabric in your Azure tenant', 'Demo mode on this computer (nothing in Azure)'])) === 1;
  if (demoChosen) {
    values.FABRIC_AUTH_MODE = 'mock';
  } else {
    const auth = options.auth || ((await choose('How should the app sign in to Fabric?', ['Your Azure CLI sign-in (az login); nothing secret is stored', 'A service principal (its secret stays in your shell as AZURE_CLIENT_SECRET)'])) === 1 ? 'sp' : 'cli');
    if (!['cli', 'sp'].includes(auth)) stop('--auth must be cli or sp.');
    values.FABRIC_AUTH_MODE = auth;
    if (auth === 'cli') {
      let account;
      try {
        account = JSON.parse(await azure(['account', 'show', '--output', 'json']));
      } catch (error) {
        stop(`The Azure CLI isn't signed in (${error.message}). Run "az login", then run the setup again.`);
      }
      say(`Azure CLI: signed in as ${account.user?.name} in tenant ${account.tenantId}.`);
      values.AZURE_TENANT_ID = options.tenant || (await ask('Tenant ID', account.tenantId));
    } else {
      values.AZURE_TENANT_ID = options.tenant || (await ask('Tenant ID (GUID)', process.env.AZURE_TENANT_ID || ''));
      values.AZURE_CLIENT_ID = options['client-id'] || (await ask('Platform app registration (client) ID', process.env.AZURE_CLIENT_ID || ''));
      if (!isGuid(values.AZURE_CLIENT_ID)) stop('The client ID must be a GUID.');
      // Its certificate or secret is asked for next (askForSecrets), and never saved.
    }
    if (!values.AZURE_TENANT_ID) stop('The tenant ID is required.');
  }
  // Each customer at its own address: http://fabrikam.localhost:3000, http://contoso.localhost:3000.
  values.APP_DOMAIN = 'localhost';
  return { values, write: true };
}

// 2. The capacity that hosts the customer workspaces. Fabric items (SQL database, Direct Lake, data agents) need an F,
// trial (FT) or P capacity; Premium Per User and Embedded A/EM capacities can't host them.
const FABRIC_SKU = /^(F|FT|P)\d+$/i;

async function pickCapacity(fabric, current) {
  let capacities;
  try {
    capacities = (await fabric.listCapacities()).filter((c) => c.state === 'Active');
  } catch (error) {
    stop(`Fabric didn't answer (${error.message}). Check the tenant setting "Service principals can use Fabric APIs" (service principal) or your access (Azure CLI).`);
  }
  const unsuitable = capacities.filter((c) => !FABRIC_SKU.test(c.sku || ''));
  capacities = capacities.filter((c) => FABRIC_SKU.test(c.sku || ''));
  if (unsuitable.length) say(`Not offered (can't host Fabric items): ${unsuitable.map((c) => `${c.displayName} (${c.sku})`).join(', ')}.`);
  if (options.capacity) {
    const match = capacities.find((c) => c.id.toLowerCase() === options.capacity.toLowerCase());
    if (!match) stop(`The identity can't use capacity ${options.capacity} for Fabric items. It needs Contributor (or Admin) rights on an F, trial or P capacity.`);
    return match;
  }
  if (current) {
    const match = capacities.find((c) => c.id.toLowerCase() === current.toLowerCase());
    if (match) return match;
  }
  if (!capacities.length) {
    if (options.workspace?.length) return null;
    stop('No Fabric capacity is available to this identity. Start a Fabric trial or give the identity Contributor rights on an F capacity, or adopt workspaces an admin created with --workspace Name=<workspace-id>.');
  }
  if (capacities.length === 1) return capacities[0];
  if (!io) stop(`Several capacities are available; choose one with --capacity: ${capacities.map((c) => `${c.displayName} ${c.id}`).join(', ')}.`);
  const index = await choose(
    'Which Fabric capacity should host the customer workspaces?',
    capacities.map((c) => `${c.displayName} (${c.sku}, ${c.region})`),
  );
  return capacities[index];
}

async function writeEnv(values) {
  if (existsSync(envFile)) {
    const backup = `${envFile}.backup-${Date.now()}`;
    await copyFile(envFile, backup);
    say(`Saved the previous settings to ${path.basename(backup)}.`);
  }
  const lines = [
    `# Written by "npm run setup" on ${new Date().toISOString().slice(0, 10)}. Local settings: never commit this file.`,
    '# No credentials are kept here. "npm start" asks for them: the platform identity\'s certificate or secret,',
    '# the key that unlocks the customers\' stored credentials (SECRETS_KEY), and a back-office key (ADMIN_KEY).',
    `FABRIC_AUTH_MODE=${values.FABRIC_AUTH_MODE}`,
    ...(values.AZURE_TENANT_ID ? [`AZURE_TENANT_ID=${values.AZURE_TENANT_ID}`] : []),
    ...(values.AZURE_CLIENT_ID ? [`AZURE_CLIENT_ID=${values.AZURE_CLIENT_ID}`] : []),
    ...(values.AZURE_CLIENT_CERTIFICATE_PATH ? ['# Where the platform identity\'s certificate is (keep the file outside the project).', `AZURE_CLIENT_CERTIFICATE_PATH=${values.AZURE_CLIENT_CERTIFICATE_PATH}`] : []),
    ...(values.FABRIC_CAPACITY_ID ? [`FABRIC_CAPACITY_ID=${values.FABRIC_CAPACITY_ID}`] : []),
    '# Each customer at its own address: http://<customer>.localhost:3000; the back office at http://localhost:3000/admin.',
    `APP_DOMAIN=${values.APP_DOMAIN || ''}`,
    'HOST=127.0.0.1',
    'PORT=3000',
    '',
  ];
  await mkdir(path.dirname(envFile), { recursive: true });
  await writeFile(envFile, lines.join('\n'), { mode: 0o600 });
  say(`Wrote ${path.basename(envFile)}.`);
}

async function main() {
  // Without a terminal to ask in, nothing is created or removed unless --yes says so.
  if (!interactive && !options.yes) stop('Run "npm run setup" in a terminal, or add --yes to accept the defaults without questions.');
  if (options.remove) {
    const config = loadConfig();
    const platform = createPlatform(config);
    try {
      const pilots = platform.store.list().filter((t) => t.pilot);
      if (!pilots.length) return say('There are no customers created by the pilot setup.');
      say(`This removes ${pilots.map((t) => t.name).join(' and ')}${options['keep-workspaces'] ? '' : ', including their Fabric workspaces and everything in them'}.`);
      if (interactive && !(await yes('Go ahead?', false))) return say('Nothing removed.');
      const removed = await removePilot({ store: platform.store, provisioner: platform.provisioner, keepWorkspaces: options['keep-workspaces'], log: say });
      return say(`Removed ${removed.join(', ')}.`);
    } finally {
      await platform.crm.closeAll();
    }
  }

  say('Platform app pilot setup: creates demo customers, each with its own Fabric workspace, CRM database, semantic model');
  say('with row-level security, starter report and assistant, and four people per customer.\n');
  const { values, write } = await settings();
  // Credentials for this run: asked for now (hidden input), never saved. The setup's own questions share the
  // terminal, so they pause meanwhile.
  io?.close();
  let env;
  try {
    env = await askForSecrets({ ...process.env, ...values }, { purpose: 'setup', interactive });
  } finally {
    if (interactive) io = readline.createInterface({ input: process.stdin, output: process.stdout });
  }
  // A certificate's path isn't a secret: remember it in the settings so the next start doesn't ask.
  if (env.AZURE_CLIENT_CERTIFICATE_PATH && !process.env.AZURE_CLIENT_CERTIFICATE_PATH) values.AZURE_CLIENT_CERTIFICATE_PATH = env.AZURE_CLIENT_CERTIFICATE_PATH;
  let config = loadConfig(env);
  let platform = createPlatform(config);

  if (!platform.mock) {
    const capacity = await pickCapacity(platform.fabric, values.FABRIC_CAPACITY_ID);
    if (capacity) {
      values.FABRIC_CAPACITY_ID = capacity.id;
      say(`Capacity: ${capacity.displayName} (${capacity.sku}).`);
      if (/^FT/i.test(capacity.sku)) say('  Note: on a trial capacity, Copilot and the data agent\'s code interpreter aren\'t supported. The data agent is documented for paid capacities; if it can\'t answer, the assistant uses quick answers from the CRM data.');
    }
    await platform.crm.closeAll();
    config = loadConfig({ ...env, ...values });
    platform = createPlatform(config);
  }

  const customers = options.customer?.length ? options.customer.map(parseCustomer) : [...PILOT_CUSTOMERS];
  const workspaces = Object.fromEntries((options.workspace || []).map((w) => w.split('=').map((s) => s.trim())));
  for (const [name, id] of Object.entries(workspaces)) if (!isGuid(id)) stop(`--workspace ${name}=${id}: the workspace ID must be a GUID.`);
  if (!getPlan(options.plan)) stop(`Unknown edition ${options.plan}.`);
  say(`\nCustomers: ${customers.map((c) => `${c.name} (@${c.domain})`).join(', ')}; edition ${getPlan(options.plan).name}.`);
  if (interactive && !(await yes('Create them now?'))) return say('Nothing created.');
  if (write) await writeEnv(values);

  try {
    const results = await setUpPilot({ store: platform.store, provisioner: platform.provisioner, crm: platform.crm, customers, plan: options.plan, workspaces, reseed: options.reseed, log: (line) => say(`  ${line}`) });
    const appUrl = platformUrl(config);
    const logins = path.join(config.dataDir, 'pilot-logins.md');
    const fresh = new Set(results.flatMap((r) => r.people.filter((p) => p.password).map((p) => p.email)));
    // The file lists every pilot customer, not only this run's, with the earlier passwords that still work.
    const byId = new Map(results.map((r) => [r.tenant.id, r]));
    const listed = platform.store.list().filter((t) => t.pilot || byId.has(t.id)).map((t) => byId.get(t.id) || { tenant: t, people: pilotPeopleOf(t) });
    await carryOverPasswords(listed, existsSync(logins) ? await readFile(logins, 'utf8') : '');
    await mkdir(config.dataDir, { recursive: true });
    await writeFile(logins, loginsMarkdown(listed, { urlOf: (tenant) => signInUrl(config, tenant), adminUrl: `${appUrl}admin` }), { mode: 0o600 });
    await chmod(logins, 0o600).catch(() => {});

    say('');
    for (const { tenant, people, note, error } of results) {
      say(`${tenant.name}${error ? `: NOT READY (${error})` : ''} at ${signInUrl(config, tenant)}`);
      for (const p of people) say(`  ${p.name.padEnd(18)} ${ROLES[p.role].padEnd(14)} ${describeAccess(p).padEnd(16)} ${p.email.padEnd(32)} ${fresh.has(p.email) ? p.password : '(unchanged)'}`);
      if (note) say(`  Note: ${note}`);
    }
    say(`\nThe sign-ins are also in ${logins}. Passwords aren't stored anywhere else: save them, then delete that file.`);
    const asks = [
      ...(config.authMode === 'sp' && !values.AZURE_CLIENT_CERTIFICATE_PATH ? ["the platform identity's certificate or secret"] : []),
      ...(config.authMode !== 'mock' ? ["the key you chose for the customers' stored credentials", `a back-office key for ${appUrl}admin`] : []),
    ];
    say(asks.length
      ? `Start the app with "npm start". It asks for ${asks.slice(0, -1).join(', ')}${asks.length > 1 ? ' and ' : ''}${asks.at(-1)}, and saves none of them.`
      : `Start the app with "npm start": demo mode needs no credentials. The back office is at ${appUrl}admin.`);
    say('Then open each customer\'s address above. The story to walk through is in PILOT.md.');
    if (results.some((r) => r.error)) process.exitCode = 1;
  } finally {
    await platform.crm.closeAll();
  }
}

try {
  await main();
} catch (error) {
  console.error(error instanceof SetupError || error instanceof PromptCancelled ? `\n${error.message}` : error);
  process.exitCode = 1;
} finally {
  io?.close();
}
