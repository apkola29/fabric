# Verification of the reference pack, round 4: briefs for three families

Round 4 is a closure check. Round 3 (every line read cold by all three families, with a verbatim evidence quote per line that a program then checked against the cited section: 291 of 291 quotes were found) raised 22 corrections to checks, one new check, and one correction to a note, and the tag explanation in two file headers was clarified. This round checks exactly those lines, each by all three families, with the lenses rotated again.

## Shared preamble (read first, then your lens)

You are verifying part of a drafted REFERENCE PACK for an open-source project: a "Fabric Code Factory" whose agents plan, test, implement and verify changes to Microsoft Fabric and Power BI items in a sandbox WITH NO NETWORK. The agents cannot read Microsoft Learn while they work, so the guidance they should apply is vendored in the repository as short checks: one line each, with an id, one sentence, where it applies, and the page and section that state it. The pack was drafted by one model (a Claude-family model) from 16 pages of learn.microsoft.com and verified three times by three other families (GPT, Gemini, Grok), with corrections after each round: round 1 found a defect in about two lines of five, round 2 in about one in four, round 3 in about one in five (and mostly Medium or Low: a lost "can", "may" or "such as", a scope wider than the page, a closed list that the page gives as examples). Treat the corrected lines as unverified: a fix can introduce a new defect, and the reviewers of earlier rounds disagreed about several lines.

The factory does NOT implement security, permission, network, sensitivity-label or tenant-setting changes in this version: it refuses and escalates them. So checks on those topics say to flag a change to a person and name the guidance (tag `[flag]`). The pack guides and never authorizes.

WHERE (everything is under <review folder>\pack4, treat it as READ-ONLY; make scratch copies under <review folder>\scratch-<your family name> if you need to):

- The four pack files: `well-architected.md`, `security-and-governance.md`, `delivery-and-lifecycle.md`, `architecture-patterns.md`.
- `sources\`: the 16 pages, reduced to text, one file per page. Each starts with `SOURCE:` (the URL) and a date line. Headings are lines that start with `#`. The reduction can lose formatting (tables become `|` lines, code becomes indented lines). If a point looks missing or garbled, read the live page at its URL (public, read only) before you decide.
- `DRAFTING-BRIEF.md`: the rules that the drafter was given (format, tags, truthfulness, exposure). Your yardstick. Additions: (a) a sentence may not copy more than 12 consecutive words of a page (a program checks this; judge meaning, not copying); (b) a check may name "Amazon S3" only as "the Amazon store that the page names" (intended, not a defect); (c) a tag clarification that was added after round 3: `[flag]` is for a CHANGE to security, permissions, a network setting, a sensitivity label or a tenant setting, which the factory only flags; what a change itself contains, such as a secret in a file, is not a change to a setting, and is a `[gate]` when a program can decide it. One round-3 reviewer had read the brief's wording as "every security topic is `[flag]`", the other two had not: say whether the clarified wording in the file headers and the line tags now agree.

THE FORMAT. A line is: `- \`std-AREA-NN\` <one sentence, at most 35 words, ends with one tag [gate], [review] or [flag] where it helps> Applies to: <what a change touches>. Source: <label>, "<section heading of the page>"[; <label>, "<heading>"] [(control "<name>")].` The label is in the file's Sources table. `Note:` lines record a tension between two places. Tags: `[gate]` a deterministic check could decide it from item definitions or the pull request; `[review]` a reviewer's judgement; `[flag]` as above; a sentence that starts `Ask:` needs knowledge that only the tenant has.

TRUTHFULNESS RULES the drafter had to follow: (1) paraphrase, never more than 12 consecutive words from a page; (2) never add a number, name, limit, feature, setting or recommendation that is not in the source text; (3) never generalize beyond the text; (4) never merge two pages into one claim unless each supports its part and both are cited; (5) keep conditions, tradeoffs and states such as preview; a permissive statement ("can", "may", "such as", "for example", "might", "typically") must not become a requirement, an example must not become a closed list, and a disjunction must not become a conjunction.

THE ROWS YOU CHECK. Exactly these 24 rows (the first 23 are checks, the last one is the fourth `Note:` of `delivery-and-lifecycle.md`, called `note-del-4`):

`std-arc-02`, `std-arc-04`, `std-arc-15`, `std-del-01`, `std-del-02`, `std-del-03`, `std-del-06`, `std-del-09`, `std-del-10`, `std-del-12`, `std-del-14`, `std-del-17`, `std-del-18`, `std-gov-01`, `std-gov-04`, `std-gov-10` (new), `std-ops-03`, `std-ops-06`, `std-rel-04`, `std-sec-10`, `std-sec-14`, `std-sec-15`, `std-sec-16`, `note-del-4`.

Read each of them cold against the cited section, then read the checks next to them in the same file, because a correction can collide with its neighbours (a `Note:` and the checks it explains; `std-del-01` to `std-del-03` and `note-del-1`; `std-del-12` and `std-del-14` and `note-del-4`; `std-gov-05` to `std-gov-07` and the new `std-gov-10`; `std-arc-02` and `std-arc-04` and `note-arc-1`).

HOW TO JUDGE A ROW. Open the cited section (the heading must be a real heading of that page, and the point must be in that section or below it) and decide one verdict:

- S = SUPPORTED: every part of the sentence (numbers, names, conditions, tradeoffs, preview states, file and setting names with their exact spelling) is in the cited section, and the "Applies to" scope does not claim more than the page does.
- P = PARTLY: some part is not in the cited section or is stronger than the page. Say which part.
- U = UNSUPPORTED: the page does not say it.
- M = MISLEADING: each word can be found, but the meaning changes in context (a condition dropped, a "may" turned into "must", an example turned into a closed list, a recommendation turned into a restriction, a scope wider than the page's).
- T = WRONG TAG: a `[gate]` that no program could decide from item definitions and the pull request; a change to security, permissions, network, labels or tenant settings that is not `[flag]`; a `[flag]` on something that is not such a change; an `Ask:` that does not need the tenant, or a tenant question without `Ask:`.
- C = WRONG CITATION: a heading that is not on the page, or that does not hold the point.
- X = CONFLICT: two checks, or a check and a `Note:`, that an agent cannot follow together without a rule that the pack does not give.

THE OUTPUT PROTOCOL. Your report starts with ONE TABLE with one row for each of the 24 rows above, in this exact row format, one row per line:

`std-arc-02 | S | quote`

where the third column is a quote of AT MOST 12 consecutive words, copied EXACTLY from the cited section in `sources\`, of the part of the source that carries the line's most conditional element (a modal verb such as "can" or "may", an "if" or "when", "such as", "for example", "whenever possible", a number, a preview state, an exception). A program will search each quote in the cited section of the cited page. For a verdict other than S add the verdict letter, the quote that shows the difference, and a short reason (at most 25 words) in the same row. For `note-del-4` the verdict is S if the tension is real and both sides are stated correctly, and otherwise M with the reason; quote one side.

After the table: (a) FINDINGS, one per row that is not S, ranked by real impact (High: a false or reversed statement, or an agent would do something forbidden; Medium: a lost condition or a wrong scope; Low: wording, tag, or citation precision), each with the evidence and a suggested replacement line in the pack's format (at most 35 words in the sentence); (b) the two file headers whose `Tags:` paragraph changed (`well-architected.md` and `delivery-and-lifecycle.md`), and the new tag explanation in `toolchain\skills\factory-standards\SKILL.md` is NOT in your folder, so do not look for it; say whether the two header paragraphs are accurate and agree with the tags of the lines of their file; (c) CONFLICTS between a changed row and any other line or note; (d) DANGER: any row that, followed literally, makes an agent do something the factory must not do (change a permission, a network setting, a label, a tenant or capacity setting, or delete, purge, pause or recreate something). No style nits. A finding you could not confirm says UNVERIFIED. If all 24 rows are S and you find nothing else, say so: do not invent findings. Return the whole report inline in your final message, at most 4000 words. Do not rely on writing files.

## The lenses

### Lens A, Gemini 4 Argon: the literal-minded agent

Be hardest on the question: would an agent that follows this line literally block a good change or pass a bad one? Look at every "Applies to", at every closed list, and at every place where a question turns a recommendation into a requirement. Read in this order: `delivery-and-lifecycle.md`, `architecture-patterns.md`, `security-and-governance.md`, `well-architected.md`.

### Lens B, Grok 4.7: tags, citations and the cited section as a whole

Be hardest on the tags (see the clarification above), on the citations (does the heading exist, does the point sit in that section; for the Azure security baseline citation check the section heading AND the control title in parentheses), and on whether another sentence of the SAME cited section adds an exception, a tradeoff or a preview state that the line leaves out. Read in this order: `well-architected.md`, `security-and-governance.md`, `architecture-patterns.md`, `delivery-and-lifecycle.md`.

### Lens C, GPT 6.1 Sol: from the page to the line

Work from the page side: for each row find in the cited section the sentence or sentences that carry it, and ask whether the line says MORE (a stronger verb, a wider scope, an invented name or number), LESS (a dropped condition or tradeoff) or something DIFFERENT than they do. Then check the neighbours and the `Note:` as described above. Read in this order: `security-and-governance.md`, `delivery-and-lifecycle.md`, `well-architected.md`, `architecture-patterns.md`.
