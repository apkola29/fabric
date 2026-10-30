# Fabric Code Factory — Decision register

Version 0.2 · 2026-10-30 · Status: proposals after the three-model design review. v0.1 is in `archive/02-decision-register-v0.1.md`. Each decision below has the position that design v0.2 takes, what closes it, and what changed since v0.1. Nothing here is final until the Phase 0 spikes named in "Closed by" have passed.

## Principles

1. Reuse before rebuild: official Fabric skills and MCP tools first, factory-authored skills only where there is a gap.
2. Deterministic outer loop. Agent loops run only inside bounded steps.
3. Agents propose, the executor disposes. Agents emit declarative changes. A policy-enforcing executor applies them, and it takes a run ID, never agent-chosen arguments.
4. Least privilege, no standing secrets, separation of duties. The author of a change never approves it.
5. Everything is idempotent, resumable and auditable. A host restart must not lose or duplicate work.
6. Evidence over claims. Every gate produces an artifact a reviewer can open.
7. Humans approve. Promotion beyond dev stays manual in the pilot.
8. Seams, not lock-in: Git host, intake channel, model gateway, runtime and workload packs are replaceable.
9. **v0.3:** Fail closed. A missing control, an unknown field or a timeout is a stop.

## Decisions

Status: **Proposed** = the position in design v0.2, pending the spikes. **Open** = needs an answer from the requester or a tenant admin. Evidence threads: T1 to T7 (research), O1 (grounding), XV (cross-verification), RV (design review), and the 2026-10-30 Learn and gh-aw re-checks in `reviews/disposition-log.md`.

| ID | Decision | Position in design v0.2 | Closed by | Changed since v0.1 | Status |
|---|---|---|---|---|---|
| D-01 | Orchestration style | Workflow-first state machine with bounded agent loops | RV (done), S5 | No | Proposed |
| D-02 | Runtime and hosting | Hybrid. GitHub is the governance plane. D0: GitHub Actions workers with the gh-aw agent substrate, plus an Azure storage account for state and evidence. D1: Durable Task Scheduler and an API Management gateway, brought forward if S5 shows Actions resumption is too brittle | S5, S7 | Yes. D0 now includes a storage account | Proposed |
| D-03 | Durable state and resume | One authoritative run store (Azure Table Storage: ETag compare-and-swap, fenced leases, operation intents) and a scheduled reconciler from D0. The Git ledger is a projection. D1 keeps the store | S5 | Yes (A-04, O-04, F-15, X-12) | Proposed |
| D-04 | Agent engine | D0: gh-aw in strict mode with the Copilot engine, if S7 shows its API proxy keeps the engine token away from the agent. Its defaults are wider than ours, so the workflow pins `network: {}` and a minimal safe-output set (no merge, no branch push, no `create-issue`). Plain headless Copilot CLI only if S7 proves equal isolation. D1: Copilot SDK in our own pinned container image. Agent Framework only if D1 needs a multi-agent graph, and then with a gateway adapter, because its provider table has no Grok provider and Foundry has no Gemini. The Claude Agent SDK is not added: one harness already reaches all four model families | S7, S9 | Yes. The old rationale (Claude Code cannot route to other vendors) was wrong for stateless verifier calls (F-19) | Proposed |
| D-05 | Multi-model verification | Verifiers are read-only and tool-less, from a family other than the implementer's. Verdicts use a strict schema, trusted code joins them to criterion IDs and ignores unknown fields, and they are advisory: they can add a block, never remove one | S9 | Yes (X-15) | Proposed |
| D-06 | Intake channel | GitHub issue form, with a server-side alias allow-list, a restricted slug, no link fetching in secret-bearing jobs, and a deterministic secret and PII scan before any model call | Review (done), S9 | Yes (X-07, X-17) | Proposed |
| D-07 | Spec, plan and clarification | Structured spec with Given, When, Then. Plan first, then classify, then approve an immutable digest of spec and plan. One batched clarification round from a fixed list of ambiguity types. Review feedback re-enters through the spec | Review (done) | Yes (A-06, F-16, X-08) | Proposed |
| D-08 | Git model and GitHub controls | HR-1. Branch per requirement, one writer, signed commits. Four rulesets: restrict updates on `main` (human bypass), review and checks on `main` (no bypass), `factory/*` writable only by the publisher App (publisher bypass), and signed commits with no force-push on `factory/*` (no bypass, so they bind the publisher too). A required approval-policy check pinned to the publisher App. Validation on the test-merge tree | S11 | Yes (A-07, A-08, A-09, X-09) | Proposed |
| D-09 | Git provider for the Fabric link | No longer on the validation path. It matters only for the one-time backup of a workspace to Git and any later dev sync. GitHub needs the tenant switch and a stored token. Azure DevOps works by default. **Needs the requester's answer** | Open question 7, S1 | Yes. Demoted from a blocker | Open |
| D-10 | Validation deployment path | Path B (`fabric-cicd`) for validation, preview and any factory-initiated deployment. Path A (Git-connected workspace) stays documented, with its failure modes, as the entry condition for any later automation. Dev deployment after a merge is outside v1 (D-32) | S3 (S4 non-blocking) | Yes (A-13, F-04, X-04) | Proposed |
| D-11 | Ephemeral environment and capacity | Dedicated sandbox capacity, no fallback to a shared one. Ordered build (seed, SQL endpoint, models and reports). Four lifetimes. Leased runner pool. Teardown by permanent item delete as workspace Admin, then workspace delete. Custom suspend and resume role | S2, S8 | Yes (F-01, F-03, A-05, A-12, X-10) | Proposed |
| D-12 | Test data strategy | Synthetic, unlabelled, from pinned generator profiles per target. A change that needs data the fixtures lack stops for a human to extend the profile | Review (done), S3 | Yes (F-11, X-03) | Proposed |
| D-13 | Quality gate catalogue | Per pack as in design 3.10, with a capability matrix. A combination the matrix does not support is refused. Thresholds are calibrated in Phase 1 | Phase 1 | Yes (A-18, F-09) | Proposed |
| D-14 | Executor and tool surface | Typed operations that take a run ID and a step only. A full deployment manifest is validated first. REST-first when unattended. MCP is author-side tooling. The executor's wrapper injects the vendor telemetry header | S2, S3, S10 | Yes (X-01, A-02, F-10) | Proposed |
| D-15 | Identity and secrets | OIDC federation. `fcf-deployer`, a leased pool of `fcf-runner` principals, a custom capacity role, a state identity with table access only. No write-capable Git credential in Fabric. A run-as proof in S2 | S2 | Yes (A-05, X-04, X-10) | Proposed |
| D-16 | Sandbox and network isolation | The gh-aw substrate in strict mode (firewall, API proxy, MCP gateway, SafeOutputs), or an ephemeral self-hosted runner behind an egress proxy with a broker. Proven in S7. **No Phase 1 on hosted runners until it is** | S7 | Yes (X-02, A-14, F-13) | Proposed |
| D-17 | Untrusted intake handling | HR-4. Intake text is data. Plan-then-execute. A fixed-enum sanitizer between stages | S7 | Yes (X-03) | Proposed |
| D-18 | Knowledge pack | Pinned official plugins plus a factory plugin. `fabriciq-ontology-cli` is quarantined. An immutable executor image runs no repo scripts. Actions are pinned by SHA | S10 | Yes (F-17, X-14) | Proposed |
| D-19 | Evaluating the factory | Golden, red-team, regression, shadow, canary and drift probes. The red-team set runs in CI before the first live intake | Phase 1 readiness | Yes (F-12) | Proposed |
| D-20 | Observability and audit | Run ID equals trace ID. Run store, plus an immutable evidence container with a time-based retention policy from D0. Detections in design 4.4 | Phase 1 readiness | Yes (A-17, Grok detections) | Proposed |
| D-21 | Cost and runaway controls | Atomic counters: reserve worst-case, reconcile after. The soft D0 credit cap gives a stated bounded overshoot that the owner must approve. The organization budget is the hard stop | S9 | Yes (A-15, X-11) | Proposed |
| D-22 | Reviewer ergonomics and evidence bundle | One-page, risk-ranked evidence from artifacts. Approval-policy check. Canary PRs. A reviewer preview on demand | Phase 1 | Yes (FR-42) | Proposed |
| D-23 | Promotion beyond dev | Manual. Nothing beyond the sandbox is automated in v1 | Review (done) | No | Proposed |
| D-24 | Workload-pack roadmap | Stage 1: semantic model and report, T0 and T1. Stage 2: data agent and ontology, with T2. Later: notebook, pipeline, lakehouse, warehouse. The data-agent pack has no official skill and is factory-authored | Review (done) | Yes (F-06) | Proposed |
| D-25 | Authoritative state store | Azure Table Storage with Entra authentication. Alternatives: Cosmos DB (more cost), Durable Task Scheduler state (D1), a Git ledger (rejected: no compare-and-swap) | S5 | New | Proposed |
| D-26 | Test format and harness | Declarative assertions (query, expected table, tolerance, structure) run by a pinned harness. No agent-supplied test code in the credentialed executor. Arbitrary-code tests wait for Phase 4 and run only inside the sandbox workspace | S3 | New (A-01) | Proposed |
| D-27 | Evidence store | An immutable blob container with a time-based retention policy. Attestations prove provenance only | S11 | New (A-17) | Proposed |
| D-28 | Baseline and repeatability | Baseline evidence is cached by base commit, fixture digest, harness version and parameters. A fresh-environment repeat runs at T2 only. Same-environment idempotency is a separate test | S3 | New (A-10) | Proposed |
| D-29 | Capability matrix and refusal | A per-pack matrix decides admission. A model with RLS or SSO is refused for unattended validation | S2, S6 | New (A-18, F-02) | Proposed |
| D-30 | Component and control naming | Components K1 to K12. Controls C1 to C15. Gates G1 to G16. Spikes S1 to S11. Pilot success criteria PS-1 to PS-6. Hard rules HR-1 to HR-12 | none | New | Proposed |
| D-31 | Human-step policy | A validation step that needs a human is allowed only as an explicit, recorded exception. It never counts as unattended validation | S6 | New (A-18) | Proposed |
| D-32 | Dev deployment after a merge | Outside v1. A person or the team's pipeline does it. Entry conditions for automating it (Phase 3): a read-only single-repo Git credential, conflict handling (`PreferRemote`, `allowOverrideItems`), post-sync binding, activation and refresh, and a parity check | S4 | New (F-04, X-04, A-13) | Proposed |

## Constraints that bind several decisions

- Fabric allows one writer per branch and one Git operation at a time per workspace (D-08, D-10, D-03).
- The MCP surface covers about half of the factory's operations (D-14, D-15).
- Item-type support in Git integration is mostly preview for the pilot types (D-10, D-24).
- Official skills assume interactive confirmation, and one plugin floats on `@latest` (D-14, D-16, D-18).
- Background agents in our own tooling were cancelled by a host restart (D-03).
- Variable libraries cannot bind semantic models or reports (D-10, D-11).
- A deleted workspace stays recoverable and billable for 7 to 90 days, and only a tenant admin can purge it (D-11).
- GitHub rulesets and the required checks posted by the publisher App are where separation of duties is enforced for the repository (D-08).

## Walk-through scenarios to stress the design

1. Add a year-over-year measure to a semantic model and a card to a report.
2. Add a column and update data agent instructions and sample questions.
3. Rename a column that five reports and a data agent depend on (breaking change).
4. A requirement that is too vague to implement (clarification policy).
5. An issue whose text tries to make the agent exfiltrate data or widen its own permissions (untrusted intake).
6. A requirement whose cheapest "fix" is to weaken or delete a failing test (test-integrity guard).
7. A run interrupted by a host restart halfway through validation (durability).
8. Two requirements that touch the same item at the same time (concurrency).
9. **v0.3:** A reviewer comments on a PR and the comment changes the scope (feedback re-entry).
10. **v0.3:** The worker is killed after Fabric accepted a job and before the checkpoint was written (ambiguous outcome).
11. **v0.3:** The requester also tries to approve the PR (separation of duties).
