import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { mkdtemp, rm } from 'node:fs/promises';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseCsv } from '../util/csv.js';

// Opens embedded reports in a real browser for the validator (npm run validate -- --live --browser): Microsoft Edge
// or Google Chrome driven over the Chrome DevTools Protocol, with Node's built-in WebSocket and no extra packages.
// It checks what each person actually sees, as Microsoft recommends for row-level security with service principals:
// https://learn.microsoft.com/fabric/security/service-admin-row-level-security

const CANDIDATES = {
  win32: [
    path.join(process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'Google', 'Chrome', 'Application', 'chrome.exe'),
  ],
  darwin: ['/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'],
  linux: ['/usr/bin/microsoft-edge', '/usr/bin/microsoft-edge-stable', '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser'],
};

// BROWSER_PATH wins; otherwise the first Edge or Chrome installed in the usual place.
export function findBrowser({ env = process.env, platform = process.platform, exists = existsSync } = {}) {
  if (env.BROWSER_PATH) return exists(env.BROWSER_PATH) ? env.BROWSER_PATH : null;
  return (CANDIDATES[platform] || []).find((candidate) => exists(candidate)) || null;
}

// The rows of a visual's exported data: the first column is the label, the last a number such as "$2228500".
export function parseExportedRows(csv) {
  const [, ...rows] = parseCsv(String(csv || '').trim());
  return rows.filter((row) => row.length >= 2 && row[0] !== '').map((row) => ({ label: row[0], value: Number(String(row[row.length - 1]).replace(/[^0-9.-]/g, '')) }));
}

// Edge relaunches itself when it starts under an app compatibility layer (__COMPAT_LAYER, which some terminals and
// editors set) or elevated. The first process then exits with code 0, and the relaunched browser's DevTools address
// never reaches us. The last two flags keep Edge in the process we started, as Playwright does; Chrome ignores them.
export function browserArgs(profile) {
  return ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--edge-skip-compat-layer-relaunch', '--disable-features=AutoDeElevate', 'about:blank'];
}

async function launch(executable, { timeoutMs = 30_000 } = {}) {
  const profile = await mkdtemp(path.join(os.tmpdir(), 'fabric-validate-'));
  const child = spawn(executable, browserArgs(profile), { stdio: ['ignore', 'ignore', 'pipe'] });
  const endpoint = await new Promise((resolve, reject) => {
    let output = '';
    const timer = setTimeout(() => reject(new Error(`The browser didn't start within ${timeoutMs / 1000} s.`)), timeoutMs);
    child.stderr.on('data', (chunk) => {
      output += chunk;
      const found = /DevTools listening on (ws:\/\/\S+)/.exec(output);
      if (found) {
        clearTimeout(timer);
        resolve(found[1]);
      }
    });
    child.on('error', (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on('exit', (code) => {
      clearTimeout(timer);
      reject(new Error(`The browser exited (code ${code}) before it was ready.`));
    });
  });
  child.stderr.resume();

  const socket = new WebSocket(endpoint);
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', () => reject(new Error("Couldn't connect to the browser.")), { once: true });
  });
  let nextId = 0;
  const pending = new Map();
  const listeners = new Set();
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(String(event.data));
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    } else for (const listener of listeners) listener(message);
  });
  const send = (method, params = {}, sessionId) =>
    new Promise((resolve, reject) => {
      const id = ++nextId;
      pending.set(id, { resolve, reject });
      socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  const next = (matches, ms) =>
    new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        listeners.delete(listener);
        reject(new Error('The page took too long to load.'));
      }, ms);
      const listener = (message) => {
        if (!matches(message)) return;
        clearTimeout(timer);
        listeners.delete(listener);
        resolve(message);
      };
      listeners.add(listener);
    });

  return {
    async open(url) {
      const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
      const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
      await send('Page.enable', {}, sessionId);
      await send('Runtime.enable', {}, sessionId);
      const loaded = next((m) => m.sessionId === sessionId && m.method === 'Page.loadEventFired', 60_000);
      await send('Page.navigate', { url }, sessionId);
      await loaded;
      return {
        async evaluate(fn, arg) {
          const { result, exceptionDetails } = await send('Runtime.evaluate', { expression: `(${fn})(${JSON.stringify(arg)})`, awaitPromise: true, returnByValue: true }, sessionId);
          if (exceptionDetails) throw new Error(exceptionDetails.exception?.description?.split('\n')[0] || exceptionDetails.text);
          return result.value;
        },
        close: () => send('Target.closeTarget', { targetId }).catch(() => {}),
      };
    },
    async close() {
      await send('Browser.close').catch(() => {});
      socket.close();
      child.kill();
      // The browser can hold its profile for a moment after it exits.
      for (let i = 0; i < 5; i += 1) {
        try {
          await rm(profile, { recursive: true, force: true });
          return;
        } catch {
          await new Promise((r) => setTimeout(r, 500));
        }
      }
    },
  };
}

// The Power BI client library exactly as the app loads it: same version, same Subresource Integrity hash.
function clientScriptTag() {
  const index = readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'public', 'index.html'), 'utf8');
  const tag = /<script src="https:\/\/cdn\.jsdelivr\.net\/npm\/powerbi-client@[^"]+"[^>]*><\/script>/.exec(index)?.[0];
  if (!tag) throw new Error("public/index.html doesn't load the Power BI client library.");
  return tag.replace(/\sdefer(?=[\s>])/, '');
}

// Runs in the page: embeds the report with the given embed token and returns one visual's summarized data as CSV.
// With `widen`, it then applies a report filter asking for every value of the row-level security column and exports
// the visual again: row-level security holds only if a filter can never show more than the roles allow.
async function exportFromReport({ embed, visual, widen = null }) {
  for (let i = 0; i < 300 && !(window.powerbi && window['powerbi-client']); i += 1) await new Promise((r) => setTimeout(r, 100));
  if (!window.powerbi) throw new Error("The Power BI client library didn't load.");
  const { models } = window['powerbi-client'];
  const host = document.getElementById('report');
  window.powerbi.reset(host);
  const report = window.powerbi.embed(host, {
    type: 'report',
    id: embed.reportId,
    embedUrl: embed.embedUrl,
    accessToken: embed.accessToken,
    tokenType: models.TokenType.Embed,
    permissions: models.Permissions.Read,
    viewMode: models.ViewMode.View,
  });
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('The report did not render within 120 seconds.')), 120_000);
    report.on('rendered', () => {
      clearTimeout(timer);
      resolve();
    });
    report.on('error', (event) => {
      clearTimeout(timer);
      reject(new Error(JSON.stringify(event.detail || {}).slice(0, 300)));
    });
  });
  const page = (await report.getPages()).find((p) => p.isActive);
  const target = (await page.getVisuals()).find((v) => v.title === visual);
  if (!target) throw new Error(`The report's first page has no visual titled "${visual}".`);
  const exported = await target.exportData(models.ExportDataType.Summarized);
  if (!widen) return exported.data;
  const rendered = new Promise((resolve) => {
    const timer = setTimeout(resolve, 20_000);
    report.on('rendered', () => {
      clearTimeout(timer);
      resolve();
    });
  });
  await report.setFilters([
    { $schema: 'http://powerbi.com/product/schema#basic', target: { table: widen.table, column: widen.column }, operator: 'In', values: widen.values, filterType: models.FilterType.Basic },
  ]);
  await rendered;
  const again = await target.exportData(models.ExportDataType.Summarized);
  return { data: exported.data, widened: again.data };
}

// A browser plus a local page that hosts the Power BI client. Embed tokens go from this process to that page only.
export async function openReportProbe({ executable = findBrowser() } = {}) {
  if (!executable) throw new Error('No Microsoft Edge or Google Chrome found. Set BROWSER_PATH to one.');
  const page = `<!doctype html><html><head><meta charset="utf-8"><title>Report check</title>${clientScriptTag()}</head><body style="margin:0"><div id="report" style="width:1280px;height:720px"></div></body></html>`;
  const server = http.createServer((req, res) => {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
    res.end(page);
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}/`;
  let browser;
  try {
    browser = await launch(executable);
  } catch (error) {
    server.close();
    throw error;
  }
  return {
    // `widen`: { table, column, values } to try a report filter for every value (see exportFromReport).
    async exportVisual(embed, visual, { widen = null } = {}) {
      const tab = await browser.open(url);
      try {
        const result = await tab.evaluate(exportFromReport, { embed, visual, widen });
        if (!widen) return { rows: parseExportedRows(result) };
        return { rows: parseExportedRows(result.data), widenedRows: parseExportedRows(result.widened) };
      } finally {
        await tab.close();
      }
    },
    async close() {
      await browser.close();
      server.close();
    },
  };
}
