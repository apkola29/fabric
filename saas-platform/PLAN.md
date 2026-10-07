# Plan: Platform app with Fabric behind the scenes

Last updated: 2026-10-02. This file is the source of truth for decisions, architecture, phases and verified findings.
The architecture, identities and runtime flows are drawn in [ARCHITECTURE.md](ARCHITECTURE.md); how to run it is in
[README.md](README.md).

Status words: **Done** (built and verified against the service), **Partly done**, **Next**, **Not started**. Findings are tagged **[Tenant]** (checked in tenant `<tenant-id>`), **[Docs]** (stated by Microsoft Learn, not yet exercised here) or **[Assumption]** (untested).

## 0. Current build-out (scaled down)

Scope:
- the CRM on Fabric SQL;
- one semantic model with relationships and territory roles, plus its twin without roles for the data agent;
- a standard embedded report;
- the assistant hovering on the report page, with charts;
- two customers, each at its own address with its own logo.

Out of scope:
- customers building their own reports: next phase, behind `REPORT_AUTHORING`;
- pipelines and data integration: they remain as the optional *data integration* add-on.

| Area | Status |
| --- | --- |
| CRM on SQL database in Fabric (`platform_app_db`), schema v3 (territories), sample data dated from the setup day | **Done** [Tenant] |
| Platform app Insights: Direct Lake on OneLake over `platform_app_db`, generated TMDL, 42 measures, 8 relationships, 4 roles | **Done** [Tenant] |
| The twin model without roles for the data agent (service principals can't query a model with roles) | **Done** [Tenant] |
| Fixed identity: cloud connection with the workspace identity, bound to the model | **Done** [Tenant] |
| Standard report "Sales overview" (generated PBIR), embedded view-only with V2 tokens carrying each person's territory role | **Done** [Tenant] |
| Customers editing and building reports, describe-a-chart | **Next phase**: built and tested, off by default (`REPORT_AUTHORING`) |
| Assistant: the data agent over its MCP server for managers, scoped quick answers for reps, charts, question log | **Done** [Tenant] |
| The data agent's code interpreter (preview) | **Partly done**: on in the agent's definition [Tenant]; no image came back on the trial capacity, which the docs exclude |
| Each customer at its own address (`APP_DOMAIN`), with its own logo and color | **Done** [Tenant]: Fabrikam and Contoso |
| Second live customer (Contoso) | **Done** [Tenant]: `saas-contoso`, created by an admin and adopted |
| Per-customer service principal (`fabrikamsa`, `contososa`), Admin of one workspace | **Done** [Tenant]: created by an Entra admin with the bootstrap script; the platform identity handed both workspaces over and keeps no role |
| Editions: Standard, Professional, Enterprise; add-on: data integration | **Done** |
| The framework: workload contract, 34 controls, a validator for the emulator, live Fabric and the browser ([FRAMEWORK.md](FRAMEWORK.md)) | **Done** [Tenant]: live, 19 pass, 3 to review, 1 failing (AI-03, the trial capacity) |
| Embedding as in Microsoft's App-Owns-Data samples: report rights per person, a report usage log, token refresh at any lifetime ([EMBEDDING.md](EMBEDDING.md) section 10) | **Done** [Tenant]: usage logged live; everyone views only while `REPORT_AUTHORING` is off |
| Credentials: MSAL, certificates and federated credentials; nothing secret in project files, asked for at runtime ([REQUIREMENTS.md](REQUIREMENTS.md)) | **Done** [Tenant]: both service principals on certificates; federated tested against a stand-in |
| Row-level security safe for every measure, and proven against filters | **Done** [Tenant]: `TREATAS` instead of `USERELATIONSHIP`; a filter for every state still shows reps their territory only |
| A public project anyone can test: requirements, runtime credentials, a pre-publish check | **Done**: `saas-platform/` in the Fabric repository |

Answers to the questions asked for this build:

- **Fabric IQ MCP instead of data agents?** No.
  - It accepts delegated user sign-in only (no service principals) and has no answering tool; it is meant for
    Copilot-style clients.
  - The data agent's MCP endpoint works with a service principal, so the assistant uses the data agent.
- **Copilot report creation for end users?** Not available for "app owns data" embedding. Building reports in the app
  (the embedded Power BI editor plus a describe-a-chart box) is the next phase.
- **Pro licenses?** None are needed to run it.
  - Service principals do all the work and need no license.
  - With "app owns data", the customers' people need none either.
  - Pro or PPU is only for people who author in the Fabric portal.
- **One semantic model for reports and the agent?** Not with "app owns data". The reasons and the options are in
  [MULTITENANCY.md](MULTITENANCY.md), "Why each customer has two semantic models".

## 1. Goal

**The platform app** is a home-grown CRM sold as SaaS. Each customer company (the first one is **Fabrikam**) gets:

- **The CRM itself:** accounts, contacts, opportunities and activities.
- **Data:** bring in their own data (files, Excel, web sources, systems on their network) next to their CRM data.
- **Reports:** a Reports tab with embedded Power BI reports over their data.
- **Assistant:** an AI tab that answers questions about their data.

Fabric does all the data work: the CRM database, ingestion, warehousing, querying, the data agent and reporting. The
**platform team** runs Fabric. Fabrikam's users only ever see the platform app. They never see Fabric, workspaces,
capacities or plans.

## 2. Verdict: hosting the CRM database on Fabric SQL

Yes, it makes sense, and it's the cleanest story: the CRM writes to a **SQL database in Fabric**. Fabric replicates every table to OneLake in near real time, so the warehouse, reports and data agent read the same data with **no ETL** for the CRM part.

| | Fabric SQL database (proposed) | Azure SQL Database + Fabric mirroring (fallback) |
|---|---|---|
| CRM data in OneLake | Automatic, near real time | Mirroring, near real time |
| Where the database lives | In the customer's workspace | In an Azure SQL elastic pool |
| Effect of capacity load on the CRM | The CRM shares the capacity: SQL work counts as interactive use and can be throttled | The CRM is independent of the capacity |
| Effect of pausing the capacity | The CRM is down | The CRM keeps running; only Insights stop |
| Authentication | Microsoft Entra only (service principal supported) | Entra or SQL authentication |
| Operations | Everything in Fabric | Two services to run |

**Decision D2:** use Fabric SQL database. The app talks to the database through one data-access layer, so a move to Azure SQL with mirroring stays cheap if capacity coupling becomes a problem. Everything downstream (warehouse, reports, data agent) is the same either way, because both land as Delta tables in OneLake.

**Fabric Apps (Rayfin) is not the right host for the customer-facing CRM.** Deployed Fabric Apps sign users in with
Fabric SSO inside the Fabric portal only, so Fabrikam's users would need identities in the platform's Entra tenant
(finding F15). The platform app stays our own web app.

## 3. Architecture

```text
Fabrikam users (browser)
   │  sign in to the platform app (never to Fabric)
   ▼
Platform app  ── run and hosted by the platform team (local now, Azure later)
   ├─ CRM tabs: Accounts · Contacts · Opportunities · Activities
   ├─ Data tab: uploads, web sources, "connect a system on our network" requests
   ├─ Reports tab: embedded Power BI (view; edit and new reports in higher editions)
   └─ Assistant tab: questions in plain language
   │
   │  every call below uses the platform identity (service principal), scoped to the signed-in customer
   ├─ CRM reads and writes ── TDS + Entra token ─────────▶ platform_app_db    (SQL database)
   ├─ Uploads and web pulls ── OneLake API + Load Table ──▶ platform_app_lake  (lakehouse)
   ├─ Report access ── Power BI GenerateToken (V2) ───────▶ report + Platform app Insights model
   └─ Assistant ── MCP endpoint ──────────────────────────▶ Platform app Assistant (data agent)

Workspace "platform-app-fabrikam" (one per customer, managed by the platform team)
   platform_app_db         SQL database: the CRM's own tables. Replicates to OneLake automatically.
   platform_app_lake       Lakehouse: data the customer brings (files, Excel, web, on-premises via pipelines)
   platform_app_wh         Warehouse: gold layer (dimensions, facts) built with T-SQL
                           from platform_app_db + platform_app_lake
   pl_refresh              Pipeline: scheduled sources, then the warehouse refresh procedure
   Platform app Insights   Semantic model: Direct Lake on platform_app_wh, bound to a fixed-identity connection
   Reports                 Pipeline overview, Account health, Team activity
   Platform app Assistant  Data agent over platform_app_wh (and platform_app_db), published, called through MCP

Workspace "platform-app-template" (golden copies, stamped into every customer workspace with IDs remapped)
Control plane (CLI + /admin back office): customers, editions, provisioning, stamping, health
```

**Tenancy:** one workspace per customer, in the platform's Fabric tenant, on capacities the platform owns. The browser
never chooses a customer: the server resolves it from the signed-in user, and every Fabric call is scoped to that
customer's workspace.

**Identities:**

| Who | Identity | Used for |
|---|---|---|
| Fabrikam users | Platform app sign-in (MVP: email domain; production: Entra External ID or multi-tenant Entra, mapped by tenant ID) | The platform app only |
| The platform app's server | Platform service principal `<platform-app-id>` (object ID `<platform-object-id>`) | SQL, OneLake, Fabric REST, Power BI embed tokens, MCP |
| Platform team | Their own Entra accounts | Fabric portal, back office |

## 4. What Fabrikam sees

| Tab | What it does | Behind it |
|---|---|---|
| Accounts, Contacts, Opportunities, Activities | Everyday CRM: lists, details, create and edit | `platform_app_db` |
| Data | Their data sets with source, rows and last update; upload files and Excel; connect web sources; request a connection to a system on their network | `platform_app_lake`, pipelines, requests in the back office |
| Reports | Ready-made reports; edit and create in higher editions | Power BI embedding, per-customer V2 tokens |
| Assistant | Ask questions; answers come from their own data | Per-customer data agent over MCP |

Tabs appear only when the customer's edition includes them. Error messages are plain ("Answers aren't available right now"); the cause goes to the back office.

## 5. Decisions

| ID | Decision | Status |
|---|---|---|
| D1 | Product **Platform app**; first customer **Fabrikam**; workspaces named `platform-app-<customer>`; rename `saas-fabrikam` to `platform-app-fabrikam` | Proposed. Owner to confirm the customer spelling ("fabikram" in chat). |
| D2 | CRM database: Fabric SQL database per customer, behind a data-access layer (fallback: Azure SQL + mirroring) | Proposed |
| D3 | Customer app: the platform app, our own web app (not Fabric Apps) | Proposed (finding F15) |
| D4 | Gold layer: Fabric Warehouse `platform_app_wh`, T-SQL procedures reading `platform_app_db` and `platform_app_lake` through cross-database queries | Proposed |
| D5 | Capacity: a paid F SKU (F2 minimum) for the platform, on 24×7 while the CRM is in use. The data agent doesn't run on the trial capacity (finding F8). Fabric items can't move across regions (F19), and `saas-fabrikam` is in West US 3. Options: a new West US 3 F2 for the platform (recommended), resume a paused F8 capacity (shared with another team), or recreate the workspace in another region. | **Owner decision** (cost) |
| D6 | Project location: move the repo out of OneDrive into git (for example `C:\src\platform-app`); the TDS driver adds the first npm dependency (`mssql`) | **Owner decision** |
| D7 | End-user sign-in: email-domain sign-in for the MVP; Entra External ID or multi-tenant Entra in production | Proposed |
| D8 | Platform identity: one service principal for the MVP; rotate its secret now (it was shared in chat), keep it in Key Vault or use a managed identity when hosted; shard service principals before 1,000 workspaces | Proposed. Rotation: **Owner, now**. |
| D9 | Editions (internal only): Standard = CRM + reports; Professional = + data integration + report authoring; Enterprise = + Assistant | Proposed |

## 6. Phases

| Phase | Outcome | Status |
|---|---|---|
| 0 | Foundations: platform identity, workspace, control plane, customer app shell | **Done** (see 6.0) |
| 1 | Platform app core on Fabric SQL, seeded with Fabrikam data | Next |
| 2 | Warehouse gold layer and refresh pipeline | Not started |
| 3 | Reports tab | Not started |
| 4 | Assistant tab | Not started (needs D5) |
| 5 | Integrations: scheduled web sources, on-premises systems | Partly done |
| 6 | Production: sign-in, hosting, secrets, CI/CD, monitoring, scale | Not started |

### 6.0 Phase 0: foundations (Done)

- Service principal secret verified; tokens for Fabric, Power BI and OneLake (F1, F2).
- Workspace `saas-fabrikam` (`<fabrikam-workspace-id>`) created by the admin on the trial capacity, with the service principal as Admin, then adopted by the platform (F4).
- Control plane: idempotent provisioning, workspace adoption, template stamping with ID remapping, data agent definition builder and sync, ingestion (CSV, TSV, JSON, Parquet, Excel in the browser, web with an SSRF guard), OneLake upload and Load Table, row counts read back from the Delta log, MCP client, embed tokens.
- Customer app shell (sign-in, Reports, Data, Ask), back office at `/admin`, operator CLI, preflight check, 58 automated tests.
- Live in tenant: lakehouse, warehouse, SQL database and data agent created by the service principal; data loaded and read back (F5 to F9).

### 6.1 Phase 1: Platform app core on Fabric SQL

1. **Schema** (versioned migrations, applied by a new provisioning step `crm-schema`): `users`, `accounts`, `contacts`, `opportunities`, `activities`, with `created_at` and `updated_at` everywhere so the warehouse can load incrementally.
2. **Data-access layer** with two drivers:
   - `fabric-sql`: TDS through `mssql`, an Entra token for `https://database.windows.net/.default` from the platform identity, and one connection pool per customer. The server and database names come from the SQL database item's properties.
   - `sqlite`: `node:sqlite` (built into Node), for local development and tests without Fabric.
3. **Seed:** a deterministic Fabrikam data set (about 80 accounts, 250 contacts, 300 opportunities, 1,200 activities and 6 sales reps), loaded by a provisioning step on first setup.
4. **CRM tabs** in the customer app: lists with search and sort, a detail view, create and edit forms.
5. **Data tab:** CRM tables show as "Platform app, live" (the sample "Sync now" loader goes away).

**Exit:** create, edit and delete round-trip in `platform_app_db` as the service principal (V1); a new opportunity shows
up in OneLake within two minutes (V2); tests pass for both drivers.

### 6.2 Phase 2: warehouse gold layer and pipeline

> The data integration add-on's design ([DATA-INTEGRATION.md](DATA-INTEGRATION.md)) builds silver and gold in a
> lakehouse with Spark notebooks instead of a warehouse. D4 stays open until one is chosen.

1. `platform_app_wh` schema `gold`: `dim_account`, `dim_owner`, `dim_date`, `fact_opportunity`, `fact_activity`, plus
   views over customer data sets.
2. Procedure `gold.refresh` reads `platform_app_db` and `platform_app_lake` through cross-database queries (V3).
3. Pipeline `pl_refresh`: copy scheduled sources, then run `gold.refresh`; hourly schedule. Customer uploads trigger a refresh.
4. Authored once in `platform-app-template` and stamped per customer.

**Exit:** gold row counts match the source counts; the pipeline run succeeds as the service principal.

### 6.3 Phase 3: Reports tab

1. Semantic model `Platform app Insights` (Direct Lake on `gold`) with measures: pipeline value, win rate, average deal
   size, activities per rep.
2. Three reports, built by the platform team in the template workspace and stamped per customer.
3. A fixed-identity cloud connection (service principal, SSO off), bound to each customer's semantic model. Embedding a Direct Lake model as a service principal requires this (F11, V5).
4. Reports tab: view; edit and new reports for the Professional edition and up; token refresh.

**Exit:** a report renders in the browser from a per-customer V2 token, and another customer's token can't open it.

### 6.4 Phase 4: Assistant tab (needs a paid capacity, D5)

1. Data agent `Platform app Assistant` over `gold` (and `platform_app_db`), with instructions and example questions.
   It's stamped from the template and synced when data sets are added (already built).
2. Assistant tab: conversation history per user, suggested questions, plain errors. Every question is logged per customer.

**Exit:** answers to five reference questions match SQL results (V4).

### 6.5 Phase 5: integrations

- **Done:** file and Excel uploads, one-off web pulls, connection requests recorded for the platform team.
- **Design:** the future state, with Data Factory pipelines, Spark notebooks and medallion layers, all running as the
  customer's service principal, is in [DATA-INTEGRATION.md](DATA-INTEGRATION.md).
- **Next:** scheduled web sources (a Fabric connection and a pipeline copy per source).
- **Next:** systems on the customer's network, through an on-premises data gateway. The customer's IT installs it, and a
  platform engineer registers it to the platform's Entra tenant, since registering needs a person's account (F67). The
  platform then creates the connection, as the customer's service principal with permission on the gateway, and the
  pipeline. Identities across the two Entra tenants: [IDENTITIES.md](IDENTITIES.md).

### 6.6 Phase 6: production

Real end-user sign-in (D7); hosting on Azure App Service or Container Apps with a managed identity; secrets in Key Vault; template workspace in Git, deployed with `fabric-cicd`; capacity sizing and alerts (Capacity Metrics app, workspace monitoring); per-customer cost reporting; service principal sharding; offboarding and data retention; load tests.

## 7. Validation checklist

| ID | Assumption | How to test | Passes when | Fallback | Result |
|---|---|---|---|---|---|
| V1 | The service principal can open a TDS session to `platform_app_db` and run DDL and DML | `mssql` with an access token; create, insert and select | All statements succeed | Grant the database role explicitly; or a workspace identity | Passed live: provisioning creates the schema and sample data, and the CRM reads and writes as each customer's service principal (DAT-01) |
| V2 | CRM changes reach OneLake quickly | Insert a row, then poll the Delta log | Visible within 2 minutes | Accept the delay, or refresh on demand | Not run |
| V3 | `platform_app_wh` can read `platform_app_db` and `platform_app_lake` in the same workspace | Cross-database `SELECT` as the service principal | Rows return | Lakehouse shortcuts to the `platform_app_db` tables | Not run |
| V4 | The data agent answers over MCP as the service principal on a paid capacity | Five reference questions | Answers match SQL | Agent over `platform_app_db` or the semantic model | Blocked on the trial capacity (finding F8) |
| V5 | A Direct Lake model can be created and bound to a fixed-identity connection through the API, then embedded | TMDL definition, connection, bind, V2 token, render | The report renders | Import-mode model with scheduled refresh | Passed live: "Sales overview" renders from V2 tokens with each person's rows (F50; RLS-03, RLS-05) |
| V6 | Template stamping works for pipeline, model, report and agent in the tenant | Stamp from `platform-app-template`, then open each item | Items open; IDs point at the customer copies | Generate definitions in code | Mock only |
| V7 | F2 carries one customer (CRM, refresh, Assistant) without throttling | Scripted usage for a day, then read the Capacity Metrics app | No throttling | F4 | Not run |
| V8 | Load Table (preview) is reliable enough | 50 mixed uploads | All load | Pipeline copy or a notebook | 5 of 5 OK |
| V9 | The data agent writes good SQL over `gold` | Reference questions with example queries | 4 of 5 correct | More examples; the semantic model as source | Not run |

## 8. Findings

| ID | Finding | Evidence |
|---|---|---|
| F1 | **[Tenant]** The service principal's secret is valid; it gets tokens for Fabric, Power BI and OneLake storage | `scripts/preflight.js`, 2026-10-01 |
| F2 | **[Tenant]** The service principal can call Fabric APIs, but the only capacity it can see is Premium Per User. It has no rights on any F capacity. | preflight, 2026-10-01 |
| F3 | **[Tenant]** Only the trial capacity (FT1, West US 3) is active. An F8 and two F2 capacities are paused. | Fabric MCP `list_capacities`, 2026-10-01 |
| F4 | **[Tenant]** The admin created `saas-fabrikam` on the trial capacity and added the service principal as Admin; the platform adopted it | Role assignment, 2026-10-01 |
| F5 | **[Tenant]** The service principal created a lakehouse, a warehouse, a SQL database and a data agent (with draft and published definition parts) on FT1 | CLI `add`, 2026-10-01 |
| F6 | **[Tenant]** OneLake upload plus Load Table created Delta tables; counts read back from `_delta_log` were 60, 240, 600, 3 and 10 | CLI `rows`, 2026-10-01 |
| F7 | **[Tenant]** Data agent `getDefinition` and `updateDefinition` work as the service principal | CLI `load-crm` agent sync, 2026-10-01 |
| F8 | **[Tenant]** The data agent MCP endpoint rejects FT1: `-32003 FT1 SKU Not Supported` | CLI `ask`, 2026-10-01 |
| F9 | **[Tenant]** The Power BI REST API works as the service principal. Fabric creates no default semantic model for a lakehouse or warehouse. | CLI `reports`, 2026-10-01 |
| F10 | **[Docs]** A service principal can belong to at most 1,000 workspaces. Service principal profiles only work with the Power BI APIs, not Fabric items or Direct Lake. | [Workspaces](https://learn.microsoft.com/fabric/fundamentals/workspaces), [SP profiles](https://learn.microsoft.com/power-bi/developer/embedded/embed-multi-tenancy) |
| F11 | **[Docs]** Embedding a Direct Lake model as a service principal needs a V2 embed token and a fixed-identity cloud connection | [Direct Lake overview](https://learn.microsoft.com/fabric/fundamentals/direct-lake-overview) |
| F12 | **[Docs]** SQL database in Fabric: Entra authentication only (service principals need Read on the item); replicates to OneLake in near real time; usage counts as interactive with 5-minute smoothing; 1 CU = 0.383 vCores; a maximum vCore limit is available (preview) | [Authentication](https://learn.microsoft.com/fabric/database/sql/authentication), [FAQ](https://learn.microsoft.com/fabric/database/sql/faq), [Billing](https://learn.microsoft.com/fabric/database/sql/usage-reporting) |
| F13 | **[Docs]** Data agents support Fabric SQL database, warehouse, lakehouse and mirrored databases as SQL sources | [SQL sources](https://learn.microsoft.com/fabric/data-science/data-agent-sql-sources) |
| F14 | **[Docs]** The OpenAI Assistants API was retired on 2026-08-26; external clients use the data agent's MCP endpoint | [Python client](https://learn.microsoft.com/fabric/data-science/consume-data-agent-python), [MCP](https://learn.microsoft.com/fabric/data-science/data-agent-mcp-server) |
| F15 | **[Docs]** Deployed Fabric Apps (Rayfin) sign users in with Fabric SSO inside the Fabric portal only | [Fabric Apps](https://learn.microsoft.com/fabric/apps/overview), rayfin skill |
| F16 | **[Docs]** The tenant setting "Service principals can create workspaces, connections, and deployment pipelines" is off by default for new tenants. Placing a workspace on a capacity also needs capacity Contributor rights. | [Developer settings](https://learn.microsoft.com/fabric/admin/service-admin-portal-developer) |
| F17 | **[Docs]** `Connect-DataGatewayServiceAccount` can sign in with a service principal, but registering a gateway needs a user credential (corrected in F67). Customers can restrict which tenants their gateways register to. | [Gateway PowerShell](https://learn.microsoft.com/powershell/gateway/overview), [Tenant restrictions](https://learn.microsoft.com/data-integration/gateway/service-gateway-tenant-registration) |
| F18 | **[Tenant]** In this sandbox, loopback and the Azure CLI profile are blocked, so live checks run in-process through the CLI | 2026-10-01 |
| F19 | **[Docs]** Only Power BI item types (reports, small semantic models, dashboards, and similar) move across regions. A workspace with a lakehouse, warehouse, SQL database or data agent can only move to a capacity in the same region. | [Capacity reassignment restrictions](https://learn.microsoft.com/fabric/admin/portal-workspace-capacity-reassignment#restrictions-on-moving-workspaces-around) |
| F20 | **[Tenant]** The service principal connects to `platform_app_db` over TDS with an Entra token (scope `https://database.windows.net/.default`), runs DDL and bulk-loads 3,694 rows in about 4 s | live `platform_app_db`, 2026-10-01 |
| F21 | **[Tenant]** A SQL database replicates to OneLake at `<workspace>/<sqlDatabaseId>/Tables/dbo/<table>` within about a minute; only tables with a primary key | Delta logs read back, 2026-10-01 |
| F22 | **[Tenant]** Direct Lake on OneLake works over a SQL database item: TMDL with `AzureStorage.DataLake` on the item path plus `schemaName: dbo` deploys (compatibility level 1702) and frames | live model, 2026-10-01 |
| F23 | **[Tenant]** A new Direct Lake model's data source is `AzureDataLakeStorage` with path `https://onelake.dfs.fabric.microsoft.com/<ws>/<item>/` (trailing slash) and `Automatic` (SSO) connectivity; a ShareableCloud connection with `WorkspaceIdentity` credentials, created with `server` + `path` parameters, matches it exactly and binds. List Item Connections shows the binding about 20 s later. | live bind, 2026-10-01 |
| F24 | **[Tenant]** A workspace identity gets no workspace role by default; Direct Lake on OneLake needs Read and ReadAll, so it is made Contributor of its own workspace | live, 2026-10-01 |
| F25 | **[Tenant]** The data agent with a **semantic model** source answers over MCP on the trial capacity (FT1), unlike the lakehouse-source agent (F8). Its answers matched SQL over `platform_app_db` exactly. | CLI `ask`, 2026-10-02 |
| F26 | **[Tenant]** `executeQueries` returns 401 `PowerBINotAuthorizedException` for the service principal (tenant setting "Dataset Execute Queries REST API" for service principals); nothing in the app depends on it | 2026-10-01 |
| F27 | **[Tenant]** `powerbi.createReport()` returns a `Create` object without page APIs: a new report must be saved (`saveAs`) and reopened in edit mode before the authoring API can add visuals | live embed, 2026-10-02 |
| F28 | **[Tenant]** `page.createVisual` without `displayState: { mode: 0 }` creates hidden visuals; `visual.sortBy` fails with `FailedSortingVisual` in edit mode, so time axes use a date column (`Calendar[Month Start]`) instead of a text one | live embed, 2026-10-02 |
| F29 | **[Tenant]** After a schema change (new column), framing can fail until the OneLake replica catches up; one retry 30 s later succeeded | provisioning run, 2026-10-02 |
| F30 | **[Docs]** Fabric IQ MCP supports delegated sign-in only; service principals and app-only tokens aren't supported | Microsoft Learn, researched 2026-10-01 (link not recorded) |
| F31 | **[Docs]** Copilot report creation isn't supported for "app owns data" embedding (only the Copilot narrative visual, in preview) | Microsoft Learn, researched 2026-10-01 (link not recorded) |
| F32 | **[Tenant]** The platform service principal has no Microsoft Graph application permissions, so it can't create per-customer service principals until an admin grants `Application.ReadWrite.OwnedBy` or runs the bootstrap script | Graph probe, 2026-10-01 |
| F33 | **[Review]** Multitenancy and least-privilege review: 18 findings (4 high, 10 medium, 4 low), all addressed in code and covered by tests; scorecard and remaining production gaps in [MULTITENANCY.md](MULTITENANCY.md) | review, 2026-10-02 |
| F34 | **[Review]** The Fabric emulator didn't enforce workspace roles, so isolation was never tested. Once it held each identity to its roles, 9 tests failed at once: template copying ran as the customer's service principal but read the platform's template workspace, which that account (rightly) can't see. Fixed: the platform reads templates, the service principal writes | `npm test`, 2026-10-02 |
| F35 | **[Review]** Fault injection found a duplicate: when `createConnection` succeeded but its response was lost, the retry hit "already exists" and created a second connection under the fallback name. Fixed: after any failed create, look again before retrying | `test/robustness.test.js`, 2026-10-02 |
| F36 | **[Docs]** Graph upserts `PATCH /applications(uniqueName='…')` and `PATCH /servicePrincipals(appId='…')` with `Prefer: create-if-missing` need only `Application.ReadWrite.OwnedBy`; they return 201 with the object when created and 204 without a body when it existed. `uniqueName` can't be filtered on, but `tags` can | [Upsert application](https://learn.microsoft.com/graph/api/application-upsert), [Upsert servicePrincipal](https://learn.microsoft.com/graph/api/serviceprincipal-upsert), [application resource](https://learn.microsoft.com/graph/api/resources/application) |
| F37 | **[Tenant]** `GenerateToken` honours `lifetimeInMinutes`: a token requested at 04:48:08 with 30 minutes expired at 05:18:12 | CLI `embed`, 2026-10-02 |
| F38 | **[Tenant]** Supersedes F25: the semantic-model data agent now also returns `-32003 FT1 SKU Not Supported` on the trial capacity. Documented requirement: a paid F2 or larger capacity (or P1 and up). The quick-answer fallback took over as designed | CLI `ask`; [Data agent as MCP server](https://learn.microsoft.com/fabric/data-science/data-agent-mcp-server#prerequisites), 2026-10-02 |
| F39 | **[Tenant]** The audit against the live workspace: 0 failing; it flagged the missing `fabrikamsa` and a person (the administrator who created the workspace) with direct Admin access. The model's connection uses the workspace identity with SSO off | CLI `audit`, 2026-10-02 |
| F40 | **[Review]** With the data agent unavailable, "total value of open opportunities by stage" got counts from the quick answers. Fixed with value phrasings in the synonyms (they aren't part of the TMDL, so no model redeploy); the stage values now add up to the CRM's pipeline value | CLI `ask`, `test/crm.test.js`, 2026-10-02 |
| F41 | **[Tenant]** Service principals live: `fabrikamsa` and `contososa` were created with `bootstrap-identities.ps1 -Register` by a Global Administrator, and provisioning in `required` and `release` mode handed both workspaces over. Each account lists only its own workspace and is refused at the other's: 403 for the workspace, 401 for its items, 404 for an embed token, "User is not authorized" from its data agent | CLI `provision`, isolation check, 2026-10-03 |
| F42 | **[Tenant]** Binding a semantic model the caller doesn't own returns HTTP 400 `BindNotModelOwner`, not 403; `TakeOver` then works. The emulator now answers the same way | CLI `provision`, 2026-10-03 |
| F43 | **[Tenant]** A new client secret was refused with `AADSTS7000215`, on and off for minutes, before Microsoft Entra ID accepted it everywhere. Token requests now retry it | CLI `provision`, 2026-10-03 |
| F44 | **[Tenant]** Removing a workspace role took about an hour to take effect: from 01:21 UTC the role list and the admin API showed no role for the platform identity on `saas-contoso`, but it could open the workspace until about 02:31 | Isolation check, 2026-10-03 |
| F45 | **[Tenant]** On the trial capacity the data agent's MCP endpoint refuses the service principals (`-32003 FT1 SKU Not Supported`), while a person can still use it. Moving both workspaces to the F8 capacity didn't help: that capacity was paused minutes later (SQL databases answered 404 `CapacityNotActive`), so they went back to the trial | CLI `ask`, capacity assignment, 2026-10-03 |
| F46 | **[Docs]** SQL database in Fabric is serverless: after 15 minutes without activity its compute is released, and the next connection waits while it resumes. The platform app now retries connections and reads on transient errors. Live, the first question after a capacity move had failed after 38 seconds | [Billing](https://learn.microsoft.com/fabric/database/sql/usage-reporting), [limitations](https://learn.microsoft.com/fabric/database/sql/limitations), `test/crm.test.js`, 2026-10-03 |
| F47 | **[Docs]** Microsoft Purview (preview) records a data agent's prompts and responses as "Copilot Interaction" audit records, shown in DSPM Activity Explorer. It needs Audit on, the DSPM setup task "Secure interactions in Microsoft Copilot experiences" and the tenant setting "Allow Microsoft Purview to secure AI interactions" (on in this tenant). The portal keeps each person's chats up to 28 days. Whether calls by a service principal over MCP are recorded isn't documented | [Purview for data agents](https://learn.microsoft.com/fabric/data-science/data-agent-purview-governance), [tenant settings](https://learn.microsoft.com/fabric/data-science/data-agent-tenant-settings), 2026-10-03 |
| F48 | **[Tenant]** The data agents on the trial capacity now refuse people too: the admin user's MCP `initialize` returns `-32003 FT1 SKU Not Supported`, where on 2026-10-03 it worked. A made-up agent ID returns `-32601 The entity could not be found`, so the endpoint the app calls does reach the published agents | Direct MCP probe, 2026-10-06 |
| F49 | **[Docs]** An embed token expires no later than the Microsoft Entra token used to create it. GenerateToken asks the token provider for the embed lifetime plus 5 minutes of remaining validity, capped at 55 minutes; a recently acquired token with more than 5 minutes left can be reused for one minute, so this is not a guaranteed minimum lifetime. Microsoft's refresh sample checks every 30 seconds, refreshes with 10 minutes left, and checks again when the tab becomes visible; the app does the same, or uses a third of the lifetime for shorter tokens (it previously refreshed 2 minutes before expiry, on a timer that stalls during sleep). It counts from when the token arrived (`expiresInSeconds`), so a wrong device clock can't cause late or repeated refreshes; checked live in Edge with the page clock moved 21 minutes ahead | [Generate an embed token](https://learn.microsoft.com/power-bi/developer/embedded/generate-embed-token#considerations-and-limitations), [Refresh the access token](https://learn.microsoft.com/javascript/api/overview/powerbi/refresh-token), `src/auth/tokens.js`, `src/fabric/client.js`, `public/embed-token.js`, `test/fabric-client.test.js`, `test/mcp-and-tokens.test.js` |
| F50 | **[Tenant]** Row-level security holds in the rendered report: the validator opened "Sales overview" in Edge as each customer's manager and Texas rep, with the tokens the app issues; the reps saw Texas only, and every number matched the database | `npm run validate -- --live --browser`, 2026-10-06 |
| F51 | **[Docs]** Service principal profiles work with the Power BI REST API, SDK and XMLA endpoint only, so they can't isolate Fabric items such as a SQL database, a cloud connection or a data agent. A service principal per tenant stays the framework's default | [Profiles: limitations](https://learn.microsoft.com/power-bi/developer/embedded/embed-multi-tenancy#considerations-and-limitations) |
| F52 | **[Docs]** Compared with Microsoft's App-Owns-Data samples (the Starter Kit, AppOwnsDataWithRLS, NetCore-AppOwnsData). The platform app already matched them on client credentials kept on the server, Generate Token V2 with an effective identity, roles decided on the server, and expiring the cached Entra token early enough for a whole embed token. Gaps found: per-person edit and create rights, a usage log, a refresh bug for short tokens, a security group for the service principal tenant settings, and reopening a report after "Save as" (F53 to F57). Deliberate differences: a service principal per tenant instead of profiles (F51), one token per report, and refresh timing: the Starter Kit's React client refreshes 2 minutes ahead by the device clock (its TypeScript client doesn't refresh), where the platform app follows Microsoft's refresh sample | [Starter Kit](https://github.com/PowerBiDevCamp/App-Owns-Data-Starter-Kit), [AppOwnsDataWithRLS](https://github.com/PowerBiDevCamp/AppOwnsDataWithRLS), [NetCore-AppOwnsData](https://github.com/PowerBiDevCamp/NetCore-AppOwnsData), EMBEDDING.md section 10, 2026-10-06 |
| F53 | **[Code]** Report rights per person, like the Starter Kit's `CanEdit` and `CanCreate`: everyone may view; the token allows editing only for people who may edit, and names a target workspace only for people who may also create; the browser gets `Read`, `ReadWrite` or `All` to match. Rights are set in the back office or with `user-access --reports`, and changing them signs the person out. Demo sign-in keeps every right. Control EMB-06 | `test/personas.test.js` |
| F54 | **[Tenant]** With app-owns-data embedding, Power BI's activity log records the service principal rather than the person, so the app keeps its own report usage log, like the Starter Kit's `ActivityLog`: who viewed or saved which report, load and render times, the embed token ID and the report's correlation ID. Live, four views on the trial capacity loaded in 10 to 12 seconds and rendered in 13 to 16. Control OPS-06 | `test/usage.test.js`, `usage Fabrikam`, 2026-10-06 |
| F55 | **[Code]** Refreshing a fixed 10 minutes before expiry would refresh a token of 10 minutes or less (the Starter Kit's own lifetime) as soon as it arrived, again and again. The browser now refreshes at the smaller of 10 minutes and a third of the lifetime before expiry (`public/embed-token.js`) | `test/embed-client.test.js` |
| F56 | **[Tenant]** "Service principals can call Fabric public APIs" and "Service principals can create workspaces, connections, and deployment pipelines" apply to the entire organization in the pilot tenant; so do profiles and embedding. Microsoft and the Starter Kit limit them to a security group. The validator now reads them (IDN-06) and warns. Also, a security group that holds the platform identity allows the read-only admin APIs and those used for updates; the app needs neither. To do: a Fabric administrator limits the settings to a group holding the platform identity and the tenant service principals, and takes the platform identity out of that group | `GET /v1/admin/tenantsettings`, `npm run validate -- --live`, 2026-10-06 |
| F57 | **[Code]** After "Save as" or saving a new report, the app kept the frame and its token, which named the original report (or only the model, for a new one), and each refresh asked for the original again. Now the saved report opens with a token of its own, in edit mode for people who may edit, as the Starter Kit does and as "describe a chart" already did. Checked in Edge on the emulator with a stand-in for Power BI: after "Save as" the app asked for the copy, the next refresh asked for the copy, and a save in place kept the token. It's on the authoring path, off in the pilot (`REPORT_AUTHORING`) | `public/app.js`, 2026-10-06 |
| F58 | **[Docs]** Current guidance, re-checked: Microsoft recommends certificates over client secrets for embedding back ends, and MSAL over hand-written OAuth calls. An app registration can trust a user-assigned managed identity (a federated identity credential: issuer `https://login.microsoftonline.com/<tenant>/v2.0`, subject the managed identity's object ID, audience `api://AzureADTokenExchange`, at most 20 per app). Managed identities can't call data agents, and Generate Token documents service principals and profiles only, so the per-customer app registrations stay, signing in with certificates or federated credentials. `powerbi-client` 2.25.0 and `powerbi-report-authoring` 3.0.0 are the latest; the refresh pattern matches Microsoft's | [Embed with a service principal](https://learn.microsoft.com/power-bi/developer/embedded/embed-service-principal), [MSAL](https://learn.microsoft.com/entra/identity-platform/msal-overview), [trust a managed identity](https://learn.microsoft.com/entra/workload-id/workload-identity-federation-config-app-trust-managed-identity), [data agent with a service principal](https://learn.microsoft.com/fabric/data-science/data-agent-service-principal), 2026-10-06 |
| F59 | **[Tenant]** Token acquisition moved to MSAL Node (already installed with the SQL driver), with three credential types: federated, certificate, secret. Both customer service principals were moved to certificates: their tokens carry `appidacr=2` (certificate), and provisioning, embedding, the SQL database and the data agent all work with them. `scripts/bootstrap-identities.ps1 -Customer Fabrikam -Register` ran end to end with the new certificate default; the certificate made earlier by hand was then deleted from the app, and the old client secrets are unused. Federated credentials were tested against a stand-in for the managed identity | `test/credential-types.test.js`, `test/identities.test.js`, live, 2026-10-06 |
| F60 | **[Code]** Nothing secret in project files: `npm start`, `npm run setup`, the CLI and the validator ask for the platform identity's certificate (or development secret), `SECRETS_KEY` and the back-office key with hidden input; `npm run setup` writes only non-secret settings to `.env`; `SESSION_SECRET` is made per run outside production. Without a terminal they come from the environment. Production refuses a client secret for the platform identity | `test/runtime-secrets.test.js`, `test/pilot.test.js`, `test/robustness.test.js` |
| F61 | **[Docs]** `USERELATIONSHIP` returns an error when a role filters a table it touches; "# Accounts Owned" turned on the inactive Accounts-to-Sales-Reps relationship, so it would fail for every rep. It now filters by owner with `TREATAS` (and only when Sales Reps is filtered): live, it gave the same numbers for every rep and the total (120) in both customers' models, and provisioning pushed it to all four models. A test keeps relationship functions out of the model | [USERELATIONSHIP remarks](https://learn.microsoft.com/dax/userelationship-function-dax#remarks), `executeQueries` as an admin, `test/crm.test.js`, 2026-10-06 |
| F62 | **[Tenant]** Row-level security holds against filters: after reading what each person sees, the validator applies a report filter asking for every territory and reads the visual again. The Texas reps still saw Texas only, the managers all three states (RLS-03). Testing a role over XMLA with an access token (`Roles=Texas`) failed to authenticate with the SSMS ADOMD client although the XMLA setting is on, so the browser check is the evidence | `npm run validate -- --live --browser`, 2026-10-06 |
| F63 | **[Code]** Fixes found by running the published path live: registering a new credential for an existing service principal dropped its recorded workspace role (it now keeps the record and changes only the credential); the bootstrap script called the CLI without the deployment's `.env`; a brand-new certificate can be refused for a moment with `AADSTS700027`, which is now retried like a new secret | `test/identities.test.js`, live, 2026-10-06 |
| F64 | **[Code]** A pre-publish check (`npm run check:publish`): credential patterns anywhere in the project, and this deployment's IDs (from the registry and settings, also as 8-character prefixes), which `--fix` replaces with placeholders such as `<fabrikam-workspace-id>`; `--strict` flags any other GUID in documentation. The project was scrubbed with it before publishing, and `test/publishing.test.js` keeps credentials out | `test/publishing.test.js`, 2026-10-06 |
| F65 | **[Tenant]** The workspace identity and both customer service principals are single-tenant apps (`signInAudience` is `AzureADMyOrg`; the workspace identity is tagged `Microsoft Fabric Identity`), so none of them can be admitted to a customer's Entra tenant, and "Workspace identity isn't supported in B2B or cross-tenant scenarios". Storage in another tenant needs a service principal or a SAS token. The add-on's design had the workspace identity read a customer's Azure sources; it now uses a reader per customer (`fabrikamreader`), a multi-tenant app whose service principal the customer admits ([IDENTITIES.md](IDENTITIES.md)) | `az ad sp show`, `az ad app show`, [workspace identity](https://learn.microsoft.com/fabric/security/workspace-identity#considerations-and-limitations), [ADLS shortcuts](https://learn.microsoft.com/fabric/onelake/create-adls-shortcut#limitations), 2026-10-07 |
| F66 | **[Tenant]** Fabric cloud connections take Anonymous, Basic, Key, KeyPair, OAuth2, ServicePrincipal, SharedAccessSignature or WorkspaceIdentity credentials: no certificate and no federated credential. A service principal credential names the principal's tenant ID and takes a secret or a Key Vault reference; Key Vault references sign in with OAuth2 or a service principal, so they move the secret rather than remove it. Salesforce takes OAuth2 only. For pipelines, the SharePoint list connector documents organizational accounts and workspace identities, though the API also lists a service principal | `GET /v1/connections/supportedConnectionTypes`, [Create Connection](https://learn.microsoft.com/rest/api/fabric/core/connections/create-connection), [Key Vault references](https://learn.microsoft.com/fabric/data-factory/azure-key-vault-reference-overview), [SharePoint list connector](https://learn.microsoft.com/fabric/data-factory/connector-sharepoint-online-list-overview), 2026-10-07 |
| F67 | **[Docs]** Gateways across tenants: registering one needs a user credential (`Add-DataGatewayCluster`), so a platform engineer registers a customer's gateway to the platform's Entra tenant; a machine can limit the tenants it registers to (`AllowedRegistrationTenants`); source credentials are encrypted for the gateway, and the service never sees them unencrypted; a service principal with permission on a gateway can create its connections; virtual network data gateways can't be created across tenants. Corrects F17 | [Add-DataGatewayCluster](https://learn.microsoft.com/powershell/module/datagateway/add-datagatewaycluster), [tenant registration](https://learn.microsoft.com/data-integration/gateway/service-gateway-tenant-registration), [security white paper](https://learn.microsoft.com/power-bi/guidance/white-paper-powerbi-security), [virtual network gateways](https://learn.microsoft.com/data-integration/vnet/create-data-gateways) |
| F68 | **[Docs]** Across tenants: external data sharing shares OneLake data in place and read-only, to a user or a service principal named by object ID and tenant ID, with a setting on each side; Cloud Application and Application Administrators can grant admin consent, except for Microsoft Graph application permissions; nothing limits which tenants admit a multi-tenant app, so sign-in checks the issuer and `tid`; a managed identity can be a federated credential across tenants; Dataverse takes multi-tenant apps as application users; Azure SQL documents that service principals can't authenticate across tenant boundaries, so it's tested first | [external data sharing](https://learn.microsoft.com/fabric/governance/external-data-sharing-overview), [admin consent](https://learn.microsoft.com/entra/identity/enterprise-apps/grant-admin-consent), [multi-tenant apps](https://learn.microsoft.com/entra/identity-platform/howto-convert-app-to-be-multi-tenant), [secretless access](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/secretless-authentication), [Dataverse](https://learn.microsoft.com/power-apps/developer/data-platform/use-multi-tenant-server-server-authentication), [Azure SQL](https://learn.microsoft.com/azure/azure-sql/database/authentication-aad-service-principal#limitations) |
| F69 | **[Code]** Local "View as" is a demo/testing aid for existing named sign-ins, not limited to pilot customers. It is refused in production or if forced with TRUST_PROXY or PUBLIC_ORIGIN; requests must come from loopback at a loopback or *.localhost host, with no X-Forwarded-For, X-Forwarded-Host or Forwarded header. Company addresses allow only that company's people; a shared local address can show all companies. Switching discards the report and clears the conversation and open account; Reports then gets that person's new token. The sign-in page clears the previous conversation. The browser validator selects one manager and one rep per distinct territory set: all four seeded pilot people, not every possible user | `src/routes/customer.js`, `public/app.js`, `src/platform/validation.js`, `test/view-as.test.js`, `test/framework.test.js`, 2026-10-07 |
| F70 | **[Tenant]** View as, live in Edge, twice: all eight people of both companies, switched with View as. Each rep's "Pipeline by state" showed only their state, with the manager's value for it, and each manager saw every state. Fabrikam: Georgia 2,828,500, Texas 2,229,000, New Mexico 455,000. Contoso: Georgia 2,151,000, Texas 2,145,500, New Mexico 712,000. One earlier run stopped at Contoso's Texas rep while this network's DNS timed out on the Contoso database's redirect host; the server's SQL retries recovered. The live validator then passed RLS-03 for the same eight people, each matching the database, with a report filter for every state still showing only their rows: 18 pass, 4 to review, 1 failing (AI-03, the trial capacity) | Playwright in Edge against the live pilot, `npm run validate -- --live --browser`, 2026-10-07 |
| F71 | **[Code]** Microsoft Edge relaunches itself when it starts under an app compatibility layer (`__COMPAT_LAYER=RunAsInvoker`, set in this environment after a restart) or elevated. The process the validator started exited with code 0, and the DevTools address never arrived. The validator now passes `--edge-skip-compat-layer-relaunch` and `--disable-features=AutoDeElevate`, as Playwright does | `src/platform/browser.js`, `test/framework.test.js`, 2026-10-07 |
| F72 | **[Code]** A validator check that stops for one tenant, such as on a dropped SQL connection, now marks every control it covers "to review" for that tenant. Before, RLS-03 and RLS-04 could pass on Fabrikam's results while Contoso's people were never checked | `src/platform/validation.js`, `test/framework.test.js`, 2026-10-07 |
| F73 | **[Code]** Code review: a View as switch could leak the previous person's data in the browser. A late embed token or assistant answer could land after the switch, an open account stayed on screen, and demo chart previews were redrawn. Every request and Power BI callback now carries an identity generation, and switching, signing in or signing out resets the views, routes and caches | `public/app.js`, `test/view-as-client.test.js` (37 tests), 2026-10-07 |

## 9. Code map

The current code map is in [README.md](README.md#code-map). Everything the table below planned is built: the CRM
data-access layer (`src/crm/*`, Fabric SQL and SQLite, migrations, seed), editions (`src/platform/plans.js`), CRM tabs
and the hovering assistant in `public/`, and the new provisioning steps. Still open from it: the platform's template
workspace with approved starter reports, and scheduled sources through pipelines (data integration add-on).

## 10. Risks

| Risk | Mitigation |
|---|---|
| Heavy reports or Assistant use throttles the CRM (shared capacity) | Size the capacity; set a maximum vCore limit per database; surge protection; dedicated capacity for big customers; fallback D2 |
| Pausing the capacity takes the CRM down | Keep the platform's capacities on 24×7; pause only dev and demo capacities |
| The CRM database pauses after 15 idle minutes (serverless), so the next question waits | Connecting and reads retry on transient errors for up to 90 seconds; writes run once (F46) |
| Fabric applies a removed role late (about an hour, F44) | After a release or an offboarding, confirm with a call that's denied; don't treat the role list alone as proof |
| Preview features (Load Table, data agent with service principals, MCP) change | Keep each behind one module with tests; follow the release notes. The data agent already changed once (F25, F38); the quick-answer fallback kept the assistant working |
| The exposed secret | Rotate it now (D8) |
| More than 1,000 customers per service principal | `PLATFORM_WORKSPACE_ACCESS=release`: the platform identity keeps no role in customer workspaces, so the limit only applies to each customer's own service principal (one workspace each) |
| A customer moves a sign-in domain, or leaves | Sessions are checked against the customer's current domains on every request; removal deletes the workspace, connection and service principal |
| An operator account is misused | `ADMIN_KEY` sign-in (required off loopback), throttled guesses, and every look at customer data logged in that customer's activity; production: workforce IdP with Conditional Access |
