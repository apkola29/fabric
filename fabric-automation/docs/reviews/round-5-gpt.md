# Verification round 5: GPT 6.1 Sol

Lens: the fact list, the design edits of round 4 against primary sources, the records, the public exposure of the folder and a cold read (slice C of a closure check). The reviewer had not seen an earlier round. It read a frozen copy of the published commit `c7c690a0eb` and the diff of round 4, fetched the sources itself, and replied inline. This is the reply condensed; locations refer to that commit. The disposition of each finding is in [round-5-findings.md](round-5-findings.md).

## Findings

| ID | Severity | Where | Evidence | Why it matters | Concrete fix |
|---|---|---|---|---|---|
| R5-C-1 | Medium | `scripts/facts.json`, the membership and team webhook entries | The membership check looks only for the word "Members" inside its segment, and on the source page that also matches "team memberships" and "Team members". Removing the permission sentence in memory leaves every predicate true. The team entry likewise checks only that keyword | The permission requirement can disappear while the claim passes | Match the whole, event-scoped sentence that requires read-level access for the Members organization permission |
| R5-C-2 | Medium | `scripts/facts.json` (the two webhook schema entries), `docs/reviews/round-4-findings.md` | Both checks establish only that a path exists, and their provenance wording, schemas "generated from GitHub's payloads", is overstated: the Octokit README calls them hand-crafted, "woefully out of date and not maintained anymore", with a broken update process. The actions themselves are right, because GitHub's current OpenAPI description also lists `removed` and `edited` | Neither the schema contents nor the claimed provenance is checked | Drop the provenance wording from the claims and the record, and prefer the official OpenAPI description with its action names asserted |
| R5-C-3 | Medium | `scripts/facts.json`, the Git connect error-code entry | The claim says five codes and none for a missing folder. The predicates require five names and exclude only `GitProviderResourceNotFound`, so a sixth, differently named error would leave them all true | The count and the absence claim can become false unnoticed | State the five names and the absence of that one code, or check the whole list and its count |
| R5-C-4 | Medium | `scripts/facts.json`, the request and token ceiling entry and the credit guard entry | The first matches only a pair of symbol names. The second is a regex that spans 21,349 characters, and removing the absolute-cap enforcement and the clamps in memory still leaves its four anchors matching | The source supports the claims today, but the predicates do not establish enforcement, an absolute ceiling or refusal of later requests | Narrow the sentences to the declarations that are checked, or add checks for the enforcement |
| R5-C-5 | Medium | `scripts/facts.json`, the stable frontmatter absence entry and the REST draft entry | The frontmatter entry tests the absence of four literal spellings, not of any description of the ceilings. The REST entry tests only the body-parameter segment while its claim says no draft parameter | Both negative claims are broader than what is checked | Say "these four identifiers do not occur" and "the documented body parameters contain no draft parameter" |
| R5-C-6 | Medium | `scripts/facts.json`, the Git supported-items entry | The semantic-model pattern matches the text "semantic models hosted in MyWorkspace ) (preview)" inside the Report exception, not the Semantic model bullet. Nothing checks the preview tag of the Report bullet | A PASS does not establish two of the status claims | Check each bullet on its own, with its own preview marker |
| R5-C-7 | Medium | `scripts/facts.json`, the recoverable-item entries | The delete entry searches only "write permissions for the workspace", while its sentence adds that another page says Admin and that the two pages disagree. The retention entry checks the action title and the numbers, not a role requirement | The Admin and disagreement clauses can become false while both checks pass | Add a scoped check of the permission table, or cut the clauses |
| R5-C-8 | Medium | `scripts/facts.json`, five other entries | Four absent root paths do not establish that validation is not public. The word `wildcard` does not verify the sentence about flexible credentials. The architecture predicates omit the firewall. The Git predicates omit that a recycle-bin restore keeps the original ID. `engine: copilot` does not establish "default" | The same whole-sentence false PASS that round 4 set out to close | Split or cut each extra clause, or add a scoped predicate for it |
| R5-C-9 | Medium | `README.md` (status and the history paragraph) against `docs/reviews/README.md` | The README says all four rounds rotated the reviewers' roles, and the index says round 4 used slices instead of rotated lenses | The rewritten introduction contradicts the detailed record | Say that the earlier rounds rotated the lenses and round 4 split the closure work into slices |
| R5-C-10 | Low | `README.md` (checking this folder), the skip conditions of three test files | "Python 3 and nothing else" is enough to run the commands, but tests that need Git or PowerShell skip without them, and the behavioural tests also need Windows and robocopy | A newcomer can mistake a reduced-coverage green run for the full check | Separate what the commands need from what full coverage needs |
| R5-C-11 | Low | `docs/reviews/verification-log.md`, Loop 5 | Loop 5 ends with local results and descriptions of the changes. It names neither the published commit nor the two successful hosted runs | The publication proof that Loop 4 received is missing from the newest loop | Append the published commit, the hosted run IDs and their results |

## The eleven claims checked

All eleven sources were fetched independently.

| Claim | Assessment |
|---|---|
| `awf-proxy-request-and-token-ceilings` | Supported today, wider than its check of two symbol names (R5-C-4) |
| `awf-ai-credits-guard` | Supported today, wider than its loose cross-function regex (R5-C-4) |
| `page-draft-pr-cannot-merge` | Supported, appropriately bounded, not vacuous |
| `page-rest-update-pr-has-no-draft-parameter` | Supported today, the body-only check is narrower than the sentence (R5-C-5) |
| `skill-git-connect-missing-directory` | Supported as an attribution to the skill, bounded, not vacuous |
| `gh-aw-frontmatter-has-no-proxy-ceilings` | Supported today, absence of the concept is wider than absence of four names (R5-C-5) |
| `page-git-connect-error-codes` | Supported today, the count and the missing-folder statement exceed the check (R5-C-3) |
| `page-webhook-membership` | Supported today, the permission pattern has unrelated matches (R5-C-1) |
| `page-webhook-team` | Supported today, the permission requirement is reduced to one keyword (R5-C-1) |
| `webhook-schema-membership-removed`, `webhook-schema-team-edited` | The actions are supported, the provenance is overstated and the path-only check is narrower than the claim (R5-C-2) |

## Design edits

No defect in the edits that were asked about. The condition under which GitHub marks a bot's commit verified and the commitment of S11 agree. The five terminal states agree with the rule that every non-terminal state can be cancelled. The REST reference documents no draft conversion, and GraphQL has both mutations. The budget row is correctly qualified by section 3.14. GitHub's required-check documentation confirms `success`, `skipped` and `neutral` as passing and the same-name rule for a check and a status.

## Stated against recomputed

No mismatch among 29 numbers: 18 findings with 16 accepted and 2 modified, author severities 1 High, 6 Medium and 11 Low with every reviewer split, 164 test definitions (61 + 65 + 18 + 6 + 14), 61 claims, 61 text files, 19 changed files, and the historical figures (132 tests, 56 files and claims, 20 definitions added and 1 removed, 19 addresses with 7 accepted and 12 refused, 24 claims with 13, 6, 2 and 3, and 3 closed with 3 reservations). The two hosted runs, read with `gh run view`, show 164 tests with 15 skipped (the 14 publish-flow tests and the junction test) and 60 confirmed, 1 drift, 0 wrong and 0 unreachable, both on `c7c690a0eb`. Every one of the 18 dispositions has a matching edit in the delta.

## Exposure and cold read

All 61 files and the delta were scanned for credentials, GUIDs, tenant endpoints, internal host names, personal addresses and user-profile paths. None were found. The hits were public bot and source addresses, documented placeholders, scanner expressions and synthetic test fixtures. The 99 relative links resolved. The only confusions for a newcomer are R5-C-9 to R5-C-11.

## Could not verify

The local fact-run figures of earlier rounds, the private term list and its validation, the historical mutation runs (not repeated), and the tenant behaviour that is reserved for the Phase 0 spikes, which was not treated as a defect.

Verdict from the reviewer: not closed, 0 high, 9 medium, 2 low.
