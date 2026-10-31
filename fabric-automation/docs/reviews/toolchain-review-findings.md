# Review of the toolchain kit: findings, checks and outcomes

The published toolchain kit (commit `3494fe4223`) was reviewed once by three model families. Each worked in its own clean clone of the public repository, with a slice of the kit and the instruction to attack it. This file says what they found, how each finding was checked, what was changed and how the change was proved. The replies are kept as the reviewers wrote them, with only the line-reference notation normalised.

| Reviewer | Model | Slice | Reply | Findings | Mutations |
|---|---|---|---|---|---|
| A | GPT 6.1 Sol | The command line: `scripts/toolchain.py` and its tests | [toolchain-review-gpt.md](toolchain-review-gpt.md) | 15 (3 High, 11 Medium, 1 Low) | 24 on copies, 3 survived |
| B | Grok 4.7 | The helper modules: processes and HTTP, the MCP probe, Git, skills and packages | [toolchain-review-grok.md](toolchain-review-grok.md) | 10 (4 High, 5 Medium, 1 Low) | 35 on copies, 5 survived |
| C | Gemini 4 Argon | The data, the documents, the workflows, the public exposure and the first run from a clean clone | [toolchain-review-gemini.md](toolchain-review-gemini.md) | 11 (4 High, 5 Medium, 2 Low) | None. It ran the first-run procedure and recomputed every skill digest and package hash |

## How each finding was handled

The author re-read the cited code, ran or reasoned through the reproduction, and re-fetched the primary source for every claim about a product, before accepting or rejecting anything. Nothing was rejected outright. Of the 36 findings, 30 were accepted as rated, 5 were accepted with a lower rating (the defect is real, the impact is smaller than stated) and 1 could not be settled (C-5). By the author's ratings that is 6 High, 26 Medium and 4 Low; the reviewers had rated 11 High, 21 Medium and 4 Low.

The fixes were made in two stages. The author wrote the parts that are not code: the router skill, the preamble, the manifest, the profiles, the facts and the workflow. The code was changed by two implementation agents working from a written specification in separate copies (X: the command line and its tests; Y: the three helper modules and theirs), and the author merged, ran and extended the result. Each agent proved its safeguards by mutating a copy and checking that the test meant for the safeguard failed.

## Findings of reviewer C (data, documents, workflows, first run)

| ID | Finding | Rated | After the check | What was done |
|---|---|---|---|---|
| C-1 | The skills of `skills-for-fabric` link to the plugin's `common` folder, and the install never copies it, so the mandatory references of 24 skills were broken | High | High | The manifest names a plugin's shared folders, the lock records their digest, and the kit vendors them and installs them beside the skills (`.github/common`, `.claude/common`). The second plugin's `common` folder has to be a byte-identical subset of the first, or the lock is refused. A link check over the installed skills went from 625 unresolved relative links of 3,938 to 6 of 3,955: five targets that do not exist upstream either (see the end of this file) and one line of prose that the checker misread as a link |
| C-2 | The weekly job launches the newest, unreviewed server versions | High | Medium | The runner holds no secrets and the candidate lock is reviewed, so the risk is lower than stated, but a schedule should not run unreviewed code. The scheduled run now reads registry and tag metadata and re-checks the pinned contracts. Launching the newest versions is a manual dispatch with a `capture` input |
| C-3 | The router and preamble say MCP only, but most pinned skills are CLI or REST skills, `sqldw-cli` names a server the kit renames, and the cost skills need a server the kit lacks | High | High | Both texts were rewritten: the surface follows the skill, CLI and REST steps run in the dev mode with a person's approval, and a table translates the plugins' server names into the kit's. The Azure cost server was added as `azure-arm-cost`. A fourth model then checked the rewrite cold against the pinned skills and found seven more mistakes (below); all were fixed |
| C-4 | One unresolved package stops `fetch`, `render` and `install`, and `verify --live` skips the profile without saying so | High | Medium | The committed lock was resolved on a hosted runner, so it did not occur there, but the logic was wrong. There is now one validation path. An unresolved package is skipped with a note in the dev mode and refused in the other modes, `fetch` no longer needs the launches, and a live check that cannot run says so |
| C-5 | `dnx ... --yes` is documented as available from .NET 11 | Medium | Unverified | Learn says so, and NuGet's own template uses `--yes` on .NET 10. Nobody could run it (the runner has no `dnx` on its path). The manifest records the doubt and a fact checks the page |
| C-6 | On a machine with Claude Code, `install --apply` writes `.mcp.json`, which Copilot CLI reads before `.github/mcp.json` | Medium | Medium | Install defaults to Copilot CLI and VS Code, and writes the Claude Code file only when that host is named. `verify --live` fails when `.mcp.json` shadows the file of the profile |
| C-7 | First-run gaps: the trust prompt is not mentioned, the doctor hint is wrong, 56 skills are fetched and 57 listed | Medium | Medium | The README explains the trust and approval prompts and the start folder, the hint names the command that writes the file, and the counts are explained (56 upstream skills and 1 skill of the repository) |
| C-8 | `verify --live` and `doctor` accept stale or wrong-profile skills | Medium | Medium | Both compare the marker's profile and its whole skill set with the profile |
| C-9 | The router is missing from `list`, from the lint and from the load plan | Medium | Medium | Skills of the repository are part of the resolved profile, so `list`, the lint, `fetch` and the load plan include them |
| C-10 | Four statements about facts | Low | Low | Three were right: `fab` is needed by one skill only, the Power BI authoring page does state the 100,000-row limit (see the episode below), and the retirement wording was loose. The tool `powerbi-report-author` was added to the manifest. The `uv` minimum needs no change, since `uvx` arrived in 0.4 |
| C-11 | The lint reads 8 file types and skips large files without saying so | Low | Low | The lint reads every text file and reports a skipped file as a finding |

## Findings of reviewer A (the command line)

| ID | Finding | Rated | After the check | What was done |
|---|---|---|---|---|
| A-1 | Installing an agent profile at user scope keeps the dev servers, and a `.mcp.json` shadows the rendered file | High | Medium | Install is for people, and a job loads the plan with a clean configuration, so the impact is lower. Even so, the non-dev profiles now refuse `--scope user`, and a shadowing `.mcp.json` fails `verify --live` |
| A-2 | A server whose contract was never captured does not stop unattended work | High | High | `verify` warns about a non-dev profile with an uncaptured contract (a failure under `--strict`), and the load plan of such a profile is refused |
| A-3 | Agent load plans launch with a run-time installer (`npx -y`) | High | Medium | Non-dev load plans use the offline forms (`npx --offline`, `uvx --offline`) and say that the package is preinstalled. Provisioning stays the loader's job, and the README says so |
| A-4 | The load plan lacks the router | Medium | Medium | Fixed with C-9 |
| A-5 | The inputs digest omits the launches and the policy | Medium | Medium | The digest covers the launch commands, arguments and environments, and the ceilings of the agent and executor modes are in the code, not only in the editable allow-lists |
| A-6 | An offline lock refresh launders a changed source | Medium | Medium | `verify` compares the repository, path and tag pattern of each source with the lock, and `lock --no-network` refuses when they differ |
| A-7 | Rendering and installing bypass the V12 and V13 failures | Medium | Medium | One validation path serves `verify`, `render`, `fetch` and `install` |
| A-8 | A variant can set the license variable's default to true | Medium | Medium | The license variable is checked after the variant's environment is merged |
| A-9 | A marker with zero digests authorises deleting foreign content | Medium | Medium | The marker's profile, lock digest and each skill's digest are checked against the folder before anything is deleted, and a mismatch is a conflict |
| A-10 | A user's folder with a staging-shaped name is deleted | Medium | Medium | Staging folders have unique names and are created exclusively |
| A-11 | Install writes through a junction | Medium | Medium | The destination, its parents and the staging folder are checked for links, and for containment in the project |
| A-12 | A skill is replaced by deleting the old one first | Medium | Medium | The old folder is moved aside and put back when the replacement fails |
| A-13 | Live verification accepts an empty marker | Medium | Medium | Fixed with C-8 |
| A-14 | `doctor --offline` runs account checks | Medium | Medium | The sign-in checks are skipped offline, and `gh auth status --no-refresh` is used otherwise |
| A-15 | Public output keeps private strings from a probe | Low | Low | Server labels and versions from a probe are sanitised and token-shaped text is redacted |

## Findings of reviewer B (the helper modules)

| ID | Finding | Rated | After the check | What was done |
|---|---|---|---|---|
| B-1 | The tree kill runs whatever `taskkill` is first on the PATH | High | Medium | The command is called by its absolute path in the system folder. The impact is lower because the caller already runs code on the machine |
| B-2 | The "anonymous" Git fetch inherits the user's configuration and can run a command | High | High | Git runs in a private environment: no global or system configuration, the `ext` transport never, and a protocol allow-list |
| B-3 | Credential-free capture still passes registry tokens and proxy passwords | High | High | The child receives a fixed list of names, and the user information of a proxy address is removed |
| B-4 | `npm view` is trusted and uses the ambient registry | High | High, in part | It runs in a clean working folder, so a hostile project `.npmrc` is not read, and the registry is cross-checked. The user's own configuration stays trusted. An answer without an integrity hash is unresolved |
| B-5 | A `file://` URL with a host is a UNC path | Medium | Medium | Refused |
| B-6 | The digest follows Windows junctions out of the folder | Medium | Medium | A junction counts as a link |
| B-7 | The modern probe sends `initialize` first | Medium | Medium | The probe tries `server/discover` first; the change was proved against the real local Fabric server before it was accepted |
| B-8 | `safe_detail` keeps IPv6 addresses and `user:password` text | Medium | Medium | Both are removed, as are path-like tokens |
| B-9 | "Resolved" with no integrity, and a NuGet pin that is not the requested string | Medium | Medium | No integrity hash means unresolved. NuGet keeps the exact spelling and records the sha256 of the package |
| B-10 | A same-host redirect may change the port | Low | Low | The port is compared too |

## The mutations that survived

| Reviewer | Mutation that no test caught | What covers it now |
|---|---|---|
| A | The marker's profile is not validated | A test that installs over a marker of another profile |
| A | The marker's lock digest is not validated | A test with a marker of another lock |
| A | The old folder is deleted before the copy's digest is checked | A test that corrupts the staged copy and expects the old folder to survive |
| B | The shim character class drops `>`, drops CR and LF, or drops `&` (three mutations) | One test for each character |
| B | The walk no longer treats symbolic links as links | A mocked link test that does not need the right to create links |
| B | A `file://` URL with a host is accepted | A test with a host |

All 8 are now caught. The author re-proved this against the corrected code, which was rewritten and so no longer holds the reviewers' exact mutants: 3 mutations of the command line, 3 of the shim character class (one per character group) and 2 of the Git and digest helper, each killed by a named test. The implementation agents proved their new safeguards the same way, with 220 mutations of the command line and 284 of the helpers, all killed by the test meant for each. The author's own additions in this round (the router guard, the comparison of a user file, the generated folders of the publish script) were proved with 7 more mutations, all killed.

## Replay of the reviewers' reproductions

The reviewers described 23 reproductions of the command-line and first-run defects. A script replays each one in a scratch copy of a project tree, with a scratch home folder, and reports whether the defect still occurs. On the published commit all 23 reproduce. On the corrected tree none of them does. The script was written by the author from the reviewers' descriptions, so it shows that the described cases are closed and not that no other case exists. The corrected kit has not been reviewed again by other models at the time of writing.

## What the author added to the review

1. **The router and preamble were checked cold.** After the rewrite for C-3, Grok 4.7 read both texts against the pinned skills and the manifest. Seven problems: the SQL endpoint tool is called `execute_query` by the skill and the plugin and `executeSQL` by Learn (which one is current is unverified); the preamble gave a wrong reason for the executor mode (the executor may hold a workload identity and a Microsoft cloud network); `semantic-model-authoring` is MCP first but also uses TMDL files and Fabric REST; `sqldw-cli` uses `az rest` only for discovery and `sqlcmd` only as a fallback; `eventhouse-cli` and `activator-cli` name MCP servers that the kit does not load; the Azure plugin registers no server called `bicep`; and `powerbi-report-cli` is a CLI skill. It also listed pinned skills that tell the agent to install tools or to fall back without asking, which the preamble overrides on purpose. All were fixed, two skills that were not routed at all were added, and two facts now check the tool-name disagreement.
2. **The 100,000-row episode.** An earlier cold check by Grok said that the row limit of the DAX execution tools was not on the Power BI authoring page, and the grounding note was changed to say so. Reviewer C found the sentence on the page. The author fetched the page and confirmed it, the note was corrected again, and a fact now checks the sentence every week. A cold checker can be wrong; each disputed claim was re-fetched from its primary source before it was accepted, as in the earlier rounds.
3. **Claude Code was run once.** `claude mcp list` (version 2.1.162) in an empty scratch folder with its own configuration read the generated `.mcp.json`, found a stdio and an HTTP server and listed both as pending approval. No server was started.
4. **The shared folder.** The `common` folder has 25 files in `fabric-skills` and 3 in `powerbi-authoring`, and the three are byte-identical to files of the first. Two other upstream targets are broken at the pinned tag and cannot be fixed by the kit: four links to a `mcp-setup` folder that exists only at the repository root, and one to a skill folder that does not exist.
5. **Facts.** The fact list grew from 81 to 86 claims: the row-limit page, the `dnx --yes` page, the ontology retirement and the two statements about the SQL endpoint tool name.
6. **Found while integrating the fixes.** A real install in a scratch repository, checked with Copilot CLI, and then the first complete run of the suite and the first hosted run showed seven things that no reviewer had raised, each fixed with a test and mutations: `verify --live` printed one warning for every kit server that the user's own MCP file lacked, which is noise on any machine that has such a file, so that file is now compared only when it already holds a kit server (a user-scope install was made); the minimum Git version was 2.30, but the private Git environment that fixes B-2 relies on `GIT_CONFIG_GLOBAL`, which Git 2.32 introduced, so the minimum is 2.32 and a test pins it; the publish script and `.gitignore` did not know the two new generated folders (`.github/common`, `.claude/common`), so a person who had run `install` would have published 435 KB of upstream text; the router guard did not know the manifest's tools; a new fact gave a reason in its claim, which the facts tests forbid; `doctor` called `gh auth status --no-refresh`, a flag that exists only from `gh` 2.103.0 (read from the CLI's own history), so it reported "not signed in" on an older `gh` (it now asks again without the flag when, and only when, the flag is unknown); and two mocked junction tests read a constant of Python's `stat` module that exists only on Windows, which turned the hosted Linux run red for the published commit.

## What was not changed, and what is still open

- C-5 stays unverified: no `dnx` was available to run the Bicep server.
- Hosted servers are still never captured, because they need a sign-in. The Power BI authoring variants stay uncaptured until an operator who accepted its license runs the capture, and a non-dev profile that loads them has no load plan until then.
- VS Code was not run. Claude Code was run only to the point of listing the servers.
- Nothing was run against a tenant. The SQL endpoint tool name and the sign-in method of the Azure cost server need a live session to settle.
