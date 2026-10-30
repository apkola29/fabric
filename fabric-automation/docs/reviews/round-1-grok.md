# Verification round 1: Grok 4.7

Lens: public exposure, script and CI security, and a cold read. The reviewer read a frozen copy of the published commit `2ae0c95302` and replied inline. This is the reply condensed. Quotes that would repeat material that was removed from the repository are described instead of quoted. The disposition of each finding is in [round-1-findings.md](round-1-findings.md).

Summary from the reviewer: no credentials, personal e-mail addresses or tenant GUIDs in the 42 files. Two High issues to fix: the verification log described non-public material that had been removed, and the publish script carried on when the private term list was missing.

## Findings

| ID | Part | Severity | Where | Evidence | Why it matters | Concrete fix |
|---|---|---|---|---|---|---|
| R1-C-1 | 1 | High | The verification log (loop 0), the research README and one raw report | Wording that says what kind of non-public material was removed and where it came from | The authors had marked this material must-not-publish, then described it. One raw report's suggested test pattern also reconstructs its detail. | Keep only the public facts about the repository tree. Remove the description of the non-public source and the specifics of the pattern. |
| R1-C-2 | 2 | High | `scripts/sync_to_github.ps1` about line 94; `ci/fabric-automation-validate.yml` | The script warns that no private denylist was found and then publishes. CI runs the validator in strict mode with no denylist. | The check fails open, and the private terms are never enforced on GitHub. | Abort when the denylist file is missing. Do not publish on a warning. |
| R1-C-3 | 1 | Medium | `o1-fabric-surface-grounding.md` finding 11; requirements open question 8 | Sentences that describe how many capacities the signed-in identity sees and that one is shared | Tenant inventory, not a product fact. The log said the size and state were removed, but this part was not. | State only the public limit (a trial capacity cannot host data agents). Drop the count and the sharing. Correct the log. |
| R1-C-4 | 1 | Medium | `t3a-ms-native.md` about lines 208 and 244; `t4-fabric-mechanics.md` about lines 216 and 329 | A local plugin install path that begins with the home-directory tilde | A local install path that the leak scanner does not match. It holds no user name. | Say "the installed fabric-collection plugin". Add a pattern for tilde-home paths and a test. |
| R1-C-5 | 2 | Medium | `sync_to_github.ps1`: the push, `-IncludeReadme`, `-AllowOtherCommits`, `$Branch` | The commit is limited to the managed paths, but the push sends every unpushed commit. `-AllowOtherCommits` skips the subject check and does not inspect paths. `-IncludeReadme` commits the repository README with no leak scan. A branch value that starts with `+` becomes a force refspec. | The script can publish more than it commits. | Push only the new SHA and reject non-fast-forward. Reject `+` and extra refspecs. Scan the README before `-IncludeReadme`. Refuse earlier commits whose diff leaves the managed paths. |
| R1-C-6 | 2 | Medium | `.github/workflows/*.yml` against `fabric-automation/ci/*.yml`; `.gitattributes` | The workflow copies in the review snapshot have CRLF endings and the `ci/` copies have LF | The folder's `.gitattributes` does not cover `.github/workflows`, and `verify_remote.py` normalizes the local side only, so the two extra files might fail or match for the wrong reason. | Store both copies as LF. Add a root `.gitattributes`. Compare raw Git blobs, or normalize both sides the same way. |
| R1-C-7 | 2 | Medium | `sync_to_github.ps1`, the robocopy block | `$ErrorActionPreference = 'Stop'` and robocopy is not wrapped like the other native calls | On PowerShell 7.4 or later, exit codes 1 to 7 (success with copies) could abort before the check for 8 or more. | Set the error action to Continue around robocopy and keep the check. |
| R1-C-8 | 3 | Medium | `README.md` "Checking this folder"; `verification-log.md` loops 0 and 1 | The documents say "32 mutation tests" in one place and "all 33 tests" in another, and "runs on every change". The commands assume the working directory and `python`. | 33 test methods are the baseline plus 32 single-defect injections. They prove that the validator reports those defects, not that every leak is caught. CI is path-filtered and uses `python3`. | Say so explicitly. Document the working directory and `python3`. Do not treat a green validator as proof of publication. |
| R1-C-9 | 2 | Low | `sync_to_github.ps1`, the origin check | A mismatch prints the full remote URL | A remote with an embedded token would leak into the error text. | Print host and path only. |
| R1-C-10 | 3 | Low | `README.md` reading order; the design's tone; `docs/research/README.md` | The design is "where to start" and is written in the present tense. Terms such as model family, Phase 0, FR, NFR and HR are not defined where a new reader starts. `docs/reviews/` has no ordered index. | A cold reader cannot tell designed from built, and gets lost in the reviews folder. | Add a short reading order and a glossary, say that the design describes a system that is not built, and index the reviews. |

## Checked and sound

- All 42 files scanned: no GUIDs, JWTs, PATs, private keys, connection strings, personal e-mail addresses or home-directory paths. The public hits (the Copilot no-reply address, a bot address, `apkola29/fabric`, public documentation and repository URLs, named public authors in citations) are acceptable.
- Workflows use `contents: read` and `persist-credentials: false`, pin `actions/checkout` by SHA, have no expression in a `run` step, no `pull_request_target` and no artifacts. A fork's pull request can run the validator, but the token stays read-only and no secret is referenced.
- The default publish does not force-push and does not stage paths outside the folder and the two workflow files. Git and `gh` are invoked with argument arrays, not through a shell.
- `verify_facts.py` and `verify_remote.py` use the standard library (plus `gh` for the remote check). The facts workflow runs only on demand.
- The README status line is accurate: design and document tooling only, nothing built.

## Could not verify

- The private term list is not in the snapshot, so the "zero hits" claim cannot be rechecked.
- That `actions/checkout` v7.0.1 equals the pinned SHA (this pass did not re-query the tag).
- Whether the parent repository has a root `.gitattributes`.
- Every in-document GitHub anchor. A spot check of one raw report rendered correctly.
- Whether the publish script was run on Windows PowerShell 5.1 or on 7.4.

Verdict: safe after fixes - 0 critical, 2 high, 5 medium, 2 low (the table above lists 6 medium)
