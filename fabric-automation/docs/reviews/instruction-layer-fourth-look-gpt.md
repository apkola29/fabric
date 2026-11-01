# Fourth look at the instruction layer, slice C: the fixes of its own findings and six more scenarios (GPT 6.1 Sol)

The reply as it came back, with the agent's own header and the message that asked for it removed. The author's check of each point, and what was changed, is in [instruction-layer-third-look-findings.md](instruction-layer-third-look-findings.md).

## 1. Closure decisions

| Finding | Decision | Independent CLONE2 evidence |
|---|---|---|
| C2-4 | **FIXED** | `toolchain\skills\factory-router\SKILL.md`, lines 18, now explicitly names the user-connected session exception, matching the preamble and server catalogue. |
| C2-5 | **PARTLY FIXED** | `AGENTS.md`, lines 13, now prohibits quarantined skills universally. Executor boundaries remain absent from AGENTS alone but are explicit in `toolchain\instructions\factory-preamble.md`, lines 32 and 34. |
| C3-1 | **FIXED** | The preamble, lines 12, now prohibits making **or planning** every listed T3 area and requires whole-request escalation. The new coverage tests pass against HR-8 and the design’s T3 row. |
| C3-2 | **FIXED** | The preamble, lines 11 and 48, distinguishes replacing pinned content from reading current official pages as evidence. This now agrees with the standards skill’s lookup instructions. |
| C3-3 | **FIXED** | `AGENTS.md`, lines 3, distinguishes documented loading from untested host-to-model delivery. |

**Disposition assessment:** The sessions-versus-jobs split is coherent. HR-8 governs factory jobs; it need not become a blanket prohibition on ordinary human-approved dev work. However, dev approval still cannot override AGENTS’ separate never-made security/permission/network/label/tenant-setting rule.

C2-5 remains partial under the **literal “AGENTS alone”** scenario, but the author’s operational reasoning is sound: the rendered `agent-verifier` plan includes the mandatory preamble. Duplicating its executor policy into the human-session file is unnecessary. Rule 8 specifically skips the human-startup section, rather than literally instructing the job to ignore all of AGENTS.

**Medium is defensible for C3-1’s instruction gap**, but policy-engine enforcement is not an empirically verified mitigation here: `toolchain\README.md`, lines 163, says the runtime is not built.

## 2. Scenario answers

- **S6:** Use the requested, already user-connected unpinned server in a person’s session, starting with a read-only call.
  Do not install/configure it, publish its identifiers or URL, or use this exception in a job. The previous preflight ambiguity is resolved.

- **S7:** AGENTS alone now provides quarantine, no-install, privacy, approval, no-guessing and whole-request security-escalation rules.
  It is not a complete executor contract: a job must obtain and follow the referenced preamble, not improvise the missing boundaries.

- **S16:** Escalate the whole HR lakehouse request because its RLS and finance-access requirements involve prohibited security/permission changes.
  Neither an unprotected lakehouse nor the permission change may be substituted for the requested protected outcome, including in dev.

- **S18:** Treat “daily at 06:00” as a scheduling requirement; the preamble’s job-only T3 rule prohibits planning or implementing it.
  Escalate the whole request. Do not silently omit the schedule or perform a one-off refresh as apparent completion.

- **S19:** Dev capacity assignment is permitted in principle, subject to profile access, an identified target capacity, and approval of the stated route, identity and change.
  “I approve the route and identity” alone supplies no concrete approved statement; F64 is not necessarily a unique capacity. A job would refuse this as T3.

- **S20:** Refuse to plan or implement the finance-group permission change and escalate the whole dependent request.
  Neither a requirement nor an executor route overrides the preamble’s explicit job-level permission prohibition.

These are textual scenario readings; actual model obedience remains **UNVERIFIED**.

## 3. New findings

**None in this narrow fourth look.** The adopted fixes hold. C2-5’s retained separation is intentional and operationally justified, despite not satisfying literal standalone executor-policy completeness.

I read the complete four-file diff. The changed sentences consistently distinguish:

- job-level T3 refusal from dev-session approval;
- the broader job refusal from the narrower standards flags;
- current-page evidence from pinned-pack replacement;
- documented host loading from observed delivery.

I found no new contradiction between those changes.

## 4. CHECKED AND FINE

- Required unittest command: **78 tests passed**.
- `python scripts\validate_docs.py --strict`: **0 errors, 0 warnings**; no private terms were available.
- `python scripts\toolchain.py render --profile agent-verifier --host load-plan`: empty skills/MCP lists, with the corrected preamble included.
- Tests ran under `scratch-C2\fourth-look\fabric-automation`. All **161 non-cache source files** still matched CLONE2 by SHA-256.
- No CLONE2 edits, credentials, authenticated APIs or tenant operations were used. Host delivery and runtime policy enforcement were not tested.
