# Verification log

Each loop is a round of checking, then fixes, then a sync to GitHub with a proof that GitHub holds what is on disk. This file is the record. Dates are 2026-10-30, US Central time.

## Loop 0: before the first publication

The repository is public, so the first question was what must not be published.

| Check | Method | Result |
|---|---|---|
| Local paths, addresses, tokens, GUIDs, internal hosts | Pattern scan of every file (`scripts/validate_docs.py`) | Local machine paths in two raw reports. Reworded. |
| Terms that must never appear | A private list of terms, kept outside the repository | Hits in two raw reports. Reworded or removed. Zero hits after. |
| Claims a public source could not confirm | Compared with the public `microsoft/skills-for-fabric` tree on 2026-10-30: it has no `tests/`, `docs/` or `build/` directory, no quality checker and no evaluation workflow. Only `issue-routing.yml` exists under `.github/workflows/` | Statements about how the skills are validated could not be confirmed from the public tree. They were removed, and the public facts above were recorded with a pattern the factory has to build. |
| Personal and tenant detail a pattern cannot see | Read `o1` and the brief in full | A named individual and tenant-specific capacity details were removed. Round 1 found one more tenant sentence and a local install path, now removed (loop 2). |
| Consistency of the document set | The validator: tables, section numbering, identifiers, coverage, counts, links, diagrams | 3 defects fixed: the design ended with stray blank lines, one results file had no final newline, and the design header named two files without their folder. |
| Does the validator catch defects | 32 mutation tests inject one known defect each into a copy of the folder | All 32 are caught. Writing them found one gap in the validator itself (an unclosed code fence at the end of a file looked like a closing fence). Fixed. |
| Concrete claims against public sources | `scripts/verify_facts.py` over 24 claims | 23 confirmed, 1 drift (a newer alpha of the data-agent SDK exists), 0 wrong, 2 unreachable (see below). |

Confirmed against their sources: `fabric-cicd` 1.4.0 and `ms-fabric-cli` 1.8.0 are the current releases; the skills plugin is at 0.3.20; `actions/checkout` v7.0.1 resolves to the commit pinned in the CI workflow; the `tj-actions/changed-files` advisory is CVE-2025-30066; "Comment and Control" is arXiv 2605.11229; variable libraries list no semantic-model or report consumers; the Fabric Delete Item and Delete Recoverable Item pages say what the design says (the two pages disagree on the role needed to purge a soft-deleted item, which the design records and spike S2 tests); Azure Table batches are atomic within one partition, up to 100 entities and 4 MiB; Entra allows 20 federated credentials and does no wildcard matching; the gh-aw defaults are as described.

Unreachable from the machine that ran the checks: the two npm packages (the network blocks the npm registry). The GitHub Action `fabric-automation facts` runs the same checks on a hosted runner (see loop 1).

Published as commit `2e1ca1b814`. `scripts/verify_remote.py` compared the Git blob hash of every file with the one GitHub holds: 40 files plus the 2 workflow files were identical.

## Loop 1: the first clean-room run

| Check | Method | Result |
|---|---|---|
| Do the documents and the validator work on a clean Linux checkout | The GitHub Action `fabric-automation validate` on a hosted runner | The baseline test passed, so the documents validate on Linux. **One test failed**: `test_mixed_line_endings` assumed files have CRLF endings, but on Linux `.gitattributes` makes them LF, so appending an LF line made no mix. The test was wrong, not the validator. It now builds its own mixed endings. Confirmed by running the validator and all 33 tests on a local copy converted to LF. |
| The claims that this network could not reach | The GitHub Action `fabric-automation facts` on a hosted runner | 25 confirmed, 1 drift, 0 wrong, 0 unreachable. Both npm packages are published: `@microsoft/powerbi-modeling-mcp` at 1.0.0 and `@microsoft/powerbi-report-authoring-cli` at 0.5.0. The one drift is `fabric-data-agent-sdk`: the research reports cite 0.1.33a0, which exists, and 0.1.34a0 is now the latest (still an alpha). No design text cites the version, so nothing needed a change. The raw reports keep the value that was true when they were written. |
| Open item 9 of the digest ("npm publication could not be verified") | The npm check above | Resolved in part. The report authoring CLI is published, at a pre-1.0 version. The digest and the design were updated. Installability and headless use in the sandbox remain spike work (S3, S10). |

## Loop 2: verification round 1 on the published design

Reviewed commit: `2ae0c95302`. Three reviewers from three model families each read a frozen copy with a different lens. The findings and what was done with each are in [round-1-findings.md](round-1-findings.md), and the three replies are in [round-1-gpt.md](round-1-gpt.md), [round-1-gemini.md](round-1-gemini.md) and [round-1-grok.md](round-1-grok.md).

| Check | Method | Result |
|---|---|---|
| Do the diagrams render on GitHub | Opened the design on github.com in a browser | Both rendered, but the zone diagram was unreadable at page width (about 3,500 px wide, so the text shrank to a few pixels). Redrawn at zone level with every component and flow kept. It now renders at about 94% of its natural width |
| Consistency and logic | GPT 6.1 Sol over the whole set | 7 findings. All accepted. The one rated Critical was re-rated High, because a merge is a human act and T2 is stage 2 only |
| Platform facts against live sources | Gemini 4 Argon checked 30 claims against Learn, GitHub documentation and package registries | 22 confirmed, 4 partly, 3 wrong or outdated, 1 unverifiable. The author re-checked every non-confirmed claim against the same primary source. One was right and mattered: the strict-binding flag of `fabric-cicd` is on `main` and not in release 1.4.0. One was partly wrong: the availability matrix marks outbound access protection Preview for reports, semantic models and data agents, not GA, and two Learn pages disagree about reports. The rest were right |
| Public exposure, scripts, cold read | Grok 4.7 scanned all 42 files and reviewed the scripts and CI | No credentials, tokens, GUIDs or personal data. Two High: the log and one README still described material that had been removed, and the publish script carried on without the private term list. Both fixed. One claim was checked and was false for GitHub: the workflow files there have no CR bytes, and the CRLF came from how the review copy was built |
| Does the checking itself work | Ran the whole test suite after the edits | Two mutation tests had stopped injecting their defect after the diagram was redrawn, and a new test tripped the validator on its own source. Both fixed, and the test helper now fails when a mutation changes nothing |
| Can the fact checker fail | 18 new offline tests with a fake network, and two in-memory mutations of the checker | Both mutations were caught (4 and 3 failing tests) |
| Concrete claims against public sources | `scripts/verify_facts.py`, now 38 claims | Run here: 35 confirmed, 1 drift (the data-agent SDK alpha), 0 wrong, 2 unreachable (the npm registry is blocked on this network). The hosted runner reaches npm |

What changed: the run lifecycle (exclusive guards, the exits that were missing, one terminal-state table), the limit of the approval-policy check and its bound, the budget wording, the `fabric-cicd` binding, outbound access protection, the OIDC subject, the capacity role, two OneLake and Git statements, the golden-set rule, the reviewer preview, the evidence-store test, the removal of the last non-public wording and a local install path, a reading order and a table of terms, an index of the reviews, the publish script (fails closed, validates the whole push range, pushes by SHA), the validator (`--require-denylist`, `--scan-file`, a local-install-path pattern), and 12 new fact checks. The suite is now 57 tests: 39 for the validator (the clean baseline, 32 injected defects, and 6 for the options that make publication fail closed) and 18 for the fact checker.

