# Fabric Code Factory — Landscape research digest

Version 0.1 · 2026-10-30 · Status: consolidated from raw reports T1 to T7 and O1 (orchestrator grounding), then patched with the cross-verification verdicts. Desk research only: nothing here has been tested on a live tenant.

**Superseded in part.** This digest was written before the design review. Where it disagrees with the design v0.2 (`04-design.md`), the decision register v0.2 or `reviews/disposition-log.md`, those win. The main differences: the digest's component numbering C1 to C11 is now K1 to K12 in the design (C1 to C15 are reserved for the security controls), the controls the digest defers to later phases now gate Phase 1, variable libraries cannot bind semantic models or reports, and a soft-deleted item can be purged with a workspace write role according to the REST reference (the admin pages say Admin, so the spikes test it). Later corrections, found by checking the documents against primary sources, are recorded in `reviews/verification-log.md`.

Raw reports are in `research/raw/` (t1 to t7, o1). Section numbers below point to the evidence, not to a source of truth: if a raw report and this digest disagree, the raw report wins.

## 1. Bottom line

1. **Nobody ships what we want.** The pattern of assign, isolated sandbox, branch and draft PR, human review has converged across platforms. None is Fabric-aware, and no data vendor ships a silent intake-to-validated-PR loop. Microsoft ships a toolbox (skills, MCP servers, CLIs), not a factory. We must build the orchestration, isolation, gates and approvals. (T1, T3a, T3b, T3c)
2. **Fabric allows the loop, with caveats.** Branch, isolated workspace, Git sync, deploy, test, PR works through REST with a service principal for the core item types. There is no one-call "branch out", and Git sync loads no data, binds no connections and activates no variable-library values. (T4)
3. **Unattended identity is the binding constraint.** Service-principal or managed-identity capable: `fab`, `fabric-cicd`, the local Power BI Authoring MCP, the local Fabric MCP in Docker, Execute DAX Queries REST, Git integration. User-only: FabricIQ MCP, hosted Core MCP, hosted Authoring MCP, ontology MCP, Project Osmos, every Copilot feature in Fabric. Update From Git with a service principal works only if every item involved in the operation supports one. (T3a, T4)
4. **Workflow first.** A deterministic, checkpointed state machine with bounded agent loops inside the implement and fix steps. The evidence is vendor engineering narrative, not controlled studies. (T2)
5. **Injection cannot be detected reliably, so structure is the control.** Adaptive attacks beat 12 published defences more than 90% of the time. Use stage separation, a read-only agent with buffered writes, a credential-injecting proxy, no standing secrets and a dedicated sandbox workspace. The 2025 and 2026 incidents show the same ingredients: reachable credentials and untrusted text (PocketOS was an agent guessing with an unscoped token, not injection). (T5, T1)
6. **Doer and judge must be separate.** Same-model self-grading is lenient and circular, agents have written `return true` to pass tests, and frontier models reward-hack. Acceptance checks must live outside the writable branch. (T1, T2, T5)
7. **Runtime: a hybrid.** GitHub is the governance plane, a durable Azure orchestrator owns run state, headless Copilot workers run in sandboxes without Fabric credentials, and separate validation workers hold the Fabric identity. Start thin on Actions and add the orchestrator when runs outgrow it. (T6)
8. **All four named models are GA in GitHub Copilot.** Foundry has three of the four (Gemini 4 Argon not found). API Management is the enterprise gateway; LiteLLM had three Critical advisories in 2026. (T6)
9. **Most data and BI gates can run headless today** (Tabular Editor 2 CLI, Semantic Link Labs, Fab Inspector, `fabric-cicd`, `datacontract-cli`). Gaps to build: data diff, golden-DAX regression, report image diff, and a data-agent evaluation gate whose service-principal path is unverified. (T3c)
10. **The vendor landscape churns fast.** Keep every engine behind a thin contract. Do not buy an agent platform. (T1, T3c)

## 2. Engines and frameworks

| Option | What it gives | Limits that matter | Verdict |
|---|---|---|---|
| GitHub Copilot cloud agent and Agent HQ | Strongest platform-enforced controls: one `copilot/` branch, draft PR only, cannot approve or merge, requester cannot approve, workflows held for a human by default (configurable), signed commits, firewall | Tasks API accepts only user-to-server tokens (a delegated user identity, not a GitHub App installation token). Sandboxes cannot use self-hosted runners. Azure Repos unsupported | Borrow the control model. Candidate worker for GitHub repos only |
| GitHub Agentic Workflows (gh-aw) | Read-only agent job, writes buffered as "safe outputs" with deterministic filters and threat detection, microVM option, engines: Copilot, Claude Code, Codex, Pi, Agy (experimental) and a Gemini CLI engine marked deprecated | New. Threat detection defaults to warn mode, so enable strict. An advisory retired some releases, so pin by SHA | Borrow the pattern. Candidate chassis |
| Copilot SDK and CLI, headless | Multi-model, runs in Actions with `GITHUB_TOKEN`, JSON-RPC server mode, session resume, soft credit cap | Being re-homed as the Microsoft Copilot SDK. No official container image | Primary worker runtime candidate, behind an adapter |
| Microsoft Copilot harness in Foundry | Managed multi-model harness, skills, MCP, subagents | Public preview since 2026-10-28. Resilience is "GA" in a blog and "preview" in Learn | Watch, do not depend on it |
| Claude Code, Agent SDK, Action | Mature headless use, OIDC federation, restores agent config from the base branch | Anthropic does not support routing Claude Code to non-Claude models, and the SDK runs the Claude Code binary | Implementer candidate. Verifiers from other families run in separate contexts |
| Codex, Devin, Factory, Cursor, Kiro, GitLab Duo, others | Same shape as above | None Fabric-aware. Jules ends 2026-12-31, Amazon Q Developer IDE plugins end 2027-04-30, legacy Codex Cloud slated for deprecation | Inspiration only |
| Microsoft Agent Framework | MIT, 1.0 GA, graph workflows with checkpoints and human-in-the-loop, OpenTelemetry, `ClaudeAgent` wrapper (pre-release package) | No Grok provider in its provider table (updated 2026-10-22). Checkpoint-format break at 1.13.0 | Best orchestrator candidate for the durable step. Fallback: LangGraph |
| OSS agents | OpenHands SDK, OpenCode, goose, Cline, mini-SWE-agent are live | Roo Code is GitHub-archived. Continue and AutoGen carry read-only or archive notices in their READMEs without the GitHub flag. SWE-agent last release 2025-05, Aider 2025-08 | Do not build on the dead ones |
| Protocols | MCP 2026-07-28 (stateless, Tasks extension, trace context in `_meta`); Agent Skills; AGENTS.md | Public MCP registry still preview. Skills are a supply-chain risk: 36.8% of about 4,000 public skills had a flaw (vendor study) | Adopt. Run a private registry, pin everything |

## 3. What Fabric allows

### 3.1 The loop that works

Create the Git branch (provider API), create the workspace and assign a capacity, connect it to the branch and initialize, update from Git, run post-deploy jobs (data, connection binding, variable-library value set, refresh), run the tests, delete the workspace. A preview Create Workspace Relation API can record the branch-to-base link. There is no single branch-out call.

### 3.2 Pilot and core item types

| Item | Git | Unattended identity | Headless test route | Notes |
|---|---|---|---|---|
| Semantic model | Yes, TMDL. Git is preview | Yes | `executeQueries` DAX (needs two tenant switches, no RLS or SSO, 120 requests a minute per user across datasets, at most 100,000 rows or 1,000,000 values per query); local Power BI Authoring MCP (GA) | Enhanced refresh causes Git diffs. Direct Lake does not auto-bind in deployment pipelines |
| Report | Yes, PBIR. Git and the PBIR setting are preview | Yes | `powerbi-report-author` validate and headless screenshot; `exportToFile` PNG (capacity-backed, not PPU, needs a tenant switch that is off by default) | Deployment pipelines say PBIR is unsupported. The skill installs the CLI with `npm install -g @microsoft/powerbi-report-authoring-cli@latest`; the package is published on npm (0.5.0 on 2026-10-30, a pre-1.0 release, verified from a hosted runner) and `@latest` must be pinned |
| Data agent | Yes, file parts. Evaluation is preview. Git is listed without a preview tag on the supported-items page (updated 2026-10-17), while the data-agent source-control page still says preview | Learn contradicts itself: the ALM page says ALM only, the SDK and MCP pages say a user or a service principal. Treat as endpoint-specific | Evaluation SDK (alpha, notebook, LLM-judged, needs a published agent); published agent callable as MCP (the SDK docs moved from the Assistants route to Responses and MCP on 2026-10-14) | No official skill. Trial capacity unsupported. Never edit `published/` |
| Ontology | Yes. Preview | Yes per the item table; the ontology MCP is user-only | Unverified | Old format retires 2027-01-31; the shipped skill authors the old format |
| Notebook | Yes. GA | Yes | Job Scheduler `RunNotebook` with `exitValue`; Livy | Lakehouse binding needs parameterization |
| Pipeline | Yes. GA | Yes | Job Scheduler; run-pipeline | Connections are not source-controlled |
| Warehouse | Yes (SQL project). Preview | Yes | T-SQL over TDS | `fabric-cicd` deploys the shell only. Cyclic dependencies and collation break branch-out |

Not supported for service principals: ML experiment and model, Activator, Digital twin builder, mirrored databases.

### 3.3 Sharp edges that break a naive design

1. Service-principal support is per item type and per API. A mixed workspace can block an unattended sync.
2. Two service-principal tenant switches exist: the public-API one is on by default, and the one for creating workspaces, connections and deployment pipelines is off by default for new customers. The GitHub Git switch is also off by default.
3. Git sync leaves data, connections, value sets and refreshes undone. Post-deploy jobs are mandatory.
4. One Git operation at a time per workspace. A stale `workspaceHead` is rejected with a `WorkspaceHeadMismatch` error (the reference does not give its HTTP status, so S4 confirms it). Status itself can return 202.
5. Files must match Fabric's serializer (LF, no trailing newline) or every sync shows phantom diffs. Commit deletes foreign files inside item folders.
6. The Git connect API does not create the target folder. GitHub needs a PAT-backed connection; a service principal needs a configured connection.
7. Throttling and smoothing are capacity-wide. Pause and resume resets throttling but bills the carry-forward and blocks all content on the capacity. Trial capacity lacks data agents.
8. Workspace delete is a soft delete (7 days by default, configurable) that keeps billing storage, and Git can re-create deleted items under a new item ID (the Git integration process page, updated 2026-10-26, says so; a restore from the recycle bin keeps the ID).
9. Schedules stored in Git can activate jobs in a test workspace.
10. DAX test and report render have hard limits (section 3.2).
11. Inbound protection blocks Git APIs, branch-out and deployment pipelines. Outbound access protection blocks Git unless allowed per workspace (the Learn availability matrix marks it Preview for reports, semantic models and data agents, and not supported for ontologies), and these settings are not copied to new workspaces.
12. Deployment-pipeline rules are portal-only, there is no compare API, and a deploy is capped at 300 items. Item pairing is maintained automatically and cannot be set through an API.
13. From 2027-02-28, users without read-write on items cannot use Git.

### 3.4 Tool surface

| Operation | MCP today | Otherwise |
|---|---|---|
| Workspace and item CRUD, definition get and replace, catalog search, operation status | Yes (hosted Core MCP; OAuth 2.0 through Entra, service principals not documented) | REST with a service principal |
| Assign capacity, run pipeline | Local Fabric MCP only | REST, `fab` |
| Git lifecycle, deployment pipelines, notebook runs, variable libraries, report render | None | REST, `fab`, `fabric-cicd`, the owning skill |
| DAX | FabricIQ MCP (read-only, user-only); local Power BI Authoring MCP (GA, service principal) | `executeQueries` REST |
| SQL | SQL endpoint MCP (one tool, preview) | T-SQL over TDS |

Rule for the factory: MCP is author-side tooling. Unattended runs are REST-first with a service principal or managed identity, through the executor.

## 4. Quality gates

| # | Gate | Cheapest reliable route on Fabric |
|---|---|---|
| G1 | Definition validity (TMDL, PBIR, item JSON parse) | Tabular Editor 2 load, Fab Inspector on PBIR, Microsoft JSON schemas |
| G2 | Best-practice lint | TE2 with Microsoft `BPARules.json`, Semantic Link Labs BPA, Fab Inspector |
| G3 | Reference integrity (catches hallucinated fields) | TE2 schema check, Semantic Link Labs broken-visual finder, constrain generation to the model's schema |
| G4 | Deploy and refresh smoke test | `fabric-cicd` to the per-branch workspace, trigger, assert |
| G5 | Contract and breaking-change check | ODCS contract, `datacontract test` and `breaking` |
| G6 | Data-quality rules | datacontract rules; Soda or Great Expectations optional |
| G7 | Data diff and reconciliation | Aggregate or EXCEPT queries against a Warehouse zero-copy clone (build) |
| G8 | Semantic-model regression with golden DAX | TE `test snapshot` (preview; its docs give two expiry dates, 2026-10-31 and 2026-12-31) or Semantic Link Labs plus stored snapshots (build) |
| G9 | Measure unit tests on tiny synthetic data | Deploy on fixtures, assert via DAX |
| G10 | Report structure and visual lint | Fab Inspector, Semantic Link Labs report BPA |
| G11 | Report visual regression | `exportToFile` PNG, perceptual diff, human reviews the diffs (build) |
| G12 | Data-agent evaluation | Git-versioned ground-truth Q&A, deterministic match first, then the SDK's LLM critic. Service-principal path unverified |
| G13 | Security regression (RLS, OLS, labels, secrets) | Semantic Link Labs impersonated DAX per role |
| G14 | Performance and capacity guard | VertiPaq Analyzer thresholds, BPA performance rules |
| G15 | Impact analysis | TE dependencies, Semantic Link Labs, Fabric lineage |
| G16 | Evidence bundle for the human | PR template with G1 to G15 results, diffs, screenshots |

G1 to G6 are cheap and run every iteration. G7 to G12 need the isolated workspace. Gates to build ourselves: data diff, golden-DAX regression, report image diff.

Failure modes seen in practice, and the gates that catch them: hallucinated or ambiguous fields (G3, G12), numbers that look right but are wrong (G7 to G9, G12), silent breakage of consumers (G8, G10, G11, G15), contract drift (G5), instruction non-compliance (deterministic gates, not prompts), unstable results across runs (repeat G12, fix dates in G8), evaluation leakage (hold the gold set out of the generator's context).

Environments: vendors use virtual or shallow copies (per-PR zero-copy clone databases, SQLMesh virtual environments, Fabric Warehouse clones with 30-day retention, which cover Warehouse only) and contracts with variables so no secrets live in Git. No source documents masked or synthetic data generation for Fabric BI.

Independent evidence is thin and sobering: ELT-Bench-Verified reports transformation success of 22.66% while extraction and loading reach 96%. Trust the gates, not the agent.

## 5. Security

Draft threat model highlights (likelihood times impact, 1 to 5 each):

| Rank | Attack path | Score |
|---|---|---|
| 1 | Intake injection makes the agent leak runner secrets or tokens through any open channel | 25 |
| 2 | Over-privileged Fabric identity lets an injected or mistaken agent change production items, permissions or shortcuts | 20 |
| 3 | Agent-authored notebook or pipeline runs with real data or open egress, then exfiltrates or reaches production | 20 |
| 4 | Confused deputy: a requester without entitlement gets data or access through the factory's broader rights | 16 |
| 5 | Reviewer rubber-stamps a large or subtle defective PR | 16 |
| 6 | Poisoned skill, template or MCP tool description steers every run | 16 |
| 7 | Malicious or typosquatted package or Action runs in the sandbox or CI | 16 |
| 8 | Agent edits its own guardrails (workflows, tests, policy files, agent config) | 15 |

Minimum control set before the factory touches any non-sandbox tenant (go-live gates, each to be demonstrated, not only configured):

- **C1** Separation of duties: protected branches, human CODEOWNERS approval, requester is not approver, factory pushes only to `factory/*` branches, empty bypass list.
- **C2** No standing secrets in the sandbox: a credential-injecting proxy or applier holds Git, model and Fabric credentials; per-task short-lived tokens through OIDC and Entra federated credentials.
- **C3** Stage separation ("Rule of Two"): the intake parser has no tools or secrets, the implementer sees only the validated spec, the applier is deterministic.
- **C4** Ephemeral sandbox with default-deny egress for every process, including MCP servers.
- **C5** Fabric blast radius: dedicated sandbox workspaces on a dedicated F-SKU capacity, factory identity is Contributor there only and has no role on production, synthetic or masked data only, no shortcuts into production. Service-principal access is bounded by workspace roles and tenant settings, not OAuth scopes.
- **C6** Promotion only through the existing human-gated path under a different identity.
- **C7** Protected paths and oracle integrity: CODEOWNERS and push rulesets over workflows, tests, quality contracts, agent config and skills; held-out tests; alerts on weakened assertions.
- **C8** Supply-chain pinning: skills, templates and MCP servers pinned by digest; Actions pinned to SHA; package installs through an allow-listed mirror; secret scanning and push protection.
- **C9** Deterministic output gate ("safe outputs"): limits on diff size, paths and file types, secret redaction, a blocklist of operations (delete, permissions, connections, tenant or capacity settings).
- **C10** Audit and provenance: signed commits with the key outside the sandbox, run-ID trailers, OpenTelemetry GenAI traces in a write-once store.
- **C11** Budgets and a kill switch, with the revoke path tested.
- **C12** A data-classification to model-eligibility matrix enforced at the gateway. Prompts carry schemas and synthetic samples, never rows. Anthropic's 30-day retention applies to Mythos-class "covered models" only (Fable and Mythos); Sonnet 5.5, Opus 5.5 and Haiku 5.5 keep zero data retention (verified).
- **C13** Authenticated intake and a confused-deputy check. Permissions, RLS and OLS, connections, deletes and tenant or capacity settings are out of autonomous scope in v1.
- **C14** A red-team and regression gate with injection payloads through every intake channel, before go-live and after any model, prompt or skill change.
- **C15** Incident readiness: runbook, credential rotation drill, named on-call.

Unverified in the source report: Fabric support for Entra agent-identity tokens, Grok data terms, OPA or Conftest for policy.

## 6. Runtime and models

- **Recommendation D, in two steps.** D0: an issue form and label start an Actions workflow that runs headless Copilot CLI or SDK on `factory/<issue>`; work-in-progress commits are the checkpoints; a validation job uses OIDC to a managed identity in an environment with required reviewers; a trusted publisher job opens the draft PR; rulesets require checks and one human approval. D1: move run state to Durable Task Scheduler, run workers as container jobs with the Copilot SDK in server mode on durable storage, put an API Management AI gateway in front for bring-your-own-model and Gemini, and add an entity lock per Fabric workspace or capacity.
- **Design now, whichever path:** run ledger schema, idempotency keys, stage boundaries, an adapter around the SDK, and a spike that kills the runner mid-run and proves resume.
- **Change the recommendation if** Git is Azure Repos (the cloud agent is unsupported there, so choose Azure-native), policy forbids third-party model data flows (Azure-hosted models only, drop Gemini), the cloud agent gains durable resume and self-hosted compute (collapse to GitHub-native), or Foundry resilience and the Copilot harness reach GA with the needed models.
- **Durability:** by default Actions keeps one running and one pending run per concurrency group (a newer pending run replaces the older), but `queue: max` queues up to 100 pending runs in FIFO order (verified). That covers bursts of intake, not resumability. Foundry recovery re-enters the handler from the start. Every option needs idempotent steps and external checkpoints.
- **Models:** Claude Sonnet 5.5, GPT 6.1 Sol, Gemini 4 Argon and Grok 4.7 are GA in GitHub Copilot. Foundry lists Sonnet 5.5, `gpt-6.1-sol` and `grok-4.7` but no Gemini, and its model router pool lacks three of the four. Gemini's enterprise path is Google Cloud behind our gateway.
- **Cost** is dominated by tokens and Fabric capacity, not orchestration. Prices in the source report come from secondary or unfetched pages and are not repeated here.

## 7. Evaluation, metrics and review ergonomics (T7)

T7 claims are in verification wave 2. The numbers below are as reported and are not yet re-checked.

- **Size units to the 80% horizon, not the 50% one.** METR's data (to 2026-05-08, page frozen 2026-09-08) puts the 80%-reliability horizon of current frontier models at about 0.9 to 3.1 hours of human time, against 5.7 to 17.4 hours at 50%. Those tasks are clean and auto-scored, so messy BI requirements will do worse, and the measurements are frozen (METR warns that estimates above 16 hours are unreliable). Design rule: units of about one human-hour, calibrated locally rather than fixed by an autonomy-hour budget.
- **"Tests pass" is not "mergeable".** Maintainer-judged scores on test-passing SWE-bench PRs ran 24.2 points (standard error 2.7) below the automated grader after normalizing against a 68% golden-patch acceptance baseline (METR, 2026-03-10, 296 PRs, four maintainers, three repositories). Keep the human gate and add convention checks.
- **Test tampering is the main integrity threat.** ImpossibleBench (2025-10): GPT-5 cheats on 54% of one impossible-task variant and 76% of another (deliberately impossible tasks, not production prevalence). Read-only tests block edits but not special-casing. Offering an escalate action cut cheating from 54% to 9%. LLM monitors miss 35% to 58%. Use protected tests, diff guards, an escalate action and deterministic checks.
- **Spec quality is the dominant lever.** Underspecified multi-turn work loses about 39% (Laban et al.). Letting the agent ask improves underspecified-task performance by up to 74% (Ambig-SWE). OpenAI estimates about 30% of SWE-bench Pro tasks are broken. SQLBI's "contract before measure" is the BI form of the fix.
- **AI review is a good filter and a poor gate.** GitHub ReviewBench (39 configurations, 219 PRs): grounded precision about 78% to 90%, grounded recall about 6% to 60% (Copilot review 22% to 28%, Cursor 9.6%). Deterministic checks must carry recall.
- **Human review is the bottleneck.** In one enterprise study (802 developers, 196k PRs) PR volume rose 3.1 times against a reviewer pool 1.5 times larger, about twice the load per reviewer. Faros reports +91% PR review time and +154% PR size (observational). Anthropic reports users accept 93% of manual permission prompts. Small PRs, risk-ranked evidence and an independent approver are the ergonomic core.
- **Evaluate the factory as a product.** 20 to 50 audited tasks per pack, a regression suite near 100%, `pass^k` (75% per trial gives 42% for three consistent passes), shadow then canary, and daily probes because a provider regression once affected up to 16% of Sonnet 4 requests at its worst hour (2025-08-31, postmortem 2025-09-17).
- **Public benchmarks are weak and do not cover Fabric.** The DAX LLM Benchmark v2 (2026-10-27) is the only Fabric-relevant one: best 95.9% single-shot; Sonnet 5.5 84.6%, Gemini 4 Argon 87.5%, Grok 4.7 91.2%, GPT 6.1 Sol 91.4%. It has 94 single-shot tasks and tests DAX writing only, not modelling or requirements (verified). Nothing public covers TMDL, PBIR, reports, pipelines, notebooks, ontology or data agents. Spider 2.0 is near saturation. In ELT-Bench, 82.7% of audited failed transformation tasks contained benchmark errors, yet 67% of column mismatches were still agent-attributable.
- **Measure outcomes, not feelings.** METR's randomized trial found developers 19% slower while believing they were 20% faster. DORA 2025 finds AI raises throughput but still lowers stability unless tests, small batches and fast feedback exist.
- **Smallest trustworthy stack for data and BI:** static BI rules, deploy to an isolated workspace, executable acceptance tests (DAX queries, data tests, golden Q&A), protected tests and diff guards, one independent AI review, and a human gate with an evidence bundle. The proposed definition of done is in the design, section 3.11.
- **Gaps in the evidence:** several leaderboards are client-rendered and unreadable; no primary source on verifier-model research, controlled automation bias in PR approval, risk-tiering policies, or mutation testing of DAX, SQL or BI artifacts.

## 8. Borrow and avoid

Borrow:

- The Copilot cloud agent control model and gh-aw safe outputs (read-only agent, buffered writes, deterministic filters).
- Anthropic's brain, hands and session split with credentials unreachable from the sandbox.
- OpenHands' per-role least-privilege tokens (the reviewer cannot push).
- StrongDM's holdout scenarios and digital twins.
- An independent, read-only, tool-less critic from another model family with a fail-safe of applying no patch. It is not a uniform gain: Terminal-Bench 2.1 improved by 4.9 points and DeepSWE fell by 1.5.
- Maia, ThoughtSpot and Cube: branch, validate, human merge. Omni's Auto mode applies changes immediately, so this is not universal.
- Snowflake's fail-closed managed settings.
- The dbt and Snowflake gate set (unit tests, contracts, slim CI, PR data diff, per-PR clones).
- A layered skill-test approach (lint, routing, smoke prompts, evaluation, real-state verifiers). The public skills repo ships none of it, so it has to be built. Also the pin-by-SHA rule for skills.

Avoid:

- LLM auto-approve as a security boundary (Databricks labels auto-approve "Recommended" while documenting it as "not a security boundary", and scheduled runs always auto-approve with the creator's permissions).
- Auto-merging watchdogs.
- Review bots as gates: Claude Code Review, Bugbot and Codex review are advisory by default.
- Floating `@latest` dependencies and run-time package installs.
- Copilot in Fabric and Power BI as an automation surface (no API or service principal), the FabricIQ MCP in the unattended path, and Project Osmos as a dependency (an optional pack behind a flag).
- Buying an agent platform.

## 9. Contradictions and open items

| # | Item | Status |
|---|---|---|
| 1 | Does the local Fabric MCP `create-item` accept a definition? | Version-dependent. Released server versions through 1.6.0 (2026-10-18) have no definition payload. The unreleased `main` branch adds it (merged 2026-10-29). The build in this host matches the released behaviour. Pin the version and keep the REST creation path |
| 2 | Data-agent service-principal support | Verified conflict: the ALM page (2026-08-31) says ALM only, the SDK page (2026-10-14) and MCP page (2026-09-04) say a user or a service principal. Endpoint-specific. Phase 0 spike S6 |
| 3 | Fabric REST quota numbers | Resolved: shared limits of 500, 200 and 500 per minute per identity, plus Job Scheduler limits of 100 submissions and 100 reads per user per minute. The 300 in one example is illustrative. Back off on 429 regardless |
| 4 | `skills-for-fabric` upstream v0.3.20 versus the installed v0.3.19. `fab` 1.8.0 versus 1.7.0 across two reports | Pin to a tagged release and re-check at upgrade |
| 5 | Bulk Import and Export APIs are labelled preview in one page and GA in another | Treat as preview |
| 6 | Hosted-agent resilience: "GA" in a blog, "preview" on its Learn page | Verified: GA per the 2026-10-28 blog, the Learn title still says preview. Checkpoint regardless |
| 7 | PocketOS and "Comment and Control" incidents rest on secondary sources | Verified with primary sources. PocketOS was an agent guessing with an unscoped token, not injection. Comment and Control is arXiv 2605.11229 |
| 8 | Gemini 4 Argon availability in the live Foundry catalog was not checked | Verified: no Gemini models in Foundry |
| 9 | `powerbi-report-author` distribution channel | Resolved in part (2026-10-30, from a hosted runner): the skill installs `@microsoft/powerbi-report-authoring-cli` with npm (`@latest`), and the package is published at 0.5.0, a pre-1.0 release. The local Power BI modeling MCP is published at 1.0.0. Still to do in Phase 0: verify installability and headless use in the sandbox, pin the version, and expect change before 1.0 |
| 10 | Whether capacity pause and resume is Azure Resource Manager only | Phase 0 |

## 10. Raw reports

| File | Scope | Status |
|---|---|---|
| t1-platforms.md | Commercial and hosted agent platforms | Complete, 73 sources |
| t2-oss-frameworks.md | OSS agents, frameworks, protocols, skills | Complete |
| t3a-ms-native.md | Microsoft-native agentic capabilities | Complete |
| t3b-data-platforms.md | Databricks, Snowflake, dbt, Google, AWS | Complete |
| t3c-bi-elt-testing.md | BI, ELT and data-testing vendors | Complete |
| t4-fabric-mechanics.md | Fabric platform mechanics and feasibility | Complete |
| t5-security-governance.md | Security, threat model, controls | Complete, 55 sources |
| t6-runtime-hosting.md | Runtime, hosting, gateway | Complete |
| t7-patterns-evals.md | Intake, iteration, evaluation, metrics | Complete |
| o1-fabric-surface-grounding.md | Tool and skill surface in this host | Complete |
