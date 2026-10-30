# Orchestrator self-review of design v0.1 (written before the panel reports arrived)

Date 2026-10-30. Reviewer: Sonnet 5.5, max reasoning, author of the design. A self-review is weaker than an independent one. It is recorded so that the panel's findings can be compared with what the author already suspected, and so that nothing the author knew is lost.

Severity: HIGH = fix before Phase 0 or 1. MEDIUM = fix before Phase 2. LOW = polish.

| ID | Sev | Location | Finding | Recommended change |
|---|---|---|---|---|
| O-01 | HIGH | 3.7, 3.9, HR-8 | HR-8 puts connections out of autonomous scope, yet the executor must bind a deployed semantic model to a data source in the sandbox (refresh needs a connection or credentials). The design does not say who creates those connections | Define a sandbox connection catalogue: a small set of named connections provisioned by a human administrator and referenced by name through the parameter file. The executor binds only from the catalogue. Agent patches still cannot add or alter connections |
| O-02 | HIGH | 3.1, 3.2 (C3), D-16 | The design says the sandbox has default-deny egress, but GitHub-hosted runners cannot enforce an egress allow-list natively. D0 on hosted runners would have open egress | State how egress is enforced in D0: the gh-aw firewall, or ephemeral self-hosted runners behind an egress proxy or firewall. Decide in spike S7. Until decided, treat egress as monitored, and rely on the absence of secrets in the sandbox |
| O-03 | HIGH | 3.6 | "Requester is not approver" cannot be expressed in a GitHub ruleset: the PR author is the factory's App, so the requester could approve the PR | Add a required status check, owned by the publisher, that fails when the only approvals come from the requester. It re-evaluates on review events and reads the requester from the ledger |
| O-04 | HIGH | 3.2 (C2), 3.3, 3.16 | In D0 nothing notices a dead run and restarts it. The design relies on resumability but names no trigger | Add a watchdog: a scheduled workflow reads the ledger, finds runs whose last event is older than the stage timeout, and re-dispatches from the last completed stage. Bounded attempts, then ESCALATED |
| O-05 | MEDIUM | 3.2 (C2), 3.3 | The ledger "on an orphan branch" invites push conflicts between jobs, workflow triggers from ledger commits, and unbounded growth | One ledger file per run, written only by the publisher, commits marked to skip CI, signed. Define retention and compaction |
| O-06 | MEDIUM | 3.11 | Hidden checks are said to live "in the run's audit store". In D0 an Actions artifact is readable by anyone with repo read access | Store hidden checks where only the executor can read them (an environment-scoped secret or a vault). Publish them in the evidence bundle after the run. Return only pass or fail and a category to the implementer |
| O-07 | MEDIUM | 4.3 | Sandbox validation proves logic on synthetic data. It does not prove behaviour on real data volumes, skew or performance. The design does not state this residual risk | Add it to the accepted residual risks. Require a human smoke test after the dev sync. Consider masked-sample validation as a later phase |
| O-08 | MEDIUM | 3.9, 3.12 | Size caps in changed lines are noisy for generated TMDL and PBIR (one visual can be hundreds of JSON lines) | Express caps in semantic units (items, measures, visuals, pages) plus a line cap. Calibrate in Phase 1 |
| O-09 | MEDIUM | 3.16 | Kill-switch behaviour is undefined for an in-flight executor call or a deployed sandbox workspace | Halt stops at the next stage boundary. Define whether the workspace is torn down at once or left for the sweeper. Test both in the drill |
| O-10 | MEDIUM | 3.10 | The identity used by the headless report preview is unknown. `exportToFile` works with a service principal but needs a tenant switch and a capacity | Spike S3 picks one route and records the identity it needs |
| O-11 | LOW | 3.5 | In D0 the model token available to the agent is the workflow's `GITHUB_TOKEN` | Set workflow `permissions` to `copilot-requests: write` only. Cap spend |
| O-12 | LOW | 3.5, 3.16 | Storage, scope and rotation of the publisher App key and the commit-signing key are not specified | Hold them only in a separate publisher job or environment with protection rules. Add rotation to the incident drill |

Other points the author considers weaker than the design implies:

- **Path B versus path A** is argued from documentation, not from a run. The parity job mitigates it, but the choice could flip after spikes S3 and S4.
- **The hidden-check design** adds machinery. A simpler start is visible oracle tests only for T1 (already the plan), but the cost-benefit for T2 is an assumption.
- **Phase 0 is sized M** for ten spikes, three of which need tenant admin actions the requester may not control. It may take longer.
- **Model-per-role defaults** follow the stated operating model and the benchmark for DAX writing suggests a different split might do better. The golden suite should decide.
