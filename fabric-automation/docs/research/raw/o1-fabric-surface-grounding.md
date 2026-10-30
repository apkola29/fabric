STATUS: COMPLETE (orchestrator notes; not yet cross-verified)

# O1: Fabric tool and skill surface, grounded in what is callable today

Date: 2026-10-30. Author: orchestrator (Sonnet 5.5, max reasoning). Sanitized: no tenant, workspace or item identifiers, no secrets. Safe to share with verifiers.

## 1. Method and evidence

- Skills: read from the installed `fabric-collection` plugin (v0.3.19): `fabric-skills` (24 skills, 4 agents) and `powerbi-authoring` (2 skills). Read in full or in part: `git-integration-operations-cli`, `deployment-pipelines-authoring-cli`, `fabriciq`, `search-consumption-cli`, plus the plugin manifests.
- MCP tools: the tool definitions exposed in this host. Live calls made, all read-only: (1) Fabric Core command listing (schema only), (2) `Fabric-MCP-docs_list-item-types` (static docs), (3) `core_list-capacities` (one inventory read). No writes were made. The FabricIQ MCP server was not started; its tool list comes from the host's routing hint and the `fabriciq` skill.
- Not verified: which of the Fabric MCP servers is hosted and which is local (names do not prove it); the tool lists of the Power BI modeling MCP and the SQL endpoint MCP beyond what the manifests declare.

## 2. Installed packs and the MCP servers they declare

| Pack | Version | Contents | MCP servers in manifest |
|---|---|---|---|
| fabric-skills | 0.3.19 | 24 skills (listed in section 4), 4 agents (FabricAdmin, FabricDataEngineer, FabricAppDev, FabricIQ) | FabricIQ (HTTP, all tools), Power BI modeling (HTTP, hosted, all tools), SQL endpoint (HTTP, `execute_query` only) |
| powerbi-authoring | 0.3.19 | `semantic-model-authoring`, `powerbi-report-cli` | Power BI modeling, local stdio via `npx -y @microsoft/powerbi-modeling-mcp@latest --start`, all tools |

Notes: the SQL endpoint server shows that a manifest can restrict tools (`execute_query` only). The local Power BI modeling server floats on `@latest` with all tools allowed.

## 3. MCP tool surface callable in this host

| Server (tool prefix) | Tools | Notes |
|---|---|---|
| Fabric Core router (`com-microsoft-microsoft-fabric-core`) and flat `Fabric-MCP-core_*` | 16 commands. Read-only: get-capacity, list-capacities, get-item, list-items, get-workspace, list-workspaces, search-catalog, get-operation-state, get-operation-result. Write: create-workspace, update-workspace, delete-workspace, assign-workspace-to-capacity, create-item, update-item, delete-item | `create-item` has no definition parameter in this host's build, so it creates empty items. (Version-dependent: released versions through 1.6.0 have no definition payload. The unreleased `main` branch adds it.) `update-item` changes name and description only. `delete-item` defaults to soft delete; hard delete is an explicit opt-in. `delete-workspace` removes the workspace and its items and needs an explicit ID. |
| Data Factory (`Fabric-MCP-datafactory_*`) | create-dataflow, create-pipeline, execute-query, get-pipeline, list-dataflows, list-pipelines, run-pipeline | The only job-run tool. |
| Docs (`Fabric-MCP-docs_*`) | list-item-types, item-definitions, item-api-spec, platform-api-spec, best-practices, api-examples | Static, works offline. `list-item-types` returned 56 entries: 52 item types plus 4 non-item areas (admin, platform, spark, realTimeIntelligence). It includes `dataAgent`, `ontology`, `operationsAgent`, `semanticModel`, `report`, `notebook`, `dataPipeline`, `variableLibrary`, `graphModel`, `userDataFunction` and `dataBuildToolJob`. |
| OneLake (`Fabric-MCP-onelake_*`) | files, directories, shortcuts, tables, data-access roles, diagnostics, immutability | Not reviewed in detail. |
| `fabric-*` (snake_case) | get_item_definition, update_item_definition, create_item, delete_item, list_folders, create/update/delete/move folder, bulk_move_items, workspace role add/get/update/delete/list, get_knowledge, search_catalog, create/update/delete workspace, list capacities | `update_item_definition` takes the full definition as base64 parts and states that all required parts must be sent, not a partial patch. Its `delete_item` is described as permanent. Only 5 of these tool schemas were read. |
| FabricIQ (`mcp_route_fabric-iq_*`) | DiscoverArtifacts, ResolveFabricItem, GetReportMetadata, GetSemanticModelSchema, ValueSearch, ExecuteQuery | Read-only consumption. `ExecuteQuery` takes 1 to 4 DAX queries, 250 rows by default, 1,000 at most. The semantic model's custom instructions and verified answers come back with the schema. Not connected in this session. |
| Power BI modeling, SQL endpoint | Declared in manifests; routes exist in the host | Tool lists not enumerated. |

## 4. Coverage of the factory's operations

"MCP" means a tool exists in the surface above. Where it does not, the owning skill's REST or CLI path is the route.

| Factory operation | MCP today | Owning skill (v0.3.19) | Route when MCP does not cover it |
|---|---|---|---|
| Create or delete an ephemeral workspace | Yes (core) | none | REST |
| Assign a workspace to a capacity | Yes (async submit) | none | REST |
| Resume or pause a capacity | No | none (the `fabric-capacity-autopause` sample in this repository covers scheduled pausing) | Azure Resource Manager. Unverified: needs T4 confirmation |
| Workspace role assignment | Yes (`fabric-*`) | none | REST |
| Create an empty item | Yes | per workload | REST |
| Get or replace an item definition | Yes (`fabric-*`; replace-all) | per workload | REST |
| Git connect, initialize, status, commit, update, disconnect | No | `git-integration-operations-cli` (maturity: experimental) | `fab api` or `az rest` |
| Git workspace relations (branch to base, preview) | No | same skill | `fab api` or `az rest` |
| Deployment pipeline stages and deploy | No | `deployment-pipelines-authoring-cli` | REST |
| Environment parameters | No | `variable-library-cli` | REST |
| Run a pipeline | Yes (data factory) | none general (`pipeline-migration` is migration only) | Job scheduler REST |
| Run a notebook or Spark job | No | `spark-cli` | Livy and REST |
| Dataflow Gen2 | Yes (create, list, query) | `dataflows-cli` | REST |
| Run DAX against a semantic model | Yes (FabricIQ `ExecuteQuery`) | `fabriciq`, `semantic-model-authoring` | `executeQueries` REST |
| Semantic model authoring (TMDL, DAX, relationships) | Yes (Power BI modeling MCP; tool list not enumerated) | `semantic-model-authoring` | PBIP and TMDL files plus REST |
| Report authoring (PBIR), validate, publish | No | `powerbi-report-cli` | PBIR files plus the skill's CLI |
| Data agent create, configure, publish, test | Partial: item type has a public API spec; definition via `update_item_definition` | none | Factory must author a skill |
| Ontology | No | `fabriciq-ontology-cli` | REST |
| Warehouse and lakehouse SQL | Yes (`execute_query` only) | `sqldw-cli` | T-SQL over the SQL endpoint |
| Eventhouse, eventstream, activator | No | `eventhouse-cli`, `eventstream-cli`, `activator-cli` | REST and KQL |
| Catalog search | Yes | `search-consumption-cli` | REST |
| Long-running operation status | Yes | all | REST |
| Autonomous lakehouse engineering | No | `project-osmos` (a remote service task) | none |

## 5. Findings that change the design

1. **MCP covers about half of what the factory needs.** It covers workspace and item CRUD, definition get and replace, DAX, pipeline runs, catalog search and operation status. It does not cover the Git lifecycle, deployment pipelines, notebook runs, variable libraries, report authoring and render, or ontology. The factory's executor therefore needs a governed CLI/REST path as well. The host rule is MCP first, with explicit authorization before non-MCP live execution.
2. **Git integration has hard rules.** One writer per branch (a workspace is never both source of truth and CI push target on the same branch). One Git operation at a time per workspace. Always pass the current `workspaceHead` and poll until `workspaceHead == remoteCommitHash` with no pending changes. The workspace needs a capacity. Connect needs Admin; commit and update need Contributor with write on all items.
3. **The credential model is a design constraint.** The GitHub provider needs a personal access token stored in a Fabric connection (fine-grained with Contents read and write, or classic `repo`). It has no automatic mode and cannot use a service principal. The GitHub sync tenant switch is off by default. Azure DevOps works with a service principal credential and its switch is on by default. Either way the credential lives in a Fabric connection, never in the agent runtime.
4. **Item-type support in Git is mostly preview.** Per the skill's reference: semantic model, report and data agent are preview; ontology is not listed. Every pilot item type is therefore preview or unlisted. This needs verification against Learn (thread T4), and the design should treat these as preview contracts.
5. **Ephemeral branch workspaces are feasible through public APIs, but only partly through MCP.** The pieces are create workspace, assign capacity, connect to the branch, update from Git (prefer remote), and the preview workspace-relations API that records the branch-to-base link (service principals and managed identities supported; both workspaces must point at the same repo root). To confirm in Phase 0. An alternative is to push definitions with `fabric-cicd` or the definition APIs and skip Git connect entirely, which removes the stored PAT from the loop. This is an architecture decision record in the design.
6. **Promotion beyond dev cannot be fully automated.** Deployment rules and parameter rules can only be set in the portal. There is no compare API, so changes between stages must be diffed by the caller. The skill ships a diff script that decodes both definitions, normalizes auto-rebound fields and prints only the differences for the model. That pattern is worth borrowing, and it supports keeping promotion human in the pilot.
7. **Destructive operations are easy to reach.** `updateDefinition` replaces everything (omitted parts are deleted), the `fabric-*` delete is permanent, and skills contain DROP, TRUNCATE and `hardDelete` paths with no dry run. Skill guardrails assume an interactive confirmation that an unattended run does not have. Agents must never be given raw tools; a policy-enforcing executor should sit in between.
8. **Supply chain needs pinning.** The local Power BI modeling server floats on `@latest` with all tools allowed. The sandbox needs pinned versions, no run-time package installs, and per-tool allowlists, as the SQL endpoint manifest already does.
9. **Skill gaps (installed v0.3.19).** No skill for Fabric data agents, `fabric-cicd`, testing Fabric items, general pipeline CRUD, ML or environments. The factory must author at least a data-agent pack, a validation and test pack, and the intake and spec pack. A layered skill-test approach (lint, routing simulation, smoke prompts, full evaluation, verifiers that check real service state, an ephemeral tenant and an orphan-workspace sweeper) is the model for the factory's evaluation. The public skills repo ships no such tests, so the factory has to build them.
10. **Versions move fast.** The installed plugin is v0.3.19 and an older local copy is v0.3.3. Conventions changed between them (a mandatory telemetry header on every Fabric API call was added; skills were consolidated). Pin the pack to a tagged release, and re-run the gap analysis and the golden suite on each upgrade.
11. **Capacity is the scarce resource.** The signed-in identity sees exactly one capacity, shared with other workspaces. Trial capacity cannot host data agents (an F SKU is needed). A dedicated small sandbox capacity with resume on demand and pause when idle is needed. Capacity pause and resume is not a Fabric MCP operation (unverified; T4 to confirm).

## 6. To verify next (handed to T4, T3a and the verifiers)

- Git integration item-type support and GA or preview status for semantic model, report, data agent and ontology.
- Whether capacity pause and resume is Azure Resource Manager only.
- Whether `fabric-create_item` accepts a definition.
- Whether a service principal can call `executeQueries` on Direct Lake models (sources conflict; to be tested).
- The tool lists of the Power BI modeling and SQL endpoint MCP servers.
- Data agent definition parts, publish flow, and service-principal support (including the evaluation route).
