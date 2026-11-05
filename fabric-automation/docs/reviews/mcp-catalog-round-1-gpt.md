# Verification of the catalog of MCP servers, round 1: the reply of GPT 6.1 Sol

The reply as it came back, with the agent's own header removed. It read the files in the state of the review snapshot of round 1 (the paths in the reply are relative to it) and took: the 77 statements of the pinned Fabric servers (`fabric-local`, `fabric-core`, `fabric-iq`, `fabric-sql`, the two Power BI authoring servers, the Learn server) and of the directory, with the flags of those servers, and `AGENTS.md` and the tables that it generates. The author's checks and the dispositions are in [mcp-catalog-findings.md](mcp-catalog-findings.md). A phrase of two words that the leak scan of this repository refuses is written `[phrase withheld]`.

directory | S | Remote servers in this table are hosted by Microsoft. | Counted all 14 directory entries: nine remote, five local; all catalog directory flags match.
skills#1 | S | Skills teach the AI assistant what to do. MCP servers do it. | The overview explicitly distinguishes static guidance from execution.
skills#2 | S | Skills for Fabric are organized by workload. | All eight claimed workload areas appear in the discovery table.
skills#3 | S | Report and semantic model authoring skills ship in the separate `powerbi-authoring` plug-in. | Supported as guidance versus execution; this must not mean agents cannot create reports using report-authoring tools.
microsoft-learn:use | S | search through documentation, fetch a complete article, and search through code samples. | Both sources describe official Microsoft documentation and sample retrieval.
microsoft-learn:where | S | It's a remote MCP server that uses streamable http. | One endpoint and no authentication are documented; pinned membership matches the manifest.
microsoft-learn:stage | U | The Microsoft Learn MCP Server is publicly available. | UNVERIFIED: publicly available does not establish GA. Neither cited snapshot nor the live cited pages states GA/general availability.
microsoft-learn#1 | S | There's no authentication required | Explicitly stated.
microsoft-learn#2 | S | publicly available documentation, not training or user profile information. | Exactly the documented content boundary.
microsoft-learn#3 | S | refreshes incrementally ... full refresh once a day. | Both incremental and daily full refresh are explicit.
microsoft-learn:tools | S | Search for official Microsoft/Azure code snippets and examples | All three names match the README; their descriptions are retrieval-only.
microsoft-learn:flagged | S | Fetch and convert a Microsoft documentation page into markdown format | No listed tool changes protected resources, accepts a license, or handles credentials.
microsoft-learn:knowledge | S | Performs semantic search against Microsoft official technical documentation | All three knowledge-tool descriptions match the README.
fabric-local:use | S | Documentation tools read bundled resources. Live tools authenticate and call | Offline documentation and live workload categories match; variant names and dev-only scope are kit policy.
fabric-local:where | S | stdio transport | Local command hosting and offline/live authentication agree with the pages; variants and directory membership match kit records.
fabric-local:stage | U | It's designed for development workflows | UNVERIFIED: no public-preview designation appears in any of the four cited sources, including their live versions.
fabric-local#1 | S | VS Code extension (recommended), npm/npx, or .NET source build | All three installation methods and development-machine hosting are documented.
fabric-local#2 | P | For OneLake and core Fabric tools, configure an identity | UNVERIFIED for Data Factory: the page limits this authentication recipe to OneLake/Core and refers Data Factory authentication elsewhere.
fabric-local#3 | S | Tool names and availability can vary by installed version and server configuration. | The Learn inventory is expressly non-exhaustive/version-dependent; using the recorded contract is appropriate.
fabric-local#4 | S | `jobs_run-on-demand-item-job` | The README names five Jobs tools; none appears in the supplied generated 62-tool locked inventory.
fabric-local:tools | T | Updates an existing item's display name or description | core_update-item, core_update-workspace and core_assign-workspace-to-capacity change metadata/assignment, not delete or replace resources. Their destructive labels do not match the brief’s semantic taxonomy. No missing/invented locked names alleged.
fabric-local:flagged | T | Creates a Fabric workspace, optionally assigning an [phrase withheld] and domain | Documented core_create-workspace capacity assignment and core_create-item label settings lack flags. Diagnostics/immutability are workspace settings, not capacity/tenant settings; pin-specific capability evidence needs qualification.
fabric-local:knowledge | S | all served locally without connecting to live Fabric environments. | All six documentation names and their offline purpose match.
fabric-core:use | S | OneLake data security ... OneLake settings ... Folder organization | The full stated resource-management scope and get_knowledge are documented.
fabric-core:where | S | browser-based OAuth 2.0 flow with Microsoft Entra ID | Endpoint, delegated user identity, manifest membership and directory entry agree.
fabric-core:stage | S | Fabric Core MCP Server is a remote endpoint | No release-stage designation appears in any of the three cited pages; also checked all three live pages.
fabric-core#1 | S | Each tool maps to a Fabric REST API operation | OAuth/Entra and enforcement of the authenticated user’s permissions are explicit.
fabric-core#2 | S | Some organizations restrict workspace creation to specific roles. | The creation permission and organizational restriction are explicit.
fabric-core#3 | S | You can't undo this operation. ... Folders must be empty before deletion. | Both permanent workspace/item removal and the empty-folder requirement are explicit.
fabric-core#4 | S | Without it, you need to provide user principal IDs for role operations. | This is the documented email-resolution limitation.
fabric-core#5 | S | Fabric Core MCP Server currently supports: | Confirmed absence of a release-stage designation across all three cited pages, including live content.
fabric-core#6 | S | All tools in this section require `WorkspaceId` | The common WorkspaceId and additional ItemId for item-scoped tools are explicit.
fabric-core:tools | T | `Abort` or `CreateOrOverwrite` | All 43 names are present. onelake_create_shortcut and onelake_create_shortcuts_in_bulk can overwrite; onelake_reset_shortcut_cache clears cached files. These are destructive-capable, not simply write under the brief’s definition.
fabric-core:flagged | T | These tools operate on a workspace | All nine listed prohibitions are justified, but onelake_modify_default_tier, onelake_modify_diagnostics and onelake_modify_immutability_policy are workspace settings, not the stated capacity/tenant scope.
fabric-core:knowledge | S | Get guidelines and best practices for item types | get_knowledge is explicitly described this way.
fabric-iq:use | S | The server exposes a read-only toolset | Reports/models, metadata inspection and query execution match the connector page.
fabric-iq:where | S | delegated OAuth 2.0 authentication through Microsoft Entra ID. | Remote endpoint, user identity, manifest and directory membership agree.
fabric-iq:stage | S | Fabric IQ MCP is generally available. | Explicit release-stage statement.
fabric-iq#1 | S | Service-principal and application-only authentication aren't supported. | Both delegated permission names and the service-principal exclusion are explicit.
fabric-iq#2 | S | It doesn't apply to Fabric IQ MCP. | The named Power BI tenant setting excludes this read-only server.
fabric-iq#3 | S | It isn't available in Power BI-only regions or sovereign clouds. | Both exclusions are explicit.
fabric-iq#4 | S | Fabric IQ MCP doesn't expose a natural-language answering tool. | The connector excludes every listed unsupported item type; the calling agent composes DAX. Its newer, endpoint-specific scope governs over the general overview’s ontology wording.
fabric-iq#5 | S | `ExecuteQuery` returns up to 250 rows by default. | maxRows can request more; this is a default, not an absolute result limit.
fabric-iq#6 | S | The current public version is `Fabric.Routing.FabricIQ.V1`. | The page specifies X-Variants on initialize, tools/list and tools/call.
fabric-iq#7 | S | https://fabriciq.svc.cloud.microsoft/v1/mcp/FabricIQ ... https://fabriciq.svc.cloud.microsoft/v1/mcp/fabriciq | Both spellings occur on the respective cited pages; the manifest uses the connector spelling.
fabric-iq#8 | S | If your organization uses private links | The documented replacement endpoint uses api.fabric.microsoft.com.
fabric-iq:tools | S | Runs a DAX query against a semantic model. | All six exact names and retrieval/query descriptions match.
fabric-iq:flagged | S | It doesn't provide workspace administration, development, or item-creation functionality. | The documented toolset is read-only and has no protected mutations or credential/license operations.
fabric-sql:use | S | write operations such as `CREATE`, `ALTER`, `DROP`, `INSERT`, `UPDATE`, or `DELETE` | Warehouse/SQL analytics endpoint scope and data/schema mutation capability are explicit.
fabric-sql:where | S | Configure either the global endpoint or an item-scoped endpoint | Hosting/endpoints match the page; Entra identity is the manifest designation and directory membership matches.
fabric-sql:stage | S | Fabric Data Warehouse MCP server (Preview) | Explicit in the page heading.
fabric-sql#1 | S | uses the signed-in user's identity and respects Fabric permissions. | Signed-in-user execution is explicit; Entra agrees with the manifest’s authentication designation.
fabric-sql#2 | C | especially for write operations such as | The SQL capability/approval requirement is documented, but AGENTS rule 10 and the flagged table prohibit both SQL names entirely, not merely unapproved writes.
fabric-sql#3 | S | `executeSQL` ... "execute_query" | Both source spellings are present. The marketplace allowlist is not proof that both tools coexist.
fabric-sql#4 | S | bound to a specific Fabric Data Warehouse item. | Both endpoint forms and their workspace/item placeholders are documented.
fabric-sql:tools | T | The Fabric Data Warehouse MCP server exposes one tool. | executeSQL/execute_query are alternative source spellings, not evidence of two tools. Both spellings must conservatively cover DROP/DELETE capability, not merely write. No additional missing tool established.
fabric-sql:flagged | C | The server only exposes `executeSQL`. | A permissions-capable SQL tool can warrant refusal, but the absolute never-call rule conflicts with the statement-scoped note, approval advice and SQL routing instructions.
powerbi-authoring-local:use | S | Work with TMDL and Power BI Project files | Local/Desktop and service semantic models, objects and DAX are documented.
powerbi-authoring-local:where | S | Runs on your machine over `stdio` | Command hosting and interactive/service-principal methods match; the three variants’ sign-in classes match the manifest.
powerbi-authoring-local:stage | S | Local (generally available) | Explicit release-stage statement.
powerbi-authoring-local#1 | S | Hosted (preview) ... Local (generally available) | Both deployment stages are explicit.
powerbi-authoring-local#2 | S | With only Build permission, the server can only run DAX queries | Write versus Build is explicitly distinguished.
powerbi-authoring-local#3 | S | XMLA endpoint set to Read Write on the capacity | The prerequisite explicitly applies to local access to Fabric workspace models.
powerbi-authoring-local#4 | M | prevents any write operations to your semantic model | The source guarantees no semantic-model writes, not every filesystem/configuration write. Default edit confirmation once per database is supported.
powerbi-authoring-local#5 | S | The MCP server blocks all other tool calls until you accept it. | Explicit for the pinned npm distribution; operator-only acceptance is the kit’s stricter policy.
powerbi-authoring-local#6 | S | No tenant setting blocks you from using the local server. | The XMLA control and its effects on other XMLA clients are explicitly stated.
powerbi-authoring-local:tools | T | create, update, delete, get, list, rename | Destructive-capable routers mislabeled write: table_operations, column_operations, measure_operations, relationship_operations, partition_operations, user_hierarchy_operations, calculation_group_operations, security_role_operations, perspective_operations, named_expression_operations, culture_operations. The cited descriptions explicitly include object deletion. All 22 names are accounted for.
powerbi-authoring-local:flagged | P | import/export TMDL folders, deploy to Fabric | UNVERIFIED completeness: accept_eula and security_role_operations are justified, but the pages do not establish that database import/deploy and Power Query parameter/source edits cannot also affect protected security/connections.
powerbi-authoring-remote:use | S | Avoid registering both local and remote servers at the same time. | The single-server/two-deployments explanation and overlap warning support the rule.
powerbi-authoring-remote:where | S | https://api.fabric.microsoft.com/v1/mcp/powerbi/authoring | Remote endpoint and Entra user authentication are explicit; manifest and directory membership agree.
powerbi-authoring-remote:stage | S | Hosted (preview) | Explicit release-stage statement.
powerbi-authoring-remote#1 | S | Streamable HTTP ... Microsoft Entra ID, as the signed-in user | Transport, identity and preview stage match the hosted setup.
powerbi-authoring-remote#2 | S | Users can use the Power BI Model Context Protocol server endpoint. | The exact setting and Fabric-administrator enablement requirement are stated.
powerbi-authoring-remote#3 | S | The hosted server doesn't support transactions or trace tools. | The capability table also excludes Desktop models and PBIP/TMDL files on disk.
powerbi-authoring-remote#4 | S | two overlapping tool sets | The overlap warning and choose-one guidance are explicit.
powerbi-authoring-remote:tools | S | The server exposes tools grouped by object type | No individual tool-name inventory is published on these pages. Unknown inventory is not an empty toolset.
powerbi-authoring-remote:flagged | S | security roles | Security-role mutation is explicitly supported, so the action-level refusal is justified; no concrete hosted tool names are asserted.

## FINDINGS

Paths are relative to `CLONE\new`. “Server reference” means `toolchain\skills\factory-router\references\mcp-servers.md`.

### F1 — High — SQL execution is simultaneously routed and prohibited

**Files:** `AGENTS.md:16,104`; `toolchain\catalog.json`, fabric-sql needs, second bullet/flagged; `toolchain\skills\factory-router\SKILL.md`, Warehouse routing row.

**Quote:** “a statement that changes permissions or row-level security is never run”.

Rule 10 categorically forbids any listed tool. The note reads like a statement-level restriction, while the catalog says other SQL changes need rule-6 approval and the router directs SQL through this same tool. Since the server has only that tool, even SELECT connectivity tests have no permitted route. An agent must either abandon the advertised SQL workflow or invent an exception to the absolute refusal.

**Suggested replacement:** “Both SQL tool spellings are blocked entirely under rule 10. Hand SQL execution to a person until a separately constrained, reviewed execution surface is available.” Remove the contrary routing/approval promises. Do not silently relax the never-call rule.

### F2 — Medium — Local create tools have documented protected modes but no flags

**Files:** `toolchain\catalog.json`, fabric-local.flagged; `AGENTS.md:105–110`; server reference, fabric-local.

**Quote — Fabric README, Core Fabric Operations:** “optionally assigning an [phrase withheld] ... label settings”.

The cited README documents capacity assignment inside `core_create-workspace` and label settings inside `core_create-item`. Blocking `core_assign-workspace-to-capacity` alone does not cover the former; no sensitivity-label flag covers the latter.

The README is main-branch documentation, while the generated inventory summarizes locked 1.6.0 without its input schemas: the supplied evidence does not establish that the pinned tools exclude these modes.

**Suggested replacement:** Flag `core_create-workspace` for capacity/settings and `core_create-item` for sensitivity labels, or supply version-specific reviewed schema evidence establishing that those protected inputs are unavailable. Regenerate the tables; do not assume exclusion from a name-only inventory.

### F3 — Medium — Broad modeling routers lack a verified protected-operation boundary

**Files:** `toolchain\catalog.json`, powerbi-authoring-local.flagged; `AGENTS.md:105`; server reference, powerbi-authoring-local.

**Quote — Power BI README, tools/examples:** “import/export TMDL folders ... easy switching of the data source location.”

The two listed flags correctly cover explicit EULA acceptance and the dedicated security-role router. They do not prove complete coverage. `database_operations` imports/deploys model definitions; `named_expression_operations` edits Power Query parameters, and the README explicitly advertises data-source-location changes.

The pages do not specify which generic import/source-edit subcommands preserve security and connections. This is **UNVERIFIED flag completeness**, not a claim that opening an XMLA session itself changes a Fabric connection.

**Suggested replacement:** Conservatively flag generic routers whose reviewed operations can carry security or data-source changes; otherwise split out a reviewed safe surface. State that import/deploy/source-edit operations remain blocked until their schemas and protected effects are checked.

### F4 — Medium — Core overwrite/cache-clearing tools are understated as ordinary writes

**Files:** `toolchain\catalog.json`, fabric-core.tools; server reference, fabric-core.

**Quote — Core tools reference, OneLake shortcuts:** “Confirm the existing shortcut and destination before choosing `CreateOrOverwrite`.”

Both shortcut-create tools accept replacement behavior, and `onelake_reset_shortcut_cache` clears cached files. The write bucket hides destructive-capable behavior under the brief’s deletion/removal/replacement definition. This does not mean ordinary shortcut creation needs a security flag.

**Suggested replacement:** Classify `onelake_create_shortcut`, `onelake_create_shortcuts_in_bulk` and `onelake_reset_shortcut_cache` as destructive-capable, or represent operation-specific effects with an enforced distinction. Preserve approval requirements and destination-data safeguards.

### F5 — Medium — SQL/modeling destructive capabilities are lost in aggregate kinds

**Files:** `toolchain\catalog.json`, fabric-sql.tools and powerbi-authoring-local.tools; corresponding server-reference sections.

**Quote — Power BI README, Available tools:** “create, update, delete, get, list, rename”.

The eleven modeling routers enumerated in the Task A row explicitly include deletion but are all write. SQL also supports DROP and DELETE. A router’s create/update operations do not make its delete operations non-destructive; this matters for a factory that refuses destructive job writes.

**Suggested replacement:** Record destructive as the conservative aggregate kind for the eleven deletion-capable modeling routers and the SQL execution capability, or classify/enforce each suboperation. Keep ordinary item deletion separate from security/license flags: destruction alone does not make a tool a never-call security tool.

### F6 — Medium — The read-only guarantee is broader than its source

**Files:** `toolchain\catalog.json`, powerbi-authoring-local needs, fourth bullet; corresponding server-reference bullet.

**Quote — Power BI README, Settings:** “prevents any write operations to your semantic model”.

The catalog drops the protected object’s scope when it says `--readonly` prevents every write. That is not a filesystem sandbox or a guarantee against local configuration/session-state changes; the same README says EULA acceptance is saved locally.

**Suggested replacement:** “--readonly prevents semantic-model mutations. It is not a guarantee of no local file/configuration writes. Default write-mode confirmation is once per database; factory approval remains per change.”

### F7 — Medium — The hosted drift rule assumes a reference contract that is not recorded

**Files:** `AGENTS.md:13`; server reference, “How to use it”, powerbi-authoring-remote Tools and fabric-sql Tools.

**Quote:** “for a hosted server, against its entry in the server reference”.

The hosted authoring entry intentionally contains no tool names or schemas. Treating every unlisted tool as drift makes every actual authoring tool fail; alternatively, treating the prose as a contract leaves schema changes undetectable.

SQL compounds this by rendering two source spellings as two tools although Learn explicitly says one. A marketplace allowlist is not an observed inventory.

**Suggested replacement:** “A documentation-only inventory is not a measured hosted contract. Where names/schemas are unknown, report contract verification unavailable and block reliance until operator-reviewed discovery is recorded.” Represent SQL spellings as alternatives for one capability, not a two-tool contract. Do not claim reference comparison proves unchanged schemas.

### F8 — Medium — The profile-only rule omits the explicit personal-server exception

**Files:** `AGENTS.md:21` versus `:65`; `toolchain\instructions\factory-preamble.md`, “What you have”, rule 1.

**Quote:** “Use only the skills and servers it loaded.”

This blanket instruction conflicts with the later permission to use an already-connected personal server the person specifically requested. The preamble and router explicitly recognize that exception, but the always-read session checklist does not. This ambiguity was already present in the old AGENTS.md; the new tables retain it.

**Suggested replacement:** “Use only profile-loaded skills and servers, except an already-connected personal server expressly requested under ‘Servers’. The same refusal, read-first and approval rules apply.”

### F9 — Low — Locked annotations and semantic effects are conflated

**Files:** Server reference, fabric-local “destructive (10)”; `AGENTS.md:63`, which points agents to these kinds.

**Quote — Fabric README, Core Fabric Operations:** “Updates an existing item's display name or description”.

The captured destructive labels for `core_update-item`, `core_update-workspace` and `core_assign-workspace-to-capacity` may accurately reproduce conservative server annotations. Their documented effects are metadata/assignment updates, not destruction under this review’s definition. Annotations can be conservative and are not an operation-effect taxonomy.

**Suggested replacement:** Retain raw locked annotations unchanged, but distinguish “server-reported destructive hint” from reviewed semantic kind. Describe these three as writes; capacity assignment still remains independently forbidden by its protected-area flag.

### F10 — Low — The settings flag names the wrong administrative scope

**Files:** `AGENTS.md:106`; `toolchain\catalog.json`, fabric-local.flagged and fabric-core.flagged.

**Quote — Core tools reference, OneLake workspace settings:** “These tools operate on a workspace”.

The three hosted OneLake modification tools and local diagnostics/immutability tools change workspace settings, not tenant/capacity settings. Their prohibition is justified, but the area is inaccurate and omits the scope the source identifies.

**Suggested replacement:** Rename the shared area to “capacity, tenant or workspace settings (tier T3)”, or separate capacity assignment and workspace settings. Keep all existing settings tools prohibited.

## CHECKED AND FINE

**64 of 77 rows are S.** All 77 row quotes matched their assigned cited sources verbatim. Compared old/new AGENTS.md and its diff; generated tables were structurally valid. Reviewed files were unchanged.

Not checked: authenticated Fabric/Azure operations, locked-schema provenance, or other reviewers’ slices; no installs or sign-in performed.
