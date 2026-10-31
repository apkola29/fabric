# Fabric Code Factory — Project brief

Version 0.1 · 2026-10-30 · Status: design phase (nothing is built yet)

## 1. The idea (from the requester)

- Fabric workspaces are backed up in Git.
- When a new requirement (a change or a feature) comes in, a **code factory** that holds all the necessary knowledge, skills and templates picks it up and implements it **silently**.
- It opens a **new branch**, does the work, and **waits for the changes to be approved/tested** by a human.
- It behaves like an **automation-led data engineer**: it does the work **plus** validation and quality tests, and delivers a final result automatically.
- It takes **intakes**, runs **behind the scenes**, and does so **securely**.
- It should use the **latest and greatest skills and top knowledge**.
- Scope is the **whole Fabric / Power BI estate**: reports, semantic models, data-agent creation, ontologies, notebooks, pipelines, lakehouses, warehouses, real-time items and more. Project Osmos (autonomous Lakehouse/OneLake engineering) is one workload pack among many, not the whole factory.

## 2. Way of working

1. Deep research on existing code factories and autonomous development systems (natural language in, iterative work with checks and balances out).
2. Work out what we need, plan, design, and **validate the design with multiple models**.
3. Solid design first, then implement slowly (phased, each phase gated by exit criteria).

## 3. Operating model

| Role | Model |
|---|---|
| Orchestrator, caretaker, default worker | Claude Sonnet 5.5, max reasoning |
| Cross-verification and extra parallel workers | GPT 6.1 Sol, Gemini 4 Argon, Grok 4.7 |

Independent work runs in parallel. Verification is risk-based. Disagreements are settled by evidence (running builds/tests, reading primary sources), not by vote.

## 4. Research ground rules (apply to every research thread)

1. Today is 2026-10-30. Establish the state of the art as of NOW using live web research. Do not rely on training-data memory: products are renamed, acquired or discontinued quickly. Verify that every system named in your thread exists and what it can do today. If something named does not exist, was renamed, merged or discontinued, or you cannot verify it, say so explicitly instead of guessing. Also add notable systems that were not listed.
2. Prefer primary sources: official docs and Microsoft Learn pages, vendor engineering blogs, GitHub repos (README, releases, changelogs, issues), papers, benchmark leaderboards. Record the publication or last-updated date of every source. Treat sources older than about 12 months as stale unless foundational, and flag them.
3. Separate facts (cite a URL) from your own inferences. Write UNVERIFIED next to any claim you could not confirm in a source. Flag vendor marketing claims as such. Never fabricate URLs, versions, metrics or quotes.
4. Read-only research. Do not modify any existing file or any external system.
5. Depth over breadth where it affects a design decision. Stop when the listed items are covered or after roughly 40 distinct sources, whichever comes first.
6. CHECKPOINT YOUR WORK. A host restart can cancel every running agent without warning (it happened on 2026-10-30 at 10:56 CDT and wiped out a full run). Within your first 5 tool calls, create your raw report file with the section skeleton and `STATUS: PARTIAL` as its first line. After roughly every 5 sources, or every 3 minutes, update that file in place (edit the existing file; do not recreate it) with the findings so far. When you finish, set the first line to `STATUS: COMPLETE`. If your file already exists with `STATUS: PARTIAL` when you start, you are a relaunch: read it and continue from it instead of starting over.
7. Flat topology. Do not spawn sub-agents; do the work yourself.
8. Do not use the orchestrator's SQL or todo tools. Your only write target is your own raw report file.

## 5. Research report format

Markdown, about 2,500 words excluding sources:

1. Executive findings: at most 10 bullets, most decision-relevant first.
2. Evidence tables as specified in the thread.
3. Transferable patterns for a Fabric code factory, plus anti-patterns and failure modes actually observed (with evidence).
4. Decision-driving claims: up to 10 claims the design would rest on, each with source URL, source date and confidence (H/M/L). Other models will cross-verify these.
5. Gaps and uncertainties.
6. Sources: URL | title | publication or updated date | primary or secondary.

## 6. Research threads

| Thread | Topic | Raw report |
|---|---|---|
| T1 | Commercial and hosted autonomous coding-agent platforms | research/raw/t1-platforms.md |
| T2 | OSS agents, frameworks, protocols, skills standards, reference architectures | research/raw/t2-oss-frameworks.md |
| T3a | Microsoft-native agentic analytics: Copilot in Fabric and Power BI, data agents, Fabric IQ, MCP servers, CLI, official skills, Project Osmos | research/raw/t3a-ms-native.md |
| T3b | Data-platform agents: Databricks, Snowflake, dbt, Google, AWS | research/raw/t3b-data-platforms.md |
| T3c | BI, semantic-layer, ELT and data-testing/observability vendors | research/raw/t3c-bi-elt-testing.md |
| T4 | Fabric and Power BI platform mechanics (Git, APIs, CI/CD, testing, limits) | research/raw/t4-fabric-mechanics.md |
| T5 | Security, safety and governance | research/raw/t5-security-governance.md |
| T6 | Runtime, hosting, orchestration and model gateway options | research/raw/t6-runtime-hosting.md |
| T7 | Intake, spec, iteration, verification, evaluation and metrics | research/raw/t7-patterns-evals.md |

## 7. Log

- 2026-10-30: brief created; threads T1–T7 launched.
- 2026-10-30 10:56 CDT: the host session shut down (routine) and resumed twice. All 9 running agents were cancelled before writing any file; about 7.6 minutes of research per agent was lost. Disk state was unaffected.
- 2026-10-30, after the restart: relaunched with the checkpoint rule (6), flat topology (7), and T3 split into T3a/T3b/T3c (the original T3 had started delegating to its own sub-agents because its scope was too wide).
- 2026-10-30 11:53–11:56 CDT: model route smoke test. Session log confirms gpt-6.1-sol, gemini-4-argon, grok-4.7 and claude-sonnet-5.5 each ran as requested with no fallback, and all four reached live web search. File writes: Sonnet 5.5 and Grok 4.7 can; GPT 6.1 Sol and Gemini 4 Argon research agents cannot, so their reviews come back inline and the orchestrator saves them.
- 2026-10-30 11:58 CDT: 9 research agents (T1, T2, T3a, T3b, T3c, T4, T5, T6, T7) and 2 local survey agents relaunched. All 9 skeleton checkpoints were on disk within about a minute.
- 2026-10-30 12:00 CDT: docs/01-requirements.md v0.1 written (28 functional and 14 non-functional requirements, 9 assumptions, proposed pilot success criteria).
- 2026-10-30 12:2x CDT: requester directive: use the official Fabric skills and, where needed, the Fabric Core and FabricIQ MCP servers. T3a and T4 were told to treat skills-for-fabric and the Fabric MCP docs tools as primary sources and to add an "MCP coverage" column.
- 2026-10-30 12:3x CDT: orchestrator grounding done with read-only calls only (Core command listing, docs item-type list, one capacity inventory). Written to research/raw/o1-fabric-surface-grounding.md. Two local surveys (L1 and L2) were kept out of this repository and never sent to external verifiers. Requirements bumped to v0.2: 34 functional and 17 non-functional requirements, 13 assumptions, 10 open questions.
- 2026-10-30 12:5x to 13:09 CDT: all 9 research threads complete. Decision register v0.1 (24 decisions) and landscape digest written.
- 2026-10-30 13:1x to 13:27 CDT: cross-verification by Gemini, GPT and Grok over 100 claims: 72 confirmed, 27 partly, 1 contradicted, 0 unverifiable. All corrections applied. Design v0.1 written (3 parts).
- 2026-10-30 13:3x to 13:51 CDT: design review by three model families (GPT 6.1 Sol: architecture, Gemini 4 Argon: completeness and Fabric fidelity, Grok 4.7: red team) plus the author's own review. 70 findings.
- 2026-10-30 13:53 to about 14:12 CDT: disposition log (44 accepted, 6 modified, 3 phased, 17 merged, 0 rejected), requirements v0.3, decision register v0.2 (32 decisions), design v0.2. Four groups of facts were re-checked directly against Microsoft Learn and the gh-aw documentation (see the log). v0.1 files archived in `archive/`.
- 2026-10-30 about 14:12 CDT: closure check sent to the three reviewers.
- 2026-10-30 14:12 to 14:37 CDT: closure replies in and applied. Gemini: 12 closed, 1 partly, 5 new problems. GPT: 16 closed, 2 partly, 3 new. Grok: 9 closed, 1 partly (phased on purpose), 3 new. All three said the design is good enough to start Phase 0. Two more facts re-fetched (the recoverable-item delete permission, and the gh-aw network and safe-output defaults). Design v0.2 now carries four rulesets, the I-8 capability pin, a stale-worker handover rule and a corrected ready-for-review condition. Nothing has been built or deployed. The only tenant calls this whole project were read-only.
- 2026-10-30 14:37 to 15:50 CDT: published to GitHub. The documents moved to a public folder (`fabric-automation` in the `fabric` repository), the raw reports were sanitized, and a validator, its mutation tests, a fact checker and two GitHub Actions were added. Every loop of checking and fixing is in `reviews/verification-log.md`.
- 2026-10-30 15:30 to 16:10 CDT: verification round 1 on the published design. Three reviewers from three model families raised 25 points. Each was checked against the document or the primary source, and all but one were acted on (the other was already gated by a spike). Some reviewer claims were wrong or overstated and were corrected by going back to the source. See `reviews/round-1-findings.md`.
- 2026-10-30 16:13 to about 16:45 CDT: verification round 2 on the corrected design, with the reviewers' lenses rotated. Three reviewers raised 25 more points. Every point was checked against the text, the code or the primary source, and all were acted on. One was a bug in the fact checker that round 1 had missed. See `reviews/round-2-findings.md`.
- 2026-10-30 16:44 to about 17:35 CDT: verification round 3 on the design and the tooling, with the lenses rotated a second time so that each family has now taken each lens once. Three reviewers raised 23 more points. Every point was checked against the text, the code or the primary source, and all were acted on, three of them in part. Two reviewer claims were right and mattered (the order in which the pinned check is set up, and a draft PR not being a durable halt), and reading a source to check a third showed that the budget text had joined two different caps. The publish script now proves, before it pushes, that the commit holds exactly the validated files. See `reviews/round-3-findings.md`.
- 2026-10-30 17:38 to about 18:40 CDT: verification round 4, a narrow closure check of the round-3 changes. The three families took slices instead of rotated lenses: the tooling code, the design text with its platform facts, and the records with the public exposure. Three reviewers raised 18 more points. Every point was checked against the text, the code or the primary source, and all were acted on, two of them in part. Gemini independently confirmed 12 platform claims and Grok recomputed every figure in the records. Most of the substance was in the publish script: it now checks every push address, scans the copy it will commit, compares Git entry modes so that a link or a submodule cannot pass for a file, and has 14 tests that run the real script with stand-in tools. Writing those tests exposed a hazard that no reviewer had raised: the mirror mode of robocopy deletes the files behind a junction in its destination even with the flag meant to skip junctions, so the script now refuses to mirror into a clone that holds a link. See `reviews/round-4-findings.md`.
- 2026-10-30 18:34 to about 20:55 CDT: verification round 5, a second closure check, this time of the round-4 changes, with the slices handed to different families (the publish script, the Python tooling, and the fact list with the records). Three reviewers raised 24 more points, and the two on code also mutated the safeguards. Every point was checked against the text, the code or the primary source, and all were acted on, two of them in part. The largest was a hole in the guard that round 4 had just added: a link at the mirror folder itself, rather than inside it, still let the script delete the files behind it and copy the project there, which was reproduced on the published script before it was fixed. Six safeguards of the publish script could be deleted without failing a test, so the behavioural tests grew from 14 to 35 and every safeguard was removed from a copy in turn (48 mutations of the script and the Python tools, all caught). A review of the fact list found that one record had called a repository's schemas generated from GitHub's payloads when its own README calls them hand-crafted and unmaintained, and that a claim about Entra wildcards matched the sentence that denies them; an audit of every page check then tied each pattern to its own sentence. See `reviews/round-5-findings.md`.
