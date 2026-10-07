// Console front end. Talks only to this server's /api; the server holds every Fabric credential.
import { TOKEN_CHECK_MS, refreshTimeOf } from '../embed-token.js';

const state = {
  config: null,
  operator: null,
  signingIn: null,
  tenants: [],
  selectedId: null,
  tenant: null,
  tab: 'overview',
  pollTimer: null,
  embedTimer: null,
  embedRequest: null,
  planRenderedFor: null,
  jobs: new Map(),
  conversations: new Map(),
};

const TABS = ['overview', 'data', 'reports', 'ask', 'license'];
const BUSY = new Set(['pending', 'provisioning', 'deprovisioning']);
const TERMINAL_JOB = new Set(['Completed', 'Failed', 'Cancelled', 'Deduped']);
const TENANT_STATUS = {
  ready: ['●', 'Ready'],
  pending: ['○', 'Waiting'],
  provisioning: ['◐', 'Provisioning'],
  deprovisioning: ['◐', 'Deleting'],
  failed: ['✕', 'Needs attention'],
};
const STEP_STATUS = {
  done: ['✓', 'Done'],
  running: ['◐', 'Running'],
  pending: ['○', 'Waiting'],
  warning: ['!', 'Needs follow-up'],
  failed: ['✕', 'Failed'],
  skipped: ['–', 'Skipped'],
  retained: ['◆', 'Kept'],
};
const IDENTITY_STATUS = {
  active: 'Active, Admin of this workspace only',
  created: 'Created; becomes Admin on the next provisioning run',
  missing: 'Not created yet; the shared platform identity is used',
  off: 'Turned off; the platform identity does everything',
};
const JOB_STATUS = {
  NotStarted: ['○', 'Queued'],
  InProgress: ['◐', 'Running'],
  Completed: ['✓', 'Completed'],
  Failed: ['✕', 'Failed'],
  Cancelled: ['✕', 'Cancelled'],
  Deduped: ['–', 'Skipped (already running)'],
};
const TYPE_LABELS = {
  DataPipeline: 'Pipeline',
  SemanticModel: 'Semantic model',
  SQLDatabase: 'SQL database',
  DataAgent: 'Data agent',
  VariableLibrary: 'Variable library',
};
const SUGGESTIONS = [
  'Which tables can you query?',
  'How many opportunities are there?',
  'What columns does crm_accounts have?',
  'How many rows are in crm_activities?',
];

const $ = (selector) => document.querySelector(selector);
const isBusy = (status) => BUSY.has(status);
const typeLabel = (type) => TYPE_LABELS[type] || type;

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

function statusChip(status, map = TENANT_STATUS) {
  const [symbol, label] = map[status] || ['○', status];
  return el('span', { class: `status status-${status}` }, el('span', { class: 'status-symbol', 'aria-hidden': 'true' }, symbol), label);
}

const emptyRow = (columns, text) => el('tr', { class: 'empty' }, el('td', { colspan: columns }, text));
const timeFormat = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
const formatTime = (iso) => (iso ? timeFormat.format(new Date(iso)) : '');
const formatBytes = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : n >= 1024 ? `${Math.round(n / 1024)} KB` : `${n} bytes`);
const stemOf = (fileName) => fileName.replace(/\.[^.]*$/, '');
const tableName = (text) =>
  String(text).toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/_+/g, '_').replace(/^_+|_+$/g, '') || 'data';

async function api(path, { method = 'GET', body, raw, headers = {} } = {}, retried = false) {
  const init = { method, headers: { ...headers } };
  if (method !== 'GET') init.headers['x-platform-client'] = 'web';
  if (raw !== undefined) init.body = raw;
  else if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers['content-type'] = 'application/json';
  }
  const res = await fetch(path, init);
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { error: text };
  }
  // The operator session ran out: sign in again, then repeat the request once.
  if (res.status === 401 && !retried && path.startsWith('/api/admin/') && !path.startsWith('/api/admin/session')) {
    await operatorSignIn();
    return api(path, { method, body, raw, headers }, true);
  }
  if (!res.ok) {
    const error = new Error(data?.error || `Request failed (HTTP ${res.status}).`);
    error.status = res.status;
    throw error;
  }
  return data;
}

// Resolves once the operator has signed in; concurrent callers share one dialog.
function operatorSignIn() {
  if (state.signingIn) return state.signingIn;
  const dialog = $('#operator-signin');
  const form = $('#operator-form');
  const error = $('#operator-error');
  state.signingIn = new Promise((resolve) => {
    error.hidden = true;
    form.onsubmit = async (event) => {
      event.preventDefault();
      const key = $('#operator-key').value;
      if (key.length < 24) {
        error.textContent = 'The operator key has at least 24 characters.';
        error.hidden = false;
        $('#operator-key').focus();
        return;
      }
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      try {
        await api('/api/admin/session', { method: 'POST', body: { key, name: $('#operator-name').value.trim() } });
        $('#operator-key').value = '';
        dialog.close();
        state.signingIn = null;
        resolve();
      } catch (failure) {
        error.textContent = failure.message;
        error.hidden = false;
        $('#operator-key').select();
      } finally {
        button.disabled = false;
      }
    };
  });
  // Escape would leave an unusable console behind the dialog.
  dialog.oncancel = (event) => event.preventDefault();
  dialog.showModal();
  ($('#operator-name').value ? $('#operator-key') : $('#operator-name')).focus();
  return state.signingIn;
}

async function signOut() {
  await api('/api/admin/session', { method: 'DELETE' }).catch(() => {});
  location.reload();
}

let toastTimer;
function toast(message, kind = 'info') {
  const node = $('#toast');
  node.textContent = message;
  node.className = kind === 'error' ? 'toast error' : 'toast';
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    node.hidden = true;
  }, kind === 'error' ? 9000 : 4500);
}

async function withBusy(button, label, work) {
  const original = button.textContent;
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  button.textContent = label;
  try {
    return await work();
  } finally {
    button.disabled = false;
    button.removeAttribute('aria-busy');
    button.textContent = original;
  }
}

const submitButton = (event) => event.submitter || event.target.querySelector('button[type="submit"]');

// ---------- Environment and plans ----------

function renderEnv() {
  const c = state.config;
  const security = c.security || {};
  const items = [
    el('li', { class: c.live ? 'mode' : 'mode mode-mock' }, c.live ? `Live · ${c.identity.label}` : 'Mock mode · no calls to Fabric'),
    el('li', {}, c.capacityConfigured ? '✓ Capacity set' : '✕ No capacity'),
    el('li', {}, c.templateConfigured ? '✓ Template workspace' : '– No template workspace'),
    el('li', {}, c.opsAccessConfigured ? '✓ Support group' : '– No support group'),
    el('li', {}, security.platformWorkspaceAccess === 'release' ? '✓ No standing platform access' : '– Platform keeps workspace access'),
    security.operatorSignIn
      ? el('li', {}, state.operator?.name ? `Signed in as ${state.operator.name}` : 'Signed in', el('button', { class: 'text-button', type: 'button', onclick: signOut }, 'Sign out'))
      : el('li', { class: 'mode-mock' }, 'No operator sign-in (loopback only)'),
  ];
  $('#env').replaceChildren(...items);
  for (const warning of c.warnings || []) toast(warning, 'error');
}

function renderPlanPicker(fieldset, name, selected) {
  const legend = fieldset.querySelector('legend');
  fieldset.replaceChildren(
    legend,
    ...state.config.plans.map((plan) =>
      el(
        'label',
        { class: 'plan-option' },
        el('input', { type: 'radio', name, value: plan.id, checked: plan.id === selected }),
        el('span', { class: 'plan-name' }, plan.name),
        el('span', { class: 'plan-summary' }, plan.summary),
      ),
    ),
  );
}

// ---------- Customer list ----------

function renderCustomerList() {
  const list = $('#customer-list');
  $('#customer-count').textContent = state.tenants.length ? String(state.tenants.length) : '';
  if (!state.tenants.length) {
    list.replaceChildren(el('li', { class: 'empty-list' }, 'No customers yet.'));
    return;
  }
  list.replaceChildren(
    ...state.tenants.map((t) =>
      el(
        'li',
        {},
        el(
          'button',
          { class: 'customer-link', type: 'button', 'aria-current': t.id === state.selectedId ? 'true' : 'false', onclick: () => selectTenant(t.id) },
          el('span', { class: 'name' }, t.name),
          el('span', { class: 'sub' }, statusChip(t.status), t.planName),
        ),
      ),
    ),
  );
}

async function refreshList() {
  try {
    state.tenants = await api('/api/admin/tenants');
    renderCustomerList();
  } catch {
    // The next refresh will try again.
  }
}

// ---------- Selected customer ----------

function showIntro() {
  $('#intro').hidden = false;
  $('#customer').hidden = true;
}

async function selectTenant(id) {
  if (state.selectedId !== id) {
    state.selectedId = id;
    state.tenant = null;
    state.tab = 'overview';
    state.planRenderedFor = null;
    resetEmbed();
    $('#audit').replaceChildren();
    $('#new-password').hidden = true;
  }
  history.replaceState(null, '', id ? `#customer=${id}` : '#');
  renderCustomerList();
  if (!id) {
    clearTimeout(state.pollTimer);
    showIntro();
    return;
  }
  await refreshTenant();
  activateTab(state.tab);
  $('#main').focus({ preventScroll: true });
}

async function refreshTenant() {
  const id = state.selectedId;
  if (!id) return;
  try {
    const tenant = await api(`/api/admin/tenants/${id}`);
    if (state.selectedId !== id) return;
    const wasBusy = state.tenant && isBusy(state.tenant.status);
    state.tenant = tenant;
    renderTenant();
    const index = state.tenants.findIndex((t) => t.id === id);
    if (index >= 0) {
      state.tenants[index] = { ...state.tenants[index], status: tenant.status, plan: tenant.plan, planName: tenant.planName };
      renderCustomerList();
    }
    if (wasBusy && !isBusy(tenant.status)) {
      if (tenant.status === 'ready') toast(`${tenant.name} is ready.`);
      else toast(tenant.error || 'Provisioning stopped.', 'error');
      if (state.tab === 'overview') loadItems();
    }
  } catch (error) {
    if (error.status === 404) {
      state.tenants = state.tenants.filter((t) => t.id !== id);
      await selectTenant(null);
      return;
    }
    toast(error.message, 'error');
  } finally {
    clearTimeout(state.pollTimer);
    if (state.selectedId === id && state.tenant && isBusy(state.tenant.status)) state.pollTimer = setTimeout(refreshTenant, 1500);
  }
}

function renderTenant() {
  const t = state.tenant;
  $('#intro').hidden = true;
  $('#customer').hidden = false;
  $('#c-plan').textContent = `${t.planName} edition${t.addons?.includes('integration') ? ' + data integration' : ''}`;
  $('#c-name').textContent = t.name;
  $('#c-status').replaceChildren(statusChip(t.status));
  $('#c-workspace').textContent = t.workspaceName || 'No workspace yet';
  $('#c-domains').textContent = t.domains?.length ? `Signs in with @${t.domains.join(', @')}` : 'No sign-in domain';
  // The customer's own address and logo (APP_DOMAIN and the Branding section).
  const url = $('#c-url');
  url.hidden = !t.url;
  if (t.url) {
    url.href = t.url;
    url.textContent = t.url.replace(/\/$/, '');
  }
  renderBranding(t);
  renderAssistant(t);
  const identity = t.identity || {};
  $('#c-identity').textContent = `Service account ${identity.name || ''}: ${IDENTITY_STATUS[identity.status] || identity.status || 'unknown'}${identity.appId ? ` (app ${identity.appId})` : ''}${identity.simulated ? ', simulated in mock mode' : ''}`;
  const portal = $('#c-portal');
  portal.hidden = !t.portalUrl;
  if (t.portalUrl) portal.href = t.portalUrl;
  const error = $('#c-error');
  error.hidden = !t.error;
  error.textContent = t.error || '';

  const idle = !isBusy(t.status);
  const workspaceReady = t.steps.some((s) => s.key === 'workspace' && s.status === 'done');
  setTabEnabled('data', idle && workspaceReady && Boolean(t.fabric.lakehouseId), 'Available when the lakehouse exists');
  setTabEnabled('reports', idle && workspaceReady && t.features.reports, 'Available when the workspace exists');
  setTabEnabled('ask', idle && workspaceReady && t.features.agent && Boolean(t.fabric.dataAgentId), t.features.agent ? 'Available when the data agent is set up' : 'Not in this plan');
  if ($(`#tab-${state.tab}`).disabled) activateTab('overview');

  renderSteps(t);
  renderActivity(t);
  renderLoads(t);
  renderUsers(t);
  $('#retry').disabled = isBusy(t.status);
  if (state.planRenderedFor !== `${t.id}:${t.plan}`) {
    renderPlanPicker($('#plan-choice'), 'plan', t.plan);
    state.planRenderedFor = `${t.id}:${t.plan}`;
  }
}

// ---------- Sign-ins ----------

const reportsLabel = (user) => {
  const rights = [user.canEdit && 'edits', user.canCreate && 'creates'].filter(Boolean);
  return rights.length ? ` · ${rights.join(' and ')} reports` : '';
};
const accessLabel = (user) => (user.role === 'manager' ? 'Sales manager · every territory' : `Sales rep · ${user.territories.join(', ') || 'no territory'}`) + reportsLabel(user);
const checkedTerritories = (container) => [...container.querySelectorAll('input[type=checkbox]:checked')].map((input) => input.value);

// Territory checkboxes, which only apply to sales reps.
function territoryChecks(container, territories, { selected = [], disabled = false } = {}) {
  container.replaceChildren(
    el('legend', { class: 'field-label' }, 'Territories'),
    ...territories.map((territory) => el('label', { class: 'check' }, el('input', { type: 'checkbox', value: territory, checked: selected.includes(territory), disabled }), ` ${territory}`)),
  );
}

function syncTerritoryChecks(roleSelect, container) {
  const manager = roleSelect.value === 'manager';
  for (const input of container.querySelectorAll('input')) input.disabled = manager;
  container.classList.toggle('muted', manager);
}

function renderUsers(t) {
  const users = t.users || [];
  // Keep what the operator is typing into the add form; redraw its territories only for another customer.
  if (state.territoriesFor !== t.id) {
    territoryChecks($('#new-user-territories'), t.territories || []);
    syncTerritoryChecks($('#new-user-role'), $('#new-user-territories'));
    state.territoriesFor = t.id;
  }
  $('#users-body').replaceChildren(
    ...(users.length
      ? users.map((user) => {
          const row = el(
            'tr',
            {},
            el('td', {}, user.email),
            el('td', {}, user.name || ''),
            el('td', {}, accessLabel(user)),
            el('td', {}, user.lastSignInAt ? formatTime(user.lastSignInAt) : 'Never'),
            el(
              'td',
              { class: 'row-actions' },
              el('button', { class: 'button small', type: 'button', onclick: () => editAccess(user, row, t.territories || []) }, 'Change access'),
              el('button', { class: 'button small', type: 'button', onclick: (event) => resetSignIn(user, event.currentTarget) }, 'New password'),
              el('button', { class: 'button small danger', type: 'button', onclick: (event) => removeSignIn(user, event.currentTarget) }, 'Remove'),
            ),
          );
          return row;
        })
      : [emptyRow(5, "No named sign-ins yet: anyone at the customer's email domain can use the demo sign-in.")]),
  );
}

// An inline editor under the person's row. Saving a change signs them out, so nothing they have open keeps old access.
function editAccess(user, row, territories) {
  if (row.nextElementSibling?.classList.contains('access-editor')) {
    row.nextElementSibling.remove();
    return;
  }
  const role = el(
    'select',
    { 'aria-label': `Role for ${user.email}` },
    el('option', { value: 'rep', selected: user.role === 'rep' }, 'Sales rep: named territories'),
    el('option', { value: 'manager', selected: user.role === 'manager' }, 'Sales manager: every territory'),
  );
  const checks = el('fieldset', { class: 'territory-checks' });
  territoryChecks(checks, territories, { selected: user.territories });
  syncTerritoryChecks(role, checks);
  role.addEventListener('change', () => syncTerritoryChecks(role, checks));
  const canEdit = el('input', { type: 'checkbox', checked: Boolean(user.canEdit) });
  const canCreate = el('input', { type: 'checkbox', checked: Boolean(user.canCreate) });
  const reports = el('fieldset', { class: 'territory-checks' }, el('legend', { class: 'field-label' }, 'Reports'), el('label', { class: 'check' }, canEdit, ' Can edit'), el('label', { class: 'check' }, canCreate, ' Can create'));
  const save = el('button', { class: 'button small', type: 'submit' }, 'Save access');
  const form = el(
    'form',
    { class: 'access-form', novalidate: true },
    el('label', { class: 'field' }, el('span', { class: 'field-label' }, 'Role'), role),
    checks,
    reports,
    el('div', { class: 'row-actions' }, save, el('button', { class: 'button small', type: 'button', onclick: () => editor.remove() }, 'Cancel')),
    el('p', { class: 'form-note' }, 'Saving a change signs them out everywhere; they sign in again with the new access.'),
  );
  const editor = el('tr', { class: 'access-editor' }, el('td', { colspan: 5 }, form));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    await withBusy(save, 'Saving…', async () => {
      try {
        const body = { role: role.value, territories: role.value === 'rep' ? checkedTerritories(checks) : [], canEdit: canEdit.checked, canCreate: canCreate.checked };
        const result = await api(`/api/admin/tenants/${state.selectedId}/users/${user.id}`, { method: 'PATCH', body });
        toast(result.signedOut ? `${user.email}: ${accessLabel(result.user)}. They've been signed out.` : 'Nothing changed.');
        await refreshTenant();
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  });
  row.after(editor);
  role.focus();
}

// A generated password is shown once, here, and never stored in clear.
function showPassword(email, password) {
  const node = $('#new-password');
  if (!password) {
    node.hidden = true;
    return;
  }
  node.replaceChildren(
    'Password for ',
    el('strong', {}, email),
    ', shown only now. Give it to them privately: ',
    el('code', {}, password),
    ' ',
    el('button', { class: 'button small', type: 'button', onclick: () => navigator.clipboard?.writeText(password).then(() => toast('Copied.'), () => toast("Couldn't copy; select it instead.", 'error')) }, 'Copy'),
  );
  node.hidden = false;
}

async function resetSignIn(user, button) {
  if (!window.confirm(`Give ${user.email} a new password? They'll be signed out everywhere.`)) return;
  await withBusy(button, 'Resetting…', async () => {
    try {
      const result = await api(`/api/admin/tenants/${state.selectedId}/users/${user.id}/password`, { method: 'POST', body: {} });
      showPassword(result.user.email, result.password);
      await refreshTenant();
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}

async function removeSignIn(user, button) {
  if (!window.confirm(`Remove the sign-in for ${user.email}? They'll be signed out everywhere.`)) return;
  await withBusy(button, 'Removing…', async () => {
    try {
      await api(`/api/admin/tenants/${state.selectedId}/users/${user.id}`, { method: 'DELETE' });
      $('#new-password').hidden = true;
      await refreshTenant();
      toast(`Removed ${user.email}.`);
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}

$('#new-user-role').addEventListener('change', () => syncTerritoryChecks($('#new-user-role'), $('#new-user-territories')));

// ---------- Branding ----------

// The data agent the app asks (through its MCP server, as the customer's service account) and the question log.
function renderAssistant(t) {
  const assistant = t.assistant;
  $('#assistant-endpoint').textContent = assistant
    ? `Managers' questions go to the data agent ${assistant.dataAgentId} through its MCP server (${assistant.mcpUrl}), as this customer's service account; reps get quick answers scoped to their territories. Code interpreter ${assistant.codeInterpreter ? 'on' : 'off'}. ${assistant.questions} question(s) logged.`
    : `No data agent${t.features?.agent ? ' yet' : ' in this edition'}: questions get quick answers from the CRM database.`;
  if (state.questionsFor !== t.id) {
    $('#questions-table').hidden = true;
    $('#questions-body').replaceChildren();
    state.questionsFor = null;
  }
  if (state.usageFor !== t.id) {
    $('#usage-table').hidden = true;
    $('#usage-summary').hidden = true;
    $('#usage-body').replaceChildren();
    state.usageFor = null;
  }
}

const USAGE_LABELS = { view: 'Viewed', save: 'Saved', copy: 'Saved a copy of', create: 'Created' };
const seconds = (ms) => (Number.isFinite(ms) ? `${(ms / 1000).toFixed(1)} s` : '–');

$('#show-usage').addEventListener('click', async (event) => {
  await withBusy(event.currentTarget, 'Loading…', async () => {
    try {
      const { entries, reports } = await api(`/api/admin/tenants/${state.selectedId}/usage`);
      state.usageFor = state.selectedId;
      $('#usage-summary').textContent = reports.length
        ? reports.map((r) => `${r.reportName || r.reportId}: ${r.views} view(s) by ${r.people} person(s), median load ${seconds(r.medianLoadMs)}, render ${seconds(r.medianRenderMs)}${r.saves ? `, ${r.saves} save(s)` : ''}.`).join(' ')
        : 'Nobody has opened a report since the usage log started.';
      $('#usage-summary').hidden = false;
      $('#usage-body').replaceChildren(
        ...(entries.length
          ? entries.map((u) =>
              el(
                'tr',
                {},
                el('td', { class: 'mono' }, u.at.slice(0, 16).replace('T', ' ')),
                el('td', {}, u.email),
                el('td', {}, u.scope),
                el('td', {}, `${USAGE_LABELS[u.event] || u.event} ${u.reportName || u.reportId}`),
                el('td', {}, u.event === 'view' ? `${seconds(u.loadMs)}, ${seconds(u.renderMs)}` : '–'),
                el('td', { class: 'mono' }, u.correlationId || '–'),
              ),
            )
          : [el('tr', {}, el('td', { colspan: 6 }, 'Nothing logged yet.'))]),
      );
      $('#usage-table').hidden = false;
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

$('#show-questions').addEventListener('click', async (event) => {
  await withBusy(event.currentTarget, 'Loading…', async () => {
    try {
      const { questions } = await api(`/api/admin/tenants/${state.selectedId}/questions`);
      state.questionsFor = state.selectedId;
      $('#questions-body').replaceChildren(
        ...(questions.length
          ? questions.map((q) =>
              el(
                'tr',
                {},
                el('td', { class: 'mono' }, q.at.slice(0, 16).replace('T', ' ')),
                el('td', {}, q.email),
                el('td', {}, q.scope),
                el('td', {}, q.answeredBy === 'data agent' ? 'Data agent' : `${q.answeredBy === 'quick answer' ? 'Quick answer' : 'No answer'} (agent: ${q.agent}${q.error ? `, ${q.error}` : ''}${q.quickError ? `; quick answer failed: ${q.quickError}` : ''})`, q.chart ? ' · chart' : '', q.images ? ` · ${q.images} image(s)` : ''),
                el(
                  'td',
                  {},
                  q.question,
                  q.answer ? el('details', { class: 'answer' }, el('summary', {}, 'Answer'), el('p', { class: 'answer-text' }, q.answer)) : null,
                ),
              ),
            )
          : [el('tr', {}, el('td', { colspan: 5 }, 'Nobody has asked anything yet.'))]),
      );
      $('#questions-table').hidden = false;
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

function renderBranding(t) {
  const branding = t.branding || {};
  for (const img of [$('#c-logo'), $('#branding-preview')]) {
    img.hidden = !branding.logoUrl;
    if (branding.logoUrl) img.src = branding.logoUrl;
    else img.removeAttribute('src');
  }
  $('#logo-remove').hidden = !branding.logoUrl;
  $('#branding-where').textContent = `The logo and accent color this customer's people see on their sign-in page and in the app${t.url ? ` at ${t.url.replace(/\/$/, '')}` : ''}.`;
  // Don't overwrite what the operator is typing.
  if (document.activeElement !== $('#brand-color')) $('#brand-color').value = branding.color || '';
}

$('#logo-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = $('#logo-file').files[0];
  if (!file) {
    toast('Choose a logo file first.', 'error');
    return;
  }
  if (file.size > 64 * 1024) {
    toast(`That file is ${Math.ceil(file.size / 1024)} KB; logos can be at most 64 KB.`, 'error');
    return;
  }
  await withBusy(submitButton(event), 'Uploading…', async () => {
    try {
      state.tenant = await api(`/api/admin/tenants/${state.selectedId}/logo`, { method: 'PUT', raw: file, headers: { 'content-type': file.type || 'application/octet-stream' } });
      event.target.reset();
      renderTenant();
      toast('Logo updated.');
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

$('#logo-remove').addEventListener('click', async (event) => {
  await withBusy(event.currentTarget, 'Removing…', async () => {
    try {
      state.tenant = await api(`/api/admin/tenants/${state.selectedId}/logo`, { method: 'DELETE' });
      renderTenant();
      toast('Logo removed.');
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

$('#color-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  await withBusy(submitButton(event), 'Saving…', async () => {
    try {
      state.tenant = await api(`/api/admin/tenants/${state.selectedId}`, { method: 'PATCH', body: { color: $('#brand-color').value.trim() } });
      renderTenant();
      toast(state.tenant.branding?.color ? 'Accent color saved.' : 'Back to the default color.');
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

$('#user-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const email = $('#new-user-email').value.trim();
  const name = $('#new-user-name').value.trim();
  const role = $('#new-user-role').value;
  const territories = role === 'rep' ? checkedTerritories($('#new-user-territories')) : [];
  if (!email) {
    toast("Enter the person's email address.", 'error');
    $('#new-user-email').focus();
    return;
  }
  if (role === 'rep' && !territories.length) {
    toast('Pick at least one territory for a sales rep, or make them a sales manager.', 'error');
    $('#new-user-territories').querySelector('input')?.focus();
    return;
  }
  await withBusy(submitButton(event), 'Adding…', async () => {
    try {
      const result = await api(`/api/admin/tenants/${state.selectedId}/users`, { method: 'POST', body: { email, name, role, territories, canEdit: $('#new-user-can-edit').checked, canCreate: $('#new-user-can-create').checked } });
      event.target.reset();
      syncTerritoryChecks($('#new-user-role'), $('#new-user-territories'));
      showPassword(result.user.email, result.password);
      await refreshTenant();
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

// ---------- Tabs ----------

function setTabEnabled(name, enabled, reason) {
  const tab = $(`#tab-${name}`);
  tab.disabled = !enabled;
  tab.title = enabled ? '' : reason;
}

function activateTab(name, { focus = false } = {}) {
  if ($(`#tab-${name}`).disabled) name = 'overview';
  state.tab = name;
  for (const tabName of TABS) {
    const selected = tabName === name;
    const tab = $(`#tab-${tabName}`);
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    $(`#panel-${tabName}`).hidden = !selected;
  }
  if (focus) $(`#tab-${name}`).focus();
  if (name === 'overview') loadItems();
  if (name === 'data') loadData();
  if (name === 'reports') loadReports();
  if (name === 'ask') renderConversation();
}

$('#tabs').addEventListener('click', (event) => {
  const tab = event.target.closest('[role="tab"]');
  if (tab && !tab.disabled) activateTab(tab.id.replace('tab-', ''));
});

$('#tabs').addEventListener('keydown', (event) => {
  const enabled = TABS.filter((name) => !$(`#tab-${name}`).disabled);
  const index = enabled.indexOf(state.tab);
  let next = null;
  if (event.key === 'ArrowRight') next = enabled[(index + 1) % enabled.length];
  if (event.key === 'ArrowLeft') next = enabled[(index - 1 + enabled.length) % enabled.length];
  if (event.key === 'Home') next = enabled[0];
  if (event.key === 'End') next = enabled[enabled.length - 1];
  if (next) {
    event.preventDefault();
    activateTab(next, { focus: true });
  }
});

// ---------- Overview ----------

function renderSteps(t) {
  const list = $('#steps');
  if (!t.steps.length) {
    list.replaceChildren(el('li', {}, el('span', { class: 'step-title' }, 'Waiting to start'), statusChip('pending')));
    return;
  }
  list.replaceChildren(
    ...t.steps.map((step) =>
      el(
        'li',
        {},
        el('span', { class: 'step-title' }, step.title),
        statusChip(step.status, STEP_STATUS),
        step.detail ? el('span', { class: 'step-detail' }, step.detail) : null,
        step.error ? el('span', { class: 'step-error' }, step.error) : null,
      ),
    ),
  );
}

function renderActivity(t) {
  $('#activity').replaceChildren(
    ...(t.activity.length
      ? t.activity.map((entry) => el('li', {}, el('time', { datetime: entry.at }, formatTime(entry.at)), el('span', { class: `level-${entry.level}` }, entry.message)))
      : [el('li', {}, 'Nothing yet.')]),
  );
}

const AUDIT_STATUS = { pass: ['✓', 'OK'], info: ['i', 'Note'], warn: ['!', 'Review'], fail: ['✕', 'Fix'] };

async function runAudit(button) {
  const id = state.selectedId;
  await withBusy(button, 'Checking…', async () => {
    try {
      const report = await api(`/api/admin/tenants/${id}/audit`);
      if (state.selectedId !== id) return;
      $('#audit').replaceChildren(
        ...report.checks.map((check) =>
          el('li', {}, el('span', { class: 'step-title' }, check.title), statusChip(check.status, AUDIT_STATUS), el('span', { class: 'step-detail' }, check.detail)),
        ),
      );
      toast(report.ok ? `No access problems (${report.counts.warn} to review).` : `${report.counts.fail} access problem${report.counts.fail === 1 ? '' : 's'} to fix.`, report.ok ? 'info' : 'error');
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}

$('#run-audit').addEventListener('click', (event) => runAudit(event.currentTarget));

async function loadItems() {
  const body = $('#items-body');
  const t = state.tenant;
  const workspaceReady = t?.steps.some((s) => s.key === 'workspace' && s.status === 'done');
  if (!workspaceReady || isBusy(t.status)) {
    body.replaceChildren(emptyRow(3, t && isBusy(t.status) ? 'Items show up here when provisioning finishes.' : 'No workspace yet.'));
    return;
  }
  try {
    const items = await api(`/api/admin/tenants/${t.id}/items`);
    body.replaceChildren(
      ...(items.length
        ? items.map((item) =>
            el('tr', {}, el('td', {}, item.displayName), el('td', {}, el('span', { class: 'tag' }, typeLabel(item.type))), el('td', { class: 'mono', title: item.id }, item.id.slice(0, 8))),
          )
        : [emptyRow(3, 'The workspace is empty.')]),
    );
  } catch (error) {
    body.replaceChildren(emptyRow(3, error.message));
  }
}

$('#retry').addEventListener('click', async (event) => {
  await withBusy(event.currentTarget, 'Starting…', async () => {
    try {
      await api(`/api/admin/tenants/${state.selectedId}/provision`, { method: 'POST', body: {} });
      await refreshTenant();
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

// ---------- Data ----------

const tableSource = (name) => (name.startsWith('crm_') ? 'CRM app' : name.startsWith('gold_') ? 'Pipeline output' : 'Customer data');

function renderLoads(t) {
  $('#loads-body').replaceChildren(
    ...(t.ingestions.length
      ? t.ingestions.map((load) =>
          el('tr', {}, el('td', {}, formatTime(load.at)), el('td', {}, load.source), el('td', {}, load.table), el('td', { class: 'num' }, formatBytes(load.bytes))),
        )
      : [emptyRow(4, 'No loads yet.')]),
  );
}

async function loadData() {
  const t = state.tenant;
  renderLoads(t);
  try {
    const [tables, items] = await Promise.all([api(`/api/admin/tenants/${t.id}/tables`), api(`/api/admin/tenants/${t.id}/items`)]);
    if (state.selectedId !== t.id) return;
    $('#tables-body').replaceChildren(
      ...(tables.length
        ? tables.map((table) => el('tr', {}, el('td', {}, table.name), el('td', {}, el('span', { class: 'tag' }, tableSource(table.name)))))
        : [emptyRow(2, 'No tables yet. Load something above.')]),
    );
    renderRunnables(items.filter((item) => item.runnable));
  } catch (error) {
    $('#tables-body').replaceChildren(emptyRow(2, error.message));
  }
}

function jobLine(job) {
  return el('span', {}, statusChip(job.status, JOB_STATUS), job.failureReason ? ` ${job.failureReason}` : '');
}

function renderRunnables(items) {
  const list = $('#runnables');
  if (!items.length) {
    list.replaceChildren(el('li', {}, el('span', { class: 'tag' }, 'None yet. Pipelines and notebooks in the template workspace are copied here.')));
    return;
  }
  list.replaceChildren(
    ...items.map((item) => {
      const job = state.jobs.get(item.id);
      const button = el('button', { class: 'button small', type: 'button', onclick: () => runItem(item, button) }, 'Run');
      return el(
        'li',
        { 'data-item': item.id },
        el('span', {}, item.displayName, ' ', el('span', { class: 'tag' }, typeLabel(item.type))),
        button,
        el('span', { class: 'job' }, job ? jobLine(job) : ''),
      );
    }),
  );
}

async function runItem(item, button) {
  const tenantId = state.selectedId;
  await withBusy(button, 'Starting…', async () => {
    try {
      const started = await api(`/api/admin/tenants/${tenantId}/items/${item.id}/jobs`, { method: 'POST', body: {} });
      if (!started.jobInstanceId) {
        toast(`${item.displayName} started. Fabric didn't return a job ID to track.`);
        return;
      }
      state.jobs.set(item.id, { status: started.status || 'NotStarted' });
      trackJob(tenantId, item, started.jobInstanceId);
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}

function trackJob(tenantId, item, jobId) {
  const tick = async () => {
    if (state.selectedId !== tenantId) return;
    try {
      const job = await api(`/api/admin/tenants/${tenantId}/items/${item.id}/jobs/${jobId}`);
      state.jobs.set(item.id, job);
      const slot = document.querySelector(`#runnables [data-item="${item.id}"] .job`);
      if (slot) slot.replaceChildren(jobLine(job));
      if (TERMINAL_JOB.has(job.status)) {
        if (job.status === 'Completed') {
          toast(`${item.displayName} finished.`);
          if (state.tab === 'data') loadData();
        } else toast(`${item.displayName}: ${job.failureReason || job.status}`, 'error');
        return;
      }
      setTimeout(tick, 2000);
    } catch (error) {
      toast(error.message, 'error');
    }
  };
  tick();
}

async function afterLoad(message) {
  toast(message);
  await refreshTenant();
  if (state.tab === 'data') loadData();
}

$('#app-data-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  await withBusy(submitButton(event), 'Syncing…', async () => {
    try {
      const result = await api(`/api/admin/tenants/${state.selectedId}/imports/app-data`, { method: 'POST', body: {} });
      await afterLoad(`Loaded ${result.records.map((r) => r.table).join(', ')}.`);
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

$('#upload-file').addEventListener('change', (event) => {
  const file = event.target.files[0];
  $('#upload-table').placeholder = file ? tableName(stemOf(file.name)) : 'from the file name';
});

async function excelToCsvUploads(file, table) {
  if (!window.XLSX) throw new Error("The Excel converter didn't load (it comes from cdn.sheetjs.com). Save the sheet as CSV instead.");
  const workbook = window.XLSX.read(await file.arrayBuffer(), { cellDates: true });
  const sheets = workbook.SheetNames.map((name) => ({
    name,
    csv: window.XLSX.utils.sheet_to_csv(workbook.Sheets[name], { blankrows: false, dateNF: 'yyyy-mm-dd' }),
  })).filter((sheet) => sheet.csv.trim());
  if (!sheets.length) throw new Error('The workbook has no data.');
  return sheets.map((sheet) => ({
    name: `${stemOf(file.name)}_${sheet.name}.csv`,
    body: new Blob([sheet.csv], { type: 'text/csv' }),
    table: sheets.length > 1 ? `${table}_${tableName(sheet.name)}` : table,
  }));
}

$('#upload-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  const file = $('#upload-file').files[0];
  if (!file) {
    toast('Choose a file first.', 'error');
    $('#upload-file').focus();
    return;
  }
  const mode = new FormData(form).get('upload-mode') || 'Overwrite';
  const table = tableName($('#upload-table').value.trim() || stemOf(file.name));
  await withBusy(submitButton(event), 'Loading…', async () => {
    try {
      const uploads = /\.(xlsx|xls)$/i.test(file.name) ? await excelToCsvUploads(file, table) : [{ name: file.name, body: file, table }];
      const loaded = [];
      for (const upload of uploads) {
        const result = await api(`/api/admin/tenants/${state.selectedId}/uploads?table=${encodeURIComponent(upload.table)}&mode=${mode}`, {
          method: 'POST',
          raw: upload.body,
          headers: { 'x-file-name': encodeURIComponent(upload.name), 'content-type': 'application/octet-stream' },
        });
        loaded.push(result.table);
      }
      form.reset();
      $('#upload-table').placeholder = 'from the file name';
      await afterLoad(`Loaded ${loaded.join(', ')}.`);
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

$('#web-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const url = $('#web-url').value.trim();
  if (!url) {
    toast('Enter a URL.', 'error');
    $('#web-url').focus();
    return;
  }
  await withBusy(submitButton(event), 'Importing…', async () => {
    try {
      const table = $('#web-table').value.trim();
      const result = await api(`/api/admin/tenants/${state.selectedId}/imports/web`, { method: 'POST', body: { url, table: table ? tableName(table) : undefined } });
      event.target.reset();
      await afterLoad(`Loaded ${result.table}.`);
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

// ---------- Reports ----------

function resetEmbed() {
  clearInterval(state.embedTimer);
  state.embedRequest = null;
  state.checkEmbedToken = null;
  const container = $('#embed-container');
  try {
    window.powerbi?.reset(container);
  } catch {
    // Nothing embedded yet.
  }
  container.replaceChildren(el('p', { class: 'embed-empty' }, 'Pick a report to open it here.'));
  $('#token-details').hidden = true;
}

async function loadReports() {
  const t = state.tenant;
  $('#authoring-note').textContent = t.features.authoring
    ? 'This edition lets the customer edit reports and build new ones, including the describe-a-chart box.'
    : 'This edition is view-only. Professional adds report building.';
  try {
    const { reports, datasets } = await api(`/api/admin/tenants/${t.id}/reports`);
    if (state.selectedId !== t.id) return;
    $('#report-list').replaceChildren(
      ...(reports.length
        ? reports.map((report) =>
            el(
              'li',
              {},
              el('span', {}, report.name),
              el(
                'span',
                { class: 'actions' },
                el('button', { class: 'button small', type: 'button', onclick: () => openEmbed({ mode: 'view', reportId: report.id }) }, 'View'),
                t.features.authoring ? el('button', { class: 'button small', type: 'button', onclick: () => openEmbed({ mode: 'edit', reportId: report.id }) }, 'Edit') : null,
              ),
            ),
          )
        : [el('li', {}, el('span', { class: 'tag' }, 'No reports yet. Reports come from the template workspace.'))]),
    );
    $('#dataset-list').replaceChildren(
      ...(datasets.length
        ? datasets.map((dataset) =>
            el(
              'li',
              {},
              el('span', {}, dataset.name),
              t.features.authoring && dataset.canCreateReport
                ? el('span', { class: 'actions' }, el('button', { class: 'button small', type: 'button', onclick: () => openEmbed({ mode: 'create', datasetId: dataset.id }) }, 'New report'))
                : null,
            ),
          )
        : [el('li', {}, el('span', { class: 'tag' }, 'No semantic models yet.'))]),
    );
  } catch (error) {
    $('#report-list').replaceChildren(el('li', {}, el('span', { class: 'tag' }, error.message)));
    $('#dataset-list').replaceChildren();
  }
}

function mockEmbed(config) {
  const what =
    config.kind === 'create' ? 'a blank report canvas on this semantic model' : config.mode === 'edit' ? 'this report in edit mode' : 'this report';
  return el(
    'div',
    { class: 'embed-mock' },
    el('h3', {}, config.kind === 'create' ? `New report on ${config.name}` : config.name),
    el('p', {}, `Mock mode has no Power BI, so nothing renders here. In live mode the browser opens ${what} with the embed token described below.`),
    el('p', {}, "The token covers only this customer's workspace, and the customer's users don't need Power BI licenses."),
  );
}

function embedLive(container, config) {
  const client = window['powerbi-client'];
  if (!window.powerbi || !client) {
    container.replaceChildren(el('p', { class: 'embed-empty' }, "The Power BI JavaScript client didn't load (it comes from cdn.jsdelivr.net)."));
    return;
  }
  const { models } = client;
  container.replaceChildren();
  window.powerbi.reset(container);
  const embedded =
    config.kind === 'create'
      ? window.powerbi.createReport(container, { tokenType: models.TokenType.Embed, accessToken: config.accessToken, embedUrl: config.embedUrl, datasetId: config.datasetId })
      : window.powerbi.embed(container, {
          type: 'report',
          id: config.reportId,
          embedUrl: config.embedUrl,
          accessToken: config.accessToken,
          tokenType: models.TokenType.Embed,
          permissions: config.mode === 'edit' ? models.Permissions.All : models.Permissions.Read,
          viewMode: config.mode === 'edit' ? models.ViewMode.Edit : models.ViewMode.View,
          settings: { panes: { filters: { visible: false } } },
        });
  embedded.on('error', (event) => toast(event.detail?.message || 'Power BI reported an error.', 'error'));
  embedded.on('saved', () => {
    toast('Report saved.');
    loadReports();
  });
  scheduleTokenRefresh(embedded, config);
}

// Embed tokens are short-lived. Check every 30 seconds and whenever the tab becomes visible again, and swap in a fresh
// token when it's due (embed-token.js says when).
function scheduleTokenRefresh(embedded, config) {
  clearInterval(state.embedTimer);
  let refreshAt = refreshTimeOf(config);
  let refreshing = false;
  const owner = state.embedRequest;
  state.checkEmbedToken = async () => {
    if (refreshing || !owner || state.embedRequest !== owner || owner.tenantId !== state.selectedId) return;
    if (Date.now() < refreshAt) return;
    refreshing = true;
    try {
      const fresh = await api(`/api/admin/tenants/${owner.tenantId}/embed`, { method: 'POST', body: owner.request });
      await embedded.setAccessToken(fresh.accessToken);
      refreshAt = refreshTimeOf(fresh);
    } catch (error) {
      clearInterval(state.embedTimer);
      toast(`Couldn't refresh the embed token: ${error.message}`, 'error');
    } finally {
      refreshing = false;
    }
  };
  state.embedTimer = setInterval(() => state.checkEmbedToken?.(), TOKEN_CHECK_MS);
}

document.addEventListener('visibilitychange', () => {
  if (!document.hidden) state.checkEmbedToken?.();
});

async function openEmbed(request) {
  const container = $('#embed-container');
  clearInterval(state.embedTimer);
  container.replaceChildren(el('p', { class: 'embed-empty' }, 'Getting an embed token…'));
  try {
    const config = await api(`/api/admin/tenants/${state.selectedId}/embed`, { method: 'POST', body: request });
    state.embedRequest = { tenantId: state.selectedId, request };
    $('#token-details').hidden = false;
    $('#token-request').textContent = [
      'POST https://api.powerbi.com/v1.0/myorg/GenerateToken',
      JSON.stringify(config.tokenRequest, null, 2),
      '',
      `The token expires at ${new Date(config.expiration).toLocaleTimeString()}.`,
    ].join('\n');
    if (config.mock) container.replaceChildren(mockEmbed(config));
    else embedLive(container, config);
  } catch (error) {
    container.replaceChildren(el('p', { class: 'embed-empty' }, error.message));
  }
}

// ---------- Ask ----------

function renderConversation() {
  const turns = state.conversations.get(state.selectedId) || [];
  $('#conversation').replaceChildren(
    ...turns.map((turn) =>
      el(
        'li',
        { class: `turn ${turn.role}${turn.error ? ' error' : ''}` },
        el('span', { class: 'who' }, turn.role === 'user' ? 'You' : 'Data agent'),
        el('div', { class: 'text' }, turn.text),
        turn.meta ? el('span', { class: 'meta' }, turn.meta) : null,
      ),
    ),
  );
  $('#ask-note').textContent = state.config.live
    ? "Questions go to this customer's published data agent through its MCP endpoint, signed in as the customer's service account."
    : 'Mock mode answers simple questions about tables, row counts and columns.';
  $('#suggestions').replaceChildren(
    ...SUGGESTIONS.map((question) =>
      el(
        'li',
        {},
        el('button', {
          type: 'button',
          onclick: () => {
            $('#question').value = question;
            $('#question').focus();
          },
        }, question),
      ),
    ),
  );
}

$('#question').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    $('#ask-form').requestSubmit();
  }
});

$('#ask-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const question = $('#question').value.trim();
  if (!question) return;
  const tenantId = state.selectedId;
  const turns = state.conversations.get(tenantId) || [];
  state.conversations.set(tenantId, turns);
  const pending = { role: 'agent', text: 'Thinking…' };
  turns.push({ role: 'user', text: question }, pending);
  $('#question').value = '';
  renderConversation();
  await withBusy(submitButton(event), 'Asking…', async () => {
    try {
      const result = await api(`/api/admin/tenants/${tenantId}/agent/ask`, { method: 'POST', body: { question } });
      pending.text = result.answer || 'The agent returned no text.';
      pending.meta = `${result.tool} · ${(result.ms / 1000).toFixed(1)} s`;
    } catch (error) {
      pending.text = error.message;
      pending.error = true;
    }
  });
  if (state.selectedId === tenantId && state.tab === 'ask') renderConversation();
});

// ---------- License ----------

$('#plan-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const plan = new FormData(event.target).get('plan');
  if (!plan) return;
  await withBusy(submitButton(event), 'Applying…', async () => {
    try {
      await api(`/api/admin/tenants/${state.selectedId}`, { method: 'PATCH', body: { plan } });
      state.planRenderedFor = null;
      toast('Applying the edition. Provisioning runs again.');
      await refreshTenant();
      activateTab('overview');
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

$('#delete-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const typed = $('#delete-confirm').value.trim();
  const tenant = state.tenant;
  if (typed !== tenant.name) {
    toast('Type the exact customer name to confirm.', 'error');
    $('#delete-confirm').focus();
    return;
  }
  await withBusy(submitButton(event), 'Removing…', async () => {
    try {
      const keepWorkspace = $('#keep-workspace').checked;
      await api(`/api/admin/tenants/${tenant.id}?confirm=${encodeURIComponent(typed)}&keepWorkspace=${keepWorkspace}`, { method: 'DELETE' });
      event.target.reset();
      state.tenants = state.tenants.filter((t) => t.id !== tenant.id);
      state.conversations.delete(tenant.id);
      toast(keepWorkspace ? `${tenant.name} was removed. Its workspace was kept.` : `${tenant.name} and its workspace were deleted.`);
      await selectTenant(null);
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

// ---------- Add a customer ----------

$('#add-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  const name = $('#new-name').value.trim();
  const plan = new FormData(form).get('new-plan');
  const workspaceId = $('#new-workspace').value.trim() || undefined;
  const domain = $('#new-domain').value.trim();
  if (name.length < 2) {
    toast('Enter a company name of 2 to 60 characters.', 'error');
    $('#new-name').focus();
    return;
  }
  await withBusy(submitButton(event), 'Creating…', async () => {
    try {
      const addons = $('#new-integration').checked ? ['integration'] : [];
      const capacityId = $('#new-capacity').value.trim() || undefined;
      const tenant = await api('/api/admin/tenants', { method: 'POST', body: { name, plan, workspaceId, capacityId, addons, sampleData: $('#new-sample').checked, domains: domain ? [domain] : [] } });
      state.tenants.push({ id: tenant.id, name: tenant.name, plan: tenant.plan, planName: tenant.planName, status: tenant.status });
      form.reset();
      renderPlanPicker($('#new-plan'), 'new-plan', state.config.plans[0]?.id);
      await selectTenant(tenant.id);
    } catch (error) {
      toast(error.message, 'error');
    }
  });
});

// ---------- Start ----------

async function init() {
  try {
    const session = await api('/api/admin/session');
    if (session.required && !session.signedIn) await operatorSignIn();
    state.operator = session.signedIn ? session : await api('/api/admin/session');
    state.config = await api('/api/admin/config');
  } catch (error) {
    toast(`Can't reach the platform server: ${error.message}`, 'error');
    return;
  }
  renderEnv();
  renderPlanPicker($('#new-plan'), 'new-plan', state.config.plans[0]?.id);
  await refreshList();
  const match = /customer=([0-9a-f-]{36})/i.exec(location.hash);
  if (match && state.tenants.some((t) => t.id === match[1])) await selectTenant(match[1]);
  else showIntro();
  setInterval(refreshList, 10_000);
}

init();
