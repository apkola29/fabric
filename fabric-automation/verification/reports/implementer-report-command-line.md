# Implementer X: the report on the fixes of the command line

The report as the implementing agent returned it, with the header of the agent removed. The briefs are in [briefs](../briefs/). The files that the report names under the temporary folder (`%TEMP%\fa-r9-x-...`) were scratch files and are not kept; the reviewers' replies and the author's checks of the same fixes are in [docs/reviews](../../docs/reviews/toolchain-delta-findings.md).

**Round 9, implementer X: D1-1…D1-10 and D2-1 are done.** Only `scripts\toolchain.py` and `scripts\test_toolchain.py` changed. The full module passes. Every mutation I wrote is killed, with two explained exceptions listed under 3. The per-mutant log with killing tests is at `%TEMP%\fa-r9-x-mutation-table.txt`, and the 89 added test names are in `%TEMP%\fa-r9-x-added-tests.txt`.

**1. Files and counts**
- `toolchain.py`: 3573 → 3665 lines (+193/−101).
- `test_toolchain.py`: 6935 → 8274 lines (+1372/−33).
- Tests: 535 (OK, skipped=1) → 620 (OK, skipped=8). That is 89 added and 4 renamed. The 7 new skips are real-symlink tests that need a privilege this account lacks. The junction and mocked variants of the same bodies ran.
- Run on the original `toolchain.py`, the new test file has 67 failing tests: 63 new ones and the 4 changed ones. The other 26 new tests pass there on purpose: the 7 skipped symlink tests, and guards for survivors of earlier rounds (M08, M17, M39, M43, M46, M47) and for unchanged behaviour. A rebuilt copy of the original test file gives 535 OK on the original code.

**2. Items**

**D1-1** `cmd_fetch` now runs every selected profile through `resolve_profile`, with `_lint_once` for the repo skills. The old select/lint code is gone.
- Decisions: the default selection is still "profiles with skills". A profile named with `--profile` is resolved even if it only has servers.
- Message changed: `profile <n> does not verify` plus `profile <n>: <problem>`, replacing `profile <n> cannot load its skills`.
- Tests (OneValidationPathTests): locked_skill_with_a_finding_stops_fetch…, repo_owned_skill_with_the_name_of_a_locked_skill_stops_fetch, …bad_name_stops_fetch…, fetch_resolves_each_profile…lints_a_repo_owned_skill_once, a_profile_without_skills_is_resolved_too_when_it_is_named, fetch_of_the_committed_project…; two renamed (see 4).

**D1-2** `VERSION_SUFFIX` is shared by `EXACT_VERSION_RE` and the new `READ_VERSION_RE`, and `read_version` keeps the suffix. `1.8.0-beta.2` and `1.8.0rc1` no longer count as `1.8.0`, and the same pre-release does match its own pin. `at_pin` is unchanged. Tests: HelperTests ×2, ToolPinTests ×1.

**D1-3** Links are refused in four places.
- `refuse_resolve_links` runs in `cmd_lock` (not `--no-network`) and in `cmd_update`. It covers the pack, what lies above it, and `.cache`.
- `copy_tree`, `repo_skill_folders`, `instruction_problems`, and `store_problems` through the new `_pack_folder_problem`.
- Tests: LinkTests (24, mocked, junction and symlink variants), plus pack-listing and malformed-MANIFEST tests.
- Decisions:
  - A link that is not behind a skill is ignored.
  - Instructions name the outermost linked folder.
  - `store_problems` does not look at the pack folder itself.
  - I also fixed a crash on a MANIFEST skill entry that is not an object.
- New texts:
  - `toolchain/skills is a link; the toolchain reads the skills of this repository from real folders only`
  - `toolchain/skills/<name> is a link; …` (same ending)
  - `instructions '<file>' is behind a link: its folder '<folder>' is a link`
  - `the local pack holds <skill X | the shared folder Y> behind a link; the toolchain reads the pack from real folders only`
  - Existing texts now reached from new places: `<path> is a link; the toolchain does not write through links`, and `<name> holds a symbolic link; skills are copied, never linked` (now also for a junction and for the folder itself).

**D1-4** `_check_contracts` adds, after the package-version check, a V10 WARN and a `continue` when the contract's launch digest differs from the manifest's. The probe is never run in that case. Tool names in drift messages go through `_clean_label`. Text: `contract <key> was not launched: it was captured for another launch (capture it again with python scripts/toolchain.py lock --contracts)`. Tests: ContractCheckTests ×4.

**D1-5** `lock_package_problems(manifest, lock)` returns `(missing, differs)`. `refresh_digest(manifest, old, deps, profiles=None)` raises `a changed package pin needs a lock with the network`, with these lines:
- `the lock has no entry for package <k>`
- `the lock has version <v> for package <k>, but the manifest pins <p>`
- `the lock has no resolved version for package <k>, but the manifest pins <p>`

With profiles given (`cmd_lock` passes them), an unused variant's contract whose launch changed is dropped with the same note, and a used one is still replaced by a placeholder. Decision: an unresolved entry with a pinned (non-latest) track counts as a difference. Tests: LockCommandTests ×6.

**D1-6**
- `main` now catches `SourceError` too and prints `error: <safe detail or type>`, exit 1.
- `_measured` returns None for a folder that cannot be measured. `_has_content`, `_managed_ops` (managed branch and removal loop), `skills_dir_problems` and `store_problems` use it.
- `remove_tree` unlinks files and links, never walks a link, and keeps the retry wait.
- New texts: `managed skill <X> in <label> cannot be measured (it is not a readable folder)`; `shared folder <where> cannot be measured (it is not a readable folder)`; `the local pack holds <what> that cannot be measured (it is not a readable folder)`.
- Tests: InstallSafetyTests ×4 plus 7 `remove_tree` tests, SharedInstallTests ×2, InstalledStateTests ×2, SharedPackTests ×1, CliTests ×2.

**D1-7**
- `install_command(profile, default, hosts)` is now the source of every hint:
  - `run: python scripts/toolchain.py install --apply`, plus ` --host claude-code` for a host that install does not pick on its own, plus ` --profile <n>` only for a non-default profile.
  - `mcp_hint`, `_check_precedence` and `skills_dir_problems` take their hint as a required argument.
- Changed texts: `… was installed for profile <p>, not profile <n> (<hint>)` (was always `--profile <n>`), `… has no managed skills marker (<hint>)`, the project-file-missing and precedence hints.
- Tests: HostTests ×3, one InstalledStateTests change.

**D1-8** `_check_contract` and `_server_label` now apply `toolchain_mcp.suspect` to the server name and version. Tool names are not subject to it, because real names such as `onelake_create-shortcut-s3-compatible` are flagged. Text: `<where>.server.<name|version>: must not read like a token, a host name or an address` (the value is not echoed). A capture stores such a label as `unknown`. Tests: SchemaTests ×3, one LockCommandTests capture test. The committed lock still validates.

**D1-9** `probe_environment` treats an empty string as unset: the default is used, or the variable is left out; an empty license variable is not passed. Tests: ProbeEnvironmentTests ×2; the first also compares the result with `toolchain_mcp.capture_env`.

**D1-10**
- M46: `remove_tree` is tested with a `mock.Mock` handler function (called once, after `make_writable`) and with an unmocked read-only file.
- M39: unit tests of `bounded_environment`.
- M43: the license variable is tested at the `lock --contracts` and `verify --contracts` level, and `license_variables` on its own.
- M17: a profile with servers and no skill is refused by `resolve_profile`, `render` and `install`. A second test covers `profile_problems`.
- M08: later-day re-captures where only the era, protocol, server, package version or nothing changed.
- M47: the shared and skill twins of "unmarked folder with the pinned content is adopted".

**D2-1** `resolve_source` creates the parent folder, then always calls `deps.fetch_git(repo, commit, git_dir, deps.runner)` once per source before reading. The `fresh` logic, the retry branch and the `remove_tree` call there are gone. Tests: four in LockCommandTests (fetch once per source even when the folder exists; a junk folder is passed to the fetch untouched; the parent folder exists at fetch time; a failed read is an error with no second fetch, for both plugin read paths) and one renamed in SharedLockCommandTests.

**3. Mutations** (all in `toolchain.py`; 148 distinct)

| ids | change | killed by (first) |
|---|---|---|
| D11-a,b,c,d,e,g (6) | old select/lint code back; `deps` dropped; shared folders dropped; tuple order; no `_lint_once`; mcp-only profiles selected by default | a_locked_skill_with_a_finding_stops_fetch…; fetch_resolves_each_profile…once; fetch_of_the_committed_project…; a_profile_without_skills_is_resolved_too… |
| D12-a…f (6) | suffix grammar, pad-zero compare, `read_version` return, own copy of the regex | a_pre_release_is_not_the_pinned_release…; an_exact_version_is_accepted_with_a_prerelease… |
| L1a–e (5) | guard missing in lock, in update, also before `--no-network`, `.cache` unchecked, pack unchecked | …junction_in_the_way_of_the_pack…; lock_without_the_network_resolves_nothing… |
| L2a–c, L3a–c, L4a–d, L5a–e (15) | `copy_tree` source, entry type, files only; skills folder and entry; any link entry; instructions (off, nearest, deepest, base); pack link, skills dir, shared, pack folder itself, non-object listing entry | copy_tree_refuses…; the_skills_of_this_repository_are_read_from_real_folders_only; instructions_behind_a_link…; a_folder_of_the_pack_that_is_a_link…; a_pack_listing_with_an_entry_that_is_not_an_object… |
| D4a–g (7) | launch check off, inverted, WARN→FAIL, no `continue`, before the package check, drift names not cleaned, message cut | a_contract_captured_for_another_launch…; …and_another_launch_is_reported_for_the_package_version_only; the_tool_names_of_a_drift_are_cleaned… |
| D5a–n (14) | missing/differs not noticed, latest needs equality, unresolved worded as a version, check skipped, lines not listed, profiles not passed, used set wrong or inverted, note lost, tool packages ignored | lock_without_the_network_refuses…; the_offline_refresh_without_the_profiles…; a_contract_of_a_variant_no_profile_uses… |
| D6a–p (16) | `main` loses OSError or SourceError, prints only the type, exits 0; `_measured` re-raises or returns ""; raw `digest_tree` at 6 call sites; 3 "cannot be measured" branches off; "differs" off | a_folder_that_cannot_be_measured_and_that_nothing_caught…; a_managed_folder_that_cannot_be_measured_counts_as_modified; a_pack_folder_that_cannot_be_measured… |
| R1–R10 (10) (= M46 R6–R10) | `remove_tree`: link/file branches off, no `make_writable` or retry, link made writable, no rmdir fallback, handler without `function()` or `make_writable` | a_link_is_removed_without_clearing…; a_folder_with_a_read_only_file…; …windows_refuses_to_delete_for_a_moment… |
| D7a–u (21) | each hint loses host or profile, is plain, or the default is computed wrongly | the_hints_of_live_verification…; the_hints_for_a_profile_other_than_the_default…; the_hint_for_a_skills_folder…; …precedence… |
| D8a–f (6) | suspect off, name only, version only, value echoed, applied to tool names (killed by the committed lock), capture label not made `unknown` | a_server_name_or_version_that_the_probe_would_not_store…; the_committed_lock_is_valid…; a_label_that_reads_like_a_token… |
| D9a–f (6) | empty license passed, empty is a value, default never used, None passed, default wins, whitespace counts | an_operator_variable_that_is_empty…; …license_variable_of_the_server_is_handed_on_only_when… |
| M39a–h (8), M43a–d (4) | `bounded_environment` removes nothing, only exact case, only lower case, everything, wrong day, wrong hour, no npm, no uv; the license argument dropped at both call sites, `license_variables` empty, only-own skip | the_bound_replaces_the_operators_own_variables…; a_real_server_process_sees_the_date_bound…; the_license_variable_goes_to_the_server_that_declares_it… |
| M17a–c (3), M08a–h (8), M47a–c (3) | lint only for profiles with skills (three places); `without_date` ignores era, protocol, server, tools, launch, package_version, or keeps the date; always keep; unmarked folder never adopted (shared or skill) or always adopted | a_profile_that_has_servers_and_no_skill…; …in_its_own_problems; a_capture_on_a_later_day…; …another_package_version_is_replaced…; a_folder_that_holds_the_pinned_content_without_a_marker… |
| D2a–j (10) | fetch only when the folder is absent; retry branch (plain and shared read); no parent mkdir; fetch per plugin; no runner; short commit; other folder; remove before or after | a_cache_folder_that_holds_junk…; every_resolution_fetches_each_source_once…; a_read_that_fails_on_the_freshly_fetched_cache… |

Mutants that first survived and were closed by a test:
- D4e (launch check before the package check): the new ordering test kills it.
- M17b (`profile_problems`): the new test kills it.
- M08f (`without_date` ignoring `package_version`): the new `merge_contract` unit test kills it.
- M47b: my spec lacked the class that holds the skill twin; re-run with it, killed.

Explained and discarded:
- D11-f (drop `base=project.dir`): equivalent, because `profiles.base == project.dir`; I removed the redundant argument.
- M43e: an invented "also skip names ending in `_ACCEPT`" mutant tied to no rule of the brief; discarded, not claimed.

**4. Existing tests changed**
1. `test_fetch_is_not_stopped_by_a_contract_that_lists_no_tool` is now `…fetch_is_stopped_by_a_captured_contract_that_lists_no_tool_like_every_other_command`. Fetch now stops, per D1-1.
2. `test_fetch_is_not_blocked_by_what_only_concerns_the_servers…` is now `…fetch_is_stopped_by_what_concerns_the_servers_of_a_profile_it_works_for`.
3. `ToolPinTests.test_fetch_is_about_skills…` is now `…fetch_is_stopped_by_an_unresolved_tool_package_of_an_agent_profile…`.
4. `InstallTests.test_a_symbolic_link_in_the_store_is_refused` now mocks `toolchain.is_link`, the kit's one link test, instead of `Path.is_symlink`.
5. `InstalledStateTests.test_a_profile_with_servers_only_still_installs_and_needs_the_router`: the hint now names `--profile dev-docs` (D1-7).
6. `SharedLockCommandTests.test_a_stale_cache_is_refetched_and_read_again…` is now `…a_read_that_fails_on_the_freshly_fetched_cache_is_an_error_for_the_source_and_is_not_fetched_again` (D2-1).
7. `InstallSafetyTests.test_what_is_removed_has_its_read_only_attribute_cleared…`: the handler's function is now a `mock.Mock` asserted once (M46).
8. `SchemaTests.test_a_server_label_is_a_plain_name_and_a_plain_version`: the valid name `A1 b_c.d-e` is now `A1 b_c 2.5-e`, and `5.3.20.RELEASE` is no longer a valid version.
9. `SchemaTests.test_a_server_version_starts_with_a_digit…`: `5.3.20.RELEASE` moved to the invalid list. Both are host-like under D1-8.
10. `LockCommandTests.test_a_contract_of_a_variant_no_profile_uses_is_kept_only_while_its_launch_is_the_same`: after `lock --no-network` the unused contract is gone, not a placeholder (D1-5b).
11. Fixture `server_label` no longer allows dots, for the same reason.

**5. README / design document**
- README V8 row ("render, install and fetch stop on them too"): now also true for locked-skill findings in agent mode on fetch.
- README V11 ("every command stops on it"): now true for fetch.
- README V10 ("with --contracts every captured server is launched again"): no longer true for a contract captured for another launch (WARN, not run).
- README Limits line on `.factory/pack/.cache` ("a hook or alternates file in an existing cache folder is not neutralised"): obsolete with D2-1 plus `fetch_git`, since the cache is deleted and rebuilt every time. It should now say that a link at the cache folder is refused.
- `docs/04-design.md` §3.13, Toolchain kit row ("A job's profile is loaded and verified before the job starts"): now also true for `fetch`.
- The README says nothing about `lock --no-network`, the hints or `error:` lines.

**6. Found and not fixed**
- `lock --no-network` still keeps entries that `lock` would drop: non-captured contracts of an unused variant, and contracts of a removed server or variant. The existing `gone/default` test wants this.
- A printed `1.8.0.dev3` or `1.8.0.post1` still reads as `1.8.0`.
- In offline `verify`, a `SourceError` from `lint_skill` now gives only the `error:` line, not a V8 FAIL plus the other findings.
- Hints for a user-scope skills folder in `verify --live` lack `--scope user`; `install_command` has no scope.
- `lock` and `update --write` write the lock file, and `render --output` and `update --summary-file` write their files, without the link test. These are the user's own tree and an explicit path.
- `toolchain_sources.digest_tree` reads through a link at the root of the walk (why `store_problems` tests it). `.cache/<commit12>` itself is left to `fetch_git` (D2-1 assumes it refuses a link and replaces the folder).
- The 7 real-symlink tests have not run on this machine, and the `os.rmdir` fallback in `remove_tree` is reached only by mock here.

Last three lines of the final full run (`python -m unittest scripts.test_toolchain`, with a blank line after the first):
```
----------------------------------------------------------------------
Ran 620 tests in 194.383s
OK (skipped=8)
```
