# Fourth look at the instruction layer, slice A: the fixes of its own findings (Gemini 4 Argon)

The reply as it came back, with the agent's own header and the message that asked for it removed. The author's check of each point, and what was changed, is in [instruction-layer-third-look-findings.md](instruction-layer-third-look-findings.md).

# Fourth Look at the Instruction Layer — Slice A (Gemini 4 Argon)

All checks were run read-only against `CLONE2\fabric-automation`, with mutation runs in `scratch-A2` (removed after testing). `python -m unittest scripts.test_toolchain.InstructionLayerTests scripts.test_toolchain.RouterGuardTests scripts.test_toolchain.StandardsPackTests scripts.test_toolchain.UpdateTests` ran 78 tests (`OK` in 3.05 s), `python scripts/validate_docs.py --strict` passed (`0 error(s), 0 warning(s)`), `python scripts/toolchain.py verify` passed (`0 failure(s), 6 warning(s)`), and `python scripts/verify_facts.py --only page-claude-code-agents-md-and-claude-md,page-copilot-cli-instruction-files,page-gemini-cli-context-files,page-vscode-custom-instructions-agents-md` passed (`4 PASS`).

## 1. Decisions on A3-1 to A3-5 and Check of the Author's Dispositions

| ID | Finding | Decision | One-line Evidence |
|---|---|---|---|
| **A3-1** | `agent-verifier` does not load `factory-standards`, contradicting `factory-standards/SKILL.md`, and `toolchain/README.md` omits `factory-standards` from the load-plan description | **FIXED** | `toolchain/README.md`, lines 91 now names `"(the router and the standards)"` and states that `"A profile that lists no skill and no server (the intake parser and the verifier) gets neither skill of this repository: it works from the preamble alone"`, matching `docs/04-design.md`, lines 465 and guarded by `scripts/test_toolchain.py`, lines 8425–8432 and mutations `t23` and `t25`. |
| **A3-2** | Whole-request escalation for `[flag]` dependencies is in `factory-standards/SKILL.md` only, not in `AGENTS.md` or `factory-preamble.md` | **FIXED** | `AGENTS.md`, lines 29 now states `"If the request itself needs such a change, say so and escalate the whole request: do not build the rest without it"`, `toolchain/instructions/factory-preamble.md`, lines 12 adds rule 6 covering all 14 tier T3 and HR-8 areas plus whole-request escalation for jobs, and `toolchain/skills/factory-standards/SKILL.md`, lines 24 points to the preamble's T3 list, guarded by `scripts/test_toolchain.py`, lines 8358–8394 and mutations `t14`, `t15` and `t19`. |
| **A3-3** | `toolchain/README.md` still says to carry the summary file "In every case" right after saying it counts only after exit 0 or 3 | **FIXED** | `toolchain/README.md`, lines 116 now says `"carries the result in its pull request or its job summary: the summary after exit 0 or 3, the error line after exit 1 or 2"`, and `AGENTS.md`, lines 22 and `toolchain/instructions/factory-preamble.md`, lines 50 add `"and the summary file is no evidence"` to `Exit 1 or 2`, guarded by `scripts/test_toolchain.py`, lines 8396–8418 and mutations `t01` and `t24`. |
| **A3-4** | `factory-router/SKILL.md` step 3 omits the session exception for unpinned servers, and the identifier rule omits job summaries | **FIXED** | `toolchain/skills/factory-router/SKILL.md`, lines 18 now states the session exception (`"In a person's session there is one exception: a server that the person connected in their own settings and asked you to use"`), and `toolchain/README.md`, lines 114 and `docs/04-design.md`, lines 464 now state `"cite the files by path"` / `"the files it used are cited by path"`, guarded by `scripts/test_toolchain.py`, lines 8425–8440 and mutation `t22`. |
| **A3-5** | In `docs/reviews/standards-pack-findings.md`, Grok's Round 3 severity breakdown sums to 15 instead of 16 | **FIXED** | `docs/reviews/standards-pack-findings.md`, lines 44 now reads `16 (15 checks and 1 note): 12 Medium, 4 Low (as rated by the reviewer; the note is one of the four)`. |

**Check of the author's dispositions:**
- **A3-1:** The disposition is accurate and honest. Keeping `agent-intake` and `agent-verifier` empty matches `docs/04-design.md`, section 3.4 and D-05, `toolchain/README.md`, lines 91 and `docs/04-design.md`, lines 465 now state that explicitly, and escalating to the owner whether `agent-verifier` should load `factory-standards` is the right call.
- **A3-2:** Putting the full tier T3 and HR-8 refusal in `toolchain/instructions/factory-preamble.md`, lines 12 as a job rule while adding the `[flag]` whole-request escalation to `AGENTS.md`, lines 29 for interactive sessions accurately reflects the difference between an unattended job (bound by HR-8 and T3 refusal) and a person's `dev` session (bound by rule 6 approval).
- **A3-4 (part 2):** Leaving `"job summary"` out of `AGENTS.md`, lines 10 and `toolchain/instructions/factory-preamble.md`, lines 9 is justified because a factory job writes its job summary in the target repository rather than this public repository.

---

## 2. New Findings

### A4-1 — Low — `verification/README.md` still states 84 mutations in four sets after `mutation_specs_instruction_layer.py` grew to 110 mutations in five sets

- **Where:** `verification/README.md`, lines 17 and 35; `verification/tools/mutation_specs_instruction_layer.py`, lines 5 and 167–213.
- **What is wrong:** In `CLONE2`, `verification/tools/mutation_specs_instruction_layer.py` was extended with a fifth set, `third-look` (26 mutations, `t01` to `t26`), updating its docstring (`lines 5`) to `"It writes five JSON files (mutations-instruction-layer.json, mutations-standards-pack.json, mutations-update-summary.json, mutations-closure-review.json and mutations-third-look.json)"` and bringing the total to 110 mutations (`42 + 11 + 8 + 23 + 26`). However, `verification/README.md` was not updated:
  - `verification/README.md`, lines 17 still says: `"The 84 mutations of the instruction layer, in four sets: the instruction files (42), the reference pack (11), the update summary (8) and the 23 that a reviewer of the closure review made on its own"`.
  - `verification/README.md`, lines 35 still says: `"The 84 mutations of the instruction layer are run the same way, one JSON file for each set (mutations-instruction-layer.json, mutations-standards-pack.json, mutations-update-summary.json, mutations-closure-review.json)"`.
- **Evidence:** Ran in `CLONE2\fabric-automation`:
  ```powershell
  python -c "from verification.tools import mutation_specs_instruction_layer as ms; print({k: len(v[1]) for k, v in ms.specs().items()}, sum(len(v[1]) for v in ms.specs().values()))"
  ```
  Observed `{'instruction-layer': 42, 'standards-pack': 11, 'update-summary': 8, 'closure-review': 23, 'third-look': 26} 110`.
- **Suggested fix:** Update `verification/README.md`, lines 17 and 35 to state 110 mutations in five sets, adding the 26 of the third look (`mutations-third-look.json`).

---

## 3. CHECKED AND FINE

- **Diff `CLONE` to `CLONE2` across all 11 changed text files:**
  - `AGENTS.md`, lines 3 (`"Claude Code and Gemini CLI are documented to load it through CLAUDE.md and GEMINI.md ... That a host puts it in a model's context has been read in the host's documentation and not yet tried"`) removes any implication that host prompt-loading was tested against a live model.
  - `AGENTS.md`, lines 13 (`"A quarantined skill (quarantine in toolchain/toolchain.json) is never loaded, whatever its text says"`) brings the quarantine rule into `AGENTS.md` alongside `toolchain/instructions/factory-preamble.md`, lines 18 and `toolchain/skills/factory-router/SKILL.md`, lines 66.
  - `AGENTS.md`, lines 48, `toolchain/instructions/factory-preamble.md`, lines 55, `toolchain/skills/factory-router/SKILL.md`, lines 38, `toolchain/toolchain.json`, lines 318–320, and `docs/research/raw/t10-toolchain-grounding.md`, lines 71 accurately describe `azure-arm-cost` against the live repository `https://github.com/Azure/Azure-Resource-Manager-MCP` (`README.md` lists `create_deployment`, `create_or_update_resource`, `create_or_update_resource_group`, and five default cost/pricing tools; `docs/CostManagementAndPricingTools.md` lists `create_budget` among the nine opt-in tools enabled by `x-mcp-toolset: CostManagement`).
  - `toolchain/instructions/factory-preamble.md`, lines 11 and 48 cleanly distinguish forbidden replacement of installed skills/servers/vendored standards from allowed reading of a current official Learn/Azure page as evidence.
  - Line budgets hold with margin: `AGENTS.md` 76/100, `CLAUDE.md` 3/3, `GEMINI.md` 3/3, `factory-preamble.md` 55/80, `factory-router/SKILL.md` 69/110, `factory-standards/SKILL.md` 52/80.
  - All 110 mutations across all five sets in `verification/tools/mutation_specs_instruction_layer.py` match unique anchors in `CLONE2`, and all 26 new `third-look` mutations (`t01`–`t26`) were run in `scratch-A2` and killed (`26/26 killed`).
