# Verification round 2: Gemini 4 Argon

Lens: public exposure, script and CI security, and a cold read. The reviewer had not seen round 1. It read a frozen copy of the published commit `41a41c285a` and replied inline. This is the reply condensed. Quotes that would repeat material removed from the repository are described instead of quoted. The disposition of each finding is in [round-2-findings.md](round-2-findings.md).

Summary from the reviewer: no credentials, tokens, keys, connection strings, GUIDs, private addresses or ticket IDs in any of the 48 files.

## Findings

| ID | Part | Severity | Where | Evidence | Why it matters | Concrete fix |
|---|---|---|---|---|---|---|
| R2-C-1 | 2 | High | `scripts/verify_facts.py`, the file, PyPI and npm checks | `if status == 404: return FAIL` followed by a search of the response body, with `expect` set to absent | `http_get` returns the status and an empty body on a non-200 answer (500, 502, 503, 429, a 403 that is not a rate limit). The file check tests only for 404, searches the empty body, and returns PASS for an "absent" claim. The PyPI and npm checks crash on an empty body | Raise Unreachable (or return FAIL) whenever the status is not 200 after the 404 case. Add a unit test for an HTTP 500 on an "absent" claim |
| R2-C-2 | 2 | Medium | `scripts/sync_to_github.ps1`; `verification-log.md` | The push range is checked by path, and the log says the script "validates the whole push range" | The validator runs only against the working tree. If the clone already holds unpushed commits that touch `fabric-automation/`, their earlier blobs are never scanned for leaks or private terms, yet they are pushed to public history | Refuse to run unless the push range is empty before mirroring, or run the validator on every commit tree in the range |
| R2-C-3 | 1 | Medium | `docs/01-requirements.md`, assumption A10 | A sentence about how many capacities the pilot tenant has and who shares it | Round 1 removed this kind of tenant inventory from one raw report and from an open question, and the log says it was removed, but the same detail survived in A10 | State only the design assumption: a dedicated sandbox capacity is needed because a shared one can be throttled or paused by other workloads |
| R2-C-4 | 1 and 2 | Medium | `scripts/sync_to_github.ps1`, the default location of the private list | A hard-coded path to a sibling local folder | It names the author's local folder layout, contradicts the parameter help ("the private folder next to the project"), and ignores a list placed in the project's own `private/` folder | Probe the project's `private/` folder and the folder next to it after the environment variable, and remove the hard-coded path |
| R2-C-5 | 2 | Medium | `ci/fabric-automation-facts.yml` and its copy in `.github/workflows/` | The step runs the checker and then appends its output to the step summary | A `run` step uses `bash -e`. When any check fails the checker exits 1 and the shell stops before the summary is written, so the summary is empty exactly when it is needed | Write the summary in a later step with `if: always()`, or capture the exit status first |
| R2-C-6 | 3 | Medium | `scripts/test_verify_facts.py` docstring; README; `verification-log.md` | The docstring says the tests show that each kind of check reports PASS, DRIFT, FAIL or UNREACHABLE. The log says "over 24 claims" for results that add up to 26, and "32 injected defects, and 6" for the options | Only 2 of the 10 kinds of check had fake-network tests, and 5 of the 18 tests were static checks of `facts.json`. In the log, the 39 validator tests are 1 baseline, 33 injected defects (`test_local_tool_path_leak` is an injection) and 5 option tests | Add tests for the other 8 kinds, or narrow the wording. Correct "24" to "26", and "32 injected defects, and 6" to "33 injected defects, and 5" |
| R2-C-7 | 2 | Low | `scripts/validate_docs.py`, the leak patterns and the denylist read | The local-tool pattern matches one tool directory. The user-path pattern accepts only lower-case names after `/Users/` and `/home/`. A missing path given to `--denylist` raises an unhandled exception | Other tilde-home tool directories and capitalised macOS user names are missed, and a missing list file is a crash, not a clean error | Broaden the tilde pattern to any hidden directory, allow capitals in the user-path pattern, and catch the read error |
| R2-C-8 | 2 and 3 | Low | `ci/fabric-automation-validate.yml`; `scripts/sync_to_github.ps1`; `docs/03-landscape-research.md` line 7 | The validate workflow's path filter omits the facts workflow, and nothing compares the two copies of each workflow. The origin check is an unanchored substring match. The digest says the raw reports are "t1 to t6" | A workflow copy could drift unseen, a longer remote name containing the repository name would pass, and the digest count is stale (the reports run to t7) | Add the facts workflow to the filter and a pair-diff step, anchor the origin check, and fix "t1 to t6" to "t1 to t7" |

## Round-1 fixes checked

- Removed non-public wording (R1-C-1): CLOSED. The log, the research README and three raw reports now state only public facts about the public repository.
- Fail-closed private term list (R1-C-2): CLOSED WITH RESERVATION. The script aborts without a list unless `-NoDenylist` is given, and the validator has `--require-denylist`, but the default location is the hard-coded path (R2-C-4).
- Push-range guard and push by SHA (R1-C-5): CLOSED WITH RESERVATION. It pushes the SHA to an explicit ref, rejects unsafe branch names and merge commits, and checks the paths in the range, but it does not scan the content of earlier unpushed commits (R2-C-2).
- LF workflow copies (R1-C-6): CLOSED. All four workflow files in the snapshot and on GitHub are byte-for-byte LF, and the script writes LF explicitly.
- README scan on `-IncludeReadme` (R1-C-5): CLOSED. The script passes the README to the validator before staging.
- Local-install-path pattern (R1-C-4): CLOSED WITH RESERVATION. The paths are gone from the raw reports, but the pattern matches only one tool directory (R2-C-7).
- Origin URL sanitising (R1-C-9): CLOSED WITH RESERVATION. User information is stripped, but the origin check is an unanchored substring match (R2-C-8).

## Checked and sound

- `verify_remote.py` confirms that all 46 files in the folder and both workflow files match GitHub at the reviewed commit, with 0 problems.
- The validator passes in strict mode with 0 errors and 0 warnings, and all 57 unit tests pass (39 for the validator and 18 for the fact checker).
- All counts in `round-1-findings.md` recompute from its 25 table rows: GPT 7 (7, 0, 0), Gemini 8 (6, 1, 1), Grok 10 (8, 2, 0), total 25 (21, 3, 1), and the author severities 5 High, 11 Medium, 8 Low and 1 none.
- The workflows use `permissions: contents: read` and `persist-credentials: false`, pin `actions/checkout` by SHA, have no `pull_request_target`, and interpolate no untrusted expression in a `run` step.
- The cold-read path in the README (where to start, the reading order, the table of terms, the commands from the stated folder, and the designed-against-built framing) is clear and runs as written.

## Could not verify

- The contents and coverage of the private term list, which is kept out of the repository and the snapshot by design.
- Live execution of `verify_facts.py` against all 38 external sources during this pass. It was checked by reading the code and the unit tests.
- Whether the parent repository carries a root `.gitattributes` outside the 48-file snapshot.

Verdict: safe after fixes - 0 critical, 1 high, 5 medium, 2 low
