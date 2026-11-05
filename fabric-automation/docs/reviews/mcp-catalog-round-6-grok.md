# Verification of the catalog of MCP servers, round 6: the reply of Grok 4.7

The reply as it came back, with the agent's own header removed. It read the files in the state of the review snapshot of round 6 (the paths in the reply are relative to it) and took: the 2 statements that round 5 changed, the changed claims of the fact list and their tests (with mutations of live page text of its own), and the closure of the round-5 findings of GPT. The author's checks and the dispositions are in [mcp-catalog-findings.md](mcp-catalog-findings.md).

Task A

powerbi-authoring-remote:flagged | S | model translations, and security rules that would otherwise take hours | The authoring page lists security roles in the create/update/delete bullet and security rules in the bulk bullet, and it names no tool for either. The connection entry is still a precaution: that object list ends with "and more", and no cited page names a data-source tool. The cited pages do not name a schedule, label, credential, license, or capacity change. UNVERIFIED: the page lists no tools, so an unnamed tool is not visible here; the flags are changes, so they cover any tool.

fabric-rti-local:flagged | S | Replace the full JSON definition of an existing Map item | The live README also says map_create creates a map from a provided configuration, eventstream_update modifies settings and destinations, eventstream_create uses a custom configuration, and it lists eventstream_create_from_definition, with no connection argument. Evidence of build 0.6.2: map_create and map_update_definition take definition: dict[str, Any] and write map.json; eventstream_create, eventstream_update, and eventstream_create_from_definition send a definition; the builder tools only append to an in-memory session, endpoint_url is unused, and properties is {}. The kusto_command entries are decision-8 precautions and do not claim the pages list those commands. map_update only patches a display name and description. No other locked tool names a schedule, label, license, or secret. activator_create_trigger stays the prior reviewed exception; the README does not say it changes a protected setting.

Task D

P5-F1 | F | in a map that `map_create` or `map_update_definition` writes | catalog.json connections now names those two tools as a precaution. The README bullets match the parenthetical, and the pinned map_service.py writes a free-form definition. A Lakehouse data source in the README example is not called a connection.

P5-A1 | F | creates a map from a provided configuration | Same catalog sentence. The live README has that wording and names no connection argument. I did not find an unflagged map or eventstream write that can carry a connection outside this change and the eventstream definition change.

P5-F2 | F | because Managed Compute allocates billable dedicated GPU capacity | The four row patterns use a gap that stops at the next tool-name plus read or write. Moving permission mode onto the following row drifts. Removing capacity units or instanceCount from the row drifts even when an example still has them. The named verb negation is covered. A prefix negation is a new hole (F2).

P5-F3 | P | retention period that was active when they were deleted | Default-on, workspace-admin, and billing patterns are whole sentences and drift when those words change. The restore pattern is not a whole sentence: "You cannot restore..." and the same phrase moved into a note still pass (F1).

P5-F4 | F | see the supported formats before sharing one file | The pattern requires a period and then "See supported formats...". Changing that to Ignore drifts, and the live page has the sentence after the cross-agent sentence. The Claude-row test does not bind the name to the table (F4).

P5-F5 | F | that Copilot calls update_pipeline_definition with a JSON definition | The pattern now requires SalesBlob and SalesLakehouse immediately before that call. On the live page the call follows SalesLakehouse. Moving the call, or writing "never calls", drifts.

P5-F6 | F | Action.Sequence` for writes, Fast Copy, Modern Evaluator | The GitHub pattern requires that whole Advanced cell, ending at the pipe. The live README has that cell. The claim text still names only Action.Sequence for writes; the extra terms are on the page, so the stronger pattern still proves the claim.

P5-F7 | F | lists eventstream_create_from_definition in its validation bullet | The live README has the name on the Validation line. Moving it to the next line drifts. A "not" on that same line still passes (F3).

FINDINGS

F1 | Medium | scripts/facts.json line 105, page-onelake-soft-delete-billing | You can restore a soft-deleted file | The restore pattern starts at "restore", so it is not the whole sentence the fix claimed. "You cannot restore a soft-deleted file during the retention period that was active when the file was deleted" still passes, and so does the phrase moved into a note after the real sentence is changed. The new tests only replace the phrase, so they do not prove the assertion. Replace the pattern with `You\s+can\s+restore\s+a\s+soft-deleted\s+file\s+during\s+the\s+retention\s+period\s+that\s+was\s+active\s+when\s+the\s+file\s+was\s+deleted`, and add a cannot-restore case.

F2 | Low | scripts/facts.json line 527, page-catalog-tools-foundry-mcp | for review because Managed Compute allocates | The billing pattern is only the because-clause. "not because Managed Compute allocates billable dedicated GPU capacity" still passes, and dropping "Before any deployment" and "for review" still passes, so the pattern does not prove the claim's review clause or a positive assertion. Bind it to `for review because Managed Compute allocates billable dedicated GPU capacity` and reject a leading not.

F3 | Low | scripts/facts.json line 648, gh-rti-mcp-eventstream-definition-tools | lists eventstream_create_from_definition in its validation bullet | Replacing the name on the Validation line with "not `eventstream_create_from_definition`" still passes. Require the exact list `` `eventstream_validate_definition`, `eventstream_create_from_definition`, `eventstream_list_available_components` ``.

F4 | Low | scripts/facts.json line 314, page-vscode-custom-instructions-agents-md | lists CLAUDE.md for Anthropic Claude | The pattern is only "Anthropic Claude CLAUDE.md". Changing the table cell and leaving that phrase in a note still passes, so the new test does not prove the harness row. Bind it to `Anthropic\s+Claude\s+CLAUDE\.md\s+OpenAI\s+Codex`.

CHECKED AND FINE

9 rows are S or F (both Task A rows; P5-F1, P5-A1, P5-F2, P5-F4, P5-F5, P5-F6, P5-F7). P5-F3 is P.

The two design sentences in docs/04-design.md both say the retention period the workspace had when the data was deleted. The live soft-delete page says "the retention period that was active when the file was deleted", a seven-day default per workspace, that workspace admins configure file-level soft delete or turn it off, and that soft-deleted data is billed at the active rate. Those clauses agree. "After a permanent item delete" is not on that page, so that trigger is UNVERIFIED, not a contradiction I could show.

Also checked and fine: the Foundry row patterns, the Data Factory blob and schedule patterns, the map bullet patterns, the authoring security-rules sentence, and the deployment-pattern date 2026-11-02. The Foundry URL redirects on the same host to /azure/foundry/mcp/available-tools; the patterns still match. A map bullet copied verbatim into an example can still satisfy the map claim; a prose example cannot, because the pattern requires the bullet markup.

Not checked: the other 22 servers; the catalog-code slice; whole-catalog contradictions; K5 closures; the t10 grounding sentences; Kusto command docs beyond decision 8; the local Power BI modeling README, which the remote server does not cite.
