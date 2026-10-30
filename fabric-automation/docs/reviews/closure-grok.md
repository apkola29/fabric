# Closure check: Grok 4.7 (lens: red team)

Date 2026-10-30. Reviewer: Grok 4.7 (`rubber-duck` agent, read-only, web access). Judged design v0.2 against its own earlier CRITICAL and HIGH findings. Transcribed by the orchestrator in condensed form from the reviewer's inline reply. The dispositions are the orchestrator's.

## Verdicts on the earlier CRITICAL and HIGH findings

| ID | Sev | Verdict | Settled in | Note |
|---|---|---|---|---|
| X-01 | CRIT | CLOSED | 3.9, HR-2 | Run ID and step only. GUID-matched registry |
| X-02 | CRIT | CLOSED | HR-3, 3.1 | No credential in the agent job, proven by S7 before Phase 1 |
| X-03 | HIGH | CLOSED | 3.11 | Declarative oracle, hidden checks outside artifacts, fixed-enum feedback, a held-out input |
| X-04 | HIGH | CLOSED | 3.5, 3.8 | Agrees with the modification: removing dev deployment is stricter than a read-only token |
| X-05 | HIGH | CLOSED | 3.9, 3.10 | Data-source allow-list, and S3 includes an exfiltration probe |
| X-06 | HIGH | PARTLY | 3.6, 3.12 | The approval-policy check closes "requester approves the bot's PR". The Fabric entitlement check is deferred to Phase 2. Accepted for a single-operator stage 1 with an onboarding list, but a user removed from the workspace yesterday stays a deputy until that check exists |
| X-07 | HIGH | CLOSED | 4.2, 3.12 | C8, C10, C12, C13 and C14 gate Phase 1. The scan precedes any model call |
| X-08 | HIGH | CLOSED | 3.3, 3.12 | The disposition log overclaimed: a T1 comment does not re-enter human approval, because T1 has none. The diff recompute still catches a rise to T2 or T3 |
| X-09 | HIGH | CLOSED (other writers, check-name spoofing) | 3.6 | The publisher's own bypass is a new hole (see item 1 below) |
| X-10 | HIGH | CLOSED | 3.5, S2 | Run-as proof, custom capacity role |

## New problems and their disposition

| # | Sev | Section | Problem | Disposition |
|---|---|---|---|---|
| 1 | HIGH | 3.6 | The publisher's bypass on RS-C skips signed commits and the force-push block too, so N6 and N9 cannot pass | Accepted. See GN-1 in `closure-gpt.md`: RS-C1 and RS-C2 |
| 2 | HIGH | 3.1 | gh-aw safe outputs include `merge-pull-request`, and `create-issue` is on unless disabled. The network default is not deny-all | Verified against the gh-aw reference pages. `merge-pull-request` (max 1, experimental) and `push-to-pull-request-branch` are built-in types, `create-issue` is auto-injected when no other safe output is set, and with no `network:` setting the default is `defaults` (basic infrastructure and common package mirrors), with GitHub's own domains allowed by default. Only `network: {}` blocks all access. Accepted: the workflow pins `network: {}` and a minimal safe-output set, new test I-8, and S7 fails if the compiled workflow grants more |
| 3 | MED | 3.7 (B4), 3.10 | Refresh runs as the Admin deployer, so agent-authored model expressions run with that identity. The runner split does not cover the main dynamic step | Accepted in modified form. A refresh runs the model's expressions with the credentials of the connections they use, and the policy already bars new sources, so the reach is the sandbox's synthetic data. S2 now tests whether a Contributor runner can take over and refresh. If the platform needs the owner, a refresh principal with Contributor on the run workspace and no right to create or delete workspaces does it. Added to the residual risks |

## Platform-claim checks (as asked)

| Claim | Reviewer's result and disposition |
|---|---|
| (a) RS-A "Restrict updates" blocks an App's API merge | Not established: the documentation defines it as a push restriction, not an API merge. N2 and the fork fallback already cover it. The RS-A row now says it is an assumption |
| (b) App commits verified | The design does not claim the Git Data API. `createCommitOnBranch` commits are signed and shown as verified (GitHub changelog, 2021-09-13). The older Git Data API path does not do this. Accepted: `createCommitOnBranch` is the one named route, and any other route is used only if S11 shows its commits verify |
| (c) Table Storage | Right within one partition, 100 entities and 4 MiB. State the cap and refuse a larger lock set. Accepted |
| (d) Fabric deletes | `hardDelete=true` needs Admin. Purging a recoverable item needs workspace write, not Admin, so the disposition overstated it. Accepted, and confirmed by my own fetch of the reference |
| (e) gh-aw substrate | Firewall and safe outputs exist. The sentence about each MCP server in its own container was unsure to the reviewer. The architecture page I fetched says the gateway "spawns isolated MCP-server containers", and the design now uses those words |

## Readiness

Yes. The biggest remaining risk, in the reviewer's words: the publisher was exempt from the signature and force-push rules that were meant to constrain it, so S11 would have failed or passed for the wrong reason. That is fixed by the RS-C split. The reviewers' other named risks (S7 and S2 to S3) are spike questions.
