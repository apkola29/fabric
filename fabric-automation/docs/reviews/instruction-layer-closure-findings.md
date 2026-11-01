# Closure review of the instruction layer: findings, checks and outcomes

This is the second look at the instruction layer: the files that tell an agent what it has, where its knowledge comes from, how sign-in works, what to do when a server does not answer, and how to look for newer skills and servers (`AGENTS.md` with the two files that import it, the preamble that every profile loads, the `factory-router` skill and the `factory-standards` skill). The first review (three families, 25 findings, all accepted at least in part) is in [instruction-layer-findings.md](instruction-layer-findings.md). The author fixed what it found, and three families then read the corrected files cold, each at a slice that another family had taken the first time, so that every family has now seen two different slices. Each decided the earlier findings of its slice, repeated the reproductions, and looked for defects in the fixes and for anything new. The brief that they were given is in [the verification material](../../verification/briefs/instruction-layer-closure-briefs.md), and the replies are kept as the reviewers wrote them, with the agent's own header removed.

| Slice | Family | What it took | Reply | Earlier findings decided | New findings (as rated by the reviewer) |
|---|---|---|---|---|---|
| A | Grok 4.7 | The six requirements of the owner, what each host does with its file (against the live pages), consistency between the files, and whether the records of the first review say what is true | [instruction-layer-closure-grok.md](instruction-layer-closure-grok.md) | A-1 to A-6: 5 closed, 1 partly closed | 5: 3 Medium, 2 Low |
| B | GPT 6.1 Sol | The two tables of servers against the manifest and the live directory, every command of the files, 23 mutations of its own, the changed code of the update report against the last published commit | [instruction-layer-closure-gpt.md](instruction-layer-closure-gpt.md) | B-1 to B-12: 9 closed, 3 partly closed | 9: 5 Medium, 4 Low, and 17 of its 23 mutations survived the tests |
| C | Gemini 4 Argon | The files read as an agent that has nothing else, in eleven scenarios | [instruction-layer-closure-gemini.md](instruction-layer-closure-gemini.md) | C-1 to C-7: 3 closed, 4 partly closed | 5: 2 Medium, 3 Low |

The reviewer of slice C returned nothing at its first turn (the agent ended after 90 seconds without a reply), and the same task sent as a second message produced the reply that is kept. The snapshot that the reviewers read was a copy of the working folder, not a clone, taken before the fixes that this record lists.

All 19 new findings were accepted in full or in part, and none was rejected. By the author's ratings that is 0 High, 7 Medium and 12 Low (the reviewers rated 0 High, 10 Medium and 9 Low). Nothing was found that made an earlier fix wrong. Four of the eight partly closed earlier findings stay partly open on purpose (B-10, B-11, B-12, and the general stop on identifiers of C-6); the other four (A-4, C-2, C-5 and C-7) were closed by the fixes that this record lists.

## The earlier findings

| ID | Decision of the reviewer | What the author found and did |
|---|---|---|
| A-1 | Closed | Reproduced by the reviewer on a scratch copy (a package that cannot be resolved: exit 0, the sentence about the part that did not run in the console and in the summary file). Nothing to do |
| A-2 | Closed | Nothing to do |
| A-3 | Closed | Nothing to do |
| A-4 | Partly closed | True. The host table of the README still said that Claude Code reads `AGENTS.md` on its own "only when no `CLAUDE.md` is there", and the Limits bullet named only the version. The grounding note and the claim of the fact list had the three files (`CLAUDE.md`, `.claude/CLAUDE.md` and `CLAUDE.local.md`). The README now says the same, in the table and in the Limits |
| A-5 | Closed | Nothing to do |
| A-6 | Closed | Nothing to do |
| B-1 | Closed | The reviewer ran the command (38 seconds, the summary file written) |
| B-2 | Closed | Fresh copy: `verify --live` exits 1 until `install --apply` ran, then 0 |
| B-3 | Closed | Checked against the upstream README of the Power BI authoring server |
| B-4 | Closed | The four servers of the paragraph match their current pages |
| B-5 | Closed | The setup page and the two endpoints per agent match the page |
| B-6 | Closed | The reviewer's own replay of the mutation fails now |
| B-7 | Closed | The three earlier reproductions are killed |
| B-8 | Closed | The reproductions are killed, but a distinct gap remained: a variant named twice in a cell (B2-1, below) |
| B-9 | Closed | The four reproductions are killed. Two gaps remained: a command with a missing operand, and the commands of the README (B2-2, below) |
| B-10 | Partly closed | As the first record said: an unpinned row whose name or description is changed while its page is kept is not caught, because the page is what identifies the row. Not done, on purpose |
| B-11 | Partly closed | The rows of `AGENTS.md` say what the servers do. The short summaries inside `toolchain/toolchain.json` (for example "All tools of the hosted server") are unchanged: they say what a variant may do (read or write, with which sign-in), not what its tools are for, and the capabilities are in the catalogue, where a test now holds the essential word of each row (B2-5). Left as it is |
| B-12 | Partly closed | As the first record said: the retry window is unchanged, and that a second run always completes in a synced folder is UNVERIFIED |
| C-1 | Closed | Nothing to do |
| C-2 | Partly closed | True in one respect: the preamble said "a tool that is not in your list does not exist for this job" with no word about the one exception that `AGENTS.md` and the router give to a person's session (C2-4) |
| C-3 | Closed | Nothing to do |
| C-4 | Closed | Nothing to do |
| C-5 | Partly closed | True in one respect: a job profile that loads no repository skill (`agent-intake`, `agent-verifier`) was still told to use the standards and the router (C2-3) |
| C-6 | Partly closed | The part that the first record left undone stays undone: an item definition in Git normally holds identifiers, so a general stop would stop the work. What the reviewer showed, and what was done, is that a citation of the files that were used should be by path and not by content (C2-2) |
| C-7 | Partly closed | The rules come first now. Two of the five rules that the reviewer found only in the preamble matter for a person's session and are now in `AGENTS.md` too: a change to security, permissions, a network setting, a label or a tenant setting is flagged and never made, and nothing that only the live tenant can tell is guessed (C2-5). The others are rules of a job, which reads the preamble |

The reviewer of slice C wrote that C-6 "not done" is partly wrong and that C-7 was rated too low. The first is the point above (identifiers in the item definitions of the target are normal; the identifiers that must not leave are those that are copied out of them, and rule 4 of `AGENTS.md` already forbids them in this repository). The second is accepted as far as the two session rules go and not further: a rating of Low for a finding about the structure of a file that is only part of what the finding said was too low by one step, and the record of the first review now says nothing that contradicts it.

## New findings of slice A (requirements, hosts, consistency, records)

| ID | Finding | Rated | After the check | What was done |
|---|---|---|---|---|
| A2-1 | The record of the first review stated numbers and checks that are not in the files: the totals of the severities (the sums were wrong: it said 1 High, 11 Medium and 13 Low for the author, and 4 High, 14 Medium and 7 Low for the reviewers), a README sentence that was not true (A-4 above), a link to a findings record and a loop of the verification log that did not exist yet, and a line count of the router that was one too high | Medium | Medium (recounted from the three replies: the reviewers rated 4 High, 15 Medium and 6 Low, the author 1 High, 17 Medium and 7 Low) | The totals are right now, the README says what the record said, the records that were cited are written, and the line counts are gone from the record (a test holds a budget for each file, which is what matters). "What was not proved" now says that a job has no runner for the look at newer skills yet |
| A2-2 | The first sign-in rule that a job reads said "Sign-in belongs to the host, not to you", and the same file, `AGENTS.md` and the router say that it belongs to the person or the runner. "The host" is neither | Medium | Low (a wording that disagrees with three other places; no rule was missing) | "Sign-in belongs to the person or the runner, not to you", in the same words as the sign-in section |
| A2-3 | A job is not told to keep identifiers out of pull request text: the rule in `AGENTS.md` names "a file or pull request text", the preamble only "a file that this repository publishes" | Medium | Low (the pull request of a job is in the repository of the target, which is not public; the public repository is the one that `AGENTS.md` covers) | One sentence in the preamble: the same goes for the text of a pull request of this repository |
| A2-4 | The router still showed a job two toolchain commands that the preamble says a job does not run (`list` in its step 2 and `doctor` in its rule about installs) | Low | Low | Both places say that a job does not run them and, for `doctor`, that a job says what is missing and ends the step |
| A2-5 | The design row for the existing deployment had less than the rules that a job is given: it did not say what to do when two existing patterns disagree, or when a secret is already in Git | Low | Low | The row says both |

## New findings of slice B (the catalogue, the commands, the tests by mutation, the changed code)

The reviewer ran 23 mutations of its own on a scratch copy and restored each byte for byte. 17 survived the tests of the first version, and 6 were killed. The first six findings are gaps in the tests, not defects in the files; the last three are defects in the code and the text of the update report, and the author reproduced each of them before changing anything.

| ID | Finding | Rated | After the check | What was done |
|---|---|---|---|---|
| B2-1 | A variant named twice in a sign-in cell, with two different words, passes (the dictionary keeps one of them); the preamble could name the offline variant as one that signs in as the person | Low | Low | The reader of the cell refuses a repeated variant; a test derives the variants that act as the person from the manifest and compares them with the ones that the preamble names |
| B2-2 | The first preflight could drop `--live`; the commands of the README were not checked (a recipe with a profile that does not exist, or `--write` in place of `--check`); a validator flag without its value passed, because the test looked for the flag in the help text | Medium | Medium | Every `verify` command of `AGENTS.md` and the router has to be the live one; the README is read like the other files (and its Gemini recipe is a full command now); the README has to give the same freshness command; each validator command is parsed by the validator itself |
| B2-3 | Valid names in the wrong place: the owner of report questions, the route of T-SQL, hosted Fabric IQ as executor-only, and the sentence that no live CLI or REST step runs in the agent and executor modes could be changed or removed | Medium | Medium | A table of the essential routes (task, skills, servers, and the mode of each server) is held by a test, and so is the sentence about the two modes in the preamble and the router |
| B2-4 | The tests kept the labels of the tags of the standards skill but not their meaning: the text could say that a `[gate]` is already enforced, or that a `[flag]` is turned into a change automatically | Medium | Medium | A test holds the sentences that say what the checks are not (an authorization, a compliance statement, a decision about a change) and what a flag means |
| B2-5 | The descriptions of pinned servers, the documentation addresses of the manifest, and the contents of a watch (the query endpoint of the operations agent) were weakly held | Low | Low | A test holds the essential word of each row of the catalogue and the hosting (remote or local) of each unpinned server; the documentation addresses of the manifest are pinned in a test, and so are the two URLs of the operations agent in its fact. Not every page of the manifest is watched by the fact list, which the test says |
| B2-6 | Two unresolved packages were reported twice on the console and once in the summary, and no test noticed | Low | Low | A test at the boundary of the command: both notes in both outputs |
| B2-7 | A failed check leaves a summary of an earlier check intact: the file still says "No upstream change", and a run that takes the summary "in every case" would carry stale evidence | Medium | Medium (reproduced on the offline fixture: exit 1 and exit 2, summary byte for byte unchanged) | The command removes the summary file before it starts, and a summary file that cannot be replaced is an error line. An invalid command line (exit 2) is refused before the command runs and cannot be helped by the command, so the README says that the file is removed by the command and that the summary is evidence only after exit 0 or 3 |
| B2-8 | Exit 3 does not always mean that something is newer: with only the manifest edited the console said so and the summary said "No upstream change", and the instructions said "something is newer" | Low | Low (reproduced) | The summary has the same line as the console, and the instructions say that exit 3 means a candidate lock that differs, because something is newer or the manifest was edited |
| B2-9 | The README and the design said that exit 3 covers "a tool contract changed upstream", and the default check launches no server (zero captures): a changed tool list is seen only by the weekly launch of the pinned servers and by a manual capture | Medium | Medium (reproduced: a destructive annotation changed upstream with the package metadata unchanged gave exit 0; `--contracts` gave 3) | The README, the design and the instructions say that the check reads metadata, launches no server and does not see a changed tool list, and where that is seen instead. The default check was not changed to launch servers: that runs code that nobody has reviewed |

## New findings of slice C (an agent that has nothing else)

| ID | Finding | Rated | After the check | What was done |
|---|---|---|---|---|
| C2-1 | The standards skill does not say what a `Note:` is, what to do when a check differs from the existing deployment, that the pack does not decide whether a change is accepted, or that a request that needs a flagged change (row-level security for HR data) is escalated as a whole and not built without its protection | Medium | Medium (the skill had none of the four; the design says that a plan with such content is escalated as a whole) | The skill says each of the four, and that a citation takes the page address and date from the table at the top of the file |
| C2-2 | The rules still allow identifiers from the target Git folder to be copied into a pull request or a file of this repository, and "cite the files you used" is not "by path" | Medium | Low (the rule exists in `AGENTS.md` and it covers this repository; a job writes to the repository of the target) | The citation is by path, and the preamble has the sentence about pull request text (A2-3) |
| C2-3 | The preamble sends every profile to the router and the standards skill, and two job profiles load neither | Low | Low (reproduced with `render --profile agent-verifier --host load-plan`) | The preamble says that a profile without them works from its rules alone |
| C2-4 | The preamble has no exception for the unpinned server that a person's session may call, and `AGENTS.md` and the router give one | Low | Low | The preamble names the exception and its source |
| C2-5 | An agent that reads only `AGENTS.md` does not see the flag rule, the quarantine, the rule against guessing live state, or the boundary of the executor mode | Low | Low | The flag rule and the rule against guessing are in `AGENTS.md`. The quarantine, the executor boundary and the rule about confirmations in skills are rules of a job, which reads the preamble |

The reviewer's scenarios S1 to S11 and what the agent would do in each are in the reply. For S2, S3, S4, S5, S9 and S10 (a command in an issue, a hosted server that does not answer, a tool result that tells the agent to add a server, the exit codes, a blanket authorization, a task that tells a job to adopt newer skills) it found the layer right and fail-closed.

## What the author added to the review

1. **The records were read too.** Slice A was asked to check that the record of the first review is true, and found five statements that were not (A2-1). The author recounted every number from the three replies. A record of a review is a document that a later reader trusts, so it is held to the standard of the code.
2. **The 23 mutations of the reviewer are now proved.** They are in `verification/tools/mutation_specs_instruction_layer.py` (the set `closure-review`, with the text of the files as they are now), together with 3 more for the new behaviour of the update report. With the other three sets (42 of the instruction files, 11 of the reference pack, 5 of the update report) 84 mutations are killed by the tests, and none survives. The tests grew from 26 to 34 for the layer, 22 to 26 for the update report, and the pack stayed at 9.
3. **The README is checked like the instruction files**: its commands are parsed by the command line of the kit, its freshness command is the same as theirs, and a command that it shows for the Gemini host is a full command.
4. **The reference pack was verified three more times**, see [standards-pack-findings.md](standards-pack-findings.md).

## What was not proved

- No host was run against a model with these files. That `AGENTS.md` reaches Copilot CLI once or twice, that Claude Code 2.1.162 takes it through the import, that Gemini CLI and VS Code read the files as their pages say, and that an agent obeys the text, are all UNVERIFIED. The tests prove that the files agree with the manifest, the commands and each other.
- A second `install --apply` in a folder that a sync client holds is UNVERIFIED (B-12).
- Linux was not run by any reviewer. The hosted runner runs the tests on Linux when the commit is published, and the result is in the verification log.
- The catalogue of servers is checked against the live directory on the day of the review. It is a list of what Microsoft publishes today, and the weekly fact check shows when the directory page changes.
