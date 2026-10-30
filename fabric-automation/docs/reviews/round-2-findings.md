# Verification round 2: findings and what was done

Round 2 checked the design as corrected after round 1 (commit `41a41c285a`). The same three model families took part, but each on a different lens from round 1, so that no family reviewed the same angle twice: Grok 4.7 on consistency and closure of the logic fixes ([round-2-grok.md](round-2-grok.md)), GPT 6.1 Sol on platform facts against live sources ([round-2-gpt.md](round-2-gpt.md)), and Gemini 4 Argon on exposure, scripts and a cold read ([round-2-gemini.md](round-2-gemini.md)). None of them had seen round 1. The loop is recorded in [verification-log.md](verification-log.md), and round 1 is in [round-1-findings.md](round-1-findings.md).

As in round 1, a reviewer's severity is not taken as given. Every finding was checked against the document, the code or the primary source before it was accepted, and the severity below is the author's after that check.

## Summary

| Reviewer | Findings | Accepted | Modified | No change |
|---|---|---|---|---|
| Grok 4.7 (R2-A) | 8 | 7 | 1 | 0 |
| GPT 6.1 Sol (R2-B) | 9 | 9 | 0 | 0 |
| Gemini 4 Argon (R2-C) | 8 | 7 | 1 | 0 |
| Total | 25 | 23 | 2 | 0 |

GPT also confirmed 28 other claims against their sources, including every platform fact that round 1 corrected. After the author's re-rating there are 4 High, 14 Medium and 7 Low. No finding was rejected. "Modified" means part of the finding was not a defect, or a related change was preferred to the one proposed.

## Findings and dispositions

| ID | Reviewer severity | Author severity | Decision | What was found and what was done | Where |
|---|---|---|---|---|---|
| R2-A-1 | High | High | Accepted | The approval window had no bound declared in advance, so N11 could not fail, and the sweep was described as a re-post. Now the bound is fixed before the test (60 seconds after a review event, 5 minutes after a team change), the sweep re-reads the team and the approvals and fails the check, the preflight asserts the Members permission and the age of the last sweep, and T2 stays off until N11 meets the bound, with two native approvals as the fallback. The merge-time audit stays detective, and the text says why it cannot be preventive: GitHub has no hook before a merge. The summary, 3.17, 4.1, FR-37 and PS-2 now point at the window | Design 1, 3.3 preflight, 3.6, 3.17, 4.1, N11, S11; requirements FR-37, PS-2 |
| R2-A-2 | High | High | Accepted | The reconciler's stage timeout matched runs that were waiting for a human, "from any state" included the terminal ones, a cancelled run with an open PR could still be merged, APPROVAL had no reject or timeout exit, and the deadline had no terminal state. Now human waits are never re-dispatched and have their own deadlines, a terminal write is compare-and-swap so the first one wins, a cancel or a halt converts an open PR to a draft and voids its evidence (a halt does so before the App is disabled), the missing exits all lead to ESCALATED, and every state has an outcome label | Design 3.3, 3.16 |
| R2-A-3 | High | Medium | Accepted | "Or 72 hours" contradicted "until the PR is merged or closed". The reservation now lasts as long as the PR, which closes after 14 idle days, and is released at once when the run ends without a PR. Each lock carries the run ID and the PR number. Moderated because the strict up-to-date rule already voids a second PR's evidence, so the failure was duplicate work, not a wrong merge | Design 3.3 |
| R2-A-4 | Medium | Medium | Accepted | Three sentences still implied a bound in D0. Reworded, and 3.16 now says that the token and dollar counters stop dispatch but not calls made inside a running job | Design 3.16, 4.1 row 1, 4.3 |
| R2-A-5 | Medium | Medium | Accepted | The publisher's GitHub side effects had no idempotency rule. A commit is made against an expected head, and on resume a PR is looked up by its head branch, a check run by its name and head SHA, and a comment by a hidden marker. S5 now fails on a duplicate PR, check run or comment | Design 3.3, S5 |
| R2-A-6 | Medium | Medium | Accepted | An ontology preview ran the data-agent publish. Only data agents get B5, and an ontology preview waits for the ontology pack | Design 3.7 |
| R2-A-7 | Medium | Medium | Accepted | "Trusted sub-group" was never defined. It is now a per-target list in the policy repo, changed only by two approvers, and a requester who is not on it, or a tier that cannot be computed, takes the approval path or stops | Design 3.3 diagram, 3.12 |
| R2-A-8 | Medium | Medium | Modified | A workspace that died before a dynamic gate had no expiry, and cancel said "at once or left to the sweeper". Expiry now starts at creation when no gate ran, and cancel tears down at once, with the sweeper only when the executor cannot run. The point about FR-39 was not a defect: T1 already has one held-out input in Phase 1 (3.12), and the roadmap row now says that the full hidden-check set is Phase 2 | Design 3.3, 3.16, 5.2 |
| R2-B-1 | High | Medium | Accepted | Verified: the Power BI export API has export, status and file retrieval, and no cancel call. An export now drains, with the residual recorded. Moderated because the design already quarantined whatever it could not cancel | Design 3.3, 3.16 |
| R2-B-2 | High | High | Accepted | Verified on GitHub's budgets page: an organization budget only sends alerts unless "Stop usage when budget limit is reached" is on, and a user-level budget always stops usage. The design had called the organization budget the hard stop. Now it is conditional, S9 shows a request refused at the limit, and the quarterly review rechecks the setting | Design 3.14, 3.16, S9; register D-21 |
| R2-B-3 | Medium | Medium | Accepted | Verified in the firewall's source: its API proxy takes signed per-invocation request and token ceilings. The design no longer says that D0 cannot cap parallel requests, and S9 asks whether the pinned path can set them | Design 3.14, I-3, S9; register D-21 |
| R2-B-4 | Medium | Low | Accepted | Verified: flexible federated credentials add wildcards. The design now says that standard credentials match exactly and that exact subjects are its own choice | Design 3.5 |
| R2-B-5 | Medium | Medium | Accepted | Verified on GitHub's page: an App can be the required source of a check only with the statuses write permission, a recent check run and an existing required check. Added to the publisher's rights, to the setup (a canary check run before the rulesets are armed) and to the preflight | Design 3.5, 3.6 |
| R2-B-6 | Medium | Low | Accepted | Verified on Learn: Update From Git needs service-principal support for every item involved in the operation, not every item in the workspace | Design 3.8; digest 1 |
| R2-B-7 | Medium | Low | Accepted | Verified: at most 100,000 rows or 1,000,000 values per query, and 120 requests a minute per user across datasets. The 15 MB figure could not be confirmed on the page, so it was not added. A 200 answer that carries an error is now a failed query | Digest 3.2; design 3.9 |
| R2-B-8 | none | Low | Accepted | That a check's success persists after a review is dismissed is now labelled an assumption that N11 tests | Design 3.6 |
| R2-B-9 | none | Low | Accepted | The digest now names the `WorkspaceHeadMismatch` error and says that S4 confirms its HTTP status | Digest 3.3 |
| R2-C-1 | High | High | Accepted | Reproduced: on any HTTP error the "absent" check returned PASS, and the registry checks reported a crash. Server errors and rate limits are now UNREACHABLE at the source, any other non-200 answer is never read as evidence, and new tests pin it. An in-memory mutation that switches the guard off fails 6 of them | `verify_facts.py`, `test_verify_facts.py` |
| R2-C-2 | Medium | Medium | Accepted | Earlier local commits were never scanned by the current run. The script now refuses them if they touch anything outside the managed set, then folds them away with a soft reset, so that only the validated state is committed and pushed | `sync_to_github.ps1` |
| R2-C-3 | Medium | Medium | Accepted | One more tenant inventory sentence survived in assumption A10. Reworded to the design assumption, and its phrases added to the private list | Requirements A10 |
| R2-C-4 | Medium | Medium | Accepted | The default location of the private list was a hard-coded sibling path. The script now probes the project's `private/` folder and the folder next to it. The canonical list moved to the project's `private/` folder, which Git, the mirror and both validators ignore, and the validator uses it by default | `sync_to_github.ps1`, `validate_docs.py`, README |
| R2-C-5 | Medium | Medium | Accepted | The facts workflow lost its summary when a check failed. The summary is now written before the step exits | `ci/fabric-automation-facts.yml` |
| R2-C-6 | Medium | Medium | Accepted | The log said "24 claims" for 26 results and "32 injected defects, and 6" for 33 and 5. Corrected, the README wording narrowed, and fake-network tests added for the other eight kinds of check | `verification-log.md`, README, `test_verify_facts.py` |
| R2-C-7 | Low | Low | Modified | The user-path pattern now accepts capital letters, the second tool directory was added, and an unreadable list file is a clean error. A pattern for every hidden directory under the home was not adopted, because one raw report quotes a public attack that names such paths and the pattern would flag it | `validate_docs.py` |
| R2-C-8 | Low | Low | Accepted | The validate workflow now also runs when the facts workflow changes and compares each workflow with its source. The origin check is anchored, and the stale "t1 to t6" in the digest is fixed | CI, `sync_to_github.ps1`, digest |

## How the uncertain points were checked

- **Export cancellation (R2-B-1).** The Power BI Reports reference lists Export To File, Get Export To File Status and Get File Of Export To File, and no operation that mentions cancelling. The Learn page's only cancellation is a client-side token in the sample code.
- **The budget stop (R2-B-2).** GitHub's page says that an organization budget limits metered charges, that usage billed to an organization from an App counts against it, and that without the stop setting "the budget only sends alerts and app spending continues after the limit is reached". It says a user-level budget "always" stops usage.
- **The proxy ceilings (R2-B-3).** The firewall's budget module decodes a signed capability with `maxRequests` and `maxTokens` claims and rejects a request that exceeds them. Whether the pinned gh-aw path lets us set those is not documented, so it is a spike question and not a claim.
- **A pass that persists (R2-B-8).** No source says what happens to a check after a review is dismissed. The design assumed it persists, which is the safe assumption to design against, and N11 now tests it.
- **The reaction to R2-A-1.** A merge-time audit cannot be made preventive: GitHub has no hook before a merge, other than a merge queue, which the design keeps off. So the preventive answer is the native count of two, and the audit stays a detective control.

## Found while fixing (not raised by a reviewer)

1. The fact checker's new "absent" mode would have passed vacuously on a missing page, which is the bug R2-C-1 reported. It was introduced in round 1 and found only by a second reviewer reading the code.
2. A fix to the publish script (R2-C-2) showed that `-NoPush` leaves a local commit that the next run would have pushed unscanned. The fold-away step covers that case too.
3. The private list now has one canonical location. The old copy is marked superseded so that the two cannot drift apart.

## Still open after round 2

As after round 1, these are spike outputs and cannot be settled by reading: the approval window (N11), whether the pinned gh-aw path can set the proxy ceilings (S9), whether the budget stop setting refuses a request (S9), which item types outbound access protection accepts (S2), whether an Entra subject that follows a repository rename breaks trust as designed (S2), whether suspend and resume need the `write` action (S8), and unattended data agent publishing (S6).
