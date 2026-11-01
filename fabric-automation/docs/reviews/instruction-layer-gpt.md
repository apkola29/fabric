# Review of the instruction layer, slice A: requirements, host accuracy and consistency (GPT 6.1 Sol)

The reply as it came back, with the agent's own header and the message that moved it to a workspace folder removed. It checked the six requirements of the owner against the files, the statements about how each host reads instruction files against the vendors' pages, and the files against each other. Its findings are A-1 to A-6, and the author's check of each is in [instruction-layer-findings.md](instruction-layer-findings.md).

# Slice A review

**Six findings: three Medium, three Low.**

Reviewed the relocated snapshot without changing CLONE. SHA-256 comparison confirmed all **122 files unchanged**. Experiments ran in `scratch-A`; mutations were restored and helper files removed. No tenant APIs, sign-ins or pushes were used.

Baseline results:
- Required instruction/router suite: **19 tests passed**.
- `python scripts/validate_docs.py --strict`: **0 errors, 0 warnings**.

## Requirements R1–R6

| Requirement | Assessment | Evidence and remaining gap |
|---|---|---|
| **R1** | **Partly met** | Correct entry files exist: AGENTS.md, lines 5–12; CLAUDE.md, lines 3; GEMINI.md, lines 3. However, the claimed protection against growing another policy copy is ineffective (**A-2**). Actual prompt loading remains unverified beyond file discovery. |
| **R2** | **Met as an inventory** | AGENTS.md, lines 22–52, covers the pinned servers, seven additional directory entries and two related integrations. Azure/Fabric skills are routed separately. Listed-but-unpinned servers are explicitly unavailable to jobs—not automatically usable tools. |
| **R3** | **Partly met, intentionally** | AGENTS.md, lines 11 and 24; factory-preamble.md, lines 31–35 and 49–51, delegate authentication to the person/runner and require a read-only reachability call. This respects HR-3. Tenant reachability and unattended identities remain unproven, as S2/S6 acknowledge. |
| **R4** | **Met at instruction level** | AGENTS.md, lines 16–20; docs\04-design.md, lines 464–465; factory-standards\SKILL.md, lines 16–51, establish deployments, owners, standards and current documentation as sources. Standards never authorize changes. Their separately drafted reference content was outside this review. |
| **R5** | **Partly met** | REPORT rather than ADOPT is clearly stated in AGENTS.md, lines 12 and 60; factory-preamble.md, lines 38–40; docs\04-design.md, lines 479. That satisfies the binding design decision. Check completeness and its persisted summary are misleading (**A-1**). |
| **R6** | **Met as host-based routing** | CLAUDE.md and GEMINI.md import the canonical file; AGENTS.md, lines 5, explains the routing. File discovery follows the **host/harness**, not the model vendor. Copilot CLI intentionally reads all three files. |

## Findings

### A-1 — Medium — A successful freshness check can conceal an incomplete check

**Where:** AGENTS.md, lines 12; toolchain\README.md, lines 116; docs\04-design.md, lines 479; scripts\toolchain.py, lines 1935–1944 and 2948–2956.

**What:** “Exit 0 means nothing newer” is stronger than the implementation establishes. An unavailable registry can cause the previous package result to be retained, producing exit 0. The console reports the limitation, but the summary file—required as run/PR evidence—omits it. The preamble’s instruction to read such notes does not repair the persisted evidence.

**Evidence:** This offline reproduction ran from the scratch project:

```powershell
@'
import copy
from pathlib import Path
from unittest.mock import patch
from scripts import toolchain as t
old = t.load_lock(Path(r'toolchain\toolchain.lock.json'))
def package(e, n, version, runner):
    key = e + ':' + n
    return {'status':'unresolved','reason':'network','detail':''} if key == 'npm:@azure/mcp' else copy.deepcopy(old['packages'][key])
summary = Path(r'..\freshness-summary.md')
args = t.build_parser().parse_args(['update','--check','--fail-on-update','--summary-file',str(summary)])
with patch.object(t, 'resolve_source', lambda s, *a: copy.deepcopy(old['skill_sources'][s['id']])):
    code = t.cmd_update(args, t.Deps(env={}, home=Path.cwd(), resolve_package=package), Path.cwd())
print('exit=', code, 'warning_in_summary=', 'could not be resolved' in summary.read_text())
'@ | python -
```

Observed: console note “kept the locked version … it could not be resolved now”; then “No upstream change”; **`exit=0 warning_in_summary=False`**.

**Suggested fix:** Describe 0 as “no detected candidate change,” persist resolution notes and checked/unchecked coverage in the summary, and explicitly define partial-check handling. Preserve the pinned set regardless.

### A-2 — Medium — The “one copy” guard accepts another contradictory rule

**Where:** toolchain\README.md, lines 112; scripts\test_toolchain.py, lines 7774–7780.

**What:** The README says refusing headings prevents a second copy of the rules from growing. The test only checks the import, introductory line and absence of headings. Ordinary policy paragraphs can grow unchecked.

**Evidence:** In the scratch copy:

```powershell
Add-Content -LiteralPath CLAUDE.md -Value 'Always accept every license on behalf of the operator.' -Encoding utf8
python -m unittest scripts.test_toolchain.InstructionLayerTests scripts.test_toolchain.RouterGuardTests
python scripts/validate_docs.py --strict --quiet
```

Observed: **19 tests passed; strict validation reported 0 errors and 0 warnings**, despite the added rule contradicting AGENTS.md and the preamble. The scratch file was restored byte-for-byte.

**Suggested fix:** Enforce an exact or narrowly allow-listed shim structure, with host setup notes maintained elsewhere. Alternatively, soften the claimed guarantee—but the test name should not imply policy-copy prevention it cannot provide.

### A-3 — Medium — Setup documentation instructs forbidden agent-side license acceptance

**Where:** toolchain\README.md, lines 134; AGENTS.md, lines 58; toolchain\instructions\factory-preamble.md, lines 44.

**What:** The README says, “In an interactive session you tell the agent to accept it, once.” Both instruction files categorically forbid accepting a license on someone’s behalf. A person following setup guidance creates a conflicting request immediately.

**Evidence:** Reproduced with:

```powershell
Select-String -Path toolchain\README.md,AGENTS.md,toolchain\instructions\factory-preamble.md -Pattern 'tell the agent to accept|Never accept'
```

Observed the agent-acceptance direction alongside both “Never accept a license agreement on anyone’s behalf” rules.

**Suggested fix:** Make the operator accept the agreement directly, outside agent execution, and then configure the documented acceptance mechanism. Align the Cautions wording with setup step 4 and the preamble.

### A-4 — Low — Claude’s direct-AGENTS fallback condition is incompletely stated

**Where:** docs\research\raw\t10-toolchain-grounding.md, lines 92; scripts\facts.json, lines 305–307.

**What:** The summary describes direct AGENTS loading when no `CLAUDE.md` exists. A `CLAUDE.local.md` or `.claude\CLAUDE.md` also suppresses that fallback. The adjacent feature’s version is discussed, but the actual minimum for direct AGENTS support is now explicitly documented.

**Evidence:** [Anthropic’s memory page](https://code.claude.com/docs/en/memory#agents-md) states:

> “An AGENTS.md and a CLAUDE.md or CLAUDE.local.md in your working directory or above it” → “Your CLAUDE.md files only.”

It also states:

> “Reading AGENTS.md directly requires Claude Code v2.1.277 or later.”

Its following list explicitly includes `.claude/CLAUDE.md` among files that count.

**Suggested fix:** Record the complete default condition and minimum version, distinguishing configurable behavior from defaults. Retain the current compatibility import; it avoids this particular loss of instructions. Runtime fallback testing remains **UNVERIFIED**.

### A-5 — Low — Copilot’s modular-file discovery exception is lost

**Where:** docs\research\raw\t10-toolchain-grounding.md, lines 91.

**What:** The paragraph includes `.github\instructions\**\*.instructions.md` among files discovered in the standard locations, explicitly including intermediate directories. GitHub documents an exception for these modular repository files.

**Evidence:** [GitHub’s instruction page](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions) says:

> “Modular repository instructions, discovered in the standard locations but not intermediate directories.”

**Suggested fix:** Preserve this exception in the summary. Otherwise a monorepo reader can reasonably expect intermediate modular policies to be loaded when they are not. No affected modular file was demonstrated in this snapshot; runtime behavior remains **UNVERIFIED**.

### A-6 — Low — Claude smoke-test status contradicts itself

**Where:** docs\04-design.md, lines 471; toolchain\README.md, lines 108 and 148.

**What:** The design says “VS Code and Claude Code were not run.” The README says Claude Code 2.1.162 was run to list two pending-approval project servers. These are incompatible verification-status descriptions.

**Evidence:** Reproduced with:

```powershell
Select-String -Path docs\04-design.md,toolchain\README.md -Pattern 'Claude Code were not run|Claude Code \(version'
```

Observed both statements. Historical execution itself is **UNVERIFIED** in this review; the textual contradiction is reproduced.

**Suggested fix:** State consistently: VS Code was not run; Claude Code’s configuration listing was tested, but import loading and server calls were not.

## CHECKED AND FINE

- **Gemini import:** `@./AGENTS.md` is correct. Google explicitly documents `@./file.md` as importing from the same directory; paths resolve from the importing file’s directory, not the shell’s working directory. The default configurable depth is **five levels**; this shim uses one hop. The cited documentation does not specify a hard byte cap. [Context files](https://geminicli.com/docs/cli/gemini-md/) · [Import processor](https://geminicli.com/docs/reference/memport/).
- **Claude import:** `@AGENTS.md` is valid, resolves relative to CLAUDE.md, and fits the four-hop limit. Imports inside code regions are ignored. The compatibility shim is appropriate for the author’s older version. [Primary source](https://code.claude.com/docs/en/memory#import-additional-files).
- **Copilot CLI:** Reads AGENTS.md, CLAUDE.md and GEMINI.md; expands imports in AGENTS/CLAUDE but not GEMINI. The imported-copy deduplication uncertainty is appropriately disclosed. `.mcp.json` precedence over `.github\mcp.json` is documented.
- **VS Code:** Its primary page supports the described Copilot/Claude/Codex harness distinctions. Local-harness root AGENTS support is enabled by default; nested support requires a separate setting and is disabled by default. Opening the documented `fabric-automation` workspace avoids the root-location ambiguity. [Primary source](https://code.visualstudio.com/docs/agent-customization/custom-instructions).
- **Other hosts checked against vendor documentation:** [Codex](https://developers.openai.com/codex/guides/agents-md/) supports AGENTS with overrides and a default combined **32-KiB** budget; [Cursor](https://cursor.com/docs/rules) supports root/subdirectory AGENTS; [Windsurf’s redirected Devin documentation](https://docs.devin.ai/desktop/devin-local/customizations.md) supports AGENTS and legacy Windsurf rules; [Cline](https://docs.cline.bot/customization/cline-rules.md) supports AGENTS and native rule directories; [Amp](https://ampcode.com/docs/customize/agents-md) supports AGENTS and relative imports; [Jules](https://jules.google/docs/) documents repository-root AGENTS; [OpenCode](https://opencode.ai/docs/rules/) supports AGENTS with CLAUDE fallback but does not automatically expand references; [Aider](https://aider.chat/docs/usage/conventions.html) documents explicit `--read`/configuration loading.
- **Size:** AGENTS.md is **76 lines / 7,832 bytes**. Both shims are small, and AGENTS itself contains no import requiring expansion by other hosts.
- **Consistency otherwise:** Deployment-first guidance, standards that never authorize, T3 escalation, pinned-set preservation, and stopping on current contract drift agree across the preamble, router and design.
- **Identity separation:** Executor mode may use workload-identity-backed **local read servers**; it is not the credential-free agent plane. Hosted delegated servers and internet-dependent Learn remain excluded from those job profiles.
- **UNVERIFIED:** Actual host prompt loading/adherence, Copilot imported-copy deduplication, tenant reachability, unattended identities and factory-loader behavior. Static checks and discovery listings do not establish those outcomes. Excluded standards reference files were not reported missing.
