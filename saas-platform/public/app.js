// The platform app, as the end customer sees it. It only calls /api/me/... and /api/session: the server decides which
// company the signed-in user belongs to and what that company can use (CRM, reports, report building, the assistant).
import { TOKEN_CHECK_MS, refreshTimeOf } from './embed-token.js';

const NAV = [
  { id: 'home', label: 'Home', feature: 'crm' },
  { id: 'accounts', label: 'Accounts', feature: 'crm' },
  { id: 'opportunities', label: 'Opportunities', feature: 'crm' },
  { id: 'activities', label: 'Activities', feature: 'crm' },
  { id: 'reports', label: 'Reports', feature: 'reports' },
  { id: 'data', label: 'Data', feature: 'data' },
];
const PAGE_SIZE = 25;
const SCHEMA = { column: 'http://powerbi.com/product/schema#column', measure: 'http://powerbi.com/product/schema#measure', property: 'http://powerbi.com/product/schema#property' };

const state = {
  identityGeneration: 0,
  me: null,
  options: null,
  setupTimer: null,
  offsets: { accounts: 0, opportunities: 0, activities: 0 },
  accountId: null,
  report: { list: [], models: [], current: null, embedded: null, mode: null, request: null, timer: null, ready: null, revision: 0 },
  demoCharts: [],
  conversation: [],
};

const $ = (selector) => document.querySelector(selector);
const currentIdentity = (generation) => generation === state.identityGeneration;
function requireIdentity(generation) {
  if (!currentIdentity(generation)) throw new Error('This request belongs to a previous sign-in.');
}
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const compactMoney = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 });
const count = new Intl.NumberFormat('en-US');
const shortDate = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
const fmtMoney = (n) => (n === null || n === undefined ? '—' : money.format(n));
const fmtDate = (iso) => (iso ? shortDate.format(new Date(`${String(iso).slice(0, 10)}T00:00:00Z`)) : '—');
const today = () => new Date().toISOString().slice(0, 10);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

async function api(path, { method = 'GET', body, raw, headers = {}, generation = state.identityGeneration } = {}) {
  requireIdentity(generation);
  const init = { method, headers: { ...headers } };
  if (method !== 'GET') init.headers['x-platform-client'] = 'web';
  if (raw !== undefined) init.body = raw;
  else if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers['content-type'] = 'application/json';
  }
  let res;
  let text;
  try {
    res = await fetch(path, init);
    text = await res.text();
  } catch (error) {
    requireIdentity(generation);
    throw error;
  }
  requireIdentity(generation);
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (res.status === 401 && path !== '/api/session') {
    showSignIn();
    throw Object.assign(new Error('Please sign in.'), { status: 401 });
  }
  if (!res.ok) throw Object.assign(new Error(data?.error || 'Something went wrong. Please try again.'), { status: res.status });
  return data;
}

const query = (params) => new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined)).toString();

let toastTimer;
function toast(message, kind = 'info') {
  const generation = state.identityGeneration;
  const node = $('#toast');
  node.textContent = message;
  node.className = kind === 'error' ? 'toast error' : 'toast';
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    if (currentIdentity(generation)) node.hidden = true;
  }, kind === 'error' ? 8000 : 4000);
}

const busyButtons = new Map();
async function withBusy(button, label, work) {
  const generation = state.identityGeneration;
  const original = button.textContent;
  const restore = () => {
    button.disabled = false;
    button.removeAttribute('aria-busy');
    button.textContent = original;
  };
  busyButtons.set(button, restore);
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  button.textContent = label;
  try {
    return await work();
  } finally {
    if (busyButtons.get(button) === restore) {
      busyButtons.delete(button);
      if (currentIdentity(generation)) restore();
    }
  }
}

function debounce(fn, ms = 250) {
  let timer;
  return (...args) => {
    const generation = state.identityGeneration;
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (currentIdentity(generation)) fn(...args);
    }, ms);
  };
}

const emptyRow = (columns, text) => el('tr', { class: 'empty' }, el('td', { colspan: columns }, text));
const loadingRow = (columns) => el('tr', { class: 'loading' }, el('td', { colspan: columns }, 'Loading…'));

function setProduct(name) {
  for (const node of document.querySelectorAll('.product-name')) node.textContent = name;
  document.title = name;
}

// The address decides the company before anyone signs in (platform/tenancy.js on the server): its logo, name and
// accent color. On the shared address, the signed-in person's company once they're in.
const THEME_PROPERTIES = ['--accent', '--accent-hover', '--accent-soft'];
async function applySite(generation = state.identityGeneration) {
  let site;
  try {
    site = await api('/api/site', { generation });
  } catch (error) {
    if (!currentIdentity(generation)) return;
    site = error.status === 404 ? { mode: 'unknown', product: 'Platform app' } : { mode: 'shared', product: 'Platform app' };
  }
  if (!currentIdentity(generation)) return;
  state.site = site;
  setProduct(site.product);
  for (const name of THEME_PROPERTIES) document.documentElement.style.removeProperty(name);
  for (const [name, value] of Object.entries(site.theme || {})) if (THEME_PROPERTIES.includes(name)) document.documentElement.style.setProperty(name, value);
  for (const id of ['#signin-logo', '#topbar-logo']) {
    const img = $(id);
    img.hidden = !site.logoUrl;
    if (site.logoUrl) img.src = site.logoUrl;
    else img.removeAttribute('src');
    img.closest('.brand').classList.toggle('has-logo', Boolean(site.logoUrl));
  }
  document.querySelector('link[rel="icon"]').href = site.logoUrl || 'data:,';
  if (site.company) document.title = `${site.company} · ${site.product}`;
  return site;
}

// "Find your company" sends people here with their email in the fragment, which never reaches a server.
const emailHint = /^#email=([^&]*)$/.exec(location.hash);
if (emailHint) {
  state.emailHint = decodeURIComponent(emailHint[1]);
  history.replaceState(null, '', location.pathname + location.search);
}

// Stage shown as text plus a shape, so it never depends on color alone.
function stageBadge(stage) {
  const kind = stage === 'Closed Won' ? 'won' : stage === 'Closed Lost' ? 'lost' : 'open';
  return el('span', { class: `stage ${kind}` }, el('span', { class: 'stage-mark', 'aria-hidden': 'true' }), stage);
}

// ---------- Session ----------

// Invalidate work before changing the session, including queued timers and SDK callbacks, not just fetch responses.
function resetIdentity() {
  state.identityGeneration += 1;
  clearTimeout(state.setupTimer);
  state.setupTimer = null;
  clearTimeout(toastTimer);
  $('#toast').hidden = true;
  for (const restore of busyButtons.values()) restore();
  busyButtons.clear();
  resetReport();
  Object.assign(state.report, { list: [], models: [], current: null });
  state.demoCharts = [];
  state.conversation = [];
  renderConversation();
  state.me = null;
  state.options = null;
  state.offsets = { accounts: 0, opportunities: 0, activities: 0 };
  clearAccount();
  if (/^#accounts\//.test(location.hash)) history.replaceState(null, '', `${location.pathname}${location.search}#accounts`);
  for (const id of [
    '#company', '#user-email', '#user-scope', '#nav', '#persona-select', '#suggestions',
    '#kpi-pipeline', '#kpi-pipeline-note', '#kpi-won', '#kpi-winrate', '#kpi-accounts', '#home-closing', '#home-upcoming',
    '#accounts-rows', '#accounts-pager', '#opportunities-rows', '#opportunities-totals', '#opportunities-pager', '#activities-rows', '#activities-pager',
    '#accounts-state', '#accounts-industry', '#opportunities-owner', '#activities-owner', '#activities-type',
    '#report-list', '#canvas', '#describe-hint', '#datasets', '#dialog-title', '#dialog-fields', '#dialog-error',
  ]) $(id).replaceChildren();
  for (const id of ['#accounts-filters', '#opportunities-filters', '#activities-filters', '#describe-form', '#ask-form', '#upload-form', '#web-form', '#request-form']) $(id).reset();
  $('#describe-hint').classList.remove('error');
  if ($('#dialog').open) $('#dialog').close();
  dialogSubmit = null;
  $('#ask-form button').disabled = false;
  $('#persona-select').disabled = false;
  $('#viewas').hidden = true;
  closeAssistant();
  for (const node of document.querySelectorAll('.view, .state')) node.hidden = true;
  $('#topbar').hidden = true;
  $('#main').hidden = true;
  $('#assistant-launcher').hidden = true;
  return state.identityGeneration;
}

function showSignIn() {
  resetIdentity();
  $('#signin').hidden = false;
  const site = state.site || { mode: 'shared' };
  // The platform's own address only finds the company; each company's address signs its people in.
  const finding = site.mode === 'platform';
  $('#signin-title').textContent = finding ? 'Find your company' : site.company ? `Sign in to ${site.company}` : 'Sign in';
  if (site.company) $('#signin-name').textContent = site.company;
  $('#password-field').hidden = finding;
  $('#signin-submit').textContent = finding ? 'Continue' : 'Sign in';
  $('#signin-form').hidden = site.mode === 'unknown';
  $('#signin-notice').hidden = site.mode !== 'unknown';
  $('#signin-notice').textContent = site.mode === 'unknown' ? "There's no company at this address. Check the link you were given." : '';
  $('#signin-help').textContent = finding
    ? "Enter your work email and we'll take you to your company's sign-in page."
    : "Your administrator gives you your password. Demo companies without named sign-ins don't need one. A real deployment signs you in with your company account.";
  if (state.emailHint) {
    $('#email').value = state.emailHint;
    state.emailHint = null;
  }
  (!finding && $('#email').value ? $('#password') : $('#email')).focus();
  renderPersonaPicker().catch(() => {});
}

$('#signin-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const email = $('#email').value.trim();
  const password = $('#password').value;
  if (!email) {
    toast('Enter your work email address.', 'error');
    return;
  }
  const generation = resetIdentity();
  await withBusy(event.submitter || event.target.querySelector('button'), state.site?.mode === 'platform' ? 'Finding…' : 'Signing in…', async () => {
    try {
      const result = await api('/api/session', { method: 'POST', body: { email, password }, generation });
      if (!currentIdentity(generation)) return;
      if (result?.url) {
        location.assign(`${result.url}#email=${encodeURIComponent(email)}`);
        return;
      }
      $('#password').value = '';
      await boot(generation);
    } catch (error) {
      if (!currentIdentity(generation)) return;
      showSignIn();
      toast(error.message, 'error');
    }
  });
});

$('#sign-out').addEventListener('click', async () => {
  const generation = resetIdentity();
  await api('/api/session', { method: 'DELETE', generation }).catch(() => {});
  if (!currentIdentity(generation)) return;
  location.hash = '';
  await applySite(generation);
  if (currentIdentity(generation)) showSignIn();
});

// ---------- View as: switch between a company's people, for demos and testing ----------

// The people who sign in at this address, and the other companies' addresses. Only when "View as" is available here:
// on this computer, outside production. Otherwise the server answers 404, and the page has the sign-in form only.
async function fetchPersonas(generation = state.identityGeneration) {
  try {
    return await api('/api/personas', { generation });
  } catch {
    return null;
  }
}

const seesText = (territories) => (territories === null ? 'every state' : territories.length ? `${territories.join(', ')} only` : 'no states yet');
const personaText = (p) => `${p.name}: ${p.roleName}, ${seesText(p.territories)}`;
const listWith = (nodes, separator) => nodes.flatMap((node, i) => (i ? [separator, node] : [node]));

// Signs in as that person, then shows the app as they see it: a report opens again with their own embed token, and
// nothing of the previous person's stays on screen (their conversation, the account they had open).
async function viewAs(email) {
  const generation = resetIdentity();
  try {
    await api('/api/persona', { method: 'POST', body: { email }, generation });
    if (currentIdentity(generation)) await boot(generation);
  } catch (error) {
    if (!currentIdentity(generation)) return;
    await boot(generation);
    throw error;
  }
}

function personaCard(persona, showCompany) {
  const card = el(
    'button',
    { type: 'button', class: 'persona-card', role: 'listitem', 'data-email': persona.email },
    el('span', { class: 'persona-role' }, showCompany ? `${persona.company} · ${persona.roleName}` : persona.roleName),
    el('span', { class: 'persona-name' }, persona.name),
    el('span', { class: 'persona-email' }, persona.email),
    el('span', { class: 'persona-sees' }, `Sees ${seesText(persona.territories)}`),
  );
  card.addEventListener('click', async () => {
    for (const other of document.querySelectorAll('.persona-card')) other.disabled = true;
    card.setAttribute('aria-busy', 'true');
    const switching = viewAs(persona.email);
    const generation = state.identityGeneration;
    try {
      await switching;
    } catch (error) {
      if (currentIdentity(generation)) toast(error.message, 'error');
    } finally {
      if (currentIdentity(generation)) {
        for (const other of document.querySelectorAll('.persona-card')) other.disabled = false;
        card.removeAttribute('aria-busy');
      }
    }
  });
  return card;
}

async function renderPersonaPicker(generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  const picker = $('#persona-picker');
  picker.hidden = true;
  $('#signin').classList.remove('picking');
  if (state.site?.mode === 'unknown') return;
  const listing = await fetchPersonas(generation);
  if (!currentIdentity(generation)) return;
  if (!listing || !$('#topbar').hidden) return;
  const here = listing.companies.filter((c) => c.here);
  const people = here.flatMap((c) => c.personas.map((p) => ({ ...p, company: c.company })));
  const others = listing.companies.filter((c) => !c.here && c.url);
  if (!people.length && !others.length) return;
  $('#persona-lede').textContent = people.length
    ? `Pick one of ${here.length === 1 ? `${here[0].company}'s` : "the companies'"} people to see the app, and its reports, the way they do. Each sales rep sees one state; the manager sees every state.`
    : 'Pick a company, then one of its people.';
  $('#persona-cards').replaceChildren(...people.map((p) => personaCard(p, here.length > 1)));
  $('#persona-cards').hidden = !people.length;
  const links = others.map((c) => el('a', { href: c.url }, c.company));
  $('#persona-elsewhere').replaceChildren(...(links.length ? [people.length ? 'Other companies, each at its own address: ' : 'Companies: ', ...listWith(links, ', ')] : []));
  $('#persona-elsewhere').hidden = !links.length;
  picker.hidden = false;
  $('#signin').classList.add('picking');
}

// The top bar's "View as" list: this company's people, then the other companies (each opens its own address). It
// names the person, so it takes the place of their name and email.
async function renderViewAs(generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  const box = $('#viewas');
  box.hidden = true;
  $('#user-email').hidden = false;
  if (!state.me?.personaSwitcher) return;
  const listing = await fetchPersonas(generation);
  if (!currentIdentity(generation)) return;
  if (!listing || !state.me) return;
  const here = listing.companies.filter((c) => c.here && c.personas.length);
  if (!here.some((c) => c.personas.some((p) => p.email === state.me.email))) return;
  const options = (c) => c.personas.map((p) => el('option', { value: p.email }, personaText(p)));
  const others = listing.companies.filter((c) => !c.here && c.url);
  $('#persona-select').replaceChildren(
    ...(here.length === 1 ? options(here[0]) : here.map((c) => el('optgroup', { label: c.company }, ...options(c)))),
    ...(others.length ? [el('optgroup', { label: 'Other companies' }, ...others.map((c) => el('option', { value: `url:${c.url}` }, `${c.company}: open its address`)))] : []),
  );
  $('#persona-select').value = state.me.email;
  box.hidden = false;
  $('#user-email').hidden = true;
}

$('#persona-select').addEventListener('change', async (event) => {
  const select = event.target;
  if (select.value.startsWith('url:')) {
    location.assign(select.value.slice(4));
    return;
  }
  const switching = viewAs(select.value);
  const generation = state.identityGeneration;
  select.disabled = true;
  try {
    await switching;
  } catch (error) {
    if (!currentIdentity(generation)) return;
    toast(error.message, 'error');
    if (state.me) select.value = state.me.email;
  } finally {
    if (currentIdentity(generation)) select.disabled = false;
  }
});

async function boot(generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  const site = await applySite(generation);
  if (!currentIdentity(generation)) return;
  if (site.mode === 'platform' || site.mode === 'unknown') {
    showSignIn();
    return;
  }
  let me;
  try {
    me = await api('/api/me', { generation });
  } catch (error) {
    if (!currentIdentity(generation)) return;
    showSignIn();
    if (error.status !== 401) toast(error.message, 'error');
    return;
  }
  if (!currentIdentity(generation)) return;
  state.me = me;
  $('#signin').hidden = true;
  $('#topbar').hidden = false;
  $('#main').hidden = false;
  $('#company').textContent = me.company;
  $('#user-email').textContent = me.name ? `${me.name} (${me.email})` : me.email;
  $('#user-email').title = $('#user-email').textContent;
  // Who sees what: managers see every territory, reps their own. The server enforces it; this just says so.
  $('#user-scope').textContent = `${me.roleName} · ${me.territories ? me.territories.join(', ') : 'All territories'}`;
  renderViewAs(generation).catch(() => {});
  renderNav();
  if (me.status !== 'ready') {
    showState(me.status);
    return;
  }
  const options = me.features.crm ? await api('/api/me/crm/options', { generation }).catch(() => null) : null;
  if (!currentIdentity(generation)) return;
  state.options = options;
  fillOptionLists();
  renderSuggestions();
  await render(generation);
}

function renderNav() {
  const available = NAV.filter((v) => state.me.features[v.feature]);
  $('#nav').replaceChildren(...available.map((v) => el('a', { href: `#${v.id}`, 'data-view': v.id }, v.label)));
}

function showState(status) {
  const generation = state.identityGeneration;
  for (const node of document.querySelectorAll('.view, .state')) node.hidden = true;
  $('#setting-up').hidden = status !== 'setting-up';
  $('#unavailable').hidden = status === 'setting-up';
  $('#assistant-launcher').hidden = true;
  clearTimeout(state.setupTimer);
  if (status === 'setting-up') state.setupTimer = setTimeout(() => {
    if (currentIdentity(generation)) boot(generation);
  }, 5000);
}

function fillOptionLists() {
  const opts = state.options;
  if (!opts) return;
  const options = (list, map = (v) => [v, v]) => list.map((item) => el('option', { value: map(item)[0] }, map(item)[1]));
  $('#accounts-industry').replaceChildren(el('option', { value: '' }, 'All industries'), ...options(opts.industries));
  $('#accounts-state').replaceChildren(el('option', { value: '' }, 'All territories'), ...options(opts.territories || []));
  $('#accounts-state').hidden = (opts.territories || []).length < 2;
  for (const id of ['#opportunities-owner', '#activities-owner']) $(id).replaceChildren(el('option', { value: '' }, 'Everyone'), ...options(opts.reps, (r) => [r.id, r.name]));
  $('#activities-type').replaceChildren(el('option', { value: '' }, 'All types'), ...options(opts.activityTypes));
}

// ---------- Routing ----------

function parseRoute() {
  const [view, id] = location.hash.replace(/^#/, '').split('/');
  const available = NAV.filter((v) => state.me.features[v.feature]).map((v) => v.id);
  if (view === 'accounts' && id && available.includes('accounts')) return { view: 'account', id: decodeURIComponent(id) };
  if (available.includes(view)) return { view, id: id ? decodeURIComponent(id) : null };
  return { view: available[0] || null, id: null };
}

async function render(generation = state.identityGeneration) {
  if (!currentIdentity(generation) || !state.me || state.me.status !== 'ready') return;
  const { view, id } = parseRoute();
  for (const node of document.querySelectorAll('.view, .state')) node.hidden = true;
  if (!view) {
    showState('unavailable');
    return;
  }
  const navView = view === 'account' ? 'accounts' : view;
  for (const link of document.querySelectorAll('#nav a')) {
    if (link.dataset.view === navView) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  if (view !== 'reports') resetReport();
  $(`#view-${view}`).hidden = false;
  $('#assistant-launcher').hidden = !(state.me.features.ask && ['home', 'reports'].includes(view));
  if ($('#assistant-launcher').hidden) closeAssistant();
  try {
    if (view === 'home') await loadHome(generation);
    if (view === 'accounts') await loadAccounts(generation);
    if (view === 'account') await loadAccount(id, generation);
    if (view === 'opportunities') await loadOpportunities(generation);
    if (view === 'activities') await loadActivities(generation);
    if (view === 'reports') await loadReports(id, generation);
    if (view === 'data') await loadData(generation);
  } catch (error) {
    if (!currentIdentity(generation)) return;
    if (error.status !== 401) toast(error.message, 'error');
  }
}

window.addEventListener('hashchange', () => render());

// ---------- Home ----------

async function loadHome(generation = state.identityGeneration) {
  const [summary, closing, upcoming] = await Promise.all([
    api('/api/me/crm/summary', { generation }),
    api(`/api/me/crm/opportunities?${query({ status: 'open', closeFrom: today(), sort: 'close', direction: 'asc', limit: 6 })}`, { generation }),
    api(`/api/me/crm/activities?${query({ status: 'open', direction: 'asc', limit: 6 })}`, { generation }),
  ]);
  if (!currentIdentity(generation)) return;
  $('#kpi-pipeline').textContent = fmtMoney(summary.pipelineValue);
  $('#kpi-pipeline-note').textContent = `across ${count.format(summary.openOpportunities)} open opportunities`;
  $('#kpi-won').textContent = compactMoney.format(summary.wonThisYear || 0);
  $('#kpi-winrate').textContent = summary.winRateThisYear === null ? '—' : `${summary.winRateThisYear}%`;
  $('#kpi-accounts').textContent = count.format(summary.accounts);
  $('#home-closing').replaceChildren(
    ...(closing.rows.length
      ? closing.rows.map((o) =>
          el('tr', {}, el('td', {}, el('a', { href: `#accounts/${encodeURIComponent(o.accountId)}` }, o.name), el('span', { class: 'sub' }, o.accountName)), el('td', {}, stageBadge(o.stage)), el('td', { class: 'num' }, fmtMoney(o.amount)), el('td', { class: 'date' }, fmtDate(o.closeDate))),
        )
      : [emptyRow(4, 'No open opportunities.')]),
  );
  $('#home-upcoming').replaceChildren(
    ...(upcoming.rows.length
      ? upcoming.rows.map((a) => el('tr', {}, el('td', { class: 'date' }, fmtDate(a.date)), el('td', {}, el('span', { class: 'type' }, a.type)), el('td', {}, a.subject, el('span', { class: 'sub' }, a.accountName))))
      : [emptyRow(3, 'Nothing planned.')]),
  );
}

// ---------- Accounts ----------

function pager(container, key, total, reload) {
  const generation = state.identityGeneration;
  const offset = state.offsets[key];
  const end = Math.min(offset + PAGE_SIZE, total);
  const go = (next) => {
    if (!currentIdentity(generation)) return;
    state.offsets[key] = next;
    reload(generation).catch((error) => {
      if (currentIdentity(generation)) toast(error.message, 'error');
    });
  };
  container.replaceChildren(
    el('span', {}, total ? `${count.format(offset + 1)}–${count.format(end)} of ${count.format(total)}` : ''),
    el('button', { class: 'button', type: 'button', disabled: offset === 0, onclick: () => go(Math.max(0, offset - PAGE_SIZE)) }, 'Previous'),
    el('button', { class: 'button', type: 'button', disabled: end >= total, onclick: () => go(offset + PAGE_SIZE) }, 'Next'),
  );
}

async function loadAccounts(generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  const body = $('#accounts-rows');
  body.replaceChildren(loadingRow(6));
  const [sort, direction] = $('#accounts-sort').value.split(':');
  const result = await api(`/api/me/crm/accounts?${query({ search: $('#accounts-search').value.trim(), state: $('#accounts-state').value, industry: $('#accounts-industry').value, sort, direction, limit: PAGE_SIZE, offset: state.offsets.accounts })}`, { generation });
  if (!currentIdentity(generation)) return;
  body.replaceChildren(
    ...(result.rows.length
      ? result.rows.map((a) =>
          el(
            'tr',
            {},
            el('td', {}, el('a', { href: `#accounts/${encodeURIComponent(a.id)}` }, a.name)),
            el('td', {}, a.industry || '—'),
            el('td', {}, [a.city, a.state].filter(Boolean).join(', ') || a.country || '—'),
            el('td', {}, a.ownerName || '—'),
            el('td', { class: 'num' }, count.format(a.openOpportunities || 0)),
            el('td', { class: 'num' }, fmtMoney(a.pipelineValue)),
          ),
        )
      : [emptyRow(6, 'No accounts match.')]),
  );
  pager($('#accounts-pager'), 'accounts', result.total, loadAccounts);
}

const reloadAccounts = () => {
  const generation = state.identityGeneration;
  state.offsets.accounts = 0;
  loadAccounts(generation).catch((error) => {
    if (currentIdentity(generation)) toast(error.message, 'error');
  });
};
$('#accounts-search').addEventListener('input', debounce(reloadAccounts));
$('#accounts-state').addEventListener('change', reloadAccounts);
$('#accounts-industry').addEventListener('change', reloadAccounts);
$('#accounts-sort').addEventListener('change', reloadAccounts);
$('#accounts-filters').addEventListener('submit', (event) => event.preventDefault());

function clearAccount() {
  state.accountId = null;
  for (const id of ['#account-title', '#account-facts', '#account-deals', '#account-activities', '#account-contacts']) $(id).replaceChildren();
  for (const id of ['#account-deal', '#account-log', '#account-contact']) $(id).disabled = true;
}

async function loadAccount(id, generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  clearAccount();
  $('#account-title').textContent = 'Loading…';
  let account;
  try {
    account = await api(`/api/me/crm/accounts/${encodeURIComponent(id)}`, { generation });
  } catch (error) {
    if (currentIdentity(generation)) {
      clearAccount();
      $('#account-title').textContent = 'Account unavailable';
    }
    throw error;
  }
  if (!currentIdentity(generation)) return;
  state.accountId = id;
  for (const button of ['#account-deal', '#account-log', '#account-contact']) $(button).disabled = false;
  $('#account-title').textContent = account.name;
  const facts = [
    ['Territory', account.state || 'Unassigned'],
    ['Industry', account.industry],
    ['Location', [account.city, account.state, account.country].filter(Boolean).join(', ')],
    ['Owner', account.ownerName],
    ['Company revenue', account.annualRevenue ? compactMoney.format(account.annualRevenue) : null],
    ['Employees', account.employees ? count.format(account.employees) : null],
  ];
  $('#account-facts').replaceChildren(...facts.map(([label, value]) => el('div', {}, el('dt', {}, label), el('dd', {}, value || '—'))));
  $('#account-deals').replaceChildren(
    ...(account.opportunities.length
      ? account.opportunities.map((o) => el('tr', {}, el('td', {}, o.name), el('td', {}, stageBadge(o.stage)), el('td', { class: 'num' }, fmtMoney(o.amount)), el('td', { class: 'date' }, fmtDate(o.closeDate)), el('td', {}, o.ownerName || '—')))
      : [emptyRow(5, 'No opportunities yet.')]),
  );
  $('#account-activities').replaceChildren(
    ...(account.activities.length
      ? account.activities.slice(0, 12).map((a) => el('tr', {}, el('td', { class: 'date' }, fmtDate(a.date)), el('td', {}, el('span', { class: 'type' }, a.type)), el('td', {}, a.subject), el('td', {}, a.completed ? 'Done' : 'Planned')))
      : [emptyRow(4, 'No activities yet.')]),
  );
  $('#account-contacts').replaceChildren(
    ...(account.contacts.length
      ? account.contacts.map((c) => el('tr', {}, el('td', {}, [c.firstName, c.lastName].filter(Boolean).join(' '), el('span', { class: 'sub' }, c.title || '')), el('td', {}, c.email ? el('a', { href: `mailto:${c.email}` }, c.email) : '—')))
      : [emptyRow(2, 'No contacts yet.')]),
  );
}

// ---------- Opportunities ----------

async function loadOpportunities(generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  const body = $('#opportunities-rows');
  body.replaceChildren(loadingRow(6));
  const status = $('#opportunities-status').value;
  const result = await api(`/api/me/crm/opportunities?${query({ search: $('#opportunities-search').value.trim(), status, ownerId: $('#opportunities-owner').value, sort: 'close', direction: status === 'open' ? 'asc' : 'desc', limit: PAGE_SIZE, offset: state.offsets.opportunities })}`, { generation });
  if (!currentIdentity(generation)) return;
  $('#opportunities-totals').textContent = `${count.format(result.total)} ${status === 'open' ? 'open ' : status === 'won' ? 'won ' : status === 'lost' ? 'lost ' : ''}opportunities`;
  body.replaceChildren(
    ...(result.rows.length
      ? result.rows.map((o) => {
          const select = el('select', { 'aria-label': `Stage of ${o.name}` }, ...state.options.stages.map((s) => el('option', { value: s, selected: s === o.stage }, s)));
          select.addEventListener('change', async () => {
            if (!currentIdentity(generation)) return;
            select.disabled = true;
            try {
              const updated = await api(`/api/me/crm/opportunities/${encodeURIComponent(o.id)}`, { method: 'PATCH', body: { stage: select.value }, generation });
              if (!currentIdentity(generation)) return;
              toast(`${updated.name} moved to ${updated.stage}.`);
            } catch (error) {
              if (!currentIdentity(generation)) return;
              select.value = o.stage;
              toast(error.message, 'error');
            } finally {
              if (currentIdentity(generation)) select.disabled = false;
            }
          });
          return el('tr', {}, el('td', {}, o.name), el('td', {}, el('a', { href: `#accounts/${encodeURIComponent(o.accountId)}` }, o.accountName)), el('td', {}, select), el('td', { class: 'num' }, fmtMoney(o.amount)), el('td', { class: 'date' }, fmtDate(o.closeDate)), el('td', {}, o.ownerName || '—'));
        })
      : [emptyRow(6, 'No opportunities match.')]),
  );
  pager($('#opportunities-pager'), 'opportunities', result.total, loadOpportunities);
}

const reloadOpportunities = () => {
  const generation = state.identityGeneration;
  state.offsets.opportunities = 0;
  loadOpportunities(generation).catch((error) => {
    if (currentIdentity(generation)) toast(error.message, 'error');
  });
};
$('#opportunities-search').addEventListener('input', debounce(reloadOpportunities));
$('#opportunities-status').addEventListener('change', reloadOpportunities);
$('#opportunities-owner').addEventListener('change', reloadOpportunities);
$('#opportunities-filters').addEventListener('submit', (event) => event.preventDefault());

// ---------- Activities ----------

async function loadActivities(generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  const body = $('#activities-rows');
  body.replaceChildren(loadingRow(6));
  const status = document.querySelector('input[name="activities-status"]:checked').value;
  const result = await api(`/api/me/crm/activities?${query({ status, type: $('#activities-type').value, ownerId: $('#activities-owner').value, direction: status === 'open' ? 'asc' : 'desc', limit: PAGE_SIZE, offset: state.offsets.activities })}`, { generation });
  if (!currentIdentity(generation)) return;
  body.replaceChildren(
    ...(result.rows.length
      ? result.rows.map((a) => {
          const box = el('input', { type: 'checkbox', checked: a.completed, 'aria-label': `Done: ${a.subject}` });
          box.addEventListener('change', async () => {
            if (!currentIdentity(generation)) return;
            box.disabled = true;
            try {
              await api(`/api/me/crm/activities/${encodeURIComponent(a.id)}`, { method: 'PATCH', body: { completed: box.checked }, generation });
              if (!currentIdentity(generation)) return;
              toast(box.checked ? 'Marked as done.' : 'Marked as planned.');
            } catch (error) {
              if (!currentIdentity(generation)) return;
              box.checked = !box.checked;
              toast(error.message, 'error');
            } finally {
              if (currentIdentity(generation)) box.disabled = false;
            }
          });
          return el('tr', {}, el('td', { class: 'date' }, fmtDate(a.date)), el('td', {}, el('span', { class: 'type' }, a.type)), el('td', {}, a.subject, a.opportunityName ? el('span', { class: 'sub' }, a.opportunityName) : null), el('td', {}, el('a', { href: `#accounts/${encodeURIComponent(a.accountId)}` }, a.accountName)), el('td', {}, a.ownerName || '—'), el('td', {}, box));
        })
      : [emptyRow(6, 'No activities match.')]),
  );
  pager($('#activities-pager'), 'activities', result.total, loadActivities);
}

const reloadActivities = () => {
  const generation = state.identityGeneration;
  state.offsets.activities = 0;
  loadActivities(generation).catch((error) => {
    if (currentIdentity(generation)) toast(error.message, 'error');
  });
};
$('#activities-filters').addEventListener('change', reloadActivities);
$('#activities-filters').addEventListener('submit', (event) => event.preventDefault());

// ---------- Record forms ----------

let dialogSubmit = null;

function fieldControl(field) {
  const generation = state.identityGeneration;
  const id = `f-${field.name}`;
  let control;
  if (field.type === 'select') {
    control = el('select', { id, name: field.name, required: field.required }, field.blank ? el('option', { value: '' }, field.blank) : null, ...field.options.map(([value, label]) => el('option', { value, selected: value === field.value }, label)));
  } else if (field.type === 'account') {
    const list = el('datalist', { id: `${id}-list` });
    control = el('input', { id, name: field.name, list: list.id, autocomplete: 'off', required: field.required, placeholder: 'Start typing an account name' });
    const lookup = debounce(async () => {
      if (!currentIdentity(generation)) return;
      const found = await api(`/api/me/crm/lookup/accounts?${query({ q: control.value.trim() })}`, { generation }).catch(() => []);
      if (!currentIdentity(generation)) return;
      control.dataset.matches = JSON.stringify(found);
      list.replaceChildren(...found.map((a) => el('option', { value: a.name })));
    });
    control.addEventListener('input', lookup);
    return el('label', { class: 'field' }, el('span', { class: 'field-label' }, field.label), control, list);
  } else if (field.type === 'textarea') {
    control = el('textarea', { id, name: field.name, rows: 3, maxlength: field.max || 1000 });
  } else if (field.type === 'checkbox') {
    return el('label', { class: 'check' }, el('input', { type: 'checkbox', id, name: field.name, checked: field.value }), ` ${field.label}`);
  } else {
    control = el('input', { id, name: field.name, type: field.type || 'text', required: field.required, value: field.value ?? undefined, min: field.min, step: field.step, maxlength: field.max || 200, autocomplete: 'off' });
  }
  return el('label', { class: 'field' }, el('span', { class: 'field-label' }, `${field.label}${field.required ? '' : ' (optional)'}`), control);
}

function openForm({ title, fields, submitLabel = 'Save', onSubmit }) {
  $('#dialog-title').textContent = title;
  $('#dialog-fields').replaceChildren(...fields.map(fieldControl));
  $('#dialog-submit').textContent = submitLabel;
  $('#dialog-error').hidden = true;
  dialogSubmit = { fields, onSubmit, generation: state.identityGeneration };
  $('#dialog').showModal();
  $('#dialog-fields').querySelector('input, select, textarea')?.focus();
}

function formValues(fields) {
  const values = {};
  for (const field of fields) {
    const control = $(`#f-${field.name}`);
    if (field.type === 'checkbox') values[field.name] = control.checked;
    else if (field.type === 'account') {
      const matches = JSON.parse(control.dataset.matches || '[]');
      const match = matches.find((a) => a.name.toLowerCase() === control.value.trim().toLowerCase());
      values[field.name] = match?.id || '';
      if (control.value.trim() && !match) throw new Error('Pick the account from the list.');
    } else values[field.name] = control.value.trim();
  }
  return values;
}

$('#dialog-cancel').addEventListener('click', () => $('#dialog').close());
$('#dialog-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!dialogSubmit) return;
  const submission = dialogSubmit;
  const { generation } = submission;
  if (!currentIdentity(generation)) return;
  const error = $('#dialog-error');
  error.hidden = true;
  await withBusy($('#dialog-submit'), 'Saving…', async () => {
    try {
      await submission.onSubmit(formValues(submission.fields), generation);
      if (!currentIdentity(generation)) return;
      $('#dialog').close();
    } catch (failure) {
      if (!currentIdentity(generation)) return;
      error.textContent = failure.message;
      error.hidden = false;
    }
  });
});

const repOptions = () => state.options.reps.map((r) => [r.id, r.name]);

function accountForm() {
  const territories = state.options.territories || [];
  // Reps add accounts in their own territories; with just one, it's preset. Managers may leave it unassigned.
  const rep = state.me.role === 'rep';
  openForm({
    title: 'New account',
    fields: [
      { name: 'name', label: 'Company name', required: true },
      { name: 'industry', label: 'Industry', type: 'select', blank: 'Choose…', options: state.options.industries.map((i) => [i, i]) },
      { name: 'city', label: 'City' },
      { name: 'state', label: 'State (territory)', type: 'select', required: rep, blank: rep && territories.length === 1 ? null : rep ? 'Choose…' : 'Unassigned', value: territories.length === 1 ? territories[0] : undefined, options: territories.map((t) => [t, t]) },
      { name: 'country', label: 'Country' },
      { name: 'ownerId', label: 'Owner', type: 'select', blank: 'Nobody yet', options: repOptions() },
    ],
    submitLabel: 'Create account',
    onSubmit: async (values, generation) => {
      const account = await api('/api/me/crm/accounts', { method: 'POST', body: values, generation });
      if (!currentIdentity(generation)) return;
      toast(`${account.name} added.`);
      location.hash = `#accounts/${encodeURIComponent(account.id)}`;
    },
  });
}

function opportunityForm(accountId) {
  openForm({
    title: 'New opportunity',
    fields: [
      ...(accountId ? [] : [{ name: 'accountId', label: 'Account', type: 'account', required: true }]),
      { name: 'name', label: 'Opportunity name', required: true },
      { name: 'stage', label: 'Stage', type: 'select', options: state.options.openStages.map((s) => [s, s]), value: 'Prospecting' },
      { name: 'amount', label: 'Amount (USD)', type: 'number', min: 0, step: 1000 },
      { name: 'closeDate', label: 'Expected close date', type: 'date' },
      { name: 'ownerId', label: 'Owner', type: 'select', blank: 'Nobody yet', options: repOptions() },
    ],
    submitLabel: 'Create opportunity',
    onSubmit: async (values, generation) => {
      const deal = await api('/api/me/crm/opportunities', { method: 'POST', body: { ...values, accountId: accountId || values.accountId }, generation });
      if (!currentIdentity(generation)) return;
      toast(`${deal.name} added.`);
      render(generation);
    },
  });
}

function activityForm(accountId) {
  openForm({
    title: 'Log activity',
    fields: [
      ...(accountId ? [] : [{ name: 'accountId', label: 'Account', type: 'account', required: true }]),
      { name: 'type', label: 'Type', type: 'select', options: state.options.activityTypes.map((t) => [t, t]) },
      { name: 'subject', label: 'Subject', required: true },
      { name: 'date', label: 'Date', type: 'date', value: today() },
      { name: 'durationMinutes', label: 'Duration in minutes', type: 'number', min: 0, step: 5 },
      { name: 'ownerId', label: 'Owner', type: 'select', blank: 'Nobody yet', options: repOptions() },
    ],
    submitLabel: 'Log activity',
    onSubmit: async (values, generation) => {
      await api('/api/me/crm/activities', { method: 'POST', body: { ...values, accountId: accountId || values.accountId }, generation });
      if (!currentIdentity(generation)) return;
      toast('Activity logged.');
      render(generation);
    },
  });
}

function contactForm(accountId) {
  openForm({
    title: 'Add contact',
    fields: [
      { name: 'firstName', label: 'First name' },
      { name: 'lastName', label: 'Last name', required: true },
      { name: 'title', label: 'Job title' },
      { name: 'email', label: 'Email', type: 'email' },
      { name: 'phone', label: 'Phone', type: 'tel' },
    ],
    submitLabel: 'Add contact',
    onSubmit: async (values, generation) => {
      await api('/api/me/crm/contacts', { method: 'POST', body: { ...values, accountId }, generation });
      if (!currentIdentity(generation)) return;
      toast('Contact added.');
      render(generation);
    },
  });
}

$('#new-account').addEventListener('click', accountForm);
$('#new-opportunity').addEventListener('click', () => opportunityForm(null));
$('#new-activity').addEventListener('click', () => activityForm(null));
$('#account-deal').addEventListener('click', () => opportunityForm(state.accountId));
$('#account-log').addEventListener('click', () => activityForm(state.accountId));
$('#account-contact').addEventListener('click', () => contactForm(state.accountId));

// ---------- Reports ----------

function resetReport() {
  state.report.revision += 1;
  clearInterval(state.report.timer);
  if (state.report.embedded) window.powerbi?.reset($('#canvas'));
  Object.assign(state.report, { embedded: null, mode: null, request: null, ready: null, onSaved: null, refreshAt: null, tokenId: null, checkToken: null });
}

const canvasNote = (title, text) => el('div', { class: 'canvas-note' }, title ? el('h2', {}, title) : null, el('p', {}, text));
// What this person may do with reports: the server decides, per person (view, edit, create).
const rights = () => state.me.reportPermissions || { view: true, edit: false, create: false };

function renderReportList() {
  const current = state.report.current;
  $('#report-list').replaceChildren(
    ...state.report.list.map((r) => el('li', {}, el('a', { href: `#reports/${encodeURIComponent(r.id)}`, 'aria-current': current?.reportId === r.id ? 'page' : undefined }, r.name))),
  );
  const editable = rights().edit && current?.reportId;
  $('#edit-report').hidden = !editable;
  $('#edit-report').textContent = state.report.mode === 'edit' ? 'Done editing' : 'Edit report';
}

async function loadReports(reportId, generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  const listing = await api('/api/me/reports', { generation });
  if (!currentIdentity(generation)) return;
  state.report.list = listing.reports;
  state.report.models = listing.models;
  $('#new-report').hidden = !(rights().create && listing.models.length);
  $('#describe-form').hidden = !(rights().edit || rights().create);
  const target = reportId || (state.report.current?.kind === 'create' ? null : state.report.current?.reportId) || listing.reports[0]?.id;
  if (target && listing.reports.some((r) => r.id === target)) {
    if (state.report.current?.reportId !== target || !state.report.embedded) await openReport(target, 'view', generation);
    else renderReportList();
    return;
  }
  state.report.current = null;
  renderReportList();
  $('#canvas').replaceChildren(canvasNote('No reports yet', listing.models.length && rights().create ? 'Start one with New report, or describe a chart above.' : 'Your reports appear here as soon as they are ready.'));
}

async function openReport(reportId, mode, generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  state.report.current = { kind: 'report', reportId };
  await embed({ mode, reportId }, generation);
  if (currentIdentity(generation)) renderReportList();
}

$('#edit-report').addEventListener('click', () => {
  const current = state.report.current;
  if (current?.reportId) openReport(current.reportId, state.report.mode === 'edit' ? 'view' : 'edit');
});

$('#new-report').addEventListener('click', async () => {
  const generation = state.identityGeneration;
  const model = state.report.models[0];
  if (!model) return;
  state.report.current = { kind: 'create' };
  state.demoCharts = [];
  renderReportList();
  await embed({ mode: 'create', datasetId: model.id }, generation);
});

async function embed(request, generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  const canvas = $('#canvas');
  resetReport();
  const revision = state.report.revision;
  const active = () => currentIdentity(generation) && state.report.revision === revision;
  canvas.replaceChildren(canvasNote(null, 'Opening…'));
  try {
    const config = await api('/api/me/embed', { method: 'POST', body: request, generation });
    if (!active()) return;
    state.report.request = request;
    state.report.mode = config.mode;
    if (config.demo) {
      renderDemoBoard(config.kind === 'create' ? 'New report' : config.name);
      state.report.ready = Promise.resolve(null);
      return;
    }
    embedLive(canvas, config, generation);
  } catch (error) {
    if (active()) canvas.replaceChildren(canvasNote(null, error.message));
  }
}

function embedLive(canvas, config, generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  const client = window['powerbi-client'];
  if (!window.powerbi || !client) {
    canvas.replaceChildren(canvasNote(null, "Reports couldn't load. Check your connection and try again."));
    return;
  }
  const { models } = client;
  canvas.replaceChildren();
  const embedded =
    config.kind === 'create'
      ? window.powerbi.createReport(canvas, { type: 'report', tokenType: models.TokenType.Embed, accessToken: config.accessToken, embedUrl: config.embedUrl, datasetId: config.datasetId })
      : window.powerbi.embed(canvas, {
          type: 'report',
          id: config.reportId,
          embedUrl: config.embedUrl,
          accessToken: config.accessToken,
          tokenType: models.TokenType.Embed,
          // As in Microsoft's App-Owns-Data Starter Kit: Read to view; editing allows Save, and Save as only for
          // people who may also create (the server leaves the workspace out of their token otherwise).
          permissions: config.mode === 'edit' ? (rights().create ? models.Permissions.All : models.Permissions.ReadWrite) : models.Permissions.Read,
          viewMode: config.mode === 'edit' ? models.ViewMode.Edit : models.ViewMode.View,
          settings: { panes: { filters: { visible: config.mode === 'edit' } } },
        });
  state.report.embedded = embedded;
  const active = () => currentIdentity(generation) && state.report.embedded === embedded;
  state.report.ready = new Promise((resolve) => embedded.on('loaded', () => resolve(embedded)));
  embedded.on('error', (event) => {
    if (active()) toast(event.detail?.message || "The report couldn't load.", 'error');
  });
  // Usage, as in Microsoft's App-Owns-Data Starter Kit: how long the report took to load and render, with the embed
  // token's ID and the report's correlation ID, which tie the view to Power BI's own records. First render only.
  const started = performance.now();
  let loadMs = null;
  let logged = config.kind === 'create';
  state.report.tokenId = config.tokenId || null;
  embedded.on('loaded', () => {
    if (active()) loadMs = Math.round(performance.now() - started);
  });
  embedded.on('rendered', async () => {
    if (!active() || logged) return;
    logged = true;
    const renderMs = Math.round(performance.now() - started);
    const correlationId = await Promise.resolve(embedded.getCorrelationId?.()).catch(() => null);
    if (!active()) return;
    logUsage({ event: 'view', reportId: config.reportId, reportName: config.name, loadMs, renderMs, correlationId, tokenId: state.report.tokenId }, generation);
  });
  embedded.on('saved', async (event) => {
    if (!active()) return;
    const savedId = event.detail?.reportObjectId;
    const saved = config.kind === 'create' ? 'create' : event.detail?.saveAs ? 'copy' : 'save';
    if (savedId) logUsage({ event: saved, reportId: savedId, reportName: event.detail?.reportName || config.name, ...(saved === 'copy' ? { originalReportId: config.reportId } : {}), tokenId: state.report.tokenId }, generation);
    // A save started by "describe a chart" continues there; any other save refreshes the list.
    if (state.report.onSaved) {
      const handler = state.report.onSaved;
      state.report.onSaved = null;
      handler(savedId);
      return;
    }
    toast('Report saved.');
    // "Save as" and a new report leave the frame on a report its token doesn't name, and a refresh would ask for the
    // original again. So the saved report opens with a token of its own, as in Microsoft's App-Owns-Data Starter Kit.
    if (savedId && saved !== 'save') {
      const listing = await api('/api/me/reports', { generation }).catch((error) => {
        if (active()) toast(error.message, 'error');
        return null;
      });
      if (!active() || !listing) return;
      state.report.list = listing.reports;
      await openReport(savedId, rights().edit ? 'edit' : 'view', generation);
      return;
    }
    if (savedId) state.report.current = { kind: 'report', reportId: savedId };
    await loadReports(savedId || undefined, generation).catch((error) => {
      if (active()) toast(error.message, 'error');
    });
  });
  scheduleTokenRefresh(embedded, config, generation);
}

// The usage log is never in the way: if it can't be written, the report keeps working.
function logUsage(body, generation = state.identityGeneration) {
  if (currentIdentity(generation)) api('/api/me/reports/usage', { method: 'POST', body, generation }).catch(() => {});
}

// Embed tokens are short-lived. Check every 30 seconds and whenever the tab becomes visible again (timers stall while
// a device sleeps), and swap in a fresh token when it's due (embed-token.js says when).
function scheduleTokenRefresh(embedded, config, generation = state.identityGeneration) {
  clearInterval(state.report.timer);
  state.report.refreshAt = refreshTimeOf(config);
  let refreshing = false;
  const active = () => currentIdentity(generation) && state.report.embedded === embedded;
  const checkToken = async () => {
    if (!active() || refreshing || !state.report.request) return;
    if (Date.now() < state.report.refreshAt) return;
    refreshing = true;
    try {
      const fresh = await api('/api/me/embed', { method: 'POST', body: state.report.request, generation });
      if (!active()) return;
      await embedded.setAccessToken(fresh.accessToken);
      if (!active()) return;
      state.report.refreshAt = refreshTimeOf(fresh);
      state.report.tokenId = fresh.tokenId || null;
    } catch {
      if (active()) {
        clearInterval(state.report.timer);
        toast('Your session for this report ended. Open it again.', 'error');
      }
    } finally {
      refreshing = false;
    }
  };
  state.report.checkToken = checkToken;
  state.report.timer = setInterval(checkToken, TOKEN_CHECK_MS);
}

document.addEventListener('visibilitychange', () => {
  if (!document.hidden) state.report.checkToken?.();
});

// "Describe a chart": the server turns the words into a visual spec; the report authoring API builds it.
$('#describe-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const generation = state.identityGeneration;
  const text = $('#describe-text').value.trim();
  const hint = $('#describe-hint');
  if (!text) return;
  await withBusy(event.submitter || event.target.querySelector('button'), 'Adding…', async () => {
    try {
      const spec = await api('/api/me/reports/describe', { method: 'POST', body: { text }, generation });
      if (!currentIdentity(generation)) return;
      if (!spec.ok) {
        hint.textContent = spec.message;
        hint.classList.add('error');
        return;
      }
      hint.classList.remove('error');
      if (state.me.demo) {
        if (!state.report.request) await embed(state.report.models[0] ? { mode: 'create', datasetId: state.report.models[0].id } : { mode: 'view' }, generation);
        if (!currentIdentity(generation)) return;
        state.demoCharts.unshift(spec);
        renderDemoBoard();
      } else {
        await ensureEditable(generation);
        if (!currentIdentity(generation)) return;
        const report = await state.report.ready;
        if (!currentIdentity(generation)) return;
        await addVisual(report, spec, generation);
      }
      if (!currentIdentity(generation)) return;
      hint.textContent = `Added “${spec.title}”.${spec.notes?.length ? ` ${spec.notes.join(' ')}` : ''} Save the report to keep it.`;
      $('#describe-text').value = '';
    } catch (error) {
      if (!currentIdentity(generation)) return;
      hint.textContent = error.message;
      hint.classList.add('error');
    }
  });
});

// Charts can only be added to a saved report open for editing. A brand-new report is saved first (Power BI's
// create mode has no page API), then reopened in edit mode with a token for that report.
async function ensureEditable(generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  if (state.report.embedded && state.report.mode === 'edit') return;
  if (!state.report.embedded && !state.report.current?.reportId && state.report.models[0]) {
    state.report.current = { kind: 'create' };
    await embed({ mode: 'create', datasetId: state.report.models[0].id }, generation);
    if (!currentIdentity(generation)) return;
  }
  if (state.report.mode === 'create' && state.report.embedded) {
    const created = await state.report.ready;
    if (!currentIdentity(generation)) return;
    const saved = new Promise((resolve) => {
      state.report.onSaved = resolve;
    });
    await created.saveAs({ name: `New report ${new Date().toISOString().slice(0, 10)}` });
    if (!currentIdentity(generation)) return;
    const reportId = await saved;
    if (!currentIdentity(generation)) return;
    if (!reportId) throw new Error("The new report couldn't be saved.");
    const listing = await api('/api/me/reports', { generation });
    if (!currentIdentity(generation)) return;
    state.report.list = listing.reports;
    await openReport(reportId, 'edit', generation);
  } else if (state.report.current?.reportId) {
    await openReport(state.report.current.reportId, 'edit', generation);
  }
  if (!currentIdentity(generation)) return;
  if (!state.report.ready) throw new Error("The report couldn't open for editing.");
}

async function addVisual(report, spec, generation = state.identityGeneration) {
  const active = () => currentIdentity(generation) && state.report.embedded === report;
  if (!active()) return;
  const page = await report.getActivePage();
  if (!active()) return;
  const visuals = await page.getVisuals().catch(() => []);
  if (!active()) return;
  const pageWidth = page.defaultSize?.width || 1280;
  const card = spec.visualType === 'card';
  const width = card ? Math.round(pageWidth / 5) : Math.round((pageWidth - 72) / 2);
  const height = card ? 180 : 380;
  const bottom = visuals.reduce((max, v) => Math.max(max, (v.layout?.y || 0) + (v.layout?.height || 0)), 0);
  // Visuals created without an explicit display state come out hidden.
  const layout = { x: 24, y: visuals.length ? bottom + 24 : 24, width, height, displayState: { mode: 0 } };
  const { visual } = await page.createVisual(spec.visualType, layout, false);
  if (!active()) return;
  const { dataRoles = [] } = await visual.getCapabilities();
  if (!active()) return;
  // 0 = grouping, 1 = measure, 2 = either (for example a table's Values).
  const grouping = dataRoles.find((r) => r.kind === 0) || dataRoles.find((r) => r.kind === 2);
  const measures = dataRoles.find((r) => r.kind === 1) || dataRoles.find((r) => r.kind === 2);
  if (spec.dimension && grouping) await visual.addDataField(grouping.name, { $schema: SCHEMA.column, table: spec.dimension.table, column: spec.dimension.column });
  if (!active()) return;
  if (measures) await visual.addDataField(measures.name, { $schema: SCHEMA.measure, table: spec.measure.table, measure: spec.measure.name });
  if (!active()) return;
  if (spec.sortByCategory && spec.dimension) {
    await visual.sortBy({ orderBy: [{ target: { table: spec.dimension.table, column: spec.dimension.column }, direction: 1 }] }).catch(() => {});
    if (!active()) return;
  }
  await visual.setProperty({ objectName: 'title', propertyName: 'visible' }, { schema: SCHEMA.property, value: true }).catch(() => {});
  if (!active()) return;
  await visual.setProperty({ objectName: 'title', propertyName: 'titleText' }, { schema: SCHEMA.property, value: spec.title }).catch(() => {});
}

// Demo mode has no Power BI: charts are drawn from the same data the assistant uses.
function renderDemoBoard(title) {
  const canvas = $('#canvas');
  const heading = title || canvas.querySelector('.demo-board h2')?.textContent || 'Report';
  const charts = state.demoCharts.map((spec) => el('figure', { class: 'demo-chart' }, el('figcaption', {}, spec.title), demoChart(spec)));
  canvas.replaceChildren(
    el(
      'div',
      { class: 'demo-board' },
      el('h2', {}, heading),
      el('p', { class: 'demo-note' }, 'Demo mode: connected to Power BI, this is the embedded report editor and each chart becomes a real visual.'),
      charts.length ? el('div', { class: 'demo-grid' }, charts) : el('p', {}, rights().edit || rights().create ? 'Describe a chart above to add one.' : 'This report opens here in the connected app.'),
    ),
  );
}

function demoChart(spec) {
  const rows = (spec.preview?.rows || []).filter((r) => r.value !== null);
  if (!rows.length) return el('p', { class: 'demo-empty' }, 'No data to show.');
  if (!spec.dimension) return el('p', { class: 'demo-card' }, rows[0].display);
  const NS = 'http://www.w3.org/2000/svg';
  const svgEl = (tag, attrs, text) => {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const max = Math.max(...rows.map((r) => r.value), 0) || 1;
  if (['lineChart', 'areaChart', 'clusteredColumnChart'].includes(spec.visualType)) {
    const w = 560;
    const h = 220;
    const step = w / Math.max(rows.length, 1);
    const svg = svgEl('svg', { viewBox: `0 0 ${w} ${h + 24}`, role: 'img', 'aria-label': spec.title });
    const points = rows.map((r, i) => [i * step + step / 2, h - (r.value / max) * (h - 12)]);
    if (spec.visualType === 'clusteredColumnChart') rows.forEach((r, i) => svg.append(svgEl('rect', { x: i * step + step * 0.15, y: points[i][1], width: step * 0.7, height: h - points[i][1], class: 'bar' })));
    else svg.append(svgEl('polyline', { points: points.map((p) => p.join(',')).join(' '), class: 'line' }));
    [0, rows.length - 1].forEach((i) => svg.append(svgEl('text', { x: points[i][0], y: h + 18, 'text-anchor': i ? 'end' : 'start', class: 'axis' }, rows[i].label)));
    return svg;
  }
  return el(
    'table',
    { class: 'demo-bars' },
    el(
      'tbody',
      {},
      rows.slice(0, 10).map((r) => el('tr', {}, el('th', { scope: 'row' }, r.label), el('td', {}, el('span', { class: 'demo-bar', style: `width:${Math.max(2, (r.value / max) * 100)}%` })), el('td', { class: 'num' }, r.display))),
    ),
  );
}

// ---------- Assistant ----------

function renderSuggestions() {
  $('#suggestions').replaceChildren(
    ...(state.me.examples || []).map((text) => el('li', {}, el('button', { type: 'button', class: 'suggestion', onclick: () => ask(text) }, text))),
  );
}

function openAssistant() {
  $('#assistant').hidden = false;
  $('#assistant-launcher').setAttribute('aria-expanded', 'true');
  $('#question').focus();
}

function closeAssistant() {
  if ($('#assistant').hidden) return;
  $('#assistant').hidden = true;
  $('#assistant-launcher').setAttribute('aria-expanded', 'false');
}

$('#assistant-launcher').addEventListener('click', () => ($('#assistant').hidden ? openAssistant() : closeAssistant()));
$('#assistant-close').addEventListener('click', () => {
  closeAssistant();
  $('#assistant-launcher').focus();
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !$('#assistant').hidden && !$('#dialog').open) closeAssistant();
});

// Charts for the assistant's answers, from the rows the server computed for what this person may see.
function answerChart(turn) {
  const rows = (turn.rows || []).filter((r) => r.value !== null && Number.isFinite(r.value));
  if (rows.length < 2) return null;
  const title = turn.measure && turn.dimension ? `${turn.measure} by ${turn.dimension}` : 'Chart';
  if (turn.chart !== 'line') {
    const max = Math.max(...rows.map((r) => r.value), 0) || 1;
    const bars = el(
      'table',
      { class: 'demo-bars' },
      el('tbody', {}, rows.slice(0, 10).map((r) => el('tr', {}, el('th', { scope: 'row', title: r.label }, r.label), el('td', {}, el('span', { class: 'demo-bar', style: `width:${Math.max(2, (Math.max(0, r.value) / max) * 100)}%` })), el('td', { class: 'num' }, r.display)))),
    );
    return el('figure', { class: 'answer-chart' }, el('figcaption', {}, title), bars);
  }
  const NS = 'http://www.w3.org/2000/svg';
  const svgEl = (tag, attrs, text) => {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const [w, h, pad] = [340, 140, 8];
  const values = rows.map((r) => r.value);
  const [low, high] = [Math.min(0, ...values), Math.max(...values)];
  const x = (i) => pad + (i * (w - 2 * pad)) / (rows.length - 1);
  const y = (v) => pad + (h - 2 * pad) * (1 - (v - low) / (high - low || 1));
  const [first, last] = [rows[0], rows[rows.length - 1]];
  const peak = rows.reduce((a, b) => (b.value > a.value ? b : a));
  const svg = svgEl('svg', { viewBox: `0 0 ${w} ${h + 20}`, role: 'img', 'aria-label': `${title}: ${rows.length} points from ${first.label} (${first.display}) to ${last.label} (${last.display}); highest ${peak.label} (${peak.display}).` });
  svg.append(svgEl('line', { x1: pad, y1: y(low), x2: w - pad, y2: y(low), class: 'baseline' }));
  svg.append(svgEl('polyline', { points: rows.map((r, i) => `${x(i)},${y(r.value)}`).join(' '), class: 'line' }));
  rows.forEach((r, i) => {
    const dot = svgEl('circle', { cx: x(i), cy: y(r.value), r: 3, class: 'dot' });
    dot.append(svgEl('title', {}, `${r.label}: ${r.display}`));
    svg.append(dot);
  });
  svg.append(svgEl('text', { x: pad, y: h + 16, class: 'axis' }, first.label), svgEl('text', { x: w - pad, y: h + 16, 'text-anchor': 'end', class: 'axis' }, last.label));
  svg.append(svgEl('text', { x: x(rows.indexOf(peak)), y: Math.max(10, y(peak.value) - 8), 'text-anchor': 'middle', class: 'axis' }, peak.display));
  const numbers = el('details', { class: 'answer-numbers' }, el('summary', {}, 'The numbers'), el('table', { class: 'answer-table' }, el('tbody', {}, rows.map((r) => el('tr', {}, el('th', { scope: 'row' }, r.label), el('td', { class: 'num' }, r.display))))));
  return el('figure', { class: 'answer-chart' }, el('figcaption', {}, title), svg, numbers);
}

const SOURCES = {
  assistant: 'Answered by the assistant from your reporting data',
  quick: 'Quick answer from your CRM records',
};

function renderConversation() {
  $('#suggestions').hidden = state.conversation.length > 0;
  $('#conversation').replaceChildren(
    ...state.conversation.map((turn) => {
      const chart = turn.chart ? answerChart(turn) : null;
      return el(
        'li',
        { class: turn.from },
        el('p', {}, turn.text),
        turn.images?.length
          ? el('div', { class: 'answer-images' }, turn.images.map((image) => el('img', { class: 'answer-image', src: `data:${image.mimeType};base64,${image.data}`, alt: `Chart the assistant drew for: ${turn.question}` })))
          : null,
        chart,
        !chart && turn.rows?.length > 1
          ? el('table', { class: 'answer-table' }, el('tbody', {}, turn.rows.slice(0, 10).map((r) => el('tr', {}, el('th', { scope: 'row' }, r.label), el('td', { class: 'num' }, r.display)))))
          : null,
        turn.suggestions ? el('ul', { class: 'inline-suggestions' }, turn.suggestions.map((s) => el('li', {}, el('button', { type: 'button', class: 'suggestion', onclick: () => ask(s) }, s)))) : null,
        turn.source ? el('p', { class: 'source' }, `${SOURCES[turn.source] || SOURCES.quick}${chart && turn.chartSource === 'quick' && turn.source === 'assistant' ? '; chart from your CRM records' : ''}`) : null,
      );
    }),
  );
  const list = $('#conversation');
  list.scrollTop = list.scrollHeight;
}

async function ask(question) {
  const generation = state.identityGeneration;
  state.conversation.push({ from: 'you', text: question });
  state.conversation.push({ from: 'bot pending', text: 'Looking…' });
  renderConversation();
  const button = $('#ask-form button');
  button.disabled = true;
  try {
    const result = await api('/api/me/ask', { method: 'POST', body: { question }, generation });
    if (!currentIdentity(generation)) return;
    const { answer, rows, suggestions, source, chart, measure, dimension, chartSource, images } = result;
    state.conversation[state.conversation.length - 1] = { from: 'bot', question, text: answer, rows, suggestions, source, chart, measure, dimension, chartSource, images };
  } catch (error) {
    if (currentIdentity(generation)) state.conversation[state.conversation.length - 1] = { from: 'bot error', text: error.message };
  } finally {
    if (currentIdentity(generation)) {
      button.disabled = false;
      renderConversation();
    }
  }
}

$('#ask-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const question = $('#question').value.trim();
  if (!question) return;
  $('#question').value = '';
  ask(question);
});
$('#question').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    $('#ask-form').requestSubmit();
  }
});

// ---------- Data (data integration add-on) ----------

async function loadData(generation = state.identityGeneration) {
  if (!currentIdentity(generation)) return;
  const body = $('#datasets');
  body.replaceChildren(loadingRow(4));
  const datasets = await api('/api/me/data', { generation });
  if (!currentIdentity(generation)) return;
  body.replaceChildren(
    ...(datasets.length
      ? datasets.map((d) => el('tr', {}, el('td', {}, d.name), el('td', {}, d.source), el('td', { class: 'num' }, d.rows === null ? '—' : count.format(d.rows)), el('td', { class: 'date' }, d.updatedAt ? fmtDate(d.updatedAt) : '—')))
      : [emptyRow(4, 'Nothing added yet.')]),
  );
}

// Pinned versions with Subresource Integrity: the browser refuses a CDN file that has been changed.
const SHEETJS = { src: 'https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js', integrity: 'sha384-EnyY0/GSHQGSxSgMwaIPzSESbqoOLSexfnSMN2AP+39Ckmn92stwABZynq1JyzdT' };

function loadScript({ src, integrity }) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const script = el('script', { src, integrity, crossorigin: 'anonymous' });
    script.addEventListener('load', resolve);
    script.addEventListener('error', () => reject(new Error("Excel support couldn't load. Save the sheet as CSV and try again.")));
    document.head.append(script);
  });
}

async function excelSheetsAsCsv(file, baseName) {
  await loadScript(SHEETJS);
  const book = window.XLSX.read(await file.arrayBuffer(), { type: 'array' });
  return book.SheetNames.map((sheet) => ({ name: book.SheetNames.length > 1 ? `${baseName} ${sheet}` : baseName, fileName: `${baseName}-${sheet}.csv`, bytes: new TextEncoder().encode(window.XLSX.utils.sheet_to_csv(book.Sheets[sheet])) }));
}

$('#upload-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const generation = state.identityGeneration;
  const file = $('#upload-file').files[0];
  if (!file) {
    toast('Choose a file to upload.', 'error');
    return;
  }
  const baseName = $('#upload-name').value.trim() || file.name.replace(/\.[^.]*$/, '');
  await withBusy(event.submitter, 'Uploading…', async () => {
    try {
      const parts = /\.xlsx?$/i.test(file.name) ? await excelSheetsAsCsv(file, baseName) : [{ name: baseName, fileName: file.name, bytes: new Uint8Array(await file.arrayBuffer()) }];
      if (!currentIdentity(generation)) return;
      for (const part of parts) {
        await api(`/api/me/uploads?${query({ name: part.name })}`, { method: 'POST', raw: part.bytes, headers: { 'x-file-name': encodeURIComponent(part.fileName), 'content-type': 'application/octet-stream' }, generation });
        if (!currentIdentity(generation)) return;
      }
      toast(`Added ${parts.map((p) => p.name).join(', ')}.`);
      event.target.reset();
      await loadData(generation);
    } catch (error) {
      if (currentIdentity(generation)) toast(error.message, 'error');
    }
  });
});

$('#web-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const generation = state.identityGeneration;
  const url = $('#web-url').value.trim();
  if (!url) {
    toast('Paste the link to connect.', 'error');
    return;
  }
  await withBusy(event.submitter, 'Connecting…', async () => {
    try {
      const result = await api('/api/me/imports/web', { method: 'POST', body: { url, name: $('#web-name').value.trim() || undefined }, generation });
      if (!currentIdentity(generation)) return;
      toast(`Added ${result.name}.`);
      event.target.reset();
      await loadData(generation);
    } catch (error) {
      if (currentIdentity(generation)) toast(error.message, 'error');
    }
  });
});

$('#request-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const generation = state.identityGeneration;
  const message = $('#request-text').value.trim();
  if (!message) {
    toast('Tell us what you would like to connect.', 'error');
    return;
  }
  await withBusy(event.submitter, 'Sending…', async () => {
    try {
      await api('/api/me/requests', { method: 'POST', body: { message }, generation });
      if (!currentIdentity(generation)) return;
      toast("Thanks. We'll contact you to set up the connection.");
      event.target.reset();
    } catch (error) {
      if (currentIdentity(generation)) toast(error.message, 'error');
    }
  });
});

boot();
