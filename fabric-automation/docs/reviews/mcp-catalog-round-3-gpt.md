# Verification of the catalog of MCP servers, round 3: the reply of GPT 6.1 Sol

The reply as it came back, with the agent's own header removed. It read the files in the state of the review snapshot of round 3 (the paths in the reply are relative to it) and took: the 22 statements that round 2 changed, the instruction text and its diffs, and the closure of the round-2 findings of Gemini. The author's checks and the dispositions are in [mcp-catalog-findings.md](mcp-catalog-findings.md).

## Task A

datafactory-local:use | S | connections, dataflows, pipelines, copy jobs, and Apache Airflow jobs | The directory and README support all five workload categories.
datafactory-local:where | S | "type": "stdio",..."command": "dnx" | The README documents command-based local hosting; the directory lists it as Local. Checked manifest and profiles: not pinned or loaded.
datafactory-local:stage | S | Pipeline management is a preview feature | No cited page assigns the server an overall release stage. Preview qualifications concern particular features, acknowledged separately in the catalog.
datafactory-local#1 | S | .NET 10.0 or later..."command": "dnx"...Pipeline management is a preview feature | Verified the runtime, recommended launch command and feature-specific previews. None establishes a server-wide stage.
datafactory-local#2 | S | `get_access_token`, `sign_out` | The documented authentication tools support the factual claim. Leaving authentication to the operator is the factory’s stricter policy, confirmed in AGENTS.md and the preamble.
datafactory-local#3 | S | Pipeline management is a preview feature that requires the `--pipeline` flag | The guide explicitly requires the flag and says pipeline tools otherwise do not appear.
datafactory-local#4 | S | Launch the interactive Create Connection form directly from chat. | The connection guide documents create_connection_ui. It is absent from the README’s Available Tools list.
datafactory-local:tools | P | `Action.Sequence` for writes...schedule modification aren't available through the MCP server | All 52 names are accounted for: 51 in the README plus create_connection_ui. No missing or invented names found. UNVERIFIED: execute_query’s read-only classification; the README advertises write-capable M actions without establishing this tool’s boundary. Also, the README lists set_pipeline_schedule_enabled while Learn denies schedule modification; both live pages retain that disagreement.
datafactory-local:flagged | T | Copilot calls `mcp_datafactorymc_update_pipeline_definition` with a JSON definition for the activity | The named authentication, connection and schedule bans are justified, but connection changes through pipeline activity definitions lack a changes flag. See F1. No job profile loads this server.
powerbi-consumption-remote:use | S | For semantic model consumption, prefer to use the Fabric IQ MCP server | The page documents DAX execution/generation, semantic-model schema and report metadata, and explicitly prefers Fabric IQ.
powerbi-consumption-remote:where | S | https://api.fabric.microsoft.com/v1/mcp/powerbi...Authenticate with your Microsoft credentials if requested | One HTTP endpoint is documented. Checked the directory, manifest and profiles: outside the directory, unpinned and not loaded.
powerbi-consumption-remote:stage | S | Power BI Consumption MCP server (preview) | The heading and introductory qualification explicitly identify preview.
powerbi-consumption-remote#1 | S | Users can use the Power BI Model Context Protocol server endpoint (preview) | The prerequisite requires Power BI administrator approval and gives this exact setting name, including the suffix.
powerbi-consumption-remote#2 | S | Power BI doesn't enforce RLS when you use service principal authentication | Both clauses match the page: user authentication applies RLS; service-principal queries can access everything that principal is authorized to access.
powerbi-consumption-remote:tools | S | Execute Query, Get Semantic Model Schema, Get Report Metadata, and Generate Query | All four names match. Their documented operations query, retrieve metadata or generate DAX; none changes models. No missing, invented or wrong-kind tool confirmed.
powerbi-consumption-remote:flagged | S | runs a DAX query...retrieves the high-level schema | No documented protected mutation, credential-returning tool or license-acceptance operation requires a flag. Generate Query requires an existing Copilot license and consumes capacity; neither is license acceptance or a capacity-setting change.
graph-enterprise:use | S | read-only Microsoft Graph API calls...resolve email addresses automatically | Verified Entra read-only scope, both provisioning roles and Core’s email-resolution recommendation. The factory separately prohibits the resulting role mutations.
graph-enterprise:where | S | https://mcp.svc.cloud.microsoft/enterprise...only delegated permissions for user-interactive scenarios | The overview provides one hosted endpoint; setup excludes app-only workflows. Checked directory, manifest and profiles: outside the directory, unpinned and not loaded.
graph-enterprise:stage | S | currently in public preview | The overview’s Current scope and capabilities section explicitly states public preview.
graph-enterprise#1 | S | Application Administrator or Cloud Application Administrator role...public preview | Setup requires tenant enablement and either named role to consent; the overview supplies the stage.
graph-enterprise:tools | S | microsoft_graph_get: Runs read-only Microsoft Graph API calls | Verified all three names and descriptions: suggest_queries retrieves examples, get performs read-only calls, and list_properties retrieves schema. No missing, invented or wrong-kind tool confirmed.
graph-enterprise:flagged | S | read-only Microsoft Graph API calls while honoring user roles | No documented tool makes protected changes or accepts a license. Administrative provisioning is a separate operator procedure, not one of these tools.

## Task D

G2-F1 | F | found = toolchain_catalog.tool_names(self.server(catalog, entry["server"]), lock) or [] | Checked catalog, profiles, skipped authoring contracts and variant tests. Security-role mutations are now changes rather than an unconditional tool ban, and uncaptured variants receive a non-vacuous catalog fallback. The accept_eula exception is explicitly UNVERIFIED; actual suppression remains unconfirmed.
G2-F2 | P | for e in server["flagged"] for c in e.get("changes", []) | The production guard, acronym splitting, expanded vocabulary and reviewed exception are implemented. The cross-area defect remains: removing get_access_token’s credential ban and mentioning it in a schedules change passes both check_structure and check_against. Area-aware coverage is still needed; this Medium portion is not closed.
G2-F3 | F | the contract of another server | Checked implementation and targeted mutation tests: foreign-server contracts, nonexistent backticked change-tool names, and knowledge tools simultaneously flagged as never called are rejected.
G2-F4 | F | a change of the data source of a model | The remote authoring entry now has a connections changes statement covering model data-source changes, including partitions. Confirmed its generated reference and AGENTS.md propagation.
G2-F5 | F | a note goes with the tools of the entry | check_structure rejects a note attached to an entry naming no tools. The targeted rejection test passes.
G2-F6 | F | the README does not say whether it covers anything else | The unsupported local-file assertion is removed. Checked the revised reference against the README’s semantic-model-only wording and its separate local EULA persistence statement.
G2-F7 | F | return learn_slug(url) + ".md" | Verified the fallback without learn_extract, consumption-tool heading extraction and removal of count slicing. All 17 list/access comparisons pass against the supplied sources, including all four consumption tools.
G2-F8 | F | core_get-item-definition, core_update-item-definition and a jobs namespace | The needs sentence includes both definition tools. Compared the README with the captured full contract: both definition tools and all five documented jobs tools are absent from that contract.

## FINDINGS

### F1 — Medium — Pipeline definitions lack a protected connection-change boundary

**File:** `CLONE3\new\toolchain\catalog.json`, lines 903–905, `datafactory-local.flagged` connections entry. This omission propagates into AGENTS.md and the generated reference.

**Quote:** reads from an Azure Blob Storage source...`mcp_datafactorymc_update_pipeline_definition`

**Source:** Cited pipeline guide, **Define pipeline activities**, lines 83–84 of its supplied snapshot; also checked the live page.

The guide demonstrates choosing pipeline source and destination through activity-definition JSON. The catalog prohibits four dedicated connection tools but supplies no connection-effect prohibition for the general definition updater. Repointing a pipeline’s data-source connection can therefore appear to be an ordinary approved write rather than a prohibited connection change. Comparable model data-source changes are already protected for Power BI.

**Suggested replacement:** Retain the named bans and add a connections `changes` statement:

> a change of a pipeline's data source connection or connection binding, including through `update_pipeline_definition`

Regenerate both instruction outputs. This should prohibit the protected effect, not ordinary pipeline-definition edits.

## CHECKED AND FINE

**27 rows have verdict S or F: 20 supported statements and seven fixed findings.** Twelve targeted snapshot tests passed; generated AGENTS.md and the reference match their generator. No additional Task C contradiction was confirmed. Every evidence quote above was checked verbatim and is at most 12 words.

**Not checked:** authenticated live behavior, actual EULA-tool suppression, execute_query side-effect restrictions, or the full toolchain suite.
