# Verification log

Each loop is a round of checking, then fixes, then a sync to GitHub with a proof that GitHub holds what is on disk. This file is the record. Dates are 2026-10-30, US Central time.

## Loop 0: before the first publication

The repository is public, so the first question was what must not be published.

| Check | Method | Result |
|---|---|---|
| Local paths, addresses, tokens, GUIDs, internal hosts | Pattern scan of every file (`scripts/validate_docs.py`) | Local machine paths in two raw reports. Reworded. |
| Terms that must never appear | A private list of 21 terms, kept outside the repository, derived from the two local surveys | Hits in two raw reports (details of a non-public mirror of the skills repository). Reworded or removed. Zero hits after. |
| Claims that came from non-public material | Compared with the public `microsoft/skills-for-fabric` tree on 2026-10-30: it has no `tests/`, `docs/` or `build/` directory, no quality checker and no evaluation workflow. Only `issue-routing.yml` exists under `.github/workflows/` | The research had recorded a skills test regime that exists only in the non-public mirror. It was rewritten as a pattern the factory has to build, and the public facts above were recorded instead. |
| Personal and tenant detail a pattern cannot see | Read `o1` and the brief in full | A named individual (a skill owner field) and the size and state of one capacity were removed. |
| Consistency of the document set | The validator: tables, section numbering, identifiers, coverage, counts, links, diagrams | 3 defects fixed: the design ended with stray blank lines, one results file had no final newline, and the design header named two files without their folder. |
| Does the validator catch defects | 32 mutation tests inject one known defect each into a copy of the folder | All 32 are caught. Writing them found one gap in the validator itself (an unclosed code fence at the end of a file looked like a closing fence). Fixed. |
| Concrete claims against public sources | `scripts/verify_facts.py` over 24 claims | 23 confirmed, 1 drift (a newer alpha of the data-agent SDK exists), 0 wrong, 2 unreachable (see below). |

Confirmed against their sources: `fabric-cicd` 1.4.0 and `ms-fabric-cli` 1.8.0 are the current releases; the skills plugin is at 0.3.20; `actions/checkout` v7.0.1 resolves to the commit pinned in the CI workflow; the `tj-actions/changed-files` advisory is CVE-2025-30066; "Comment and Control" is arXiv 2605.11229; variable libraries list no semantic-model or report consumers; the Fabric Delete Item and Delete Recoverable Item pages say what the design says (the two pages disagree on the role needed to purge a soft-deleted item, which the design records and spike S2 tests); Azure Table batches are atomic within one partition, up to 100 entities and 4 MiB; Entra allows 20 federated credentials and does no wildcard matching; the gh-aw defaults are as described.

Unreachable from the machine that ran the checks: the two npm packages (the network blocks the npm registry). The GitHub Action `fabric-automation facts` runs the same checks on a hosted runner.
