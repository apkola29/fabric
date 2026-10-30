# Disposition log: design v0.1 review findings

Date 2026-10-30. Author: Sonnet 5.5 (orchestrator, design author). Input: the four registers `review-gemini.md` (F), `review-gpt.md` (A), `review-grok.md` (X) and `review-orchestrator.md` (O), 70 findings in all. Output: design v0.2 (`04-design.md`), requirements v0.3, decision register v0.2.

## How to read this

- **Accepted**: the change is made as recommended or equivalently.
- **Accepted, modified**: the problem is accepted, and the fix differs from the recommendation. The reason is in the row.
- **Accepted, phased**: accepted, with part of the work placed in a later phase. The row says which part.
- **Merged**: the finding duplicates another and is closed by the same change.
- Nothing was rejected. Each finding was checked against the design text and, where it rested on a platform fact, against the cross-verification results. Four groups of facts I re-fetched myself from Microsoft Learn or the gh-aw documentation on 2026-10-30 (marked **[V]**).
- "Addressed in" uses v0.2 section numbers. Components are now named K1 to K12 (v0.1 called them C1 to C11, which collided with the security controls C1 to C15).

## Facts re-checked while writing this log [V]

1. **Variable libraries cannot bind semantic models or reports.** The Learn overview lists the supported consumers: pipeline, lakehouse shortcut, notebook, Dataflow Gen2, copy job, user data functions, eventstream, deployment-plan actions and Plan. This confirms F-01.
2. **Deletion mechanics.** `DELETE /v1/workspaces/{ws}/items/{id}?hardDelete=true` deletes permanently and needs the workspace Admin role. The default is a soft delete for supported types. `DELETE /v1/workspaces/{ws}/recoverableItems/{id}` purges an already soft-deleted item. The admin pages say this needs workspace Admin, but the REST reference says workspace write permission and lists service-principal support, so the two Learn pages disagree (found in the closure check, then confirmed by fetching the reference). S2 tests it. Soft-deleted items count towards the workspace item maximum and keep billing storage. Semantic models and reports are not in the soft-delete list, so deleting them is final. A deleted workspace can be restored or permanently deleted only by a tenant admin, in the portal, and it stays for 7 to 90 days. Lowering the tenant retention setting purges already-deleted workspaces at once. After a permanent item delete, OneLake keeps the data a further 7 days. The billing effect of that last point is unverified. This confirms F-03 and refines its fix.
3. **Bulk Import and Export Item Definitions APIs** (public preview since March 2026) exist, rebind dependencies by `logicalId`, and do not seed data, activate value sets or create shortcuts. Microsoft's own guidance is to prefer `fabric-cicd` for standard CI/CD, and to run automation as service principals. A semantic model that depends on a lakehouse SQL endpoint must be imported in a later batch than the lakehouse. This supports path B and the ordered build in §3.7.
4. **gh-aw architecture.** Its substrate is a network firewall, an API proxy (which may hold engine credentials) and an MCP gateway. Agent writes are buffered as artifacts by SafeOutputs and externalized by a later stage. Setup, post, detection and safe-output steps are trusted code and are not confined. A read-only `GITHUB_TOKEN` does not remove other credentials. This is close to the zone model in v0.1, and it is why D-04 now names gh-aw in strict mode as the preferred D0 substrate, to be proven in S7.

## Summary

| Source | Findings | Accepted | Accepted, modified | Accepted, phased | Merged |
|---|---|---|---|---|---|
| Gemini (F) | 20 | 15 | 2 | 0 | 3 |
| GPT (A) | 20 | 11 | 3 | 2 | 4 |
| Grok (X) | 18 | 11 | 1 | 1 | 5 |
| Orchestrator (O) | 12 | 7 | 0 | 0 | 5 |
| **Total** | **70** | **44** | **6** | **3** | **17** |

Modified fixes: F-04 and X-04 (path B, a read-only credential if path A is ever used, and dev deployment taken out of v1), F-15 (the branch ledger becomes a projection of a run store), A-04 (Table Storage run store), A-10 (baseline cache instead of a standing baseline), A-15 (bounded overshoot instead of a hard cap). Phased: A-19 and A-20 (Phase 2) and X-06 (entitlement check, Phase 2).

## Gemini (lens: completeness and Fabric fidelity)

| ID | Sev | Decision | Reason and change | Addressed in |
|---|---|---|---|---|
| F-01 | CRIT | Accepted [V] | Value sets are dropped from model and report binding. Binding uses `parameter.yml` (`find_replace`, strict `semantic_model_binding`, dynamic `$sqlendpoint`). The build is ordered: create and seed the synthetic lakehouse, wait for the SQL endpoint, then deploy models and reports | 3.7, 3.8, 3.10, 5.1 (S3) |
| F-02 | CRIT | Accepted | The deployer creates, deploys, seeds, binds, refreshes and tears down. The runner only runs jobs and non-RLS queries. A model with RLS or SSO is refused for unattended validation | 3.5, 3.9, 3.10 |
| F-03 | CRIT | Accepted, refined [V] | Teardown order: cancel jobs, revoke the runner, hard-delete every item as workspace Admin (`hardDelete=true`), purge anything soft-deleted, then delete the empty workspace. The factory never touches tenant retention settings | 3.7, 3.9, 4.3, 5.1 (S2, S8) |
| F-04 | CRIT | Accepted, modified | Dev deployment after merge leaves v1 scope: the team's existing route (a human or pipeline) does it. The factory validates with path B and offers an on-demand preview. Path A's failure modes (`PreferRemote`, `allowOverrideItems`, post-sync binding and activation) are written down as the entry conditions for ever automating it | 3.8, 6 (D-10), 5.3 |
| F-05 | HIGH | Accepted | `published/**` and `publish_info.json` join the deny-list. A `publish` step belongs to the data-agent post-deploy and is run by the executor | 3.9, 3.10 |
| F-06 | HIGH | Accepted | Pilot stage 1 is semantic model and report, T0 and T1. Stage 2 adds data agent and ontology with T2. A3 and D-24 are aligned | 5.2, requirements A3 |
| F-07 | HIGH | Accepted | The `sandbox` Environment has no required reviewers and is limited to `factory/*` branches. Any dev-side Environment has reviewers, and a preflight asserts it | 3.1, 3.5, 3.3 |
| F-08 | HIGH | Accepted | `exportToFile` PNG is the primary render gate. Its prerequisites (tenant switch, capacity type, model on PPU, page and visual caps, labels, uncertified visuals) enter S2 and S3, and a static check for non-exportable visuals | 3.10, 5.1 |
| F-09 | HIGH | Accepted | Static tooling: Tabular Editor 2 CLI with Microsoft BPA rules, the Authoring MCP in `--readonly` mode, Fab Inspector. Semantic Link Labs runs only inside a notebook. The `te` preview CLI is dropped | 3.10, 3.13 |
| F-10 | HIGH | Accepted | FR-33 narrowed: the executor's REST and `fab` wrapper injects the header. `fabric-cicd` calls are tagged at process level if feasible. Tested in S10 | 3.9, 5.1 |
| F-11 | HIGH | Accepted | Unlabelled synthetic fixtures. The label Git switch is checked in S1 and S2. A reconciliation check and a refresh-idempotency check join the semantic-model pack. The policy engine rejects label changes | 3.7, 3.9, 3.10 |
| F-12 | HIGH | Merged with A-16, X-07 | C8, C10 (retention-controlled evidence), C12, C13, C14 and spikes S9 and S10 move into Phase 0 exit or Phase 1 readiness | 4.2, 5.1, 5.2 |
| F-13 | HIGH | Merged with X-02, A-14, O-02 | The isolation mechanism is specified and proven in S7. `--readonly` and `--accepteula` are mandatory for the Authoring MCP | 3.1, 5.1 (S7) |
| F-14 | MED | Accepted | Four path A failure modes recorded: missing `directoryName` gives 404, `git/status` can be a long-running operation, a service principal needs a configured connection and the tenant switches, and `fabric-cicd` binding must be strict | 3.8 |
| F-15 | MED | Accepted, modified (with O-05, X-12, A-04) | The branch ledger stops being authoritative. The run store is the system of record. Each run has its own projection ref with one writer | 3.2, 3.3 |
| F-16 | MED | Merged with A-06, X-08 | Feedback re-enters through SPECIFIED, PLANNED, TEST. The commenter must be a code owner. At most 2 review rounds | 3.3, 3.12 |
| F-17 | MED | Accepted | `fabriciq-ontology-cli` is quarantined in `knowledge.lock`. The ontology pack follows the Learn TMDL-based specification | 3.10, 3.13 |
| F-18 | MED | Accepted | The spec carries an estimated cost. Multi-item dependencies need `parameter.yml` filters. A `verify-local` script runs the static gates on a laptop | 3.8, 3.12, 3.17 |
| F-19 | MED | Accepted | D-04 rationale corrected. Any use of Agent Framework needs a gateway adapter for Grok and Gemini | 6 (D-04) |
| F-20 | LOW | Accepted | Versions standardized: `ms-fabric-cli` 1.8.0, `fabric-cicd` 1.4.0. One audited REST and `fab` path. The local MCP `run-pipeline` is noted but unused | 3.9, 6 |

## GPT (lens: architecture and feasibility)

| ID | Sev | Decision | Reason and change | Addressed in |
|---|---|---|---|---|
| A-01 | HIGH | Accepted | Oracle tests are declarative data (query, expected table, tolerance, structure assertion) run by a pinned harness. Fixture generators are trusted and pinned. Arbitrary-code tests wait for Phase 4 and run only inside the sandbox workspace | 3.9, 3.11 |
| A-02 | HIGH | Accepted | The orchestrator compiles a complete deployment manifest from the test-merge tree: dependency closure, schedules removed, every reference resolved, every data source on the allow-list. Sandbox transformations are recorded apart from the source patch | 3.9 |
| A-03 | HIGH | Accepted | Operation intents, provider IDs, reconciliation by query, and rebuild or quarantine on ambiguity. S5 kills the worker after provider acceptance and before the checkpoint | 3.3, 5.1 (S5) |
| A-04 | HIGH | Accepted, modified | The system of record is a run store on Azure Table Storage (ETag compare-and-swap, fenced leases, a reconciler) from D0. The reviewer's option of an earlier Durable Task is kept as the fallback if S5 shows Actions resumption is too brittle | 3.2, 3.3, 6 (D-03) |
| A-05 | HIGH | Accepted | A pool of runner principals, one leased per active environment. The deployer revokes the earlier grant and checks for outstanding jobs before reuse | 3.5, 5.1 (S2) |
| A-06 | HIGH | Accepted | Plan first, then classify, then approve an immutable digest of spec and plan. The tier is recomputed from the actual semantic diff. A tier increase voids approval | 3.3, 3.12 |
| A-07 | HIGH | Accepted | Four rulesets (see 3.6) with named negative tests, in the new spike S11. The closure check showed that a bypass actor skips every rule in its ruleset, so the writer restriction (RS-C1, publisher bypass) is separate from signed commits and no force-push (RS-C2, no bypass). The `Restrict updates` effect on merges is a stated assumption that S11 must confirm | 3.6, 5.1 (S11) |
| A-08 | HIGH | Merged with X-06, O-03 | A required check `factory/approval-policy`, posted by the publisher App and pinned to its App ID. It excludes the requester and bots and binds to head SHA, tier and spec digest | 3.6 |
| A-09 | HIGH | Accepted | Validation runs on the test-merge tree. Evidence names both base and candidate SHAs and is void if either moves. The strict up-to-date rule enforces it (a merge queue only after S11 shows an App cannot enqueue) | 3.6, 3.11 |
| A-10 | HIGH | Accepted, modified | No standing baseline workspace. A baseline evidence cache is keyed by base SHA, fixture digest, harness version and parameters. A fresh-environment repeat runs at T2 only. Same-environment idempotency is a separate, named test | 3.7, 3.11 |
| A-11 | HIGH | Accepted | An independent watchdog with per-operation cancel, idempotent finalizers for every terminal outcome, and quarantine for work that cannot be cancelled | 3.3, 3.16 |
| A-12 | HIGH | Accepted | Four lifetimes: compute lease, item reservation, workspace expiry, PR. Reviewer preview is re-provisioned on request after expiry | 3.3, 3.7 |
| A-13 | HIGH | Merged with X-04, F-04 | Path B for validation and preview. Dev deployment is outside v1. No parity claim is made that is not tested | 3.8 |
| A-14 | HIGH | Merged with X-02 | Credential placement, mounts, process and network isolation, and model-request mediation are specified and proven in S7 | 3.1 |
| A-15 | HIGH | Accepted, modified | Reserve a worst-case cost before each dispatch and reconcile after. The D0 credit cap is soft, so the design states a bounded overshoot (one response times the concurrency cap) for the owner to approve, and relies on the organization budget as the hard stop | 3.14, 10 |
| A-16 | HIGH | Merged with F-12, X-07 | Phase exit and readiness are now explicit, per requirement | 4.2, 5.1, 5.2 |
| A-17 | HIGH | Accepted | Evidence and manifests live in an immutable blob container with a time-based retention policy, from D0. Attestations prove provenance only | 3.16, 4.2 |
| A-18 | HIGH | Accepted | A per-pack capability matrix (endpoint, identity, model features, dependencies, refresh, render, evaluation). Unsupported combinations are refused. A human step never counts as unattended validation | 3.10 |
| A-19 | MED | Accepted, phased | Tests are protected from the implementer, not from approved requirement changes. The test author may propose a versioned expectation migration tied to approved criteria. Built in Phase 2 with T2 | 3.11, 5.3 |
| A-20 | MED | Accepted, phased | T2 breaking changes need an operator-kept consumer manifest, else the run refuses. Closure above the unit cap needs a compatibility migration, not a split. Built in Phase 2 | 3.12, 5.3 |

## Grok (lens: red team)

| ID | Sev | Decision | Reason and change | Addressed in |
|---|---|---|---|---|
| X-01 | CRIT | Accepted | Executor operations take a run ID and step only. The orchestrator picks suite, fixtures and parameter file from the policy pin. The workspace registry is a list of GUIDs in the run store, never in the branch, and every call matches the GUID | 2 (HR-2), 3.7, 3.9 |
| X-02 | CRIT | Accepted | HR-3 is reworded so that it is true: no model or Git token in the agent job. The preferred D0 substrate is gh-aw in strict mode (API proxy and SafeOutputs). No Phase 1 on hosted runners until S7 proves egress deny and token isolation. Fallback: a self-hosted ephemeral runner with a broker, or per-run gateway tokens | 2, 3.1, 5.1 (S7) |
| X-03 | HIGH | Accepted | Spec, fixtures, generators and `factory-oracle/**` are frozen against the implementer after approval. Hidden tests sit in a store the agent job cannot reach. The sanitizer is a fixed enum. At least one held-out input exists even for T1 | 3.9, 3.11 |
| X-04 | HIGH | Accepted, modified | No write-capable Git credential in Fabric. Dev deployment leaves v1. If path A is ever adopted, its credential is read-only, single-repo and short-lived, so Commit to Git cannot succeed from the factory | 3.5, 3.8 |
| X-05 | HIGH | Accepted | The semantic diff rejects any new or changed data-source expression, partition, external URL, custom visual or web action unless the executor's allow-list has it. S3 tests an exfiltration probe through a new partition and through a report | 3.9, 3.10, 5.1 (S3) |
| X-06 | HIGH | Accepted, phased | Requester is not approver is enforced by A-08's check in Phase 1. The check that the requester still holds access to the target workspace needs a read-only identity and arrives in Phase 2. Until then the per-target requester list is reviewed at onboarding | 3.6, 3.12, 5.3 |
| X-07 | HIGH | Merged with F-12, A-16 | A deterministic secret and PII scan runs before any model call. No fallback to a shared capacity | 3.12, 4.2 |
| X-08 | HIGH | Merged with F-16, A-06 | Clarification questions come from an enum. Comments are scanned. Any scope or spec change re-enters the spec stage, and approval is required again where the tier needs approval (T2 or a low-trust requester). An escalation report carries the reason, never a patch | 3.3, 3.12 |
| X-09 | HIGH | Merged with A-07 | `@copilot` is disabled on `factory/*`. Required checks are pinned to the publisher App. A signature check rejects unsigned commits | 3.6 |
| X-10 | HIGH | Accepted | S2 prints the effective identity of a notebook run and a refresh and proves the runner cannot create workspaces. A custom role holds only suspend, resume and read. Nothing that needs tenant admin is attempted | 3.5, 5.1 (S2) |
| X-11 | MED | Accepted | Budget counters are atomic in the run store. The lock key is the sorted item paths plus the capacity, taken before the planner mutates anything | 3.3, 3.14 |
| X-12 | MED | Merged with A-04, O-05 | The projection ref is protected, has no force-push, and is written by one identity. Evidence is regenerated by the publisher from artifacts, never from a file the agent can edit | 3.2, 3.16 |
| X-13 | MED | Merged with X-05 | TMDL and PBIR are parsed. Roles, labels, schedules and connections are rejected anywhere in an item. `**/CODEOWNERS` and `**/.github/**` are denied | 3.9 |
| X-14 | MED | Accepted | An immutable executor image runs no repo scripts. Actions are pinned by SHA. Skill text cannot authorize an install. The only package source is a hash-pinned mirror | 3.1, 3.13, 5.1 (S10) |
| X-15 | MED | Accepted | New rule HR-12: fail closed. A preflight conformance check runs before every run. Verifier output uses a strict schema | 2, 3.3, 3.9 |
| X-16 | MED | Accepted | `env.create` is find-or-create by intent and tag. Orphans on the sandbox capacity that are not in the registry raise an alert before they are swept | 3.3, 3.7 |
| X-17 | MED | Accepted | The alias comes from a server-side allow-list. The slug allows `[a-z0-9-]` only. No issue field reaches a shell. No job holding a secret fetches a link | 3.12 |
| X-18 | LOW | Accepted | Stated as a hard limit. The proof-of-concept identity holds no role on a shared, demo or production workspace and no Fabric Git credential | 4.3 |
| Detections | - | Accepted | The red team's list of missing detections becomes section 4.4 | 4.4 |
| Residual risks | - | Accepted | The red team's list joins section 4.3 | 4.3 |

## Orchestrator self-review

| ID | Sev | Decision | Reason and change | Addressed in |
|---|---|---|---|---|
| O-01 | HIGH | Accepted | A sandbox connection catalogue: named connections made by a human administrator. The parameter file refers to names only and the executor binds only from the catalogue | 3.7, 3.9 |
| O-02 | HIGH | Merged with X-02, F-13 | See X-02 | 3.1 |
| O-03 | HIGH | Merged with A-08 | See A-08 | 3.6 |
| O-04 | HIGH | Merged with A-04, A-11 | A scheduled reconciler resumes stale runs from the last completed stage, with a bounded attempt count, then ESCALATED | 3.3 |
| O-05 | MED | Merged with F-15, X-12 | See F-15 | 3.2 |
| O-06 | MED | Merged with X-03 | See X-03 | 3.11 |
| O-07 | MED | Accepted | A new residual risk (synthetic data does not prove behaviour on real volumes). A human smoke test follows any deployment to dev. Masked-sample validation is a later option | 3.17, 4.3 |
| O-08 | MED | Accepted | Size caps are in semantic units (items, measures, visuals, pages) plus a line cap, calibrated in Phase 1 | 3.12 |
| O-09 | MED | Accepted | Halt stops at the next stage boundary, cancels active provider operations, and leaves workspaces to the sweeper. Both paths are drilled | 3.16 |
| O-10 | MED | Accepted | S3 picks the render route and records the identity it needs. The primary route is `exportToFile` | 3.10, 5.1 |
| O-11 | LOW | Accepted | The agent job's workflow permissions are read-only, with no ID token, and the model credential stays in the substrate | 3.1 |
| O-12 | LOW | Accepted | The App key and signing key live only in a protected Environment used by the publisher job. Rotation is part of the drill | 3.5, 3.16 |

## What the log shows about the review itself

- **No finding was weak enough to reject.** I looked for weak ones. The nearest were F-19 and O-11, which are small. The panel's lenses overlapped on the high-severity items (egress, approval policy, state, phase gating), which is a sign that those were real.
- **Where I changed the recommended fix**, it was to remove a dependency rather than add a control. Taking dev deployment out of v1 removes F-04, X-04 and A-13 from the critical path, and matches what the user asked for (a PR that waits for a human).
- **Reviewer-specific blind spots.** Gemini found the Fabric-mechanics errors (F-01 to F-04). Grok found the executor trust problems (X-01, X-02). GPT found the state and recovery problems, all rated HIGH. Of the six CRITICAL findings no reviewer found more than four (Gemini four, Grok two, GPT none), so the panel caught what any one reviewer would have missed.

## Closure check

The three reviewers re-read design v0.2 and this log, and judged each of their own CRITICAL and HIGH findings (files: `closure-gemini.md`, `closure-gpt.md`, `closure-grok.md`). They also checked five platform claims that I named: the rulesets, App-signed commits, Table Storage, the Fabric delete routes and the gh-aw substrate.

| Reviewer | Own CRITICAL and HIGH findings | Closed | Partly | Open | New problems | Phase 0 can start |
|---|---|---|---|---|---|---|
| Gemini | 13 | 12 | 1 (F-13) | 0 | 5 | Yes |
| GPT | 18 | 16 | 2 (A-04, A-07) | 0 | 3 | Yes |
| Grok | 10 | 9 | 1 (X-06, phased on purpose) | 0 | 3 (one repeats GPT's) | Yes |

Two more facts I re-fetched myself at closure **[V]**: (5) the REST reference for Delete Recoverable Item says workspace write permission and lists service-principal support, which contradicts the admin pages and my earlier note in this log. (6) The gh-aw safe-outputs and network reference pages confirm Grok's claim that the defaults are wider than the design assumed: `merge-pull-request` and `push-to-pull-request-branch` exist as safe outputs, `create-issue` is auto-injected, and the network default allows basic infrastructure and common package mirrors, with GitHub's own domains allowed by default.

What changed after the closure check:

| Change | Raised by | Where |
|---|---|---|
| RS-C split into RS-C1 (writer, publisher bypass) and RS-C2 (signed commits, no force-push, no bypass). N6 and N9 run with the publisher's own token | GPT GN-1, Grok 1, A-07 | 3.2, 3.5, 3.6 |
| Ready for review depends on the automated checks, and the approval-policy check gates only the merge. The definition of done is reworded | GPT GN-2 | 3.6, 3.11 |
| Handover for a stale worker: cancel and wait, an epoch check before each call, rebuild when the old run cannot be confirmed ended. S5 freezes a worker to test it | GPT A-04 | 3.3, S5 |
| The purge-permission conflict is recorded, S2 tests it, and the privilege model does not rely on it | GPT GN-3, Grok (d) | 3.7, S2 |
| gh-aw defaults pinned: `network: {}`, a minimal safe-output set, and a new test I-8 | Grok 2 | 3.1, S7, D-04 |
| gh-aw tests I-1 to I-3 reworded to match its documented limits | Gemini NP-1 | 3.1 |
| Refresh runs model expressions: S2 tests the runner, a fallback principal, a residual risk | Grok 3 | 3.5, 3.7, 4.3, S2 |
| Run-store keys encoded, one partition for each lock set and each budget, a 100-row cap with refusal, an item GUID registry | Gemini NP-2, NP-5, Grok (c) | 3.2, 3.7 |
| One named commit route (`createCommitOnBranch`) with no custom author or committer | Gemini NP-3, Grok (b) | 3.5, 3.6 |
| No merge queue in v1 until N2 tests an enqueue by the App | Gemini NP-4 | 3.6 |
| RS-A's effect on an API merge is marked as an assumption | Grok (a) | 3.6 |
| X-08 wording corrected: approval re-entry applies only where the tier needs approval. Scenario 9 reworded | Grok | this log, 9 |

What stays open on purpose: the entitlement check (X-06, Phase 2), and every claim that only a spike can settle (design section 10). "Closed" in the verdict tables means closed on paper.
