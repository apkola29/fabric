# Verification round 6: Grok 4.7

Lens: the fact list (the 6 new entries and the 25 entries whose patterns or definition changed in round 5), the design edits of round 5 against primary sources, the records, the public exposure of the folder and a cold read (slice C of a closure check, with the slices handed to different families than in round 5). The reviewer had not seen an earlier round. It read a frozen copy of the published commit `f6ed0fc4de` and the diff of round 5, fetched the sources itself, and replied inline. This is the reply condensed; locations refer to that commit. The disposition of each finding is in [round-6-findings.md](round-6-findings.md).

## Findings

| ID | Severity | Where | Evidence | Why it matters | Concrete fix |
|---|---|---|---|---|---|
| R6-C-1 | Medium | `scripts/facts.json`, `page-entra-federated-credential-limits` | The claim says that the subject setting must exactly match the workflow configuration. The pattern is "subject setting values must exactly match the configuration", and the source sentence ends "on the GitHub workflow configuration". The word "workflow" is in no pattern | A PASS survives if the page keeps "exactly match the configuration" and drops the word | Put "GitHub workflow configuration" into the subject pattern |
| R6-C-2 | Medium | `scripts/facts.json`, `gh-aw-ai-credit-caps` | The claim says that AIC values are computed on a best-effort basis. The pattern is only "computed on a best-effort basis", and the live note reads "AIC values are computed on a best-effort basis using pricing data sourced from the models.dev catalog" | If that note is rewritten about something else, or removed while another best-effort sentence remains, the check still passes | Require the whole opening of the note |
| R6-C-3 | Medium | `scripts/facts.json`, `page-table-entity-group-transactions` | The claim says that an entity group transaction has its operations processed atomically. "processed atomically" matches twice, both times about change sets of a batch, and not next to the words "entity group" | Atomicity is not what the pattern proves | Bound the phrase to the sentence about the change set, or drop the clause |
| R6-C-4 | Medium | `scripts/facts.json`, `page-copilot-budget-stop-setting` | The claim says that an organization budget enforces a hard stop only if the stop setting is enabled. The row pattern ends at the stop setting and does not include the column header "Hard stop?" | The reading "hard stop" for that budget can become false while every predicate stays true | Include the header in the row pattern, or stop saying "hard stop" for that budget |
| R6-C-5 | Low | `scripts/facts.json`, `page-required-check-app-source` | The claim ends "to be the source of a required check". The pattern is only the three conditions, and the page says just before them that one can select an app as the expected source of status updates | The purpose clause is not checked | Add that sentence to the pattern, or cut the clause |
| R6-C-6 | Low | `README.md`, the Reviews row of the table | The cell says "the closure check", while the status and the reviews index describe the design closure and two later closure checks in slices | A newcomer can think that there was one closure | Say "the design closure and the later verification rounds" |

## Design edits and the firewall entries

No defect in the design edits. In section 3.7 lakehouses, notebooks and pipelines have a check mark in the last column (outbound access protection), reports, semantic models and data agents are Preview, and ontologies have a dash that the page does not define. In 3.3 the body parameters of Update a pull request are title, body, state, base and `maintainer_can_modify`, and GraphQL has both mutations. In 3.8 the skill says `404 GitProviderResourceNotFound` and the Connect reference lists exactly five other codes. In 3.5 and 3.6 both webhook events need at least read-level access for the Members organization permission. GitHub's OpenAPI description has the five webhook operations, each once.

The five firewall regexes bind to live code and not to comments or dead branches: the refusals in the enclave budget module, the hard-cap constant and the block-state function of the credits guard, and the returned descriptor of the common guard checks (HTTP 403, the event name and `maxExceeded`). The two control patterns are in the files that were meant, and a raw 404 body would match neither.

## Entries checked

All 31 entries (6 new, 25 changed) matched the live source. Five were wider than their check (R6-C-1 to R6-C-5), and the rest were supported and no wider. The 11 claim-only cuts were scanned and the 21 unchanged entries held no clear case of the same defect.

## Stated against recomputed

No mismatch. The reviewer matched the 24 findings with 22 accepted and 2 modified, the author severities 1, 12 and 11, the reviewer severities 3, 17 and 4, the reply verdicts, the Loop 6 splits, the 230 tests as 75 + 87 + 27 + 6 + 35, the 63 claims, the 65 text files, the 4 entries removed and 6 added, the 36 changed (25 and 11), the 45 page and file checks of the earlier list, and the hosted run on `f6ed0fc4de` (230 tests, 35 skipped).

## Exposure and cold read

No GUIDs, token prefixes, secret assignments, internal hosts, invisible characters or real user-profile paths in the 65 files or in the delta. The address hits are public (the allow-listed ones and a research citation). The path-like hits are placeholders, scanner expressions and a public news address. The non-ASCII characters are arrows, check marks and one middle dot. The cold read found only R6-C-6.

## Could not verify

The mutation runs of the author (not repeated), the local split of the fact run in the log, the date shown on the matrix page, and the caller that turns the credits descriptor into the HTTP response (the descriptor itself is live code).

Verdict from the reviewer: 0 high, 4 medium, 2 low.
