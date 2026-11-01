# Third look at the instruction layer, slice B: the catalogue, the commands, the tests by mutation and the changed code (Grok 4.7)

The reply as it came back, with the agent's own header removed. The author's check of each finding, and what was changed, is in [instruction-layer-third-look-findings.md](instruction-layer-third-look-findings.md).

The closure fixes hold for the original reproductions. Two gaps remain: a false claim about the cost server, and tests that still miss contradictions next to the sentences they guard.

## 1. Closure findings

| ID | Decision | Evidence |
|---|---|---|
| B2-1 | FIXED | Replay of the duplicate `full` cell was killed by `test_the_servers_table_lists_every_server_once_with_the_sign_in_of_each_of_its_variants`. `sign_in()` no longer folds a repeated variant. The preamble test derives `entra-delegated` names from the manifest. |
| B2-2 | FIXED | Replay that dropped `--live` from the first preflight was killed. The freshness string is required in `AGENTS.md`, the preamble, the router and the README. Validator commands are parsed, not scanned in `--help`. |
| B2-3 | FIXED | Replay that deleted the agent/executor CLI sentence was killed. The routing test holds the essential task, skill, server and mode phrase for each row in `ROUTES`. |
| B2-4 | FIXED | The standards test holds the non-authorization sentences and `Do not turn a [flag] into a change.` A mutation that replaces that sentence with automatic implementation fails that test. |
| B2-5 | FIXED | Replays that marked the operations agent local, and that deleted the `/query` watch, were killed. Documentation addresses are an exact dict against the manifest. |
| B2-6 | FIXED | Replay of `notes=notes[:1]` on the summary call was killed by `test_every_note_reaches_the_console_and_the_summary`. |
| B2-7 | FIXED | On the scratch copy, a summary left from a clean check was removed when the lock was replaced with invalid JSON: exit 1, file absent, error `toolchain.lock.json: not valid JSON`. `--bogus-flag` exited 2 and left the file byte-identical. A directory path raises `cannot replace the summary file: Access is denied`. |
| B2-8 | FIXED | `test_the_summary_says_why_the_exit_code_is_three_when_only_the_manifest_changed` requires the manifest-edited line in the summary. `AGENTS.md` line 22 and `toolchain/README.md` line 116 define exit 3 as a candidate lock that differs, not as "something is newer". |
| B2-9 | FIXED | The same README sentence, the preamble and design 3.13 say the check reads metadata and launches no server. `cmd_update` calls `build_lock` without launching a server unless `--contracts`. A live run printed no capture lines. |

The author's ratings of these nine were fair. His "not done" on B-11 is wrong for `azure-arm-cost`: that summary is not a harmless abbreviation. It states a restriction the upstream page contradicts (B3-1).

## 2. New findings

### B3-1 — High: the cost server is not limited to cost queries

**Where:** `AGENTS.md`, line 48; `toolchain/toolchain.json`, lines 322–324; `.github/mcp.json` (the `azure-arm-cost` entry).

**What is wrong:** The catalogue says use `azure-arm-cost` for "Azure cost queries". The manifest says `x-mcp-toolset: CostManagement` "only selects the cost toolset". The rendered project config sends that header and `"tools": ["*"]`. `dev-azure` and `dev-factory` load this server. The header does not hide the rest of the server.

**Evidence:** [Cost Management and Pricing tools](https://github.com/Azure/Azure-Resource-Manager-MCP/blob/main/docs/CostManagementAndPricingTools.md): "A core set of these tools is enabled by default" (`query_costs` and four others); the rest, including `create_budget`, "are opt-in via the `CostManagement` toolset"; "To also enable the optional Cost Management tools … add the `x-mcp-toolset: CostManagement` header". [The server README](https://github.com/Azure/Azure-Resource-Manager-MCP): it "equips agents with tools to query Azure resources, deploy and manage ARM templates, create or update resources". The lock contract `azure-arm-cost/default` is `needs-sign-in` with no tool list, so the kit has not measured this.

**Fix:** Say the header adds optional cost tools, including a write, and does not remove deploy tools. Do not render `tools: ["*"]` until a captured contract lists only the intended tools. Until then, tell the agent this connection can change Azure resources, and those calls need the approval rule.

### B3-2 — Medium: exit-code sentences and the sign-in legend are not held

**Where:** `AGENTS.md`, lines 22 and 34; `toolchain/README.md`, lines 11 and 116; `scripts/test_toolchain.py`, the freshness and preflight tests.

**What is wrong:** The tests require the freshness command string, and `--live` on `verify` in `AGENTS.md` and the router. They do not hold what those exits mean, the sign-in legend, or `--live` on the README's own verify step.

**Evidence:** On a scratch copy, these mutations left all 69 tests passing: `AGENTS.md` line 22 changed to "Exit 1 or 2: nothing is newer, so carry on."; the README's "Exit 3 means that the candidate lock differs" changed to "Exit 3 means nothing is newer and the run may switch to it."; "Azure identity is not interactive" changed to "Azure identity opens a browser window."; README step 5 `verify --live` changed to `verify`.

**Fix:** Hold the exit sentences in `AGENTS.md` and the README, the legend that Azure identity is not a browser sign-in, and `--live` on the README verify step.

### B3-3 — Medium: the mode boundary is only an opening phrase

**Where:** `toolchain/instructions/factory-preamble.md`, line 31; `toolchain/skills/factory-router/SKILL.md`, lines 28 and 31; `AGENTS.md`, the `fabric-local` row.

**What is wrong:** The boundary test searches for "In the agent and executor modes no live CLI or REST step runs". The routing test searches for "dev mode only". Either sentence can be cancelled and still pass.

**Evidence:** All 69 tests passed after replacing "Report that the step needs a dev-mode session or an executor operation, and stop it." with "Carry on with the live CLI step."; after appending "or executor mode if asked" to the `fabric-sql` cell and "or any mode" to the Fabric IQ cell; and after changing "`full`: changes, dev only" to "`full`: changes, any job".

**Fix:** Hold the stop sentence, and reject a mode phrase that grants executor, agent or "any job" on a row the table marks dev-only.

### B3-4 — Medium: a standards prohibition can be undone in the next sentence

**Where:** `toolchain/skills/factory-standards/SKILL.md`, lines 26 and 51.

**What is wrong:** The tests require the escalate sentence and "Do not turn a `[flag]` into a change." They do not require that the next sentence leave those rules standing.

**Evidence:** All 69 tests passed after appending "If the lakehouse is ordinary, build it and leave the protection for later." to the escalate sentence, and after appending "A `[flag]` may be implemented when the requirement names it."

**Fix:** Fail the skill text if a later sentence tells the agent to build without the flagged protection, or to implement a `[flag]`.

### B3-5 — Medium: the operations-agent watch matches a substring, not the URL

**Where:** `scripts/facts.json`, line 336; `scripts/test_toolchain.py`, `test_the_two_urls_of_an_operations_agent_are_watched_on_its_page`.

**What is wrong:** The test only checks that some pattern contains `/configure` and some pattern contains `/query`. A pattern that cannot match the live URL still passes.

**Evidence:** Changing `"/operationsAgents/[^/]+/query"` to `"/operationsAgents/[^/]+/query-disabled"` left all 69 tests passing. The live page gives `https://api.fabric.microsoft.com/v1/mcp/workspaces/<Workspace ID>/operationsAgents/<Item ID>/query` ([operations agent MCP](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/mcp-remote-operations-agent)). The current pattern is right; the test would not notice a broken one. Deleting the pattern is killed, which is why B2-5 is still fixed.

**Fix:** Require the pattern to match a sample of the published URL, and reject a pattern that also matches a different suffix.

### B3-6 — Medium: a failed check is only proved to delete a clean summary

**Where:** `scripts/toolchain.py`, lines 2936–2943; `scripts/test_toolchain.py`, line 7631.

**What is wrong:** The removal test writes a summary that says "No upstream change.", then fails the resolver. A removal that keeps every other summary still passes. An exit 3 summary would then survive a later exit 1, which is the stale evidence B2-7 closed.

**Evidence:** This `clear_summary` still passed all 28 `UpdateTests`: if the path is a file and its text does not contain "No upstream change", return without deleting; otherwise unlink. The directory case still raises, so the directory test does not catch it.

**Fix:** Fail the check once with a summary that says the manifest was edited, and assert that file is gone.

### B3-7 — Medium: the manifest-edited line is not tested when a note is present

**Where:** `scripts/toolchain.py`, line 2077; `scripts/test_toolchain.py`, line 7650.

**What is wrong:** The exit 3 test and the formatter test use no resolution notes. The live check has a note, so the case a person will actually read is untested.

**Evidence:** Changing `if manifest_edited:` to `if manifest_edited and not notes:` left all 69 tests passing. A live run of the documented command exited 0 and wrote one note, `kept the locked version of nuget:Azure.Bicep.McpServer: it could not be resolved now`, in both the console and the summary (LF, no CR). An exit 3 on this tree would usually carry that note. If the reason line were then omitted, the summary would say only that part of the check did not run.

**Fix:** One command test with a manifest edit and an unresolved package, asserting both the reason line and the note.

### B3-8 — Low: "carry the summary in every case" fights the exit 2 rule

**Where:** `toolchain/README.md`, line 116.

**What is wrong:** The paragraph says the summary counts only after exit 0 or 3, then says that in every case the run carries the summary. Exit 2 never reaches `clear_summary`, so the previous file is still there to be carried.

**Evidence:** `python scripts/toolchain.py update --bogus-flag --summary-file <path>` exited 2 with `unrecognized arguments: --bogus-flag`. The file was byte-identical, including `No upstream change.`

**Fix:** Say that after exit 1 or 2 the run carries the error line, not the summary file.

## 3. CHECKED AND FINE

- The [directory](https://learn.microsoft.com/en-us/rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list) (updated 2026-10-21) still lists 14 servers. All 14 are in the two tables. The GraphQL sample and the customer-hosted SQL MCP server are named. I found no directory entry that is in neither table.
- Sign-in cells match the manifest variants (`none`, `azure-identity`, `entra-delegated`). Fabric IQ is read-only and "Service-principal and application-only authentication aren't supported" ([Fabric IQ MCP](https://learn.microsoft.com/en-us/fabric/iq/connectors/fabric-iq-mcp)). The pinned URL is the page's primary endpoint.
- Live `update --check --fail-on-update --summary-file .factory/update-summary.md` exited 0 in under a minute, needed the network, and did not need a local skill store. The summary matched the console, including the partial-check sentence. It is LF.
- `verify --live` on this copy exited 1 (`V9`, no managed-skills marker) until `install --apply`. `verify` without `--live` exited 0. `install` without `--apply` printed a plan and fetched nothing. `doctor --offline` exited 0. I did not run `doctor` without `--offline`: that command calls `az account show`, `gh auth status` and hosted probes.
- `render --host load-plan --profile agent-implementer` exited 1 because `powerbi-authoring-local/offline-readonly` has no captured contract. The same README paragraph says an agent plan is refused in that case. `agent-planner` rendered and exited 0.
- A missing parent directory is created by `write_atomic`, and the file is LF. A read-only summary on Windows is not deleted (`Access is denied`, exit 1, file kept). That is safe. Linux would unlink a read-only file if the directory is writable. Actual Linux execution is UNVERIFIED. The 69 tests passed on a copy normalized to LF, and on the CRLF snapshot.
- `--summary-file` without `--check` is accepted and does not write the lock. Exit 3 still requires `--fail-on-update`. The documented command includes both flags.
- `python scripts/validate_docs.py --strict` exited 0 (0 errors). It reported 158 CRLF files and that Git stores LF. No instruction command uses a backslash path. `sync_to_github.ps1` is labeled Windows PowerShell, and `python3` is the documented substitute.
