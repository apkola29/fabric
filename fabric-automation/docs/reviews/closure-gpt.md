# Closure check: GPT 6.1 Sol (lens: architecture and feasibility)

Date 2026-10-30. Reviewer: GPT 6.1 Sol (`rubber-duck` agent, read-only, web access). Judged design v0.2 against its own earlier findings, all of them HIGH. Transcribed by the orchestrator in condensed form from the reviewer's inline reply. The dispositions are the orchestrator's. The reviewer notes that CLOSED means closed in the design, not that the required spikes have passed.

## Verdicts on the earlier HIGH findings

| ID | Verdict | Settled in | Note |
|---|---|---|---|
| A-01 | CLOSED | 3.9, 3.11 | Declarative assertions and a pinned harness |
| A-02 | CLOSED | 3.9 | Manifest admission covers unchanged definitions |
| A-03 | CLOSED | 3.3, S5 | Intents, provider reconciliation, quarantine |
| A-04 | PARTLY | 3.2, 3.3 | An ETag fences writes to the store, not calls to Fabric. Specify how an old worker is stopped or isolated at handover |
| A-05 | CLOSED | 3.5 | Exclusive runner leases with revoke before reuse |
| A-06 | CLOSED | 3.3, 3.12 | Plan, then classify, then approve a digest |
| A-07 | PARTLY | 3.6 | Main's separation is coherent, but the bypass on RS-C defeats its own integrity rules (see GN-1) |
| A-08 | CLOSED | 3.6 | Approval-policy check excludes requester and bots |
| A-09 | CLOSED | 3.3, 3.6 | Test-merge validation, SHA-bound evidence |
| A-10 | CLOSED | 3.7, 3.11 | Accepts the modified baseline cache |
| A-11 | CLOSED | 3.3, 3.16 | Watchdog, finalizers, quarantine |
| A-12 | CLOSED | 3.3, 3.7 | Four separate lifetimes, rebuildable preview |
| A-13 | CLOSED | 3.8 | Path B throughout, dev deployment out of v1 |
| A-14 | CLOSED | 3.1 | S7 must prove it |
| A-15 | CLOSED | 3.14, 10 | Accepts reserve and reconcile, with an owner-approved overshoot. S9 must quantify the bound |
| A-16 | CLOSED | 4.2, 5.1, 5.2 | Prerequisites now gate live operation |
| A-17 | CLOSED | 3.16 | Retention-controlled storage |
| A-18 | CLOSED | 3.10, 5.1 | Capability matrix, RLS and SSO refusals |

## New problems and their disposition

| # | Sev | Section | Problem | Disposition |
|---|---|---|---|---|
| GN-1 | HIGH | 3.6 | The publisher is the bypass actor on RS-C, and a bypass skips every rule in that ruleset. The publisher could push unsigned commits and force-push, so N6 and N9 cannot pass as written | Accepted. RS-C is split. RS-C1 (restrict creation, update and deletion) has the publisher as bypass. RS-C2 (signed commits, block force pushes) has no bypass and so binds the publisher. N6 and N9 are run with the publisher's own token. Four rulesets in all. Grok raised the same finding |
| GN-2 | HIGH | 3.6 | "Marked ready only when every required check is green" includes `factory/approval-policy`, which passes only after a human approves. Approval would become a precondition of the ready notification | Accepted. Ready for review depends on the automated checks only (`factory/static`, `dynamic`, `integrity`, `evidence` and normal CI). The approval-policy check gates the merge, and reports "awaiting eligible approval" until then. The definition of done is reworded to match |
| GN-3 | MED | 3.5, 3.7 | The disposition log said that purging a soft-deleted item needs workspace Admin. The REST reference for Delete Recoverable Item documents workspace write permission | Accepted after I fetched the reference myself: it says write permission and lists service-principal support, while the admin pages say Admin. The Learn pages disagree. The design now records the conflict, S2 tests it, the deployer (Admin) purges either way, and the privilege model does not rely on a Contributor being unable to purge |

## Platform-claim checks (as asked)

| Claim | Reviewer's result |
|---|---|
| (a) Three rulesets, and RS-A blocking an App's API merge | Ruleset layering is documented. The exact effect on an App's API merge is unsure until N2, so N2 stays mandatory |
| (b) App commits shown verified | Conditional: GitHub documents verification for an App's authenticated request with no custom author, committer or signature data. Verify the exact route in N6 |
| (c) Table Storage batches and ETags | Correct within one table and one partition, up to 100 entities and 4 MiB. No cross-table transaction and no fencing of external services |
| (d) Fabric deletes | Both routes exist. `hardDelete=true` needs workspace Admin. The recoverable-items delete documents workspace write permission |
| (e) gh-aw substrate | Matches its architecture documentation, including trusted and unconfined setup, post and output steps. Copilot-specific credential separation is unsure until S7 |

## Readiness

Yes, v0.2 is sufficient to start isolated Phase 0 spikes. The biggest remaining risk, in the reviewer's words: whether S7 can actually demonstrate credential-free Copilot execution on the selected substrate.
