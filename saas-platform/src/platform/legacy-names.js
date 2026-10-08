// Names that earlier versions gave to resources that are already deployed, from before the product was called
// "Platform app". Provisioning, the identity broker and scripts/bootstrap-identities.ps1 look for these as well, and
// rename what they find in place, so an upgrade never leaves a second database, model, agent, connection or app
// registration behind. This is the only file that still holds the old names (test/naming.test.js checks).

// The product name, as it appears in connection and app registration names.
export const LEGACY_PRODUCT_NAMES = Object.freeze(['HiCRM']);

// Fabric items, by what they're for.
export const LEGACY_ITEM_NAMES = Object.freeze({
  crmDatabase: Object.freeze(['hicrm_db']),
  reportsModel: Object.freeze(['HiCRM Insights']),
  assistantModel: Object.freeze(['HiCRM Insights - Assistant']),
  dataAgent: Object.freeze(['HiCRM Assistant']),
});

// The shared Direct Lake expression inside a semantic model. This one isn't renamed: Analysis Services can't rename it
// in a definition update, so a model published under one of these keeps it.
export const LEGACY_DIRECT_LAKE_EXPRESSIONS = Object.freeze(['DirectLake - HiCRM']);

// Microsoft Graph tags on the app registrations and service principals the platform created for customers.
export const legacyTenantTags = (tenantId) => [`hicrm-tenant-${tenantId}`];
export const LEGACY_SERVICE_ACCOUNT_TAGS = Object.freeze(['hicrm-service-account']);
