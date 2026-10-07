// HiCRM editions. The edition decides which Fabric resources a customer gets and which features the app shows.
// Customers never see edition names; the app simply shows or hides features.

export const CORE_ITEMS = Object.freeze({
  sqlDatabase: { type: 'SQLDatabase', name: 'hicrm_db' },
  semanticModel: { type: 'SemanticModel', name: 'HiCRM Insights' },
  dataAgent: { type: 'DataAgent', name: 'HiCRM Assistant' },
  lakehouse: { type: 'Lakehouse', name: 'lh_customer' },
  warehouse: { type: 'Warehouse', name: 'wh_customer' },
});

const REPORT_TEMPLATE_TYPES = ['Report'];

export const PLANS = Object.freeze({
  standard: {
    id: 'standard',
    name: 'Standard',
    summary: 'HiCRM with ready-made reports over the CRM data.',
    resources: { crm: true, semanticModel: true, dataAgent: false },
    features: { crm: true, reports: true, authoring: false, agent: false, ingestion: false },
    templateTypes: REPORT_TEMPLATE_TYPES,
  },
  professional: {
    id: 'professional',
    name: 'Professional',
    summary: 'Adds building and editing your own reports, with a describe-a-chart box.',
    resources: { crm: true, semanticModel: true, dataAgent: false },
    features: { crm: true, reports: true, authoring: true, agent: false, ingestion: false },
    templateTypes: REPORT_TEMPLATE_TYPES,
  },
  enterprise: {
    id: 'enterprise',
    name: 'Enterprise',
    summary: 'Adds the assistant: questions in plain language, right on the report page.',
    resources: { crm: true, semanticModel: true, dataAgent: true },
    features: { crm: true, reports: true, authoring: true, agent: true, ingestion: false },
    templateTypes: [...REPORT_TEMPLATE_TYPES, 'DataAgent'],
  },
});

// Optional add-ons on top of an edition. Data integration (files, web, pipelines) is outside the current build-out.
export const ADDONS = Object.freeze({
  integration: {
    id: 'integration',
    name: 'Data integration',
    resources: { lakehouse: true },
    features: { ingestion: true },
  },
});

// Earlier plan IDs keep working for existing customer records.
const LEGACY_PLANS = { analytics: 'standard', 'analytics-plus': 'professional', 'analytics-ai': 'enterprise' };

export function getPlan(id) {
  return PLANS[id] || PLANS[LEGACY_PLANS[id]] || null;
}

export function listPlans() {
  return Object.values(PLANS).map(({ id, name, summary, resources, features }) => ({ id, name, summary, resources, features }));
}

export function listAddons() {
  return Object.values(ADDONS).map(({ id, name }) => ({ id, name }));
}

// The edition plus add-ons: what this customer is entitled to.
export function entitlements(tenant) {
  const plan = getPlan(tenant.plan);
  const addons = (tenant.addons || []).map((id) => ADDONS[id]).filter(Boolean);
  return {
    plan,
    resources: Object.assign({}, plan.resources, ...addons.map((a) => a.resources)),
    features: Object.assign({}, plan.features, ...addons.map((a) => a.features)),
  };
}
