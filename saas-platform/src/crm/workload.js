// HiCRM's workload: what the framework needs to know about the application it hosts.
//
// The framework core (src/auth, src/fabric, src/http, src/platform) reaches the sample application only through this
// module, and test/framework.test.js enforces it. To host another application, replace src/crm and implement the same
// exports. FRAMEWORK.md, "Adopting the framework", describes each one.

// Data: the tenant's operational database (schema, migrations, sample data) and its data access.
export { createCrmService } from './index.js';
export { createFabricSqlStore } from './stores.js';
export { CRM_SCHEMA_VERSION, TERRITORIES } from './schema.js';
export { pilotPersonas, sampleSeedOf } from './seed.js';

// Analytics: the semantic model with row-level security, its role-free twin for the data agent, the roles a person
// gets, and the standard report.
export { ALL_TERRITORIES_ROLE, ASSISTANT_MODEL_NAME, MODEL_NAME, agentTables, buildSemanticModelDefinition, rolesFor } from './model.js';
export { STARTER_REPORT_NAME, buildStarterReportDefinition } from './report.js';

// AI: the questions the assistant suggests when it can't answer.
export { QUICK_EXAMPLES } from './insights.js';

// Validation (npm run validate): how to show row-level security at work, and what to ask the data agent.
export const RLS_PROBE = Object.freeze({
  // A visual of the standard report broken down by the row-level security dimension. Each person must see only the
  // labels their roles allow.
  visual: 'Pipeline by state',
  // The same breakdown as a quick answer from the tenant's database, scoped the same way, to reconcile the numbers.
  question: 'pipeline by state',
  // The column the roles filter: the validator also applies a report filter asking for every territory, which must
  // not show anyone more than their roles allow.
  column: Object.freeze({ table: 'Accounts', column: 'State' }),
});
export const AGENT_PROBE_QUESTION = 'What is the total pipeline value of open opportunities by state?';
