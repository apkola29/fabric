# Reviews

The trail from the first research to the current design, in reading order.

| Step | Files | What they are |
|---|---|---|
| 1 | [xv-results.md](xv-results.md), [xv-grok-claims.md](xv-grok-claims.md) | Cross-verification of the decision-driving claims by three model families |
| 2 | [review-gpt.md](review-gpt.md), [review-gemini.md](review-gemini.md), [review-grok.md](review-grok.md), [review-orchestrator.md](review-orchestrator.md) | The design review of v0.1: 70 findings from three reviewers and the author's own pass |
| 3 | [disposition-log.md](disposition-log.md) | What was done with every one of those findings |
| 4 | [closure-gpt.md](closure-gpt.md), [closure-gemini.md](closure-gemini.md), [closure-grok.md](closure-grok.md) | The closure check of design v0.2 by the same three reviewers |
| 5 | [verification-log.md](verification-log.md) | Every verification loop: what was checked, what failed, what changed, and the proof that GitHub holds what is on disk |
| 6 | [round-1-findings.md](round-1-findings.md), with the three replies [round-1-gpt.md](round-1-gpt.md), [round-1-gemini.md](round-1-gemini.md) and [round-1-grok.md](round-1-grok.md) | Verification round 1 on the published design: the findings, how each was checked, and what was done |
| 7 | [round-2-findings.md](round-2-findings.md), with the three replies [round-2-grok.md](round-2-grok.md), [round-2-gpt.md](round-2-gpt.md) and [round-2-gemini.md](round-2-gemini.md) | Verification round 2 on the corrected design, with the reviewers' lenses rotated so that no family reviewed the same angle twice |
| 8 | [round-3-findings.md](round-3-findings.md), with the three replies [round-3-gemini.md](round-3-gemini.md), [round-3-grok.md](round-3-grok.md) and [round-3-gpt.md](round-3-gpt.md) | Verification round 3 on the design and the tooling as corrected after round 2. The lenses rotated a second time, so each family has now taken each lens once. What stays open is the list of spike outputs at the end of the findings file, not unfinished fixes to the text |
| 9 | [round-4-findings.md](round-4-findings.md), with the three replies [round-4-gpt.md](round-4-gpt.md), [round-4-gemini.md](round-4-gemini.md) and [round-4-grok.md](round-4-grok.md) | Verification round 4: a narrow closure check of what round 3 changed. The families took slices instead of rotated lenses: GPT the tooling code, Gemini the design text and the platform facts, Grok the records, the public exposure and a cold read. The open items are again the spike outputs at the end of the findings file |

A reviewer is a model from a different vendor family than the one that wrote the text under review, so that one family's blind spots are not shared. Reviewers were told to read only the published files.
