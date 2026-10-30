# Verification round 1: findings and what was done

Round 1 checked the published design (commit `2ae0c95302`) with three reviewers from different model families, each with its own lens, reading a frozen copy: GPT 6.1 Sol on consistency and logic ([round-1-gpt.md](round-1-gpt.md)), Gemini 4 Argon on platform facts against live sources ([round-1-gemini.md](round-1-gemini.md)), and Grok 4.7 on public exposure, scripts and a cold read ([round-1-grok.md](round-1-grok.md)). The loop and its proof of publication are in [verification-log.md](verification-log.md).

A reviewer's severity is not taken as given. Every finding was checked against the document or the primary source before it was accepted, and the severity below is the author's after that check.

## Summary

| Reviewer | Findings | Accepted | Modified | No change |
|---|---|---|---|---|
| GPT 6.1 Sol (R1-A) | 7 | 7 | 0 | 0 |
| Gemini 4 Argon (R1-B) | 8 | 6 | 1 | 1 |
| Grok 4.7 (R1-C) | 10 | 8 | 2 | 0 |
| Total | 25 | 21 | 3 | 1 |

Gemini also confirmed 22 other claims against their sources. After the author's re-rating there are 5 High, 11 Medium and 8 Low, plus one finding that needs no change. No finding was rejected. "Modified" means the reviewer was partly wrong, or the premise did not hold as stated, but a related change was still made.

## Findings and dispositions

| ID | Reviewer severity | Author severity | Decision | What was found and what was done | Where |
|---|---|---|---|---|---|
| R1-A-1 | Critical | High | Accepted | The second T2 approval is enforced only by an event-driven check, so a dismissed approval or a team change leaves a stale pass for a short window. Moderated because a merge is a human act by the maintainers team and T2 is stage 2 only. Added a bounded-window rule: more events, a periodic sweep, a merge-time audit that halts new runs, a fallback to two native approvals, and negative test N11 | Design 3.6, S11 |
| R1-A-2 | High | High | Accepted | A requester outside the trusted sub-group at tier T0 or T1 matched both exits from PLANNED. The guards are now exclusive and ordered | Design 3.3 |
| R1-A-3 | High | Medium | Accepted | A cap on concurrent runs does not bound parallel requests from one agent container, so the claimed overshoot bound had no basis in D0. The design now states the real bound (engine limits plus the organization budget), makes S9 measure it with parallel requests, and says D1's gateway gives a real per-run bound | Design 3.14, I-3, 4.1, S9; register D-21; requirements NFR-09 and question 5 |
| R1-A-4 | Medium | Medium | Accepted | The text named DONE, PARTIAL, BLOCKED and ABANDONED while the diagram had other terminal states, and the 7-day clarification timeout had no transition. One terminal-state table, the missing transition, and a mapping from the outcome labels | Design 3.3 |
| R1-A-5 | Medium | Medium | Accepted | "0% pass is treated as broken" turned a heuristic into a rule that could inflate the pass rate. A zero-pass task now goes to an audit, and an exclusion is recorded with the original denominator | Design 3.15 |
| R1-A-6 | Medium | Medium | Accepted | The reviewer preview rebuilt B1 to B4 only, so a data agent would not be published. It now adds B5 for data agents and ontologies, and says no LLM agent runs in the rebuild | Design 3.7 |
| R1-A-7 | Medium | Medium | Accepted | D-27 named S11 as its test, but S11 tested only repository controls. S11 now includes the evidence store, with new negative test N12, and the audit paragraph points to it | Design 3.6, 3.16, S11 |
| R1-B-1 | Critical | High | Accepted | Confirmed against the source: the strict-binding flag of `fabric-cicd` is on `main` since 2026-10-28 and not in release 1.4.0, which only logs a failed binding. Moderated because B4 already read back and refreshed. The design now says so, adds a connections read-back that stands in for the flag, and S3 tests a deliberately bad binding | Design 3.7 (B3, B4), 3.9 pack table, S3 |
| R1-B-2 | High | Medium | Modified | The reviewer said the protection is GA and that reports cannot be in a protected workspace. Two Learn pages disagree: the availability matrix (updated 2026-10-15) says Preview for reports, semantic models and data agents and unsupported for ontologies, and the overview (2026-09-01) says reports cannot be created in a protected workspace. The design's "preview" was right, but its limit was misdescribed. Rewritten with both pages, no reliance on the protection for report or ontology workspaces, and an S2 test | Design 3.7, 4.1, 4.3, S2; digest 3.3 |
| R1-B-3 | High | Medium | Accepted | Confirmed on docs.github.com: repositories created, renamed or transferred after 2026-07-15 emit an immutable subject with the owner and repository IDs. Credentials are created from the subject the repository emits, the preflight compares them, and S2 shows a rename breaking trust | Design 3.5, 3.3 preflight, S2 |
| R1-B-4 | Medium | Medium | Accepted | Confirmed on Learn: the custom role for pause and resume also lists `write`, which would let the identity resize the capacity. S8 tests with and without it and records the exposure if it is needed | Design 3.5, S8, claims to confirm |
| R1-B-5 | Medium | Low | Accepted | Confirmed on Learn: OneLake bills soft-deleted data at the active rate, and Git operations re-create a deleted item under a new ID. Both are now stated as documented | Design 3.7, 4.3, 10; digest 3.3 |
| R1-B-6 | Low | Low | Accepted | Confirmed on Learn and in the gh-aw reference: data agents are listed without a preview tag, the ontology is preview, and the Gemini CLI engine is deprecated. The design uses the Copilot engine, so nothing else changes | Requirements A12; digest 2 and 3.2 |
| R1-B-7 | Low | Low | Accepted | Confirmed on docs.github.com: `Restrict updates` is worded as limiting who can push, and any user with write access can enqueue a passing PR. Quoted in the design, and the queue stays off in v1 | Design 3.6 |
| R1-B-8 | High | none | No change | Unverifiable from public sources, which is what the design already says: it is gated on spike S6 and the exception policy D-31 | Already in design 3.10 and S6 |
| R1-C-1 | High | High | Accepted | The verification log, the research README and one raw report described non-public material that had been removed. Rewritten to the public facts only, and the raw report's test pattern was made generic. The private term list now covers the phrases | Verification log, research README, README, raw reports T3a, T4 and O1 |
| R1-C-2 | High | High | Accepted | The publish script warned and carried on without the private term list, and CI cannot hold it. The script now stops unless a list is found or `-NoDenylist` is given, the validator has `--require-denylist`, and the README explains that CI applies only the generic patterns | Sync script, validator, README |
| R1-C-3 | Medium | Medium | Accepted | One sentence about the tenant's capacity inventory survived. Reworded to the public limit, and the log corrected | Raw report O1, requirements question 8 |
| R1-C-4 | Medium | Low | Accepted | A local plugin install path appeared in two raw reports. Reworded, and the validator now flags a local Copilot install path | Raw reports T3a and T4, validator |
| R1-C-5 | Medium | Medium | Accepted | The push sent every unpushed commit. The script now refuses a range that has a merge commit or any commit touching a path outside the managed set, pushes the commit by SHA to an explicit ref, rejects unsafe branch names, and scans the root README before `-IncludeReadme`. `-AllowOtherCommits` is gone | Sync script, validator |
| R1-C-6 | Medium | Low | Modified | The premise was wrong for GitHub: the four workflow files there have no CR bytes and each pair is the same size, so the repository holds LF. The CRLF came from how the review snapshot was built. The real gap was that the local copies of the two workflow files depended on the clone's settings, so the script now writes them with LF | Sync script |
| R1-C-7 | Medium | Low | Modified | On PowerShell 7 a native command's exit code raises an error only when a non-default preference is set, so the described failure does not occur by default. The script now sets the preference explicitly | Sync script |
| R1-C-8 | Medium | Medium | Accepted | "32 mutation tests" and "33 tests" were used for the same suite, the commands assumed a folder and `python`, and the claims were broader than the tests. Wording corrected, and the README says what the tests do and do not prove | README, verification log |
| R1-C-9 | Low | Low | Accepted | A remote URL with embedded credentials would have been printed on a mismatch. User information is now removed | Sync script |
| R1-C-10 | Low | Low | Accepted | Added a reading order and a table of terms to the README, a sentence in the design that it describes a system that is not built, and an index of the reviews | README, design header, reviews README |

## How the disputed points were checked

- **R1-B-1 (confirmed).** The code of `fabric-cicd` at tag v1.4.0 logs "Failed to bind" and continues. The flag exists only on `main`, added by commit `4bf12265` on 2026-10-28. PyPI and GitHub Releases both name v1.4.0 (2026-10-07) as the latest release. The documentation on `main` says a failed binding is logged and the deployment continues unless the flag is set. The connections read-back relies on the List Item Connections endpoint, which `fabric-cicd` itself calls.
- **R1-B-2 (partly wrong).** The Learn overview (updated 2026-09-01) marks only Real-Time Events as preview, and says Power BI items other than semantic models cannot be created in a protected workspace. The availability matrix (updated 2026-10-15) lists Power BI Report, Semantic Model and Data Agent as Preview and Ontology as unsupported, with lakehouses, notebooks and pipelines supported. So "GA" is not what the matrix says for the items that matter here, and the two pages conflict about reports. The design records the conflict and S2 tests it.
- **R1-A-1 (severity).** The race needs a human maintainer to merge inside the window, or a team change that raises no review event. Both are real, so the fix is a bounded window plus a detective control, with a fallback that closes it. It is a High, not a Critical, because no external party can use it and T2 is stage 2 only.
- **R1-C-6 (false alarm for GitHub).** The raw files on GitHub at the reviewed commit have no CR bytes: 37 and 26 LF in the two workflow files, with the `ci/` copies the same size. The snapshot the reviewers read had been made with `git archive` in a clone that has `core.autocrlf` on, which is where the CRLF came from.

## Found while fixing (not raised by a reviewer)

1. The lifecycle had no exit from PLANNED for a T3 or oversize plan, although triage "stop" is described in 3.12. Added while fixing R1-A-2.
2. Two mutation tests injected their defect by matching text in the zone diagram that had just been redrawn, so they no longer injected anything. The test helper now fails when a mutation changes nothing.
3. A new test wrote its private term literally and the validator found it in the test's own source. The term is now built at run time, like the other leak tests.
4. The budget text said "open question 5", which is the requirements numbering. Both numberings are now given.

## Still open after round 1

These cannot be settled by reading and are spike outputs: the bound on the approval window (N11), whether a release of `fabric-cicd` gets the strict-binding flag, which item types outbound access protection accepts (S2), the OIDC subject format of the target repository (S2), whether suspend and resume need the `write` action (S8), the measured overshoot with parallel requests (S9), and unattended data agent publishing (S6).
