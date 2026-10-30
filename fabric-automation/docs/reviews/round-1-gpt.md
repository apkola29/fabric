# Verification round 1: GPT 6.1 Sol

Lens: cross-document consistency and logical soundness. The reviewer read a frozen copy of the published commit `2ae0c95302` and replied inline. This is the reply with the links into the temporary copy removed. The disposition of each finding is in [round-1-findings.md](round-1-findings.md).

Semantic spot-check covered 15 requirements: FR-12, FR-15, FR-21, FR-24, FR-37 to FR-41, NFR-01 to NFR-03, NFR-07, NFR-09 and NFR-19.

## Findings

| ID | Severity | Where | Evidence (25 words or fewer) | Why it matters | Concrete fix |
|---|---|---|---|---|---|
| R1-A-1 | Critical | 04-design.md 3.6, RS-B and approval-policy | "At least one code-owner approval"; "recomputed on every review, push and dismissal" | T2 approval revocation has a race. After one of two eligible approvals is dismissed, the existing successful check remains until its webhook is processed. Native protection still requires only one approval, allowing a merge without the required quorum. | Enforce the eligible T2 quorum natively, with requester and approver roles separated, or keep T2 disabled. Add S11 tests that delay webhook processing and attempt merges after dismissal. |
| R1-A-2 | High | 04-design.md 3.3, diagram; 3.12 | "tier T2 or low-trust requester"; "tier T0 or T1" | A low-trust T0 or T1 requester satisfies both outgoing guards from PLANNED. The direct TEST_AUTHORING edge bypasses mandatory spec approval. | Make the direct guard "tier is T0 or T1 AND the requester is trusted". Test the complete tier and trust combination matrix. |
| R1-A-3 | High | 04-design.md 3.1 and 3.14, I-3; S9 | "code running in the container can still use it for inference"; "one response times the concurrency cap" | Run concurrency does not bound concurrent inference requests from an agent container. Dispatch-level reservations and a soft SDK cap therefore do not establish the claimed per-run overshoot bound. The organization budget only supplies a broader ceiling. | Put atomic request admission, in-flight limits and output-token limits in the proxy. S9 must adversarially test parallel direct-proxy requests, not merely record an overshoot figure. |
| R1-A-4 | Medium | 04-design.md 3.3 and 3.12 | "DONE (PR open), PARTIAL, BLOCKED and ABANDONED" | These end states are absent from the lifecycle diagram. The seven-day clarification timeout ends ABANDONED, but its persisted transition and finalization behavior are undefined. DONE also conflicts with the continuing AWAITING_HUMAN lifecycle unless it is a separate outcome. | Define one canonical state enumeration and a separate outcome enumeration where necessary. Specify timeout transitions, finalizers and reconciler treatment for every terminal outcome. |
| R1-A-5 | Medium | 04-design.md 3.15; research report T7, section 2.1, row 12 | "A task with 0% pass is treated as broken"; "0% pass@many usually = broken task" | The design converts a research heuristic into a categorical rule. Zero agent success does not establish a defective task. Reclassifying hard, valid tasks can inflate PS-1 and conceal capability gaps. | Trigger independent task and reference-solution audits instead. Require demonstrated benchmark defects before exclusion, and retain the original denominator and exclusion history. |
| R1-A-6 | Medium | 04-design.md 3.7, ordered build and reviewer preview | "B1 to B4, no agents"; "evaluation and the MCP endpoint need a published agent" | Stage-2 previews omit B5, the publishing step. A rebuilt data agent therefore cannot provide the usable published result promised to reviewers. | Make preview steps pack-dependent, including `env.publish` and publication read-back for data agents. Test preview after workspace expiry. |
| R1-A-7 | Medium | 04-design.md 5.1 and 6, S11 and D-27 | "N1 to N10 all behave as expected" | D-27 names S11 as its closure mechanism, but S11's criteria test repository controls, not evidence retention or immutability. Passing S11 cannot establish the storage guarantee of HR-10 and NFR-18. | Extend S11, owned by K11, with retention-policy read-back and overwrite and delete rejection tests under the publisher and state identities, or assign a separate mandatory readiness test. |

## Checked and sound

- Stage-1 and stage-2 workload and tier boundaries agree across requirements, decisions and design.
- Automated readiness correctly excludes the human approval-policy check, avoiding the earlier circular gate.
- Complete-manifest validation covers unchanged dependencies; sandbox transformations remain separate from source changes.
- Strict base freshness and base and candidate evidence binding address stale validation after `main` advances.
- Research supports the sizing rationale, escalation benefit, review-load concern and DAX benchmark limitations.
- The digest explicitly identifies its superseded controls and architecture statements.

## Could not verify

- Runtime enforcement: S1 to S11 remain unrun, so these findings assess the design, not observed implementation behavior.
- Every assertion across the complete raw research corpus. Research checks were targeted, principally against T6 and T7 and the digest.
- Whether the proposed GitHub protections can enforce the eligible quorum without the asynchronous-check race; S11 needs to establish that.

Verdict: ready after fixes - 1 critical, 2 high, 4 medium, 0 low
