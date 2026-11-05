# MCP servers and their tools

This file is generated from `toolchain/catalog.json`, the lock and the manifest by `python scripts/toolchain.py instructions --write`. Do not edit it.
A person read the pages named below on 2026-11-04. A change of the catalog is checked against them by a model family other than the one that wrote it (rule 9 of AGENTS.md).
The weekly fact check shows a page that changed as drift, and a person refreshes the catalog in a reviewed pull request.

How to use it:

- A server that the lock measured (a stdio server that was launched and listed its tools) has a contract: a tool of it that is missing, renamed or changed against the lock is a contract drift. Stop and report it.
- Any other server has no measured contract, and its entry here is a person's reading of its pages. Where the entry lists tools, compare the names that the server lists with them (names only, not schemas): a tool that the work needs and the server does not list, or a tool that it lists and this file does not, is a difference to report to the person before you go on. Where the entry lists no tools, tell the person what the server listed before you call one.
- The kinds. Where a person listed the tools from the pages: `read` only reads, `write` creates or changes, `destructive` deletes, removes or replaces, and `mixed` is one tool that reads and also writes or deletes, where the operation or the statement that a call names decides which. Where the lock measured the tools: the annotations that the server reported (read-only; destructive, the protocol's hint that a tool may perform destructive updates; or neither). They are the server's own words and no review of what each tool does.
- A call that changes the live state of a tenant or of Azure needs the approval that the rules ask for in a session (rule 6 of AGENTS.md; rule 2 of "How to work" in the preamble), and a job makes no change through an MCP tool. A tool that changes only a file on the machine works within the access of its profile.
- "Never called" lists the tools that no agent calls. "Never made" lists the changes that no agent makes through any tool that can run them (a statement, a call with a protected argument), in a session or in a job.

| Server | Group | Runs | Stage |
|---|---|---|---|
| `microsoft-learn` | pinned | remote | not stated on the pages that were read |
| `fabric-local` | pinned | local | public preview |
| `fabric-core` | pinned | remote | not stated on the pages that were read |
| `fabric-iq` | pinned | remote | generally available |
| `fabric-sql` | pinned | remote | preview |
| `powerbi-authoring-local` | pinned | local | generally available |
| `powerbi-authoring-remote` | pinned | remote | preview |
| `fabric-rti-local` | pinned | local | public preview |
| `azure-mcp` | pinned | local | beta |
| `bicep-mcp` | pinned | local | preview |
| `azure-arm-cost` | pinned | remote | preview |
| `eventhouse-remote` | listed | remote | preview |
| `activator-remote` | listed | remote | preview |
| `operations-agent-remote` | listed | remote | preview |
| `data-agent-remote` | listed | remote | not stated on the pages that were read |
| `ontology-remote` | listed | remote | preview |
| `datafactory-local` | listed | local | not stated on the pages that were read |
| `notebook-integration-local` | listed | local | not stated on the pages that were read |
| `onelake-hosted` | also | remote | public preview |
| `powerbi-consumption-remote` | also | remote | preview |
| `graph-enterprise` | also | remote | public preview |
| `foundry-mcp` | also | remote | public preview |
| `graphql-sample` | related | local | not stated on the pages that were read |
| `sql-mcp-server` | related | customer | not stated on the pages that were read |

## `microsoft-learn`: Microsoft Learn MCP Server

- Group: pinned in the manifest. Runs: remote, one URL. Stage: not stated on the pages that were read.
- Sign-in: none.
- Needs and limits:
  - No sign-in is needed.
  - It holds publicly available documentation, not training or user profile information.
  - Its index refreshes incrementally after content updates and fully once a day.
  - The pages say that it is publicly available and free of charge, and state no release stage for it.
- Read from: `training/support/mcp` (updated 2026-05-22); `github.com/MicrosoftDocs/mcp`.
- Tools (3, from the pages):
  - read (3): `microsoft_docs_search`, `microsoft_docs_fetch`, `microsoft_code_sample_search`
- Knowledge: `microsoft_docs_search`, `microsoft_docs_fetch`, `microsoft_code_sample_search`: search the current Microsoft documentation, read a page as markdown, find official code samples.

## `fabric-local`: Fabric MCP Server (local)

- Group: pinned in the manifest. Runs: local, started by a command. Stage: public preview.
- Sign-in: `docs` none; `read` Azure identity; `full` Azure identity.
- Needs and limits:
  - It runs on the development machine; the install methods are a VS Code extension, npm with npx, or a build from source.
  - Live operations sign in with the Azure CLI (az login) for a user, or with service-principal variables for a process; the page sends Data Factory authentication to the Data Factory tools reference.
  - Its Learn tool reference lists only some of the tools and says that names and availability vary by installed version and server configuration, so the list of this kit is the one measured in the lock.
  - The README on the main branch also documents core_get-item-definition, core_update-item-definition and a jobs namespace (jobs_run-on-demand-item-job and four more tools) that the locked version does not expose.
  - The README of the microsoft/mcp repository lists it as Microsoft Fabric (Public Preview); the Learn pages and its own README state no stage.
- Read from: `rest/api/fabric/articles/mcp-servers/pro-dev-local/overview-local-mcp-server` (updated 2026-09-23); `rest/api/fabric/articles/mcp-servers/pro-dev-local/get-started-local` (updated 2026-09-23); `rest/api/fabric/articles/mcp-servers/pro-dev-local/tools-local-mcp-server` (updated 2026-09-23); `github.com/microsoft/mcp/blob/main/servers/Fabric.Mcp.Server/README.md`; `github.com/microsoft/mcp`; `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools: the lock's contract `fabric-local/full`, measured at 1.6.0 on 2026-10-31 (variants: `docs` 6; `full` 62; `read` 34).
  - annotated read-only (34): `core_get-capacity`, `core_get-item`, `core_get-operation-result`, `core_get-operation-state`, `core_get-workspace`, `core_list-capacities`, `core_list-items`, `core_list-workspaces`, `core_search-catalog`, `datafactory_execute-query`, `datafactory_get-pipeline`, `datafactory_list-dataflows`, `datafactory_list-pipelines`, `docs_api-examples`, `docs_best-practices`, `docs_item-api-spec`, `docs_item-definitions`, `docs_list-item-types`, `docs_platform-api-spec`, `onelake_download-file`, `onelake_get-data-access-role`, `onelake_get-settings`, `onelake_get-shortcut`, `onelake_get-table`, `onelake_get-table-config`, `onelake_get-table-namespace`, `onelake_list-data-access-roles`, `onelake_list-files`, `onelake_list-items`, `onelake_list-items-dfs`, `onelake_list-shortcuts`, `onelake_list-table-namespaces`, `onelake_list-tables`, `onelake_list-workspaces`
  - annotated neither read-only nor destructive (18): `core_create-item`, `core_create-workspace`, `datafactory_create-dataflow`, `datafactory_create-pipeline`, `datafactory_run-pipeline`, `onelake_create-directory`, `onelake_create-or-update-data-access-role`, `onelake_create-shortcut-adls-gen2`, `onelake_create-shortcut-amazon-s3`, `onelake_create-shortcut-azure-blob`, `onelake_create-shortcut-dataverse`, `onelake_create-shortcut-gcs`, `onelake_create-shortcut-onedrive-sharepoint`, `onelake_create-shortcut-onelake`, `onelake_create-shortcut-s3-compatible`, `onelake_modify-diagnostics`, `onelake_modify-immutability-policy`, `onelake_reset-shortcut-cache`
  - annotated destructive (10): `core_assign-workspace-to-capacity`, `core_delete-item`, `core_delete-workspace`, `core_update-item`, `core_update-workspace`, `onelake_delete-data-access-role`, `onelake_delete-directory`, `onelake_delete-file`, `onelake_delete-shortcut`, `onelake_upload-file`
- Knowledge: `docs_list-item-types`, `docs_item-api-spec`, `docs_platform-api-spec`, `docs_item-definitions`, `docs_best-practices`, `docs_api-examples`: Fabric API specifications, item definitions, best practices and request examples, offline in the `docs` variant.
- Never called, row-level or object-level security (tier T3): `onelake_create-or-update-data-access-role`, `onelake_delete-data-access-role`.
- Never called, capacity, tenant or workspace settings (tier T3): `core_assign-workspace-to-capacity`, `onelake_modify-diagnostics`, `onelake_modify-immutability-policy`.
- Never made, through any tool, capacity, tenant or workspace settings (tier T3): a `core_create-workspace` call that assigns a capacity or a domain.
- Never made, through any tool, sensitivity labels (tier T3): a `core_create-item` call that carries label settings.

## `fabric-core`: Fabric Core MCP Server

- Group: pinned in the manifest. Runs: remote, one URL. Stage: not stated on the pages that were read.
- Sign-in: Entra.
- Needs and limits:
  - Sign-in is OAuth 2.0 with Microsoft Entra, as the signed-in user: each tool maps to a Fabric REST API operation, so that user's permissions decide what works.
  - Creating a workspace needs the permission to create workspaces, which some organizations restrict.
  - Deleting a workspace permanently removes its items and cannot be undone, and a folder must be empty before it is deleted.
  - Without the Microsoft Graph MCP server, a role operation needs user principal IDs and not e-mail addresses.
  - The pages state no release stage for it.
  - The OneLake tools of this server take the workspace id, and the item-scoped ones the item id, as parameters.
- Read from: `rest/api/fabric/articles/mcp-servers/core-remote/overview-core-mcp-server` (updated 2026-10-27); `rest/api/fabric/articles/mcp-servers/core-remote/get-started-core` (updated 2026-09-29); `rest/api/fabric/articles/mcp-servers/core-remote/tools-core-mcp-server` (updated 2026-10-27); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (43, from the pages):
  - read (18): `search_catalog`, `list_workspaces`, `get_workspace`, `list_workspace_roles`, `get_workspace_role`, `list_items`, `get_item`, `get_item_definition`, `list_folders`, `get_folder`, `list_capacities`, `get_operation_state`, `get_operation_result`, `get_knowledge`, `onelake_list_shortcuts`, `onelake_get_shortcut`, `onelake_list_data_access_roles`, `onelake_get_settings`
  - write (15): `create_workspace`, `update_workspace`, `add_workspace_role`, `update_workspace_role`, `create_item`, `update_item`, `update_item_definition`, `bulk_move_items`, `create_folder`, `update_folder`, `move_folder`, `onelake_create_or_update_single_data_access_role`, `onelake_modify_default_tier`, `onelake_modify_diagnostics`, `onelake_modify_immutability_policy`
  - destructive (10): `delete_workspace`, `delete_workspace_role`, `delete_item`, `delete_folder`, `onelake_delete_shortcut`, `onelake_delete_data_access_role`, `onelake_create_or_update_data_access_roles`, `onelake_create_shortcut`, `onelake_create_shortcuts_in_bulk`, `onelake_reset_shortcut_cache`
- Knowledge: `get_knowledge`: guidelines and best practices for item types.
- Never called, permissions (tier T3): `add_workspace_role`, `update_workspace_role`, `delete_workspace_role`.
- Never called, row-level or object-level security (tier T3): `onelake_create_or_update_single_data_access_role`, `onelake_create_or_update_data_access_roles`, `onelake_delete_data_access_role`.
- Never called, capacity, tenant or workspace settings (tier T3): `onelake_modify_default_tier`, `onelake_modify_diagnostics`, `onelake_modify_immutability_policy`.

## `fabric-iq`: Fabric IQ MCP server

- Group: pinned in the manifest. Runs: remote, one URL. Stage: generally available.
- Sign-in: Entra.
- Needs and limits:
  - Sign-in is delegated OAuth with the scopes Item.Read.All and Item.Execute.All; a service principal is not supported.
  - It is read-only, and the Power BI tenant setting for the Model Context Protocol server endpoints does not apply to it.
  - It is not available in Power BI-only regions or in sovereign clouds.
  - It does not cover dashboards, paginated reports, apps, ontologies or data agents, and it has no tool that answers a natural-language question: the agent writes the query from the schema.
  - ExecuteQuery returns up to 250 rows unless maxRows asks for more.
  - The header X-Variants with the value Fabric.Routing.FabricIQ.V1 pins the tool contract.
  - The Power BI MCP servers overview spells the path of its URL with capitals and the connector page in lower case; the manifest follows the connector page.
  - With private links, the endpoint on the Fabric API host is used instead of the Fabric IQ host.
- Read from: `fabric/iq/connectors/fabric-iq-mcp` (updated 2026-10-21); `power-bi/developer/mcp/mcp-servers-overview` (updated 2026-09-29); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (6, from the pages):
  - read (6): `DiscoverArtifacts`, `ResolveFabricItem`, `GetReportMetadata`, `GetSemanticModelSchema`, `ValueSearch`, `ExecuteQuery`

## `fabric-sql`: Fabric Data Warehouse MCP server

- Group: pinned in the manifest. Runs: remote, one URL, or one URL per item. Stage: preview.
- Sign-in: Entra.
- Needs and limits:
  - A person signs in with Microsoft credentials, and the statements run with that person's Fabric and SQL permissions.
  - Its one tool can run DDL and DML, so a call that changes data or schema is a change of a tenant and needs the approval that the rules ask for.
  - The Learn page names the tool executeSQL and the marketplace file of the skills repository names it execute_query: call the name that the server lists.
  - There is a global endpoint and an item-scoped endpoint that names a workspace and an item.
- Read from: `fabric/data-warehouse/data-warehouse-mcp-server` (updated 2026-06-23); `github.com/microsoft/skills-for-fabric/blob/v0.3.20/.github/plugin/marketplace.json`; `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (1, from the pages):
  - mixed (1): `executeSQL`
- Never made, through any tool, permissions (tier T3): a statement that changes permissions.
- Never made, through any tool, row-level or object-level security (tier T3): a statement that changes row-level security.

## `powerbi-authoring-local`: Power BI Authoring MCP server (local)

- Group: pinned in the manifest. Runs: local, started by a command. Stage: generally available.
- Sign-in: `offline-readonly` none; `service-readonly` Azure identity; `interactive` Entra.
- Needs and limits:
  - It is generally available; the hosted twin is in preview.
  - It needs Write permission on the semantic model to change it: with only Build permission it can only run DAX queries.
  - For a model in a Fabric workspace, the XMLA endpoint must be set to Read Write on the capacity.
  - The --readonly switch prevents any write operations to the semantic model (the README's words), and the README does not say whether it covers anything else: the license acceptance is saved in a local configuration. Without it, the server asks for a confirmation before an edit, once per database.
  - It blocks every other tool call until its license (EULA) is accepted: the operator accepts it once, on purpose, and the server saves the acceptance in a local configuration.
  - The README says that database_operations can import and export TMDL folders and deploy to Fabric, and its examples change the data source of a model through Power Query parameters.
  - The variable PBI_MODELING_MCP_ALLOWED_CONNECTION_HOSTS adds hosts that the server connects to and sends access tokens to; the kit does not set it.
  - No tenant setting blocks it: only disabling the XMLA endpoint does, and that blocks every tool that uses XMLA.
- Read from: `power-bi/developer/mcp/power-bi-authoring-mcp` (updated 2026-09-29); `github.com/microsoft/powerbi-modeling-mcp`; `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (22, from the pages):
  - read (3): `connection_operations`, `dax_query_operations`, `trace_operations`
  - write (2): `accept_eula`, `transaction_operations`
  - mixed (17): `database_operations`, `model_operations`, `table_operations`, `column_operations`, `relationship_operations`, `measure_operations`, `partition_operations`, `user_hierarchy_operations`, `calculation_group_operations`, `security_role_operations`, `perspective_operations`, `named_expression_operations`, `function_operations`, `culture_operations`, `object_translation_operations`, `calendar_operations`, `query_group_operations`
- Never called, license (never accepted for anyone): `accept_eula` (the operator accepts the license, never the agent).
- Never made, through any tool, row-level or object-level security (tier T3): a change of a security role or of a row-level security permission through `security_role_operations`.
- Never made, through any tool, connections (tier T3): a change of the data source of a model, for example a Power Query parameter that `named_expression_operations` updates.

## `powerbi-authoring-remote`: Power BI Authoring MCP server (hosted)

- Group: pinned in the manifest. Runs: remote, one URL. Stage: preview.
- Sign-in: Entra.
- Needs and limits:
  - It is in preview, uses Streamable HTTP and signs in with Microsoft Entra as the signed-in user.
  - A Fabric administrator must enable the tenant setting Users can use the Power BI Model Context Protocol server endpoint.
  - It has no transactions, no Analysis Services traces, no access to a model open in Power BI Desktop and no access to PBIP or TMDL files on disk.
  - Registering the local and the hosted server together gives the agent two overlapping tool sets: pick one.
- Read from: `power-bi/developer/mcp/power-bi-authoring-mcp` (updated 2026-09-29); `power-bi/developer/mcp/mcp-servers-overview` (updated 2026-09-29); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools: The page lists no tools: it says that the server exposes tools grouped by object type, such as tables, columns, measures and relationships, and that the agent can be asked what is available.
- Never made, through any tool, row-level or object-level security (tier T3): a change of a security role, which the page lists among the objects that the server changes and for which it names no tool.
- Never made, through any tool, connections (tier T3): a change of the data source of a model, for example of a partition, which the page lists among the objects that the server changes.

## `fabric-rti-local`: Real-Time Intelligence MCP server (local)

- Group: pinned in the manifest. Runs: local, started by a command. Stage: public preview.
- Sign-in: Azure identity.
- Needs and limits:
  - It is in public preview, and its README says that the implementation may change significantly before general availability.
  - Started by a command (stdio mode, as the kit does), it signs in with the default Azure credential chain; by default in HTTP mode a request needs a bearer token and no credentials of the local process are used, unless FABRIC_RTI_HTTP_ALLOW_MI (a managed identity) or FABRIC_RTI_HTTP_DEBUG_MODE (local process credentials) is enabled.
  - Its README counts 13 tools for Eventhouse and one more that is optional (kusto_get_shots, when KUSTO_SHOTS_TABLE is configured), 17 for Eventstreams, 2 for Activator and 7 for Map; the lock lists 39.
- Read from: `fabric/real-time-intelligence/mcp-local-server` (updated 2026-06-22); `github.com/microsoft/fabric-rti-mcp`; `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools: the lock's contract `fabric-rti-local/default`, measured at 0.6.2 on 2026-10-31 (variants: `default` 39).
  - annotated read-only (21): `activator_list_artifacts`, `eventstream_get`, `eventstream_get_current_definition`, `eventstream_get_definition`, `eventstream_list`, `eventstream_list_available_components`, `eventstream_validate_definition`, `kusto_deeplink_from_query`, `kusto_describe_database`, `kusto_describe_database_entity`, `kusto_diagnostics`, `kusto_graph_query`, `kusto_known_services`, `kusto_list_entities`, `kusto_query`, `kusto_sample_entity`, `kusto_show_command`, `kusto_show_queryplan`, `map_get`, `map_get_definition`, `map_list`
  - annotated neither read-only nor destructive (7): `eventstream_add_custom_endpoint_destination`, `eventstream_add_custom_endpoint_source`, `eventstream_add_derived_stream`, `eventstream_add_eventhouse_destination`, `eventstream_add_sample_data_source`, `eventstream_start_definition`, `kusto_ingest_inline_into_table`
  - annotated destructive (11): `activator_create_trigger`, `eventstream_clear_definition`, `eventstream_create`, `eventstream_create_from_definition`, `eventstream_delete`, `eventstream_update`, `kusto_command`, `map_create`, `map_delete`, `map_update`, `map_update_definition`
- Never made, through any tool, permissions (tier T3): a management command of `kusto_command` that changes who may access a cluster, a database, a table or a function.
- Never made, through any tool, row-level or object-level security (tier T3): a management command of `kusto_command` that changes a row-level security policy.
- Never made, through any tool, security settings (tier T3): a management command of `kusto_command` that changes another security policy of a database or a table.
- Never made, through any tool, capacity, tenant or workspace settings (tier T3): a management command of `kusto_command` that changes a policy of a cluster, for example its capacity.
- Never made, through any tool, connections (tier T3): a management command of `kusto_command` that creates or changes a connection to another source, for example an external table.
- Never made, through any tool, credentials (rule 2): a management command of `kusto_command` that carries a secret, a key or a connection string with a secret.

## `azure-mcp`: Azure MCP Server

- Group: pinned in the manifest. Runs: local, started by a command. Stage: beta.
- Sign-in: `read` Azure identity; `full` Azure identity.
- Needs and limits:
  - Its tools are disabled by default in supported hosts, and the Azure RBAC permissions of the signed-in identity decide which work.
  - Sign-in is Microsoft Entra ID through the Azure Identity library.
  - The kit starts the read variant with the server's read-only switch, which allows no write operation; the lock lists the namespace tools of that variant.
  - The server asks for confirmation before a high-risk command, such as returning a Key Vault secret; the option that turns that off is not recommended, and the kit does not set it.
  - The stage here is that of the pinned build, a pre-release: the README on the main branch announces version 2.0 as generally available, and the Learn pages state no stage.
  - Its Learn tools page lists namespaces that the locked build does not have (azuremigrate, communication and resilience), and the lock has namespaces that the page does not list (arm, azd, containerapps, deviceprovisioning, documentation, foundryextensions, functions, iotoperations, netappfiles and resiliency).
  - The page names some tools by a namespace where the lock has tools with a suffix (extension, group and subscription against extension_cli_generate, extension_cli_install, group_list, group_resource_list and subscription_list), and writes get_azure_bestpractices as get azure bestpractices get: the list of this kit is the lock's.
- Read from: `azure/developer/azure-mcp-server/overview` (updated 2026-10-16); `azure/developer/azure-mcp-server/tools/` (updated 2026-10-16); `github.com/microsoft/mcp/tree/main/servers/Azure.Mcp.Server`.
- Tools: the lock's contract `azure-mcp/read`, measured at 4.0.0-beta.4 on 2026-10-31 (variants: `read` 70).
  - 70 tools, each one a namespace of commands. The kit starts this variant with the server's read-only switch, so none of its commands writes; the server's own annotations of a namespace tool do not say which of its commands write, so no kinds are listed.
  - `acr`, `adme`, `advisor`, `aks`, `appconfig`, `applens`, `applicationinsights`, `appservice`, `arm`, `azd`, `azurebackup`, `azureterraform`, `azureterraformbestpractices`, `bicepschema`, `cloudarchitect`, `compute`, `confidentialledger`, `containerapps`, `cosmos`, `datadog`, `deploy`, `deviceprovisioning`, `deviceregistry`, `documentation`, `eventgrid`, `eventhubs`, `extension_cli_generate`, `extension_cli_install`, `fileshares`, `foundry`, `foundryextensions`, `functionapp`, `functions`, `get_azure_bestpractices`, `grafana`, `group_list`, `group_resource_list`, `insights`, `iothub`, `iotoperations`, `keyvault`, `kusto`, `loadtesting`, `managedlustre`, `marketplace`, `monitor`, `mysql`, `netappfiles`, `optimization`, `policy`, `postgres`, `pricing`, `quota`, `redis`, `resiliency`, `resourcehealth`, `role`, `search`, `servicebus`, `servicefabric`, `signalr`, `speech`, `sql`, `sreagent`, `storage`, `storagesync`, `subscription_list`, `virtualdesktop`, `wellarchitectedframework`, `workbooks`
- Knowledge: `get_azure_bestpractices`, `azureterraformbestpractices`, `cloudarchitect`, `wellarchitectedframework`: Azure best practices, Terraform best practices, guided cloud architecture design, and architecture guidance by Well-Architected pillar.
- Never made, through any tool, credentials (rule 2): a call of any namespace that returns or takes the value of a secret, a key, a password, a connection string or a certificate, for example a `keyvault` secret or the application settings of an App Service web app (`appservice`): the read-only switch does not stop a read.
- Never made, through any tool, permissions (tier T3): a change of a role assignment (`role`), or of who may access a resource, through any namespace.
- Never made, through any tool, security settings (tier T3): a change of an Azure Policy assignment, definition or initiative (`policy`), of a firewall rule, of the approval of a private endpoint connection or of a security setting of a backup, through any namespace.
- Never made, through any tool, connections (tier T3): a change of a connection of a resource, for example the database connection of an App Service web app (`appservice`) or a connector of an SRE agent (`sreagent`).
- Never made, through any tool, schedules (tier T3): a change of a schedule, for example the schedule of a backup policy (`azurebackup`) or a scheduled task of an SRE agent (`sreagent`).

## `bicep-mcp`: Bicep MCP server

- Group: pinned in the manifest. Runs: local, started by a command. Stage: preview.
- Sign-in: none.
- Needs and limits:
  - The tools page says that its tools give context for writing Bicep and are not designed to deploy directly to Azure.
  - It uses stdio transport, launched locally by a client process, and is provided by the Azure.Bicep.McpServer NuGet tool.
  - The tools page names it Bicep (PREVIEW) in the tool picker of GitHub Copilot Chat, and states no other stage.
  - The tools page on the main branch lists get_bicep_file_diagnostics, which the locked contract does not have, and omits build_bicep and build_bicepparam, which the locked contract has.
  - Its catalog of resource type schemas is bundled with Bicep and not queried live from Azure: a selected version does not guarantee availability in a particular cloud, region or subscription.
- Read from: `github.com/Azure/bicep/blob/main/docs/mcp-tools.md`; `azure/azure-resource-manager/bicep/visual-studio-code` (updated 2026-06-02).
- Tools: the lock's contract `bicep-mcp/default`, measured at 0.48.1 on 2026-11-01 (variants: `default` 14).
  - annotated read-only (14): `build_bicep`, `build_bicepparam`, `decompile_arm_parameters_file`, `decompile_arm_template_file`, `format_bicep_file`, `get_azure_resource_type_schema`, `get_bicep_best_practices`, `get_deployment_snapshot`, `get_extension_resource_type_schema`, `get_file_references`, `list_avm_metadata`, `list_azure_resource_types`, `list_extension_resource_types`, `list_well_known_extensions`
- Knowledge: `get_bicep_best_practices`: Bicep best practices.

## `azure-arm-cost`: Azure Resource Manager MCP server

- Group: pinned in the manifest. Runs: remote, one URL. Stage: preview.
- Sign-in: Entra.
- Needs and limits:
  - Its README calls it a preview, and says that it can only be used with a set of MCP clients: GitHub Copilot Chat in VS Code and GitHub Copilot CLI.
  - The README says to sign in with Azure credentials, that every call is made on behalf of the signed-in user with that user's permissions, and does not name the method.
  - Its default tools include template deployments and creating or updating resources and resource groups, besides Azure Resource Graph queries, resource type schemas and cost and pricing queries.
  - The README names an Azure Policy that denies the requests of its deployment tool, create_deployment, as the way to block deployments.
  - The Cost Management toolset is optional, and a client turns it on with the header x-mcp-toolset set to CostManagement; it adds nine tools, one of which creates a budget. The kit sets that header, so those nine tools are on.
- Read from: `github.com/Azure/Azure-Resource-Manager-MCP`; `github.com/Azure/Azure-Resource-Manager-MCP/blob/main/docs/CostManagementAndPricingTools.md`.
- Tools (26, from the pages):
  - read (12): `list_resource_types`, `get_resource_type_schema`, `generate_query`, `validate_query`, `execute_query`, `get_deployment_status`, `get_async_operation_status`, `whatif_deployment`, `query_costs`, `query_aks_costs`, `get_retail_prices`, `get_pricesheet_status`
  - write (5): `create_deployment`, `cancel_deployment`, `create_or_update_resource`, `create_or_update_resource_group`, `start_pricesheet_download`
  - optional Cost Management toolset:
    - read (8): `forecast_costs`, `list_dimensions`, `list_budgets`, `get_budget`, `list_alerts`, `list_benefit_utilization`, `get_benefit_recommendations`, `list_reservation_transactions`
    - write (1): `create_budget`
- Never called, credentials (rule 2): `get_pricesheet_status` (it returns a time-limited SAS download URL).
- Never made, through any tool, credentials (rule 2): a payload of `create_deployment` or `create_or_update_resource` that carries a secret, a key or a password.
- Never made, through any tool, permissions (tier T3): a change of a role assignment through `create_deployment` or `create_or_update_resource`.
- Never made, through any tool, security settings (tier T3): a change of a policy assignment, a network security rule or another security resource through `create_deployment` or `create_or_update_resource`.
- Never made, through any tool, connections (tier T3): a change of a connection of a resource to another through `create_deployment` or `create_or_update_resource`.
- Never made, through any tool, schedules (tier T3): a change of a schedule or a trigger of a resource through `create_deployment` or `create_or_update_resource`.
- Never made, through any tool, capacity, tenant or workspace settings (tier T3): a change of a capacity, or of a setting of a tenant, a management group or a subscription, through `create_deployment` or `create_or_update_resource`.

## `eventhouse-remote`: Eventhouse MCP server

- Group: listed by Fabric, not pinned. Runs: remote, one URL, or one URL per item. Stage: preview.
- Needs and limits:
  - It is in preview.
  - The page names no tools.
- Read from: `fabric/real-time-intelligence/mcp-remote-eventhouse` (updated 2026-10-23); `fabric/real-time-intelligence/mcp-overview` (updated 2026-10-23); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools: The page names no tools.

## `activator-remote`: Activator MCP server

- Group: listed by Fabric, not pinned. Runs: remote, one URL per item. Stage: preview.
- Needs and limits:
  - It is in preview.
  - A rule can have a KQL source only, and an e-mail or a Teams action only.
- Read from: `fabric/real-time-intelligence/mcp-remote-activator` (updated 2026-10-23); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (4, from the pages):
  - read (1): `list_rules`
  - write (3): `create_rule`, `start_rule`, `stop_rule`

## `operations-agent-remote`: Operations agent MCP server

- Group: listed by Fabric, not pinned. Runs: remote, two URLs per item. Stage: preview.
- Needs and limits:
  - It is in preview, and only manual configuration is supported.
  - Using it needs Contributor or Admin access to the workspace that has the operations agent.
- Read from: `fabric/real-time-intelligence/mcp-remote-operations-agent` (updated 2026-10-23); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (21, from the pages):
  - configure URL:
    - read (7): `get_agent_instructions`, `get_agent_knowledge_sources`, `get_agent_actions`, `get_playbook_summary`, `get_playbook_rules`, `get_rule_details`, `get_generate_playbook_status`
    - write (7): `set_agent_instructions`, `add_or_update_eventhouse_knowledge_source`, `add_or_update_fabric_ontology_knowledge_source`, `add_or_update_agent_action`, `generate_playbook`, `start_agent`, `stop_agent`
    - destructive (2): `remove_knowledge_source`, `remove_agent_action`
  - query URL:
    - read (5): `get_agent_summary`, `get_agent_state`, `get_monitored_rules`, `get_operation_details`, `query_operations`

## `data-agent-remote`: Fabric data agent as an MCP server

- Group: listed by Fabric, not pinned. Runs: remote, one URL per item. Stage: not stated on the pages that were read.
- Needs and limits:
  - Only a published data agent is an MCP server, and it exposes a single tool that stands for the agent: its description is the description of the data agent.
  - A request carries a Fabric bearer token of a user or of a service principal.
  - The server does not support dynamic client registration, and it supports MCP tasks for a long-running question.
  - The page states no release stage for it.
- Read from: `fabric/data-science/data-agent-mcp-server` (updated 2026-09-04); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools: One tool that stands for the published data agent.

## `ontology-remote`: Ontology MCP server

- Group: listed by Fabric, not pinned. Runs: remote, one URL per item. Stage: preview.
- Needs and limits:
  - It is in preview, and because of a known issue a service principal cannot use it.
  - The page names no tools.
- Read from: `fabric/iq/ontology/how-to-use-ontology-mcp-server` (updated 2026-10-01); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools: The page names no tools.

## `datafactory-local`: DataFactory MCP server

- Group: listed by Fabric, not pinned. Runs: local, started by a command. Stage: not stated on the pages that were read.
- Needs and limits:
  - It is a .NET 10 tool that starts with dnx; the README marks some tools as preview and the pipelines page calls pipeline management a preview feature, and no page states a release stage for the server as a whole.
  - Some of its tools sign in or out, or return an access token; the kit leaves sign-in to the person or the runner (rule 2), so no agent calls them.
  - The pipeline tools are a preview feature, and they appear only with the --pipeline flag.
  - The guide to connection management also names a tool, create_connection_ui, that opens a form for a new connection and is not in the list of the README.
- Read from: `github.com/microsoft/DataFactory.MCP`; `github.com/microsoft/DataFactory.MCP/blob/main/docs/connection-management.md`; `fabric/data-factory/pipelines-manage-vs-code` (updated 2026-06-11); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (52, from the pages):
  - read (26): `get_authentication_status`, `get_access_token`, `list_gateways`, `get_gateway`, `list_supported_connection_types`, `list_connections`, `get_connection`, `list_workspaces`, `list_dataflows`, `get_dataflow_definition`, `refresh_dataflow_status`, `execute_query`, `list_capacities`, `list_pipelines`, `get_pipeline`, `get_pipeline_definition`, `get_pipeline_run_status`, `list_pipeline_schedules`, `list_copy_jobs`, `get_copy_job`, `get_copy_job_definition`, `get_copy_job_run_status`, `list_copy_job_schedules`, `list_airflow_jobs`, `get_airflow_job`, `get_airflow_job_definition`
  - write (25): `authenticate_interactive`, `authenticate_service_principal`, `sign_out`, `create_virtualnetwork_gateway`, `create_connection`, `create_connection_ui`, `create_dataflow`, `add_connection_to_dataflow`, `add_or_update_query_in_dataflow`, `save_dataflow_definition`, `refresh_dataflow_background`, `create_pipeline`, `update_pipeline`, `update_pipeline_definition`, `run_pipeline`, `create_pipeline_schedule`, `set_pipeline_schedule_enabled`, `create_copy_job`, `update_copy_job`, `update_copy_job_definition`, `run_copy_job`, `create_copy_job_schedule`, `create_airflow_job`, `update_airflow_job`, `update_airflow_job_definition`
  - destructive (1): `delete_airflow_job`
- Never called, credentials (rule 2): `get_access_token`, `authenticate_interactive`, `authenticate_service_principal`, `sign_out`.
- Never called, connections (tier T3): `create_connection`, `create_connection_ui`, `create_virtualnetwork_gateway`, `add_connection_to_dataflow`.
- Never called, schedules (tier T3): `create_pipeline_schedule`, `set_pipeline_schedule_enabled`, `create_copy_job_schedule`.

## `notebook-integration-local`: Fabric Data Engineering notebook integration

- Group: listed by Fabric, not pinned. Runs: local, inside an extension of VS Code. Stage: not stated on the pages that were read.
- Needs and limits:
  - It is a feature of the Fabric Data Engineering VS Code extension: the Claude Code or Codex extension uses the local MCP server of it to read the notebook language, target, document revision, workspace and runtime context, and attached-resource metadata.
  - It needs the Fabric Data Engineering extension and the Claude Code or the Codex extension, signed in; the page states no release stage for it.
- Read from: `fabric/data-engineering/claudecode-codex-with-vs-code` (updated 2026-09-23); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools: The page names no tools.

## `onelake-hosted`: Hosted OneLake MCP server

- Group: published by Microsoft outside the directory. Runs: remote, one URL per item. Stage: public preview.
- Needs and limits:
  - It is in public preview, and its token audience is the storage audience and not the Fabric one.
  - It is not in the directory of Fabric MCP servers.
- Read from: `fabric/onelake/onelake-hosted-mcp` (updated 2026-10-23); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (15, from the pages):
  - read (11): `onelake_list_files`, `onelake_blob_list`, `onelake_list_items_data`, `onelake_read_file`, `onelake_download_file`, `onelake_get_principal_access`, `onelake_list_namespaces`, `onelake_get_namespace`, `onelake_get_table_config`, `onelake_get_download_instructions`, `onelake_get_upload_instructions`
  - destructive (4): `onelake_create_directory`, `onelake_delete_directory`, `onelake_delete_file`, `onelake_blob_delete`

## `powerbi-consumption-remote`: Power BI Consumption MCP server

- Group: published by Microsoft outside the directory. Runs: remote, one URL. Stage: preview.
- Needs and limits:
  - It is in preview, and a Power BI administrator must enable the tenant setting Users can use the Power BI Model Context Protocol server endpoint (preview).
  - Row-level security applies to user authentication; Power BI does not enforce it for a service principal, which can then access all the data that it is authorized to access.
- Read from: `power-bi/developer/mcp/remote-mcp-server-get-started` (updated 2026-09-17); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (4, from the pages):
  - read (4): `Execute Query`, `Get Semantic Model Schema`, `Get Report Metadata`, `Generate Query`

## `graph-enterprise`: Microsoft MCP Server for Enterprise

- Group: published by Microsoft outside the directory. Runs: remote, one URL. Stage: public preview.
- Needs and limits:
  - It is in public preview and must be enabled in the tenant: an Application Administrator or a Cloud Application Administrator consents to the permissions.
- Read from: `graph/mcp-server/get-started` (updated 2026-07-04); `graph/mcp-server/overview` (updated 2026-07-04); `rest/api/fabric/articles/mcp-servers/core-remote/tools-core-mcp-server` (updated 2026-10-27); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (3, from the pages):
  - read (3): `microsoft_graph_suggest_queries`, `microsoft_graph_get`, `microsoft_graph_list_properties`

## `foundry-mcp`: Foundry MCP Server

- Group: published by Microsoft outside the directory. Runs: remote, one URL. Stage: public preview.
- Needs and limits:
  - It is in public preview, without a service-level agreement.
  - Every operation runs with the signed-in user's permissions through the Microsoft Entra On-Behalf-Of flow.
  - Its page lists 79 tools in 17 categories and marks 35 as read and 44 as write; 13 of the 44 delete or replace something and are listed here as destructive.
  - Its model deployment tools allocate billable capacity (capacity units, or dedicated GPU instances for Managed Compute), and each is a write that needs approval.
- Read from: `azure/ai-foundry/mcp/get-started` (updated 2026-09-10); `azure/ai-foundry/mcp/available-tools` (updated 2026-08-19); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (79, from the pages):
  - read (35): `agent_get`, `agent_container_status_get`, `agent_definition_schema_get`, `session_get`, `session_list`, `session_logstream`, `session_file_list`, `session_file_stat`, `session_file_download`, `toolbox_get`, `toolbox_version_get`, `evaluation_dataset_get`, `evaluation_dataset_versions_get`, `evaluation_dataset_sas_url_get`, `data_generation_job_get`, `evaluation_get`, `evaluation_comparison_get`, `evaluation_suite_get`, `evaluation_suite_generation_job_get`, `evaluator_catalog_get`, `evaluator_generation_job_get`, `model_catalog_list`, `model_details_get`, `model_deployment_get`, `model_benchmark_get`, `model_benchmark_subset_get`, `model_similar_models_get`, `model_switch_recommendations_get`, `model_monitoring_metrics_get`, `model_deprecation_info_get`, `model_quota_list`, `project_connection_list`, `project_connection_get`, `project_connection_list_metadata`, `continuous_eval_get`
  - write (31): `agent_update`, `agent_invoke`, `agent_container_control`, `session_create`, `session_file_mkdir`, `session_file_upload`, `toolbox_version_create`, `toolbox_update`, `evaluation_dataset_create`, `data_generation_job_create`, `data_generation_job_cancel`, `evaluation_agent_batch_eval_create`, `evaluation_dataset_batch_eval_create`, `evaluation_comparison_create`, `evaluation_agent_traces_batch_eval_create`, `evaluation_traces_batch_eval_create`, `evaluation_suite_create`, `evaluation_suite_update`, `evaluation_suite_run`, `evaluation_suite_generation_job_create`, `evaluation_suite_generation_job_cancel`, `evaluator_catalog_create`, `evaluator_catalog_update`, `evaluator_generation_job_create`, `evaluator_generation_job_cancel`, `model_deploy_azure_direct_model`, `model_deploy`, `model_deploy_managed_compute`, `project_connection_update`, `prompt_optimize`, `continuous_eval_create`
  - destructive (13): `agent_delete`, `session_delete`, `session_file_delete`, `toolbox_delete`, `toolbox_version_delete`, `data_generation_job_delete`, `evaluation_suite_delete`, `evaluation_suite_generation_job_delete`, `evaluator_catalog_delete`, `model_deployment_delete`, `project_connection_create`, `project_connection_delete`, `continuous_eval_delete`
- Never called, connections (tier T3): `project_connection_create`, `project_connection_update`, `project_connection_delete`.
- Never called, schedules (tier T3): `continuous_eval_create`, `continuous_eval_delete`.
- Never called, credentials (rule 2): `evaluation_dataset_sas_url_get`.
- Never made, through any tool, permissions (tier T3): a `session_file_mkdir` call that sets a permission mode.

## `graphql-sample`: Fabric API for GraphQL sample MCP server

- Group: related to Fabric. Runs: local, started by a command and reached at a local address. Stage: not stated on the pages that were read.
- Needs and limits:
  - It is a Node.js sample that the page starts from the fabric-samples repository, and it listens on a local address.
  - Introspection is disabled by default and only a workspace administrator can enable it; the sample needs it.
- Read from: `fabric/data-engineering/api-graphql-local-model-context-protocol` (updated 2026-09-29); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (2, from the pages):
  - read (1): `introspect-schema`
  - mixed (1): `query-graphql`

## `sql-mcp-server`: SQL MCP Server

- Group: related to Fabric. Runs: hosted by the customer. Stage: not stated on the pages that were read.
- Needs and limits:
  - It is part of Data API builder from version 1.7 and is hosted by the customer, over streamable HTTP or stdio.
  - The page lists aggregate_records for version 2.0 and later and not for 1.7.x, and says that in 2.0 a stored procedure can be registered as a named tool (custom-tool), which this list does not hold.
  - It is designed for data and not for schema; execute_entity runs a stored procedure, and the pages do not limit what the procedure does.
- Read from: `azure/data-api-builder/mcp/overview` (updated 2026-05-15); `azure/data-api-builder/mcp/data-manipulation-language-tools` (updated 2026-06-22); `rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list` (updated 2026-10-21).
- Tools (7, from the pages):
  - read (3): `describe_entities`, `read_records`, `aggregate_records`
  - write (2): `create_record`, `update_record`
  - destructive (1): `delete_record`
  - mixed (1): `execute_entity`
- Never made, through any tool, permissions (tier T3): a call of `execute_entity`, or of a custom tool, that runs a stored procedure which changes permissions or row-level security.
- Never made, through any tool, credentials (rule 2): a call of `execute_entity`, or of a custom tool, that runs a stored procedure which returns a secret, a key or a password.
