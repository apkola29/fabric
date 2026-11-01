# Closure review of the instruction layer, slice A: requirements, host accuracy, consistency and the records (Grok 4.7)

The reply as it came back, with the agent's own header removed. It decided the six findings of the first review of this slice, re-checked the requirements, the host statements against the live pages and the consistency of the files, and read the records of the first review for statements that are not true. The author's check of each finding is in [instruction-layer-closure-findings.md](instruction-layer-closure-findings.md).

# Slice A closure check (Grok 4.7)

Read-only on the clone. Experiments only in `scratch-A`. No credentials, no push. Host claims were re-checked against the live pages on 2026-11-01 (`python scripts/verify_facts.py --only` the four instruction-file claims: 4 PASS).

## 1. Earlier findings

| ID | Decision | Evidence |
|---|---|---|
| A-1 | CLOSED | Scratch reproduction (unresolved `npm:@azure/mcp`, sources patched to the lock): console printed `note: kept the locked version of npm:@azure/mcp: it could not be resolved now` and `No upstream change was found, but part of the check did not run (see the notes).` Summary file held the same sentence and a Notes section. `exit=0`. |
| A-2 | CLOSED | The original extra paragraph on `CLAUDE.md` now fails `test_claude_and_gemini_are_exactly_the_three_lines_that_import_the_one_copy` (`AssertionError`, the added license sentence). Both shims are exactly the three-line text the test holds. |
| A-3 | CLOSED | `toolchain/README.md`, line 10, says the operator accepts the license "yourself, and never through the agent". Cautions forbid the `accept_eula` tool. `AGENTS.md`, line 9, and the preamble, line 7, still forbid accepting on anyone's behalf. The "tell the agent to accept" sentence is gone. |
| A-4 | PARTLY CLOSED | Grounding note, line 92, and claim `page-claude-code-agents-md-and-claude-md` match the live memory page (v2.1.277, and `CLAUDE.md`, `.claude/CLAUDE.md`, and `CLAUDE.local.md` all count). `toolchain/README.md`, line 108, still says "only when no `CLAUDE.md` is there". Limits, line 159, names only the version. |
| A-5 | CLOSED | Grounding note, line 91, and claim `page-copilot-cli-instruction-files` match the live sentence: "Modular repository instructions, discovered in the standard locations but not intermediate directories." |
| A-6 | CLOSED | `docs/04-design.md`, line 471, and `toolchain/README.md`, line 148, agree: VS Code was not run; Claude Code only as far as listing a generated `.mcp.json` as pending approval. The old "were not run" sentence is gone. |

The author's "not done" on A-4 ("Not run against a model") is fair. The same row's "the README now state the version and the three files" is not. No other A-1 to A-6 row has a "not done" that this check contradicts.

### R1–R6

| Req | Verdict | Lines | What the owner would still find missing |
|---|---|---|---|
| R1 | Met | `AGENTS.md`, line 5; `CLAUDE.md` and `GEMINI.md`, lines 1–3; design, line 466 | No proof a host puts this text in a model. Disclosed. |
| R2 | Met as an inventory | `AGENTS.md`, lines 32–62 (pinned table, unpinned table, four other Microsoft servers) | Unpinned servers are named and refused to jobs, not loaded. Catalogue was not re-audited here. |
| R3 | Partly met, by design | `AGENTS.md`, lines 8 and 19–21; preamble, lines 39–45 | A person signs in. An unattended identity is still S2/S6. |
| R4 | Met at instruction level | `AGENTS.md`, lines 25–30; preamble, lines 21–26; `factory-standards/SKILL.md` | The second standards check is cited and not in the record (A2-1). |
| R5 | Partly met | `AGENTS.md`, line 22; preamble Freshness; design, line 479 | Report-not-adopt holds, and A-1's hole is closed. A job does not run the check. The runner that should is not built (`toolchain/README.md`, Limits). |
| R6 | Met as routing | Shims plus `AGENTS.md`, line 5; host table, lines 104–108 | Claude's direct-read condition is still wrong in that table (A-4). Copilot CLI reading all three files is disclosed. |

## 2. New findings

### A2-1 — Medium — The review record states numbers and a verification that are not in the files

**Where:** `docs/reviews/instruction-layer-findings.md`, lines 13, 22, 65, 66, and 68–72. `docs/04-design.md`, line 465.

**What is wrong:** Several sentences a later reader would trust are false or overstated.

**Evidence:**
- Line 13 says the author's ratings are 1 High, 11 Medium and 13 Low, and that the reviewers rated 4 High, 14 Medium and 7 Low. The "After the check" column is 1 High, 17 Medium and 7 Low (A: 3 Medium, 3 Low; B: 9 Medium, 3 Low; C: 1 High, 5 Medium, 1 Low). The review files' own headings are 4 High, 15 Medium and 6 Low (C-1 and C-2 High; C-3 through C-7 Medium; B-1 and B-2 High; B-3 through B-9 Medium; B-10 through B-12 Low; A: 3 Medium, 3 Low).
- Line 22 says the README states the version and the three Claude files. It does not (`toolchain/README.md`, lines 108 and 159).
- Line 65 says the standards pack was verified separately and points at `standards-pack-findings.md`. That file is not in the snapshot. Only `standards-pack-round-1-gemini.md`, `standards-pack-round-1-gpt.md` and `standards-pack-round-1-grok.md` exist. The GPT reply's heading is "CORRECTIONS REQUIRED". There is no second-round file.
- Design, line 465, says the corrected pack was checked again by three families "with the files rotated (verification log, loop 13)". `docs/reviews/verification-log.md` ends at Loop 12 (243 lines). A search of `docs` finds no "loop 13" heading.
- Line 66 says the router is 70 lines. `len(splitlines())` is 69. The preamble (54) and `AGENTS.md` (76) match.
- "What was not proved" does not mention the unbuilt job runner, or that the standards disposition it cites is absent. The host-loading bullets themselves match the files.

**Suggested fix:** Correct the two totals. Delete or rewrite the README sentence in the A-4 row. Do not cite `standards-pack-findings.md` or loop 13 until those records exist. Say in "What was not proved" that the per-job look has no runner yet.

### A2-2 — Medium — The first sign-in rule a job sees names the wrong actor

**Where:** `toolchain/instructions/factory-preamble.md`, lines 8 and 39. `AGENTS.md`, line 8. `toolchain/skills/factory-router/SKILL.md`, line 19.

**What is wrong:** The never-bend rule says "Sign-in belongs to the host, not to you." The same preamble, `AGENTS.md`, and the router say it belongs to the person or the runner. A job reads the preamble, not `AGENTS.md`. "Host" is not the person and not the runner. A weak model can treat a host login command as in scope.

**Evidence:** The three sentences, read as written. HR-3 allows a credentialed server only for a person in `dev` or the trusted executor.

**Suggested fix:** In preamble line 8, say "the person or the runner", the same words as line 39.

### A2-3 — Medium — A job is not told to keep identifiers out of pull request text

**Where:** `toolchain/instructions/factory-preamble.md`, line 9. `AGENTS.md`, line 10.

**What is wrong:** `AGENTS.md` forbids a tenant, workspace, item or capacity identifier, a person's name, a token, a local path, or an MCP server URL in a file or in pull request text. The preamble, which is what a job reads, forbids those identifiers (and not a token, and not an MCP URL in the same clause) only in "a file that this repository publishes." Pull request text is not that file. The preamble also tells the job to put a freshness line in the pull request.

**Evidence:** The two rules, side by side. The C-2 fix added pull request text to `AGENTS.md` rule 4 and did not add it to the job's rule.

**Suggested fix:** Give the preamble the same list and the same "file or pull request text" scope as `AGENTS.md` rule 4.

### A2-4 — Low — The router still shows a job two toolchain commands the preamble forbids

**Where:** `toolchain/skills/factory-router/SKILL.md`, lines 17 and 48. Preamble, line 45.

**What is wrong:** The preamble says a job runs none of `verify`, `list`, `doctor`, `install`, or `update`. The router exempts a job from `verify` and from the freshness command, then still places `python scripts/toolchain.py list` and `python scripts/toolchain.py doctor` in the numbered procedure with no such exemption. A job has no copy of the script.

**Evidence:** Those three sentences. Steps 1 and 5 show the author knew to exempt jobs; steps 2 and the doctor sentence do not.

**Suggested fix:** Say a job does not run `list` or `doctor`, as steps 1 and 5 already say for the other commands.

### A2-5 — Low — The design row for existing deployments is weaker than the rules a job is given

**Where:** `docs/04-design.md`, line 464. Preamble, line 23. `toolchain/README.md`, line 114.

**What is wrong:** The design row says a conflicting requirement is raised and never resolved silently. It does not say what to do when two patterns in the deployment disagree, and it does not forbid copying or quoting a secret already in Git. The preamble and the README do both.

**Evidence:** The three sentences. An agent that is given the preamble is still bound. The binding design row is not.

**Suggested fix:** Add those two sentences to the design row.

## 3. CHECKED AND FINE

- A-1's summary path matches the instructions: exit 0 still means nothing newer was detected, the note is quoted as the command prints it, and a dropped-contract note does not use the partial sentence (`scripts/test_toolchain.py`, lines 7589 and 7608).
- Shim syntax still matches the vendors. Claude: `@AGENTS.md`, relative to the importing file, maximum four hops, not parsed in code spans (https://code.claude.com/docs/en/memory). Gemini: `@./AGENTS.md` is the documented same-directory form; default import depth is 5 (https://geminicli.com/docs/reference/memport/).
- Copilot CLI still reads `AGENTS.md`, `CLAUDE.md` (and `.claude/CLAUDE.md`) and `GEMINI.md`, expands `@` in `AGENTS.md` and `CLAUDE.md` but not in `GEMINI.md`, and does not define precedence. The imported-copy uncertainty on README line 159 is still an accurate limit, not a false claim.
- VS Code: the facts URL redirects to https://code.visualstudio.com/docs/agent-customization/custom-instructions. The claim strings are on that page. Copilot harness uses `AGENTS.md` or `.github/copilot-instructions.md`; Claude harness uses `CLAUDE.md`; Codex uses `AGENTS.md`. Local-harness root `AGENTS.md` is on by default; nested files are off by default. The grounding note does not mention those two settings; it does not contradict them.
- The live Claude page adds cases the grounding note does not list (plugin disabled, first session after an upgrade, and before v2.1.281 some Bedrock or telemetry-disabled sessions). Direct `AGENTS.md` reading fails there. The import shim is what the page itself recommends, and the kit has it. Not raised.
- The nine never-bend rules and the preamble's five agree on license refusal, tokens found in text, data-not-instructions, no `update --write`, and contract drift as a stop. Design line 479 matches the reproduced exit-0 wording. Instruction-files row (design, line 466) matches the shims.
- `factory-standards/SKILL.md` says the checks guide and never authorize, are not a compliance statement, and a `[flag]` is not turned into a change. No misuse instruction beyond the tag ambiguity already left to the separate pack review.
- Mutation spec counts in the findings file match the file: 58 mutations (42 layer, 11 pack, 5 update). Test counts match: 26 layer tests, 9 pack tests, 22 `UpdateTests`.
- "What was not proved" is right that no host was run against a model, and that Copilot CLI 1.0.102 listing the three files is the one instruction-file experiment on record.
