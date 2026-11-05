# Verification of the catalog of MCP servers, round 5: the reply of GPT 6.1 Sol

The reply as it came back, with the agent's own header removed. It read the files in the state of the review snapshot of round 5 (the paths in the reply are relative to it) and took: the 4 statements that round 4 changed, the diff of the fact list and the tests of its claims, and the closure of the round-4 findings of Gemini. The author's checks and the dispositions are in [mcp-catalog-findings.md](mcp-catalog-findings.md).

## Task A

azure-mcp:flagged | S | Update VMSS 'my-vmss' capacity to 5 instances | The revised capacity examples are supported. The other documented protected operations are covered by change statements, including credential-returning reads. Confirmed 70 tools and the read-only switch against the lock and manifest; no job profile loads this server.
datafactory-local#5 | S | Pipeline deletion and schedule modification aren't available through the MCP server | This sentence is on the pipelines page. That page also documents schedule creation; the README lists set_pipeline_schedule_enabled. The revised wording distinguishes creation from the disagreement about modification.
fabric-rti-local:flagged | T | add LakeHouse with name 'MyLakeHouse' as a data source | The Eventstream precaution is repaired, but Map data-source changes remain outside the connection statements. map_create accepts configuration and map_update_definition replaces the complete definition. See F1. Confirmed both tools against the 39-tool lock.
powerbi-authoring-remote:flagged | S | partitions, security roles, and more. | Security roles are explicitly documented. The connection restriction is now clearly a precaution, not a claim that the pages document rebinding. No additional protected operation was established from the cited pages.

## Task D

G4-F1 | F | active = (words & SECRET_WORDS) | Tested generic-word precedence, secret-bearing read names and plural policies. modify_tier flagged only under license is rejected; get_connection_token requires credentials rather than connections; policies belongs to both settings areas.
G4-F2 | F | elif name not in unflagged_tools(server, lock, reviewed=()): | Tested redundant exceptions for an already-correctly-flagged tool and a harmless read name. Both are rejected. An exception is not incorrectly declared redundant merely because its tool has a wrong-area flag.
G4-F3 | F | left = (sets - covered) if None in sets | Tested unread named and unnamed sets, an unscoped list covering entirely named sets, and set-aside tools across sets. Unexpected appearance or disappearance is rejected. Baseline lists also exits successfully.

## FINDINGS

The fact-checker counterexamples below were reproduced using mutated copies of current live responses. All nine unmodified responses pass their current checks.

### F1 — Medium — Map source bindings remain unflagged

**File:** `toolchain\catalog.json:466–473`, `fabric-rti-local.flagged`, connections; generated reference line 184.

**Quote:** `a connection, or the binding of one, in an eventstream`

The connection precautions cover Kusto commands and Eventstreams, but not Maps. The cited README explicitly demonstrates adding a Lakehouse as a Map data source, documents configuration-based `map_create`, and documents full-definition replacement through `map_update_definition`.

This leaves the same definition-carried binding gap that the Eventstream change addressed. The catalog should identify the protected change, rather than leave it among ordinary Map writes.

**Suggested replacement:** Add a separate, explicitly precautionary connection-change statement covering connections or bindings in Map configurations or definitions written through `map_create` and `map_update_definition`. Ordinary Map edits need not be prohibited wholesale.

### F2 — Medium — Foundry checks still accept cross-row evidence and reversed billing

**Files:** `scripts\facts.json:528–529`, `page-catalog-tools-foundry-mcp`; `scripts\test_verify_facts.py:907–941`.

**Quote:** `in the table row of the tool concerned`

Two counterexamples remain:

- Removing permission mode from the `session_file_mkdir` row and inserting it into the following `session_file_upload` row still produces **PASS**. The 200-character wildcard crosses the flattened row boundary.
- Reversing the Managed Compute example from allocating billable GPU capacity to **not allocating** it still produces **PASS**. The pattern checks only the billing noun phrase, not the allocation assertion.

The existing permission mutation places the surviving decoy far away. It therefore demonstrates distance sensitivity, not row isolation.

**Suggested replacement:** Evaluate tool-specific assertions within individual HTML table rows before flattening their contents. Bind the GPU assertion to the positive Managed Compute allocation sentence in its example. Add adjacent-row relocation and negative-allocation mutations, both requiring DRIFT.

### F3 — Medium — OneLake patterns omit the revised retention conditions

**File:** `scripts\facts.json:103–106`, `page-onelake-soft-delete-billing`.

**Quote:** `the retention period that was active when they were deleted`

The live page supports this condition, but none of the three patterns checks it. Each of these changes independently remains **PASS**:

1. Replacing deletion-time retention with the workspace’s currently configured retention.
2. Replacing workspace admins with any workspace member.
3. Changing soft delete to off by default while retaining a sentence mentioning an optional seven-day period.

The patterns establish billing wording, mention of seven-day retention and configuration capability—not the complete claim. `ClaimPrecisionTests` has no corresponding condition-reversal tests.

**Suggested replacement:** Check the complete default-retention statement, the workspace-admin configuration statement and the deletion-time retention statement. Add mutations for each lost condition.

### F4 — Low — VS Code’s supported-formats instruction can be reversed undetected

**File:** `scripts\facts.json:314–316`, `page-vscode-custom-instructions-agents-md`.

**Quote:** `see the supported formats before sharing one file across harnesses`

The final pattern checks only the temporal phrase about sharing. Changing the live page’s instruction from seeing supported formats to **ignoring** supported formats still produces **PASS**.

The cross-agent assertion and current Claude table entry are present; the defect concerns the claimed instruction.

**Suggested replacement:** Match the affirmative instruction to consult supported formats before sharing, rather than its trailing phrase alone. Add an instruction-reversal mutation.

### F5 — Low — DataFactory’s Blob example can borrow another example’s call

**Files:** `scripts\facts.json:541–543`; `scripts\test_verify_facts.py:948–955`.

**Quote:** `in one example`

The 240-character wildcard is proximity, not example containment.

I changed the Blob example’s response to refuse that activity, followed immediately by a separate local-file example containing the definition-tool call. The claim still produces **PASS**, associating the Blob prompt with the other example’s response.

The existing direct call-negation test correctly detects its narrower mutation.

**Suggested replacement:** Isolate the relevant example’s prompt and response using preserved document structure. Add a mutation moving the call into a neighbouring, unrelated example.

### F6 — Low — Advanced-topic negation after the topic passes

**Files:** `scripts\facts.json:544–546`; `scripts\test_verify_facts.py:961–963`.

**Quote:** `Action.Sequence for writes`

The strengthened pattern checks the beginning of the Advanced topics cell. Rewriting that cell to say the named writes topic is **NOT covered**, followed by the remaining topics, still produces **PASS**.

The new test catches negation before the topic, but not after it.

**Suggested replacement:** Match the complete positive Advanced topics cell, not merely its prefix. Test negation both before and after the writes topic.

### F7 — Low — Eventstream builder name is not bound to its tool list

**Files:** `scripts\facts.json:648–650`; `scripts\test_verify_facts.py:977–982`.

**Quote:** `and lists eventstream_create_from_definition`

The third lookahead accepts the tool name anywhere in the README.

Removing it from the Validation list produces DRIFT, as intended. Adding only an unsupported-tool mention elsewhere restores **PASS**. Consequently, the existing removal test does not establish list membership.

The create and update description controls correctly reject their tested capability changes.

**Suggested replacement:** Bind `eventstream_create_from_definition` to the Validation tool-list bullet. Add a removal mutation retaining an unsupported mention outside that list.

## CHECKED AND FINE

- **Task A:** 3 S, 1 T. **Task D:** 3 F.
- All **27 `ClaimPrecisionTests` passed**. The helper rejects no-op mutations; the weaknesses are missing adversarial cases, not unnoticed unchanged samples.
- All **nine changed claims** pass against freshly fetched public sources. Baseline catalog structure, manifest/lock checks and tool-list comparisons pass.
- The EULA authorization, Power BI authoring-bullet and Azure capacity-example changes passed their positive checks and meaningful live-response negative controls.
- The live OneLake and VS Code pages support the revised factual descriptions. The supplied design sentence agrees on default retention, administrator configuration and billing.
- **UNVERIFIED:** The actual `docs\04-design.md` and `docs\research\raw\t10-toolchain-grounding.md` are absent from `CLONE5\new`; I could not inspect their complete paragraphs or confirm the permanent-item-delete linkage from the soft-delete page alone. Undocumented runtime argument schemas were not verified.
- No installs, sign-in or live MCP operations. All 14 report evidence quotes were verified verbatim and contain at most 12 words.
