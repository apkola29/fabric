# Drafting brief: the reference pack of the `factory-standards` skill

You are a drafting agent. Write a small reference pack that condenses Microsoft's current guidance for Fabric workloads into checks that an agent can apply to a proposed change or to a review. A second model family will then check every line against the source text, so write only what the sources support.

## Why the pack exists

The project is a "code factory": a requirement for a Fabric workspace that is backed up in Git comes in, agents plan and implement it on a branch, other agents verify it, and a person approves a draft pull request. The agents that plan, write tests, implement and verify run in a sandbox **with no network**. They cannot read Microsoft Learn while they work. So the standards they should apply have to be in the repository, in a form they can use, with the source of each point and the date of the page.

The factory does **not** implement security, permission, network, sensitivity-label or tenant-setting changes in this version: a change like that is refused and escalated to a person. For those topics the pack's checks are "flag it, and say which guidance applies", never "do it". Mark each such check with the tag `[flag]`.

## Inputs (the only source of truth)

16 pages from learn.microsoft.com were downloaded and converted to text, one file per page, in `%TEMP%\fa-frameworks\`. Each file starts with `SOURCE:` (the URL) and `MS.DATE:` (the date that Microsoft gives for the last update). Read those files. Do not write from memory. You may fetch the same pages live from learn.microsoft.com (read only) to double check one point; use no other site.

Files: the six Well-Architected pages for Fabric workloads (overview, reliability, security, cost optimization, operational excellence, performance efficiency), Fabric security fundamentals, Security in Microsoft Fabric, the Azure security baseline for Fabric, best practices for lifecycle management in Fabric (CI/CD), the Fabric CI/CD concepts and best practices page (very large, about 150,000 characters: read its headings first and use only the sections you need), Fabric governance in a unified data platform (Cloud Adoption Framework), the Fabric adoption roadmap governance page, Choose a Microsoft Fabric deployment pattern, Greenfield lakehouse on Microsoft Fabric, and the medallion lakehouse architecture page.

## Outputs

Write into `%TEMP%\fa-standards-draft\` (create it). Five files, nothing else, nothing outside that folder:

1. `well-architected.md`: the five pillars applied to Fabric workloads (reliability, security, cost optimization, operational excellence, performance efficiency), from the six Well-Architected pages.
2. `security-and-governance.md`: from Fabric security fundamentals, Security in Microsoft Fabric, the Azure security baseline for Fabric, the Cloud Adoption Framework governance page and the adoption roadmap governance page. Identity and access, workspace and item boundaries, network, data protection, auditing and logging, governance and ownership.
3. `delivery-and-lifecycle.md`: from the two CI/CD pages. Git integration, branching and workspace layout, environments, deployment pipelines, what to parameterize, what not to put in a branch, testing and release.
4. `architecture-patterns.md`: from the deployment patterns page, the greenfield lakehouse page and the medallion page. Layering, where each kind of item belongs, choosing between item types, workspace and capacity layout.
5. `DRAFT-NOTES.md`: see "Notes" below.

## Format of each reference file

```
# <Title>

<Two or three lines: what this file is for, and what it does not do (it guides, it never authorizes a change).>

## Sources

| Label | Page | Updated | Retrieved |
|---|---|---|---|
| <short label you use below> | <full URL> | <MS.DATE as yyyy-mm-dd> | 2026-11-01 |

## <Topic heading>

- `std-<area>-<nn>` <the check, in one sentence> Applies to: <what a change touches>. Source: <label>, "<section heading of the page>".
```

Rules for the checks:

- Ids are lower-case, `std-` then an area (`rel`, `sec`, `cost`, `ops`, `perf`, `gov`, `del`, `arc`) then two digits, unique across all four files (`std-rel-01`, `std-rel-02`, ...). Do not use any other id style.
- One sentence, at most 35 words, in the imperative or as a question. It must be something that a reader can decide by looking at a proposed change, the item definitions in the branch, or the pull request description. If it needs knowledge of the tenant, begin with "Ask:".
- End the sentence with one tag where it helps: `[gate]` when a deterministic check could verify it (for example, a name pattern or a missing setting in an item definition), `[review]` when it needs a reviewer's judgement, `[flag]` for security, permission, network, label and tenant-setting topics (the factory only flags these).
- "Applies to" names the kind of change (for example: a new notebook, a pipeline schedule, a semantic model, a lakehouse, a workspace layout, a deployment pipeline stage). Keep it short.
- Cite the page and the section heading that states the point. If the point comes from a table or a list inside a section, cite the section.
- At most 10 checks per topic and about 60 to 80 checks in all. Quality over quantity. Leave out generic cloud advice that is not specific to data platforms or Fabric, product marketing, and anything that a pull request could not change or should not decide (for example, buying capacity). Capacity and cost checks that a change can influence (schedule frequency, refresh settings, Spark pool or environment settings, what is materialized and how often) are in scope.
- Keep the nuance of the source: conditions ("when ... use ..."), tradeoffs, and states such as preview or retiring. If a page says that a baseline is a starting point and not a checklist, say so in the file's header lines. The Azure security baseline page says it is based on version 1.0 of the Microsoft cloud security benchmark and may be outdated: say that in `security-and-governance.md`.
- If two pages say different things, say so in a line starting `Note:` under the topic, and cite both.

## Truthfulness rules (a reviewer will check each line against the page)

1. Paraphrase. Never copy more than 12 consecutive words from a page.
2. Never add a number, a name, a limit, a feature, a setting or a recommendation that is not in the source text. Copy numbers exactly. If you are unsure, leave the point out and list it in the notes as UNVERIFIED.
3. Do not generalize beyond the text: if a page says "workspaces map to teams, projects or environments", do not turn it into "always use one workspace per project".
4. Do not merge two pages into one claim unless each page supports its part, and then cite both.

## Exposure rules (the repository is public and a validator scans every file)

- Plain ASCII: straight quotes, a hyphen or a comma instead of a dash, no arrows, no symbols.
- No four numbers separated by dots (the validator reads that as an IP address), no GUIDs, nothing that looks like an e-mail address, no file system path, no token, no person's name, no tenant, workspace or item identifier.
- The validator treats upper-case family letters followed by digits or a hyphen and digits as references to design identifiers (for example `K9`, `S3`, `C2`, `HR-4`, `FR-01`, `PS-2`). Do not write words of that shape. Product names with digits that are written in another way are fine.
- Do not claim or imply a certification, compliance status or guarantee that the pages do not state.

## Notes (`DRAFT-NOTES.md`)

For each reference file: the sections that you used per page; the sections you skipped, with a few words of reason; every point that you could not phrase without copying or that you could not fully support (mark it UNVERIFIED and say what is missing); every contradiction or outdated signal that you saw. At the end, the SHA-256 of each of the 16 source files (use `Get-FileHash -Algorithm SHA256` or Python), so that the checker can confirm that it reads the same text.

## Limits

Touch nothing outside `%TEMP%\fa-standards-draft\` and scratch files named `%TEMP%\fa-standards-*`. No installs, no sign-in, no network except read-only fetches of learn.microsoft.com pages. Do not edit the project. When done, reply in at most 400 words: the files and their line counts, the number of checks per file, and anything the checker should look at first.
