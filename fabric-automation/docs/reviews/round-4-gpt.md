# Verification round 4: GPT 6.1 Sol

Lens: the tooling code that round 3 changed (a narrow closure check). The reviewer had not seen an earlier round. It read a frozen copy of the published commit `6ca7594335` and the diff of round 3, ran Python and PowerShell against copies of it, and replied inline. This is the reply condensed; file names are relative to the folder. The disposition of each finding is in [round-4-findings.md](round-4-findings.md).

## Findings

| ID | Severity | Where | Evidence | Why it matters | Concrete fix |
|---|---|---|---|---|---|
| R4-A-1 | High, blocking | `scripts/sync_to_github.ps1`, the address check | A clone configured with two push addresses, the repository and another host: `git remote get-url --push origin` returned only the first, and `--all` returned both | Git pushes to every push address of a remote, so the gate validated only the first of the destinations | List every address with `--all` and validate each, or push to one explicitly validated address |
| R4-A-2 | High, blocking | `scripts/sync_to_github.ps1`, the order of validation, mirror and tree check | In-memory fixture: the source validates clean, text with a private term is then added, the matching commit reports 0 problems, and revalidation reports the term | The tree check compares the commit with the current source, not with the bytes that were scanned, so a change between validation and mirroring publishes unread content | Validate a frozen copy, or keep the scanned manifest and compare the commit with it |
| R4-A-3 | High, blocking | `scripts/verify_remote.py`, the tree listing | A tree with a gitlink entry passes with 0 problems, and changing a matching blob's mode to a symbolic link also passes | Gitlinks vanish from the comparison and modes are discarded, so zero problems does not show that the commit holds only the validated regular files | Keep type and mode, and reject gitlinks and symbolic links unless they are explicitly expected |
| R4-A-4 | High, blocking | `scripts/sync_to_github.ps1`, the optional repository README | A README that is a symbolic link: the leak scan reads its target, Git publishes the link path, and the pre-push check never asks about the README | With `-IncludeReadme` the file that is scanned is not the file that is committed, and the README is outside the tree check | Include the README in the compared set, and reject links or compare the committed blob and its mode |
| R4-A-5 | High, blocking | `scripts/verify_facts.py`, the contents and tree checks | A contents answer of `[null]` gives PASS, and a tree entry with a null path gives FAIL as a checker crash instead of UNREACHABLE | The checks look at the shape of an answer but not at the types of the fields they read | Validate the fields before evaluating a claim, and raise Unreachable for a malformed answer |
| R4-A-6 | High, blocking | `scripts/verify_facts.py`, the definition check | A page fact whose `all` is the string `alpha` passes against a page that says only `aplha` | A string is read one character at a time, so an invalid entry can produce a successful verdict | Check each entry against a per-kind schema, including lists of strings, scalar types, the `expect` values and booleans, before any request |
| R4-A-7 | Medium, non-blocking | `scripts/verify_remote.py`, the hash of a local file | 1,024 bytes of `\x01` followed by CRLF validates clean; Git hashes it unchanged and the checker hashes it with LF, so clone mode reports DIFFERENT | The gate treats every file without a NUL byte as text, and Git is more careful, so a correct commit can be rejected | Follow Git's own rule, or validate the staged blobs. LF-only content avoids it |
| R4-A-8 | Medium, non-blocking | `scripts/test_sync_script.py`, the four order tests | Removing the abort after a failed tree check leaves them green, and so does removing the fetch iteration | Positions of strings in a script do not prove fail-closed behaviour | Add behavioural tests with stand-in commands: a failed verification must prevent the push, and the fetch and every push address must really be checked |

## Checked and sound

- 55 validator tests passed on a virtual filesystem, and 60 fact-checker tests and the five parse and order tests passed.
- Handling of a byte-order mark and of UTF-16 in the private list, missing and empty lists, the allowed SSH user address, unsupported extensions, and NUL bytes and lone carriage returns in regular files were exercised.
- Forced-tracked private, bytecode and environment files were rejected as extras. Unicode, spaces and tabs in paths survived the NUL-delimited tree parsing.
- Ordinary CRLF text, binary data with a NUL, and large text files hashed the same as native Git.
- The 19-address matrix passed under Windows PowerShell 5.1 and PowerShell 7.6. Changes to an unmanaged workflow file were rejected, and the push uses the checked commit.

## Mutation checks (by the reviewer)

- Disabling the check for unread files failed both of its tests, and disabling the byte-order-mark handling failed its regression test.
- Disabling the extra-file detection failed the two original regression tests, with Git input and output mocked.
- Mutations of the empty-body rule, the JSON key check, the status classification, the SSH exception and the definition check each failed a targeted test. The order-test mutations of R4-A-8 were not caught.

## Could not verify

- The full disk-backed suite and the native clone and robocopy path were not run: the source mutations and file fixtures stayed in memory, and the Git-tree counterexamples used mocked transport.
- Traversal and deletion through a real NTFS junction, publication of a real symbolic link, and PowerShell 7 on Linux were not exercised end to end, so the destructive behaviour of the purge stayed unverified.
- No live fetch or push and no real private list were used, and the private-term probes used synthetic terms. No flakiness was seen in what ran.

Verdict from the reviewer: 0 critical, 6 high, 2 medium.
