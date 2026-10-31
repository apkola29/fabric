# Verification round 5: Gemini 4 Argon

Lens: the publish script and its behavioural tests (slice A of a closure check). The reviewer had not seen an earlier round. It read a frozen copy of the published commit `c7c690a0eb` and the diff of round 4, ran the behavioural tests, and tried to break the script with its own mutations (a modified copy of the script, run through the environment variable that points the tests at it). This is the reply condensed; locations refer to that commit. The disposition of each finding is in [round-5-findings.md](round-5-findings.md).

## Findings

| ID | Severity | Where | Evidence | Why it matters | Concrete fix |
|---|---|---|---|---|---|
| R5-A-1 | High | `scripts/sync_to_github.ps1` (the link search and the mirror step), `scripts/validate_docs.py` (the link check) | The search for links looks only at the children of the mirror folder, never at the folder itself, the clone, or the workflow folder. In the test harness the mirror folder was replaced by a junction to an outside folder holding two files. The search found no link, the purge and `robocopy /MIR` went through the junction and deleted both files, and the run exited 0. The workflow files are also written without a check for links on `.github`, its `workflows` folder or the files. The validator resolves its root before it can see that the root is a link | A link at the mirror folder, the workflow folder or a workflow file makes the script delete or overwrite files outside the clone, and the run succeeds | Check the folder itself before listing its children, and check the clone's `.github`, the workflow folder, the workflow files and the README before anything is mirrored or written. In the validator, test the root for a link before it is resolved |
| R5-A-2 | High | `scripts/sync_to_github.ps1` (the README arguments), `scripts/validate_docs.py` (the extra-file scan), `scripts/verify_remote.py` | With `-IncludeReadme`, the README is scanned by the leak scan only, which read it as UTF-8 with replacement. A README saved as UTF-16 (the default encoding of `>` in Windows PowerShell 5.1) left NUL bytes between the letters, so no pattern and no private term matched, and the validator exited 0. The commit check saw a NUL and, as Git does for binary files, skipped the line-ending step and matched the committed blob | A README with a private term or a token can be published unscanned | Give every file passed with `--scan-file` the checks of a project file (no byte-order mark, no NUL, valid UTF-8, no control characters, not a link), and refuse a NUL in the commit check |
| R5-A-3 | Medium | `scripts/test_sync_flow.py` | Six mutations of the script left all 14 behavioural tests and the 6 text tests green: the whole private-list gate removed, staging and committing without the path list, the check of the paths and merges hollowed out, the abort after a failed check of GitHub removed (the stand-in has a switch for it that no test sets), the copy of the workflow files removed, and the purge of leftovers moved after the mirror scan (the test only looks at the disk after the run) | Six safeguards that the README claims can be deleted without failing a test | One test per safeguard, a stand-in that inspects the disk when the mirror is scanned, and a test that sets the switch for a failed check of GitHub |
| R5-A-4 | Medium | `scripts/sync_to_github.ps1`, `scripts/verify_remote.py` | The project's `.gitattributes` covers only the project folder. A README with Windows line endings is committed as it is, the commit check hashes it with LF, reports DIFFERENT, and the run stops after the commit | A run with `-IncludeReadme` can stop at the gate and leave an unpushed commit behind | Normalise the README, or compare the exact bytes for a file that the attributes do not cover |
| R5-A-5 | Medium | `scripts/sync_to_github.ps1` (the fold, the excluded folders, the verification) | (1) The soft reset that folds earlier commits keeps their index, so a file that an earlier commit force-added although `.gitignore` keeps it out is committed again on every run and stopped by the gate every time. (2) An abort between the fold and the commit leaves the folded changes staged. (3) The mirror excludes only the top-level private folder, while the validator skips a private folder at any depth, so a nested one is copied into the clone without being scanned. The reviewer also suggested comparing the verification with the mirror instead of the live source | A wedged clone, an unclear state after an abort, and a difference between what the validator skips and what the mirror copies | A mixed reset, the fold right before staging, a bare folder name in the excludes and in the purge, and the mirror as the reference of the verification |
| R5-A-6 | Medium | `scripts/sync_to_github.ps1` (the wrapper for native commands) | The wrapper merges standard error into the answer. In both Windows PowerShell 5.1 and PowerShell 7, a command that succeeds but writes a warning to standard error returns the warning inside its answer | A benign warning corrupts the parsed login, the commit counts, the changed-file list, the head hash and the JSON of the CI watch | Keep the two streams apart, return the answer from standard output only, and put standard error into the error message |
| R5-A-7 | Low | `scripts/sync_to_github.ps1` (the check of managed paths) | The check compares paths without regard to case, while the pathspecs that Git is given are case-sensitive. A commit that touched a path whose folder name differs in case passes the check, is folded into the index, and is then ignored by the pathspec, which leaves a dirty index. A user's `log.showSignature` or the default quoting of non-ASCII names changes the parsed lines | A path that Git treats as outside the managed set passes the check | Compare case-sensitively and read the log with the quoting and signature options off |
| R5-A-8 | Low | `scripts/sync_to_github.ps1` (the project folder), `scripts/test_sync_flow.py` | The project folder is derived from the script's own location, so a modified copy of the script outside the scripts folder mirrors the wrong folder and fails 7 of the 14 tests for a reason unrelated to the mutation | The mutation harness that the tests invite does not work from anywhere | Add a parameter for the project folder, defaulting to the folder above the script, and pass it from the tests |

## Mutations tried

| Mutation | Caught by | Verdict |
|---|---|---|
| The whole private-list gate removed | Nothing | Survived |
| Staging and committing without the path list | Nothing | Survived |
| The check of the managed paths and of merge commits hollowed out | Nothing | Survived |
| The abort after a failed check of what GitHub holds removed | Nothing | Survived |
| The copy of the workflow files removed | Nothing | Survived |
| The purge of leftovers moved after the mirror scan, and partly dropped | Nothing | Survived |
| The abort when the signed-in account is not the owner removed | The test for another account | Caught |

## Checked and sound

- `insteadOf` and `pushInsteadOf` rewrites: the address check asks Git to expand them, and the rewritten address was refused.
- `remote.pushDefault`, `branch.<name>.pushRemote` and `push.default` cannot redirect the push, because the script names the remote and the full refspec.
- A credential in an address is refused and removed from the message.
- A gitlink or a symbolic link in the commit tree is reported, in the folder, in the workflow copies and in the README.
- Paths with spaces and a hyphen, which the real project path has.
- OneDrive placeholders are not mistaken for links, in the script or in the validator.

## Could not verify

Live NTFS file symbolic links, which need a privilege that the host did not grant (the cases were checked through the index and with junctions instead), and anything that needs a push or a call to GitHub, which the reviewer was told not to do.

Verdict from the reviewer: 2 high, 4 medium, 2 low, and 6 of 7 mutations survived.
