# Closure check of the toolchain kit after the third review, slice A: the command line (Gemini 4 Argon)

The reply as it came back, with the agent's own header removed. It checked the published commit `2231f55f7a` from a clean clone: whether the fixes closed its ten findings of the third review (R-D1-1 to R-D1-10) and the six mutations that had survived, a read of the whole diff of `scripts/toolchain.py` and its tests since `abe6b9d614`, 37 new mutations (2 survived) and five new findings (R-E1-1 to R-E1-5). The one more point in its diff review that it did not number is R-E1-6 in the findings file. The author's checks and the dispositions are in [toolchain-recheck-findings.md](toolchain-recheck-findings.md).

Checked out `2231f55f7a` in `R:\cl3-a`. All reproductions and mutations were run on scratch copies under `R:\scratch-cl3-a-r4` (cleaned up afterwards) with `R:\cl3-a` untouched.

---

## 1. Closure of Round 3 Findings (`R-D1-1` to `R-D1-10`) and Surviving Mutations

### Findings `R-D1-1` to `R-D1-10`

- **R-D1-1 (`fetch` bypassed `profile_findings`; README V11 wording): Closed.**
  - *Re-run:* In a scratch copy with `"findings": ["description longer than 1024 characters"]` added to `semantic-model-authoring` in `toolchain/toolchain.lock.json`, `python scripts/toolchain.py fetch --profile agent-planner` now calls `resolve_profile`, prints `error: profile agent-planner does not verify: skill skills-for-fabric/powerbi-authoring/semantic-model-authoring has findings: description longer than 1024 characters`, and exits `1` without calling `vendor_skills`. `toolchain/README.md`, line 82 now scopes V11 to `verify`, `render`, `install`, `fetch`, and the load plan.
- **R-D1-2 (`read_version` and `at_pin` stripped PEP 440 pre-release suffixes): Closed.**
  - *Re-run:* `VERSION_SUFFIX` (`scripts/toolchain.py`, line 87) is shared by `EXACT_VERSION_RE` and `READ_VERSION_RE`. `toolchain.read_version("fab 1.8.0rc1")` returns `((1, 8, 0), 'rc1')`, `at_pin("fab 1.8.0rc1", "1.8.0")` returns `False`, `at_pin("fab 1.8.0a1", "1.8.0rc1")` returns `False`, and dotted suffixes (`1.8.0.dev3`, `1.8.0.post1`) are also distinguished from `1.8.0` while ignoring sentence-ending periods.
- **R-D1-3 (`lock`, `update`, `copy_tree`, `repo_skill_folders`, and `instruction_problems` link traversal): Partly closed.**
  - *What held:* With a Windows junction at `.factory` pointing to an outside folder, both `python scripts/toolchain.py lock` and `python scripts/toolchain.py update` now call `refuse_resolve_links` (`scripts/toolchain.py`, lines 3044–3046), print `error: .factory is a link; the toolchain does not write through links`, and exit `1` with nothing written outside. `copy_tree` checks `is_link(source)` and `is_link(Path(folder) / entry)`, `instruction_problems` checks parent folders with `is_link`, `repo_skill_folders` checks `is_link(root)` and `is_link(entry)`, and `store_problems` checks `is_link(skills_dir) or is_link(folder)`.
  - *What remains:* `repo_skill_folders` (`scripts/toolchain.py`, lines 2171–2188) checks `is_link` only on `toolchain/skills` and `toolchain/skills/<name>`, not on entries *inside* `<name>` (contradicting `docs/reviews/toolchain-delta-findings.md`, table row R-D1-3, which states that the repo-owned skill check refuses a link "at the folder or inside it"). A junction or symlink inside `toolchain/skills/factory-router` passes `verify`, `render --host load-plan`, `fetch`, and `list` (see **R-E1-2**).
- **R-D1-4 (`verify --contracts` launched a server whose launch changed): Closed (author's decision verified and sound).**
  - *Re-run & Judgment:* Changing `fabric-local/docs` `args` in `toolchain.json` and running `run_verify(..., profile_names=["agent-planner"], contracts=True)` no longer calls `probe_stdio` (`launched == []`). It emits `[FAIL] V10` from `profile_findings` (`was captured for another launch`) and `[WARN] V10: contract fabric-local/docs was not launched: it was captured for another launch` from `_check_contracts` (`scripts/toolchain.py`, lines 2609–2611), and cleans tool names in drift reports with `_clean_label` (line 2620). Using `WARN` + `continue` in `_check_contracts` is the right design because `profile_findings` already emits the `FAIL V10` for every profile using that contract, avoiding duplicate `FAIL V10` lines while preventing execution of the unreviewed launch.
- **R-D1-5 (`lock --no-network` accepted changed package pins and left `skipped` placeholders for unused variants): Closed.**
  - *Re-run:* Setting `fabric-local.package.track` to `"1.7.0"` in `toolchain.json` and running `python scripts/toolchain.py lock --no-network` now exits `1` with `error: a changed package pin needs a lock with the network` (`the lock has version 1.6.0 for package npm:@microsoft/fabric-mcp, but the manifest pins 1.7.0`). For an unused variant whose launch changed, `refresh_digest` deletes the contract key when `profiles` is given, matching `build_lock` so `lock --check` exits `0`.
- **R-D1-6 (Uncaught `SourceError` on unmeasurable/file-replaced managed skill folders): Closed.**
  - *Re-run:* Replacing `.github/skills/factory-router` with a regular file after `install --apply` and running `install --apply` exits `1` with `! skill factory-router: modified since it was installed; use --force to replace it` (no traceback); running with `--force` unlinks the file via `remove_tree`, installs the directory, and exits `0`. `main` (`scripts/toolchain.py`, line 3667) also catches `toolchain_sources.SourceError` as an `error:` line.
- **R-D1-7 (Hints in `skills_dir_problems`, `_check_skills_dir`, and `_check_live`): Partly closed.**
  - *What held:* All four project-scope hint sites now call `install_command` / `mcp_hint` with the host and profile. For `.claude/skills` installed for `dev-docs`, `doctor --host claude-code --profile agent-planner` now prints `(run: python scripts/toolchain.py install --apply --host claude-code --profile agent-planner)`.
  - *What broke:* Adding `--scope user` to `install_command` in `_check_live` (`scripts/toolchain.py`, lines 2486–2496, 2562–2563, and 2573–2574) introduced two broken hints for user-scope files: (1) for an `agent` or `executor` profile, `verify --live --profile agent-planner` tells the operator to run `python scripts/toolchain.py install --apply --profile agent-planner --scope user`, which `cmd_install` refuses with exit code `2` (`UsageError: a user-level file is shared by everything this user runs`); (2) for a differing server entry in `$HOME/.copilot/mcp-config.json`, `verify --live` tells the operator to run `install --apply --scope user` without `--force`, which exits `1` on conflict (see **R-E1-1**).
- **R-D1-8 (`SERVER_VERSION_RE`, `SERVER_NAME_RE`, and `TOOL_NAME_RE` vs `toolchain_mcp.suspect`): Closed (author's decision verified and sound).**
  - *Re-run & Judgment:* `_check_contract` (`scripts/toolchain.py`, lines 905–908) and `_server_label` (line 1749) now enforce `not toolchain_mcp.suspect(value)` on `server.name` and `server.version`; `"1.host-1.com"`, `"1.web2.com"`, `"pkgs.contoso.invalid"`, IPv4 literals, and 30-character tokens all become `"unknown"` on capture and fail `validate_lock`. Checking `toolchain/toolchain.lock.json` directly with `[t for t in c["tools"] if toolchain_mcp.suspect(t)]` confirmed the author's claim: in `fabric-local/full`, `onelake_create-shortcut-adls-gen2`, `onelake_create-shortcut-amazon-s3`, and `onelake_create-shortcut-s3-compatible` all have 24+ character letter-and-digit runs (`create-shortcut-adls-gen2` is 25 chars, `create-shortcut-amazon-s3` is 25 chars, `create-shortcut-s3-compatible` is 29 chars) that trigger `_token_like`. Exempting tool names from `suspect` while keeping `TOOL_NAME_RE` (`[A-Za-z0-9_.-]{1,128}`) is therefore justified.
- **R-D1-9 (`probe_environment` passed `""` for empty operator variables): Closed.**
  - *Re-run:* `toolchain.probe_environment({"ACME_MODE": {"from_env": "ACME_MODE", "default": "safe"}, "ACME_TARGET": {"from_env": "ACME_TARGET"}}, {"ACME_MODE": "", "ACME_TARGET": ""}, None, ())` now returns `{'ACME_MODE': 'safe'}`, and an empty license variable `""` is also treated as unset.
- **R-D1-10 (`remove_tree` test passed when `function(target)` was dropped): Closed.**
  - *Re-run:* `InstallSafetyTests` (`scripts/test_toolchain.py`, lines 4392–4430) now asserts `function.assert_called_once_with(inner)` and `steps == ["chmod", "function"]`, and adds unmocked tests removing a read-only file inside a folder and a standalone read-only file.

### Six Round 3 Surviving Mutations (`M39`, `M43`, `M46`, `M17`, `M08`, `M47`)

All 6 mutations that survived in Round 3 are **KILLED** on `2231f55f7a`:
1. **`M39_bounded_env_keep_operator_entries`** -> **KILLED** (4 failures in `ProbeEnvironmentTests`).
2. **`M43_probe_env_callsites_omit_license_variables`** -> **KILLED** (1 failure in `ContractCheckTests`, plus 1 in `LockCommandTests`).
3. **`M46_remove_tree_drop_function_call`** -> **KILLED** (3 failures in `InstallSafetyTests`).
4. **`M17_repo_lint_resolve_profile_skills_only`** -> **KILLED** (5 failures in `OneValidationPathTests`).
5. **`M08_without_date_ignore_era_protocol_server`** -> **KILLED** (1 failure in `LockCommandTests`).
6. **`M47_has_content_shared_folder_skipped`** -> **KILLED** (1 failure in `SharedInstallTests`).

---

## 2. Diff Review (`abe6b9d614..2231f55f7a`)

Reading the full diff of `scripts/toolchain.py` and `scripts/test_toolchain.py` identified four issues in the new code and its interactions:

1. **Broken user-scope hints and false `FAIL V9` in `_check_live` (`scripts/toolchain.py`, lines 2560–2575; `scripts/test_toolchain.py`, lines 5881–5885).** `_check_live` now passes `scope="user"` into `install_command` for `$HOME/.copilot/mcp-config.json` and `$HOME/.copilot/skills`. First, when `verify --live` runs on an `agent` or `executor` profile and `$HOME/.copilot/skills` has a marker from a `dev` install, `_check_live` fails the `agent`/`executor` profile on the user's home folder and prints `run: python scripts/toolchain.py install --apply --profile <agent-profile> --scope user`—a command that `cmd_install` rejects with exit code `2`. Second, when `$HOME/.copilot/mcp-config.json` holds a differing entry for a server, `_entries_missing` suggests `install --apply --scope user` without `--force`, which fails with exit code `1` (`! mcp-user ... differs (use --force to replace it)`). In `HostTests.test_the_hint_for_a_user_mcp_file_names_the_scope_and_the_lines_for_a_project_file_have_no_hint` (`scripts/test_toolchain.py`, lines 5881–5884), the test overwrote `user_file` to remove the differing `"docs"` entry before calling `self.run_the_hint(hint)`, masking the fact that the hint fails on a differing entry.
2. **Incomplete link check for repo-owned skills (`scripts/toolchain.py`, lines 2171–2188).** `repo_skill_folders` checks `is_link(root)` and `is_link(entry)`, but does not check if `(entry / "SKILL.md")` or any entry inside `entry` is a link. Because `lint_skill` and `digest_tree` treat links inside a folder as regular files holding their link target, `verify`, `render --host load-plan`, `fetch`, and `list` all pass when a junction or symlink sits inside `toolchain/skills/factory-router`, while `install --apply` fails in `copy_tree`.
3. **`remove_tree` `unlink_link()` turns a transient Windows lock on a file symlink into an immediate `NotADirectoryError` (`scripts/toolchain.py`, lines 221–228).** In `unlink_link()`, `except OSError: os.rmdir(path)` assumes any `os.unlink` failure means `path` is a junction. If `path` is a file symlink on Windows that is momentarily held open (`PermissionError`, `winerror=5`), `os.unlink(path)` raises `PermissionError`, `except OSError:` catches it and calls `os.rmdir(path)`, which raises `NotADirectoryError` (`winerror=267`). Because `transient_refusal` (`scripts/toolchain_io.py`, line 146) returns `False` for `NotADirectoryError` (`winerror=267`), `retrying(unlink_link)` aborts on the first attempt without retrying.
4. **Bare `fetch` regression when a server or tool package is unresolved on a restricted network (`scripts/toolchain.py`, lines 2943–2950).** Because `cmd_fetch` without `--profile` resolves all profiles that have `skills` (including `agent-planner`, `agent-test-author`, and `agent-implementer`), and an unresolved npm package in the lock is a V3 `FAIL` in `agent` mode, a developer on a network that blocks npm who runs `lock` followed by bare `fetch` (as `toolchain/README.md`, lines 100–101 describes) can no longer vendor skills without passing `--profile dev-factory`.

---

## 3. Mutation Results

37 new mutations (`N01`–`N37`) targeting the safeguards added in `2231f55f7a` were executed against scratch copies of `scripts/toolchain.py` by running `python -m unittest scripts.test_toolchain` (628 tests; 620 run, 8 real-symlink tests skipped on unprivileged Windows). **35 of 37 were killed** and **2 survived all 628 tests**:

### Mutations that NO test noticed (2 survivors)

1. **`N36_doctor_skills_wrong_hint_to_skills_dir_problems` (`scripts/toolchain.py`, line 3466):**
   - *Mutation:* In `_doctor_skills`, replace `skills, shared = skills_dir_problems(project, deps, resolved, directory, rel, marker, hint)` with `skills, shared = skills_dir_problems(project, deps, resolved, directory, rel, marker, INSTALL_HINT + " --profile " + resolved["name"])` (reverting `_doctor_skills` to the pre-R-D1-7 hint that omits `--host claude-code`).
   - *Why no test noticed:* `HostTests.test_the_hint_for_a_skills_folder_that_was_installed_for_another_profile_names_the_host_of_that_folder` (`scripts/test_toolchain.py`, lines 5800–5809) only tests `verify --live --host claude-code --profile agent-ok` (which goes through `_check_skills_dir`), and no test runs `doctor --host claude-code` when `.claude/skills/.toolchain-managed.json` records a different profile.
2. **`N37_store_problems_shared_entry_not_isinstance_dict` (`scripts/toolchain.py`, line 2258):**
   - *Mutation:* In `store_problems`, change `if not isinstance(entry, dict) or entry.get("digest") != item["digest"]:` (for `shared` folders) to `if entry is None or entry.get("digest") != item["digest"]:`.
   - *Why no test noticed:* `LinkTests.test_a_pack_listing_with_an_entry_that_is_not_an_object_is_a_warning_and_not_a_crash` (`scripts/test_toolchain.py`, lines 5365–5370) sets `pack["skills"]["gamma"] = "not an object"`, but never tests a non-dict entry in `pack["shared"]`.

### Mutations that WERE killed (35 of 37)

- **`VERSION_SUFFIX` (`N01`–`N03`):** Dropping `\.(?=[A-Za-z])`, dropping `(?=[A-Za-z])`, or allowing a trailing period — all 3 killed by `SchemaTests`, `PackageTests`, and `HelperTests`.
- **`remove_tree` (`N04`–`N06`):** Dropping `make_writable(path)` on a file, dropping `retrying` on `unlink_link`, or dropping `retrying` on file `os.unlink` — all 3 killed by `InstallSafetyTests`.
- **`suspect` on server name/version (`N07`–`N09`):** Applying `toolchain_mcp.suspect` only to `version`, only to `name`, or dropping it from `_server_label` — all 3 killed by `SchemaTests` and `LockCommandTests`.
- **`instruction_problems` link depth (`N10`–`N11`):** Checking only `parts[:1]` or only `parts[:len(parts)]` — both killed by `LinkTests`.
- **`resolve_source` fresh cache (`N12`):** Skipping `fetch_git` when `git_dir.is_dir()` — killed by `LockCommandTests`.
- **`probe_environment` empty values (`N13`–`N15`):** Reverting `base.get(own)` to `own in base`, keeping `""`, or stripping whitespace `" "` — all 3 killed by `ProbeEnvironmentTests`.
- **`refresh_digest` and `lock_package_problems` (`N16`–`N18`):** Skipping `lock_package_problems`, keeping `skipped` placeholders for unused variants, or dropping `used is None` — all 3 killed by `LockCommandTests`.
- **`repo_skill_folders`, `store_problems`, and `copy_tree` link checks (`N19`–`N23`, `N34`–`N35`):** Dropping `is_link(root)` or `is_link(entry)` in `repo_skill_folders`, `is_link(skills_dir)` or `is_link(folder)` in `store_problems`, `measured is None` in `_pack_folder_problem`, `is_link(source)` in `copy_tree`, or reverting `copy_tree` to `.is_symlink()` — all 7 killed by `LinkTests` and `SharedPackTests`.
- **Hints, `_check_contracts`, `refuse_resolve_links`, and `cmd_fetch` (`N24`–`N33`):** Dropping `--scope user` in `install_command`, dropping user MCP/skill hints in `_check_live`, dropping `measured is None` for shared folders in `skills_dir_problems`, dropping the launch check or `_clean_label` in `_check_contracts`, dropping `refuse_resolve_links` in `cmd_lock` or `cmd_update` or `.cache` in `refuse_resolve_links`, or dropping `_lint_once` in `cmd_fetch` — all 10 killed.

---

## 4. New Findings

### R-E1-1 Medium. `verify --live` checks user-scope files for `agent`/`executor` profiles and emits hints that fail (`UsageError` exit 2, or conflict exit 1 without `--force`)

- **Where:** `scripts/toolchain.py`, lines 2385–2388, 2486–2496, 2560–2575, and 3297–3299; `scripts/test_toolchain.py`, lines 5881–5885.
- **What is wrong:**
  1. `cmd_install` (`scripts/toolchain.py`, lines 3297–3299) forbids `--scope user` for `agent` and `executor` profiles (`UsageError`, exit code 2). However, `_check_live` (lines 2560–2575) still inspects `mcp_user` (`$HOME/.copilot/mcp-config.json`) and `skills_user` (`$HOME/.copilot/skills`) when verifying an `agent` or `executor` profile. If a developer has installed a `dev` profile at `--scope user` and runs `verify --live --profile agent-planner` (or `verify --live --profile dev-factory agent-planner`), `_check_live` fails `agent-planner` on `$HOME/.copilot/skills` and instructs the user to run `python scripts/toolchain.py install --apply --profile agent-planner --scope user`, which fails with exit code `2`.
  2. When `$HOME/.copilot/mcp-config.json` holds a differing entry for a server in `dev` mode, `_entries_missing` (line 2387) emits the hint `run: python scripts/toolchain.py install --apply ... --scope user` without `--force`. Running that command fails with exit code `1` because `mcp_user_ops` (lines 3260–3265) treats a differing user server entry as a conflict unless `--force` is passed.
- **Evidence:** In a scratch copy after `install --profile dev-docs --scope user --host copilot-cli --apply`:
  - `run_verify(..., profile_names=["agent-planner"], live=True, hosts=["copilot-cli"])` emitted `[FAIL] V9: $HOME/.copilot/skills was installed for profile dev-docs, not profile agent-planner (run: python scripts/toolchain.py install --apply --profile agent-planner --scope user)`, and running that hinted command exited `2`.
  - Editing `fabric-local` in `$HOME/.copilot/mcp-config.json` and running `verify --live --profile dev-docs --host copilot-cli` emitted `[WARN] V9: $HOME/.copilot/mcp-config.json holds a different entry for the server fabric-local (run: python scripts/toolchain.py install --apply --profile dev-docs --scope user)`, and running that hinted command exited `1` (`1 conflict(s)`).
- **Suggested fix:** In `_check_live` (lines 2560 and 2566), check `mcp_user` and `skills_user` only when `resolved["mode"] == "dev"`; and in `_entries_missing` (line 2387), append `" --force"` to `hint` on the `elif servers[sid] != entry:` branch.

### R-E1-2 Low. `repo_skill_folders` does not check for links inside a repo-owned skill folder, contrary to `toolchain-delta-findings.md`

- **Where:** `scripts/toolchain.py`, lines 2171–2188; `docs/reviews/toolchain-delta-findings.md`, line 39 (table row R-D1-3).
- **What is wrong:** `docs/reviews/toolchain-delta-findings.md` states for R-D1-3 that "the folder of the skills of this repository ... use the junction-aware link test and refuse a link, at the folder or inside it." However, `repo_skill_folders` (`scripts/toolchain.py`, lines 2171–2188) checks `is_link(root)` and `is_link(entry)` only, never walking inside `entry`. Because `toolchain_sources.lint_skill` and `digest_tree` hash links inside a directory as files holding their target path, a junction or symlink inside `toolchain/skills/factory-router` passes `verify`, `render --host load-plan`, `fetch`, and `list` (exiting `0`), and only fails when `install --apply` calls `copy_tree`.
- **Evidence:** Creating a junction `mklink /J <proj>\toolchain\skills\factory-router\linked-dir <outside>` and running `python scripts/toolchain.py --root <proj> verify` and `render --host load-plan --profile agent-planner` both exited `0` (with `"files": 2` in `repo_skills`).
- **Suggested fix:** In `repo_skill_folders` (line 2180), also refuse when any entry inside `entry` (including `entry / "SKILL.md"`) satisfies `is_link`.

### R-E1-3 Low. `remove_tree` does not retry a transiently locked file symlink on Windows (`os.rmdir` raises `NotADirectoryError`, `winerror=267`)

- **Where:** `scripts/toolchain.py`, lines 221–228; `scripts/toolchain_io.py`, lines 141–146.
- **What is wrong:** In `remove_tree`, `unlink_link()` catches any `OSError` from `os.unlink(path)` and immediately calls `os.rmdir(path)`. On Windows, if `path` is a symbolic link to a file (not a directory junction) and is momentarily held open by a scanner or sync client (`PermissionError`, `winerror=5`), `os.unlink(path)` raises `PermissionError`, and the fallback `os.rmdir(path)` raises `NotADirectoryError` (`[WinError 267] The directory name is invalid`). Because `toolchain_io.transient_refusal` returns `False` for `NotADirectoryError` (`winerror=267`), `retrying(unlink_link)` aborts on the first attempt without waiting or retrying. On POSIX, `unlink_link()` also replaces any `PermissionError` from `os.unlink(path)` on a symlink with `Errno 20 Not a directory` from `os.rmdir(path)`.
- **Evidence:** In `InstallSafetyTests.test_a_file_and_a_link_that_windows_refuses_to_delete_for_a_moment_are_deleted_after_a_pause` (`scripts/test_toolchain.py`, lines 4460–4465), the test passed only because it mocked `os.rmdir` to raise `PermissionError` and mocked `transient_refusal` to return `True` for all errors.
- **Suggested fix:** In `unlink_link()`, fall back to `os.rmdir(path)` only on Windows when `os.unlink(path)` fails on a directory/junction reparse point (or if `os.rmdir(path)` raises `NotADirectoryError`, re-raise the original `OSError` from `os.unlink(path)` so `transient_refusal` sees the `PermissionError`).

### R-E1-4 Low. Non-UTF-8 or unreadable `.github/mcp.json` or `.vscode/mcp.json` aborts `verify` and `doctor` (including `--json`) instead of recording a finding

- **Where:** `scripts/toolchain.py`, lines 2361 and 3488.
- **What is wrong:** `_check_precedence` (`scripts/toolchain.py`, lines 2475–2478) wraps `read_text_lf(path, ...)` in `try ... except ToolchainError: same = False` so a corrupt `.mcp.json` is reported as a `FAIL` finding. By contrast, `_check_project_files` (line 2361, V5 in `verify`) and `_doctor_hosts` (line 3488, in `doctor`) call `read_text_lf(path, ...)` without catching `ToolchainError`. If `.github/mcp.json` or `.vscode/mcp.json` contains non-UTF-8 bytes (e.g., `b"\xff\xfe"`), `read_text_lf` raises `ToolchainError`, aborting `verify` and `doctor` before remaining checks run and suppressing JSON output under `--json`.
- **Evidence:** Writing `b"\xff\xfe"` to `.github/mcp.json` in a scratch copy and running `python scripts/toolchain.py verify --json` or `python scripts/toolchain.py doctor --offline --json` printed `error: .github/mcp.json: the file is not valid UTF-8` to `stderr` with empty `stdout` instead of a JSON report.
- **Suggested fix:** Catch `ToolchainError` around `read_text_lf` in `_check_project_files` and `_doctor_hosts` and record a `FAIL` (V5) or `WARN` (`host <host> mcp`) finding, just as `_check_precedence` and `_entries_missing` do.

### R-E1-5 Low. Surviving mutations `N36` and `N37` show two untested branches in `_doctor_skills` and `store_problems`

- **Where:** `scripts/toolchain.py`, lines 2258 and 3466; `scripts/test_toolchain.py`, lines 5365–5370 and 5800–5809.
- **What is wrong:** As shown in Section 3, mutating `_doctor_skills` (line 3466) to pass `INSTALL_HINT + " --profile " + resolved["name"]` (without `--host claude-code`) into `skills_dir_problems` (`N36`) and mutating `store_problems` (line 2258) to drop `not isinstance(entry, dict)` on `listed_shared` (`N37`) both survive all 628 tests in `scripts/test_toolchain.py`.
- **Evidence:** Running `python -m unittest scripts.test_toolchain` against copies of `scripts/toolchain.py` with `N36` and `N37` applied exited `0` (`Ran 628 tests — OK (skipped=8)`) for both.
- **Suggested fix:** Add a `doctor --host claude-code --profile agent-ok` assertion to `HostTests.test_the_hint_for_a_skills_folder_that_was_installed_for_another_profile_names_the_host_of_that_folder`, and add `pack["shared"]["common"] = "not an object"` to `LinkTests.test_a_pack_listing_with_an_entry_that_is_not_an_object_is_a_warning_and_not_a_crash`.
