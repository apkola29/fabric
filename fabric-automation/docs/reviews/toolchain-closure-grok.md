# Closure review of the toolchain kit, slice A: the command line (Grok 4.7)

The reply as it came back, with the agent's own header removed. Two example values that the document checks would read as a profile path and as a token are spelled out. It reviewed the published commit `a7932d1bf9` from a clean clone: whether the fixes of the first review closed the findings on the command line (A-1 to A-15 and C-4 to C-9), seven new findings (R-N1-1 to R-N1-7) and 31 mutations, none of which survived. The author's checks and the dispositions are in [toolchain-closure-findings.md](toolchain-closure-findings.md).

Closure review of the command line at `a7932d1`. Experiments were on scratch copies. No sign-in, no tenant call. `python -m unittest scripts.test_toolchain.InstallSafetyTests.test_a_failed_swap_puts_the_old_skill_back_and_leaves_nothing_behind` passed.

## Closure

**A-1 Closed.** `install --profile agent-intake --scope user` and the same for `executor-sandbox-read` exit 2: a user-level file is refused. `verify --live` fails when `.mcp.json` is not that profile's Claude rendering. Default `install` (Claude is on PATH here) plans only `.github/mcp.json` and `.vscode/mcp.json`.

**A-2 Closed.** `verify --profile agent-implementer` exits 0 with a V10 warning; `--strict` exits 1. `render --host load-plan` exits 1: no captured contract for `powerbi-authoring-local/offline-readonly`. Same for `executor-static-gates` and `executor-sandbox-read`. `agent-planner` (captured `fabric-local/docs`) still gets a plan.

**A-3 Partly closed.** The `agent-planner` plan is `npx --offline -y @microsoft/fabric-mcp@1.6.0 ...` with `provisioning: preinstalled`. The offline form is only inserted for the literal commands `npx` and `uvx` (R-N1-2). `-y` is still there.

**A-4 / C-9 Closed** for list, lint, and the load plan. `list --profile agent-planner` shows 3 skills including `toolchain/skills/factory-router`. `dev-factory` lists 57. Empty profiles stay empty. `fetch` does not copy the router into the pack; the plan points at the repository path, which a checkout has.

**A-5 Partly closed.** Widening `modes.agent.allow.network` to `internet` fails V1. A launch change makes the lock stale. `lock` and `lock --no-network` then re-stamp the digest and keep the old contract (R-N1-1).

**A-6 Closed.** Changing the Fabric source repository to `https://github.com/acme/other-skills.git`: `verify` exits 1, `lock --no-network` exits 1 and does not rewrite the lock, `verify` still exits 1.

**A-7 Closed for V12 and V13.** A bundled name `fabric-local`, and `read_only: false` on one docs tool, each make `verify` and `render --host load-plan` exit 1. V8 of the router and V11 are not on that path (R-N1-3).

**A-8 Closed.** A variant `env` that sets `PBI_MODELING_MCP_ACCEPT_EULA` default `true` fails V1: the license variable is set at the server level only.

**A-9 / A-13 / C-8 Closed.** A marker for `dev-docs` with an empty skill map: `verify --live --profile agent-planner` fails on profile, lock, missing skills (including `factory-router`), and missing `common`. `doctor --offline --profile agent-planner` fails the same skill checks.

**A-10 / A-11 Closed by tests and by reading the fix.** Staging is `mkdtemp`. `refuse_links` walks to the project or home boundary and treats junctions as links. The named restore test passed. I did not re-plant a skills-folder junction; the store junction is a different hole (R-N1-5).

**A-12 Partly closed.** The restore test passed. `install --apply` still prints `applied` before the swap, and a failed `os.replace` is an uncaught `OSError` (R-N1-7).

**A-14 Closed for offline.** `doctor --offline` prints `sign-in checks skipped offline` and does not run `gh` or `az` account checks. I did not run `gh auth status` (it would touch credentials). The retry is only when the output contains `unknown flag`.

**A-15 Partly closed.** A probe name `<profile path>\box` becomes `unknown`. The version `build.private.example`, the protocol path, and a tool name that is a path are stored (R-N1-6). `safe_detail` keeps `ghp_` plus 20 letters and `user:password`.

**C-4 Closed.** With `npm:@microsoft/fabric-mcp` unresolved: `verify --profile dev-docs` exits 0 with a warning; `agent-planner` exits 1. `render --host copilot-cli` for `dev-docs` omits that server and prints `note: server fabric-local is not rendered: its package is unresolved in the lock`. `verify --live` for the agent profile says live checks were skipped because the profile cannot be resolved.

**C-5 Not closed. Execution UNVERIFIED.** This machine's `dotnet` is 9.0.320; `dnx` was not run. The manifest launch is still `dnx` plus `{package}` plus `--yes`. Learn still says, under Options for `-y|--yes`: "Available starting with .NET 11." https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-tool-exec

**C-6 Closed** for the default install. Claude is on PATH; `install` without `--host` does not plan `.mcp.json`. A differing `.mcp.json` fails `verify --live`. `doctor` does not (R-N1-4).

**C-7 Partly closed.** The README trust and start-folder wording is present. The Claude MCP hint is `install --apply --host claude-code`. The skills hint is not (R-N1-4). `list` shows 57 for `dev-factory`.

## New findings

### R-N1-1 High. A changed launch keeps the old captured contract

**Where:** `scripts/toolchain.py`, lines 1673-1684, 1770-1772, and 1691-1702.

**What is wrong:** `merge_contract` keeps a captured contract when the package version is unchanged and no new capture was attempted. `lock` captures only with `--contracts`. `lock --no-network` rewrites `inputs_digest` whenever the skill-source identity still matches. The contract does not record the launch that produced it, so `verify` cannot see that the args changed. The test `test_no_network_still_re_derives_the_digest_when_everything_agrees` (`scripts/test_toolchain.py`, lines 1863-1867) requires this re-stamp even after the launch command is changed to `pnpm`.

**Evidence:** In `R:\cl2-a-scratch\attack-args`, the `fabric-local` / `docs` args were set to `server start --mode all` (the full variant; the committed docs variant also passes `--namespace docs`). `verify --profile agent-planner` exited 1 (stale). `lock --no-network` exited 0. `verify` then reported 0 failures. `render --host load-plan` exited 0 with args `--offline -y @microsoft/fabric-mcp@1.6.0 server start --mode all` and a captured contract whose tools were still only `docs_api-examples`, `docs_best-practices`, `docs_item-api-spec`, `docs_item-definitions`, `docs_list-item-types`, `docs_platform-api-spec`.

The same refresh after dropping `--read-only` from `fabric-local` / `read` (`R:\cl2-a-scratch\attack-exec`): `verify --profile executor-sandbox-read` exited 0 (one pre-existing V10 warning). `server_launch` returned `npx -y @microsoft/fabric-mcp@1.6.0 server start --mode all`. The contract stayed captured, 34 tools, none marked not read-only. That variant is the one `executor-sandbox-read` loads, and that mode is allowed `azure-identity`.

An in-process `build_lock(..., contracts=False)` with the docs args widened did not call the probe, changed the digest, and kept the old contract byte for byte.

**Fix:** If the command, args, or env of a captured variant change, drop that contract (or refuse the refresh) until `--contracts` recaptures it. Record the launch in the contract and fail verify when they differ.

### R-N1-2 Medium. `--offline` is a name match, and a blessed rename drops it

**Where:** `scripts/toolchain.py`, lines 61 and 1453-1455.

**What is wrong:** Non-dev plans insert `--offline` only when `command` is exactly `npx` or `uvx`. They still say `provisioning: preinstalled`. A renamed launcher is a launch change, which R-N1-1's refresh accepts.

**Evidence:** In `R:\cl2-a-scratch\attack-npxcmd`, `fabric-local.launch.command` was set to `npx.cmd`. `lock --no-network` exited 0. `verify --profile agent-planner` exited 0. The load plan command was `npx.cmd` and the args did not contain `--offline`. npm's own exec page says `-y` installs a package that is not already available. https://docs.npmjs.com/cli/v10/commands/npm-exec/

**Fix:** For every non-dev stdio launch, require an offline form or refuse the command. Do not set `provisioning` to `preinstalled` unless that form is present. Drop `-y` from non-dev plans.

### R-N1-3 Medium. The single validation path still skips V8 of the router and V11

**Where:** `scripts/toolchain.py`, lines 2348-2360 and 2120. `resolve_profile` (lines 1362-1406) does not call either check.

**What is wrong:** `verify` fails. `render --host load-plan` and `install` do not.

**Evidence:** After padding the router description past 1024 characters (`R:\cl2-a-scratch\attack-lint`), `verify --profile agent-planner` exited 1 (`repo-owned skill factory-router: description longer than 1024 characters`). `render --host load-plan` exited 0. `install --skip-skills` exited 0. After emptying `contracts["fabric-local/docs"].tools` (`R:\cl2-a-scratch\attack-v11`), `verify` failed V11 and `render --host load-plan` exited 0 with `"tools": {}`.

**Fix:** Raise those failures from `resolve_profile`, so render, fetch of a profile, and install cannot proceed.

### R-N1-4 Medium. `doctor` misses a shadowing `.mcp.json`, and one hint does not fix Claude skills

**Where:** `scripts/toolchain.py`, lines 3082-3096 and 3060.

**What is wrong:** `doctor` compares each host file with its own rendering and never runs the precedence check. Default `doctor` includes Claude when `claude` is on PATH. The skills hint is `install --apply`, which does not install `.claude/skills`.

**Evidence:** With `.mcp.json` containing `{"mcpServers":{"fabric-local":{"type":"stdio","command":"evil","args":["x"]}}}` (`R:\cl2-a-scratch\attack-doctor`), `doctor --offline --host copilot-cli` exited 0 and printed `[PASS] host copilot-cli mcp: .github/mcp.json equals the rendering of profile dev-factory`. `verify --live --host copilot-cli` exited 1: `.mcp.json takes precedence over .github/mcp.json`. GitHub's page says: "If both `.mcp.json` and `.github/mcp.json` exist in the same directory, `.mcp.json` takes precedence." https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers

Default `doctor --offline` on this machine also printed `[WARN] host claude-code skills: no skills are installed in .claude/skills (run: python scripts/toolchain.py install --apply)`. That command does not target Claude. `doctor --profile agent-planner` tells you to run `render --write-project`, which writes the default profile, not `agent-planner`.

**Fix:** Run the same precedence check as `verify --live`. Put `--host claude-code` on the Claude skills hint, and include `--profile` when the profile is not the default.

### R-N1-5 Medium. `fetch` writes the pack through a junction

**Where:** `scripts/toolchain.py`, lines 2632-2656. `refuse_links` is not called on the store. `store_op` (lines 2761-2778) is the same for `install`.

**What is wrong:** Skill destinations are checked for links. The pack directory is not. A junction at `.factory` is a write outside the project.

**Evidence:** `cmd /c mklink /J R:\cl2-a-scratch\attack-junction\.factory R:\cl2-a-scratch\junction-outside` succeeded. `is_link` on that path was true, and `refuse_links` would have raised. `fetch --profile agent-planner` with `vendor_skills` stubbed to write `WROTE.txt` exited 0 and created `R:\cl2-a-scratch\junction-outside\pack\WROTE.txt`.

**Fix:** Refuse a link on the store, its parents up to the project root, and the staging directory inside it, before `fetch` or `install` writes.

### R-N1-6 Medium. Probe text still reaches the lock

**Where:** `scripts/toolchain.py`, lines 1629-1661 and 230-235. Tool names are not checked (`_check_tools_map`, lines 851-856). `SERVER_VERSION_RE` allows dotted names.

**What is wrong:** The name whitelist does not cover protocol, tool names, or host-shaped versions. `safe_detail` keeps underscore tokens and `user:password`.

**Evidence:** A fake probe returned name `<profile path>\box`, version `build.private.example`, protocol `<profile path>\token`, and a tool named `<profile path>\tool`. `capture_contract` for `fabric-local/docs` returned status `captured`, name `unknown`, version `build.private.example`, protocol `<profile path>\token`, and that tool name as a key. `safe_detail("ghp_" + "a"*20 + " and user:password@host")` returned `ghp_<20 letters> and user:password host`.

**Fix:** Allow tool names and protocol only as plain tokens. Reject a version that matches a host. Strip token-shaped words and `user:password` in `safe_detail`.

### R-N1-7 Low. `install` says `applied` before it applies

**Where:** `scripts/toolchain.py`, lines 2988-2994. `main` (line 3252) catches `ToolchainError` only.

**What is wrong:** The summary is printed, then the swaps run. A failed rename is not turned into exit 1.

**Evidence:** With `os.replace` raising `OSError('rename fault')`, `install --profile dev-docs --host copilot-cli --skip-skills --apply` printed `applied: profile dev-docs, 0 to add, 1 to change, 0 unchanged, 0 conflict(s)` and then the exception propagated. The restore test shows the old skill folder is put back when the swap fails inside `_copier`.

**Fix:** Print `applied` only after every apply returns. Catch `OSError` and exit 1.

## Mutations

31 mutations of a scratch copy, each followed by `python -m unittest scripts.test_toolchain` (413 tests). None survived.

Caught: each mode-ceiling attribute and the unattended ceiling; unattended required; quarantine wildcard; stale check in verify and in `Project.load`; digest parts launch, server env, variant env, variant args, modes, quarantine; shared-subset early return; marker profile, lock, and skill digest; digest check before swap; restore of the old folder; `refuse_links` no-op and the apply-time `guard` in `_copier`; unique staging; modified-folder conflict; load-plan refusal; `--offline` insert; license variant and license default; `--scope user`; `.mcp.json` shadow; user-file guard (`needs_one` always returns).

## Checked and fine

Mode ceilings reject an edited allow-list at load. Quarantine, stale lock, and source identity still fail closed. V12 and V13 stop render. Dev omits an unresolved package with a note; agent refuses it; live verify says the check was skipped. The license variable cannot be re-defaulted on a variant. Marker profile, lock, and skill set are checked by both `verify --live` and `doctor`. A user MCP file with only a foreign server is not compared; one that already has `fabric-local` is. `doctor --offline` runs no sign-in check. The `agent-planner` plan includes the router, `common`, and `--offline`. Empty profiles stay empty. Default install does not write `.mcp.json`.
