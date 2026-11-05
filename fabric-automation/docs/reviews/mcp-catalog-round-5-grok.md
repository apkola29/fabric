# Verification of the catalog of MCP servers, round 5: the reply of Grok 4.7

The reply as it came back, with the agent's own header removed. It read the files in the state of the review snapshot of round 5 (the paths in the reply are relative to it) and took: the 4 statements that round 4 changed, the changed instruction text (rule 6 and its three copies) and the catalog, and the closure of the round-4 findings of GPT. The author's checks and the dispositions are in [mcp-catalog-findings.md](mcp-catalog-findings.md).

## Task A

azure-mcp:flagged | S | Update VMSS 'my-vmss' capacity to 5 instances | Each example is on a cited page: VMSS capacity and SQL performance tier, disk SKU and file-share size on the README; `role`, `policy`, `quota`, `appservice`, `sreagent`, `keyvault` and `azurebackup` on the tools page; firewall rules, private-endpoint approval, backup schedule and SRE scheduled task on the README. "If true, no write operations are allowed" supports the read-only clause. "Connection strings and passwords" supports credentials. Broader "through any namespace" wording is a precaution for a namespace server (decision 4), not an extra page claim. No cited page names a label, a license, or an RLS or OLS command that this statement leaves unflagged. The lock lists namespaces, not commands, so command-level completeness of the locked build is UNVERIFIED.

datafactory-local#5 | S | Pipeline deletion and schedule modification aren't available through the MCP server. | The same Learn page says Copilot calls `mcp_datafactorymc_create_pipeline_schedule` with a recurrence definition. The README lists `set_pipeline_schedule_enabled` and does not say modification is unavailable. The disagreement is correctly limited to modifying a schedule. Creation is not denied.

fabric-rti-local:flagged | P | Create new Eventstreams with custom configuration | The `kusto_command` clauses are precautions: the README says that tool runs `.show`, `.create`, `.alter` and `.drop`, not those policies (decision 8). The new connections clause overclaims. The README says `eventstream_update` modifies settings and destinations, `eventstream_create` creates an eventstream with a custom configuration, and it only lists `eventstream_create_from_definition` under Validation. It does not say all three create or modify an eventstream and its destinations. Decision 9 (builder tools take no connection argument) is UNVERIFIED: no build 0.6.2 source is in this set.

powerbi-authoring-remote:flagged | T | and security rules that would otherwise take hours | The security-role clause and the connections precaution match the authoring page: the object list includes security roles and ends with "and more", and no cited page names a data-source tool. The same shared bullet says the server changes security rules. The remote never-made text names only a security role. The local entry treats a row-level security permission as separate. A security-rule change can still be made without matching the remote flag. No cited page names a label, license, schedule, credential or capacity tool for this server.

## Task D

P4-F1 | F | Model name, deployment name, capacity units | `facts.json` binds capacity units, `instanceCount`, alias wording, regeneration, permission mode and replace wording to table-row patterns. `ClaimPrecisionTests` removes each from its row while the sample still has those phrases in examples, and expects the claim to stop passing.

P4-F2 | F | an agent can call an accept_eula tool | The claim regex in `facts.json` starts at `your\s+agent\s+can\s+call\s+the`, and the test turns that into "your agent cannot call".

P4-F3 | F | Copilot never calls mcp_datafactorymc_create_pipeline_schedule | One pattern holds the Blob Storage copy activity and the `update_pipeline_definition` call; another holds the `create_pipeline_schedule` call with a recurrence definition. The tests change each call to "never calls".

P4-F4 | F | Does not cover `Action.Sequence` for writes | The regex requires the Advanced row of the knowledge table, and the test prefixes that row with "Does not cover".

P4-F5 | F | Author models in natural language. | The claim pattern starts at that sentence, and the test replaces it and also drops "and more".

P4-A1 | F | kept as a precaution: no page names a tool for it | `catalog.json` and the generated reference both say the data-source flag is a precaution and that no page names a tool. The object list on the authoring page does end with "and more".

P4-D1 | F | every bold lower-case cell | `names_on` for `operations` matches a bold lower-case first cell and no longer requires `_operations`. I did not re-run the writer's scratch README check, so the claimed "DIFF twice, exit 1" is UNVERIFIED.

## FINDINGS

F1. Medium. `mcp-servers.md`, heading `powerbi-authoring-remote`, never-made row-level or object-level security. Quote: "and security rules that would otherwise take hours". The remote flag names only a security role. Suggested replacement: "a change of a security role or of a security rule, which the page lists and for which it names no tool".

F2. Low. `catalog.json`, `fabric-rti-local` connections changes. Quote: "create or modify an eventstream and its destinations". That citation is stronger than the README. Suggested replacement: "a precaution: the README says eventstream_update modifies settings and destinations, eventstream_create creates an eventstream with a custom configuration, and it lists eventstream_create_from_definition; it names no connection argument".

F3. Low. `AGENTS.md` rule 6 and `mcp-servers.md` header. Quote: "changes only a file on the machine". A session can follow every rule at once. A Fabric item is live state of a tenant, so the four phrases cover it by MCP, CLI or REST. A local-file-only tool is covered by profile access, not by that approval. No phrase covers a GitHub commit, push or pull request, or a `create_record` write through `sql-mcp-server` to a customer-hosted database that is neither a tenant nor Azure. Router step 5.6 points every write tool at rule 6, whose trigger is only a tenant or Azure. Suggested replacement: "Before a change of a Git repository, of GitHub, or of a customer-hosted database that is not a tenant and not Azure, say the route, the identity and the change, and wait. A local file stays within the profile. A Fabric item is live state of a tenant."

F4. Low. `factory-preamble.md`, "How to work", and `AGENTS.md` rule 8. Quote: "A job (started by a runner, with no person)". The preamble applies to every job and requires a person to approve a tenant or Azure change. A job can follow that only by not making the change. That matches "a job makes no change through an MCP tool" and "no live CLI or REST". The README says agent and executor writes are typed executor operations and does not say those operations never change a tenant. If one does, the job cannot follow every rule at once. Suggested replacement: "A job makes no change of the live state of a tenant or of Azure, including by a typed executor operation. It does not wait for a person."

## CHECKED AND FINE

Two Task A rows are S and all seven Task D rows are F. The four copies of "Before anything that changes the live state of a tenant or of Azure" match, and no file still says "changes a tenant". Flagged changes and needs sentences in the catalog match the generated reference. Tool totals for the four servers match their lists. I did not re-fetch live pages, did not re-run `lists` on a scratch README, and could not confirm decision 9 from source.
