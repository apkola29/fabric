# Verification of the catalog of MCP servers, round 2: the reply of Grok 4.7

The reply as it came back, with the agent's own header removed. It read the files in the state of the review snapshot of round 2 (the paths in the reply are relative to it) and took: 73 statements, `AGENTS.md` and the generated tables, and the closure of the round-1 findings of GPT. The author's checks and the dispositions are in [mcp-catalog-findings.md](mcp-catalog-findings.md).

eventhouse-remote:use | S | Discover KQL database schemas and metadata dynamically | The page also says to generate KQL queries and to sample data; the directory says discover schemas and query with KQL.
eventhouse-remote:where | S | acts as an HTTP-based MCP endpoint | Remote HTTP. The example has a per-item URL and a global `kqlEndpoint`. The directory lists it as Remote. Not in `toolchain.json`.
eventhouse-remote:stage | S | remote MCP server for eventhouses (preview) | The title states preview.
eventhouse-remote#1 | S | remote MCP server for eventhouses (preview) | The title states preview.
eventhouse-remote#2 | S | exposes a set of tools that AI agents can use | The page describes tools and names none.
eventhouse-remote:tools | S | exposes a set of tools that AI agents can use | No named tool list on the cited pages.
eventhouse-remote:flagged | S | Schema discovery, KQL query generation, data sampling | Those are the remote capabilities. No security, connection, schedule, or credential tool is named.
activator-remote:use | S | KQL data sources only ... Teams and email actions only | The limitations state both restrictions.
activator-remote:where | S | applies to a single Activator artifact | One URL per artifact. The directory hosting is Remote. Not in `toolchain.json`.
activator-remote:stage | S | remote MCP server for Activator (preview) | The title states preview.
activator-remote#1 | S | remote MCP server for Activator (preview) | The title states preview.
activator-remote#2 | S | KQL data sources only ... Teams and email actions only | Both limits are on the page.
activator-remote:tools | S | list_rules | The table names exactly `list_rules`, `create_rule`, `start_rule`, and `stop_rule`. Start and stop change a rule; they do not delete it.
activator-remote:flagged | S | Teams and email actions only | No tool changes a role, a schedule, a label, or a credential. A KQL source on a rule is not a Fabric connection.
operations-agent-remote:use | S | exposes two MCP endpoints | Configure and query. The directory says configure and manage monitoring.
operations-agent-remote:where | S | two HTTP-based MCP endpoints | Two URLs per item. The directory hosting is Remote. Not in `toolchain.json`.
operations-agent-remote:stage | S | operations agents (preview) | The title states preview.
operations-agent-remote#1 | S | operations agents (preview) ... only manual configuration is supported | Both clauses are on the page.
operations-agent-remote#2 | S | Contributor or Admin access to the workspace | The page states that access.
operations-agent-remote:tools | P | Remove a data source | `remove_knowledge_source` and `remove_agent_action` are Type Write on the page; destructive is stronger than that label. The other 19 names match the two tables.
operations-agent-remote:flagged | S | write tools use the signed-in user's permissions | No tool changes roles, RLS, schedules, labels, capacity, or credentials. A knowledge source is not a Fabric connection.
data-agent-remote:use | S | Ask a published data agent questions | Directory primary use.
data-agent-remote:where | S | workspaces/{WorkspaceId}/dataagents/{DataAgentId}/agent | One URL per published agent. The directory hosting is Remote. Not in `toolchain.json`.
data-agent-remote:stage | S | When you publish a Fabric data agent | Neither cited page says preview, public preview, GA, generally available, or beta for this server.
data-agent-remote#1 | S | exposes a single MCP tool ... its description becomes the tool description | Both clauses are on the page.
data-agent-remote#2 | S | Fabric bearer token ... user identity or a service principal | Both clauses are on the page.
data-agent-remote#3 | S | doesn't support dynamic client registration ... server supports tasks | Both clauses are on the page.
data-agent-remote#4 | S | When you publish a Fabric data agent | The page and the directory state no release stage.
data-agent-remote:tools | S | exposes a single MCP tool | The tool name is per agent and is not a fixed name on the page.
data-agent-remote:flagged | S | exposes a single MCP tool | The tool asks a question. The client attaches the token. Nothing changes security.
ontology-remote:use | S | business entities, relationships, and definitions from an ontology | Directory primary use.
ontology-remote:where | S | items/<ontology-item-ID>/ontologyEndpoint | One URL per item. The directory hosting is Remote. Not in `toolchain.json`.
ontology-remote:stage | S | This feature is in preview | The page states preview, not public preview.
ontology-remote#1 | S | This feature is in preview ... can't currently use Service Principal | Both clauses are on the page.
ontology-remote#2 | S | exposing an API | The page names no tool.
ontology-remote:tools | S | exposing an API | No tool names on the cited pages.
ontology-remote:flagged | S | can't currently use Service Principal | No tool is named that changes a protected area.
datafactory-local:use | S | connections, dataflows, pipelines, copy jobs, and Apache | Directory primary use. The README lists the same areas.
datafactory-local:where | S | "command": "dnx" | Stdio command on the README. The directory hosting is Local. Not in `toolchain.json`.
datafactory-local:stage | P | Pipeline management is a preview feature | Preview is on the cited pages for tools and for pipeline management, so "not stated" is too strong for the pages.
datafactory-local#1 | S | .NET 10.0 or later ... "command": "dnx" ... *(Preview)* | The README states .NET 10, dnx, and Preview on tools, and names no stage for the server.
datafactory-local#2 | P | get_access_token ... sign_out | The auth tools are on the README. "the person or the runner" and rule 2 are not on a cited page.
datafactory-local#3 | S | Pipeline management is a preview feature that requires the `--pipeline` flag | The Learn page states both parts.
datafactory-local#4 | S | Launch an interactive Create Connection form via `create_connection_ui` | The guide names it. The README tool list does not.
datafactory-local:tools | S | delete_airflow_job ... create_connection_ui | The README names 51 tools and the guide adds `create_connection_ui`. Kinds match read, write, and the one delete.
datafactory-local:flagged | S | get_access_token ... create_connection ... create_pipeline_schedule | Those tools return a token, create a connection or gateway, or create or enable a schedule. `get_connection`'s example returns a credential type, not a secret.
notebook-integration-local:use | S | notebook context to Claude Code and Codex | Directory primary use.
notebook-integration-local:where | S | Local (VS Code extension) | Directory hosting. The page says the agent uses the local MCP server. Not in `toolchain.json`.
notebook-integration-local:stage | S | Develop Fabric notebooks with Claude Code | Neither cited page says preview, public preview, GA, generally available, or beta.
notebook-integration-local#1 | S | notebook language, target, document revision, workspace and runtime context ... attached-resource metadata | The page states that retrieval.
notebook-integration-local#2 | S | Install the Fabric Data Engineering VS Code extension and complete the sign-in | Prerequisites. Neither page states a release stage.
notebook-integration-local:tools | S | uses the local MCP server | The page names no tool.
notebook-integration-local:flagged | S | doesn't change your Fabric authentication, workspace permissions | The page excludes credentials and does not change permissions.
onelake-hosted:use | S | browse files, inspect table metadata, and manage directories | In one Fabric item.
onelake-hosted:where | S | without installing a local MCP server ... items/{itemId}/mcp | Hosted, one URL per item. Not in the directory table. Not in `toolchain.json`.
onelake-hosted:stage | S | currently in public preview | The page states public preview.
onelake-hosted#1 | S | currently in public preview ... Azure Storage audience ... Don't substitute a token for | Storage audience, and do not use the Fabric API token.
onelake-hosted#2 | S | Choose a Microsoft Fabric MCP server | I read the directory table. This server is not in it.
onelake-hosted:tools | S | 11 marked read-only and idempotent, and four marked destructive | The 15 names match the tables, including `onelake_create_directory` as destructive.
onelake-hosted:flagged | S | The link doesn't contain the file bytes or grant access | Upload instructions are not a SAS. Principal access is a read. Deletes are ordinary files.
powerbi-consumption-remote:use | P | prefer to use the Fabric IQ MCP server | The page says Fabric IQ MCP server, not the catalog id `fabric-iq`. DAX and metadata are on the page.
powerbi-consumption-remote:where | S | is a remote-hosted endpoint | One URL on the page. Not in the directory table. Not in `toolchain.json`.
powerbi-consumption-remote:stage | S | which is in preview | The page states preview.
powerbi-consumption-remote#1 | P | Users can use the Power BI Model Context Protocol server endpoint (preview) | The statement drops `(preview)` from the setting name.
powerbi-consumption-remote#2 | M | doesn't enforce RLS when you use service principal | The page says RLS is not enforced for a service principal. The statement says the principal does not support it.
powerbi-consumption-remote:tools | S | Execute Query, Get Semantic Model Schema, Get Report Metadata, and Generate Query | The page names these four and sends creates and changes to the authoring server.
powerbi-consumption-remote:flagged | S | Execute Query, Get Semantic Model Schema | The four tools read or generate DAX. None changes RLS or accepts a license.
graph-enterprise:use | P | Add Microsoft Graph MCP Server to resolve email addresses | The Core page suggests it for role lookups. "tenant administrator" and "the factory flags" are not on the cited pages.
graph-enterprise:where | S | https://mcp.svc.cloud.microsoft/enterprise | One URL. Not in the Fabric directory. Not in `toolchain.json`.
graph-enterprise:stage | P | currently in public preview | The overview says public preview. The catalog stage is preview.
graph-enterprise#1 | S | currently in PREVIEW ... Application Administrator or Cloud Application Administrator | Enablement and the consenting roles are on the get-started page.
graph-enterprise:tools | S | microsoft_graph_get ... Runs read-only Microsoft Graph API calls | The overview lists exactly these three tools.
graph-enterprise:flagged | S | Runs read-only Microsoft Graph API calls | The tools do not change roles, licenses, or settings.

P-F1 | F | mixed (1): `executeSQL` | `mcp-servers.md` lists one mixed tool and never-made changes for permissions and row-level security. `execute_query` is only in the needs sentence. AGENTS.md rule 10, preamble "What you never do" 7, and router 5.6 say never called and never made.
P-F2 | F | a `core_create-item` call that carries label settings | AGENTS.md flagged table also has the `core_create-workspace` capacity-or-domain change. Both are in the catalog. Claim `gh-fabric-mcp-readme-protected-arguments` is in `scripts\facts.json`.
P-F3 | F | PBI_MODELING_MCP_ALLOWED_CONNECTION_HOSTS adds hosts | The reference needs sentence also says `database_operations` can deploy to Fabric, and a data-source change is never made.
P-F4 | F | onelake_create_shortcut, onelake_create_shortcuts_in_bulk, onelake_reset_shortcut_cache | Those three are on the `destructive (10)` line of `fabric-core` in the reference.
P-F5 | F | mixed (17): `database_operations` | The reference lists 17 mixed routers, `accept_eula` and `transaction_operations` as write, and three read routers.
P-F5b | F | mixed (1): `executeSQL` | `executeSQL` is mixed, not write. Same closure as P-F1.
P-F6 | F | it does not cover local files or configuration | That clause is in the needs of `powerbi-authoring-local` in the reference.
P-F7 | P | A server that the lock did not measure (a hosted one) | Router 5.3 and the reference header say any server the lock did not measure. AGENTS.md rule 7 and preamble "How to work" 6 still say hosted only. AGENTS.md also omits "where it lists none, say what the server listed."
P-F8 | F | a server that they connected in their own settings | AGENTS.md "Start of every session" 2. The preamble "What you have" 1 and router 1.3 have the same exception.
P-F9 | F | annotated neither read-only nor destructive | The reference uses annotated read-only, annotated destructive, and annotated neither. The header says they are the server's own words.
P-F10 | F | capacity, tenant or workspace settings | That area name is in the AGENTS.md flagged table and in the reference, including OneLake workspace settings.
P rows | F | Microsoft Fabric (Public Preview) | `microsoft-learn` manifest status is `unverified`, and its needs say the pages state no release stage. `fabric-local` needs say Data Factory authentication is on another page, and the stage cites that README. The protected-arguments claim is in `facts.json`.

FINDINGS

F1 Medium. AGENTS.md line 13, rule 7, and `toolchain\instructions\factory-preamble.md` line 37, "How to work" 6. Quote: "A server that the lock did not measure (a hosted one)". Router 5.3 and the reference header say any unmeasured server, including a local one such as `datafactory-local`. A literal reading of AGENTS.md does not require a name comparison for that server. Replacement: "A server that the lock did not measure has no contract. Where its entry lists tools, report a difference of names before you go on. Where it lists none, say what the server listed."

F2 Medium. `toolchain\skills\factory-router\references\mcp-servers.md` line 333, `powerbi-consumption-remote`. Quote: "a service principal does not support it". The page says "doesn't enforce RLS when you use service principal" and that the principal can access all data it is authorized to access. An agent can read the catalog as "a service principal cannot use RLS" and miss the bypass. Replacement: "Row-level security applies to a user. Service principal authentication does not enforce it, so a service principal can access all data it is authorized to access."

F3 Low. Same file, line 340, `graph-enterprise`. Quote: "one URL. Stage: preview". The overview says "currently in public preview". The kit uses `public-preview` for that phrase (`onelake-hosted`, `foundry-mcp`). Replacement: stage `public preview`.

F4 Low. AGENTS.md line 86, generated others table. Quote: "a tenant administrator provisions it". The get-started page requires an Application Administrator or a Cloud Application Administrator. Replacement: "an Application Administrator or a Cloud Application Administrator provisions it".

F5 Low. Reference line 332, `powerbi-consumption-remote`. Quote: "Users can use the Power BI Model Context Protocol server endpoint". The page's setting name ends with "(preview)". Replacement: add "(preview)" to the setting name.

CHECKED AND FINE

76. I did not re-fetch live pages, did not run these servers, and did not re-read the modeling README to prove that each of the 17 routers deletes.
