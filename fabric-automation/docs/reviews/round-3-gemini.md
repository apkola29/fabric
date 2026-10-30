# Verification round 3: Gemini 4 Argon

Lens: consistency and the closure of the round-2 logic fixes. The reviewer had not seen rounds 1 or 2. It read a frozen copy of the published commit `c8c18b4198` and replied inline. This is the reply condensed; line numbers refer to that commit. The disposition of each finding is in [round-3-findings.md](round-3-findings.md).

## Findings

| ID | Severity | Where | Evidence | Why it matters | Concrete fix |
|---|---|---|---|---|---|
| R3-A-1 | High | Design 3.3 (the lifecycle prose and diagram) and 3.6 | A PR is marked ready for review when every automated check is green, and review feedback sends the run from AWAITING_HUMAN back to SPECIFIED | Once marked ready in PUBLISHING, the PR is never converted back to a draft and `factory/evidence` is never failed when the run re-enters SPECIFIED, or later escalates during a revision. The earlier head still has passing checks, and a comment review does not dismiss an earlier approval, so a maintainer can merge the stale commit in the middle of a revision | On the transition out of AWAITING_HUMAN to SPECIFIED (or ESCALATED), convert the PR back to a draft and fail `factory/evidence` and `factory/approval-policy` on the current head before the revision starts |
| R3-A-2 | Medium | Design 3.3 (preflight), 3.5 (identity table), 3.6 | The text says the App needs the organisation Members permission for the team events, and the preflight asserts it | The identity table omits the Members read permission from the publisher, and nothing requires verifying that the membership and team webhook events are subscribed. A permission without the subscription silently drops the 5-minute team-change bound to the sweep (up to 10 minutes) | Add the Members read permission and the membership and team subscriptions to the publisher in 3.5, and assert the subscriptions in the preflight |
| R3-A-3 | Medium | Design 3.3 (state list, deadline) | "From any working state (IMPLEMENTING to PUBLISHING)" and "Each run also has a deadline" | (1) The first range omits RECEIVED, VALIDATED, SPECIFIED, PLANNED and TEST_AUTHORING, so early states have no defined exit to ESCALATED on an infrastructure failure or budget exhaustion. (2) A wall-clock deadline of hours would kill runs that wait for a human (7 and 14 days) | Define working states everywhere as every non-terminal state except NEEDS_INFO, APPROVAL and AWAITING_HUMAN, and make the deadline count working-state time only |
| R3-A-4 | Medium | Design 3.3 (locks, terminal table, lifetimes) | Locks are held from PLANNED until the PR is merged or closed, each carrying the run ID and the PR number | (1) No PR exists at PLANNED, so the PR number needs a second write that is not described. (2) A revision that adds an item path cannot add a row to an existing batch atomically, and risks a deadlock. (3) In ESCALATED, "a draft PR keeps them until it is closed" has no auto-close, so locks could be held indefinitely | Acquire at PLANNED with the run ID and add the PR number at PUBLISHING, apply the 14-day idle close to the ESCALATED draft PR, and make a scope expansion release and re-acquire the full sorted batch atomically |
| R3-A-5 | Low | Design 3.6 (N2), 3.5 | If N2 triggers the fork fallback, the publisher "gets branch rights only on a factory-owned fork and opens a cross-repo PR" | The publisher must still open PRs, post the required checks and run the approval-policy check on the target repository, so "no factory token has write on the target repository" conflicts with its checks, statuses and pull-request write | Say that the fallback removes contents write on the target repository from the publisher and keeps pull-request, checks and statuses write |
| R3-A-6 | Low | Design 8 (traceability), requirements NFR-10 | NFR-10 is traced to 3.7, 3.14 and 3.16 | None of those sections, nor S3 or S8, states the targets of 30 minutes for a small change and 2 hours for a medium one | State the NFR-10 targets in S3 (and 3.16) so that Phase 0 measures them |

## Latest fixes checked

- **Approval window:** closed with a reservation. The 60 second and 5 minute bounds, the active 5-minute sweep, the 10-minute preflight check, the detective merge-time audit, the T2 gating and the two-approver fallback are sound and testable in N11 and S11. The reservation is the missing Members permission in 3.5 and the webhook subscription check (R3-A-2).
- **Lifecycle:** closed with a reservation. The ordered exclusive guards, the compare-and-swap terminal transitions, the human-wait exemptions and the APPROVAL exits are sound. The reservations are the PR re-drafting and evidence voiding on AWAITING_HUMAN to SPECIFIED (R3-A-1) and the run deadline against human waits (R3-A-3).
- **Locks and expiry:** closed with a reservation. The 72-hour contradiction is gone, workspace expiry starts at creation, and cancel tears down at once. The reservations are the missing close for an ESCALATED draft PR and the lock update on a scope change (R3-A-4).
- **Budget story:** closed. Sections 3.14, I-3, 3.16, 4.1, 4.3, S9, D-21 and NFR-09 are consistent, and nothing claims a hard per-run D0 bound before S9.
- **Trusted requester:** closed. Defined in 3.12 with fail-closed routing, and the reviewer preview runs B5 for data agents only.
- **GitHub-side idempotency:** closed. Expected-head commits, and resume lookups by head branch, by name and head SHA, and by hidden marker, are falsifiable in S5.

## Checked and sound

- A spot-check of 12 requirements and the six success criteria matched their cited sections, except NFR-10.
- Every invariant has a test and a fallback, and every spike has a falsifiable criterion and a phase rule.
- Golden-set integrity (3.15) and the scoping of FR-39 in 5.2 are accurate.
- Stale-worker fencing closes the non-transactional Fabric window.

## Could not verify

- What GitHub does when a ready PR is converted back to a draft while a merge is in flight (S11).
- Whether the pinned gh-aw compiler exposes the proxy's request and token ceilings (S9).
- Live service-principal behaviour for Delete Recoverable Item, and outbound access protection with reports (S2).

Verdict from the reviewer: ready after fixes, with 0 critical, 1 high, 3 medium and 2 low.
