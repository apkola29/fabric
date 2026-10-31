# Review of the toolchain kit, slice B: the helper modules (Grok 4.7)

The reply as it came back, with the agent's own header removed, and with line references written as "file, lines N" (the document checks cannot resolve `file:line`). One example version number that looks like an address is spelled out. It reviewed the published commit `3494fe4223` from a clean clone: the process and HTTP helper, the MCP probe, and the Git, skill and package helper, with 35 mutations. The author's checks and the dispositions are in [toolchain-review-findings.md](toolchain-review-findings.md).

## Baseline

Commit `3494fe4223`. Baseline from `R:\clone-b\fabric-automation`: `python -m unittest scripts.test_toolchain_io scripts.test_toolchain_mcp scripts.test_toolchain_sources`: 233 tests, 1 skipped, OK, 108.7 s. The clone was not modified. Mutations ran on copies under `R:\scratch-b\muts`.

## Findings

### R-B-1 High: tree kill runs whatever `taskkill` is on PATH

Where: `scripts/toolchain_io.py`, line 160 (`_taskkill`), used by `kill_tree` at line 185.

`shutil.which("taskkill")` wins over `%SystemRoot%\System32\taskkill.exe`. A `taskkill.cmd` earlier on PATH is executed. `proc.kill()` ends only the direct child.

Evidence: PATH prefixed with `R:\scratch-b\taskkill-probe` (a `taskkill.cmd` that writes a marker and exits 0). `which` returned `taskkill.CMD`. After `kill_tree`, the direct child was dead, the marker existed, and a grandchild process was still alive.

Fix: call `%SystemRoot%\System32\taskkill.exe` by absolute path, or use a Job Object with `KILL_ON_JOB_CLOSE`. Do not search PATH.

### R-B-2 High: "anonymous" git fetch inherits config and can run a command

Where: `scripts/toolchain_sources.py`, line 164 and `fetch_git` at line 347. `SystemRunner.run` inherits the parent environment. Git then reads `GIT_CONFIG_GLOBAL` and the global git configuration file. `-c credential.helper=` does not disable `url.*.insteadOf` or `protocol.*.allow`.

Evidence (host `invalid.invalid` only):

1. `GIT_CONFIG_GLOBAL` rewrote `https://invalid.invalid/repo.git` to a local bare repository. `fetch_git` returned, and `git cat-file -t <sha>` printed `commit`.
2. A config with `[protocol "ext"] allow = always` and an `insteadOf` rewrite to an `ext::` helper made `fetch_git("https://invalid.invalid/ext.git", ...)` run the helper. A marker file was created. Without `allow = always`, git said `transport 'ext' not allowed` and the marker was absent.
3. Control: `-c credential.helper=` did stop a global credential helper. That flag works. It is not sufficient.

Fix: private git environment: empty `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM=1`, no `GIT_CONFIG_COUNT`, and `-c protocol.ext.allow=never`.

### R-B-3 High: credential-free capture still receives registry tokens and proxy passwords

Where: `scripts/toolchain_mcp.py`, lines 49-57 and `capture_env` at line 147. The comment says a secret in the operator shell must not reach a credential-free capture. The allow-list copies every `npm_config_*` name and `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` verbatim.

Evidence: `capture_env(None, parent)` kept the per-registry `_authToken` variable, `NPM_CONFIG__AUTH`, and proxy URLs with passwords in the userinfo. `GITHUB_TOKEN`, `NPM_TOKEN`, and `AZURE_CLIENT_SECRET` were not copied. The captured process is the untrusted server (HR-3).

Fix: allow only a fixed `npm_config_` set (`registry`, `cache`, `cafile`, `ignore-scripts`). Strip proxy userinfo.

### R-B-4 High: `npm view` is trusted, and it uses the ambient registry

Where: `scripts/toolchain_sources.py`, lines 794-798. The first stage that succeeds is the answer. `runner.run` inherits the environment, so npm honors `npm_config_registry` and a project `.npmrc`.

Evidence: a localhost server answered `GET /left-pad` with version `9.9.9` and an attacker-chosen `sha512-` integrity. `resolve_package("npm", "left-pad", "latest")` returned that pair with `"via": "npm-cli"`. The only request was to the loopback address. A separate `npm view` against a closed local port hung, so the CLI does follow `npm_config_registry`.

Fix: pass `--registry https://registry.npmjs.org/`, or skip the CLI. Accept a CLI result only when it matches the official registry document.

### R-B-5 Medium: `file://` URLs with a host are UNC paths

Where: `scripts/toolchain_sources.py`, line 149. Any `file` URL is allowed, and `_network_argv` sets `protocol.file.allow=always`.

Evidence: `_check_url("file://invalid.invalid/share/repo.git")` returned true. Git printed `fatal: '//invalid.invalid/share/repo.git' does not appear to be a git repository`. That is a UNC path. I did not capture an NTLM handshake (UNVERIFIED that Windows sent credentials).

Fix: allow `file` only when the hostname is empty.

### R-B-6 Medium: `digest_tree` follows Windows junctions out of the folder

Where: `scripts/toolchain_sources.py`, line 94. `is_symlink()` is false for a junction, so `_walk` recurses. Symlinks are hashed as the target string. Junctions are followed. `vendor_skills` calls `digest_tree` on the staged tree.

Evidence: a folder with only `SKILL.md` plus `mklink /J leak <outside>`. `leak.is_symlink()` was false. `digest_tree` returned `"files": 2`. The second file is outside the folder.

Fix: treat `IO_REPARSE_TAG_MOUNT_POINT` as a link, as `_is_link` already does for deletion.

### R-B-7 Medium: modern probe speaks `initialize` first

Where: `scripts/toolchain_mcp.py`, lines 370-374.

The stdio spec says a dual-era client should probe with `server/discover` before any other request, and fall back to `initialize` only if discover errors or times out. An `UnsupportedProtocolVersionError` must not fall back to `initialize`. Source: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio (Backward Compatibility): "A client that supports both modern ... and a legacy version ... SHOULD probe with `server/discover` before sending any other request."

Evidence: a stand-in that answers `server/discover` and `tools/list` and ignores `initialize` produced `McpProbeError: timeout: no answer to initialize` after 8.4 s. A spec-compliant modern server that does not answer `initialize` cannot be pinned. The job stops (HR-12), which is fail-closed, but the contract is never recorded.

Fix: call `server/discover` first. Use `initialize` only when discover errors or times out.

### R-B-8 Medium: `safe_detail` keeps IPv6 addresses and `user:password` text

Where: `scripts/toolchain_io.py`, lines 62-72. There is an IPv4 pattern and an `@` pattern. No IPv6 pattern. `:` and `=` are allowed.

Evidence:

- `failed connecting to 2001:db8:85a3::8a2e:370:7334` is unchanged.
- `basic alice:s3cret-token rejected` is unchanged.
- `cannot open Users\alice\secrets\token.txt` becomes `cannot open Users alice secrets`.

Absolute paths, `https://` URLs, dotted hostnames, and `user@host` are removed. Those tests hold.

Fix: strip IPv6 and `user:secret` tokens. Re-run the host pattern after the character filter.

### R-B-9 Medium: "resolved" with no integrity, and a NuGet pin is not the requested string

Where: `scripts/toolchain_sources.py`, line 791 (jsDelivr always `integrity: None`), line 845 (NuGet the same), line 842 (match by collapsed version key).

Evidence:

- Live, after the CLI and the npm registry failed: `resolve_package("npm", "left-pad", "latest")` returned `{"status":"resolved","version":"1.3.0","integrity":null,"via":"jsdelivr"}`.
- A stand-in NuGet index of four spellings of one version (the three-part number, with a fourth part, with build metadata, and with a pre-release label), for a pin of the three-part form, returned the four-part spelling with integrity null. The three-part and four-part forms compare equal.

HR-9 asks for a version, SHA, or digest. A version with no hash is a pin the feed can replace.

Fix: return `unresolved` when there is no integrity. Do not accept a different NuGet spelling than the pin.

### R-B-10 Low: a same-host redirect may change port

Where: `scripts/toolchain_io.py`, line 227. The host is compared. The port is not.

Evidence: a 302 from the loopback address to a different local port was followed (`status=0`, `error=refused`). A redirect to another host stayed 302. https to http is refused.

Fix: require the same port, or the default port for the scheme.

## Mutation table

35 mutations on copies. "Survived" means the module suite exited 0.

| Mutation | Result | Test |
|---|---|---|
| Shim class: drop `>` only | Survived | none (`>` appears only beside `&`) |
| Shim class: drop CR/LF | Survived | none |
| Shim class: drop `&` only | Survived | none (`>` still matches the payload) |
| Shim class: drop `&` and `>` | Caught | `test_shell_metacharacters_are_refused_before_a_shim_runs` |
| Shim class: drop `\|`, `"`, or `%` | Caught | same |
| `safe_detail`: disable URL, host, path, address, IPv4, or the unsafe-character filter | Caught | `test_urls_hosts_and_addresses_are_removed`, `test_paths_and_addresses_with_a_user_are_removed`, `test_only_safe_characters_survive_and_the_length_is_capped` |
| Redirect: any host, or https to http | Caught | `test_redirect_rule` |
| Body cap disabled | Caught | `test_a_body_over_the_limit_is_cut_and_reported` |
| `kill_tree` is a no-op | Caught | suite hung past 180 s |
| `kill_tree` kills only the direct child | Caught | `test_kill_tree_ends_a_child_and_its_grandchild` |
| Duplicate-tool check disabled | Caught | `test_duplicate_tool_names_are_a_protocol_error` |
| Line limit multiplied by 100 | Caught | `test_a_line_over_the_limit_is_a_protocol_error` (failed as timeout) |
| Allow-list gains `GITHUB_TOKEN` | Caught | CaptureEnvTests (2 failures) |
| `capture_env` copies every variable | Caught | CaptureEnvTests |
| `ENV_ALLOW_PREFIXES` widened to `npm_` | Caught | `test_only_allow_listed_names_and_the_declared_ones_remain` |
| Cursor-seen check removed | Caught | `test_a_cursor_that_never_ends_is_a_protocol_error` |
| Accept any JSON-RPC id | Caught | `test_garbage_on_standard_output_and_noise_on_standard_error_are_ignored` |
| Submodule refusal disabled | Caught | `test_a_submodule_inside_a_skill_is_refused_rather_than_left_out` |
| SHA pattern widened to 40-64 hex | Caught | `test_a_commit_is_taken_as_given_without_a_call` |
| `..` allowed in paths | Caught | `test_bad_commit_and_path_values_are_refused_before_git_runs` |
| Vendor digest check disabled | Caught | `test_a_digest_that_does_not_match_stops_everything_and_writes_nothing` |
| Staging directory left in place | Caught | `test_a_failed_run_leaves_the_earlier_store_alone` |
| Quarantine forced false | Caught | `test_a_quarantined_skill_is_never_written` |
| `_walk` no longer treats symlinks as links | Survived | real symlink test skipped: "this account cannot create symbolic links" |
| Refuse `file://` URLs that have a host | Survived | no test uses a file URL with a host |
| `credential.helper=` removed | Caught | `test_git_runs_anonymously_without_a_prompt` |
| `GIT_TERMINAL_PROMPT` cleared | Caught | `test_git_runs_anonymously_and_the_file_protocol_only_for_file_urls` |

Five survived: three shim-class gaps, the symlink walk, and the missing file-host refusal.

## Checked and fine

- The three modules pass, aside from the symlink skip above.
- On this Python, a `.cmd` argument with a trailing backslash, `!PATH!`, or U+FF06 did not break out of the shim. `| < " ^ %` are refused.
- `-c credential.helper=` clears a global helper. `ext::` is refused unless that same config also sets `protocol.ext.allow`.
- Submodule entries, `..` paths, 40-character commit ids, vendor digest-before-copy, quarantine, and staging cleanup are enforced and tested.
