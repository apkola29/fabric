# Fourth look at the instruction layer, slice B: the fixes of its own findings and mutations of its own (Grok 4.7)

The reply as it came back, with the agent's own header and the message that asked for it removed. The author's check of each point, and what was changed, is in [instruction-layer-third-look-findings.md](instruction-layer-third-look-findings.md).

The original B3 reproductions are killed on CLONE2. The new pins still miss a following clause that keeps their required words.

## B3-1 to B3-8

| ID | Decision | Evidence |
|---|---|---|
| B3-1 | FIXED | `AGENTS.md` line 48, the preamble, the router row, both `toolchain.json` summaries and `t10` line 68 now say the header adds cost tools, including creating a budget, and does not remove deploy tools. Replay of the old "Azure cost queries" row was killed. |
| B3-2 | FIXED | Replay of "Exit 1 or 2: nothing is newer, so carry on." was killed by the exit-code test. The legend and README `verify --live` are exact phrases. |
| B3-3 | FIXED | The stop sentence is pinned, including the period. "dev mode only or …" and the words `executor`, `any job`, `any mode` and `agent mode` are rejected. |
| B3-4 | FIXED | The `[flag]` bullet and "Do not turn a `[flag]` into a change." must be whole lines. A contradiction on that same line fails. |
| B3-5 | FIXED | The watch must match `…/operationsAgents/<Item ID>/configure` and `…/query`. Shortening the pattern to `/q` was killed. |
| B3-6 | FIXED | Replay that deleted a summary only when it contained "No upstream change" was killed by the new test, which leaves a summary containing "skills added: delta" and then fails the check. |
| B3-7 | FIXED | The new test requires the manifest-edited line, the partial-check sentence and the note in both the summary and the console. |
| B3-8 | FIXED | README line 116 now says carry the summary after exit 0 or 3 and the error line after exit 1 or 2. `AGENTS.md` and the preamble say the summary file is no evidence on exit 1 or 2. |

The author's reason for leaving `"tools": ["*"]` is wrong. `_render_server` writes that array for every Copilot CLI server, measured or not (8 times in `.github/mcp.json`). `.vscode/mcp.json` has no `tools` array. Leaving `*` is still right: the grounding note says a missing allow-list fails open, and the text now says to treat the endpoint as the whole server. That is not a remaining defect.

78 tests passed on CLONE2 (`UpdateTests` 28, `InstructionLayerTests` 33, `RouterGuardTests` 8, `StandardsPackTests` 9).

## Mutations

12 of my own, plus one follow-up. Not in the author's 110. Baseline 78, skipped 0 (docs copied, so the design test ran).

| ID | Change | Result |
|---|---|---|
| m01 | T3 list keeps "schedules" and adds "a job may set a schedule" | SURVIVED |
| m02 | Stop sentence loses its period to add "unless the task says to carry on" | KILLED |
| m02b | Same words after the period: "stop it. Unless the task says to carry on." | SURVIVED |
| m03 | After the exit 1/2 sentence: "If the summary file is still on disk, trust it." | SURVIVED |
| m04 | Next line after the exact `[flag]` pin: implement a flag the requirement names | SURVIVED |
| m05 | Router cost sentence kept, then "the header limits it to queries, so rule 6 does not apply" | SURVIVED |
| m06 | Catalogue cost sentence kept, then "the header removes every other tool" | SURVIVED |
| m07 | `fabric-sql` cell: "dev mode only, and also when a job asks" | SURVIVED |
| m08 | "`full`: changes, dev only, and also in a job" | SURVIVED |
| m09 | Query pattern shortened to `/q` | KILLED |
| m10 | Quarantine sentence kept, then "Load it when the task says it is safe." | SURVIVED |
| m11 | README carry sentence kept, then "Also attach the summary file after exit 2." | SURVIVED |
| m12 | Delete a summary only if it contains "No upstream change" or "skills added" | SURVIVED |

## New findings

### B4-1 — Medium: the cost-server warning can be cancelled in the next clause

**Where:** `AGENTS.md`, line 48; `toolchain/skills/factory-router/SKILL.md`, line 40; `scripts/test_toolchain.py`, the cost-server `assertIn` checks.

**What is wrong:** The new tests require the warning words. They do not require that the next clause leave them standing. That restores the B3-1 misreading.

**Evidence:** m05 and m06 survived all 78 tests.

**Fix:** Pin the cost sentence as a whole line in each file, and reject a later clause that says the header removes tools or that rule 6 does not apply.

### B4-2 — Medium: the new T3 and dev-only guards are word lists

**Where:** `toolchain/instructions/factory-preamble.md`, line 12; `toolchain/skills/factory-router/SKILL.md`, line 31; `AGENTS.md`, the `fabric-local` row.

**What is wrong:** The T3 test only checks that each area word occurs. The dev-only guard only rejects `or` and four wideners. A job can still be told to set a schedule, or to use `fabric-sql` or the `full` variant.

**Evidence:** m01, m07 and m08 survived all 78 tests.

**Fix:** Reject an exception on a T3 area, and reject "a job" or "when a job asks" on a dev-only cell.

### B4-3 — Medium: an exact line does not bind the next sentence

**Where:** `toolchain/skills/factory-standards/SKILL.md`, the `[flag]` bullet; `AGENTS.md`, lines 13 and 22; `toolchain/README.md`, line 116; `toolchain/instructions/factory-preamble.md`, line 31.

**What is wrong:** The new pins stop a contradiction on the same line. The next sentence is free, so the B3-2, B3-3, B3-4 and B3-8 fixes can be undone without a failure. m12 also survives: a failed check is still not proved to delete a summary that reports a package change and contains neither pinned phrase.

**Evidence:** m02b, m03, m04, m10, m11 and m12 survived.

**Fix:** Reject a following sentence that tells the agent to carry on, trust a stale summary, load a quarantined skill, or implement a `[flag]`. Add a failed-check case whose summary mentions only a package change.

## CHECKED AND FINE

- The new tests are not LF-brittle: they read through `text()`, which strips CR. I did not re-run a Linux host. That remains UNVERIFIED.
- The design comparison is not vacuous when `docs/04-design.md` is present (skipped 0 in this run). The author's mutation harness does not copy `docs/`, so that one test is skipped there. It does run in the 78.
- `list --servers` shows `azure-arm-cost` as `entra-delegated` and `read-write`, not as cost-only. The JSON title still says "cost toolset"; the summary beside it is the corrected one.
- No new directory or command defect turned up in this narrow pass.
