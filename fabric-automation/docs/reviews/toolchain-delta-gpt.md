# Delta review of the toolchain kit, slice B: the helper modules (GPT 6.1 Sol)

The reply as it came back, with the agent's own header removed. It reviewed the published commit `abe6b9d614` from a clean clone, against the commit `a7932d1bf9` that the second review had looked at: whether the fixes of the second review closed the findings on the helper modules (R-N2-1 to R-N2-8), eight new findings (R-D2-1 to R-D2-8) and 80 mutations, none of which survived. The author's checks and the dispositions are in [toolchain-delta-findings.md](toolchain-delta-findings.md).

Reviewed `abe6b9d6145d44ede21957a73a81ccdd0f8ae9ea` against `a7932d1`, including the full six-file delta and relevant module wiring. Experiments used `R:\cl3-b-review2`; the reviewed project’s tracked files remained unchanged.

All work ran on Windows with Python 3.11.9. No machine credential store or signed-in tenant API was used. Authentication experiments used only synthetic credentials against a loopback server.

## 1. Diff review

The corrections substantially improve command lookup, ordinary Git configuration isolation, link refusal, npm cross-checking, protocol validation and lint consistency. The Windows-only `make_writable` change correctly avoids chmod in the POSIX branch.

The principal remaining gaps are at module/filesystem seams:

- Resetting `<cache>/config` does not necessarily reset the configuration Git actually reads.
- An empty Git working directory is not an empty credential environment.
- Cache-root link checks do not cover links inside a cache.
- HTTP body errors can erase an already-received “not found” status.
- Successful initialization accepts protocol dates that the client does not support.
- Windows hard-link content survives configuration replacement, but its read-only protection does not.

Some tests also give misleading assurance: one explicitly accepts an unsupported protocol date, and two existing tests are sensitive to legitimate environment settings or interpreter startup time.

### Tests run

```powershell
python -m unittest scripts.test_toolchain_io scripts.test_toolchain_mcp scripts.test_toolchain_sources -v
```

**526 tests: 2 failures, 3 skips.**

- I/O: 112 tests; no failures.
- MCP: 137 tests; two failures described below.
- Sources: 277 tests; no failures.
- Removing ambient npm settings and rerunning the unchanged MCP module produced **137 passing tests**.
- The initially skipped system-configuration control passed separately with system configuration enabled and redirected exclusively to a scratch configuration file.

Linux was **not run**. POSIX rule tests and mocked POSIX branches ran, but these are not equivalent to Linux execution.

## 2. Closure of listed items

| Item | Decision | Independent evidence |
|---|---|---|
| **R-N2-1** | **Partly closed** | A real child received none of the nine repository variables. Ordinary CWD/parent configuration, matching `includeIf`, and junction-backed temporary-directory experiments were isolated correctly. Ordinary cache configuration was replaced. However, `commondir` bypasses replacement, and `.netrc` credentials are still consumed: findings D2-1 and D2-2. |
| **R-N2-2** | **Closed** | Current-directory and relative-PATH decoys were not run; relative-only lookup returned 127. Bare, drive-relative and rooted-without-drive finder results were refused. PATHEXT order and fallback endings behaved as specified. |
| **R-N2-3** | **Partly closed** | Original pack/skills/shared-folder and nested-link scenarios are refused, including shared Git-tree links. A junction inside cache `objects`, however, receives writes outside the pack: D2-3. |
| **R-N2-4** | **Partly closed** | Agreement, mismatch, absent version, ordinary not-found, malformed metadata and missing integrity behaved correctly. Real npm confirmed parent-project configuration isolation. A 404 accompanied by a body-reading error nevertheless restores CLI-only acceptance: D2-4. |
| **R-N2-5** | **Closed** | Errors naming only unknown dates stopped before further requests; explicitly naming `2026-07-28` selected modern handling. Successful responses have a separate remaining defect, D2-5. |
| **R-N2-6** | **Closed** | Booleans, numbers, arrays, ordinary words and non-ASCII date digits were rejected before initialization continued. Supported date strings worked. |
| **R-N2-7** | **Partly closed; qualification** | Mixed-alphanumeric keys, hosts and IPv4 addresses became `unknown`. Alphabetic synthetic token-prefixed labels remained accepted because `_token_like` requires a digit. Acceptance was reproduced, including through capture wiring; **an actual valid-credential leak through this label case is UNVERIFIED**, so I do not claim one. |
| **R-N2-8** | **Closed** | A real Windows junction was linted as its target text, not followed. Disk/Git-style lint results agreed; link file-count and byte-count boundaries were exercised. |

## 3. Mutation results

**80 distinct mutations; all caught. No invalid or timed-out mutation runs.**

Affected module suites were selected with the focused safeguard class first and `-f`; detected failures stopped those runs.

| Area | Mutations | Caught | Survivors |
|---|---:|---:|---|
| `which`/`resolve_command`: relative and empty entries, named paths/results, PATHEXT ordering/default/endings, folder ordering, default PATH | 13 | 13 | None |
| Git: nine variables individually; ceiling, empty/canonical working folder, resets before use/after init, four `--git-dir` locations, cache-link refusal | 21 | 21 | None |
| Vendoring: entry call, store/skills/selected/stale/shared/nested links, `.git`, shared selection scans, cache root/commit, fast path, shared-tree staging | 16 | 16 | None |
| npm: agree, mismatch, absent, notfound, bad, no-integrity, network, `.npmrc`, `package.json` | 9 | 9 | None |
| MCP: modern naming, unknown/older dates, protocol string/ASCII checks, key/host/address/dot/digit rules, discovery wait | 11 | 11 | None |
| Link lint: reading, file limit, byte limit | 3 | 3 | None |
| Deletion: always/never/wrong chmod; both source call sites removed; both wrong-path variants | 7 | 7 | None |
| **Total** | **80** | **80** | **None** |

**Every mutation unnoticed by all applicable tests: none.**

For deletion specifically:

- Always chmod, never chmod and wrong mode failed both I/O and source tests independently.
- Removing either source call site failed source tests; unchanged I/O tests alone passed, as expected.
- All mutation copies were restored and byte-compared with the clone afterward.

These results do **not** cover the separate gaps found by independent reproductions.

## 4. What held up

- Absolute-only launcher lookup prevents the original Windows CWD hijack.
- Relative PATH rejection is deliberate, documented incompatibility—not an accidental regression.
- Listed PATHEXT precedence, fallback endings and absolute-result enforcement held.
- Git isolation held for ordinary local configuration, matching conditional includes, parent repositories and canonicalized junction-backed temporary directories.
- Real read-only file/folder deletion worked on Windows.
- The POSIX branch left another hard-link name’s mode unchanged.
- Vendored skill links remained ordinary files containing target text; shared-tree links were refused.
- Dotted names and four-part numeric versions became `unknown`, as documented.
- A `reference-transaction` hook in an existing cache executed during fetch. This is an **already documented residual**, not counted as a new finding; a subsequent digest check cannot prevent that execution.

### Real MCP probe

Attempted:

```powershell
npx -y @microsoft/fabric-mcp@1.6.0 server start --mode all --namespace docs
```

The probe reported `exited: code 1`. Public npm metadata lookup failed with `ERR_SSL_SSL/TLS_ALERT_HANDSHAKE_FAILURE`, including a validated TLS-1.2 retry.

**No real server era or label was obtained.** This is an environmental limitation, not evidence of a protocol defect.

## 5. New findings

Commands below refer to experiment scripts in the scratch copy; setup and observed results are included inline.

### R-D2-1 — High — `commondir` bypasses cache configuration isolation

**Location:** `scripts/toolchain_sources.py, lines 233–242 and 434–463`.

**Wrong:** Git can obtain configuration from the common directory named by a plain `commondir` file. Replacing the leaf cache’s `config` does not remove that configuration.

**Evidence:** Ran `python review2_repros.py commondir` from the scratch project. Created two ordinary bare repositories, placed a `commondir` file in the cache pointing to the other, and configured the common repository’s `remote.<file-url>.uploadpack` to run a harmless marker program. `fetch_git` executed it:

- `marker_executed: true`
- `leaf_config_is_minimal: true`
- common configuration still contained `uploadpack`
- fetch subsequently failed with Git exit 128.

**Suggested fix:** Refuse `commondir`/linked-worktree caches before any Git invocation, or prove that the effective common directory is precisely the owned cache and sanitize that directory too.

### R-D2-2 — High — anonymous Git still sends `.netrc` credentials

**Location:** `scripts/toolchain_sources.py, lines 199–230 and 245–250`.

**Wrong:** Disabling credential helpers and configuration does not disable libcurl’s `.netrc` handling. Git inherits HOME/USERPROFILE.

**Evidence:** From the scratch root, ran:

```powershell
python review2_netrc.py
python review2_netrc_fetch.py
```

Created an isolated profile containing synthetic `.netrc`/`_netrc` entries and a loopback TLS server returning a Basic-auth challenge. Both lookup and fetch made two requests and sent the matching synthetic `Authorization` header:

```text
synthetic_netrc_credentials_sent: true
result: network: authentication required
```

No real account credentials were used. Certificate validation was disabled only for that generated loopback certificate.

**Suggested fix:** Give anonymous Git an empty credential home/profile, remove explicit netrc overrides, and audit other implicit credential sources. Add real HTTP authentication tests for both operations.

### R-D2-3 — Medium — junctions inside a Git cache escape the pack

**Location:** `scripts/toolchain_sources.py, lines 434–463 and 1344–1366`.

**Wrong:** Cache checks examine `.cache` and commit-directory roots, not their contents.

**Evidence:** Ran `python review2_repros.py cache-link`. Replaced an ordinary cache’s `objects` directory with a junction to an outside scratch directory, then vendored the pinned router. Vendoring succeeded; the outside directory acquired three Git pack/index/reverse-index files:

```text
cache_root_is_link: false
objects_is_link: true
outside_files_before: 0
outside_files_after: 3
```

The CLI ancestor guard does not inspect these cache internals either.

**Suggested fix:** Refuse symlinks/junctions anywhere inside caches that Git will use, before staging or invoking Git.

### R-D2-4 — Medium — body errors override an authoritative npm 404

**Location:** `scripts/toolchain_sources.py, lines 877–898 and 998–1018`.

**Wrong:** `_stage_failure` checks `error` before status. A received 404/410 becomes `network` if reading its body fails, permitting CLI-only resolution.

**Evidence:** Ran `python review2_http.py`. A real loopback HTTP response returned 404 with a body beyond a temporarily reduced body limit; the CLI stand-in supplied version `9.9.9` with syntactically valid integrity:

```text
real_HTTP_response: {"error": "too-large", "status": 404}
resolver_outcome: {"status": "resolved", "version": "9.9.9", "via": "npm-cli"}
```

**Suggested fix:** Preserve 404/410 precedence despite body errors. Distinguish an absent HTTP response from unusable metadata received with a response. Document intentional 403/429/5xx fallback exceptions accurately.

### R-D2-5 — Medium — successful initialization accepts unsupported protocols

**Location:** `scripts/toolchain_mcp.py, lines 435–442`; `scripts/test_toolchain_mcp.py, lines 1329–1333`.

**Wrong:** `_legacy` checks date-string shape but not supported-version membership. The test explicitly accepts `2027-01-01`.

**Evidence:** Ran `python review2_repros.py protocol`: both `2027-01-01` and invalid `9999-99-99` continued through `notifications/initialized` and `tools/list`. Ran `python review2_wiring2.py` through the real probe/capture composition: it recorded:

```text
status: captured
era: legacy
protocol: 2027-01-01
```

The [MCP lifecycle specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) says: “If the client does not support the version in the server’s response, it SHOULD disconnect.”

**Suggested fix:** Require membership in supported handshake revisions before continuing; reject unsupported successful responses and replace the positive test with rejection coverage.

### R-D2-6 — Low — Windows configuration replacement changes another hard link’s protection

**Location:** `scripts/toolchain_io.py, lines 165–171`; `scripts/toolchain_sources.py, lines 233–242 and 1147–1159`.

**Wrong:** Clearing Windows’s read-only attribute changes the shared file behind all hard-link names. The existing configuration-link test checks content, not protection.

**Evidence:** Ran `python review2_hardlink.py`. Hard-linked `cache/config` to a scratch outside file and made it read-only. After configuration reset:

```text
outside_writable_before: false
outside_writable_after: true
outside_mode_before: 0o444
outside_mode_after: 0o666
outside_content_unchanged: true
```

This concerns the read-only attribute, **not an ACL bypass**.

**Suggested fix:** Refuse read-only hard-linked configurations before clearing the attribute, or remove the name using a mechanism that preserves shared attributes. Test actual Windows protection preservation.

### R-D2-7 — Low — environment test rejects intentionally allowed npm variables

**Location:** `scripts/test_toolchain_mcp.py, lines 639–648`.

**Wrong:** The expected-name set includes `ENV_ALLOW_LIST` but omits `ENV_ALLOW_NPM`.

**Evidence:** Ran the individual `test_the_child_does_not_inherit_the_environment_of_the_parent` with isolated-profile npm settings. It failed on six deliberately allowed variables, including `NPM_CONFIG_CACHE` and `NPM_CONFIG_USERCONFIG`. The unchanged module passed after removing them.

**Suggested fix:** Include the fixed npm allow-list in the expected set; continue rejecting credential settings. Do not require callers to erase legitimate configuration merely to make tests green.

### R-D2-8 — Low — restart-count test assumes sub-second interpreter startup

**Location:** `scripts/test_toolchain_mcp.py, lines 446–452`.

**Wrong:** The 0.5-second timeout can kill the first process before it writes `FAKE_STARTS`. Process creation and marker-file entries are not equivalent.

**Evidence:** The initial full run failed with `AssertionError: 2 != 1`. Ran `python review2_startup_test.py`, adding only 0.8 seconds before the stand-in writes its start marker. The correct modern contract was returned, but the same count assertion failed.

**Suggested fix:** Count parent-side process/session starts, or establish explicit readiness before inducing the timeout.

D2-7 and D2-8 are existing test defects exposed during this review, not newly introduced production regressions.
