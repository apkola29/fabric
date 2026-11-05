# Verification of the five workload reference files of the pack: the briefs of the drafter, of the three rounds and of the fixer

The briefs that the model which drafted the five workload files (data engineering, semantic models, data agents, capacity and cost, OneLake security) was given, the briefs of the three rounds in which three other families read them (round A: every file by one family; round B: every file by a family that had not read it, and every fix closed by a family other than the one that raised the finding; round C: the seven lines that round B changed), and the brief of the agent that applied the 37 findings of round A.

## The drafter

You are a drafting agent. The project is a "code factory" for Microsoft Fabric: a requirement for a workspace that is backed up in Git comes in, agents plan and implement it on a branch, other agents verify it, and a person approves a draft pull request. The agents run in a sandbox with **no network**, so the guidance they apply has to be in the repository, as short checks with the page and the section that state each point.

An existing pack of 89 checks in four files already covers the Well-Architected pillars, Fabric security and governance, lifecycle (CI/CD) and architecture patterns. It was written and then checked four times against the page text by three other model families, and those reviews found what goes wrong in a line like this. You write FIVE NEW files for the workloads themselves, from pages that the first pack did not use.

### Read first (the existing pack, read only)

The project is in `<project folder>` (read only; do not edit anything in it). Read `toolchain\skills\factory-standards\SKILL.md` and the four files in `toolchain\skills\factory-standards\references\`. Match their format, tone and level of detail. Do not repeat a point that those files already make (grep them for the topic before you write a line); where a new page deepens an existing check, write the new check and do not copy the old one.

### Inputs (the only source of truth)

28 pages of learn.microsoft.com were reduced to text, one file per page, in `<review folder>\pack-sources\` (`<review folder>` is `<review folder>`). Each file starts with `SOURCE:` (the address), `UPDATED_AT:` (the date that the pack records), `MS_DATE:` and `TITLE:`, then the text with `#` headings, lists, pipe tables and fenced code. Read those files. Do not write from memory. You may fetch the same pages live from learn.microsoft.com (read only) to double check one point; use no other site.

The files that feed each reference file (the file name is the address after `learn.microsoft.com/` with other characters turned into hyphens):

1. `data-engineering.md`, area `eng`: `fabric-data-engineering-spark-monitoring-best-practices`, `fabric-data-engineering-spark-best-practices-development-monitoring`, `fabric-data-engineering-spark-best-practices-capacity-planning`, `fabric-data-engineering-delta-optimization-and-v-order`, `fabric-fundamentals-table-maintenance-optimization`, `fabric-data-engineering-sql-analytics-endpoint-performance`, `fabric-data-engineering-native-execution-engine-overview`, `fabric-data-factory-dataflow-gen2-performance-best-practices`.
2. `semantic-models.md`, area `sem`: `fabric-fundamentals-direct-lake-understand-storage`, `fabric-fundamentals-direct-lake-develop`, `power-bi-guidance-star-schema`, `power-bi-guidance-power-bi-optimization`, `power-bi-guidance-import-modeling-data-reduction`, `fabric-data-warehouse-dimensional-modeling-overview`.
3. `data-agents.md`, area `agt`: `fabric-data-science-data-agent-configuration-best-practices`, `fabric-data-science-data-agent-configurations`, `fabric-data-science-data-agent-example-queries`, `fabric-data-science-data-agent-add-datasources`, `fabric-data-science-semantic-model-best-practices`, `fabric-data-science-data-agent-source-control`.
4. `capacity-and-cost.md`, area `cap`: `fabric-enterprise-optimize-capacity`, `fabric-enterprise-capacity-planning-plan-deployment`, `fabric-enterprise-capacity-planning-manage-capacity-growth-governance`, `fabric-enterprise-throttling`.
5. `onelake-security.md`, area `olk`: `fabric-onelake-security-best-practices-secure-data-in-onelake`, `fabric-onelake-security-data-access-control-model`, `fabric-onelake-security-table-column-row-security`, `fabric-onelake-security-get-started-security`.

### Outputs

Write into `<review folder>\pack-draft\` (create it): the five files above, and `DRAFT-NOTES.md`. Nothing else, nothing outside that folder.

### Format of each reference file (exactly as the existing files)

```
## <Title>

<Two or three lines: what this file is for, and what it does not do (it guides, it never authorizes a change).>

### Sources

| Label | Page | Updated | Retrieved |
|---|---|---|---|
| <short label you use below> | <the SOURCE address, as written in the file> | <UPDATED_AT as yyyy-mm-dd> | 2026-11-04 |

### <Topic heading>

- `std-<area>-<nn>` <the check, in one sentence> Applies to: <what a change touches>. Source: <label>, "<section heading of the page>".
```

- The `Updated` column is the `UPDATED_AT` date of the file (not `MS_DATE`). The `Page` column is the `SOURCE` address exactly.
- A `Note:` line records a tension between two places or a choice that a page leaves open: `Note: <text> Source: <label>, "<heading>"; <label>, "<heading>".`
- Ids: `std-` then the area of the file (`eng`, `sem`, `agt`, `cap`, `olk`) then two digits, unique across the five files (`std-eng-01`, `std-eng-02`, ...).
- One sentence, at most 35 words (the tag does not count), in the imperative or as a question, that a reader can decide by looking at a proposed change, the item definitions in the branch or the pull request description. If it needs knowledge that only the tenant has, begin with `Ask:`.
- End the sentence with at most one tag: `[gate]` when a program could decide it from item definitions or the pull request (a name pattern, a missing property, a file that must not be committed); `[review]` for a reviewer's judgement; `[flag]` for a CHANGE to security, permissions, network, sensitivity labels or tenant or capacity settings (the factory never makes such a change; it flags it to a person). What a change merely contains, such as a secret in a file, is not such a change. A capacity setting, a role, a data access role or a tenant setting that a change would alter is a `[flag]`.
- "Applies to" names the kind of change (a new notebook, a lakehouse table, a semantic model, a data agent, a capacity assignment). Keep it short.
- Cite the page and the exact heading of the section (a heading that is in the text file, any level) that states the point. If the point comes from a table or list inside a section, cite that section. Two citations are fine where each page supports its part.
- About 10 to 16 checks per file, about 60 in all. Quality over quantity. Leave out marketing, generic cloud advice, and what a pull request cannot change or should not decide (buying capacity, hiring). Choices that a change can influence (a schedule, a refresh mode, table layout, what is materialized, a data agent instruction) are in scope.

### What the earlier reviews found wrong in lines like these (read this twice)

The four rounds of review found a defect in about one line of four in the first draft. The same kinds of defect will occur again unless you avoid them:

1. **A lost condition.** A page says "can", "may", "when X", "if X", "for example", "usually", "consider", "in most cases", "for small tables". A check that drops the condition turns an option into a requirement. Keep the condition in the sentence.
2. **A closed list made from an open one.** "such as A and B" is not "A or B". Say "for example" when the page gives examples.
3. **A scope that is wider than the page.** If the page is about one item type, one mode (import, Direct Lake, DirectQuery), one engine or one tier, say so in the check.
4. **A state that the page marks.** Preview, retiring, "currently", "not supported yet", a runtime version, a limit of a size or a number: keep it and copy numbers exactly. A recommendation that depends on a default ("it is off by default") must say what the default is as the page states it.
5. **A tradeoff turned into a rule.** If a page weighs two options, the check asks which one the change uses and why, or states the tradeoff; it does not pick one.
6. **A wrong tag.** `[gate]` only if a program can decide it; `[review]` is the safe tag for a judgement; do not tag a performance or modelling point `[flag]`.
7. **Two checks that cannot both be followed**, or a check that conflicts with the existing pack. Write a `Note:` instead and cite both.
8. **Wording that reads as an order to act.** The pack guides. Phrase a check as a question or as "Flag a change to ...; guidance: ...", and never "assign roles" or "enable X".
9. **A claim about a number or a name that is not in the cited section.** Every number, product name, setting name and limit must be found in the cited section. If it is in another section of the page, cite that section.

### Truthfulness rules (a reviewer will check each line against the page, and a program checks the numbers and headings)

1. Paraphrase. Never copy more than 12 consecutive words from a page.
2. Never add a number, a name, a limit, a feature, a setting or a recommendation that is not in the source text. If you are unsure, leave the point out and list it in the notes as UNVERIFIED.
3. Do not generalize beyond the text.
4. Do not merge two pages into one claim unless each supports its part, and then cite both.
5. Where two pages differ (for example two pages that give different thresholds), say so in a `Note:` and cite both. Do not rank the pages.

### Exposure rules (the repository is public and a validator scans every file)

- Plain ASCII: straight quotes, a hyphen or a comma instead of a dash, no arrows, no symbols, no accented letters.
- No four numbers separated by dots, no GUIDs, nothing that looks like an e-mail address, no file system path, no token, no person's name, no tenant, workspace or item identifier.
- The validator treats a capital letter followed by digits or by a hyphen and digits (for example `F64`, `P1`, `F2`, `K9`, `S3`, `C2`, `HR-4`, `FR-01`, `D-04`, `A1`) as a reference to a design identifier and fails the file. Never write such a token. For capacity sizes write "an F SKU", "a P SKU", "the smallest F SKU" and so on, as the page allows; if the page names a SKU, say "a capacity of the size that the page names" and cite it. Version words like `Runtime 1.3` and names like `V-Order` are fine; check each capital-plus-digit token before you write it.
- Do not claim or imply a certification, compliance status or guarantee that the pages do not state.

### Notes (`DRAFT-NOTES.md`)

For each reference file: the sections you used per page; the sections you skipped, with a few words of reason; every point that you could not phrase without copying or that you could not fully support (UNVERIFIED, and what is missing); every contradiction, outdated signal or preview/retiring state that you saw. At the end, the SHA-256 of each of the 28 source files (Python `hashlib` is fine), so that the checker can confirm that it reads the same text.

### Self-check before you finish

From the project folder you may run (read only) `python verification\tools\pack_mechanics.py <review folder>\pack-draft <review folder>\pack-sources`. It reports a citation, a number or a heading that it cannot find in the cited pages and any run of more than 12 copied words. Fix everything it reports. Also count the words of each sentence (35 at most) and check each id is unique.

### Limits

Touch nothing outside `<review folder>\pack-draft\` and scratch files named `fa-pack-*` in the temporary folder. No installs, no sign-in, no network except read-only fetches of learn.microsoft.com pages. Do not edit the project. When done, reply in at most 400 words: the files with the number of checks and notes in each, and what the checker should look at first.

## Round A

Slices: P1 = GPT 6.1 Sol (`data-engineering.md` and `data-agents.md`, every line, cold), P2 = Gemini 4 Argon (`semantic-models.md` and `onelake-security.md`, every line, cold), P3 = Grok 4.7 (`capacity-and-cost.md`, every line, and a different angle over all five files).
Nobody has read these files before. Each file has been checked only by a program (format, ids, copied runs, numbers, tags), never by a model of another family.

### Shared preamble (read first, then your slice)

You are verifying five drafted REFERENCE FILES for an open-source project: a "Fabric Code Factory" whose agents plan, test, implement and verify changes to Microsoft Fabric and Power BI items in a sandbox WITH NO NETWORK. The agents cannot read Microsoft Learn while they work, so the guidance they should apply is vendored in the repository as short checks: one line each, with an id, one sentence, where it applies, and the page and section that state it. The files were drafted by one model (a Claude-family model) from 28 pages of learn.microsoft.com. You are an independent family, and every line will be trusted by agents, so a line that the page does not support, that loses a condition of the page, or that says more than the page says is a defect. An older pack of four files (89 checks) was verified in the same way: round 1 found a defect in about every third line (a lost condition, a wrong scope, a wrong tag, an invented name, a copied run of words). Expect the same here.

The factory does NOT implement security, permission, network, sensitivity-label or tenant-setting changes in this version: it refuses and escalates them. So checks on those topics say to flag a change to a person and name the guidance (tag `[flag]`). The pack guides and never authorizes.

WHERE (everything is under <review folder>\PACK-VERIFY , treat it as READ-ONLY; make scratch copies under <review folder>\scratch-pack-<your slice id> if you need to):

- `pack\`: the five files to verify: `data-engineering.md` (area `eng`, 28 checks and notes), `semantic-models.md` (`sem`, 24), `data-agents.md` (`agt`, 22), `capacity-and-cost.md` (`cap`, 21), `onelake-security.md` (`olk`, 20).
- `sources\`: the 28 pages, reduced to text, one file per page (`<slug>.md`; the slug is the address after `learn.microsoft.com/` with every run of other characters turned into one hyphen), and `<slug>.links.txt` (the links of the page). Each page starts with `SOURCE:` (the address), `UPDATED_AT:` (the date that the pack records), `MS_DATE:` and `TITLE:`; headings are lines that start with `#`. The reduction can lose formatting (tables become `|` lines, code becomes indented lines). If a point looks missing or garbled, read the live page at its address (public, read only) before you decide.
- `notes\NOTES-<area>.md`: what the drafter used, skipped, found contradictory and was unsure of, with the SHA-256 of every source file it used (check the files you use against it). It is the drafter's own account: do not trust it, use it to know where to look. The drafter named places where it went beyond a page; look at those first.
- `DRAFTING-BRIEF.md`: the rules that the drafter was given (format, tags, truthfulness, exposure). Your yardstick. A sentence may not copy more than 12 consecutive words of a page (a program checks this, with a stricter limit; judge meaning, not copying). A check may name "Amazon S3" only as "the Amazon store that the page names", because the repository's validator reads the two-character name as a reference to a design identifier (this is intended, not a defect).
- `existing\`: the four files of the older pack, for conflicts and duplicates only. `SKILL.md`: the skill that carries the pack (section 2 says what the tags mean).

THE FORMAT. A line is: `- \`std-AREA-NN\` <one sentence, at most 35 words, ends with one tag [gate], [review] or [flag] where it helps> Applies to: <what a change touches>. Source: <label>, "<section heading of the page>"[; <label>, "<heading>"].` The label is in the file's Sources table (label, page address, the page's `updated_at` date, the day it was read). `Note:` lines record a tension between two places or a choice that a page leaves open (no id; number them in file order as `note-AREA-N`: `note-eng-1`, `note-sem-2`, ...). Tags: `[gate]` a deterministic check could decide it from item definitions or the pull request (a name pattern, a missing setting, a file that must not be committed); `[review]` a reviewer's judgement; `[flag]` a CHANGE to security, permission, network, sensitivity-label or tenant or capacity settings, which the factory only flags (what a change merely contains, such as a secret in a file, is not such a change); a sentence that starts `Ask:` needs knowledge that only the tenant has.

TRUTHFULNESS RULES the drafter had to follow: (1) paraphrase, never more than 12 consecutive words from a page; (2) never add a number, name, limit, feature, setting or recommendation that is not in the source text; numbers copied exactly; (3) never generalize beyond the text (a page that says "workspaces map to teams, projects or environments" must not become "always use one workspace per project"); (4) never merge two pages into one claim unless each supports its part and both are cited; (5) keep conditions ("when ... use ..."), tradeoffs and states such as preview or retiring; a permissive statement ("can", "may") must not become a requirement ("must", "does ... always"), and a disjunction ("A, B or C") must not become a conjunction.

HOW TO JUDGE A LINE. For each check, open the cited section (the heading must be a real heading of that page, and the point must be in that section or below it) and decide:

- S SUPPORTED: every part of the sentence (numbers, names, conditions, tradeoffs, preview or retiring states, file and setting names with their exact spelling) is in the cited section, and the "Applies to" scope does not claim more than the page does.
- P PARTLY: some part is not in the cited section or is stronger than the page. Say which part and quote the page.
- U UNSUPPORTED: the page does not say it.
- M MISLEADING: each word can be found, but the meaning changes in context (a condition dropped, a tradeoff inverted, a "may" turned into "must", an example turned into a rule, a preview feature presented as general, a recommendation turned into a restriction).
- T WRONG TAG: a `[gate]` that no program could decide from item definitions and the pull request; a change of security, permission, network, label or tenant or capacity setting that is not `[flag]`; a `[flag]` on something that is not one of those; an `Ask:` that does not need the tenant, or a tenant question without `Ask:`.
- C CONFLICT OR WRONG CITATION: two checks, or a check and a `Note:`, that an agent cannot follow together without a rule that the pack does not give; or a heading that is not on the page or does not hold the point. Say which.
- X OTHER defect.

For a `Note:` the verdict says whether the tension is real (quote both sides) and whether each side is stated correctly.

Also look for: a number that differs from the page by one digit; a name of a setting or feature spelled differently; a check that would make an agent DO something that the factory must not do (change a permission, a network setting, a label, a tenant or capacity setting, or delete or recreate something); text in the headers that claims more than the pages say.

THE REPORT. One row for EVERY check and EVERY note of your slice, in the exact format `id | verdict | quote | reason` (one line each, with the vertical bars). The quote is at most 12 words, copied VERBATIM from the cited section of the cited page; it is the text that shows the verdict is right. A program looks every quote up in the cited section of the cited page; a row whose quote is not there shows that the line was not read against the page, and the row is worthless. A line that you could not confirm gets P or U and says UNVERIFIED in the reason.

RULES FOR FINDINGS. Be adversarial and honest. Every finding needs the evidence: the source file and heading, and a quote of at most 12 words, or the live address and the sentence. Rank by real impact on an agent that trusts the line (High: a false or reversed statement, or an agent would do something forbidden; Medium: a lost condition or a wrong scope; Low: wording, tag, or citation precision). No style nits. State a suggested replacement line for each finding (keep the format, at most 35 words in the sentence). Return the whole report inline in your final message, at most 7000 words, in this order: the rows, then `FINDINGS` (numbered F1, F2, ... with severity, the id of the line, the quote, and the replacement), then `CHECKED AND FINE` (the number of rows with verdict S and a one-line statement of what you did NOT check). Do not rely on writing files. No installs, no sign-in; the only network use is read-only fetches of the cited public pages.

### Slice P1 (GPT 6.1 Sol): `data-engineering.md` (28) and `data-agents.md` (22), every line

All checks and notes of both files, and the header paragraphs of both (every claim about what a page says or about the preview state of a feature). In `data-agents.md` the drafter named seven places where it went beyond the page (see `notes\NOTES-agt.md`): check each of them first. Pay special attention to numbers (thresholds, sizes, counts of data sources or queries), names of settings, runtimes and file names, the preview state of each feature, and the tags (is every `[gate]` decidable by a program from the item definitions? is a change to access to a workspace `[flag]`?).

### Slice P2 (Gemini 4 Argon): `semantic-models.md` (24) and `onelake-security.md` (20), every line

All checks and notes of both files, and the header paragraphs of both. `onelake-security.md` is the file that agents will use to decide what to flag to a person about data access: pay special attention to its tags (is every change of a data access role, a permission, row-level or column-level or object-level security, a workspace role or a tenant setting a `[flag]`?), to the exact names of roles and permissions, to what a page says about what security applies to which kind of access, and to every claim in the header. In `semantic-models.md` pay special attention to Direct Lake behaviour (fallback, framing, transcoding, column and table limits as the pages state them), numbers and sizes, and the difference between a recommendation and a requirement.

### Slice P3 (Grok 4.7): `capacity-and-cost.md` (21) every line, and a different angle over all five files

1. EVERY LINE of `capacity-and-cost.md` and its header, as the other slices do, with the same rows. Pay special attention to numbers (percentages, seconds, minutes, days, smoothing windows, SKU sizes, limits), to what throttling and smoothing do to interactive and to background operations, and to every line that tells an agent what to do about a capacity (that is a `[flag]` when it changes a capacity or a tenant setting).
2. SAMPLE of the other four files: choose 24 checks yourself (at least 5 from each of the other four files, including at least 8 that are `[gate]` or `[flag]` or start with `Ask:`) and judge each as the other slices do, with a row each. List the ids that you chose at the start of FINDINGS.
3. CONFLICTS AND DUPLICATES: find checks of the five new files that conflict with each other, with a `Note:`, or with a check of the four older files in `existing\` (a pattern presented as a rule, a recommendation with its condition removed, two checks that an agent cannot follow together), and checks that repeat an older check without adding anything.
4. TAGS: list every `[gate]` of the five files that no program could decide from item definitions and the pull request description, and every change of security, permission, network, sensitivity label, tenant or capacity setting that is not `[flag]`.
5. DANGER: is there any check that, followed literally by an autonomous agent, would make it change a permission, a network setting, a label, a tenant or capacity setting, or delete or recreate something? Is there any text in the five files (header paragraphs included) that reads like an instruction to an agent about anything other than applying checks, or that could be misread as an authorization?
6. HEADERS: are the headers honest about what each file is (guidance condensed from pages, not a Microsoft checklist, not a compliance statement)? Is anything claimed about the pages that is not on them?

## The fixer

You are the drafter of the five reference files (a Claude-family model). Three other model families (GPT 6.1 Sol, Gemini 4 Argon, Grok 4.7) read the files against the pages and raised findings. You apply the fixes. You work only in `<review folder>\PACK-FIX\` (edit the files in `PACK-FIX\pack\`; `PACK-FIX\original\` is the untouched copy to diff against). Everything else is read-only for you.

### Inputs (read them all first)

- The files to fix: `PACK-FIX\pack\` (`data-engineering.md`, `semantic-models.md`, `data-agents.md`, `capacity-and-cost.md`, `onelake-security.md`).
- The rules you drafted under: `<review folder>\PACK-VERIFY\DRAFTING-BRIEF.md` (format, tags, truthfulness, exposure). They still hold in full: one sentence of at most 35 words per check, at most 12 consecutive words from a page (the checking program is stricter: keep copied runs short), no number, name, limit, feature or setting that the cited section does not state, conditions and preview states kept, "may" never becomes "must", a disjunction never becomes a conjunction, `Source:` headings must be real headings of the page and hold the point.
- The pages: `<review folder>\PACK-VERIFY\sources\` (28 pages as text; live pages at learn.microsoft.com may be fetched read-only to settle a doubt). Your own notes: `PACK-VERIFY\notes\NOTES-<area>.md`.
- The older pack, which you must NOT edit: `PACK-VERIFY\existing\` (`well-architected.md`, `security-and-governance.md`, `delivery-and-lifecycle.md`, `architecture-patterns.md`). It was verified four times. Where a new line conflicts with an older one, resolve it inside the new file (narrow the scope of the new line to what its page says, or add a `Note:` that names the tension and the older id), never by changing the older file.
- The three reports (their FINDINGS sections, and the rows whose verdict is not S): `<review folder>\reports\pa-gpt.txt` (findings F1 to F4; call them P-F1 to P-F4), `pa-gemini.txt` (F1 to F17; G-F1 to G-F17) and `pa-grok.txt` (F1 to F16; K-F1 to K-F16). The reviewers' suggested replacements are suggestions: check each against the page before you adopt it, and adapt it when it breaks a rule above.
- The tool: `python "<project folder>\verification\tools\pack_mechanics.py" "<dir with the five files>" "<review folder>\PACK-VERIFY\sources"` prints the mechanical problems of the files (labels, headings, numbers, copied runs, ids). It must print `0 problem(s)` at the end. Run it on `PACK-FIX\pack`.

### Decisions of the orchestrator (follow them; where you disagree, say so in the dispositions and still follow them)

1. TAGS FOR ONELAKE SECURITY. The factory flags and never makes a change of security roles, data access roles, row-level or column-level rules, workspace roles or tenant settings. The older pack's convention: a check whose topic is such a change, or whose remedy is such a change, is `[flag]`, including when it starts with `Ask:` (see `std-sec-06`, `std-sec-11`, `std-sec-12`, `std-sec-13` in `security-and-governance.md`). So `std-olk-05`, `std-olk-08`, `std-olk-09` and `std-olk-14` become `[flag]` lines in the style `Flag ...; guidance: ...` (or `Ask: ... [flag]`), keeping the guidance of the page in the clause after `guidance:`. For `std-olk-14` use the exact name of the tenant setting from the page. For `std-olk-08` keep both the conditions of Gemini (Tables directory, valid schema folder if schemas are enabled, no child shortcuts) and the detail of Grok (a `_delta_log` folder that has the metadata JSON files), each only as far as the page says it.
2. DECIDABLE GATES. A `[gate]` must be decidable by a program from the item definitions or the pull request. Where only part of a line is decidable, split the line: the decidable part stays `[gate]`, the judgement part becomes a new `[review]` line with the next free number of that file (append it at the end of its section; never renumber an existing id). Apply this to `std-sem-04` (G-F5) after you read the page and your own notes on how the parts appear in Git.
3. NO RENUMBERING. Never change the id of an existing check, and avoid adding or removing a `Note:` (notes are numbered `note-AREA-N` in file order, and the reviewers' reports use those numbers). If a note must go or must be added, say so in the dispositions.
4. CONFLICTS WITH THE OLDER PACK (K-F14: `std-sem-08` against `std-arc-07`; G-F6: `std-olk-16` against `std-eng-01`; G-F7: `std-sem-10` against `std-arc-05`; K-F15: `note-cap-4` against `std-perf-02`; K-F16: `std-sec-11` against the OneLake note): resolve them in the new file only. Make the new line say the condition of its page, so that an agent can tell which line applies when (for example by naming the case in "Applies to", or by adding the older id to the note that records the tension). Do not rank two pages that the pages themselves do not rank.
5. LOW findings: apply them when they are right (check the page), and say so. If a finding is wrong, reject it with the page text that shows it.
6. HEADERS: G-F17 asks that the headers of `semantic-models.md` and `onelake-security.md` be true after the fixes (and mention a preview or retiring notice where the pages carry one). Re-read both headers against your fixed lines and the pages, and fix what is not true. Do not add claims that the pages do not carry.
7. Do not touch a line that no reviewer questioned, except where a fix needs it.

### Findings by file (all of them are in the three reports; this list only tells you where to look)

- `data-engineering.md`: `std-eng-01` (K-F9), `note-eng-2` (P-F1), `note-eng-4` (P-F2).
- `data-agents.md`: `std-agt-09` (P-F3), `std-agt-14` (P-F4, K-F11), `std-agt-01` (K-F10).
- `semantic-models.md`: `std-sem-04` (G-F5), `std-sem-08` (K-F14), `std-sem-10` (G-F7), `std-sem-11` (G-F8), `std-sem-17` (G-F9), `note-sem-5` (G-F14), header (G-F17).
- `onelake-security.md`: `std-olk-02` (G-F10), `std-olk-04` (G-F11), `std-olk-05` (G-F1), `std-olk-08` (G-F2, K-F4), `std-olk-09` (G-F3), `std-olk-11` (G-F12, K-F12), `std-olk-12` (G-F13), `std-olk-14` (G-F4, K-F13), `std-olk-16` (G-F6), `note-olk-3` (G-F15), `note-olk-4` (G-F16), header (G-F17).
- `capacity-and-cost.md`: `std-cap-11` (K-F6), `std-cap-12` (K-F5), `std-cap-13` (K-F3), `std-cap-15` (K-F1), `std-cap-16` (K-F2), `note-cap-2` (K-F7), `note-cap-5` (K-F8), `note-cap-4` (K-F15).
- `K-F16` concerns `std-sec-11` of the older pack, which you may not edit: answer it by what the new OneLake note says (and, if needed, by naming `std-sec-11` in it).

### Outputs

1. The fixed files in `PACK-FIX\pack\` (same file names, same format, plain ASCII).
2. `PACK-FIX\DISPOSITIONS.md`: a table with one row for every finding id (P-F1 to P-F4, G-F1 to G-F17, K-F1 to K-F16): the line id, the decision (ADOPTED, ADAPTED, REJECTED, SPLIT, NOTE), a one-sentence reason that names the page heading you checked, and the new text of the line (or "unchanged"). After the table: a list of every id that you added, every note that you added or removed, and anything you could not settle (say UNVERIFIED).
3. The last line of your final message must be the output of `pack_mechanics.py` (`0 problem(s)`).

Return a short final message (at most 400 words): what you changed, what you rejected and why, what is open. Do not write anywhere else, install nothing, sign in nowhere.

## Round B

Slices: B1 = GPT 6.1 Sol (`onelake-security.md` and `capacity-and-cost.md`, every line, cold, and the closure of the findings that Gemini and Grok raised about them), B2 = Gemini 4 Argon (`data-engineering.md` and `data-agents.md`, every line, cold, and the closure of the findings that GPT and Grok raised about them), B3 = Grok 4.7 (`semantic-models.md`, every line, cold, the closure of the findings that Gemini raised about it, and a cold read of every changed line of the other four files).
Rotation: in round A each file was read by one family, and the three families raised 37 findings (GPT 4, Gemini 17, Grok 16). The drafter fixed them. Now every file is read, cold, by a family that has not read it, and every finding is closed by a family other than the one that raised it. A fix can introduce a new defect: treat the changed text as unverified.

### Shared preamble (read first, then your slice)

You are verifying five drafted REFERENCE FILES for an open-source project: a "Fabric Code Factory" whose agents plan, test, implement and verify changes to Microsoft Fabric and Power BI items in a sandbox WITH NO NETWORK. The agents cannot read Microsoft Learn while they work, so the guidance they should apply is vendored in the repository as short checks: one line each, with an id, one sentence, where it applies, and the page and section that state it. The files were drafted by one model (a Claude-family model) from 28 pages of learn.microsoft.com, read once by a family each in round A (a defect in about one line in three), and corrected. You are an independent family, and every line will be trusted by agents, so a line that the page does not support, that loses a condition of the page, or that says more than the page says is a defect.

The factory does NOT implement security, permission, network, sensitivity-label or tenant-setting changes in this version: it refuses and escalates them. So checks on those topics say to flag a change to a person and name the guidance (tag `[flag]`). The pack guides and never authorizes.

WHERE (everything is under <review folder>\PACK-VERIFY2 , treat it as READ-ONLY; make scratch copies under <review folder>\scratch-packb-<your slice id> if you need to):

- `pack\`: the five fixed files: `data-engineering.md` (area `eng`, 18 checks and 10 notes), `semantic-models.md` (`sem`, 18 checks and 7 notes), `data-agents.md` (`agt`, 16 and 6), `capacity-and-cost.md` (`cap`, 16 and 5), `onelake-security.md` (`olk`, 16 and 4).
- `original\`: the same files as round A read them. `diffs\`: the unified diffs from `original\` to `pack\` (the changed lines only).
- `sources\`: the 28 pages, reduced to text, one file per page (`<slug>.md`; the slug is the address after `learn.microsoft.com/` with every run of other characters turned into one hyphen), and `<slug>.links.txt`. Each page starts with `SOURCE:`, `UPDATED_AT:` (the date that the pack records), `MS_DATE:` and `TITLE:`; headings are lines that start with `#`. The reduction can lose formatting (tables become `|` lines, code becomes indented lines). If a point looks missing or garbled, read the live page at its address (public, read only) before you decide.
- `reports-a\`: the three reports of round A (`pa-gpt.txt`, `pa-gemini.txt`, `pa-grok.txt`): their `FINDINGS` sections hold the findings by id (the reports number them F1, F2, ...; the closure ids are P-F1 to P-F4 for the findings of GPT, G-F1 to G-F17 for those of Gemini, K-F1 to K-F16 for those of Grok).
- `DISPOSITIONS.md`: what the drafter did about each finding, as its own account (do not trust it; use it to find what to check). The orchestrator decided five things that the drafter followed, and you may challenge a decision only with evidence from a page or from the files:
  1. A check whose topic, or whose remedy, is a change of a OneLake security role, a data access role, a row-level or column-level rule, a workspace role or a tenant setting is `[flag]` (including when it starts with `Ask:`), in the style `Flag ...; guidance: ...` or `Ask: ... [flag]`, as the older pack does (`std-sec-06`, `std-sec-11`, `std-sec-12`, `std-sec-13`).
  2. A `[gate]` has to be decidable by a program from the item definitions or the pull request. Where only a part of a line is decidable, the line was split: the decidable part stays `[gate]` and the judgement part is a new `[review]` line with the next free number (for example `std-sem-18`). Existing ids were never renumbered, and no note was added or removed.
  3. Conflicts with the older pack were resolved in the new file only (the older files were not edited): the new line names its case, and a note names the tension and the older id, without ranking two pages that do not rank each other.
  4. A finding that was wrong was rejected with the page text that shows it (the table of dispositions says which parts of a suggestion were not taken and why).
  5. The headers of `semantic-models.md` and `onelake-security.md` carry the preview and retiring notices of their pages.
- `notes\NOTES-<area>.md`: the drafter's notes of the first draft, with the SHA-256 of every source file it used (check the files you use against it). `DRAFTING-BRIEF.md`: the rules that the drafter was given (format, tags, truthfulness, exposure). Your yardstick. A sentence may not copy more than 12 consecutive words of a page (a program checks this with a stricter limit; judge meaning, not copying). A check may name "Amazon S3" only as "the Amazon store that the page names" (the repository's validator reads the two-character name as a reference to a design identifier: intended, not a defect).
- `existing\`: the four files of the older pack, for conflicts and duplicates only. `SKILL.md`: the skill that carries the pack.

THE FORMAT, THE TRUTHFULNESS RULES, HOW TO JUDGE A LINE and the verdict letters S, P, U, M, T, C, X are exactly those of round A (the brief is in this folder as `PACK-A-BRIEF.md`; read its sections "THE FORMAT", "TRUTHFULNESS RULES", "HOW TO JUDGE A LINE", "THE REPORT" and "RULES FOR FINDINGS" first). In short: for every check and every note, open the cited section of the cited page (the heading must be a real heading of that page and the point must be in that section or below it) and decide S supported, P partly, U unsupported, M misleading, T wrong tag, C conflict or wrong citation, X other. Notes are numbered in file order as `note-AREA-N`.

THE REPORT. (1) One row for EVERY check and EVERY note of your files, in the exact format `id | verdict | quote | reason` (one line each, with the vertical bars); the quote is at most 12 words, copied VERBATIM from the cited section of the cited page, and a program looks it up in that section: a row whose quote is not there is worthless. (2) One closure row for EVERY finding of your closure list, in the format `finding-id | verdict | quote | reason` with the verdict F (fixed: the new text does what the finding asked, and is itself supported by the page), P (partly), N (not fixed, or the drafter's disposition says DONE and the file does not show it), R (the fix made something worse: a new unsupported claim, a lost condition, a conflict) or J (the drafter rejected the finding or part of it, and the rejection is justified by the page: say which page text); the quote is at most 12 words copied VERBATIM from the NEW line in `pack\` (or from the page, for J); the reason says what you looked at. Do not trust DISPOSITIONS.md. (3) `FINDINGS` (F1, F2, ... with severity High, Medium or Low, the id of the line, a quote, and a suggested replacement line in the same format, at most 35 words in the sentence), then `CHECKED AND FINE` (the number of rows S or F, and a one-line statement of what you did NOT check). Return the whole report inline in your final message, at most 7500 words. Do not rely on writing files. Edit nothing outside your scratch folder; install nothing; sign in nowhere; the only network use is read-only fetches of the cited public pages.

### Slice B1 (GPT 6.1 Sol): `onelake-security.md` and `capacity-and-cost.md`

- Rows: every check and note of both files (`std-olk-*`, `note-olk-*`, `std-cap-*`, `note-cap-*`), and the header paragraphs of both (every claim about what a page says or about the preview or retiring state of a feature).
- Closure: G-F1, G-F2, G-F3, G-F4, G-F6, G-F10, G-F11, G-F12, G-F13, G-F15, G-F16 (Gemini, about `onelake-security.md`), K-F4, K-F12, K-F13 (Grok, about `onelake-security.md`), K-F16 (Grok, about the older `std-sec-11` and `note-olk-4`), K-F1, K-F2, K-F3, K-F5, K-F6, K-F7, K-F8, K-F15 (Grok, about `capacity-and-cost.md`).
- `onelake-security.md` is the file that agents use to decide what to flag to a person about data access: check that every change of a data access role, a permission, row-level or column-level security, a workspace role or a tenant setting is `[flag]`, the exact names of roles, permissions and settings, what a page says about which security applies to which access, and that no line says more than its section.
- `capacity-and-cost.md`: numbers (percentages, seconds, minutes, days, smoothing windows, SKU sizes, limits), what throttling and smoothing do to interactive and to background operations, and every line that tells an agent what to do about a capacity (a change of a capacity or a tenant setting is `[flag]`).

### Slice B2 (Gemini 4 Argon): `data-engineering.md` and `data-agents.md`

- Rows: every check and note of both files (`std-eng-*`, `note-eng-*`, `std-agt-*`, `note-agt-*`), and the header paragraphs of both.
- Closure: P-F1, P-F2 (GPT, about `data-engineering.md`), P-F3, P-F4 (GPT, about `data-agents.md`), K-F9 (Grok, `std-eng-01`), K-F10, K-F11 (Grok, `std-agt-01` and `std-agt-14`), K-F14 (Grok, `std-sem-08` of `semantic-models.md` against the older `std-arc-07`: read that one line of `semantic-models.md`, its notes and `existing\architecture-patterns.md`).
- Pay attention to numbers (thresholds, sizes, counts of data sources or queries), names of settings, runtimes and file names, the preview state of each feature (data agents: source control, schema object descriptions, topics and advanced DAX generation are marked as preview by their pages), and the tags (is every `[gate]` decidable by a program from the item definitions? is a change to access to a workspace `[flag]`?). In `data-engineering.md` check the notes against both sides: a note that claims that two pages do not reconcile must be right about both.

### Slice B3 (Grok 4.7): `semantic-models.md`, and the changed lines of the other four files

- Rows: every check and note of `semantic-models.md` (`std-sem-*`, `note-sem-*`), and its header paragraphs. `std-sem-18` is new, and `std-sem-04` was split.
- Closure: G-F5, G-F7, G-F8, G-F9, G-F14 (Gemini, about `semantic-models.md`) and G-F17 (Gemini, the headers of `semantic-models.md` and `onelake-security.md`: say whether each header is true after the fixes and carries the preview and retiring notices of its pages).
- Cold read of the changed lines of the other four files: read `diffs\data-engineering.md.diff`, `data-agents.md.diff`, `capacity-and-cost.md.diff` and `onelake-security.md.diff`, and give one row for every changed or new check or note in them (format as above, quote from the cited section). Look for what a fix introduces: a number, a name or a condition that its section does not hold, a tag that is wrong after the change, a line over 35 words, a conflict with a neighbouring line or with the older pack.
- Direct Lake behaviour (fallback, framing, transcoding, the limits that the pages state), numbers and sizes, and the difference between a recommendation and a requirement, in `semantic-models.md`.

### All slices: what else to look for

- A check that, followed literally by an autonomous agent, would make it change a permission, a network setting, a label, a tenant or capacity setting, or delete or recreate something; any text in the headers that reads like an instruction to an agent about anything other than applying checks, or that could be misread as an authorization.
- A line that conflicts with another line of the five files, with a `Note:`, or with the older pack in `existing\`.
- A header that claims more than the pages say.

## Round C

Round A had every file read by one family and found 37 defects (about one line in four). The drafter fixed them. Round B had every file read, cold, by a family that had not read it, and every fix closed by a family other than the one that raised the finding: it read 142 rows and found 7 defects (3 Medium, 4 Low), and the closure rows of 37 findings were F (fixed) except for 3 that were partly fixed and one justified rejection. The 7 defects were fixed again. Round C is the last, small round: every family reads exactly the 7 lines that round B changed (and the header and the table of sources of one file), cold, and decides whether each fix is right and whether it introduced a new defect. A fix can introduce a new defect: treat the changed text as unverified.

### Shared preamble

You are verifying drafted REFERENCE FILES for an open-source project: a "Fabric Code Factory" whose agents plan, test, implement and verify changes to Microsoft Fabric and Power BI items in a sandbox WITH NO NETWORK. The agents cannot read Microsoft Learn while they work, so the guidance they should apply is vendored in the repository as short checks: one line each, with an id, one sentence, where it applies, and the page and section that state it. A line that the page does not support, that loses a condition of the page, or that says more than the page says is a defect. The factory does NOT implement security, permission, network, sensitivity-label or tenant-setting changes in this version: it refuses and escalates them, so checks on those topics say to flag a change to a person and name the guidance (tag `[flag]`). The pack guides and never authorizes.

WHERE (everything is under <review folder>\PACK-VERIFY3 , treat it as READ-ONLY; make scratch copies under <review folder>\scratch-packc-<your family> if you need to):

- `pack\`: the five files as they are now: `data-engineering.md` (area `eng`), `semantic-models.md` (`sem`), `data-agents.md` (`agt`), `capacity-and-cost.md` (`cap`), `onelake-security.md` (`olk`).
- `original\`: the same files as round B read them. `diffs\`: the unified diffs from `original\` to `pack\`: they are exactly the changed lines (13 diff lines for `onelake-security.md`: its header, a new row of the table of sources, `std-olk-12` and `note-olk-4`; 5 for each of the others, one changed line each; 7 for `capacity-and-cost.md`: two changed lines).
- `sources\`: the 28 pages of the five files and the Fabric security fundamentals page (29 pages), reduced to text, one file per page (`<slug>.md`; the slug is the address after `learn.microsoft.com/` with every run of other characters turned into one hyphen). Each page starts with `SOURCE:`, `UPDATED_AT:`, `MS_DATE:` and `TITLE:`; headings are lines that start with `#`. The reduction can lose formatting (tables become `|` lines, code becomes indented lines). If a point looks missing or garbled, read the live page at its address (public, read only) before you decide.
- `existing\`: the four files of the older pack, for conflicts and duplicates only (`std-sec-11` of `security-and-governance.md` is the line that `note-olk-4` names; `std-arc-05` and `std-arc-07` of `architecture-patterns.md`; `std-perf-02` of `well-architected.md`).
- `reports-b\`: the three reports of round B (`pb-gpt.txt`, `pb-gemini.txt`, `pb-grok.txt`); their `FINDINGS` sections hold the 7 findings. `PACK-A-BRIEF.md`: the brief of round A, which defines the format, the truthfulness rules, how to judge a line, and the verdict letters S, P, U, M, T, C, X (read "THE FORMAT", "TRUTHFULNESS RULES", "HOW TO JUDGE A LINE" and "RULES FOR FINDINGS"). `DRAFTING-BRIEF.md`: the rules that the drafter was given (a sentence may not copy more than 12 consecutive words of a page; a check is at most 35 words before `Applies to:`, not counting the tag, counting `Ask:`). `SKILL.md`: the skill that carries the pack.

### The 7 changed lines and the findings that they answer

- `std-agt-06` (data-agents.md): Gemini, Low (the question asked only about "the instructions" and dropped the schema object descriptions that `Applies to` names). Id `B-G1`.
- `std-sem-04` (semantic-models.md): Grok, Low (the gate said "partitions in directLake mode", which a program can read as every partition; the page sets the mode on Direct Lake partitions). Id `B-K1`.
- `note-eng-2` (data-engineering.md): Grok, Medium (the note said that the pages give no rule for dividing settings between the environment and `%%configure`, and "Configuration hierarchy" gives one). Id `B-K2`.
- `std-cap-12` (capacity-and-cost.md): Grok, Medium (the line left out that many interactive operations, such as a SQL query, are also considered background and might be rejected). Id `B-K3`.
- `std-cap-13` (capacity-and-cost.md): Grok, Low (the line left out that the page says first to make sure that the capacity is not in use). Id `B-K4`.
- `std-olk-12` (onelake-security.md): GPT, Medium (the line did not state the owner identity of Direct Lake over SQL, which the page puts in the same exception as the delegated SQL analytics endpoint). Id `B-P1`.
- `note-olk-4` (onelake-security.md): GPT, Low (the note described the older TLS check and the Fundamentals page without citing them). Its fix added the row `Fundamentals` to the table of sources, cites it in the note, names `std-sec-11`, and the header of the file now says that one note sets the data security page beside the Fundamentals page. Id `B-P2`.

### Your task (everyone: the same task)

1. One row for EVERY changed line, in the exact format `id | verdict | quote | reason` (the ids of the lines, `std-agt-06` and so on; one line each, with the vertical bars): open the cited section of the cited page; the quote is at most 12 words, copied VERBATIM from the cited section of the cited page, and a program looks it up in that section; the verdict is one of S, P, U, M, T, C, X. For `note-olk-4` also say whether the table of sources and the header of `onelake-security.md` are true after the change (give a row with the id `header-olk` and a quote from the page that the header's new clause rests on).
2. One closure row for EVERY finding above, in the format `finding-id | verdict | quote | reason` with the verdict F (fixed: the new text does what the finding asked, and is itself supported by the page), P (partly), N (not fixed), R (the fix made something worse: a new unsupported claim, a lost condition, a conflict with a neighbouring line, a tag that is wrong, a sentence over 35 words) or J (the drafter did not take part of a suggestion and that is right: say which page text shows it); the quote is at most 12 words copied VERBATIM from the NEW line in `pack\`.
3. `FINDINGS` (F1, F2, ... with severity High, Medium or Low, the id of the line, a quote, and a suggested replacement line in the same format, at most 35 words in the sentence), then `CHECKED AND FINE` (the number of rows S or F, and a one-line statement of what you did NOT check).

Look hard for: a number, a name or a condition that its section does not hold; a conflict with a neighbouring line or with the older pack (a note that names an older id must name the right one); a lost hedge ("can", "might", "recommended"); a tag that is wrong after the change; a line that now says what the page says only about one case as if it held for all. Return the whole report inline in your final message, at most 3500 words. Do not rely on writing files. Edit nothing outside your scratch folder; install nothing; sign in nowhere; the only network use is read-only fetches of the cited public pages.
