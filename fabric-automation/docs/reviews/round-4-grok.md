# Verification round 4: Grok 4.7

Lens: the verification records, the public exposure of the folder, and a cold read (a narrow closure check). The reviewer had not seen an earlier round. It read a frozen copy of the published commit `6ca7594335` and the diff of round 3, ran the suite and the newest ten fact checks, and replied inline. This is the reply condensed; line numbers refer to that commit. The disposition of each finding is in [round-4-findings.md](round-4-findings.md).

## Findings

| ID | Severity | Where | Evidence | Why it matters | Concrete fix |
|---|---|---|---|---|---|
| R4-C-1 | Medium | `docs/reviews/verification-log.md`, the last row of Loop 4 | "now 56 claims" followed by a pointer to a final entry. No result line and no publish commit follow | A reader treats the log as the proof, and the row points at a result that was never written | Add the counts and the commit that holds this tree |
| R4-C-2 | Medium | `docs/reviews/round-3-findings.md` (R3-C-6) | "19 tests are new". The reviewer counted 22 test definitions added in `test_verify_facts.py` and 1 removed, which it read as a net of 21 | A reader reconciling the suite with the disposition will not get 19 | Say 22 added and 1 replaced |
| R4-C-3 | Medium | `docs/reviews/round-3-findings.md` (R3-C-4), `scripts/sync_to_github.ps1`, `scripts/test_sync_script.py` | "only the two canonical GitHub forms" and "2 run the shipped function against 19 addresses". One test uses the 19 addresses, and the accepted set holds 7 strings including one in the `ssh://` form | "Only two" reads as if the `ssh://` form is refused, and the log's "7 accepted, 12 refused" is the accurate count | Say one test, 7 accepted and 12 refused, and name the `ssh://` form |
| R4-C-4 | Medium | `scripts/facts.json`, four entries | All ten newest facts passed. Four claims are wider than their patterns: the draft entry adds that the failed check is the control, the skill entry adds that the REST reference does not list the code, the webhook entry says "a team edited" and "both need" the permission while its patterns hold "granted access" and one permission phrase, and the credit-guard entry says later requests are refused while its pattern is two strings about 21,000 characters apart | A PASS is read as source proof of the whole sentence, including clauses that the pattern cannot fail | Cut each claim to the clause the pattern checks, or add a pattern for the extra clause |
| R4-C-5 | Medium | `README.md` (status line and the production paragraph) | The status says "corrected after a first verification round", and the paragraph ends at "a second three-model pass". The brief and the reviews index record three rounds | The first thing a newcomer reads understates the trail. The truth is one click away, so this is not a false result | One status sentence: how many verification rounds, where the record is, that nothing is built, and that the Phase 0 spikes are open |
| R4-C-6 | Low | `docs/reviews/round-3-findings.md` (R3-C-3) against `docs/00-brief.md` | The disposition says the documents "now say only that two local surveys are not published", and the brief still says two local survey agents were relaunched and that the surveys were kept out | No survey contents are exposed, and the word "only" is tighter than the brief | Trim the brief to the README wording, or correct the cell |

## Stated against recomputed

- 23 findings (6 + 11 + 6), 20 accepted, 3 modified and 0 with no change: matches. The modified ones are R3-A-4, R3-B-2 and R3-C-3.
- Author severities 4 High, 11 Medium and 8 Low, and the per-reviewer splits: match.
- Grok's 24 claims, 13 confirmed, 6 partly, 2 wrong and 3 unverifiable: match its record and Loop 4. Gemini's "3 closed, 3 with a reservation": matches.
- 132 tests, 55 + 60 + 11 + 6: matches the loader and the definitions. The suite ran 132 tests and passed.
- 56 facts and 56 files: match.
- The newest ten facts all passed.

## Checked and sound

Ten dispositions were matched with the text or the code of the snapshot, with file and line: R3-A-1, R3-A-2, R3-A-6, R3-B-1, R3-B-2, R3-B-5, R3-B-6, R3-B-7, R3-C-1 and R3-C-2. Three of the newest facts also match their patterns. The README says plainly that nothing is built and nothing has been tested on a tenant.

Exposure scan of all 56 files and the two workflow files, with patterns for GUIDs, token prefixes, user paths, secret assignments and internal host suffixes, and a keyword pass for survey, tenant, inventory and personal names: no GUIDs, tokens, user paths or secret assignments. The address hits were public (`git@github.com` and a public bot address), and the Microsoft hits were public documentation. The survey text is "not published" or an evidence identifier, with no survey contents. One raw report still says "this host" and "one inventory read" and states that tenant, workspace and item identifiers were removed. None were found.

## Could not verify

- The sentence in Loop 4 that mutations back to the old behaviour fail the new tests. The tests exist, and the mutations were not re-applied.
- A full run of all 56 facts (only the last 10 were run), and whether GitHub holds this tree, because Loop 4 recorded no commit and the remote check was not run.
- The private term list, which is absent on purpose.

Three confusing places for a newcomer who starts at the README: the status line stops at the first verification round (R4-C-5), Loop 4 sends the reader to a final entry that is not there (R4-C-1), and the reviews index describes round 3 as a review without saying that the open work is the spike list at the end of the findings file and not unfinished document fixes.

Verdict from the reviewer: 0 critical, 0 high, 5 medium, 1 low.
