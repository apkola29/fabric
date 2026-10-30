# Verification round 3: GPT 6.1 Sol

Lens: public exposure, scripts and CI, and a cold read. The reviewer had not seen rounds 1 or 2. It read a frozen copy of the published commit `c8c18b4198` (52 files), ran the validator and the fact checker's offline tests, and replied inline. This is the reply condensed. Quotes that would repeat wording reworded in this round are described instead of quoted. The disposition of each finding is in [round-3-findings.md](round-3-findings.md).

Summary from the reviewer: all 52 files were pattern-scanned, including the raw research and the reviews. No actual credentials, tenant GUIDs or private personal data were found.

## Findings

| ID | Part | Severity | Where | Evidence | Why it matters | Concrete fix |
|---|---|---|---|---|---|---|
| R3-C-1 | Scripts | High, blocking | `scripts/validate_docs.py`, the reader of the private list | The list is read as plain UTF-8 | Reproduced by the reviewer: a private term behind a byte-order mark matches nothing, and a list that holds only a comment behind a byte-order mark satisfies `--require-denylist`. Both returned zero errors, while the same term without the mark produced 10. This defeats the fail-closed safeguard | Read with a decoder that drops the mark, normalise before filtering comments and counting terms, and add both regression tests |
| R3-C-2 | Scripts | High, blocking | `scripts/sync_to_github.ps1` (fold, mirror) and `scripts/validate_docs.py` (which files are read) | A soft reset of earlier commits, an exclusion of bytecode from the mirror, and a read of known text suffixes only | The published tree is not necessarily the scanned tree. Excluded bytecode that is already tracked can survive the fold and the mirror, and a new file with another extension, such as a CSV, is copied and staged without a private-term scan. The remote check runs only after publication | Before committing or pushing, enumerate the prospective Git tree, reject private and cache paths and unsupported files, and validate every permitted file's actual content |
| R3-C-3 | Exposure and cold read | High, blocking | The README, the research index, the brief, the archive, and three raw reports | Descriptions of the private surveys, of the installed tool inventory and of an older copy of a repository | Provenance of private surveys, the installed inventory and session-specific tooling remain public, which contradicts the claim that the last non-public wording was removed | Remove the descriptions of the private surveys, and re-ground the retained technical statements in identified public commits and documentation instead of the author's installation |
| R3-C-4 | Scripts | High, blocking | `scripts/sync_to_github.ps1`, the origin check | An anchored expression that ends with the repository name | It still accepts HTTPS and SSH addresses on hosts other than GitHub whose path ends in the repository, so a publication could reach the wrong server before the remote check notices | Parse the address and allow only the canonical GitHub HTTPS and SSH forms of the exact owner and repository, and reject embedded credentials |
| R3-C-5 | Scripts | Medium | `scripts/verify_facts.py`, the file, repository and npm checks | A pattern that is not found returns PASS | Reproduced: an HTTP 200 with an empty body passes an absence claim, `{}` passes a repository check, and an unversioned npm check accepts missing metadata. Handling error statuses alone does not make the evidence valid | Require the expected structure and meaningful content before a claim is evaluated, treat empty or invalid evidence as UNREACHABLE, and add regression tests |
| R3-C-6 | Scripts and cold read | Medium | `scripts/verify_facts.py`, the run loop | Any exception is reported as FAIL | Reproduced: malformed JSON from a source becomes FAIL, so a transient truncated answer declares a claim wrong. That contradicts the README and workflow statement that only wrong claims fail the weekly run | Separate unusable answers from invalid fact definitions and programming errors, and report unusable answers as UNREACHABLE |

## Latest fixes checked

- **Fold-away of earlier commits:** not closed. Excluded tracked content can survive, the final publication tree is not comprehensively validated, and `-NoPush` still resets, mirrors and commits.
- **Location of the private list and the fail-closed check:** not closed. Discovery and the rejection of a missing, empty or unreadable list work, and the byte-order mark bypasses them.
- **Handling of HTTP errors:** closed with a reservation. Rate limits and server errors are handled, and empty successful answers and malformed payloads are not.
- **Workflow changes:** closed. The two copies are byte-identical with LF endings, the Monday schedule, the pinned runner, the read-only permissions and the summary before the failure are correct.
- **Counts in the log:** closed. 85 tests are 44 plus 41, there are 44 facts, and both findings tables recompute, including the per-reviewer decisions and severity totals.

## Checked and sound

- The exposure hits that remain are acceptable: public bot addresses, public repository handles, vendor and product references, generic capacity requirements, path templates and constructed test fixtures. None is a tenant inventory or a credential.
- The reading order, the glossary and the referenced sections can be followed, and the line between the proposed factory and the existing tooling is clear.
- The baseline validator reports no errors or warnings, and all 41 offline fact-checker tests passed.
- Explicit SHA refspecs, the rejection of merge commits, and a read-only pull-request checkout with credentials disabled are sound safeguards.

## Could not verify

- The contents and completeness of the private list, which is not in the copy.
- The 44 validator mutation tests by running them, because they copy folders. They were read and counted.
- Publishing and destructive Git edge cases against a real clone, and historical claims about model routing.
- Live tenant behaviour, rendering, and remote byte equality independent of the assurance supplied with the copy.

Verdict from the reviewer: safe after fixes, with 0 critical, 4 high and 2 medium.
