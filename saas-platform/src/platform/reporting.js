import { HttpError } from '../http/router.js';
import { STARTER_REPORT_NAME } from '../crm/workload.js';
import { entitlements } from './plans.js';

// Embedding for customers ("app owns data"): the customer's service account asks Power BI for a short-lived V2 embed
// token that only covers this customer's report, semantic model and workspace. End users need no Power BI license.
// lifetimeInMinutes can only shorten a token; the browser asks for a new one before it runs out.
// https://learn.microsoft.com/power-bi/developer/embedded/embed-sample-for-customers
// https://learn.microsoft.com/rest/api/power-bi/embed-token/generate-token

const clampLifetime = (minutes) => Math.min(60, Math.max(5, Math.round(Number(minutes) || 30)));
// How long the token has left, by the server's clock. The browser counts from when the token arrives, so a device
// clock that's wrong neither refreshes too late nor over and over.
const secondsLeft = (expiration) => Math.max(0, Math.round((Date.parse(expiration) - Date.now()) / 1000));

// Row-level security: Power BI says which models need the viewer's identity (isEffectiveIdentityRequired) and roles.
// Those get the identity; models without roles must not. No identity, or no roles, for a model that needs them means
// no token at all. A viewer limited to some territories (`identity.limited`) only ever gets tokens for models that
// enforce row-level security, so a model without roles can't show them everyone's data.
// https://learn.microsoft.com/power-bi/developer/embedded/embedded-row-level-security
function identitiesFor(datasets, identity) {
  if (identity?.limited && datasets.some((d) => !d?.isEffectiveIdentityRequired)) throw new HttpError(403, "This report isn't available for your territories.");
  const secured = datasets.filter((d) => d?.isEffectiveIdentityRequired);
  if (!secured.length) return undefined;
  if (!identity?.username) throw new HttpError(403, 'This report needs to know who is viewing it.');
  if (!identity.roles?.length && secured.some((d) => d.isEffectiveIdentityRolesRequired)) {
    throw new HttpError(403, "You don't have a sales territory yet. Ask your administrator to assign one.");
  }
  return [{ username: identity.username, roles: identity.roles || [], datasets: secured.map((d) => d.id) }];
}

export async function listReporting({ fabric, tenant }) {
  const workspaceId = tenant.fabric.workspaceId;
  const [reports, datasets] = await Promise.all([fabric.pbiListReports(workspaceId), fabric.pbiListDatasets(workspaceId)]);
  return {
    reports: reports.map((r) => ({ id: r.id, name: r.name, datasetId: r.datasetId || null, reportType: r.reportType || 'PowerBIReport' })),
    datasets: datasets.map((d) => ({ id: d.id, name: d.name, canCreateReport: Boolean(d.createReportEmbedURL) })),
  };
}

// The reports the platform provides: the generated starter report, or the ones copied from the template workspace.
// Until customers build their own (REPORT_AUTHORING), these are the only reports the app shows and embeds.
export function isStandardReport(tenant, report) {
  const ids = [tenant.fabric?.starterReportId, ...(tenant.fabric?.templateItems || []).filter((i) => i.type === 'Report').map((i) => i.id)].filter(Boolean);
  if (!ids.length) return report.name === STARTER_REPORT_NAME;
  return ids.some((id) => String(id).toLowerCase() === String(report.id).toLowerCase());
}

// `identity` is who is viewing: { username, roles, limited } with the row-level security roles they may use.
// `datasetIds`, when given, are the only models new reports may be built on; `allowReport`, which reports may open.
// `canCreate`: whether the person may create reports. Only then does a token name the workspace, which is what lets
// "Save as" and "New report" save there (Microsoft's App-Owns-Data Starter Kit does the same).
export async function createEmbedConfig({ fabric, tenant, mode = 'view', reportId, datasetId, lifetimeMinutes = 30, identity = null, datasetIds = null, allowReport = null, canCreate = true }) {
  const workspaceId = tenant.fabric.workspaceId;
  const { plan, features } = entitlements(tenant);
  const lifetimeInMinutes = clampLifetime(lifetimeMinutes);
  if (!['view', 'edit', 'create'].includes(mode)) throw new HttpError(400, 'mode must be view, edit or create.');
  if (mode !== 'view' && !features.authoring) {
    throw new HttpError(403, `The ${plan.name} edition doesn't include report authoring.`);
  }
  if (mode === 'create' && !canCreate) throw new HttpError(403, "You don't have permission to create reports.");

  if (mode === 'create') {
    // IDs come from the browser, so only accept ones that exist in this customer's own workspace.
    const dataset = (await fabric.pbiListDatasets(workspaceId)).find((d) => d.id === datasetId && (!datasetIds || datasetIds.includes(d.id)));
    if (!dataset) throw new HttpError(404, "That semantic model isn't in this customer's workspace.");
    if (!dataset.createReportEmbedURL) throw new HttpError(409, "Power BI didn't return a create URL for this semantic model.");
    const identities = identitiesFor([dataset], identity);
    const tokenRequest = { datasets: [{ id: dataset.id }], targetWorkspaces: [{ id: workspaceId }], ...(identities ? { identities } : {}), lifetimeInMinutes };
    const token = await fabric.pbiGenerateToken(tokenRequest);
    return { kind: 'create', mode, datasetId: dataset.id, name: dataset.name, embedUrl: dataset.createReportEmbedURL, accessToken: token.token, tokenId: token.tokenId || null, expiration: token.expiration, expiresInSeconds: secondsLeft(token.expiration), tokenRequest };
  }

  const [reports, datasets] = await Promise.all([fabric.pbiListReports(workspaceId), fabric.pbiListDatasets(workspaceId)]);
  const report = reports.find((r) => r.id === reportId);
  if (!report || (allowReport && !allowReport(report))) throw new HttpError(404, "That report isn't in this customer's workspace.");
  const allowEdit = mode === 'edit';
  const identities = identitiesFor(report.datasetId ? [datasets.find((d) => d.id === report.datasetId)] : [], identity);
  const tokenRequest = {
    reports: [{ id: report.id, ...(allowEdit ? { allowEdit: true } : {}) }],
    datasets: report.datasetId ? [{ id: report.datasetId }] : [],
    ...(allowEdit && canCreate ? { targetWorkspaces: [{ id: workspaceId }] } : {}),
    ...(identities ? { identities } : {}),
    lifetimeInMinutes,
  };
  const token = await fabric.pbiGenerateToken(tokenRequest);
  return {
    kind: 'report',
    mode,
    reportId: report.id,
    datasetId: report.datasetId || null,
    name: report.name,
    embedUrl: report.embedUrl,
    accessToken: token.token,
    // The token's ID (not a secret): the usage log records it, so a view can be traced to the token that opened it.
    tokenId: token.tokenId || null,
    expiration: token.expiration,
    expiresInSeconds: secondsLeft(token.expiration),
    tokenRequest,
  };
}
