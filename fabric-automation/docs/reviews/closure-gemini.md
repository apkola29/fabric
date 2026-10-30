# Closure check: Gemini 4 Argon (lens: completeness and Fabric fidelity)

Date 2026-10-30. Reviewer: Gemini 4 Argon (`rubber-duck` agent, read-only, web access). Judged design v0.2 against its own earlier CRITICAL and HIGH findings. Transcribed by the orchestrator in condensed form from the reviewer's inline reply. The disposition of each new problem is the orchestrator's.

## Verdicts on the earlier CRITICAL and HIGH findings

| ID | Sev | Verdict | Settled in | Note |
|---|---|---|---|---|
| F-01 | CRIT | CLOSED | 3.7, 3.8, 3.10, 5.1 (S3) | Variable libraries removed from binding. Ordered build |
| F-02 | CRIT | CLOSED | 3.5, 3.9, 3.10 | Deployer owns binding and refresh. Runner pool. RLS and SSO refused |
| F-03 | CRIT | CLOSED | 3.7, 3.9, 5.1 (S2) | Hard delete as workspace Admin, then workspace delete |
| F-04 | CRIT | CLOSED | 3.6, 3.8, 5.3, 6 | Agrees with the modification (dev deployment leaves v1) |
| F-05 | HIGH | CLOSED | 3.7 (B5), 3.9, 3.10 | Deny-list and an executor publish step |
| F-06 | HIGH | CLOSED | 1, 3.10, 5.2 | Pilot stages aligned across documents |
| F-07 | HIGH | CLOSED | 3.1, 3.3, 3.5 | `sandbox` Environment has no required reviewers, and the preflight asserts others |
| F-08 | HIGH | CLOSED | 3.10, 5.1 | `exportToFile` primary, prerequisites in S2 and S3 |
| F-09 | HIGH | CLOSED | 3.10, 3.13 | `te` preview dropped |
| F-10 | HIGH | CLOSED | 3.9, 5.1 (S10) | FR-33 narrowed |
| F-11 | HIGH | CLOSED | 3.7, 3.9, 3.10 | Unlabelled fixtures, label deltas rejected |
| F-12 | HIGH | CLOSED | 4.2, 5.1, 5.2 | C8, C10, C12, C13, C14 gate Phase 1 |
| F-13 | HIGH | PARTLY | 3.1, 5.1 (S7) | `--readonly` and the EULA flag are mandated, but two I-tests contradict gh-aw's documented limits (NP-1) |

## New problems and their disposition

| # | Sev | Section | Problem | Disposition |
|---|---|---|---|---|
| NP-1 | HIGH | 3.1 (I-1, I-2, I-3) | gh-aw's architecture page says setup and pre-activation steps are not confined by the firewall, so "a canary from a setup step fails" cannot be required. Its auth reference says the API proxy is not a caller-authentication boundary for code already inside the agent container, and the Copilot engine uses `copilot-requests: write` on the job token, so "read-only permissions" must allow that | Accepted. I-1 allows `copilot-requests: write` and states that the raw credential is unreadable from inside the container. I-2 confines agent, child and MCP processes and treats setup, post and detection steps as pinned, reviewed trusted code with no network calls. I-3 states that code in the container can still use the proxy for inference, bounded by the budget |
| NP-2 | HIGH | 3.2 (K3), 3.3, 3.12 | Table Storage batches are atomic only within one table and one `PartitionKey`, up to 100 entities and 4 MiB. Keys forbid `/`, `\`, `#` and `?`, so raw item paths fail as `RowKey`. A budget reservation that updates a per-run row and a daily row is atomic only if both share a partition | Accepted. Keys are encoded. `Locks` use the target alias as partition, with at most 100 item rows per batch. `Budgets` keep the per-run and daily rows in one partition. Anything spanning tables relies on the intent-first protocol, not on a transaction |
| NP-3 | MED | 3.5, 3.6 (RS-C, N6) | GitHub signs an App's commits only when `author` and `committer` are omitted | Accepted. The publisher omits them and credits the requester only through the `Co-authored-by` trailer. N6 also tests a custom author |
| NP-4 | MED | 3.6 (RS-B, N2) | A merge queue merges on behalf of whoever enqueues, which might bypass RS-A's actor check | Accepted. v1 uses the up-to-date rule, not a merge queue. A merge queue is adopted only after N2 includes an enqueue attempt by the App |
| NP-5 | LOW | 3.7 (teardown) | Fabric documents no list endpoint for soft-deleted items, so a sweeper that resumes after a crash cannot find them | Accepted. Every created item GUID is recorded in the run store, and items are deleted with `hardDelete=true` first. The recorded GUIDs make a fallback purge possible |

## Readiness

Yes, v0.2 is ready for the Phase 0 spikes. The biggest remaining risk, in the reviewer's words: unattended service-principal and sandbox isolation gaps in practice, specifically whether gh-aw satisfies credential isolation in S7, and whether the tenant switches, `exportToFile` PNG and data-agent evaluation work end to end under service principals in S2, S3 and S6.
