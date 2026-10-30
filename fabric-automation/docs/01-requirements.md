# Fabric Code Factory — Requirements and constraints

Version 0.3 · 2026-10-30 · Status: revised after the three-model design review (70 findings, see `reviews/disposition-log.md`). Changes from v0.2 are marked **v0.3**. Pilot success criteria are now named PS-1 to PS-6, so that they no longer collide with the Phase 0 spikes S1 to S11.

## 1. Problem and vision

Fabric and Power BI teams spend much of their delivery effort on routine, well-understood changes: a new measure, a column, a report page, a pipeline step, a data agent instruction. Every change needs the same chain of work: understand the ask, change the right items, test them in isolation, check data quality, then get it reviewed.

The factory automates that chain for the whole Fabric estate, acting as an automation-led data engineer. A natural-language requirement goes in. A pull request that is ready to review comes out, with the evidence attached. A human approves.

"Silent" means no human interaction is needed while a run executes. People are told when a PR is ready or when the factory has to escalate.

## 2. Roles

| Role | Does what |
|---|---|
| Requester | Files a requirement through intake. Can cancel their own run. |
| Approver | Reviews and approves or rejects the PR. Never the same identity that authored it. |
| Factory operator | Owns the runtime, budgets, kill switch and knowledge pack. |
| Security / governance reviewer | Owns policy files and identity scopes. Reviews incidents. |
| Factory (agents) | Plans, implements, validates, verifies, opens the PR. Holds no standing secrets and cannot merge. |

## 3. Scope

In scope: the whole Fabric / Power BI estate through workload packs. Pilot slice (assumed), **v0.3: in two stages**: stage 1 is semantic models and reports (PBIR) with risk tiers T0 and T1. Stage 2 adds data agents and ontology and enables tier T2. Next slices: notebooks, pipelines and dataflows, lakehouse and warehouse SQL, real-time items, governance configuration.

Out of scope for the pilot:

- Production data or production workspaces.
- Autonomous merge or promotion beyond dev.
- **v0.3:** Deployment to the dev workspace after a merge. The team's existing route does it (a person pressing Update from Git, or its own pipeline). The factory can only show the result in a sandbox preview.
- Cross-tenant operation.
- Changes to the factory's own policies and workflows by the factory itself.
- **v0.3:** Changes to security, row-level or object-level security, permissions, connections, sensitivity labels, schedules and tenant or capacity settings (tier T3). The factory refuses them.

## 4. Functional requirements

Priority: M = must, S = should, C = could.

### Intake and triage

| ID | Pri | Requirement |
|---|---|---|
| FR-01 | M | Accept a requirement from an authenticated, allow-listed requester through one canonical intake (GitHub Issue form): goal, target repo/workspace/items, type (feature, change, fix), optional acceptance criteria, constraints, risk hints. |
| FR-02 | M | Normalize the request into a structured spec (goal, scope, testable acceptance criteria, assumptions, out of scope), stored in the repo and linked from the issue. |
| FR-03 | M | Run a definition-of-ready check and triage: workloads involved, size, risk tier, cost estimate. At most one batched clarification round; otherwise proceed and flag the assumptions in the PR. **v0.3:** the cost estimate is stated in tokens and capacity seconds. Clarification questions come from a fixed list of ambiguity types and never ask for credentials or free text to be pasted. |
| FR-04 | S | Detect duplicate and conflicting in-flight work (same items on other factory branches or open PRs) and serialize or reject. |
| FR-05 | M | Treat intake text, linked documents and tool output as untrusted data. It can never widen permissions, change policy or select credentials. **v0.3:** a deterministic secret and personal-data scan runs before any model sees the text, and the target alias comes from a server-side allow-list. No job that holds a secret fetches a link from the issue. |

### Planning

| ID | Pri | Requirement |
|---|---|---|
| FR-06 | M | Produce a plan before acting: items to change and their order, impact analysis over dependents and lineage, test plan, rollback plan. |
| FR-07 | M | Ground the work in a versioned knowledge pack: official Fabric / Power BI skills, house conventions, templates and golden examples, per workload. |

### Implementation

| ID | Pri | Requirement |
|---|---|---|
| FR-08 | M | Work only on a dedicated branch per requirement (for example `factory/<issue>-<slug>`). Never write to protected branches. Commits are small, attributed to the factory identity and carry a run ID. |
| FR-09 | M | Edit Fabric items in their Git definition formats (for example TMDL, PBIR, notebook, pipeline, data agent and ontology definitions) through workload packs. |
| FR-10 | S | Coordinate changes that span several items (for example column, measure, report visual, data agent) in dependency order. |

### Validation

| ID | Pri | Requirement |
|---|---|---|
| FR-11 | M | Static gates: definition validity, lint and best-practice rules, naming conventions, secret and PII scanning, reference and dependency checks. |
| FR-12 | M | Deploy the branch to an isolated, ephemeral Fabric workspace with a time to live. No shared or production workspace is touched. **v0.3:** the build is ordered: seed the synthetic data, wait for the SQL endpoint, then deploy models and reports (variable libraries cannot bind semantic models or reports). The deployment is validated as a complete manifest before anything is created. |
| FR-13 | M | Functional gates per workload: execute notebooks, pipelines and dataflows, run DAX and SQL tests, render reports, evaluate data agents against expected answers. |
| FR-14 | M | Data-quality gates: schema and contract checks, reconciliation and data diff against a baseline, re-run (idempotency) safety, performance and cost regression. |
| FR-15 | M | Iterate on failures inside hard budgets (iterations, wall-clock, model spend, capacity use). On exhaustion, stop and escalate with diagnostics. Never weaken a gate to get a pass. |
| FR-16 | M | Independent verification: a separate verifier context (a different model where policy allows) judges the diff against the spec, acceptance criteria and evidence. The verifier cannot modify the change. |
| FR-17 | M | Test-integrity guard: block changes that delete, skip or weaken tests, thresholds or gates, or that edit the factory's own policy and workflow files. |

### Delivery

| ID | Pri | Requirement |
|---|---|---|
| FR-18 | M | Open a pull request with an evidence bundle: spec, plan, diff summary, gate results with links, risk statement, rollback plan, cost, provenance (models, knowledge-pack and prompt versions, run ID). |
| FR-19 | M | Notify requester and approvers when the PR is ready or the run escalates. No other interaction is required. |
| FR-20 | S | Handle review feedback: reviewer comments start a bounded revision cycle on the same branch. **v0.3:** feedback from an authenticated code owner re-enters through the spec and the plan, at most 2 rounds. A change of scope voids earlier approval. |
| FR-21 | M | Never approve or merge its own PR. Promotion beyond dev is always a human action in the pilot. |
| FR-22 | S | Tear down ephemeral workspaces on merge, rejection or TTL expiry, and report residual cost. **v0.3:** teardown deletes every item permanently as workspace Admin before it deletes the workspace, because a deleted workspace stays recoverable (and billable) for at least 7 days and only a tenant admin can purge it. |

### Operations

| ID | Pri | Requirement |
|---|---|---|
| FR-23 | M | Kill switch: cancel any run from the issue; pause the whole factory with one action. |
| FR-24 | M | Durable runs: after a crash or host restart, resume from the last checkpoint without repeating side effects. **v0.3:** the system of record is a run store with compare-and-swap updates, fenced leases and a reconciler (FR-35). Git is a projection of it. |
| FR-25 | M | Full audit trail and traces per run, retained and tamper-evident. |
| FR-26 | S | Usage and cost reporting per run, requester and workload. |
| FR-27 | M | Knowledge-pack lifecycle: versioned skills, templates and conventions. Every change is evaluated against the golden suite before rollout and can be rolled back. Track upstream official skills and refresh them (the factory may propose refresh PRs, gated the same way). |
| FR-28 | M | Factory self-evaluation: golden requirement set, regression run on any change to prompts, skills, models or policies, and a shadow or canary mode before autonomy is widened. |

### Fabric surface and execution

| ID | Pri | Requirement |
|---|---|---|
| FR-29 | M | Reuse the official Microsoft Fabric and Power BI skills (`fabric-collection`: `fabric-skills`, `powerbi-authoring`) as the base of the knowledge pack. Install from the marketplace pinned to a tagged release, add the factory's own skills as a separate plugin, never edit vendor files, and re-run the gap analysis and the golden suite on every upgrade. |
| FR-30 | M | Prefer MCP tools where a capable one exists and supports a non-interactive identity (for example the local Power BI Authoring MCP). Several do not: the FabricIQ MCP, the hosted Core MCP and the ontology MCP are user-only, and no MCP server covers the Git lifecycle, deployment pipelines, notebook runs or report rendering. Unattended runs therefore use REST, `fab` or `fabric-cicd` with a service principal or managed identity through the executor, on an explicit allow-list, and record which surface was used. MCP remains author-side tooling. |
| FR-31 | M | A policy-enforcing executor sits between agents and the tenant. Agents emit declarative changes and run requests. The executor applies them with scoped identities, allow-lists, a plan or dry-run step, read-back verification (compare parsed content, not HTTP status), idempotency keys and run locks. Agents never hold tenant credentials or raw destructive tools. |
| FR-32 | S | Capacity lifecycle: resume a dedicated sandbox capacity on demand, pause it when idle, enforce a capacity-unit budget per run, and never validate on a shared demo or production capacity. |
| FR-33 | M | Honour vendor conventions centrally: **v0.3:** the executor's own REST and `fab` wrapper sends the skill's mandatory telemetry header on every Fabric call it makes for a skill-derived operation (including polls and retries). Calls made by `fabric-cicd`, which has its own HTTP client and does not set that header, are tagged at process level if that proves feasible (spike S10). Update checks are pinned or disabled in the sandbox. |
| FR-34 | S | Git discipline: one writer per branch, one Git operation at a time per workspace, head checks and poll-until-synced after every sync. **v0.3:** the factory only reads from factory-managed workspaces and reports drift between them and their Git branch. It does not sync the dev workspace after a merge in v1. If that is automated later (Phase 3), the Git credential in Fabric is read-only, scoped to one repository and short-lived, and the sync handles conflicts (`PreferRemote`, `allowOverrideItems`) and the post-sync steps that Update from Git does not do (bind connections, activate value sets, refresh). |

### Run integrity and control (new in v0.3)

| ID | Pri | Requirement |
|---|---|---|
| FR-35 | M | One authoritative run store (compare-and-swap, fenced leases, operation intents with provider IDs). A reconciler resumes stale runs. An ambiguous outcome after a lost response is resolved by querying the provider, and then by adopting, rebuilding or quarantining. |
| FR-36 | M | Four separate lifetimes: compute lease, item reservation, workspace expiry and the pull request. One must not end another. |
| FR-37 | M | A required approval-policy check enforces separation of duties: at least one eligible human approval (two for T2), never the requester and never a bot, bound to the head commit, the tier and the approved spec digest, and re-evaluated on every push or review. Required checks are pinned to the publishing App. |
| FR-38 | M | Plan first, then classify, then approve a digest of spec and plan. The tier is recomputed from the actual semantic diff. A higher tier or a wider scope voids the approval. |
| FR-39 | M | Test integrity by construction: the spec, fixtures, generators and oracle tests are frozen against the implementer after approval. Hidden checks are unreachable from the agent job. Failure feedback to the implementer is a fixed set of categories. At least one held-out input exists even for T1. Oracle tests are declarative data run by a pinned harness. |
| FR-40 | M | A complete deployment manifest (dependency closure, schedules removed, every reference and data source resolved against an allow-list and a connection catalogue) is validated before anything is created. The policy engine parses item definitions and rejects connection, role, label, schedule and external-URL changes anywhere in an item. |
| FR-41 | M | Fail closed. A preflight conformance check runs before every run (rulesets, environments, identity scopes, target capacity, egress canary). Any schema error, unknown field, timeout or missing control is a stop. |
| FR-42 | S | Reviewer preview on demand: a label re-provisions the sandbox result for a reviewer after its expiry, without agents. |
| FR-43 | M | A per-pack capability matrix (endpoint, effective identity, model features such as RLS or SSO, dependencies, refresh, render, evaluation). An unsupported combination is refused. A step that needs a human never counts as unattended validation. |
| FR-44 | M | Baseline evidence is cached by base commit, fixture digest, harness version and parameters. Evidence names both the base and the candidate commit, and is void if either moves. Validation runs on the test-merge tree. |

## 5. Non-functional requirements

| ID | Area | Requirement |
|---|---|---|
| NFR-01 | Security | Least privilege and short-lived credentials. No standing secrets. Identities scoped per run and per environment. Production data and workspaces are unreachable by the factory identity in the pilot. |
| NFR-02 | Security | Each run executes in a disposable sandbox with a network egress allow-list. No cross-run state except through the repo and the run store. **v0.3:** no model, Git or Fabric credential is reachable from the agent job, and egress deny covers every process, including MCP servers. Both are proven by test (spike S7) before any live issue is processed. |
| NFR-03 | Security | Separation of duties: the identity that authors a change cannot approve or merge it. Policy files are protected by CODEOWNERS and rulesets. |
| NFR-04 | Security | Data boundary: synthetic or sample data only in the pilot. Model-vendor policy tiers define which content may go to which model vendor. |
| NFR-05 | Security | Supply chain: pinned dependencies, restricted package sources, provenance for the knowledge pack. |
| NFR-06 | Reliability | At-least-once execution with idempotent side effects, bounded retries with backoff, and quarantine for runs that keep failing. |
| NFR-07 | Reliability | Concurrency control: no two runs mutate the same items or the same workspace. |
| NFR-08 | Observability | One trace ID from intake to merge. Structured logs. Metrics for time to PR, gate pass rates, acceptance rate, rework, escaped defects, cost per merged change. |
| NFR-09 | Cost | Hard per-run and per-day budgets for model spend, Fabric capacity and wall-clock. Ephemeral capacity is paused or released when idle. **v0.3:** budgets are atomic counters: reserve a worst-case cost before each dispatch, reconcile after. Where the platform cap is soft (the Copilot AI-credit cap can be exceeded by one response, and parallel requests add up), the design measures the overshoot and the owner approves the measured figure. |
| NFR-10 | Performance | Proposed targets: small change to PR in under 30 minutes, medium in under 2 hours. To be validated by the Phase 0 spikes. |
| NFR-11 | Extensibility | Workload packs are pluggable. Seams for Git host, intake channel, model gateway and runtime, so none is hard-wired. |
| NFR-12 | Reproducibility | The evidence bundle is enough for a human to re-run the gates locally or in CI. |
| NFR-13 | Usability | A reviewer can decide in minutes: a one-page, risk-ranked summary on top, with the evidence behind links. |
| NFR-14 | Governance | Sensitivity labels, workspace and tenant policies are honoured and never bypassed by the factory. **v0.3:** pilot fixtures are unlabelled synthetic data, and any change to a label is tier T3. |
| NFR-15 | Security | No floating dependencies: skills, MCP servers and CLIs are pinned by version or hash. No run-time `npx -y @latest` or global installs. Per-tool allow-lists on every MCP server. |
| NFR-16 | Security | Knowledge-pack and skill content is scanned for instruction-override phrasing and secrets before it is loaded, and re-scanned on every upgrade. |
| NFR-17 | Reliability | Destructive operations (replace-all definition updates, deletes, drops) need a plan, an allow-listed target and a recorded approval. Permanent deletion is never available to agents. **v0.3:** the executor's own teardown of a workspace it created is the one permitted permanent delete, and it is registry-bound. |
| NFR-18 | Security | **v0.3:** evidence, manifests and the audit trail live in storage with an enforced retention period from the first live run, independent of any identity that can delete branches or artifacts. Attestations prove provenance only. |
| NFR-19 | Security | **v0.3:** the minimum controls for authentication of intake, supply-chain pinning, model eligibility and audit (C8, C10, C12, C13) and the red-team set (C14) are demonstrated before the first live issue, not after the pilot starts. |

## 6. Constraints and assumptions

These were set by default because the requester was unavailable for the scoping questions. Each is to be re-confirmed.

| # | Assumption | Impact if wrong |
|---|---|---|
| A1 | Git provider is GitHub; Azure DevOps is a documented alternative. | Runtime and intake design shift to Azure DevOps. |
| A2 | Canonical intake is a GitHub Issues form. Other channels are normalized through a thin gateway later. | Adds a gateway earlier. |
| A3 | Pilot slice, **v0.3: in two stages.** Stage 1: semantic models and reports (PBIR), tiers T0 and T1. Stage 2: data agents and ontology, with T2 enabled. | Changes which workload packs and gates are built first. |
| A4 | Data boundary: synthetic or sample data in a dev capacity only. | Production data needs masking, tighter identity and a different risk model. |
| A5 | Content sensitivity: internal, demo or synthetic. | Customer content limits which model vendors may see it. |
| A6 | Autonomy ceiling: PR approval required, no promotion beyond dev. | Higher autonomy needs much stronger gates and evidence. |
| A7 | First audience is a personal proof of concept in a single tenant. | Team or customer use needs tenancy, onboarding and support design. |
| A8 | No live tenant discovery has been done. Feasibility is proven by Phase 0 spikes, not assumed. | Platform limits could force design changes. |
| A9 | Models: Sonnet 5.5 (max reasoning) leads. GPT 6.1 Sol, Gemini 4 Argon and Grok 4.7 verify. All four are reachable today through the Copilot agent harness. | Another gateway may be needed for an enterprise-controlled path. |
| A10 | The pilot tenant has one existing capacity, shared with demo workspaces. A dedicated small sandbox capacity is needed. | Validation could throttle or pause demos, or fail while the shared capacity is paused. |
| A11 | The Git provider choice depends on tenant settings. GitHub needs a tenant switch (off by default) and a personal access token stored in a Fabric connection. Azure DevOps works by default and supports a service principal credential. **v0.3:** this now affects only the one-time backup of the workspace to Git and any later automated dev sync, not the validation path. | The pilot may have to use Azure DevOps for the backup step. |
| A12 | Git integration status, checked against Learn on 2026-10-30 (the supported-items page, updated 2026-10-17): semantic model and report are preview, the ontology is listed and is preview, and data agents are listed with no preview tag while the data-agent source-control page still calls the feature preview. The installed skill reference had shown the ontology as absent. | Preview limits or API changes could break the pipeline. |
| A13 | The requester directed use of the official Fabric skills and, where needed, the Fabric Core and FabricIQ MCP servers. Only read-only calls have been made so far. | Writes and non-MCP (REST or CLI) live calls need explicit scoping and approval. |
| A14 | **v0.3:** An Azure subscription is available for a storage account (run store and immutable evidence), and Entra rights exist to create the factory identities and a custom role. | Without them the durable run store has to be built on another service, and Phase 0 slips. |
| A15 | **v0.3:** One operator is requester and approver in the proof of concept. This is a stated limit: that person can change any ruleset. The design's separation of duties is demonstrated with a second account, not relied on. | Real separation of duties needs a second person. |

Facts learned during this project that shape the requirements:

- A host restart cancelled every background agent and lost all unsaved work (2026-10-30). This is why FR-24 is a must, and why research agents now checkpoint to disk.
- GPT 6.1 Sol and Gemini 4 Argon sub-agents could not write files in the smoke test, so cross-verification output must be returned inline and persisted by the orchestrator.
- The Fabric MCP servers cover about half of the factory's operations. The Git lifecycle, deployment pipelines, notebook runs, variable libraries and report authoring are not covered, and no official skill covers Fabric data agents (see `research/raw/o1-fabric-surface-grounding.md`).
- The official skills assume an interactive confirmation that an unattended run does not have, and one plugin floats on `@latest` with all tools allowed. This is why FR-31, NFR-15 and NFR-17 exist.

## 7. Pilot success criteria (proposed, to be calibrated after Phase 0)

Named PS-1 to PS-6 from v0.3. Earlier drafts called them S1 to S6, which collided with the Phase 0 spikes.

| # | Criterion |
|---|---|
| PS-1 | At least 70% of a golden requirement set for the pilot slice ends in a PR that passes every gate within two iterations. |
| PS-2 | Zero policy violations: no write outside the factory branch and the ephemeral workspace, no secret in a diff or log. |
| PS-3 | At least 90% of seeded defects (a red-team set of bad requirements and regressions) are caught by a gate or by the verifier. |
| PS-4 | Median reviewer time per PR is 15 minutes or less. |
| PS-5 | At least 60% of PRs are accepted with at most one revision. |
| PS-6 | Cost per accepted change stays inside a budget the requester sets. |

## 8. Open questions for the requester

1. Is "silent" correct as defined: no interaction while a run executes, notification at PR-ready or escalation?
2. Who are the approvers, and is a named approver group required? **v0.3:** the design needs at least two people for T2 and a requester who is not the approver. With a single operator there is no real separation of duties (a stated limit).
3. Which repo and workspace are the pilot target? **v0.3:** the target needs a profile (item inventory, synthetic fixture package, connection catalogue entries, capability-matrix row, RLS and SSO flags).
4. Is it acceptable that internal, non-customer design content goes to GPT, Gemini and Grok through the Copilot harness?
5. What is the pilot budget for model spend and Fabric capacity? **v0.3:** and is the overshoot that S9 measures acceptable where the platform cap is soft (one response beyond the AI-credit limit, with parallel requests adding up)?
6. Is Azure DevOps required at any point?
7. Can the tenant admin enable "Users can sync workspace items with GitHub repositories", and is storing a fine-grained GitHub token in a Fabric connection acceptable? If not, the pilot should use Azure DevOps. **v0.3:** this is no longer on the critical path. It matters only for the one-time backup of the workspace to Git and for any later automated dev sync.
8. May we provision a dedicated small F-SKU sandbox capacity, or must the factory share an existing one? **v0.3:** the design refuses to fall back to a shared capacity.
9. Is "Git is the source of truth, no direct edits in factory-managed workspaces" acceptable? Fabric allows only one writer per branch.
10. May the factory use REST or CLI (`fab`, `az rest`) for operations the MCP servers cannot do (Git lifecycle, deployment pipelines, notebook runs), within an explicit allow-list?
11. **v0.3:** May we create an Azure storage account (run store, immutable evidence container), Entra app registrations and federated credentials for the factory identities, and a custom role that only suspends and resumes the sandbox capacity?
12. **v0.3:** Is deployment to dev after a merge acceptable as a human step in v1? (This is the design's assumption.)

## 9. Glossary

| Term | Meaning |
|---|---|
| Factory | The whole system: intake, orchestration, agents, gates, PR publishing. |
| Run | One execution of the factory for one requirement. |
| Workload pack | The skills, templates, gates and tools for one kind of Fabric item. |
| Knowledge pack | The versioned set of skills, conventions, templates and golden examples the agents are grounded in. |
| Gate | An automated check that must pass before a PR is marked ready. |
| Evidence bundle | The spec, plan, results, risk statement and provenance attached to a PR. |
| Ephemeral workspace | A per-branch Fabric workspace created for validation and deleted after. |
| Golden set | A fixed set of requirements with known-good outcomes, used to evaluate the factory itself. |
