# Fabric Code Factory — Decision register

Version 0.1 · 2026-10-30 · Status: working list. Leanings are provisional and come only from evidence gathered so far. Nothing here is decided until the design is validated by the model panel.

## Principles (from the requirements and the first findings)

1. Reuse before rebuild: official Fabric skills and MCP tools first, factory-authored skills only where there is a gap.
2. Deterministic outer loop. Agent loops run only inside bounded steps.
3. Agents propose, the executor disposes. Agents emit declarative changes. A policy-enforcing executor applies them.
4. Least privilege, no standing secrets, separation of duties. The author of a change never approves it.
5. Everything is idempotent, resumable and auditable. A host restart must not lose or duplicate work.
6. Evidence over claims. Every gate produces an artifact a reviewer can open.
7. Humans approve. Promotion beyond dev stays manual in the pilot.
8. Seams, not lock-in: Git host, intake channel, model gateway, runtime and workload packs are replaceable.

## Decisions

Status: Open = no leaning yet. Leaning = provisional direction from evidence. Evidence threads: T1 to T7 (research reports) and O1 (orchestrator grounding). Two local environment surveys also exist and are not shared.

| ID | Decision | Options | Evidence | Provisional leaning | Status |
|---|---|---|---|---|---|
| D-01 | Orchestration style | Workflow-first state machine with bounded agent steps; agent-loop-first | T2, T6, T7 | Workflow-first outer loop. Evidence so far is vendor narrative, not controlled studies | Leaning |
| D-02 | Runtime and hosting | GitHub-native; Azure-native; self-hosted OSS; hybrid | T6, T1 | Open | Open |
| D-03 | Durable state and resume | Durable workflow engine; run ledger in the repo plus queue; CI run state | T6, T2 | Open. Must survive host restarts (lived incident on 2026-10-30) | Open |
| D-04 | Implementer agent engine | Copilot SDK or CLI headless; Claude Agent SDK; Microsoft Agent Framework with a Claude wrapper; Copilot coding agent | T1, T2, T6 | Open. T2 found Agent Framework the best fit for a Claude lead, with GPT, Gemini and Grok as read-only verifiers | Open |
| D-05 | Multi-model verification policy | Which model verifies what; independence rules; tool-less read-only verifiers; gateway path | T2, T6, T7 | Verifiers read-only and tool-less. Model reachability confirmed through the Copilot harness (2026-10-30). Enterprise path open | Leaning |
| D-06 | Intake channel and form | GitHub Issue form; Azure Boards; Teams or Forms through a gateway | T7, T1 | GitHub Issue form as canonical (assumption A2) | Leaning |
| D-07 | Spec format and clarification policy | Structured spec file with Given/When/Then; spec-driven tooling; ask-once policy | T7, T2 | Open | Open |
| D-08 | Git model | Branch per requirement; one writer per branch; protected main; signed commits; Git as source of truth | O1, T4, L1 | Leaning: Git is the source of truth, factory-managed workspaces are downstream-only | Leaning |
| D-09 | Git provider | GitHub (tenant switch plus stored token); Azure DevOps (service principal credential) | O1, T4, T6 | Open. Depends on whether the tenant admin can enable the GitHub switch (open question 7) | Open |
| D-10 | Validation deployment path | Git-connected branch workspace with workspace relations; definition push through fabric-cicd or APIs into an unconnected workspace | O1, T4 | Open. The second path removes the stored token from the loop. Needs a Phase 0 spike | Open |
| D-11 | Ephemeral environment and capacity | Workspace per branch or per run; dedicated sandbox capacity; time to live; pause and resume; capacity-unit budgets | O1, L2, T4 | Dedicated small sandbox capacity (assumption A10). Resume and pause route unverified | Leaning |
| D-12 | Test data strategy | Synthetic generators; sampled or masked copies; shortcuts | T3b, T3c, T4 | Synthetic only in the pilot (assumption A4) | Leaning |
| D-13 | Quality gate catalog | Per workload pack: static, functional, data-quality, performance and cost, security | T3a, T3b, T3c, T7 | Open. Must include a test-integrity guard | Open |
| D-14 | Executor and tool surface | Policy-enforcing executor; MCP where capable, REST or CLI where not; a factory-owned MCP facade for agents | O1, L2, T5 | Leaning: agents never hold tenant credentials or raw tools (FR-31) | Leaning |
| D-15 | Identity and secrets | Managed identity; workload identity federation; service principal; per-run scoped credentials; just-in-time access | T5, T6, O1 | Open. Git provider credentials live in Fabric connections, never in the agent runtime | Open |
| D-16 | Sandbox and network isolation | Ephemeral containers or VMs; egress allow-list; no run-time package installs | T5, T6, L1 | Open. Pinning and allow-lists required (NFR-15) | Open |
| D-17 | Untrusted intake handling | Spotlighting; plan-then-execute; CaMeL-style designs; human confirmation for sensitive actions | T5, T7 | Leaning: intake text is data, never instructions (FR-05) | Leaning |
| D-18 | Knowledge pack architecture | Official plugins pinned plus a factory plugin; templates; golden examples; refresh process; content scanning | T2, T3a, L1, O1 | Leaning: install official plugins from the marketplace, pinned, and ship the factory pack as its own plugin | Leaning |
| D-19 | Evaluating the factory itself | Golden set; seeded-defect red team set; regression on prompt, skill and model changes; shadow and canary; real-state verifiers (checks against actual service state) | T7, L1 | Open | Open |
| D-20 | Observability and audit | Trace ID from intake to merge; OpenTelemetry GenAI traces; run ledger; tamper-evident logs | T5, T6, T7 | Open | Open |
| D-21 | Cost and runaway controls | Per-run and per-day budgets for model spend, capacity and time; kill switch; step limits | T5, T6 | Open | Open |
| D-22 | Reviewer ergonomics and evidence bundle | PR template; one-page risk-ranked summary; batch size; risk tiers | T7 | Open | Open |
| D-23 | Promotion beyond dev | Manual through deployment pipelines or fabric-cicd; rules are portal-only; no compare API | O1, T4, L1 | Leaning: manual in the pilot | Leaning |
| D-24 | Workload-pack roadmap | Order of packs after the pilot slice; which official skills each pack wraps; which skills must be authored | T3a, T4, O1 | Pilot: semantic models, reports, data agents and ontology. Data-agent skill must be factory-authored | Leaning |

## Constraints that bind several decisions

- Fabric allows one writer per branch and one Git operation at a time per workspace (D-08, D-10, D-03).
- The MCP surface covers about half of the factory's operations (D-14, D-15).
- Item-type support in Git integration is mostly preview for the pilot types (D-10, D-24).
- Official skills assume interactive confirmation, and one plugin floats on `@latest` (D-14, D-16, D-18).
- Background agents in our own tooling were cancelled by a host restart (D-03).

## Walk-through scenarios to stress the design (used in validation)

1. Add a year-over-year measure to a semantic model and a card to a report.
2. Add a column and update data agent instructions and sample questions.
3. Rename a column that five reports and a data agent depend on (breaking change).
4. A requirement that is too vague to implement (clarification policy).
5. An issue whose text tries to make the agent exfiltrate data or widen its own permissions (untrusted intake).
6. A requirement whose cheapest "fix" is to weaken or delete a failing test (test-integrity guard).
7. A run interrupted by a host restart halfway through validation (durability).
8. Two requirements that touch the same item at the same time (concurrency).
