# Verification round 5: Grok 4.7

Lens: the Python tooling that round 4 changed (slice B of a closure check): the commit check, the validator, the fact checker, the schema of the fact list and their tests. The reviewer had not seen an earlier round. It read a frozen copy of the published commit `c7c690a0eb` and the diff of round 4, ran the suite on a copy (164 tests, 2 skipped, as claimed), and mutated the safeguards one by one. This is the reply condensed; locations refer to that commit. The disposition of each finding is in [round-5-findings.md](round-5-findings.md).

## Findings

| ID | Severity | Where | Evidence | Why it matters | Concrete fix |
|---|---|---|---|---|---|
| R5-B-1 | High | `scripts/validate_docs.py`, the user-path leak pattern | The pattern is case-sensitive and needs a backslash after a capitalised folder name. A full run on a copy whose README held a Windows user-profile path in lower case, and another with forward slashes, reported no error. Mixed slashes, upper case, a lower-case application-data folder and a lower-case OneDrive tenant folder were all clean. A path with a capitalised folder name and forward slashes was caught only by the macOS rule | CI applies only these generic patterns. A real Windows path in another case or with other slashes is published as clean | Make the pattern case-insensitive, accept both slashes, and add tests |
| R5-B-2 | Medium | `scripts/verify_facts.py` (the file check and the HTTP wrapper) | An absence claim passes on any non-empty answer that lacks the pattern: a mocked sign-in page returned PASS. The wrapper follows redirects, and a local redirect to an unrelated page was returned as status 200, so a page claim against that address passed. Two entries use absence | A captive portal, a sign-in page or a redirect proves that a pattern is absent, and the weekly run stays green | Raise UNREACHABLE when the final host differs, and do not read "not found" as evidence unless the body is the file |
| R5-B-3 | Medium | `scripts/validate_docs.py`, the control-character check and the scan | A private term split by a zero-width space or a C1 control character was missed, and a Windows path written with a Cyrillic look-alike letter was missed. The control-character set is right for Git's binary heuristic but too loose as a backstop for the leak scan | A private term hidden by an invisible character is not a hygiene error | Refuse invisible format characters and C1 controls, and fold look-alike letters or state that only ASCII forms are scanned |
| R5-B-4 | Medium | `scripts/verify_remote.py` (the tree normaliser and the listing) | An entry without a type was dropped from the listing, so an extra file disappeared, and a missing `truncated` flag was read as complete. Removing the exit for a truncated listing left all 18 tests green | A partial or malformed GitHub listing can be reported as identical, and a fail-closed exit has no test | Stop on an entry that lacks a path, type or hash and on a flag that is not explicitly false, with tests |
| R5-B-5 | Medium | `scripts/validate_docs.py` (the ignore rules) | Negated rules are skipped, and `fnmatch` lets `*` match a slash. For a rule shape that the project does not use, the list of publishable files differs from what `git add` would take. The current rules did match `git check-ignore` | A later negation or a wildcard that spans a slash drops a file from the list, the unscanned-file check misses it, and CI stays green. The publish-time commit check would still report the file as extra | Last match wins for a negation, a `*` that does not cross a slash, and tests against Git |

## Mutations tried

| Mutation | Caught by | Verdict |
|---|---|---|
| The mode check of the commit check dropped | The test with a symbolic link whose text equals a file | Caught |
| The exit for a truncated GitHub listing dropped | Nothing (18 tests green) | Survived |
| The string-for-list check of the fact entries dropped | Three tests | Caught |
| The `archived` flag read as truthy instead of exactly true | The test for a flag that is not a boolean | Caught |
| The control-character report dropped | The control-character test | Caught |
| The junction reparse tag ignored | The junction test | Caught |
| The NUL-byte hygiene error dropped | Nothing (61 tests green) | Survived |

## Checked and sound

- The blob hash against Git itself, with CRLF, form feed and escape plus CRLF, a lone CR, a NUL plus CRLF and a C1 character plus CRLF. A file with SOH, DEL or a vertical tab and CRLF differs from what Git stores, which is DIFFERENT and never a false PASS, as the comment in the function says.
- A case-only rename, names with spaces, accents, semicolons and a hash sign, a different Unicode normalisation (which stops the check), quoted tree lines, and an absolute path with a space and an equals sign in an extra file.
- UTF-16 text with ASCII letters fails on its NUL bytes, and UTF-16 without ASCII becomes mojibake. Both fail closed.
- The junction reparse tag is the mount-point tag, and OneDrive placeholders have other tags.
- The fact list: 61 entries, all valid, ten kinds of check, exit codes and summary counts consistent. The facts workflow does not pass the strict option, so DRIFT and UNREACHABLE stay green, which matches the README.
- A truncated GitHub listing in the fact checker is UNREACHABLE, and wrongly typed answers are UNREACHABLE, both tested.

## Could not verify

The suite on Linux (the host skipped the two symbolic-link tests), a live symbolic link through the commit check (by inspection a link whose target bytes match would pass that check, and the validator refuses links first), a dangling link and a link that is the project folder itself, the GitHub-mode calls of the commit check, and OneDrive placeholder files on the host.

Verdict from the reviewer: 1 high, 4 medium, 0 low. The leak scan could still report a clean tree for a real user-profile path, and the other holes need a bad remote body, a split token, a malformed listing, or an ignore-file shape that this folder does not use.
