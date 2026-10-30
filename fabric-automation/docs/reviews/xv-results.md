# Cross-verification results

Date 2026-10-30. Verifiers: Gemini 4 Argon (this section complete), GPT 6.1 Sol (running), Grok 4.7 (running), GPT 6.1 Sol wave 2 on T7 claims (running). Claim IDs match the "Decision-driving claims" tables in `research/raw/`. Verdicts are the verifier's own, recorded by the orchestrator; corrections are applied to the digest and design as noted.

Verdict key: C = confirmed, P = partly confirmed, X = contradicted, U = unverifiable.

## 1. Gemini 4 Argon: platform, security and runtime claims (T1, T5, T6)

Result: 26 C, 4 P, 0 X, 0 U. Gemini cannot write files, so this is the orchestrator's transcription of its returned table.

| ID | V | Correction or addition | Design impact |
|---|---|---|---|
| T1-1 | C | Extra approval for bot-attributed PRs needs an existing rule of at least one approval. Claude and Codex agents on GitHub are preview. Doc URL moved to `/en/copilot/concepts/agent-capabilities/about-agents/about-third-party-coding-agents` | Require at least one human approval by ruleset |
| T1-2 | C | "Bot user" is the digest's inference, not stated on the page. Copilot Automations and `gh-aw` with `GITHUB_TOKEN` run unattended without a bot user | Prefer `gh-aw` or headless CLI with `GITHUB_TOKEN` |
| T1-3 | C | A fifth engine (`Pi`) exists. **Threat detection defaults to `warn` mode** (annotated outputs still publish) unless `strict` is set. Cap of 1,000 AI credits per run | If `gh-aw` is used, enable strict mode |
| T1-4 | C | The SDK rename quote is on the `github/copilot-sdk` README. Foundry sandbox compute is billed from 2026-12-01 (free runtime until then) | Watch, budget from December |
| T1-5 | C | Base-branch config restore applies to `claude-code-action` only, not `base-action`. `package.json`, `Makefile` and `bunfig.toml` stay at PR head | Never execute PR-head scripts in privileged triggers |
| T1-6 | C | `--full-auto` was removed from `codex exec`. `drop-sudo` is unsupported on Windows runners. Secret proxy substitution works on HTTPS port 443 only | Linux or macOS runners only |
| T1-7 | C | Jules goes read-only 2026-11-11 and ends 2026-12-31 (to Antigravity). Amazon Q IDE plugins end 2027-04-30 (to Kiro) | Avoid both |
| T1-8 | C | Overall merge rate across the five agents is 71.48% (24,014 of 33,596). Reviewer abandonment is the top non-merge reason | Small PRs |
| T1-9 | C | Cursor Bugbot can be configured to fail on unresolved issues. Claude Code Review is unavailable under ZDR, HIPAA or CMEK. Bugbot default for public-repo external PRs turned off for teams created from 2026-10-22 | Never use default AI review as a merge gate |
| T1-10 | **P** | Primary sources found: Comment and Control is the JHU paper arXiv 2605.11229 (disclosed 2026-04-15; 4,714 GitHub workflows across 15 Actions and 8 n8n templates hijacked). PocketOS is the founder's post-mortem (2026-04-25 about the 2026-04-24 outage). The cited OWASP Q1 report contains neither incident. **PocketOS was not prompt injection**: an agent (Cursor running Claude Opus 4.6) guessed during a staging credential mismatch and used an unscoped CLI token found in the repo to call a volume-delete mutation | Attribute correctly. Isolate staging and production identities, strip credentials from agent runtimes |
| T5-1 | C | - | Deterministic boundaries, not prompt filters |
| T5-2 | C | - | Split intake parsing, secret access and writes across stages |
| T5-3 | C | Comment and Control disclosed 2026-04-15, CSA note 2026-04-17. None of the three vendors assigned a CVE | Never pass raw issue text into secret-bearing jobs |
| T5-4 | C | **The Copilot firewall applies only to processes the agent starts through its Bash tool. It does not apply to MCP server processes or setup steps** | Restrict MCP servers separately (design C4 already requires egress control for every process) |
| T5-5 | C | The microVM option exists only on eligible GitHub-hosted runners; the default is Docker isolation | Do not count on microVM isolation |
| T5-6 | C | Composite calls fail if an underlying item or job type (for example Data Warehouse creation or a Notebook on-demand job) lacks service-principal support | Spike S2 and S3 must test notebook job runs under a service principal |
| T5-7 | C | Also incompatible with F SKU trials, OneLake Diagnostics (unless same-workspace lakehouse), external data sharing, and portal rule edits with private links | Separate report workspaces from protected data workspaces |
| T5-8 | C | Anthropic also shows reward hacking generalizing to emergent misalignment (12% sabotage rate in Claude Code evaluations) | Make tests and scoring immutable to agents |
| T5-9 | C | 3,984 skills scanned. 10.9% contained hard-coded secrets. 8 confirmed malicious skills were still live at publication | Pin and hash all skills |
| T5-10 | **P** | **"Covered models" means Mythos-class only (Claude Fable 5 and 5.1, Mythos 5 and 5.1).** Sonnet 5.5, Opus 5.5 and Haiku 5.5 keep zero data retention. Eligible ZDR organisations get a Fable exemption through 2026-12-31 | Data-class matrix: Sonnet 5.5 keeps ZDR. Avoid Fable and Mythos for confidential content |
| T6-1 | C | Gemini uses durable caching (encrypted data held up to 24 hours). Anthropic beta features such as Messages API tool search fall outside ZDR | Avoid beta features for confidential content |
| T6-2 | C | Foundry GA: `claude-sonnet-5-5`, `gpt-6.1-sol` (2026-09-29), `grok-4.7`. The model router (2025-11-18) omits all three. Live catalog check: zero Gemini models in Foundry (Gemini is on Azure Databricks only) | Deploy named models directly. Gemini needs Google Cloud behind the gateway |
| T6-3 | **P** | The Learn page title still says preview, but the 2026-10-28 Foundry blog announces GA of long-running resilience. On the Responses protocol, crash recovery needs stored background responses | Persist external checkpoints regardless |
| T6-4 | C | Triggered through `@copilot` on an existing PR, it pushes to that PR's branch, not a new `copilot/` branch. Copilot Automations can trigger on schedules and events | Account for existing-PR writes |
| T6-5 | C | Since 2026-10-28 a third environment option, Remote (custom environment), exists beside cloud sandbox and Actions | Use Actions or Remote for self-hosted runners |
| T6-6 | C | A 1-hour App installation token cannot be refreshed in place: restart the SDK client or runtime with a new token. Headless TCP has no built-in authentication | Build a custom CLI image, bind headless TCP to loopback, restart the client on token refresh |
| T6-7 | C | Concurrent creation of several federated credentials on one user-assigned managed identity fails with HTTP 409 (provision serially). Unsupported in Malaysia South | Provision credentials serially, at most 20 per identity |
| T6-8 | C | The unified model API (preview) also supports classic APIM tiers through the AI Gateway early release channel | Use the AI gateway for hard token quotas |
| T6-9 | C | Also a High file-read advisory on 2026-10-01 and two Moderate SSRF advisories | Avoid LiteLLM unless patched and private |
| T6-10 | **P** | **"One running, one pending" is only the default (`queue: single`).** `concurrency: { group, queue: max }` queues up to 100 pending runs or jobs per group in FIFO order (not combinable with `cancel-in-progress`) | D0 can queue bursts up to 100 on Actions. Resumability is still needed |

### Gemini: other September and October 2026 developments

- 2026-10-29: Google Jules wind-down announced.
- 2026-10-28: Microsoft Copilot harness in Foundry (preview, free runtime until 2026-12-01), hosted-agent resilience GA, Copilot SDK rename, "Copilot in the cloud" with three environments.
- Foundry added `gpt-6.1-sol` (2026-09-29) and `gpt-6.1-terra` (2026-10-26); the model router still tops out at `gpt-6-astra`, `claude-opus-5`, `sonnet-5`, `fable-5-1` and `grok-4.6`.
- LiteLLM advisories on 2026-09-30, 2026-10-01 and 2026-10-27.
- 2026-10-22: Cursor Bugbot public-repo default changed.
- 2026-09-01: Fabric outbound access protection documentation update.

## 2. GPT 6.1 Sol: Fabric platform claims (T4, T3a, T3c, plus second opinions)

Result: 19 C, 7 P, 1 X, 0 U over 27 claims. GPT cannot write files, so this is the orchestrator's transcription.

Contradicted:

| ID | Correction | Design impact |
|---|---|---|
| T4-C8 | The local Fabric MCP server's run-pipeline command triggers a pipeline run (a Job Scheduler job) in release 1.6.0. So "no Fabric MCP server exposes Job Scheduler runs" is wrong for pipelines. Notebook runs, Git, deployment pipelines and report rendering stay uncovered. The hosted Core MCP documents browser OAuth, not service principals | The local MCP can run pipelines |

Partly confirmed:

| ID | Correction | Design impact |
|---|---|---|
| T4-C5 | The ALM page (2026-08-31) says service principals are supported for data agents "only as part of ALM scenarios". The SDK page (2026-10-14) says "You can use either a user account or a service principal", and the MCP page (2026-09-04) says the token "can represent either a user identity or a service principal" | Endpoint-specific. Do not encode "ALM only" as universal. Spike S6 |
| T4-C9 | Item pairing is maintained automatically and cannot be set through an API, so it is not "UI-only". Rules and compare-API gaps, the 300-item cap and the inbound-protection restriction are confirmed | Implement our own diffs. Account for automatic pairing |
| T4-C10 | The default retention for collaborative workspaces is 7 days and the period is configurable (the verifier's own workspace shows 30 days). Storage billing and re-creation are confirmed. "With new IDs" is not explicitly stated | Budget retained storage. Reconcile re-created items |
| T3a-8 | Osmos is preview and uses `az login` (confirmed). "Undocumented API" is not established by the overview | Do not assume a stable automation contract |
| T3a-9 | The skill installs the CLI with `npm install -g @microsoft/powerbi-report-authoring-cli@latest` (skill reference, commit 2026-09-24). The npm page returned 403 and the registry failed TLS retrieval, so publication is unverified | Verify installability and pin the version |
| T1-1 | Workflow holding is configurable ("Optionally, you can configure Copilot to allow workflows to run automatically"). The extra approval is conditional | Enforce policy, do not trust defaults |
| T1-2 | The tasks API needs a user identity. A bot account is not required, and delegated authorization can run unattended | Not a blocker |

Confirmed, with details worth keeping:

- **T3a-2** The FabricIQ MCP page says: "Service-principal and application-only authentication aren't supported." Grok did not find this sentence. **Resolved by the orchestrator fetching the page directly:** it appears twice (authentication section and limitations), and the page adds that the server does not support Fabric ontologies or data agents. GPT was right.
- **T3a-4** **Released versions through 1.6.0 (2026-10-18) have no definition payload on `create-item`. The `main` branch adds it (commit `96b20bc`, merged 2026-10-29), unreleased.** This settles the earlier disagreement: Grok read the unreleased README, and this host's build matches the released behaviour. Pin the version and keep the REST creation path.
- **T4-C1, C2, C3, C4** Service-principal conditions and exclusions for Update from Git and Bulk Import. No dedicated branch-out operation. Update from Git does not populate lakehouse tables, though supported inter-item dependencies can auto-bind. The public-API service-principal switch is on by default, the creation switch is off by default, and the GitHub switch is off by default.
- **T4-C6** Shared limits of 500, 200 and 500 per minute per identity, plus Job Scheduler limits of 100 submissions and 100 reads per user per minute. The "300" on the throttling page is illustrative.
- **T4-C7** Pausing makes the paused F capacity, not the whole tenant, unavailable. Settlement is billed.
- **T3a-1** 25 unique skills at v0.3.20.
- **T3a-3, T3a-5, T3a-6, T3a-7** Local Power BI Authoring MCP is GA with service principal and `--readonly`. The data-agent conflict above. Evaluation SDK 0.1.33a0. `fabric-cicd` 1.4.0 (2026-10-07) does a full deployment every time and `fab` 1.8.0 (2026-10-20) is current.
- **T3a-10** The old ontology experience retires 2027-01-31. The new-definition URL the report gave was wrong (GPT read an official replacement). The shipped skill still authors the old entity-type JSON.
- **T3c-7** `exportToFile` supports 500 concurrent requests per capacity. PNG export also needs a tenant switch that is off by default.
- **T6-3** Resilient background execution is opt-in, and the preview label is superseded by the 2026-10-28 GA announcement.
- **T6-6** The `GITHUB_TOKEN` route is organization-workflow scoped. The AI-credit cap is soft: "one response can exceed the configured value".
- **T5-1** Applies to the evaluated defences, not every defence.

Other developments: on 2026-10-14 the data-agent SDK documentation moved from the Assistants route to Responses and MCP. On 2026-10-22 the Update from Git documentation added **beta deployment plans with pre and post actions**, which may help close the post-deploy gap. On 2026-10-28 hosted-agent resilience went GA. On 2026-10-29 the `create-item` definition support was merged but not released.

<!-- NEXT -->

## 3. Grok 4.7: frameworks, data platforms, BI and testing (T2, T3b, T3c) plus Fabric second opinions

Result: 23 C, 10 P, 0 X, 0 U over 33 claims. Grok's own full table is in `reviews/xv-grok-claims.md`. No claim was wholly false, but several bundled an accurate fact with an inference or a status the cited page does not state.

Partly confirmed claims and their corrections:

| ID | Correction | Design impact |
|---|---|---|
| T2-C3 | The cited pages say Anthropic does not support routing Claude Code to non-Claude models through any gateway, and that the SDK runs the Claude Code binary. They do not say other vendors' models cannot be sub-agents. That part was the digest's inference | Keep verifiers in separate contexts, but do not state it as a documented limit |
| T2-C10 | Roo Code is GitHub-archived. Continue's README says read-only, and AutoGen's README carries an archive notice, but neither has the GitHub archived flag set (AutoGen's 2026-10-28 commit only added the notice, and Continue was pushed 2026-10-30). Aider's last release is v0.86.0 (2025-08-09), last push 2026-05-22 | Do not build on them, but do not call them GitHub-archived |
| T3b-C2 | Genie auto-approve is labelled "(Recommended)" and documented as "a productivity feature, not a security boundary". Scheduled tasks always auto-approve with the creator's permissions. It is not stated as the default | Scheduled runs are not a boundary |
| T3b-C6 | dbt v2 GA and Wizard Desktop public beta (October 2026) confirmed. "Agent authorship disclosure" is not on the cited release notes | Do not cite authorship from those notes |
| T3b-C8 | Headline table: Semantic Layer 98.2% and 100% against text-to-SQL 90.0% and 84.1% on 11 questions, vendor-run. It is not labelled "with modeling", and another table shows text-to-SQL at 50% to 65% | Do not treat 98% as general |
| T3c-8 | Maia: skills are "guidance, not hard-coded rules". ThoughtSpot's page is about Git for TML, not an agent merge gate. Omni's Auto mode applies changes immediately | Branch, validate, human merge is common but not universal |
| T3c-9 | Fivetran and dbt Labs merger completed 2026-06-01. The GX Cloud page is future tense ("definitive agreement to acquire") and a SQLMesh article still says the dbt merger "hasn't closed". Ascend is winding down | The category map is time-sensitive |
| T4-C8 | The hosted Core MCP tools page (updated 2026-10-27) lists `update_item_definition` and says "OAuth 2.0 via Microsoft Entra ID". Job Scheduler, deployment pipelines and report rendering are absent. "Delegated-user" is the digest's wording and service principals are simply not documented | Do not expect Git or jobs on hosted Core |
| T3a-2 | The FabricIQ MCP page says generally available, read-only toolset, delegated OAuth 2.0. The sentence "service principals are unsupported" was not found on it. To be reconciled with GPT's verdict on the same claim | Do not assume service principals for FabricIQ |
| T3a-4 | The current README of the local Fabric MCP server says `core_create-item` accepts a definition or creation payload. Releases 1.5.0 (2026-10-14) and 1.6.0 (2026-10-18) exist. The first version with the payload was not found. The build in this host exposes no such parameter | **Version-dependent.** Pin the server version and verify in Phase 0 |

Confirmed with details worth keeping:

- **T2-C1** MCP 2026-07-28 is current. Dynamic Client Registration remains available for old authorization servers.
- **T2-C2** Microsoft Agent Framework 1.0 is MIT with superstep checkpoints. The `ClaudeAgent` wrapper needs the `--pre` package. The provider table (ms.date 2026-10-22) has no xAI or Grok provider.
- **T2-C5** The independent-critic pattern is not a uniform gain: Terminal-Bench 2.1 improved by 4.9 points but DeepSWE fell by 1.5.
- **T3b-C9** The 82.7% is of 81 failed transformation tasks, not of all failures.
- **T3c-4** Tabular Editor's `te` CLI is Limited Public Preview. One page says it expires 2026-10-31 and another 2026-12-31. The cited `te-cli.html` page returns 404. Tabular Editor 2 needs no TE3 licence.
- **T4-C4** The public-API service-principal switch is on by default. The one for creating workspaces, connections and deployment pipelines is off by default for new customers. GitHub sync is off by default.
- **T3a-3** The local Power BI Authoring MCP is GA with `--readonly` and `--authmode=serviceprincipal` (v1.0.0, 2026-09-25).
- **T3c-6** Fab Inspector is a community project, not supported by Microsoft (v3.4.0).
- **T3c-1, T3c-2, T3c-3** `datacontract-cli` supports Fabric through its SQL Server type (v1.2.9, 2026-10-30). ODCS 3.2.0 variables exist. Datafold CI is Classic-only and OSS data-diff is archived.

Not accessible to Grok: GitHub code search (401), the OpenAI harness post date, the exact version that first added a definition payload to `create-item`.

<!-- NEXT -->

## 4. GPT 6.1 Sol, wave 2: evaluation and metrics claims (T7)

Result: 4 C, 6 P, 0 X, 0 U. The numbers are authentic. The corrections concern denominators, normalization and generalization.

| ID | V | Correction or addition | Design impact |
|---|---|---|---|
| T7-1 | P | Recomputed from the YAML: p80 69.87, 53.88 and 185.91 minutes; p50 11.98, 5.70 and 17.41 hours. The measurements are frozen (data to 2026-05-08, page frozen 2026-09-08) and do not establish current frontier capability. METR warns that estimates above 16 hours are unreliable | Calibrate unit size locally. Do not fix an autonomy-hour budget |
| T7-2 | P | The gap is 24.2 percentage points (standard error 2.7) between baseline-normalized overall scores, including imputed failures, against a 68% golden-patch acceptance baseline. It is not a raw rejection rate among test-passing PRs. 296 PRs, four maintainers, three repositories | Passing tests cannot substitute for maintainability review |
| T7-3 | C | 54% is the Conflicting-SWEbench variant and 76% the Oneoff variant. Loosening the same Conflicting prompt gave 66%. Abort option 54% to 9%. Monitor sensitivity 42% to 65%. Deliberately impossible tasks, not production prevalence | Protected tests, escalation and independent validation together |
| T7-4 | C | Laban: 39% average degradation across six generation tasks and more than 200,000 simulated conversations. Ambig-SWE: up to 74% relative improvement (ICLR 2026), not percentage points | Make clarification an explicit intake stage |
| T7-5 | P | 39 configurations, 219 PRs. Precision 77.8% to 90.2%. Recall 5.65% to 60.17% (the range goes below 10%). Copilot recall 21.8%, 23.0%, 28.0%. Cursor 9.57%. "Typical commercial" is an undefined cohort | Layer reviewers with tests. Measure missed defects independently |
| T7-6 | P | DORA reports relationships, not causes. Enterprise paper v2 (2026-10-27): 802 developers, 196,212 PRs, volume 3.1 times, reviewer pool 1.5 times, about 2.07 times the load. The mandate gave about 12% throughput gain at individual adoption, doubling only by month ten. Faros: review time +91%, PR size +154% (observational) | Track review queues, stability and batch size with throughput |
| T7-7 | P | OpenAI audit (2026-07-08): 200 of 731 (27.4%) automated, 249 of 731 (34.1%) human, about 30%. It stopped reporting SWE-bench Verified scores. ELT-Bench: 67 of 81 audited failed transformation tasks (82.7%) contained benchmark errors, but 218 of 660 (33.0%) column mismatches were benchmark-attributable, so 67% stayed agent-attributable | Audit specifications, fixtures and graders before interpreting failures |
| T7-8 | C | 94 single-shot tasks. Sonnet 5.5 rank 12, 84.59% (accuracy 86.17%, syntax 97.87%, 81 of 94). Gemini 4 Argon rank 8, 87.54% (88.3%, 98.94%, 83 of 94). Grok 4.7 rank 6, 91.22% (92.55%, 100%, 87 of 94). GPT 6.1 Sol rank 5, 91.42% (92.55%, 96.81%, 87 of 94). Leader GPT-6 Astra 95.91%, 91 of 94. Tests model understanding, not model design or requirements | Benchmark DAX generation separately from end-to-end business correctness |
| T7-9 | P | 16% of Sonnet 4 requests at the worst hour (2025-08-31), postmortem 2025-09-17. It does not identify a pinned model ID. "Difficult to distinguish from normal variation" referred to user reports | Pin versions and run regression canaries |
| T7-10 | C | "In practice users accept 93%" refers to manual permission prompts, from Anthropic's auto-mode post (2026-03-25, modified 2026-10-18). Sampling period and sample size undisclosed | Risk-tier approvals instead of repeated click-through |

### Wave 2: other developments

- METR's 2026-09-08 freeze undermines "current frontier" wording.
- The enterprise paper's v2 (2026-10-27) stresses a modest early gain.
- DAX benchmark v2 (2026-10-27) strengthens the evidence for native DAX generation but not for autonomous requirements-to-production delivery.
