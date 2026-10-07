import { createServer } from 'node:http';
import path from 'node:path';
import { createApp } from './src/app.js';
import { PromptCancelled, askForSecrets } from './src/auth/runtime-secrets.js';
import { createTokenProvider } from './src/auth/tokens.js';
import { loadConfig } from './src/config.js';
import { createFabricClient } from './src/fabric/client.js';
import { createMockFabric } from './src/fabric/mock.js';
import { createTenantStore } from './src/platform/store.js';
import { customerUrl, platformUrl } from './src/platform/tenancy.js';

// Credentials are asked for here (or come from the environment), never from a file in the project.
let config;
try {
  config = loadConfig(await askForSecrets(process.env, { purpose: 'server' }));
} catch (error) {
  console.error(error instanceof PromptCancelled ? 'Cancelled.' : error.message);
  process.exit(1);
}

const mock = config.authMode === 'mock';
const tokens = mock ? null : createTokenProvider(config);
const fabric = mock
  ? createMockFabric({ stateFile: path.join(config.dataDir, 'mock-fabric.json'), latencyMs: 250 })
  : createFabricClient({ tokens, endpoints: config.endpoints });
const store = createTenantStore({ file: path.join(config.dataDir, mock ? 'tenants.mock.json' : 'tenants.json') });
// Demo mode keeps each customer's CRM in a SQLite file next to the mock state, so edits survive restarts.
const app = createApp({ config, fabric, store, tokens, crmDir: mock ? config.dataDir : null });

const server = createServer(app.handler);
// Long enough for large uploads; headers must arrive quickly, so idle connections can't hold sockets open.
server.requestTimeout = 15 * 60 * 1000;
server.headersTimeout = 30 * 1000;
server.listen(config.port, config.host, () => {
  const address = server.address();
  const base = config.appDomain || config.publicOrigin ? platformUrl(config) : `http://${config.host === '0.0.0.0' ? 'localhost' : config.host}:${address.port}/`;
  console.log(`${config.productName} platform: ${base} (back office at ${base}admin)`);
  // Each customer's own address (APP_DOMAIN), where its people sign in.
  if (config.appDomain) for (const tenant of store.list()) console.log(`  ${tenant.name}: ${customerUrl(config, tenant)}`);
  console.log(`Mode: ${config.authMode}${mock ? ' (no calls to Fabric)' : ''} | environment: ${config.appEnv} | data: ${config.dataDir}`);
  if (!mock) console.log(`Platform identity: ${tokens.describe().label}${config.authMode === 'sp' ? `, ${tokens.describe().credential}` : ''}`);
  console.log(
    `Security: operator sign-in ${config.adminKey ? 'on' : 'off (loopback only)'} | customer service accounts ${config.identity.mode} | platform workspace access ${config.platformWorkspaceAccess} | embed tokens ${config.embedTokenMinutes} min`,
  );
  for (const warning of config.warnings) console.warn(`Warning: ${warning}`);
  const resumed = app.resumeInterrupted();
  if (resumed) console.log(`Resumed provisioning for ${resumed} customer(s).`);
});

const shutdown = () => server.close(() => app.close().finally(() => process.exit(0)));
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
