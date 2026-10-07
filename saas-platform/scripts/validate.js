// Validates the framework's controls (FRAMEWORK.md, section 6) against a platform.
//
//   npm run validate                        the emulator: two tenants built in memory, nothing leaves the machine
//   npm run validate -- --live              this deployment: the registry in DATA_DIR and live Fabric, read-only
//   npm run validate -- --live --browser    also opens the standard report as each person in Edge or Chrome
//
// Options: --tenant <name> (repeatable) to limit the tenants, --json <file> and --markdown <file> to save the results.
// The exit code is 1 when a control fails.
import { writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { askForSecrets } from '../src/auth/runtime-secrets.js';
import { openReportProbe } from '../src/platform/browser.js';
import { countResults, createEmulatedPlatform, createLivePlatform, formatScorecard, toMarkdown, validatePlatform } from '../src/platform/validation.js';

const { values: options } = parseArgs({
  options: {
    live: { type: 'boolean', default: false },
    browser: { type: 'boolean', default: false },
    tenant: { type: 'string', multiple: true },
    json: { type: 'string' },
    markdown: { type: 'string' },
    help: { type: 'boolean', short: 'h', default: false },
  },
});

if (options.help) {
  console.log('Usage: npm run validate [-- --live [--browser]] [--tenant <name>] [--json <file>] [--markdown <file>]');
  process.exit(0);
}
if (options.browser && !options.live) {
  console.error('--browser needs --live: the emulator has no Power BI to render reports.');
  process.exit(2);
}

let platform;
let probe = null;
try {
  // Live: the platform credential and the credential-store key are asked for, as for the server.
  platform = options.live ? createLivePlatform(await askForSecrets(process.env, { purpose: 'cli' })) : await createEmulatedPlatform();
  const wanted = (options.tenant || []).map((name) => name.toLowerCase());
  const tenants = wanted.length ? platform.tenants.filter((t) => wanted.includes(t.name.toLowerCase())) : platform.tenants;
  if (!tenants.length) throw new Error(wanted.length ? `No tenant named ${options.tenant.join(', ')}.` : 'There are no tenants to validate.');
  if (options.browser) probe = await openReportProbe();

  const started = new Date();
  const results = await validatePlatform({ ...platform, tenants, browser: probe });
  const heading = `Framework validation, ${platform.mode === 'live' ? 'live' : 'emulator'}: ${tenants.map((t) => t.name).join(', ')} (${started.toISOString().slice(0, 16).replace('T', ' ')} UTC)`;
  console.log(formatScorecard(results, { heading }));
  if (options.json) writeFileSync(options.json, `${JSON.stringify({ heading, mode: platform.mode, at: started.toISOString(), results }, null, 2)}\n`);
  if (options.markdown) writeFileSync(options.markdown, toMarkdown(results, { heading }));
  process.exitCode = countResults(results).fail ? 1 : 0;
} catch (error) {
  console.error(`Validation couldn't run: ${error.message}`);
  process.exitCode = 2;
} finally {
  await probe?.close().catch(() => {});
  await platform?.close().catch(() => {});
}
