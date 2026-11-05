# Verification of the catalog of MCP servers, round 4: the reply of GPT 6.1 Sol

The reply as it came back, with the agent's own header removed. It read the files in the state of the review snapshot of round 4 (the paths in the reply are relative to it) and took: the 7 statements that round 3 changed, the diff of the fact list and the tests of its claims, and the closure of the round-3 findings of Gemini. The author's checks and the dispositions are in [mcp-catalog-findings.md](mcp-catalog-findings.md).

fabric-local:use | S | Documentation tools use bundled specifications | README supports offline documentation and live operations. Manifest confirms docs namespace, read-only and unrestricted full arguments; lock counts are 6/34/62. Profiles load full only in dev mode.
fabric-sql#2 | S | especially for write operations | Learn explicitly includes CREATE, ALTER, DROP, INSERT, UPDATE and DELETE and requires reviewing/approving execution. The catalog correctly distinguishes writes from reads.
powerbi-authoring-local#6 | S | to enable easy switching of the data source location. | README database_operations row confirms TMDL import/export and deployment; its parameter example supports exactly this purpose, not a claim that switching already occurred.
powerbi-authoring-local:tools | S | Control database transactions (begin, commit, rollback, get status) | All 22 names are present: 21 operation routers plus accept_eula. Transaction status supports mixed rather than write-only. No missing, invented or wrong-kind tool confirmed under the brief’s page-reading convention; no measured Power BI contract exists.
powerbi-authoring-local:flagged | S | after you explicitly authorize it | EULA note correctly separates README permission from stricter kit policy. Security-role and data-source restrictions have README evidence. Job exposure of accept_eula remains UNVERIFIED because every local Power BI lock capture was skipped.
powerbi-authoring-remote:use | S | Avoid registering both local and remote servers at the same time. | The revised recommendation matches Learn; it no longer turns advice into an absolute prohibition.
powerbi-authoring-remote:flagged | P | security roles, and more. | Security-role mutation is documented. UNVERIFIED: mutation/rebinding of an existing model data-source connection. Neither cited authoring/overview page, also refetched publicly, establishes it; an open-ended object list is insufficient. Keep the refusal as an explicitly conditional precaution. See F5.

G3-F1 | F | a tool is listed in two entries | scripts\toolchain_catalog.py:354,519–526: unknown server, absent tool, empty tool list, overlapping reviewed/flagged names and duplicate knowledge membership are rejected. Targeted existing tests passed; an additional reviewed-name-in-changes probe also failed correctly.
G3-F2 | P | ([a-z_]+_operations) | verification\tools\catalog_quotes.py:236: missing LISTS coverage, catalog-absent exceptions, overlong quotes and cross-page fragments are detected. However, adding a bold accept_eula row to a scratch README tools table still returns lists status 0 and page 21/catalog 21: the extractor ignores non-_operations names before the new exception check. Replace that extraction with all tool-name cells in Available tools, then apply exceptions.
G3-F3 | F | a change of a quota or a limit | toolchain\catalog.json:537 covers quota/limits, size/SKU/capacity and tenant/management-group/subscription settings through any namespace. The source quota row supports its example; AREA_WORDS includes quota and quotas in the settings area.
G3-F4 | F | omits kusto_show_command, which the lock has | toolchain\catalog.json:428 states the omission. README lists twelve nonoptional Eventhouse names plus the optional name; the lock contains kusto_show_command and 39 tools. The changed negative assertion rejects adding that name to the README.
G3-F5 | F | each one a namespace of commands or a single command. | Generated reference:200 and scripts\toolchain_catalog.py:685 now cover both forms. Regeneration exactly matches the committed reference; the lock still contains 70 Azure tools.

## FINDINGS

Paths below are relative to `CLONE4\new`. Source mutations were synthetic, in-memory probes against scratch copies; these are regression-guard defects, not assertions that today’s pages contain the reversed wording.

### F1 — Medium — Foundry capacity assertions are satisfied by examples, not tool inputs

- **File:** `scripts\facts.json:527–529`, `page-catalog-tools-foundry-mcp`.
- **Quote:** model deployment tools take capacity units or an instance count
- **Patterns:** `capacity\\s+units` and `\\binstanceCount\\b` are independent whole-page searches.
- **Reproduced:** Removed capacity-units inputs from both Azure deployment table rows and removed instanceCount from the Managed Compute input cell, leaving example prompts unchanged. Every pattern still passed. Thus the fact does not prove the tool/input relationships that `toolchain\catalog.json:1082` and its protected-capacity statement depend on. The alias phrase is likewise not bound to its tool row.
- **Suggested replacement:** Check each named deployment row’s Key inputs cell, bind the alias assertion to model_deploy, and require the expected capacity field for each applicable tool. Add the table-edit/example-retention mutation as a failing regression test.

### F2 — Low — EULA fact omits the affirmative permission it claims

- **File:** `scripts\facts.json:505–506`, `gh-pbi-authoring-accept-eula-tool`.
- **Quote:** an agent can call an accept_eula tool
- **Pattern:** ``(?s)(?=.*`accept_eula` tool on your behalf after you explicitly authorize it)`` checks the suffix but not the preceding permission/modal clause.
- **Reproduced:** Changed the README’s can-call wording to cannot-call wording. The complete regex still passed. Removing explicit authorization does fail, so the new condition is checked, but permission is not.
- **Suggested replacement:** Match the complete affirmative agent-can-call clause together with the explicit-authorization condition, and test its negation. Preserve the kit’s stricter operator-only policy.

### F3 — Low — Pipeline-definition fact does not establish an affirmative call

- **File:** `scripts\facts.json:541–543`, `page-datafactory-pipeline-flag`.
- **Quote:** mcp_datafactorymc_update_pipeline_definition.{0,20}with\\s+a\\s+JSON\\s+definition
- **Pattern:** The quoted expression, plus an independent Copy Activity/source search.
- **Reproduced:** Changed the example from Copilot calling update_pipeline_definition to Copilot never calling it with that JSON definition. All five patterns still passed. The source and tool fragments need not establish the asserted affirmative workflow.
- **Suggested replacement:** Bind the source activity and affirmative Copilot-calls clause to the same example, including the JSON-definition relationship. Retain the successful preview/flag and schedule-unavailability checks.

### F4 — Low — Knowledge coverage can be explicitly denied without drift

- **File:** `scripts\facts.json:544–546`, `gh-datafactory-mcp-readme-preview-and-dnx`.
- **Quote:** lists a knowledge file that covers Action.Sequence for writes
- **Pattern:** The whole-file lookahead ``(?=.*`Action\\.Sequence`\\s+for\\s+writes)`` checks topic occurrence.
- **Reproduced:** Prefixed the Advanced table cell with an explicit does-not-cover statement while retaining that topic phrase. The complete regex still passed. It checks topic occurrence, not affirmative coverage by a listed knowledge file.
- **Suggested replacement:** Verify the positive Advanced knowledge-file/topic association, with a negative coverage mutation test, rather than searching globally for the topic fragment. The existing preview, dnx and .NET assertions can remain.

### F5 — Low — Object-list occurrence is neither affirmative-capability proof nor connection evidence

- **Files:** `scripts\facts.json:568–570`, `page-pbi-authoring-remote-objects`; `toolchain\catalog.json:412`; generated reference:164.
- **Quote:** security\\s+roles,\\s+and\\s+more
- **Pattern:** The single unanchored expression starts with `Create,\\s+update,\\s+and\\s+delete\\s+tables` and ends with the quoted suffix.
- **Reproduced:** Replaced the affirmative authoring introduction with an unsupported-operations introduction while retaining the enumerated operations. The fact still passed.
- Separately, even its current successful match proves only the listed object types and an open-ended remainder, not modification of an existing data-source connection. The Direct Lake creation example does not establish that rebinding operation. The conservative refusal is safe; its claimed capability basis remains UNVERIFIED.
- **Suggested replacement:** Bind the object list to the affirmative authoring bullet. Keep the connections refusal, but explicitly identify it as conditional policy whose specific hosted capability was not established by the reviewed pages; do not use and more as proof.

## CHECKED AND FINE

- **10 positive rows:** six Task A S and four Task D F. G3-F2 is only partly closed.
- Seven targeted existing tests passed; baseline list comparison returned 0; generated reference exactly matched regeneration. All seven changed facts matched the supplied source text after removing Markdown code delimiters for page-pattern probes.
- Azure quota-row changes and RTI name/count changes correctly triggered drift. Foundry count changes and removal of the new evaluator-regeneration sentence also triggered drift.
- **Task B:** Documented Fabric role/settings/label flags and SQL permissions/RLS precautions were checked. No additional unflagged documented protected operation was confirmed. Fabric job docs/read contracts expose none of their never-called tools. Power BI’s possible accept_eula exposure is the existing disclosed, unmeasured exception, not newly verified safe.
- **Not checked:** Authenticated tools/list results, actual argument schemas, live write enforcement, EULA acceptance, or the real weekly fetch runner, which is not supplied. No installs, sign-in or live Fabric operations; no reviewed file was edited. Every evidence quote was checked verbatim and is at most twelve words.
