STATUS: COMPLETE

# T6 — Runtime, hosting, orchestration and multi-model gateway options

Thread owner: research thread T6 of 9 · Started 2026-10-30 · Completed 2026-10-30 · Sources: 59 (58 primary, 1 secondary) · Method: live web fetches of vendor docs; no hands-on tests; every non-trivial claim carries a source in section 7 or is marked UNVERIFIED / inference

## 1. Executive findings (max 10 bullets, most decision-relevant first)

1. **Recommendation: architecture D (hybrid).** GitHub is the governance plane (issues/Projects intake, branch, draft PR, rulesets, required checks); a durable Azure orchestrator (Durable Task Scheduler, or an Agent Framework workflow with Cosmos checkpoints) owns run state; headless Copilot SDK/CLI workers run in ephemeral sandboxes with no Fabric credentials; separate validation workers hold the Fabric identity. Start as D0 (Actions-hosted workers, Git-branch checkpoints) and add the orchestrator when runs outgrow what Actions can resume. Pure A is fastest but weakest on durability; pure B makes us rebuild PR governance; C costs the most to secure.
2. **All four named models are GA in GitHub Copilot today** (Claude Sonnet 5.5, GPT-6.1 Sol, Gemini 4 Argon, Grok 4.7; docs.github.com, live 2026-10-30), so one org-billed policy plane (model enablement, ZDR agreements, AI-credit budgets, audit log) covers them.
3. **Foundry covers three of the four, not Gemini.** Claude Sonnet 5.5 (Azure-hosted GA and Anthropic-hosted GA), `gpt-6.1-sol` and `grok-4.7` are listed on Learn; Gemini 4 Argon is not (UNVERIFIED in the live portal). Gemini's enterprise path is Google Cloud's Gemini Enterprise Agent Platform (GA 2026-10-13) behind our gateway. Foundry's model router pool lacks three of the four, so do not use it for role-pinned models.
4. **Durability is a gap in A and a platform feature in B/C**, but every option still needs idempotent steps plus external checkpoints. Foundry says it plainly: recovery re-enters the handler from the beginning and "conversation history alone isn't enough". Actions concurrency keeps one running and one pending run per group (the newer pending replaces the older), so it is not a queue.
5. **Copilot cloud agent has the best built-in human gate** (write-access trigger; pushes only to one `copilot/` branch; cannot approve or merge; requester cannot approve; extra approval for unattributed PRs; signed commits; firewall). Catches: workflows do not run until a human clicks "Approve and run workflows" by default; cloud sandboxes cannot use self-hosted runners or custom compute; Azure Boards integration supports GitHub repos only, not Azure Repos.
6. **Identity needs no secrets**: `GITHUB_TOKEN` with `copilot-requests: write` (or a GitHub App installation token) for model access; GitHub OIDC to an Entra federated credential on an SPN or user-assigned MI for Fabric. Fabric accepts SPN and MI when the tenant setting is on, but support is per API and per item type (data-warehouse creation fails for them). Entra allows max 20 federated credentials per identity, so bind trust to GitHub environments, not branches.
7. **Gateway: APIM AI gateway is the best enterprise-controlled choice** (token quotas, token metrics, content safety, managed identity to Foundry, Anthropic Messages in v2 tiers, unified model API in preview). LiteLLM has three Critical advisories in 2026 (latest 2026-10-27) and its budgets fail open without a database. OpenRouter is a third-party broker (its ZDR docs banner announces CSAM screening of all traffic, including ZDR, from 2026-10-27).
8. **Cost is dominated by tokens and Fabric capacity, not orchestration.** About $2 in / $10 out per 1M tokens for Sonnet 5.5, GPT-6.1 Sol and Gemini 4 Argon ($2/$6 Grok 4.7) through Copilot; Actions $0.006/min hosted, self-hosted runners free; Temporal $25-50 per million actions. Choose on durability and security.
9. **High churn this week** (re-verify before Phase 1): Copilot SDK is becoming "Microsoft Copilot SDK" (README banner), "Copilot in the cloud" launched 2026-10-28, Microsoft Copilot harness in Foundry is public preview, and hosted-agent resilience is "GA" in the 2026-10-28 blog but "(preview)" on its Learn page (updated 2026-09-10).
10. **Most transferable security pattern: gh-aw's "read-only agent, SafeOutputs apply writes".** The agent proposes; a separate scoped job applies. gh-aw itself had an advisory that retired releases >=0.83.3 <0.85.4, so pin by SHA.

## 2. Evidence tables

### 2.1 Candidate architectures A / B / C / D (trigger, queue/state, runtime, sandbox, identity, validation workers, PR publishing, observability, cost)

| Dimension | A. GitHub-native | B. Azure-native | C. Self-hosted OSS | D. Hybrid (recommended) |
|---|---|---|---|---|
| Silent trigger | Issue/Project label or assignment to Copilot cloud agent; Copilot automations (schedule, repo event, REST; private/internal repos only); Actions `issues`/`workflow_dispatch` running gh-aw or `copilot -p`; Azure Boards "create PR with Copilot" (GitHub repos only) | GitHub App or ADO service hook, Function, Service Bus/Event Grid, ACA event job or DTS orchestration; Foundry hosted-agent Invocations endpoint is a documented webhook receiver | OpenHands Automation Server cron/webhooks (**beta**) or own receiver into Temporal | GitHub App webhook, thin Function (signature check, delivery-ID dedupe), starts orchestration with deterministic instance ID (repo+issue) |
| Queue / state | Issues/Projects, Actions run queue, Git branch; 35-day run cap incl. waits | Service Bus; DTS history or MAF checkpoints (InMemory/File/Cosmos); Foundry work+input identity | Temporal history; Postgres for OpenHands | DTS (or MAF + Cosmos) run state; Git holds artifacts; issue shows status |
| Agent runtime | Cloud agent; Copilot CLI/SDK on runner; gh-aw (Copilot, Claude Code, Codex, Gemini, Pi) | MAF; Foundry hosted agents (any framework); Copilot harness in Foundry (public preview) | OpenHands Agent Server + Sandbox Server (community-supported); Enterprise = licensed | Copilot SDK/CLI headless (server mode) as MAF agent or durable activity; BYOK optional |
| Sandbox | Hosted runner VM, or self-hosted/ARC; gh-aw adds firewall, API proxy (may hold model keys), MCP gateway, container or Cloud Hypervisor microVM | Hosted-agent per-session VM sandbox (persistent `$HOME`); ACA Sandboxes (suspend/resume, egress policy; GA status not stated) | Docker/K8s pods we harden | ACA job or sandbox per run, egress allow-list, no Fabric credentials inside |
| Fabric identity | OIDC to Entra FIC to SPN/UAMI in a gated GitHub environment | Agent identity / UAMI / SPN, Key Vault, VNet | AKS workload identity or secret SPN | Validation-worker UAMI per trust zone; agent sandbox has none |
| Validation workers | Actions jobs (fabric-cicd, Fabric CLI/REST); blocked until human approval for agent-pushed code unless configured | ACA jobs / Azure Pipelines | Temporal activities | Orchestrator-launched ACA jobs; results posted as GitHub check runs |
| PR publishing | Native draft PR, signed commits, session-log link, rulesets | Must build (GitHub App or Azure Repos policies) | Must build | GitHub App opens draft PR; rulesets enforce approval; app cannot merge |
| Observability | Session logs, Actions logs, audit log; SDK OpenTelemetry | App Insights/OTel, DTS dashboard, APIM metrics | Temporal UI + own stack | OTel end to end plus run ledger |
| Cost drivers | AI credits; hosted runner $0.006/min or self-hosted free; cloud sandbox $0.000024/s + $0.000003/GiB-s | Tokens (Claude via Marketplace CCU); hosted-agent container hours; DTS SKU; ACA | Tokens + infra + Temporal + ops staff | Tokens + ACA/DTS + Actions minutes (orchestration small vs tokens + Fabric capacity) |

### 2.2 Durability / resumability / idempotency / concurrency per architecture

| | A | B | C | D |
|---|---|---|---|---|
| Multi-hour work | Run up to 35 days incl. waits; env approval gate up to 30 days; per-job cap (6 h hosted, 5 d self-hosted) from secondary sources only, UNVERIFIED | DTS/Durable Functions long-lived; hosted agent idle timeout 2-240 min, session kept 30 days; ACA job `replicaTimeout` max UNVERIFIED | Temporal long-lived with heartbeats; OpenHands agent loop itself is not durable | Orchestration unbounded; each worker stage chunked (~1-2 h) with checkpoint |
| Resume after host loss | Re-run restarts job (max 50 re-runs); SDK session dir lost on ephemeral runner unless persisted; pushed commits survive | Foundry: lease expiry then handler re-entered from start with same IDs; MAF superstep checkpoints; DTS replay | Temporal replay | DTS replay + SDK `sessionId` resume from persisted store + branch |
| Idempotency | Key on issue/branch; check-then-create PR | Same one-shot work identity converges; side-effect watermarks | Workflow-ID uniqueness (UNVERIFIED here) | Instance ID = repo+issue; deterministic workspace/branch names; persist watermark before non-repeatable calls |
| Concurrency | Concurrency groups (1 running + 1 pending); one `copilot/` branch per task | Per-session isolation; DTS entity work items usable as locks (inference) | Task-queue priority and fairness (vendor page) | Entity lock per Fabric workspace/capacity + global semaphore |
| Retries | Job re-run (max 50) or agent-level loops; no activity-level retry | DTS automatic retries (page description); Foundry distinguishes recovery (same attempt continues) from retry (consumes retry budget) | Retries with backoff, four timeout classes, heartbeats, saga compensation (vendor page) | Stage-level retries with a budget in the orchestrator; bounded agent fix-and-revalidate loops (N), then escalate to the human PR |

### 2.3 Fabric identity and validation orchestration (SPN vs managed identity vs WIF; ephemeral workspaces; job APIs)

- **Identity choice.** Fabric REST accepts user, service principal and managed identity once "Service principals can use Fabric APIs" is enabled; each API page states support and a call fails when a dependent item type lacks it (examples: creating a data warehouse, running some notebook job types). Keep a capability matrix and a documented user-delegated fallback lane (inference).
- **Workload identity federation.** Entra FIC on an app or user-assigned MI trusts GitHub OIDC; max 20 per identity, no wildcards, and a wrong `subject` fails silently at exchange. Use environment-scoped subjects (`repo:ORG/REPO:environment:NAME`) and one identity per trust zone (sandbox-validate vs prod-deploy). Environment secrets can require reviewer approval.
- **Orchestration sequence** (inference from documented APIs): create `cf-<runId>` workspace on a small dedicated capacity; connect to the branch (Git integration with SPN) or deploy with fabric-cicd; run item jobs through the Job Scheduler API; Fabric LROs return 202 + `Location`/`x-ms-operation-id`/`Retry-After`, so persist the operation ID in run state and resume polling after a crash rather than resubmitting; run DAX/SQL and data-quality tests; post check runs; tear down in a `finally` stage plus a TTL reaper for leaks. T4 owns the Fabric API details.

### 2.4 Multi-model gateway: model availability by path (verified vs UNVERIFIED)

The user confirmed today that all four are reachable as sub-agents through the Copilot CLI harness; the GitHub docs below independently confirm they are supported GA models.

| Model | GitHub Copilot (CLI, SDK, cloud agent, gh-aw) | Microsoft Foundry | Other enterprise-controlled path | Retention / terms |
|---|---|---|---|---|
| Claude Sonnet 5.5 | GA; $2 in / $10 out per 1M tokens | **Yes**: Azure-hosted GA and Anthropic-hosted GA; partner model, Marketplace CCU billing, Anthropic is seller and data processor; not in router pool | Bedrock/Vertex host Claude for GitHub; direct enterprise access to 5.5 there UNVERIFIED | Copilot: ZDR (GA features; Fable 5/5.1 excluded). Foundry: Anthropic DPA; Azure-hosted keeps data at rest in selected geography, DataZone (US) option |
| GPT-6.1 Sol | GA; $2 / $10 (<=272K) | **Yes**: `gpt-6.1-sol` (2026-09-29), sold by Azure, 1.05M context; not in router pool | OpenAI direct UNVERIFIED | Copilot: GitHub ZDR agreement with OpenAI. Foundry: Microsoft DPA, no training, not shared across customers, but the service stores/processes data to monitor abuse (modifiable for managed customers) and Responses API stores state (Learn 2026-06-05) |
| Gemini 4 Argon | GA; $2 / $10 (promo footnote) | **Not found** on "sold by Azure" or "partners and community" Learn pages (UNVERIFIED in portal) | Google Gemini Enterprise Agent Platform + AI Studio, GA 2026-10-13, intro price $2/$10; APIM can front Vertex-schema APIs | Copilot: GCP-hosted, no training, durable cache up to 24 h. Google direct terms not read |
| Grok 4.7 | GA; $2 / $6 (<=200K) | **Yes**: `grok-4.7` v1 under sold-by-Azure "SpaceXAI" models (Learn 2026-10-05); router pool has 4.6 only | xAI/SpaceXAI direct; OpenRouter has a SpaceXAI ZDR endpoint (model-level UNVERIFIED) | Copilot: xAI ZDR API policy (RAM only, no human review). Foundry: same sold-by-Azure terms as GPT-6.1 Sol (inference: listed as sold by Azure) |

| Gateway / path | What it gives | Logging | Spend caps | Verdict |
|---|---|---|---|---|
| GitHub Copilot (CLI/SDK/cloud agent/gh-aw) | All four models, one org policy plane; no PAT (`GITHUB_TOKEN` + `copilot-requests: write`, or App token, 1 h expiry) | Audit log, session logs, SDK OpenTelemetry | Org AI-credit budgets (stop at limit), per-automation credit limits, SDK `maxAiCredits` (soft; can overshoot) | **Primary** |
| Copilot BYOK to APIM/Foundry | Traffic stays in our tenant; CLI `providers.json` (openai-compatible/azure/anthropic, `bearerToken`); SDK Entra token callback | APIM + App Insights | APIM token quotas | **Fallback / non-Copilot models** |
| Foundry catalog + project AI gateway | 3 of 4 models; project-level TPM (429) and quota (403) | Foundry tracing, App Insights | TPM + quota | Good for Azure-only policy |
| Foundry model router | Auto-selects among pool; auto-update changes models | n/a | n/a | **Avoid for role-pinned models** |
| APIM AI gateway (+ unified model API, preview) | OpenAI/Anthropic-Messages(v2)/Vertex schemas, aliases, cross-provider failover, content safety, MI to Foundry | `llm-emit-token-metric` | `llm-token-limit` TPM/quota | **Best enterprise-controlled gateway** |
| LiteLLM (self-hosted) | Any model; key/team/agent budgets | Callbacks | Budgets need Postgres, fail open without it | **Avoid or isolate**: 3 Critical advisories in 2026 |
| OpenRouter (SaaS) | Easiest multi-model; ZDR per model group | Dashboard | UNVERIFIED | **Not for regulated data**: third-party broker |

### 2.5 Comparison matrix A/B/C/D (security, silent operation, auditability, durability, setup effort, multi-model flexibility, Fabric+Git fit, cost, lock-in, maturity)

Scores are my judgement from the evidence above (1-5, 5 = most favourable; unweighted), not measurements.

| Criterion | A GitHub-native | B Azure-native | C Self-hosted OSS | D Hybrid | Basis |
|---|---|---|---|---|---|
| Security | 4 | 4 | 2 | 5 | A: single-branch push, no self-approval, firewall; B: agent identity, VNet, VM sandboxes but PR governance is ours; C: we harden sandbox + gateway; D: A's gate + B's identity separation |
| Silent operation | 4 | 5 | 3 | 5 | A: automations/events but workflow-approval gate by default; C: OpenHands automation beta |
| Auditability | 5 | 4 | 3 | 5 | A: signed commits, session logs, audit log |
| Durability / resumability | 2 | 5 | 4 | 5 | B/D rest on DTS replay + checkpoints; A is job-scoped; C needs Temporal wrapping |
| Setup effort (5 = least) | 5 | 2 | 1 | 3 | D0 starts like A; D1 adds orchestrator |
| Multi-model flexibility | 4 | 4 | 5 | 5 | A: Copilot catalog + BYOK; B: Foundry lacks Gemini |
| Fabric + Git fit | 3 | 4 | 3 | 5 | A: GitHub only, cloud sandbox cannot reach private networks; B: Entra-native but PR layer to build |
| Cost | 4 | 3 | 2 | 3 | Tokens dominate everywhere; C adds ops staff |
| Lock-in (5 = least) | 2 | 3 | 5 | 3 | B uses OSS SDKs (MAF, Durable Task) |
| Maturity | 3 | 3 | 2 | 4 | D composes GA parts; B has preview pieces; C beta automation |
| **Total** | **36** | **37** | **30** | **43** | |

## 3. Transferable patterns, anti-patterns and observed failure modes

**Patterns to adopt**
- **Read-only agent, trusted publisher** (gh-aw SafeOutputs): the agent sandbox only writes to a branch/patch artifact; a separate scoped job opens the PR and posts checks; only validation workers hold Fabric identity.
- **Work identity + input identity + lease + small checkpoint index** (Foundry resilience): run ID = repo+issue; stage watermarks in a run ledger; large artifacts in Git/blob.
- **Git as checkpoint, issue as human-visible state**: commit WIP at each stage boundary to `factory/<issue>`; Copilot cloud agent already works this way (one branch, session-log link in commits).
- **Resumable agent sessions**: explicit `sessionId`, `sessionFs`/durable storage instead of local disk (Copilot SDK session persistence).
- **Layered budgets**: org AI-credit budget (stop at limit) + per-automation credit limit + SDK `maxAiCredits` (soft) + APIM token quota (hard 429/403).
- **Ephemeral Fabric workspace per run with saga teardown and TTL reaper**; persist LRO operation IDs.
- **Environment-bound OIDC identities with reviewer gates** (one identity per trust zone).

**Anti-patterns / failure modes with evidence**
- **In-memory agent state.** The 2026-10-30 10:56 CDT host restart cancelled nine agents and lost all state (brief, section 7).
- **"Resume = replay the conversation".** Foundry: recovery re-enters the handler from the start; conversation history alone is not enough (Learn 2026-09-10; blog 2026-10-28).
- **Actions concurrency as a queue.** One running plus one pending; newer pending replaces older (GitHub docs).
- **Agent-authored CI running with secrets.** Cloud agent workflows are gated by default; if auto-run is enabled, protect `.github/` with CODEOWNERS and keep Fabric secrets only in environment-gated jobs (inference; gh-aw doc says authored steps are trusted code, not sandboxed).
- **Start-job permission equals secret access** on ACA jobs (Learn 2026-09-16): grant only to the orchestrator identity.
- **Gateway as credential concentrator.** LiteLLM: Critical advisories 2026-05-28, 2026-09-30, 2026-10-27; budgets fail open without a DB.
- **Silent misconfiguration.** Wrong FIC `subject` creates fine and fails at exchange; Fabric SPN/MI gaps surface only at call time.
- **Doc drift.** SDK README says BYOK is key-only while a setup doc shows Entra tokens; Learn says "(preview)" while the blog says GA; router "updated in place" changes underlying models.
- **Soft caps.** SDK `maxAiCredits` is checked after a model call returns, so a single response can overshoot.

## 4. Recommendation and conditions under which it would change

**Recommendation: D, built in two steps.**
- **D0 (thin slice, fastest to evidence).** Issue form (intake) + label starts an Actions workflow that runs Copilot CLI/SDK headless (`GITHUB_TOKEN` with `copilot-requests: write`, or gh-aw) on branch `factory/<issue>`; WIP commits are the checkpoints; a validation job (hosted or ARC self-hosted runner) uses OIDC to a user-assigned MI in an environment with required reviewers; a trusted publisher job opens the draft PR; ruleset requires checks, CODEOWNERS and one human approval; org AI-credit budget caps spend. Expect to hit: runner death losing the session, pending-replace concurrency, workflow-approval gate.
- **D1 (durability).** Move run state to Durable Task Scheduler (Durable Functions or Durable Task SDK on ACA; Agent Framework workflow only if a multi-agent graph is needed), workers as ACA jobs/sandboxes running Copilot SDK in server mode (`copilot --headless`; there is no official CLI container image, so build and pin our own) with `sessionFs` on durable storage, an APIM AI gateway for BYOK and for Gemini via Google Cloud, entity-lock per Fabric workspace/capacity. Keep model IDs in configuration (default Sonnet 5.5 worker; GPT-6.1 Sol, Gemini 4 Argon, Grok 4.7 as verifiers).
- **Design now, whichever path:** run ledger schema, idempotency keys, stage boundaries, an adapter around the SDK (rename in progress), and a spike that kills the runner mid-run and proves resume.

**Change the recommendation if:**
1. The estate's Git is **Azure Repos**: Copilot cloud agent is unsupported there (Boards doc), so choose B (ADO Pipelines + own workers).
2. Policy forbids third-party-hosted model data flows (Anthropic-hosted, xAI, Google via GitHub): choose B with Azure-hosted models only and drop Gemini; read Azure data terms first.
3. "Copilot in the cloud" gains durable resume, self-hosted compute and stable gh-aw: collapse to A. Also stay on A if runs are short (<1 h) and low volume.
4. Foundry hosted-agent resilience is confirmed GA and the Copilot harness reaches GA with the needed models: consider B-pure to reduce moving parts.
5. Multi-cloud, on-prem or strict-OSS requirements appear: choose C with Temporal and a patched, private gateway.

## 5. Decision-driving claims (max 10; source URL, source date, confidence H/M/L)

| # | Claim | Source URL | Source date | Conf. |
|---|---|---|---|---|
| 1 | Claude Sonnet 5.5, GPT-6.1 Sol, Gemini 4 Argon and Grok 4.7 are all GA in GitHub Copilot, with ZDR/no-training terms per provider (Claude Fable 5/5.1 excepted) | https://docs.github.com/en/copilot/reference/ai-models/supported-models ; .../model-hosting | live 2026-10-30 (no stamp) | H |
| 2 | Foundry lists Claude Sonnet 5.5 (Azure- and Anthropic-hosted GA), `gpt-6.1-sol`, `grok-4.7`; no Gemini on Learn pages; router pool lacks gpt-6.1-sol, claude-sonnet-5-5, grok-4.7 | https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/claude-models ; .../models-sold-directly-by-azure ; .../openai/concepts/model-router | 2026-09-21 ; live ; live | H presence, M absence/router |
| 3 | Foundry hosted-agent recovery re-enters the handler from the beginning; app must checkpoint and be idempotent (GA vs preview wording conflicts) | https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience ; https://devblogs.microsoft.com/foundry/microsoft-copilot-harness-in-foundry | 2026-09-10 ; 2026-10-28 | H semantics, M GA status |
| 4 | Cloud agent: write-access trigger, one `copilot/` branch, cannot approve/merge, workflows gated by default, requester cannot approve, signed commits, firewall | https://docs.github.com/en/copilot/concepts/security-governance-and-network-settings/risks-and-mitigations | live 2026-10-30 | H |
| 5 | Cloud sandboxes lack self-hosted runners/custom compute; Actions-based sessions support them (single repo, 28-day retention) | https://docs.github.com/en/copilot/concepts/copilot-surfaces/copilot-on-github | live 2026-10-30 (feature from 2026-10-28) | H |
| 6 | Copilot SDK/CLI can run headless with `GITHUB_TOKEN` (`copilot-requests: write`, org policy "Allow use of Copilot CLI billed to the organization", on by default) or an App installation token (1 h); `copilot --headless` serves JSON-RPC over TCP (no official container image); sessions resume by `sessionId`; soft `maxAiCredits` cap | https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-in-actions ; https://raw.githubusercontent.com/github/copilot-sdk/main/docs/auth/server-to-server-tokens.md ; .../setup/backend-services.md ; .../features/session-persistence.md ; .../features/session-limits.md | live 2026-10-30 ; SDK main, fetched 2026-10-30 | H (Actions) / M (SDK, being re-homed) |
| 7 | Fabric accepts SPN/MI only per API/item type (tenant setting needed); Entra FIC max 20 per identity, no wildcards, silent subject mismatch | https://learn.microsoft.com/en-us/rest/api/fabric/articles/identity-support ; https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-considerations | updated 2026-04-08 ; 2026-06-15 | H |
| 8 | APIM AI gateway gives token limits/metrics/content safety, Anthropic Messages (v2 tiers), unified model API (preview) | https://learn.microsoft.com/en-us/azure/api-management/genai-gateway-capabilities ; .../unified-model-api | 2026-06-25 ; 2026-06-26 | H features, M preview |
| 9 | LiteLLM had Critical advisories 2026-05-28, 2026-09-30, 2026-10-27; budgets fail open without a DB | https://github.com/BerriAI/litellm/security/advisories ; https://docs.litellm.ai/docs/proxy/users | live 2026-10-30 | H |
| 10 | Actions: run cap 35 days incl. waits, 30-day approval gate, 50 re-runs; concurrency = one running + one pending (newer pending replaces) | https://docs.github.com/en/actions/reference/limits ; .../workflow-syntax | live 2026-10-30 | H |

## 6. Gaps and uncertainties

- **Not verified on a primary page:** per-job time caps (6 h hosted / 5 d self-hosted; only secondary search summaries); ACA job `replicaTimeout` maximum; DTS and Foundry hosted-agent price rates (pricing pages not captured); ACA Sandboxes GA status; Temporal workflow-ID idempotency semantics; OpenRouter spend-limit features and model coverage.
- **Not read:** Google's direct-API terms; whether Bedrock or OpenAI-direct offer Sonnet 5.5 / GPT-6.1 Sol to us; whether the sold-by-Azure privacy page applies verbatim to Grok 4.7 (inferred from its "sold by Azure" listing).
- **Inferred, not observed:** Gemini's absence from Foundry (Learn pages only, portal not checked); Gemini 4 Argon post-intro pricing (only an AI search summary; Google blog confirms the introductory price); DTS entities as locks; APIM reaching Gemini via an OpenAI-compatible endpoint.
- **Doc conflicts left open:** Copilot SDK README (BYOK key-only) vs managed-identity setup doc; Learn "(preview)" vs blog "GA" for hosted-agent resilience; SDK rename to Microsoft Copilot SDK (timeline unknown). Cloud sessions in the SDK appear to need a user token or logged-in CLI identity, so service-identity use is unconfirmed.
- **No hands-on tests.** All durability claims are documentation-level. Suggested spikes: (1) kill a runner/pod mid-run and resume via `sessionId` plus branch; (2) SPN/MI call matrix against the Fabric item types we need; (3) Actions-based vs cloud-sandbox session for a Fabric validation workflow with auto-run approval; (4) APIM unified model API fronting Foundry plus Google.
- **Not researched:** Azure DevOps Pipelines limits and agent pools; Fabric capacity cost of ephemeral workspaces (T4); LiteLLM PyPI supply-chain claim (search tool returned 504s, UNVERIFIED).

## 7. Sources (URL | title | publication or updated date | primary or secondary)

1. https://github.com/github/copilot-sdk | github/copilot-sdk README (banner: "GitHub Copilot SDK is becoming Microsoft Copilot SDK") | fetched 2026-10-30 (live) | primary
2. https://blogs.microsoft.com/blog/2026/10/28/introducing-the-microsoft-copilot-harness-unlocking-the-potential-of-truly-multi-model-agentic-work/ | Introducing the Microsoft Copilot harness | 2026-10-28 | primary
3. https://devblogs.microsoft.com/foundry/microsoft-copilot-harness-in-foundry | Microsoft Copilot harness in Foundry Agent Service (public preview) + hosted-agent long-running resilience GA | 2026-10-28 | primary
4. https://raw.githubusercontent.com/github/copilot-sdk/main/docs/features/session-persistence.md | Copilot SDK: session resume and persistence | fetched 2026-10-30 (main branch) | primary
5. https://github.com/github/copilot-sdk/tree/main/docs | Copilot SDK docs index (setup: backend services, scaling, azure-managed-identity, cloud sessions, fleet mode, session limits) | fetched 2026-10-30 | primary
6. https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience | Resilience for long-running Foundry hosted agents | ms.date 2026-07-30, updated_at 2026-09-10 (title still says "(preview)"; 2026-10-28 blog says GA) | primary
7. https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents | Hosted agents in Foundry Agent Service | ms.date 2026-10-19, updated_at 2026-10-27 | primary
8. https://raw.githubusercontent.com/github/copilot-sdk/main/docs/setup/azure-managed-identity.md | Copilot SDK: Azure Managed Identity with BYOK (Foundry) | fetched 2026-10-30 (main) | primary
9. https://docs.github.com/en/copilot/reference/ai-models/supported-models | Supported AI models in GitHub Copilot | live 2026-10-30 (no date stamp on page) | primary
10. https://docs.github.com/en/copilot/reference/ai-models/model-hosting | Hosting of models for GitHub Copilot (data retention per provider) | live 2026-10-30 (no date stamp) | primary
11. https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing | Models and pricing for GitHub Copilot (AI credits, per-token rates) | live 2026-10-30 (no date stamp) | primary
12. https://docs.github.com/en/copilot/concepts/copilot-surfaces/copilot-on-github | GitHub Copilot on GitHub.com and Mobile ("Copilot in the cloud" from 2026-10-28; cloud sandboxes vs Actions-based) | live 2026-10-30 | primary
13. https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/automate-with-actions | Automating tasks with Copilot CLI and GitHub Actions | live 2026-10-30 | primary
14. https://github.com/github/gh-aw | GitHub Agentic Workflows (gh-aw) README: Actions + Agent + Safety; engines Copilot/Claude Code/Codex/Gemini/Pi; advisory GHSA-8h78-hpm7-29gg retired >=0.83.3,<0.85.4 | live 2026-10-30 | primary
15. https://github.github.com/gh-aw/introduction/architecture/ | gh-aw security architecture (3 trust layers, SafeOutputs, firewall, API proxy, MCP gateway, ARC DinD, Cloud Hypervisor microVM) | live 2026-10-30 | primary
16. https://learn.microsoft.com/en-us/agent-framework/overview/ | Microsoft Agent Framework overview (.NET/Python/Go; Go in public preview) | ms.date 2026-10-23, updated 2026-10-28 | primary
17. https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints | Agent Framework Workflows: Checkpoints (superstep checkpoints; InMemory/File/Cosmos storage) | ms.date 2026-09-16, updated 2026-09-21 | primary
18. https://github.com/microsoft/agent-framework/releases | Agent Framework releases (dotnet-1.26.0, python 1.23.0 changelog visible) | live 2026-10-30 | primary
19. https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/claude-models | Claude models in Microsoft Foundry (claude-sonnet-5-5: Hosted on Azure GA + Hosted on Anthropic infra GA) | ms.date 2026-09-21, updated 2026-09-22 | primary
20. https://learn.microsoft.com/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure | Foundry Models sold by Azure (gpt-6.1-sol 2026-09-29 listed; gpt-6.1-terra 2026-10-26) | live 2026-10-30 (date not shown) | primary
21. https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-grok | Deploy and use Grok models in Foundry (grok-4.7 GA-listed; Chat Completions + Responses) | ms.date 2026-10-05, updated 2026-10-06 | primary
22. https://learn.microsoft.com/azure/foundry/foundry-models/concepts/models-from-partners | Foundry Models from partners and community (no Gemini/Google match on page) | live 2026-10-30 | primary
23. https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-argon/ | Gemini 4 Argon announcement (GA via AI Studio + Gemini platform; $2/$10 intro pricing) | 2026-10-13 | primary (vendor marketing for benchmark claims)
24. https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/4-argon | Gemini 4 Argon | Gemini Enterprise Agent Platform (Google Cloud) docs | live 2026-10-30 | primary
25. https://learn.microsoft.com/azure/foundry/openai/concepts/model-router | Model router for Microsoft Foundry (version 2025-11-18, updated in place; pool lacks gpt-6.1-sol / claude-sonnet-5-5 / grok-4.7 as listed) | live 2026-10-30 (date not shown) | primary
26. https://learn.microsoft.com/en-us/azure/api-management/genai-gateway-capabilities | AI gateway capabilities in Azure API Management | ms.date 2026-05-29, updated 2026-06-25 | primary
27. https://learn.microsoft.com/en-us/azure/api-management/unified-model-api | Create and manage a unified model API (preview; OpenAI Chat Completions front, OpenAI/Anthropic backends, aliases, failover) | ms.date 2026-05-29, updated 2026-06-26 | primary
28. https://learn.microsoft.com/en-us/azure/foundry/control-plane/how-to-enforce-limits-models | Enforce token limits for models (Foundry Control Plane + AI Gateway; project-level TPM + quota) | ms.date 2026-07-15, updated 2026-08-13 | primary
29. https://docs.litellm.ai/docs/proxy/users | LiteLLM: Budgets, rate limits (virtual keys, team/member/agent budgets; DB required) | live 2026-10-30 (references v1.94/v1.95) | primary
30. https://openrouter.ai/docs/guides/features/zdr | OpenRouter Zero Data Retention (per-model-group ZDR; note planned 2026-10-27 CSAM screening incl. ZDR traffic) | live 2026-10-30 | primary
31. https://github.com/BerriAI/litellm/security/advisories | LiteLLM security advisories list (Critical: GHSA-7hp6-4w63-5g45 2026-09-30; GHSA-w4c7-34wj-hqm8 2026-10-27; GHSA-4xpc-pv4p-pm3w 2026-05-28; High GHSA-g5ff-637f-6q2m 2026-10-01) | live 2026-10-30 | primary
32. https://docs.github.com/en/actions/reference/limits | GitHub Actions limits (35-day workflow run incl. waiting/approval; 30-day environment approval gate; 50 re-runs; 256 matrix jobs; 500 runs/10s queue) | live 2026-10-30 (no date stamp; 'subject to change') | primary
33. https://learn.microsoft.com/en-us/azure/container-apps/jobs | Jobs in Azure Container Apps (manual/schedule/event triggers; replicaTimeout/replicaRetryLimit; start-job permission leaks secrets warning; self-hosted runner pattern) | ms.date 2026-09-16, updated 2026-09-16 | primary
34. https://learn.microsoft.com/en-us/rest/api/fabric/articles/identity-support | Identity support for Fabric REST APIs (user / service principal / managed identity; tenant setting; per-API support; unsupported-item examples) | ms.date 2024-08-04, updated_at 2026-04-08 | primary
35. https://learn.microsoft.com/en-us/fabric/cicd/cicd-overview | Introduction to CI/CD in Microsoft Fabric (Git integration w/ SPN, deployment pipelines, Variable library, Fabric CLI, fabric-cicd, branch-out workspaces) | ms.date 2026-08-23, updated 2026-09-29 | primary
36. https://learn.microsoft.com/en-us/azure/durable-task/scheduler/durable-task-scheduler | Durable Task Scheduler (managed durable-execution backend for Durable Functions and Durable Task SDKs on ACA/AKS/App Service/VMs; Dedicated + Consumption SKUs) | ms.date 2026-10-13, updated 2026-10-15 | primary
37. https://docs.openhands.dev/overview/introduction.md | OpenHands introduction (Agent Canvas, Software Agent SDK + Agent Server, Cloud, Enterprise, Sandbox Server, Automation Server; Local GUI deprecated) | live 2026-10-30 (no date stamp) | primary
38. https://github.com/OpenHands/automation | OpenHands Automation Service (BETA; cron + webhook-triggered automations; Postgres; run history) | live 2026-10-30 | primary
39. https://temporal.io/pricing | Temporal Cloud pricing ($50 per million actions PAYG, $25 with volume; storage $/GBhr; 99.9% SLA; durable AI agents via OpenAI Agents SDK + Google ADK) | live 2026-10-30 (vendor page, no date) | primary (vendor marketing)
40. https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/claude-models-hosting-comparison | Compare hosting options for Claude models in Foundry (Anthropic = seller, operator, data processor; Azure-hosted vs Anthropic-hosted residency) | ms.date 2026-09-21, updated 2026-09-22 | primary
41. https://raw.githubusercontent.com/github/copilot-sdk/main/docs/features/session-limits.md | Copilot SDK: Session limits (maxAiCredits soft cap; usage_checkpoint events) | fetched 2026-10-30 (main) | primary
42. https://docs.github.com/en/copilot/concepts/security-governance-and-network-settings/risks-and-mitigations | Risks and mitigations for GitHub Copilot cloud agent (write-access trigger, single copilot/ branch, no self-approval, Approve-and-run-workflows gate, firewall, signed commits, automations) | live 2026-10-30 (no date stamp) | primary
43. https://docs.github.com/en/copilot/concepts/agent-capabilities/agent-powered-workflows-and-operations/about-automations | Copilot automations (schedule / repo event / API triggers; tools, model, AI-credit limits; private/internal repos only) | live 2026-10-30 | primary
44. https://docs.github.com/en/billing/concepts/product-billing/github-actions | GitHub Actions billing (self-hosted runners free; standard Linux $0.006/min example) | live 2026-10-30 | primary
45. https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect | Authenticate to Azure from GitHub Actions by OIDC (federated credential on Entra app or user-assigned managed identity; environment secrets + approvals) | ms.date 2024-07-01, updated 2026-01-21 | primary
46. https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-llm-models | Adding LLM models to GitHub Copilot CLI (BYOK providers.json: openai-compatible / azure / anthropic; apiKey or bearerToken) | live 2026-10-30 | primary
47. https://learn.microsoft.com/azure/devops/boards/github/work-item-integration-github-copilot | Use GitHub Copilot with Azure Boards (work item -> branch + draft PR; GitHub repos only, Azure Repos NOT supported) | ms.date 2026-06-17, updated 2026-07-23 | primary
48. https://learn.microsoft.com/azure/container-apps/sandboxes-overview | Azure Container Apps Sandboxes overview (Microsoft.App/SandboxGroups; suspend/resume snapshots; egress/ingress policy) | ms.date 2026-05-26, updated 2026-10-16 (GA/preview status not stated on page) | primary
49. https://docs.github.com/en/billing/concepts/product-billing/cloud-and-local-sandboxes | Billing for cloud and local sandboxes for GitHub Copilot ($0.000024/compute-sec, $0.000003/GiB-sec, $0.005/GiB-month snapshot) | live 2026-10-30 | primary
50. https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-considerations | Workload identity federation for app considerations (max 20 FICs per app/UAMI, no wildcards, silent failure on subject mismatch) | ms.date 2024-02-28, updated 2026-06-15 | primary
51. https://raw.githubusercontent.com/github/copilot-sdk/main/docs/integrations/microsoft-agent-framework.md | Copilot SDK: Microsoft Agent Framework integration (Copilot SDK as MAF agent provider; .NET Microsoft.Agents.AI.GitHub.Copilot prerelease; Python agent-framework-github-copilot) | fetched 2026-10-30 (main) | primary
52. https://azure.microsoft.com/en-us/pricing/details/foundry-agent-service/ | Foundry Agent Service pricing (prompt agents no extra charge; hosted agents billed on container compute per hour; tokens separate) | live 2026-10-30 | primary
53. https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax | Workflow syntax (concurrency groups: 1 running + pending replaced by default; cancel-in-progress) | live 2026-10-30 | primary
54. https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-in-actions | Using Copilot CLI in GitHub Actions with GITHUB_TOKEN (copilot-requests: write; org policy; non-interactive runs auto-deny unapproved tools; fork-PR warning) | live 2026-10-30 | primary
55. https://raw.githubusercontent.com/github/copilot-sdk/main/docs/setup/backend-services.md | Copilot SDK: Backend services (headless CLI server over TCP; no official Docker image) | fetched 2026-10-30 (main) | primary
56. https://raw.githubusercontent.com/github/copilot-sdk/main/docs/auth/server-to-server-tokens.md | Copilot SDK: Server-to-server authentication (GITHUB_TOKEN in Actions; GitHub App installation token, 1 h) | fetched 2026-10-30 (main) | primary
57. https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy | Data, privacy and security for Foundry Models sold by Azure (Microsoft DPA; no training; abuse-monitoring storage) | ms.date 2026-05-18, updated 2026-06-05 | primary
58. https://learn.microsoft.com/en-us/rest/api/fabric/articles/long-running-operation | Fabric REST: Long running operations (202 + Location, x-ms-operation-id, Retry-After; Get Operation State/Result) | ms.date 2025-03-14, updated 2025-07-02 (stale >12 months but foundational) | primary
59. https://www.bing.com (web_search AI summaries citing warpbuild.com, dev.to, markaicode.com; Fabric identity and Gemini availability summaries) | per-job timeout limits (6 h hosted / 5 d self-hosted) and Gemini 4 Argon post-intro price | 2026-10-30 | secondary, used only where flagged UNVERIFIED






