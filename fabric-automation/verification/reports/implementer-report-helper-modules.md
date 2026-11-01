# Implementer Y: the report on the fixes of the helper modules

The report as the implementing agent returned it, with the header of the agent removed. The briefs are in [briefs](../briefs/). The files that the report names under the temporary folder (`%TEMP%\fa-r9-y-...`) were scratch files and are not kept; the reviewers' replies and the author's checks of the same fixes are in [docs/reviews](../../docs/reviews/toolchain-delta-findings.md).

All seven items are done and every mutation was killed, with the platform and equivalence caveats in §3. Two real-process caveats: Linux was not run, and the symlink variants could not be made on this account, so the link tests used a junction.

## 1. Files and counts
Only the six allowed files changed; they are CRLF and pyflakes-clean.

| File | Lines |
|---|---|
| `toolchain_io.py` | +12 −3 |
| `toolchain_mcp.py` | +10 −4 |
| `toolchain_sources.py` | +52 −24 |
| `test_toolchain_io.py` | +68 −1 |
| `test_toolchain_mcp.py` | +153 −20 |
| `test_toolchain_sources.py` | +609 −24 |

Test counts, and the last three lines of the final run of each module:

| Module | Before → after | Last three lines |
|---|---|---|
| io | 112 → 118 | `Ran 118 tests in 35.341s` · `OK (skipped=1)` |
| mcp | 137 → 146 | `Ran 146 tests in 124.066s` · `OK` |
| sources | 277 → 305 | `Ran 305 tests in 864.160s` · `OK (skipped=1)` |

The skips are old tests (a POSIX decoy test in io; a test that needs a symlink in sources). None of my new tests skipped.

## 2. Items
**Y-1.** `fetch_git` refuses a link at `dest`, then calls `_remove(dest)` and makes a fresh bare repository. `_remove` tests `lexists` itself, so I call it without a guard. The "reset config, `_has_commit`, return" shortcut is gone; `_reset_cache_config` stays after `git init`. I also mapped a failed `mkdir` to a source error, because `mkdir` now runs on every call.
- New messages: `unresolved: cannot remove the old cache folder` and `unresolved: cannot make the cache folder`.
- Tests: `StaleCacheTests` — commondir (with plain-git control), link inside `objects` (control writes outside, ours leaves the outside folder byte-identical), `reference-transaction` hook, junk and alternates, file in place of cache. Also `VendorLinkTests` link-inside-cache, `VendorTests.test_one_call_fetches_each_commit_once…`, and `GitIsolationTests` unit tests for both messages and for a template that leaves `config` as a folder or hard link.

**Y-2.** `_run_alone` sets `HOME`, `USERPROFILE` and `XDG_CONFIG_HOME` to its empty working folder and removes `HOMEDRIVE` and `HOMEPATH`.
- Environment audit, measured against a loopback TLS server (control = plain git):
  - `NETRC` is honoured by this Git's libcurl; HOME, and USERPROFILE or HOMEDRIVE+HOMEPATH when HOME is unset, also leak credentials.
  - `GIT_SSL_CERT` makes git offer a client certificate.
  - `CURL_HOME`, `XDG_CONFIG_HOME`, `NETRC_FILE`, `CURL_NETRC`, `GIT_NETRC`, `SSL_CERT_FILE` and `CURL_CA_BUNDLE` do nothing.
  - Once HOME is set, USERPROFILE and HOMEDRIVE/HOMEPATH are not consulted.
- Decision: `_GIT_NETWORK_DROPPED` now also drops `NETRC`, `GIT_SSL_CERT`, `GIT_SSL_KEY` and `GIT_SSL_CERT_PASSWORD_PROTECTED`.
- Left alone: proxy variables and `GIT_PROXY_SSL_*` (they go to the proxy only), trust settings such as `GIT_SSL_CAINFO` and `GIT_SSL_NO_VERIFY` (not credentials), and local trace variables.
- Tests: `AnonymousGitTests` runs four real-process cases against a throw-away CA made with Git for Windows' openssl, each with a plain-git control: home netrc, `default` entry for `localhost`, `NETRC`, and client certificate. `resolve_git_ref` and `fetch_git` each make their request with no `Authorization` header and no client certificate. Unit tests check the overlay, that the folder is the cwd, empty, present during the call and gone after, and the child environment via `merged_env`.
- The wrapper also injects `-c http.sslBackend=openssl` on Windows. `GIT_CONFIG_NOSYSTEM=1` drops Git for Windows to schannel, which ignores `http.sslCAInfo`.

**Y-3.** `_stage_failure` now checks 404/410 first, so those statuses win over a body error and give `<label> not found` with kind `notfound`. 403, 429, 5xx and a missing response keep the CLI fallback. The docstrings of `_stage_failure` and `_resolve_npm` say what is now true.
- The same shared helper changes pypi and nuget, so I added tests there too.
- A run without the npm CLI now returns reason `unresolved`, detail `npm missing - registry not found` (it used to be `network`, `… registry too-large`).
- Tests: `StageFailureTests` (table), plus npm, pypi and nuget cases over all nine body-error words that `_get` can report, checked against `classify_exception`.

**Y-4.** `_legacy` raises `protocol-error: unsupported protocol version` for a date not in `HANDSHAKE_VERSIONS`, before `notifications/initialized`. A non-date value keeps its old message.
- The test that accepted `2027-01-01` is replaced by accept and refuse tests (`2027-01-01`, `9999-99-99`, `0000-00-00`, `2026-07-28`, and dates between or before the revisions), asserting `server.sent == ["initialize"]`.
- Real stand-in test: the log is `["server/discover","initialize"]` and the server is gone.
- `CommittedLockTests` reads the committed lock.
- `ToolNameTests` plus a real test keep the three `onelake_create-shortcut-*` names intact.

**Y-5.** `make_writable` does nothing when `st_nlink > 1` on Windows; a path it cannot examine behaves as before. Tests are mocked (nlink 1, 2, 3, unexaminable, real hard link with `WINDOWS` patched) plus real Windows tests, including a `fetch_git`-level one where the outside file stays 0o444.

**Y-6.**
- (a) The expectation now includes `ENV_ALLOW_NPM`; tokens, passwords, a `NPM_CONFIG_` credential not in the list and a proxy password still never arrive; new test with the npm names set.
- (b) Starts are counted parent-side by wrapping `popen_tree`.
- One extra fix: my own full mcp run, under heavy load, failed a log assertion because the first process woke and logged `server/discover`. The stand-in's first process (made by `O_EXCL` marker `FAKE_FIRST`) now sleeps 10 s and its replacement does not sleep. The full module then passed.

**Y-7.** No change, and I do not disagree. A purely alphabetic label can only carry what the server chooses to say.

## 3. Mutations (all killed)
Specs and logs are in `%TEMP%\fa-r9-y-tmp\` (`spec-*.json`, `mut-*.log`). A mutant that survived one spec was killed by another unless marked equivalent.

| Id | File | Change | Killed by |
|---|---|---|---|
| y5-ignore-nlink | io | nlink check removed | mocked "more than one name"; Windows real tests |
| y5-ge-1, y5-gt-2 | io | `>= 1`, `> 2` | `test_a_read_only_file_with_one_name…` (Windows real); mocked "more than one name" |
| y5-unexaminable-left-alone | io | unexaminable path returns | mocked "cannot be examined" |
| y3-old-order, y3-only-404, y3-only-410, y3-403-authoritative, y3-5xx-authoritative | sources | order restored, one status only, extra statuses | `StageFailureTests` and npm/pypi/nuget tests |
| y4-accept-any-date, y4-after-initialized, y4-accept-modern | mcp | check dropped, moved after the notify, modern accepted | refuse tests, unit and real stand-in |
| y4-newest-only, y4-oldest-only | mcp | accept only one revision | "taken as it is" and six real stdio tests |
| y4-constant-without-legacy, y4-constant-modern-changed | mcp | constants changed | `CommittedLockTests`, pin test, real oldest/newest test |
| tool-names-checked-as-secrets | mcp | `_suspect` applied to tool names | `ToolNameTests`, real real-names test |
| y6-npm-credential-allowed, y6-npm-settings-dropped, y6-proxy-password-kept | mcp | env rules broken | real env tests plus existing `CaptureEnvTests` |
| y6-restart-starts-two, y6-restart-starts-none | mcp | restart changed | the three counted-start tests |
| y1-old-shortcut, y1-no-removal, y1-no-config-reset-after-init | sources | shortcut kept, removal dropped, reset dropped | unit and real stale-cache tests |
| y1-removal-follows-links | sources | `_rmtree` follows links | both real link tests (junction) |
| y1-removal-failure-swallowed, y1-mkdir-failure-raised, y1-no-link-refusal | sources | error mapping and refusal dropped | unit tests |
| y1-fetch-per-skill | sources | memo dropped | `VendorTests` once-per-commit |
| y2-no-HOME, y2-home-not-for-init | sources | HOME dropped, overlay skipped for `init` | unit; HOME also by the real netrc tests |
| y2-NETRC-kept, y2-GIT_SSL_CERT-kept, y2-network-drops-not-applied | sources | credential names kept | unit and real tests |
| y2-network-drops-in-local-calls | sources | network drops applied to local calls | `PrivateGitSettingsTests` local-call test |
| y2-no-USERPROFILE, y2-no-XDG_CONFIG_HOME, y2-home-removed-not-set, y2-HOMEDRIVE-kept, y2-HOMEPATH-kept | sources | variable dropped, or HOME removed instead of set | unit only |
| y2-GIT_SSL_KEY-kept, y2-GIT_SSL_CERT_PASSWORD_PROTECTED-kept | sources | name kept | unit only |

- **Real tests cannot see (unit only).**
  - USERPROFILE, XDG_CONFIG_HOME, HOMEDRIVE and HOMEPATH are not consulted once HOME is set, so real tests cannot see them.
  - HOME removed instead of set cannot be seen by a real test on either platform. On POSIX libcurl would read the passwd home, which is not the synthetic folder.
  - Dropping only `GIT_SSL_KEY` is equivalent in a real run.
- **Windows only.** The real hard-link tests and the junction link tests.
- **Linux.** Not run, so the `onexc` branch of `_rmtree` was not mutated.
- **Request-time TLS.** The four TLS tests skip when openssl is missing or git does not read the netrc or trust the CA.

## 4. Existing tests changed
- Inverted on purpose: `FetchGitTests.test_a_second_call…` and `test_another_commit_can_join…`; `GitIsolationTests.test_an_existing_cache_gets_the_minimal_configuration…` and `test_a_cache_that_already_holds_the_commit…`; the two `VendorTests` "rewritten from the cache without a new fetch" tests. The reason is that an old cache is never reused.
- Replaced: `InitializeTests.test_a_protocol_version_that_is_a_date_is_taken_as_it_is`, because it accepted `2027-01-01`.
- Fixed: `StdioTests` env expectation; the three counted-start tests and `modern-slow-named`; the stand-in sleep.
- Strengthened: `assertEmptyFolderOfItsOwn`, the `NETWORK_DROPPED` constant, and the local-call loop.
- Helper: `remove_folder_link` now acts only on a real link. Without that change, cleanup failed after `fetch_git` replaced a junction with a real folder.
- Comment only: the one above `test_a_registry_that_cannot_be_reached…`.
- Still passes, for a new reason: `test_a_cache_whose_configuration_cannot_be_written_is_a_source_error` now fails at the removal step.

## 5. Documents
- `toolchain/README.md` line 128 is now wrong. Suggested text: "The cache of the pack is local state and is never trusted: the kit removes a cache folder (never following a link inside it) and fetches the commit into a new one whenever it needs it."
- `docs/reviews/toolchain-closure-findings.md` lines 45 and 95 describe the old replace-before-use and "hooks and alternates not neutralised" state.
- Optional README addition: a server that answers `initialize` with a revision the probe does not speak is not captured.

## 6. Found, not fixed
- `make_writable` calls `os.chmod`, which follows a link. This only happens if an unlink of a link fails, and the effect is limited to a folder's attribute.
- `read_plugin`, `digest_git_tree`, `read_shared_entries` and `_has_commit` trust whatever `git_dir` they are given (commondir, promisor, alternates). They are safe only because every caller passes a cache made in the same run. A `GIT_NO_LAZY_FETCH` guard would be cheap.
- `fetch_git` does not check the ancestors of `dest`; `vendor_skills` guards `.cache` itself, but a direct call does not.
- Windows integrated authentication (Negotiate/NTLM) is a logon-session credential, not an environment one, and was not tested.
- By design: the MCP child receives HOME, USERPROFILE and APPDATA; the npm CLI reads the operator's `~/.npmrc`.
- `GIT_SSL_NO_VERIFY` in the operator's shell still disables certificate checking for the anonymous calls.
