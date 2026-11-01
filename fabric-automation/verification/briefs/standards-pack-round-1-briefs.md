# Verification of the reference pack, round 1: briefs for three families

Slices: P1 = GPT 6.1 Sol (well-architected.md and architecture-patterns.md, line by line), P2 = Gemini 4 Argon (security-and-governance.md and delivery-and-lifecycle.md, line by line), P3 = Grok 4.7 (all four files, a different angle: omissions, misleading framing, tags, conflicts, and a line-by-line sample of its own choosing).

## Shared preamble (read first, then your slice)

You are verifying a drafted REFERENCE PACK for an open-source project: a "Fabric Code Factory" whose agents plan, test, implement and verify changes to Microsoft Fabric and Power BI items in a sandbox WITH NO NETWORK. The agents cannot read Microsoft Learn while they work, so the guidance they should apply is vendored in the repository as short checks: one line each, with an id, one sentence, where it applies, and the page and section that state it. The pack was drafted by one model (a Claude-family model) from 16 pages of learn.microsoft.com. You are an independent family, and every line will be trusted by agents, so a line that the page does not support, that loses a condition of the page, or that says more than the page says is a defect.

The factory does NOT implement security, permission, network, sensitivity-label or tenant-setting changes in this version: it refuses and escalates them. So checks on those topics say to flag a change to a person and name the guidance (tag `[flag]`). The pack guides and never authorizes.

WHERE (everything is under <review folder>\pack, treat it as READ-ONLY; make scratch copies under <review folder>\scratch-<your slice id> if you need to):

- The four pack files: `well-architected.md`, `security-and-governance.md`, `delivery-and-lifecycle.md`, `architecture-patterns.md`.
- `sources\`: the 16 pages, reduced to text, one file per page. Each starts with `SOURCE:` (the URL) and a date line. Headings are lines that start with `#`. The reduction can lose formatting (tables become `|` lines, code becomes indented lines). If a point looks missing or garbled, read the live page at its URL (public, read only) before you decide. The SHA-256 of each source file is at the end of `DRAFT-NOTES.md`: check the files you use against it.
- `DRAFT-NOTES.md`: what the drafter used, skipped, found contradictory and was unsure of. It is the drafter's own account: do not trust it, use it to know what to look at.
- `DRAFTING-BRIEF.md`: the rules the drafter was given (format, tags, truthfulness, exposure). Your yardstick.

THE FORMAT. A line is: `- \`std-AREA-NN\` <one sentence, at most 35 words, ends with one tag [gate], [review] or [flag] where it helps> Applies to: <what a change touches>. Source: <label>, "<section heading of the page>"[; <label>, "<heading>"] [(control "<name>")].` The label is in the file's Sources table (label, page URL, the page's `updated_at` date, the day it was read). `Note:` lines record a tension between two places. Tags: `[gate]` a deterministic check could decide it from item definitions or the pull request (a name pattern, a missing setting, a file that must not be committed); `[review]` a reviewer's judgement; `[flag]` security, permission, network, sensitivity-label or tenant-setting topics, which the factory only flags; a sentence that starts `Ask:` needs knowledge that only the tenant has.

THE TRUTHFULNESS RULES the drafter had to follow: (1) paraphrase, never more than 12 consecutive words from a page; (2) never add a number, name, limit, feature, setting or recommendation that is not in the source text; numbers copied exactly; (3) never generalize beyond the text (a page that says "workspaces map to teams, projects or environments" must not become "always use one workspace per project"); (4) never merge two pages into one claim unless each supports its part and both are cited; (5) keep conditions ("when ... use ..."), tradeoffs and states such as preview or retiring.

HOW TO JUDGE A LINE. For each check, open the cited section (the heading must be a real heading of that page, and the point must be in that section or below it) and decide:

- SUPPORTED: every part of the sentence (numbers, names, conditions, tradeoffs, preview or retiring states) is in the cited section, and the "Applies to" scope does not claim more than the page does.
- PARTLY: some part is not in the cited section or is stronger than the page. Say which part and quote the page.
- UNSUPPORTED: the page does not say it.
- MISLEADING: each word can be found, but the meaning changes in context (a condition dropped, a tradeoff inverted, a "may" turned into "must", an example turned into a rule, a preview feature presented as general).
- WRONG TAG: a `[gate]` that no program could decide; a `[review]` that is really a security, permission, network, label or tenant-setting topic and should be `[flag]`; a `[flag]` on something else; an `Ask:` that does not need the tenant, or a tenant question without `Ask:`.
- WRONG CITATION: a heading that is not on the page, or that does not hold the point.

Also look for: a number that differs from the page by one digit; a name of a setting or feature spelled differently; a check that would make an agent DO something that the factory must not do; a check that contradicts another check of the pack or one of the `Note:` lines.

RULES FOR FINDINGS. Be adversarial and honest. Every finding needs the evidence: the source file and heading, and a quote of at most 12 words, or the live URL and the sentence. A finding you could not confirm says UNVERIFIED. Rank by real impact on an agent that trusts the line (High: a false or reversed statement, or an agent would do something forbidden; Medium: a lost condition or a wrong scope; Low: wording, tag, or citation precision). No style nits. State a suggested replacement text for each finding (keep the format, at most 35 words in the sentence). Return the whole report inline in your final message, at most 3500 words. Do not rely on writing files. The report ends with "CHECKED AND FINE": the number of lines that you checked and found fully supported, and the ids.

## Slice P1 (GPT 6.1 Sol): `well-architected.md` and `architecture-patterns.md`, every line

All 25 + 16 checks and the 4 `Note:` lines. For each check give the verdict only when it is not SUPPORTED; list the supported ids at the end. For each `Note:` say whether the tension is real (quote both sides) and whether the Note states each side correctly. Also check the header paragraphs of both files (for example the claims about what the security page and the medallion page say) and the `(control ...)` style of citations if you meet them.

## Slice P2 (Gemini 4 Argon): `security-and-governance.md` and `delivery-and-lifecycle.md`, every line

All 18 + 19 checks and the 5 `Note:` lines. The security file is the one that agents will use to decide what to flag to a person, so pay special attention to: tags (is every security, permission, network, label and tenant-setting topic `[flag]`?), the citations of the Azure security baseline page (a section heading plus a control title in parentheses: check both exist on the page), the notice about the baseline being based on version 1.0 of the Microsoft cloud security benchmark, and every claim about what a page "says" in the header paragraphs. In the delivery file pay special attention to the `[gate]` checks (could a program decide them from item definitions?) and to numbers, file names and setting names (`.platform`, `logicalId`, `notebook-settings.json`, SqlPackage, variable libraries, value sets).

## Slice P3 (Grok 4.7): all four files, a different angle

You are the second pair of eyes on a different question: not "is each line supported" (the other two reviewers do that) but "what would hurt an agent that trusts this pack".

1. LINE-BY-LINE SAMPLE. Choose 24 checks yourself across all four files (at least 6 from each file, including at least 8 that are `[gate]` or `[flag]` or start with `Ask:`) and judge them as the other slices do. Say which ids you chose.
2. OMISSIONS. Read the 16 source pages (start with the headings; the very large page is `sources\fabric-fundamentals-understand-best-practices-fabric-cicd.md`). List up to 10 points that a pull request could decide or a reviewer should check, that the pages state clearly, and that the pack leaves out. For each give the page, the heading and a quote of at most 12 words, and a proposed check line in the format above. Do not propose generic cloud advice or anything a pull request cannot change.
3. FRAMING AND CONFLICTS. Find checks that conflict with each other, with a `Note:`, or with the page's own caveats (for example a pattern presented as a rule, or a recommendation with its condition removed). Find checks whose "Applies to" would make an agent apply them to the wrong kind of change.
4. TAGS. List every `[gate]` that no program could decide from item definitions and the pull request description, and every security, permission, network, sensitivity-label or tenant-setting topic that is not `[flag]`.
5. DANGER. Is there any check that, followed literally by an autonomous agent, would make it change a permission, a network setting, a label, a tenant or capacity setting, or delete or recreate something? Is there any text in the four files (header paragraphs included) that reads like an instruction to an agent about anything other than applying checks, or that could be misread as an authorization?
6. THE FILES AS WHOLE. Are the headers honest about what the pack is (guidance condensed from the pages, not a Microsoft checklist, not a compliance statement)? Is anything claimed about the pages (for example "the page says it is not a comprehensive reference") that is not on the page?
