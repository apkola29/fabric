# Closure review of the instruction layer, slice B: the catalogue, the commands, the tests by mutation and the changed code (GPT 6.1 Sol)

The reply as it came back, with the agent's own header removed. It decided the twelve findings of the first review of this slice, repeated the reproductions, ran 23 mutations of its own on a scratch copy (17 survived the tests of the first version), diffed the changed code of the update report against the last published commit and ran the commands of the files. The author's check of each finding is in [instruction-layer-closure-findings.md](instruction-layer-closure-findings.md).

## 1. Earlier findings

| ID | Decision | Independent evidence |
|---|---|---|
| B-1 | CLOSED | Corrected freshness command wrote `.factory/update-summary.md` in 37.8 seconds; strict validation reported only the four permitted missing-review links. Network dependence is now documented. |
| B-2 | CLOSED | Fresh-copy `verify --live` exited 1 with V9 failures; after `install --apply`, it exited 0, including the Claude-specific installation and verification. |
| B-3 | CLOSED | The legend now distinguishes local interactive authentication and service-principal variables, matching the [upstream settings](https://github.com/microsoft/powerbi-modeling-mcp/blob/main/README.md): `AZURE_CLIENT_ID` is “Required when --authmode=serviceprincipal.” |
| B-4 | CLOSED | All four formerly missing servers appear in `AGENTS.md`, line 61. Their added page assertions independently matched the current public pages. |
| B-5 | CLOSED | Correct setup link, two endpoints and five per-item servers are recorded. The [primary page](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/mcp-remote-operations-agent) confirms: “Each operations agent exposes two HTTP-based MCP endpoints.” |
| B-6 | CLOSED | Replaying the standards-file mutation containing an unknown name, invalid command and 500 blank lines now fails; the skill is included in `ALL` and the path-keyed budgets. |
| B-7 | CLOSED | The earlier one-word typo, wrong-category name and deleted-routing-table reproductions were all killed. |
| B-8 | CLOSED | The earlier swapped sign-ins, false qualifier and duplicate-server-row reproductions were all killed. A distinct duplicate-variant gap remains below. |
| B-9 | CLOSED | All four earlier command/profile/validator/freshness reproductions were killed. Missing operands and README coverage are separate remaining gaps below. |
| B-10 | PARTLY CLOSED | Import, rule, fragment and RTI-address controls now fail. The original fake unpinned name/description still passes, confirming the author’s admitted omission. |
| B-11 | PARTLY CLOSED | `AGENTS.md` descriptions are corrected, but `toolchain\toolchain.json`, lines 159 and 262, retains the abbreviated Core and RTI summaries that prompted the original finding. |
| B-12 | PARTLY CLOSED | Windows-only publishing and `python3` substitution are documented. The retry window remains 6.35 seconds. Installation succeeded here; the original OneDrive failure and guaranteed recovery remain **UNVERIFIED**. |

## 2. New findings

### Mutation method and results

Every mutation was applied separately to a scratch copy, tested, and restored byte-for-byte. The common test command was:

```text
python -m unittest scripts.test_toolchain.InstructionLayerTests scripts.test_toolchain.RouterGuardTests scripts.test_toolchain.StandardsPackTests scripts.test_toolchain.UpdateTests
```

The unmodified baseline passes **57 tests**. I ran **23 independent mutations: 17 survived, six were killed**. Separately, 16 earlier-reproduction controls yielded 15 kills and the acknowledged B-10 survivor.

Findings B2-1 through B2-6 concern regression coverage—not assertions that the unmodified instructions currently contain the mutated defects.

### B2-1 — Low: Conflicting credential pairs and false authentication prose pass

**Where:** `scripts\test_toolchain.py`, lines 7917–7922; `AGENTS.md`, lines 34–39; `toolchain\instructions\factory-preamble.md`, line 42.

**Evidence:** M19 changed the Fabric-local cell to:

```text
`docs` none; `read` Azure identity; `full` none; `full` Azure identity
```

All 57 tests passed. `sign_in()` silently folds both `full` pairs into a dictionary and returns only `full: Azure identity`. M04 also survived after assigning delegated authentication to `offline-readonly` in the preamble.

**Fix:** Reject repeated variant names before building the dictionary; guard the authentication prose against variant-specific facts.

### B2-2 — Medium: Command guards omit readiness semantics, README recipes and operand arity

**Where:** `scripts\test_toolchain.py`, lines 7874–7881 and 7960–7978; `AGENTS.md`, lines 19 and 72; `toolchain\README.md`, lines 108 and 116.

**Evidence:** M01 removed `--live` from the first preflight; M11 changed README freshness from `--check` to `--write`; M12 supplied a nonexistent README profile. All survived. The M12 command actually exits 2.

M21 appended the existing flag `--denylist` without its required value. All tests passed, but:

```text
python scripts\validate_docs.py --strict --denylist
```

exits 2: `argument --denylist: expected one argument`.

**Fix:** Include the relevant README section, require installed-state preflight, and parse complete validator argument lists rather than testing whether flag names appear in help.

### B2-3 — Medium: Valid identifiers can describe invalid routing and mode boundaries

**Where:** `scripts\test_toolchain.py`, lines 7815–7844; `toolchain\skills\factory-router\SKILL.md`, lines 28–32; `toolchain\instructions\factory-preamble.md`, line 31.

**Evidence:** M06 assigned report questions to `sqldb-cli`; M07 assigned T-SQL to `fabric-iq`; M08 changed hosted consumption to executor-only. M05 removed the executor CLI/REST prohibition. Each passed all 57 tests.

The new typed checks establish membership, not correct task/owner/server relationships or mode restrictions.

**Fix:** Assert essential routing relationships and the credential-free executor boundary, including the procedural text outside table identifier cells.

### B2-4 — Medium: Standards tests preserve tag labels but not their meaning

**Where:** `toolchain\skills\factory-standards\SKILL.md`, lines 24 and 50; `scripts\test_toolchain.py`, lines 8274–8282.

**Evidence:** M09 replaced the `[gate]` explanation with “a mandatory blocking gate already enforced by the static validator.” M10 replaced the prohibition on turning `[flag]` into changes with automatic implementation. Both passed all 57 tests.

**Fix:** Guard the skill’s non-authorizing, advisory status and mandatory human handling of flags—not merely the existence of tag-definition lines.

### B2-5 — Low: Catalogue descriptions, documentation metadata and watch contents remain weakly guarded

**Where:** `scripts\test_toolchain.py`, lines 8011–8099; `AGENTS.md`, lines 40 and 55; `toolchain\toolchain.json`, line 263; `scripts\facts.json`, lines 335–337.

**Evidence:** M13 misspelled the newly added RTI documentation address; M15 removed the Operations-agent query-endpoint assertion; M17 labelled that remote server local; M18 described pinned Fabric Core as documentation-only. All survived.

This extends the author’s accurately acknowledged unpinned-description gap to pinned descriptions, manifest documentation and specific watch assertions.

**Fix:** Check essential catalogue capabilities/hosting, validate documentation associations, and require the important endpoint assertions within each corresponding fact.

### B2-6 — Low: Update integration tests accept losing every resolution note except the first

**Where:** `scripts\toolchain.py`, lines 2954–2955; `scripts\test_toolchain.py`, lines 7583–7643.

**Evidence:** M22 changed the summary call from `notes=notes` to `notes=notes[:1]`. All 57 tests passed. With two unresolved packages, the mutated command returned 0 and printed **two** console notes but wrote **one** summary note.

The formatter’s multiple-note unit test does not protect the command boundary.

**Fix:** Add a command-level case with multiple retained package/contract notes and compare their complete presence in both outputs.

### B2-7 — Medium: Failed checks leave a previous successful summary intact

**Where:** `scripts\toolchain.py`, lines 2933–2955 and 3698–3711; `toolchain\README.md`, line 116.

**Reproduction:** Using the repository’s offline `UpdateTests` fixture, run the documented freshness arguments successfully, then make its source resolver fail; repeat with `--bogus-flag`.

**Observed:** The first invocation returned 0 and wrote a clean summary. Subsequent invocations returned **1** and **2**, respectively, while the summary remained byte-identical and still said `No upstream change.`

The README says to carry the summary “In every case,” without preventing attachment of this stale success evidence.

**Fix:** Distinguish attempt-specific evidence and explicitly prohibit reusing a previous summary after exits 1/2; the runner should remove or mark stale evidence before checking.

### B2-8 — Low: Exit 3 does not necessarily mean something newer, and Markdown omits that distinction

**Where:** `AGENTS.md`, line 22; `toolchain\README.md`, line 116; `scripts\toolchain.py`, lines 2950–2955.

**Reproduction:** In `UpdateTests`, append a quarantine entry to the manifest without changing upstream metadata; run `update --check --fail-on-update --summary-file`.

**Observed:** Exit **3**. Console: `The lock inputs changed (the manifest was edited); nothing changed upstream.` Markdown: `No upstream change.`, without the manifest-change explanation.

Thus the instruction “something is newer” is too strong, and the durable report loses the reason for exit 3.

**Fix:** Define exit 3 as a changed candidate lock, distinguish local-input changes, and include that explanation in Markdown.

### B2-9 — Medium: Default freshness is advertised as checking tool-contract changes, but performs no capture

**Where:** `toolchain\README.md`, lines 116 and 121; `scripts\toolchain.py`, line 2939.

**Reproduction:** Change the fake upstream `acme-py/tool_b` annotation to destructive while keeping package metadata unchanged. Run the documented freshness command.

**Observed:** Exit **0**, `No upstream change.`, **zero** stdio captures. Adding `--contracts` to the controlled fixture detects the change and returns 3.

**Fix:** Describe default freshness as metadata checking. Explain the separate pinned-contract verification path; do not simply add candidate-server execution to ordinary agent freshness.

### Independent mutation ledger

“S” means all 57 tests passed; “K” means a test failed.

| Mutation | Change | Result / finding |
|---|---|---|
| M01 | First preflight drops `--live` | S — B2-2 |
| M02 | Claude import becomes `@../AGENTS.md` | K |
| M03 | Gemini shim identifies Claude Code | K |
| M04 | Preamble assigns delegated sign-in to offline authoring | S — B2-1 |
| M05 | Remove executor CLI/REST prohibition | S — B2-3 |
| M06 | Report owner becomes `sqldb-cli` | S — B2-3 |
| M07 | SQL route becomes `fabric-iq` | S — B2-3 |
| M08 | Hosted IQ becomes executor-only | S — B2-3 |
| M09 | `[gate]` falsely described as already enforced | S — B2-4 |
| M10 | Automatically implement `[flag]` checks | S — B2-4 |
| M11 | README freshness becomes `--write` | S — B2-2 |
| M12 | README Gemini recipe uses nonexistent profile | S — B2-2 |
| M13 | RTI documentation becomes `mcp-local-servers` | S — B2-5 |
| M14 | Manifest Core credentials become `none` | K |
| M15 | Remove Operations-agent `/query` watch pattern | S — B2-5 |
| M16 | OneLake fact becomes `stable: true` | K |
| M17 | Operations-agent hosting becomes local | S — B2-5 |
| M18 | Core described as documentation-only | S — B2-5 |
| M19 | Duplicate contradictory `full` credential pair | S — B2-1 |
| M20 | Write summaries only when `changed` | K |
| M21 | Validator `--denylist` lacks its value | S — B2-2 |
| M22 | Summary receives only `notes[:1]` | S — B2-6 |
| M23 | Filter dropped-contract notes from formatter | K |

## 3. CHECKED AND FINE

- **Catalogue:** The [live Fabric directory](https://learn.microsoft.com/en-us/rest/api/fabric/articles/mcp-servers/fabric-mcp-servers-list) still lists 14 main entries, all represented across the two tables. Its two related customer-hosted integrations are mentioned. All 11 manifest server IDs and their credential variants match the catalogue.
- **Additional servers:** Independently rechecked OneLake, earlier Power BI Consumption, Enterprise Graph and Foundry. Current public-page assertions match; no additional directory entry was missing.
- **Changed code:** Public comparison against `11b1cf6084` confirms only `format_report` and `cmd_update` changed. Current retained-package and retained-contract notes receive the incomplete-check qualification; dropped-contract notes do not. Console notes are not duplicated, and Markdown retains them.
- **Commands:** Executed the documented toolchain forms in scratch copies, including installation, rendering and maintainer lock/write forms. Dev rendering succeeds; agent-implementer rendering correctly refuses the uncaptured licensed-server contract. Public freshness returned 0 with five retained-package notes, all present in the qualified summary.
- **Portability:** Python 3.11.9 on Windows; the same 57 tests pass with original CRLF and a copy normalized to LF. Strict validation has only the four permitted link errors. Actual Linux-host execution is **UNVERIFIED**.
- **Authorization:** No credentials or tenant operations were used. Doctor’s sign-in queries and hosted probes were intercepted; unrestricted live doctor behavior was not tested.
- **Records:** B-10’s “not done” is honest. B-11 should explicitly retain the unchanged manifest summaries as unfinished. I found no evidence requiring changes to the author’s earlier severity ratings.
- **Read-only integrity:** All 135 snapshot files match the pristine scratch copy byte-for-byte. Mutations were restored, and the restored baseline passes.
