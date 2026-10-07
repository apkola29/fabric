import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { Script, createContext } from 'node:vm';
import { TOKEN_CHECK_MS, refreshTimeOf } from '../public/embed-token.js';

const APP = new URL('../public/app.js', import.meta.url);
const HTML = readFileSync(new URL('../public/index.html', import.meta.url), 'utf8');
const MANAGER = 'manager@fabrikam.example';
const REP = 'texas@fabrikam.example';
const plain = (value) => JSON.parse(JSON.stringify(value));
const tick = () => new Promise((resolve) => setImmediate(resolve));
const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
};

class DomNode {
  constructor(tag = '#text', text = '') {
    this.tag = tag;
    this.data = text;
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.dataset = {};
    this.style = { removeProperty() {}, setProperty() {} };
    this.hidden = false;
    this.disabled = false;
    this.checked = false;
    this.files = [];
    this.open = false;
    this.classList = {
      add: (...names) => { this.className = [...new Set([...this.className.split(/\s+/).filter(Boolean), ...names])].join(' '); },
      remove: (...names) => { this.className = this.className.split(/\s+/).filter((name) => !names.includes(name)).join(' '); },
      toggle: (name, on) => {
        const present = this.className.split(/\s+/).includes(name);
        if (on ?? !present) this.classList.add(name);
        else this.classList.remove(name);
      },
    };
  }
  get textContent() { return this.tag === '#text' ? this.data : this.children.map((child) => child.textContent).join(''); }
  set textContent(text) { this.replaceChildren(new DomNode('#text', String(text))); }
  get className() { return this.attributes.get('class') || ''; }
  set className(value) { this.attributes.set('class', value); }
  get id() { return this.attributes.get('id') || ''; }
  get value() {
    if (this.inputValue !== undefined) return this.inputValue;
    if (this.tag === 'select') {
      const options = this.querySelectorAll('option');
      return (options.find((option) => option.attributes.has('selected')) || options[0])?.value || '';
    }
    return this.attributes.get('value') || '';
  }
  set value(value) { this.inputValue = value; }
  append(...nodes) {
    for (const value of nodes) {
      const node = value instanceof DomNode ? value : new DomNode('#text', String(value));
      node.parent = this;
      this.children.push(node);
    }
  }
  replaceChildren(...nodes) {
    for (const child of this.children) child.parent = null;
    this.children = [];
    if (this.tag === 'select') this.inputValue = undefined;
    this.append(...nodes);
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
    if (['hidden', 'disabled', 'checked'].includes(name)) this[name] = true;
    if (name.startsWith('data-')) this.dataset[name.slice(5)] = String(value);
  }
  removeAttribute(name) { this.attributes.delete(name); }
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }
  matches(selector) {
    const parts = selector.trim().split(/\s+/);
    const match = (node, part) => {
      if (node.tag === '#text') return false;
      const tag = /^[\w-]+/.exec(part)?.[0];
      if (tag && tag !== node.tag) return false;
      if ([...part.matchAll(/#([\w-]+)/g)].some(([, id]) => id !== node.id)) return false;
      if ([...part.matchAll(/\.([\w-]+)/g)].some(([, name]) => !node.className.split(/\s+/).includes(name))) return false;
      if ([...part.matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)].some(([, name, value]) => value === undefined ? !node.attributes.has(name) : node.attributes.get(name) !== value)) return false;
      return !part.endsWith(':checked') || node.checked;
    };
    if (!match(this, parts.pop())) return false;
    let parent = this.parent;
    while (parts.length) {
      const part = parts.pop();
      while (parent && !match(parent, part)) parent = parent.parent;
      if (!parent) return false;
      parent = parent.parent;
    }
    return true;
  }
  querySelectorAll(selector) {
    const found = [];
    const visit = (node) => {
      for (const child of node.children) {
        if (selector.split(',').some((part) => child.matches(part))) found.push(child);
        visit(child);
      }
    };
    visit(this);
    return found;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) {
    let node = this;
    while (node && !node.matches(selector)) node = node.parent;
    return node;
  }
  focus() {}
  showModal() { this.open = true; }
  close() { this.open = false; }
  reset() {
    for (const control of this.querySelectorAll('input, select, textarea')) {
      control.inputValue = undefined;
      control.checked = control.attributes.has('checked');
      control.files = [];
    }
  }
}

function makeDocument() {
  const root = new DomNode('document');
  const stack = [root];
  const voidTags = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr']);
  for (const [token] of HTML.matchAll(/<!--[\s\S]*?-->|<![^>]*>|<\/[^>]+>|<[^>]+>|[^<]+/g)) {
    if (/^<!/.test(token)) continue;
    if (/^<\//.test(token)) {
      stack.pop();
    } else if (token.startsWith('<')) {
      const [, tag, attributes] = /^<([\w-]+)([^>]*)>/.exec(token);
      const node = new DomNode(tag);
      for (const [, name, value] of attributes.matchAll(/([^\s=]+)(?:="([^"]*)")?/g)) node.setAttribute(name, value || '');
      stack.at(-1).append(node);
      if (!voidTags.has(tag)) stack.push(node);
    } else {
      stack.at(-1).append(new DomNode('#text', token));
    }
  }
  root.createElement = (tag) => new DomNode(tag);
  root.createElementNS = (_namespace, tag) => new DomNode(tag);
  root.createTextNode = (text) => new DomNode('#text', text);
  root.documentElement = root.querySelector('html');
  root.head = root.querySelector('head');
  return root;
}

const response = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(body) });
const chart = (email) => ({
  ok: true, title: `Pipeline by state (${email === MANAGER ? 'manager' : 'Texas'})`, visualType: 'clusteredBarChart',
  dimension: { table: 'Accounts', column: 'State' }, measure: { table: 'Opportunities', name: 'Pipeline Value' },
  preview: { rows: (email === MANAGER ? ['Texas', 'New Mexico', 'Georgia'] : ['Texas']).map((label) => ({ label, value: 10000, display: '$10,000' })) },
});

// Only the module import and automatic startup are adapted; every callback and renderer is the real app.js.
async function client({ hash = '#home', live = false } = {}) {
  const document = makeDocument();
  const location = { hash, pathname: '/', search: '', assign() {} };
  const history = { replaceState(_state, _title, url) { location.hash = new URL(url, 'http://fabrikam.localhost').hash; } };
  let identity = MANAGER;
  const calls = [];
  const holds = [];
  const frames = [];
  const timers = new Map();
  let nextTimer = 0;
  const startTimer = (fn) => { const id = ++nextTimer; timers.set(id, fn); return id; };
  const me = (email) => ({
    email, name: email === MANAGER ? 'Manager' : 'Texas rep', company: 'Fabrikam', product: 'HiCRM', status: 'ready',
    role: email === MANAGER ? 'manager' : 'rep', roleName: email === MANAGER ? 'Sales manager' : 'Sales rep',
    territories: email === MANAGER ? null : ['Texas'], demo: !live, personaSwitcher: true,
    features: { crm: true, reports: true, authoring: true, ask: true, data: true },
    reportPermissions: { view: true, edit: true, create: true }, examples: [`${email === MANAGER ? 'Manager' : 'Texas'} pipeline`],
  });
  const account = (id) => ({
    id, name: id === 'georgia' ? 'Georgia confidential account' : 'Texas account', state: id === 'georgia' ? 'Georgia' : 'Texas',
    opportunities: [{ name: `${id} deal`, stage: 'Prospecting', amount: 10000, closeDate: '2026-10-30' }],
    activities: [{ subject: `${id} private meeting`, date: '2026-10-07', type: 'Meeting' }],
    contacts: [{ firstName: id, lastName: 'Contact', email: `${id}@customer.example` }],
  });
  const resultFor = (call) => {
    const { route, method, body, identity: email } = call;
    const manager = email === MANAGER;
    const label = manager ? 'Manager Georgia' : 'Texas';
    if (route === '/api/persona' || (route === '/api/session' && method === 'POST')) {
      identity = body.email;
      return response({});
    }
    if (route === '/api/session' && method === 'DELETE') { identity = null; return response({}); }
    if (route === '/api/site') return response({ mode: 'customer', product: 'HiCRM', company: 'Fabrikam' });
    if (route === '/api/me') return email ? response(me(email)) : response({ error: 'Sign in' }, 401);
    if (route === '/api/personas') return response({ current: email, companies: [{ company: 'Fabrikam', here: true, personas: [me(MANAGER), me(REP)] }] });
    if (route === '/api/me/crm/options') return response({
      territories: manager ? ['Texas', 'New Mexico', 'Georgia'] : ['Texas'], industries: [label],
      reps: [{ id: email, name: label }], stages: ['Prospecting', 'Closed Won'], openStages: ['Prospecting'], activityTypes: ['Meeting'],
    });
    if (route === '/api/me/reports') return response({ reports: [{ id: 'sales', name: `${label} report` }], models: [{ id: `${label} model` }] });
    if (route === '/api/me/embed') return response({
      kind: body.mode === 'create' ? 'create' : 'report', mode: body.mode, reportId: body.reportId, datasetId: body.datasetId,
      name: `${label} report`, demo: !live, accessToken: `${label} token`, tokenId: `${label} token-id`,
      embedUrl: 'https://app.powerbi.com/reportEmbed', expiresInSeconds: 1800,
    });
    if (route === '/api/me/reports/describe') return response(chart(email));
    if (route === '/api/me/reports/usage' || route === '/api/me/requests' || route === '/api/me/uploads') return response({});
    if (route === '/api/me/crm/summary') return response({ pipelineValue: manager ? 90000 : 10000, openOpportunities: 1, accounts: manager ? 2 : 1, winRateThisYear: 50 });
    if (route === '/api/me/crm/accounts') return response(method === 'POST' ? { id: 'created', name: body.name } : { rows: manager ? [account('georgia'), account('texas')] : [account('texas')], total: manager ? 2 : 1 });
    if (route.startsWith('/api/me/crm/accounts/')) {
      const id = route.split('/').at(-1);
      return !manager && id !== 'texas' ? response({ error: 'Account not found' }, 404) : response(account(id));
    }
    if (route === '/api/me/crm/opportunities') return response({ rows: [{ id: 'deal', name: `${label} deal`, accountId: 'texas', accountName: `${label} account`, stage: 'Prospecting', amount: 10000, closeDate: '2026-10-30' }], total: 1 });
    if (route === '/api/me/crm/activities') return response({ rows: [{ id: 'activity', subject: `${label} meeting`, accountId: 'texas', accountName: `${label} account`, date: '2026-10-07', type: 'Meeting' }], total: 1 });
    if (route === '/api/me/crm/lookup/accounts') return response(manager ? [account('georgia')] : [account('texas')]);
    if (route.startsWith('/api/me/crm/opportunities/') || route.startsWith('/api/me/crm/activities/')) return response({ name: `${label} updated`, stage: body.stage });
    if (route === '/api/me/data') return response([{ name: `${label} upload`, source: 'File', rows: 1 }]);
    if (route === '/api/me/imports/web') return response({ name: `${label} web source` });
    if (route === '/api/me/ask') return response({ answer: `${label} answer`, source: 'quick' });
    throw new Error(`Unexpected request: ${method} ${call.path}`);
  };
  const fetch = async (path, init = {}) => {
    const call = { path, route: new URL(path, 'http://fabrikam.localhost').pathname, method: init.method || 'GET', body: init.body && typeof init.body === 'string' ? JSON.parse(init.body) : init.body, identity };
    calls.push(call);
    const result = resultFor(call);
    const hold = holds.find((item) => !item.used && item.route === call.route && item.method === call.method);
    if (!hold) return result;
    hold.used = true;
    hold.result = result;
    hold.started.resolve(call);
    return hold.gate.promise;
  };
  const defer = (route, method = 'GET') => {
    const hold = { route, method, gate: deferred(), started: deferred() };
    holds.push(hold);
    return {
      started: hold.started.promise,
      reply: (body, status = 200) => hold.gate.resolve(body === undefined ? hold.result : response(body, status)),
      fail: (message = 'Old network failure') => hold.gate.reject(new Error(message)),
    };
  };
  const powerbi = {
    reset() {},
    embed(canvas, config) {
      const listeners = new Map();
      const frame = {
        config, tokens: [],
        on(type, callback) {
          if (!listeners.has(type)) listeners.set(type, []);
          listeners.get(type).push(callback);
        },
        emit: async (type, detail = {}) => { await Promise.all((listeners.get(type) || []).map((callback) => callback({ detail }))); },
        getCorrelationId: async () => `correlation-${config.accessToken}`,
        setAccessToken: async (token) => { frame.tokens.push(token); },
      };
      frames.push(frame);
      canvas.textContent = config.accessToken;
      return frame;
    },
    createReport(canvas, config) { return this.embed(canvas, config); },
  };
  const window = new DomNode('window');
  window.powerbi = powerbi;
  window['powerbi-client'] = { models: { TokenType: { Embed: 1 }, Permissions: { Read: 0, ReadWrite: 1, All: 2 }, ViewMode: { View: 0, Edit: 1 } } };
  const context = createContext({
    document, window, location, history, Node: DomNode, fetch, URLSearchParams, performance, TextEncoder,
    TOKEN_CHECK_MS, refreshTimeOf, setTimeout: startTimer, setInterval: startTimer,
    clearTimeout: (id) => timers.delete(id), clearInterval: (id) => timers.delete(id),
  });
  const source = readFileSync(APP, 'utf8').replace(/^import .*'\.\/embed-token\.js';\r?\n/m, '').replace(/\bboot\(\);\s*$/, '');
  new Script(`'use strict';\n${source}\nglobalThis.app = { state, boot, render, viewAs, ask, openReport, showSignIn, renderViewAs, fieldControl };`, { filename: APP.pathname }).runInContext(context);
  const app = context.app;
  const node = (selector) => {
    const found = document.querySelector(selector);
    assert.ok(found, `DOM selector exists: ${selector}`);
    return found;
  };
  const fire = async (selector, type, extra = {}) => {
    const target = node(selector);
    const event = { target, submitter: target.querySelector('button'), preventDefault() {}, ...extra };
    await Promise.all((target.listeners.get(type) || []).map((callback) => callback(event)));
    await tick();
  };
  await app.boot();
  await tick();
  return { app, node, fire, defer, frames, calls, timers, location };
}

test('obsolete live embed and assistant responses cannot restore a manager after View as', async () => {
  const c = await client({ hash: '#reports', live: true });
  const embed = c.defer('/api/me/embed', 'POST');
  const answer = c.defer('/api/me/ask', 'POST');
  const opening = c.app.openReport('sales', 'view');
  const asking = c.app.ask('Manager question');
  await Promise.all([embed.started, answer.started]);
  await c.app.viewAs(REP);
  await c.app.ask('Texas question');
  const frame = c.app.state.report.embedded;
  const embeds = c.frames.length;
  embed.reply();
  answer.reply();
  await Promise.all([opening, asking]);
  assert.equal(c.frames.length, embeds, 'the manager token is never embedded after the switch');
  assert.equal(c.app.state.report.embedded, frame);
  assert.equal(frame.config.accessToken, 'Texas token');
  assert.deepEqual(plain(c.app.state.conversation).map((turn) => turn.text), ['Texas question', 'Texas answer']);
  assert.doesNotMatch(c.node('#conversation').textContent, /Manager|Georgia/);
});

test('obsolete assistant errors and finally handlers cannot replace or enable a new pending conversation', async () => {
  const c = await client();
  const old = c.defer('/api/me/ask', 'POST');
  const asking = c.app.ask('Manager question');
  await old.started;
  await c.app.viewAs(REP);
  const fresh = c.defer('/api/me/ask', 'POST');
  const current = c.app.ask('Texas question');
  await fresh.started;
  old.reply({ error: 'Manager private error' }, 503);
  await asking;
  assert.equal(c.node('#ask-form button').disabled, true);
  assert.deepEqual(plain(c.app.state.conversation).map((turn) => turn.text), ['Texas question', 'Looking…']);
  fresh.reply();
  await current;
  assert.equal(c.node('#ask-form button').disabled, false);
  assert.equal(c.app.state.conversation.at(-1).text, 'Texas answer');
});

for (const path of ['/api/site', '/api/me', '/api/me/crm/options']) {
  test(`obsolete boot response from ${path} cannot replace the new identity or its metadata`, async () => {
    const c = await client();
    const old = c.defer(path);
    const booting = c.app.boot();
    await old.started;
    await c.app.viewAs(REP);
    old.reply(path === '/api/site' ? { mode: 'customer', product: 'Manager private CRM', company: 'Manager private company' } : undefined);
    await booting;
    assert.equal(c.app.state.me?.email, REP);
    assert.equal(c.app.state.site.company, 'Fabrikam');
    assert.deepEqual(plain(c.app.state.options.territories), ['Texas']);
    assert.doesNotMatch(c.node('#accounts-industry').textContent, /Manager|Georgia/);
  });
}

for (const transition of ['sign-out/sign-in', 'sign-in']) {
  test(`${transition} invalidates in-flight assistant results from the previous session`, async () => {
    const c = await client();
    const old = c.defer('/api/me/ask', 'POST');
    const asking = c.app.ask('Manager question');
    await old.started;
    if (transition === 'sign-out/sign-in') await c.fire('#sign-out', 'click');
    c.node('#email').value = REP;
    await c.fire('#signin-form', 'submit');
    await c.app.ask('Texas question');
    old.reply();
    await asking;
    assert.equal(c.app.state.me?.email, REP);
    assert.deepEqual(plain(c.app.state.conversation).map((turn) => turn.text), ['Texas question', 'Texas answer']);
  });
}

for (const [view, path, selector] of [
  ['home', '/api/me/crm/summary', '#kpi-pipeline'],
  ['accounts', '/api/me/crm/accounts', '#accounts-rows'],
  ['opportunities', '/api/me/crm/opportunities', '#opportunities-rows'],
  ['activities', '/api/me/crm/activities', '#activities-rows'],
  ['data', '/api/me/data', '#datasets'],
  ['reports', '/api/me/reports', '#report-list'],
]) {
  test(`obsolete ${view} responses cannot redraw manager-scoped data after View as`, async () => {
    const c = await client({ hash: `#${view}` });
    const old = c.defer(path);
    const rendering = c.app.render();
    await old.started;
    await c.app.viewAs(REP);
    const current = c.node(selector).textContent;
    assert.ok(current, 'the new identity has rendered');
    old.reply();
    await rendering;
    assert.equal(c.node(selector).textContent, current);
    assert.doesNotMatch(c.node(selector).textContent, /Manager|Georgia/);
  });
}

test('obsolete 401s cannot sign out a new persona, while current 401s still show sign-in', async () => {
  const c = await client({ hash: '#reports' });
  const old = c.defer('/api/me/reports');
  const rendering = c.app.render();
  await old.started;
  await c.app.viewAs(REP);
  old.reply({ error: 'Old session expired' }, 401);
  await rendering;
  assert.equal(c.app.state.me?.email, REP);
  assert.equal(c.node('#signin').hidden, true);
  const fresh = c.defer('/api/me/reports');
  const current = c.app.render();
  await fresh.started;
  fresh.reply({ error: 'Current session expired' }, 401);
  await current;
  assert.equal(c.app.state.me, null);
  assert.equal(c.node('#signin').hidden, false);
  assert.equal(c.node('#canvas').textContent, '');
});

for (const outcome of ['HTTP error', 'network error']) {
  test(`obsolete embed ${outcome} cannot replace the new report canvas with a private error`, async () => {
    const c = await client({ hash: '#reports', live: true });
    const old = c.defer('/api/me/embed', 'POST');
    const opening = c.app.openReport('sales', 'view');
    await old.started;
    await c.app.viewAs(REP);
    if (outcome === 'HTTP error') old.reply({ error: 'Manager private embed error' }, 503);
    else old.fail('Manager private network error');
    await opening;
    assert.equal(c.node('#canvas').textContent, 'Texas token');
  });
}

for (const outcome of ['success', 'HTTP error', 'network error']) {
  test(`obsolete token refresh ${outcome} cannot update a token, stop a new timer or show an error`, async () => {
    const c = await client({ hash: '#reports', live: true });
    const oldFrame = c.app.state.report.embedded;
    const old = c.defer('/api/me/embed', 'POST');
    c.app.state.report.refreshAt = 0;
    const refreshing = c.app.state.report.checkToken();
    await old.started;
    await c.app.viewAs(REP);
    const frame = c.app.state.report.embedded;
    const timer = c.app.state.report.timer;
    if (outcome === 'success') old.reply();
    else if (outcome === 'HTTP error') old.reply({ error: 'Manager expired' }, 503);
    else old.fail();
    await refreshing;
    assert.deepEqual(oldFrame.tokens, []);
    assert.equal(c.app.state.report.embedded, frame);
    assert.equal(c.app.state.report.tokenId, 'Texas token-id');
    assert.ok(c.timers.has(timer), 'the new report still refreshes');
    assert.equal(c.node('#toast').hidden, true);
    c.app.state.report.refreshAt = 0;
    await c.app.state.report.checkToken();
    assert.deepEqual(frame.tokens, ['Texas token'], 'the new report can still refresh');
  });
}

test('a token SDK promise completing after View as cannot update the new report state', async () => {
  const c = await client({ hash: '#reports', live: true });
  const oldFrame = c.app.state.report.embedded;
  const started = deferred();
  const completion = deferred();
  oldFrame.setAccessToken = async () => { started.resolve(); await completion.promise; };
  c.app.state.report.refreshAt = 0;
  const refreshing = c.app.state.report.checkToken();
  await started.promise;
  await c.app.viewAs(REP);
  completion.resolve();
  await refreshing;
  assert.equal(c.app.state.report.tokenId, 'Texas token-id');
});

test('obsolete report events and delayed correlation IDs cannot save, log or alter the new report', async () => {
  const c = await client({ hash: '#reports', live: true });
  const oldFrame = c.app.state.report.embedded;
  const correlation = deferred();
  oldFrame.getCorrelationId = () => correlation.promise;
  const rendering = oldFrame.emit('rendered');
  await c.app.viewAs(REP);
  const embeds = c.frames.length;
  await oldFrame.emit('error', { message: 'Manager report error' });
  assert.equal(c.node('#toast').hidden, true);
  await oldFrame.emit('saved', { reportObjectId: 'manager-copy', reportName: 'Manager private copy', saveAs: true });
  correlation.resolve('manager-correlation');
  await rendering;
  assert.equal(c.frames.length, embeds);
  assert.equal(c.app.state.report.current.reportId, 'sales');
  assert.equal(c.calls.filter((call) => call.route === '/api/me/reports/usage').length, 0);
  await c.app.state.report.embedded.emit('rendered');
  assert.equal(c.calls.filter((call) => call.route === '/api/me/reports/usage').length, 1, 'current events still work');
});

for (const outcome of ['success', 'error']) {
  test(`obsolete describe-chart ${outcome} cannot add a preview or change the new hint`, async () => {
    const c = await client({ hash: '#reports' });
    const old = c.defer('/api/me/reports/describe', 'POST');
    c.node('#describe-text').value = 'Manager pipeline by state';
    const describing = c.fire('#describe-form', 'submit');
    await old.started;
    await c.app.viewAs(REP);
    c.node('#describe-text').value = 'Texas pipeline by state';
    await c.fire('#describe-form', 'submit');
    const hint = c.node('#describe-hint').textContent;
    if (outcome === 'success') old.reply();
    else old.reply({ error: 'Manager chart error' }, 503);
    await describing;
    assert.equal(c.node('#describe-hint').textContent, hint);
    assert.equal(c.app.state.demoCharts.length, 1);
    assert.deepEqual(plain(c.app.state.demoCharts[0].preview.rows).map((row) => row.label), ['Texas']);
    assert.doesNotMatch(c.node('#canvas').textContent, /manager|Georgia|New Mexico/);
  });
}

test('live chart authoring stops before SDK mutations when an awaited page belongs to an obsolete identity', async () => {
  const c = await client({ hash: '#reports', live: true });
  await c.app.openReport('sales', 'edit');
  const frame = c.app.state.report.embedded;
  await frame.emit('loaded');
  const started = deferred();
  const page = deferred();
  let created = 0;
  frame.getActivePage = () => { started.resolve(); return page.promise; };
  c.node('#describe-text').value = 'Manager pipeline by state';
  const describing = c.fire('#describe-form', 'submit');
  await started.promise;
  await c.app.viewAs(REP);
  page.resolve({
    getVisuals: async () => [],
    createVisual: async () => {
      created += 1;
      return { visual: {
        getCapabilities: async () => ({ dataRoles: [{ kind: 0, name: 'Category' }, { kind: 1, name: 'Values' }] }),
        addDataField: async () => {}, setProperty: async () => {},
      } };
    },
  });
  await describing;
  assert.equal(created, 0);
  assert.doesNotMatch(c.node('#describe-hint').textContent, /manager/);
});

for (const [view, selector, path] of [
  ['opportunities', '#opportunities-rows select', '/api/me/crm/opportunities/deal'],
  ['activities', '#activities-rows input', '/api/me/crm/activities/activity'],
]) {
  test(`obsolete ${view} edits cannot show feedback in the new persona`, async () => {
    const c = await client({ hash: `#${view}` });
    const old = c.defer(path, 'PATCH');
    const editing = c.fire(selector, 'change');
    await old.started;
    await c.app.viewAs(REP);
    old.reply();
    await editing;
    assert.equal(c.node('#toast').hidden, true);
    assert.doesNotMatch(c.node(`#${view}-rows`).textContent, /Manager|Georgia/);
  });
}

test('obsolete record creation cannot navigate or close the new persona\'s dialog', async () => {
  const c = await client({ hash: '#accounts' });
  await c.fire('#new-account', 'click');
  c.node('#f-name').value = 'Manager confidential draft';
  const old = c.defer('/api/me/crm/accounts', 'POST');
  const saving = c.fire('#dialog-form', 'submit');
  await old.started;
  await c.app.viewAs(REP);
  await c.fire('#new-account', 'click');
  c.node('#f-name').value = 'Texas draft';
  old.reply();
  await saving;
  assert.equal(c.location.hash, '#accounts');
  assert.equal(c.node('#dialog').open, true);
  assert.equal(c.node('#f-name').value, 'Texas draft');
  assert.equal(c.node('#toast').hidden, true);
});

test('obsolete account lookups cannot retain previous-territory suggestions in a record form', async () => {
  const c = await client();
  const field = c.app.fieldControl({ name: 'accountId', label: 'Account', type: 'account' });
  c.node('#dialog-fields').append(field);
  const control = c.node('#f-accountId');
  const old = c.defer('/api/me/crm/lookup/accounts');
  control.value = 'Georgia';
  await c.fire('#f-accountId', 'input');
  c.timers.get([...c.timers.keys()].at(-1))();
  await old.started;
  await c.app.viewAs(REP);
  old.reply();
  await tick();
  assert.equal(control.dataset.matches, undefined);
});

test('obsolete web imports cannot reset new input or show previous-person feedback', async () => {
  const c = await client({ hash: '#data' });
  c.node('#web-url').value = 'https://manager.example/data.json';
  const old = c.defer('/api/me/imports/web', 'POST');
  const importing = c.fire('#web-form', 'submit');
  await old.started;
  await c.app.viewAs(REP);
  c.node('#web-url').value = 'https://texas.example/data.json';
  old.reply();
  await importing;
  assert.equal(c.node('#web-url').value, 'https://texas.example/data.json');
  assert.equal(c.node('#toast').hidden, true);
});

test('a file read started by the previous persona cannot upload its bytes as the new persona', async () => {
  const c = await client({ hash: '#data' });
  const reading = deferred();
  c.node('#upload-file').files = [{ name: 'manager.csv', arrayBuffer: () => reading.promise }];
  const uploading = c.fire('#upload-form', 'submit');
  await c.app.viewAs(REP);
  reading.resolve(new TextEncoder().encode('name\nmanager\n').buffer);
  await uploading;
  assert.equal(c.calls.filter((call) => call.route === '/api/me/uploads').length, 0);
  assert.equal(c.node('#upload-form button').disabled, false);
  assert.equal(c.node('#upload-form button').textContent, 'Upload');
});

test('View as resets an account-detail route and clears every previous account field immediately', async () => {
  const c = await client({ hash: '#accounts/georgia' });
  assert.match(c.node('#view-account').textContent, /Georgia confidential account|georgia private meeting/);
  const switching = c.app.viewAs(REP);
  assert.equal(c.location.hash, '#accounts');
  assert.equal(c.app.state.accountId, null);
  assert.equal(c.node('#account-title').textContent, '');
  for (const selector of ['#account-facts', '#account-deals', '#account-activities', '#account-contacts']) assert.equal(c.node(selector).textContent, '');
  await switching;
  assert.equal(c.node('#view-account').hidden, true);
  assert.match(c.node('#accounts-rows').textContent, /Texas account/);
  c.location.hash = '#accounts/georgia';
  await c.app.render();
  assert.equal(c.app.state.accountId, null);
  assert.doesNotMatch(c.node('#view-account').textContent, /Georgia confidential|georgia private|georgia@/);
});

for (const status of [403, 404]) {
  test(`account details disappear while loading and remain cleared after ${status}`, async () => {
    const c = await client({ hash: '#accounts/georgia' });
    const pending = c.defer('/api/me/crm/accounts/missing');
    c.location.hash = '#accounts/missing';
    const loading = c.app.render();
    await pending.started;
    assert.equal(c.app.state.accountId, null);
    assert.doesNotMatch(c.node('#view-account').textContent, /Georgia confidential|georgia deal|georgia private|georgia@/);
    assert.equal(c.node('#account-contact').disabled, true);
    pending.reply({ error: 'Not available' }, status);
    await loading;
    assert.equal(c.app.state.accountId, null);
    assert.equal(c.node('#account-title').textContent, 'Account unavailable');
    for (const selector of ['#account-facts', '#account-deals', '#account-activities', '#account-contacts']) assert.equal(c.node(selector).textContent, '');
    c.location.hash = '#accounts/texas';
    await c.app.render();
    assert.equal(c.app.state.accountId, 'texas');
    assert.equal(c.node('#account-title').textContent, 'Texas account');
    assert.equal(c.node('#account-contact').disabled, false);
  });
}

test('obsolete account-detail responses cannot repopulate cleared details after View as', async () => {
  const c = await client({ hash: '#accounts/georgia' });
  const old = c.defer('/api/me/crm/accounts/georgia');
  const rendering = c.app.render();
  await old.started;
  await c.app.viewAs(REP);
  old.reply();
  await rendering;
  assert.equal(c.app.state.accountId, null);
  assert.equal(c.node('#account-title').textContent, '');
  assert.doesNotMatch(c.node('#view-account').textContent, /Georgia confidential|georgia deal|georgia private|georgia@/);
});

for (const transition of ['View as', 'sign-out', 'sign-in']) {
  test(`demo chart caches are cleared at ${transition}, with new previews fetched only as Texas`, async () => {
    const c = await client({ hash: '#reports' });
    c.node('#describe-text').value = 'pipeline by state';
    await c.fire('#describe-form', 'submit');
    assert.match(c.node('#canvas').textContent, /Georgia/);
    if (transition === 'View as') await c.app.viewAs(REP);
    else if (transition === 'sign-out') await c.fire('#sign-out', 'click');
    else {
      c.node('#email').value = REP;
      await c.fire('#signin-form', 'submit');
    }
    assert.equal(c.app.state.demoCharts.length, 0);
    assert.doesNotMatch(c.node('#canvas').textContent, /Georgia|New Mexico|manager/);
    if (transition === 'sign-out') {
      c.node('#email').value = REP;
      await c.fire('#signin-form', 'submit');
    }
    c.location.hash = '#reports';
    await c.app.render();
    c.node('#describe-text').value = 'pipeline by state';
    await c.fire('#describe-form', 'submit');
    assert.deepEqual(plain(c.app.state.demoCharts[0].preview.rows).map((row) => row.label), ['Texas']);
    assert.equal(c.calls.filter((call) => call.route === '/api/me/reports/describe').at(-1).identity, REP);
    assert.doesNotMatch(c.node('#canvas').textContent, /Georgia|New Mexico|manager/);
  });
}
