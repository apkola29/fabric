# Verification material

The process material behind the evidence in [docs/reviews](../docs/reviews/README.md): the briefs that the reviewers and the implementers were given, what the implementers reported, and the scripts that produced the mutation, replay, Linux and fresh-clone numbers. It is kept so that a reader can see how the checks were done and can run them again. It is **not** part of the [toolchain kit](../toolchain/README.md), and nothing in the kit depends on it.

## What is here

| Path | What it is |
|---|---|
| [briefs/toolchain-review-briefs.md](briefs/toolchain-review-briefs.md) | The first review of the kit: a shared preamble and three slice briefs (command line, helper modules, data and documents) for three model families working cold and in parallel |
| [briefs/toolchain-closure-briefs.md](briefs/toolchain-closure-briefs.md) | The second review (a closure check of the corrections), with the slices rotated so that no family kept the slice it had before |
| [briefs/toolchain-delta-briefs.md](briefs/toolchain-delta-briefs.md) | The third review (the delta after the second), rotated a third time, so that every family had every slice once |
| [briefs/toolchain-recheck-briefs.md](briefs/toolchain-recheck-briefs.md) | The fourth look: each family checks the fixes of its own findings and the diff of its own slice |
| [briefs/implementer-brief-command-line.md](briefs/implementer-brief-command-line.md), [briefs/implementer-brief-helper-modules.md](briefs/implementer-brief-helper-modules.md) | The briefs of the two implementation agents that fixed the findings of the third review, each in an isolated copy of the project, with the rules of the house and the mutation proof that each had to bring |
| [reports/implementer-report-command-line.md](reports/implementer-report-command-line.md), [reports/implementer-report-helper-modules.md](reports/implementer-report-helper-modules.md) | What those two implementers reported back, with their mutation tables |
| [tools/mutate.py](tools/mutate.py) | The mutation harness: replaces one text of the code by a broken one, runs the tests that should notice it, and says KILLED or SURVIVED |
| [tools/mutation_specs_fourth_look.py](tools/mutation_specs_fourth_look.py) | The 21 mutations of the fourth look, as specifications for the harness |
| [tools/mutation_specs_instruction_layer.py](tools/mutation_specs_instruction_layer.py) | The 123 mutations of the instruction layer, in six sets: the instruction files (42), the reference pack (11), the update summary (8), the 23 that a reviewer of the closure review made on its own, the 26 of the third look and the 13 of the fourth, which the digest test of the text kills |
| [briefs/instruction-layer-review-briefs.md](briefs/instruction-layer-review-briefs.md), [briefs/instruction-layer-closure-briefs.md](briefs/instruction-layer-closure-briefs.md), [briefs/instruction-layer-third-look-briefs.md](briefs/instruction-layer-third-look-briefs.md) | The review of the instruction layer by three families (a shared preamble and three slice briefs), the closure review with the slices handed to different families, and the third look with the slices rotated again, so that every family has read every slice. The fourth look was a message to each of the three in its own session and has no brief of its own. In these briefs `<review folder>` stands for the folder of the author's machine in which the reviewers worked, and `CLONE` for the snapshot of the project that they read |
| [briefs/standards-pack-drafting-brief.md](briefs/standards-pack-drafting-brief.md) | The brief of the model that drafted the reference pack from 16 pages of Microsoft Learn |
| [briefs/standards-pack-round-1-briefs.md](briefs/standards-pack-round-1-briefs.md), [round 2](briefs/standards-pack-round-2-briefs.md), [round 3](briefs/standards-pack-round-3-briefs.md), [round 4](briefs/standards-pack-round-4-briefs.md) | The four verifications of the pack against the text of its pages: the files divided, then rotated, then every line read by all three families with a quote for every row, then the changed lines again. The questions that followed round 4 were messages in the same sessions and have no brief of their own |
| [tools/pack_mechanics.py](tools/pack_mechanics.py), [tools/pack_quotes.py](tools/pack_quotes.py), [tools/pack_dates.py](tools/pack_dates.py), [tools/pack_hedges.py](tools/pack_hedges.py) | What a program can check of the reference pack: that each citation, number and heading is in the cited pages and that no long run of words is copied; that the quote in each row of a report is in the cited section; that the date of each page is its live `updated_at`; and which hedge words of a source sentence a check has lost |
| [tools/replay.py](tools/replay.py), [tools/standin_server.py](tools/standin_server.py), [tools/standin_env.py](tools/standin_env.py) | The replay of the reviewers' reproductions (51 scenarios) and the stand-in servers that some of them start |
| [tools/ci_probe.ps1](tools/ci_probe.ps1) | Runs the validate workflow on a throw-away branch with the current files, so that the Linux result is known before the main branch is touched |
| [tools/fresh_clone_acceptance.ps1](tools/fresh_clone_acceptance.ps1) | A first run from a fresh clone of the public repository at a commit: doctor, install, a second install, verify, the renderings, a tampered skill, fetch and the validator |

## How the pieces were used

**A review.** The reviewer gets the shared preamble, then the brief of its slice. It works in its own clean clone of the public repository at a given commit, reads the delta, tries to break the fixes, mutates the safeguards of its slice and answers with findings that each carry a reproduction or a primary-source citation (UNVERIFIED where it could not reproduce), capped in number and length. The author then checks every point against the code or the source before accepting or rejecting it. The replies are in `docs/reviews`, the author's checks in the findings file of each round.

**A mutation proof.** A specification names the project, the tests that should notice, and a list of mutations (a file, the old text, the new text). The harness copies the project once, checks that the tests pass, and for each mutation requires the old text to occur exactly once, writes the broken text, runs the tests and puts the file back. A mutation that no test notices is reported as SURVIVED and is a gap in the tests.

```
python verification/tools/mutation_specs_fourth_look.py --out %TEMP%
python verification/tools/mutate.py %TEMP%/mutations-fourth-look-a.json
```

The 123 mutations of the instruction layer are run the same way, one JSON file for each set (`mutations-instruction-layer.json`, `mutations-standards-pack.json`, `mutations-update-summary.json`, `mutations-closure-review.json`, `mutations-third-look.json` and `mutations-fourth-look.json`), from `python verification/tools/mutation_specs_instruction_layer.py --out %TEMP%`. A mutation of this set changes one text of an instruction file, of the fact list, of a reference file or of the update command, and the tests that are meant to notice it are the ones of the instruction layer, the reference pack or the update report. The last set also runs `ReviewedTextTests`, which holds the text of the instruction files and of the reference pack by a digest and so kills every change of that text: it is left out of the other sets, because it would hide what their tests hold.

**The checks of the reference pack.** The programs that read the pack take the folder of the four reference files (`toolchain/skills/factory-standards/references`) and, except `pack_dates.py`, the 16 pages reduced to text: one file for each page, named by the page address with every run of other characters replaced by a hyphen, and starting with a line `SOURCE: <address>`. `pack_mechanics.py PACKDIR SOURCEDIR` prints a line for every check whose citation, number or heading it cannot find in the cited pages, or that copies more than 12 words in a row. `pack_quotes.py PACKDIR SOURCEDIR REPORT...` reads a report with one row for each check (`id | verdict | quote | reason`) and prints the rows whose quote is not in the cited section of the cited page, which is the proof that the row was read against the page. `pack_dates.py PACKDIR` compares the date of each page in the pack with the live page (it needs the network and no sign-in). `pack_hedges.py PACKDIR SOURCEDIR [ID...]` prints, for each check, the sentences of the cited sections and the hedge words of those sentences that the check does not carry. None of them decides whether a line is supported; a reader does.

**The replay.** Each of the 51 scenarios copies the toolchain files of a tree into a scratch folder with its own home folder, applies the change that a reviewer described, runs the command line and says whether the behaviour that the reviewer reported still happens. REPRODUCED means that the defect is present. Run on the commit that the reviewers reviewed it reproduces the defects; run on the corrected tree none should reproduce.

```
python verification/tools/replay.py .                    # the tree of this folder
python verification/tools/replay.py OLD_TREE --only D1-1,D2-1
```

`OLD_TREE` is a checkout of an earlier commit (the folder that holds `scripts` and `toolchain`). A tree whose lock holds no captured contract borrows one from the lock of this project (`--reference-lock` names another).

**The Linux probe and the fresh-clone run.** `ci_probe.ps1` pushes the current files to a throw-away branch, dispatches the validate workflow there, prints the test count and deletes the branch; it needs a signed-in `gh` with the right to push and never touches the main branch. `fresh_clone_acceptance.ps1 -Sha COMMIT` clones the public repository at that commit into a temporary folder and runs the first-run checks with a scratch home folder.

## Limits

- These are scratch tools. They were written while the work was done, they are Windows-first (the PowerShell scripts need PowerShell, the Python ones run on both systems), the tests of this repository do not cover them, and no model family reviewed them: the families reviewed the kit. Read them before you trust them.
- The replay scenarios and the mutation specifications are tied to the code of the commits that they were written for. When the code moves, a mutation reports ERROR because its old text no longer occurs exactly once, and a replay scenario may stop meaning what it meant. The acceptance script checks what the lock held when it was written.
- Not kept: the written specifications of the first two rounds of fixes (they were scratch files), the first build specification of the kit (a working document for the implementers, not for publication), the scripts of the SDK experiments (they used a small tool package that was not kept), the script that reduced the 16 pages of Microsoft Learn to text (the pack tools say what format they need; the pages themselves change without notice), and the raw replies of the reviewers (the normalised replies are in `docs/reviews`).
- The numbers in the records came from these tools run on the author's Windows machine and on the hosted Linux runner. The records say which.
