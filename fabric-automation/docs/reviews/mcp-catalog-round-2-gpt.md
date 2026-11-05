# Verification of the catalog of MCP servers, round 2: the reply of GPT 6.1 Sol

The reply as it came back, with the agent's own header removed. It read the files in the state of the review snapshot of round 2 (the paths in the reply are relative to it) and took: 62 statements, the preamble, the router skill, the changed passages of the README, the header of the reference, and the closure of the round-1 findings of Gemini. The author's checks and the dispositions are in [mcp-catalog-findings.md](mcp-catalog-findings.md).

```text
fabric-rti-local:use | S | eventhouse, eventstream, Activator, and map resources. | Learn covers these workloads, KQL and Azure Data Explorer; the directory agrees.
fabric-rti-local:where | S | In `stdio` mode (local) | Manifest confirms the uvx command and azure-identity; directory confirms local hosting and membership.
fabric-rti-local:stage | S | This project is in Public Preview | README explicitly states Public Preview; manifest agrees.
fabric-rti-local#1 | S | implementation may significantly change prior to General Availability. | Both preview and the implementation-change warning are explicit.
fabric-rti-local#2 | M | unless `FABRIC_RTI_HTTP_ALLOW_MI` or `FABRIC_RTI_HTTP_DEBUG_MODE` is explicitly enabled: | catalog.json:412 drops the default-HTTP condition. Managed-identity/debug modes admit bearer-less requests; debug permits local credentials. Replace with “In default HTTP mode…” and name the exceptions. Manifest confirms stdio launch.
fabric-rti-local#3 | S | Eventhouse (Kusto) - 13 Tools + 1 Optional | README headings report the four counts and optional configuration. Lock fabric-rti-local/default independently confirms 39 tools; these are reported README counts, not a reconciled upstream total.
fabric-rti-local:tools | S | Execute Kusto management commands | Lock 0.6.2 confirms every listed name and annotations: 21 read-only, seven neither, eleven destructive. README's optional kusto_get_shots and omitted kusto_show_command do not contradict that captured build. No annotation was reinterpreted as reviewed behavior.
fabric-rti-local:flagged | T | Execute Kusto management commands (`.show`, `.create`, `.alter`, `.drop`) | The generic management runner is not bounded to database/table grants and RLS. Other protected management changes lack a prohibition; broaden statement-level flags rather than banning the runner. See F5.
azure-mcp:use | S | Get architectural best practices, design patterns, and recommendations | Tools page and README cover Azure resource operations and all four knowledge areas.
azure-mcp:where | S | Transport mechanism to use for Azure MCP Server. Default: `stdio`. | Manifest confirms local npx launch and azure-identity for both read/full variants.
azure-mcp:stage | S | Azure MCP Server 2.0 is now [generally available] | Manifest beta and lock 4.0.0-beta.4 establish the pinned build's stage; needs #5 explicitly distinguishes it from the README's 2.0 GA announcement.
azure-mcp#1 | S | Azure MCP Server tools are disabled by default in supported hosts. | Overview also explicitly makes tool availability depend on the identity's subscription RBAC permissions.
azure-mcp#2 | S | The server uses Entra ID through the Azure Identity library | Exact authentication statement appears in the overview.
azure-mcp#3 | S | If true, no write operations are allowed. | Tools page documents read-only mode; manifest read args contain --read-only; lock azure-mcp/read contains its namespace list.
azure-mcp#4 | S | Tools that handle sensitive data, such as secrets, require user consent | Tools page documents elicitation, Key Vault secrets, the discouraged bypass and its false default. Neither manifest launch sets that bypass.
azure-mcp#5 | S | Azure MCP Server 2.0 is now [generally available] | Checked both Learn pages for a server release stage; neither states one. Manifest/lock establish beta for the pinned 4.0.0-beta.4 build, not the whole upstream project.
azure-mcp#6 | M | Azure Resiliency Agent ... General Azure resiliency guidance | catalog.json:454 conflates different services: README separately lists Resilience Management and Resiliency Agent. Replace “which the lock spells resiliency” with “resiliency is a separate locked namespace.” Other named page/lock differences were checked.
azure-mcp:tools | S | Server mode: `namespace` (default) | Every name and the total 70 match azure-mcp/read in the lock. Manifest confirms --read-only; documented upstream/version differences are not invented locked tools. Namespace annotations are not per-command kinds.
azure-mcp:flagged | T | Connection strings and passwords | Only Key Vault output, role assignments and Policy mutations are covered. Credential input/output elsewhere, connection/schedule changes and other security mutations are missing. See F1–F2; use operation-level flags, not blanket namespace bans.
azure-mcp:knowledge | S | Design cloud systems by gathering requirements through guided questions | Checked all four documented knowledge capabilities; exact namespace tool spellings also match the lock.
bicep-mcp:use | S | Lists up-to-date recommended Bicep best-practices for authoring templates. | README documents schema, formatting and best-practice authoring tools.
bicep-mcp:where | S | **stdio** transport, launched locally by a client process | Manifest confirms dotnet tool exec and credentials none; this is the kit's local variant, not the README's optional remote-hosting sample.
bicep-mcp:stage | S | Bicep (PREVIEW) | README names the tool picker entry explicitly; manifest now says preview.
bicep-mcp#1 | S | These tools are not designed to deploy directly to Azure. | README limitations explicitly distinguish authoring context from deployment.
bicep-mcp#2 | S | `Azure.Bicep.McpServer` NuGet tool. | README Transport also explicitly describes stdio and launch by a local client.
bicep-mcp#3 | S | search for "Bicep (PREVIEW)" | This is the documented picker label. Neither cited page states another release stage for this server.
bicep-mcp#4 | S | `get_bicep_file_diagnostics` | Compared README tool list against lock bicep-mcp/default: diagnostics is page-only; build_bicep and build_bicepparam are lock-only, exactly as stated.
bicep-mcp#5 | S | The catalog is bundled with Bicep, not queried live from Azure. | The following sentence disclaims cloud/region/subscription availability. This concerns schema selection, not every discovery tool's data source.
bicep-mcp:tools | S | `format_bicep_file` | Lock 0.48.1 confirms all 14 names and read-only annotations. Page/lock version differences are disclosed in needs #4; no reviewed behavioral kind is inferred from annotations.
bicep-mcp:flagged | S | not designed to deploy directly to Azure | Reviewed the complete documented tool list: no tenant security, connection, schedule, capacity, credential or license operation is documented. Local formatting/decompilation is not a protected tenant change.
bicep-mcp:knowledge | S | Lists up-to-date recommended Bicep best-practices for authoring templates. | Exact get_bicep_best_practices name and knowledge purpose appear together.
azure-arm-cost:use | S | deploy and manage ARM templates, create or update resources | README and cost guide support the full-server warning, default resource writes and optional create_budget. Approval is correctly identified as kit policy, not a server-enforced restriction.
azure-arm-cost:where | S | all tool calls are made on behalf of that user | Manifest confirms HTTP, the single URL, pinned membership and entra-delegated. That is the kit's declared sign-in class; the README does not specify the protocol.
azure-arm-cost:stage | S | During this preview | README explicitly identifies the current server preview; manifest agrees.
azure-arm-cost#1 | S | Right now you can use: | README's Supported Clients section names GitHub Copilot Chat in VS Code and GitHub Copilot CLI during preview.
azure-arm-cost#2 | S | sign in with your Azure credentials. | Governance separately confirms the signed-in user's permissions and on-behalf-of execution; no authentication mechanism is named.
azure-arm-cost#3 | S | Create or update Azure resources and resource groups. | Checked the default table: deployments, generic writes, ARG, schemas and cost/pricing tools all appear.
azure-arm-cost#4 | S | denies requests made by the deployment tool | Governance explicitly identifies create_deployment and an Azure Policy blocking its requests. This does not claim that direct resource writes disappear.
azure-arm-cost#5 | S | `x-mcp-toolset: CostManagement` | Cost guide lists nine opt-in tools, including create_budget; manifest sets this exact header and does not remove default tools.
azure-arm-cost:tools | S | Starts an asynchronous EA or MCA Azure pricesheet download. | Compared all 17 default and nine optional names: none missing or invented. Kinds fit the stated behavior, including write start_pricesheet_download and read-but-forbidden get_pricesheet_status.
azure-arm-cost:flagged | T | Creates or updates a single Azure resource | SAS, role-assignment and policy/network-rule flags are justified but incomplete. Generic template/resource payloads can also perform protected connection, schedule, capacity/settings or credential actions. See F3.
foundry-mcp:use | S | agents, sessions, toolboxes, datasets, evaluations, model deployments | Available-tools introduction supports the stated Foundry workload scope.
foundry-mcp:where | P | a cloud-hosted implementation of the Model Context Protocol (MCP) | Remote hosting and one public endpoint are supported; it is absent from the manifest. UNVERIFIED from its cited pages: directory-exclusion/group “also”; its pages array omits the directory citation. See G-F6.
foundry-mcp:stage | S | This feature is currently in public preview. | Both cited pages expressly state public preview.
foundry-mcp#1 | S | This preview is provided without a service-level agreement | Exact preview limitation is stated on both pages.
foundry-mcp#2 | S | All operations run with the authenticated user's permissions | Available-tools Permissions explicitly specifies Microsoft Entra ID On-Behalf-Of flow.
foundry-mcp#3 | S | 79 Foundry MCP Server tools across 17 categories | Parsed all tool rows: 35 read, 44 write; twelve named delete tools are mapped to destructive. The separate replacement-kind defect is in the tools row/G-F1.
foundry-mcp:tools | T | Create or replace a project connection. | All 79 names are present and none invented. Wrong kind: project_connection_create is write despite explicit replacement behavior; move it to destructive, yielding 35 read/31 write/13 destructive. Other listed kinds match the documented operations.
foundry-mcp:flagged | T | permission mode (optional) | Existing connection, continuous-evaluation and SAS flags are justified. Missing protected arguments: session_file_mkdir permission mode and model deployment capacity/instance allocation. See F4; read-only metadata/quota tools need not be banned.
graphql-sample:use | S | expose GraphQL schema discovery and queries. | Directory and tutorial describe the same locally hosted sample and Fabric GraphQL purpose.
graphql-sample:where | S | The server starts on `http://localhost:3000` | Tutorial gives local HTTP /mcp configuration; directory places it under related integrations/samples. It is not in the manifest.
graphql-sample:stage | S | This local server is intended for development and learning. | Checked the complete tutorial and directory: neither states preview, beta or GA for this sample. Development intent is not a release stage.
graphql-sample#1 | S | node FabricGraphQL_MCP.js | Tutorial explicitly clones microsoft/fabric-samples, runs Node.js and states the localhost listener.
graphql-sample#2 | S | Only workspace admins can enable introspection. | Same section says introspection is disabled by default and required for the MCP server to work.
graphql-sample:tools | S | For all data retrieval and manipulation operations | Both exact names are present; introspection reads metadata, while query-graphql supports retrieval and manipulation, correctly mixed.
graphql-sample:flagged | S | Retrieves the complete GraphQL schema | Neither documented tool administers the prerequisite identity/introspection settings or takes credentials. Those are operator setup steps, not MCP tools. Ordinary exposed-data mutations require approval, not a blanket flag.
sql-mcp-server:use | S | builds on Data API builder's entity abstraction | Overview and directory support customer-hosted database entity access through DAB.
sql-mcp-server:where | S | The server is self hosted | Overview permits standard hosting or local CLI; directory calls it customer-hosted/related. No manifest entry exists.
sql-mcp-server:stage | S | a production-ready surface | Checked all three cited pages: no explicit preview, beta or GA stage for the SQL MCP server. “Production-ready” is not a release-stage declaration.
sql-mcp-server#1 | S | It supports two transports: streamable HTTP ... stdio | Overview explicitly states inclusion from DAB 1.7 and self-hosting; both transports are documented.
sql-mcp-server:tools | T | `execute_entity` - Runs stored procedures | Wrong kind: execute_entity can encapsulate queries or mutating/deleting procedures; use mixed. No built-in name is missing/invented, but qualify aggregate_records as 2.0+ and seven as built-ins; overview also documents dynamically named custom procedure tools.
sql-mcp-server:flagged | T | enforces execute permissions, and passes parameters safely | execute_entity delegates to a configured procedure; parameter safety and RBAC do not prohibit protected actions inside its body. Add statement-level prohibitions for protected procedure effects/results, including custom procedure tools. See F6.
```

```text
G-F1 | P | write (32): ... `project_connection_create` | catalog.json foundry-mcp and Reference now include all 79 tools and the claimed flags. However, the page explicitly says create OR REPLACE; move this tool to destructive and adjust counts. Protected-argument gaps remain (F4).
G-F2 | F | mixed (1): `executeSQL` | Checked fabric-sql catalog entry, Reference, AGENTS rule 10, preamble Never-do 7 and router 5.6: SQL is no longer globally forbidden; permissions/RLS are statement-level refusals. execute_query is explanatory, not an invented second catalog tool.
G-F3 | F | Any other server has no measured contract | Checked Reference header, AGENTS rule 7, preamble How-to-work 6 and router 5.3: measured contracts stop on drift; unmeasured lists require name-difference reporting, with no schema-contract claim.
G-F4 | F | mixed (1): `query-graphql` | Catalog and generated Reference contain introspect-schema/read and query-graphql/mixed, the local-URL endpoint, and the page-tool fact claim.
G-F5 | F | Never called, credentials (rule 2): `get_access_token` | Verified get_access_token is read, all four authentication/token tools are flagged, add_connection_to_dataflow and create_connection_ui are connection flags, and the new UI tool is sourced from the connection guide.
G-F6 | P | Read from: `azure/ai-foundry/mcp/get-started` | Pipeline --pipeline citation, connection guide and Graph/Core citation are fixed. Directory citations cover every claimed directory member and other external/related server except foundry-mcp. Add the directory to that server's pages array; the claim “every” is not satisfied.
G-F7 | R | A call that changes anything is a change of a tenant | LOCK_KIND_WORDS and generated annotation/namespace wording are fixed. But the new header also recasts local-file mutations as tenant changes, importing tenant approval into offline authoring; qualify it to live tenant state (F7).
G-F8 | F | every tool of a server whose tools were read from a page | Checked README Instructions-for-agents/Keeping-it-current against facts.json: all 38 cited Learn URLs have date checks; page-sourced tool lists have claims, with separately watched EULA/UI exceptions. Coverage is no longer presented as exhaustive arbitrary GitHub-page monitoring.
G-F9 | F | Using it needs Contributor or Admin access to the workspace | Catalog operations-agent-remote needs #2 and generated Reference match the page's workspace-role prerequisite, rather than describing it as a different role scope.
G-F10 | F | inside an extension of VS Code ... reached at a local address | Catalog endpoint values and Reference distinguish notebook extension integration from the GraphQL local HTTP listener.
G-F11 | F | Stage: public preview. | Both onelake-hosted and foundry-mcp now have status public-preview in catalog.json and public-preview wording in the generated Reference.
G-F12 | F | `get_bicep_best_practices` of the Bicep server | Preamble knowledge step 2 includes Bicep. Preamble reachability step 3 and router 4.2 use documented Azure best-practice/Well-Architected tools, not an invented documentation-tool capability.
```

## FINDINGS

Paths below are relative to `CLONE2\new`.

### F1 — High — Azure credential protection is narrower than the documented surface

**File:** `toolchain\catalog.json`, `azure-mcp.flagged.credentials`; generated Reference line 196.  
**Quote:** “Connection strings and passwords”

The cited Azure tools page identifies these as sensitive outputs and also accepts key/connectionString authentication. `appconfig` can retrieve a ConnectionString; `appservice` can retrieve application settings. The credential flag covers only Key Vault outputs—not these reads, credential-valued inputs, or secret creation/import. Read-only mode does not prevent sensitive reads.

**Replacement:** Prohibit secret-valued inputs and outputs across every namespace, including secret-bearing authentication arguments; retain ordinary metadata/name listing.

### F2 — Medium — Azure protected mutations are not limited to role and Policy operations

**File:** `toolchain\catalog.json`, `azure-mcp.flagged`; generated Reference lines 197–198.  
**Quote:** “Add a database connection for an App Service web app”

The cited README also advertises SRE Agent connectors/scheduled tasks, SQL firewall changes, Backup scheduling/security settings, and file-share private-endpoint approval. These protected operations have no applicable connection, schedule or broader security/settings flag. The read variant blocking writes does not define the full variant’s refusal policy.

**Replacement:** Add category-specific `changes` for protected effects through any namespace, including generic `arm`/`deploy` commands. Do not prohibit ordinary resource CRUD or metadata reads wholesale.

### F3 — Medium — ARM generic payloads escape the narrow protected-change list

**File:** `toolchain\catalog.json`, `azure-arm-cost.flagged`; generated Reference lines 232–234.  
**Quote:** “Creates or updates a single Azure resource”

The cited ARM README permits arbitrary resource body/template payloads at tenant and lower scopes. Denying only role assignments, policy assignments and network-security rules leaves connections, schedules, capacity/settings, other security resources and credential-bearing payloads uncovered. The SAS flag is correctly present.

**Replacement:** Add protected-target/body/parameter changes under each applicable area, independent of which generic deployment/resource tool performs them. Ordinary budget creation should remain an approval-governed write.

### F4 — Medium — Foundry tools have unflagged protected arguments

**File:** `toolchain\catalog.json:1038–1044`, `foundry-mcp.flagged`; generated Reference lines 359–361.  
**Quote:** “permission mode (optional) ... capacity units ... billable dedicated GPU capacity”

The cited tools page gives `session_file_mkdir` an explicit permission mode. `model_deploy_azure_direct_model` and its `model_deploy` alias allocate/update capacity units; `model_deploy_managed_compute` allocates dedicated GPU capacity through its template and `instanceCount`. None is covered by the connection/schedule/SAS flags.

**Replacement:** Add permissions changes for explicit access-mode selection and capacity changes for those three deployment tools. Leave ordinary file creation and model/quota inspection available where otherwise allowed. The replacement-kind defect is recorded in G-F1.

### F5 — Medium — RTI’s management-command safeguard is incomplete

**File:** `toolchain\catalog.json`, `fabric-rti-local.flagged`; generated Reference lines 177–178.  
**Quote:** “Execute Kusto management commands (`.show`, `.create`, `.alter`, `.drop`)”

The cited README describes a general management-command runner. Current prohibitions cover only database/table access and RLS policies—not other protected management effects, such as security settings or connection/credential configuration, or permissions outside those scopes. A destructive annotation requires approval but does not supply these categorical refusals.

**Replacement:** Forbid all protected management effects under their corresponding areas and supported scopes, rather than only the two examples or the entire `kusto_command` tool.

### F6 — Medium — Stored-procedure execution lacks a protected-effect boundary

**File:** `toolchain\catalog.json`, `sql-mcp-server.flagged`; generated Reference section `sql-mcp-server`.  
**Quote:** “enforces execute permissions, and passes parameters safely”

The cited DML page describes parameter validation and execute permission—not restriction of procedure bodies. `execute_entity` can delegate protected or credential-returning operations to a configured procedure; DAB 2.0’s custom named procedure tools provide another route. No actual customer procedure bodies were inspected.

**Replacement:** Prohibit protected procedure effects and credential-valued arguments/results through `execute_entity` or custom tools; require verification of the selected procedure’s effects. Do not ban all ordinary CRUD/procedure calls.

### F7 — Medium — The new header conflates local effects with tenant mutations

**File:** `toolchain\skills\factory-router\references\mcp-servers.md:11`; generator heading `render_reference` in `scripts\toolchain_catalog.py`.  
**Quote:** “A call that changes anything is a change of a tenant”

The catalog distinguishes local authoring/configuration effects from semantic-model writes. A local-only export or configuration change is not a tenant change. The new sentence incorrectly extends the cited tenant-approval rule to these effects; this is the G-F7 regression, not an objection to the corrected annotation wording.

**Replacement:** “A call that changes live tenant state requires approval in a dev session. Jobs make no MCP writes. Local-only effects follow the profile and local-file rules.” Change the generator and regenerate.

## CHECKED AND FINE

**52 S + 9 F = 61 supported/fixed rows.** All **62 Task A IDs and 12 G findings** are covered; all 74 row quotes passed verbatim-source and twelve-word checks. None of the seven assigned servers appears in an agent/executor profile, so this slice has no by-name flag conflict with an actual job variant.

**Not checked:** live authentication/runtime behavior, tenant data, full schemas/procedure bodies, or other families’ complete review slices; no installs, sign-in or live operations were performed.
