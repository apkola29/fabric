# Closure check of the toolchain kit after the third review, slice B: the helper modules (GPT 6.1 Sol)

The reply as it came back, with the agent's own header removed. It checked the published commit `2231f55f7a` from a clean clone: whether the fixes closed its eight findings of the third review (R-D2-1 to R-D2-8), by repeating each of its reproductions, a read of the whole delta of the three helper modules and their tests, 21 mutations (none survived) and one new finding (R-E2-1). The author's checks and the dispositions are in [toolchain-recheck-findings.md](toolchain-recheck-findings.md).

Reviewed `2231f55f7a`. Read the complete helper-module and test deltas. Used a new scratch copy, `R:\cl3-b-review2-r4`; the clone’s reviewed project remained unchanged.

**All eight original findings are closed in their reproduced scenarios.** One additional credential-channel qualification is reported below. All 21 focused mutations were caught.

## 1. Closure replay

The original scripts were copied into the new tree. Adaptations were limited to the revision, recording expected exceptions, and adding plain-Git positive controls.

| Finding | Decision | Command and observation |
|---|---|---|
| **R-D2-1 — common-directory configuration** | **Closed** | `python review2_repros.py commondir`: fetch succeeded; marker did **not** execute. The common repository remained untouched. `cache-hook` also showed no hook execution. |
| **R-D2-2 — netrc credentials** | **Closed** | `python review2_netrc.py` and `python review2_netrc_fetch.py`: plain Git sent the synthetic credentials, proving the fixture worked. The kit sent **no Authorization header**, making one unauthenticated request in each operation. |
| **R-D2-3 — cache-internal junction** | **Closed** | `python review2_repros.py cache-link`: vendoring succeeded, the cache’s `objects` junction was replaced, and the outside directory remained at **zero files**. |
| **R-D2-4 — unreadable 404 body** | **Closed** | `python review2_http.py`: real HTTP result remained `404 / too-large`; resolution now returned **unresolved / mismatch**, not CLI version `9.9.9`. |
| **R-D2-5 — unsupported successful initialization** | **Closed** | `python review2_repros.py protocol`: future, impossible and modern-revision answers to legacy initialization stopped before notification/tools requests. `python review2_wiring2.py` returned **unavailable / protocol-error**, not a captured contract. |
| **R-D2-6 — hard-link protection** | **Closed** | `python review2_hardlink.py`: configuration replacement was refused; outside content remained unchanged and mode remained **0o444**, with writing still refused. The new real-file test also exercised rejection through `fetch_git`. |
| **R-D2-7 — permitted npm environment settings** | **Closed** | The individual `StdioTests.test_the_child_does_not_inherit_the_environment_of_the_parent` passed with the permitted npm settings present. |
| **R-D2-8 — interpreter-start race** | **Closed** | `python review2_startup_test.py`, retaining the added 0.8-second delay before the child marker, passed. Parent-side process counting removes the original assumption. |

R-N2-7 remains the documented qualification. I did not turn the synthetic alphabetic-label example into a claim of a verified real-credential leak.

## 2. Diff review and adversarial checks

The full six-file delta contained **969 insertions and 80 deletions**.

The new design is materially stronger: old cache contents are removed before Git runs; network operations receive an empty home; received not-found statuses retain precedence; initialization requires a known revision; Windows hard-link attributes are preserved.

### Focused tests

Ran the following classes together:

- Sources: `StaleCacheTests`, `AnonymousGitTests`, `StageFailureTests`, `GitIsolationTests`, `VendorRetryTests`
- I/O: `MakeWritableTests`
- MCP: `InitializeTests`, `CommittedLockTests`, `ToolNameTests`

**76 tests passed, no skips.** This included the real-process TLS tests using the available OpenSSL executable.

### What held up

- **Cache contents:** common-directory pointers, object-directory junctions, hooks, alternates, stale refs and stray files no longer survived cache rebuilding.
- **Caller wiring:** `resolve_source` fetches every time. `lock` and `update` call `refuse_resolve_links`, including the `.cache` directory and the store’s ancestor guard. `Project.store` does not resolve away those links before checking.
- **Locked Windows files:** `python r4_locked_cache.py` left a partially removed cache containing only its locked file, returned `unresolved: cannot remove the old cache folder`, and made **zero Git calls**. After unlocking, the next call fetched anew and removed both old files. It did not trust the remainder.
- **Locked hard-link metadata:** the separate sharing-lock experiment still reported two names; `make_writable` preserved outside read-only protection and content.
- **TLS test soundness:** the tests require a positive plain-Git credential/certificate control, require the kit actually to reach the server, and check the observed headers/certificate. They cannot pass merely because TLS failed before HTTP.
- **Compatibility choices:** 403/429/5xx and unreadable non-not-found responses intentionally retain CLI fallback. Unknown initialization revisions now intentionally stop rather than being recorded. These match the updated documentation.
- **Staging:** fresh staging directories are allocated rather than adopting old staging contents. No staging-based escape was reproduced.
- **Probe environment:** inherited credentialed proxy addresses were sanitized; disallowed npm credential settings remained excluded.

### Limits

Linux was **not rerun**. I inspected the POSIX-sensitive paths and TLS tests but do not replace the author’s hosted evidence with a Windows claim.

The Windows TLS tests explicitly select the OpenSSL backend. Domain-joined SSPI behavior and third-party/name-surrogate reparse tags other than ordinary symlinks/junctions remain **UNVERIFIED** here. No exploit through `_run_bytes` local object reads or `.curlrc` was reproduced.

Explicitly declared probe environment values remain trusted input; they can intentionally carry credentials. That differs from inherited-environment filtering.

## 3. Mutation results

Mutations used separate copies and matching classes, with `-f`. Every copy was restored and byte-compared with the clone afterward.

| Safeguard weakened | Mutations | Caught | Survivors |
|---|---:|---:|---|
| Cache purge/reuse, cache-link refusal, removal/mkdir failure handling, post-init configuration replacement | 6 | 6 | None |
| HOME/USERPROFILE/XDG_CONFIG_HOME and HOMEDRIVE/HOMEPATH isolation, individually | 5 | 5 | None |
| NETRC and three client-certificate-variable removals, individually | 4 | 4 | None |
| `http.emptyAuth=false` | 1 | 1 | None |
| 404 body-error precedence and 410 recognition | 2 | 2 | None |
| Supported handshake-revision membership | 1 | 1 | None |
| Hard-link exclusion and exact two-name boundary | 2 | 2 | None |
| **Total** | **21** | **21** | **None** |

**Every unnoticed mutation: none.** No invalid or timed-out mutation execution was counted.

## 4. New finding

### R-E2-1 — Medium — authenticated proxy settings remain a credential channel for “anonymous” Git

**Location:** `scripts/toolchain_sources.py, lines 206–246`.

**What is wrong:** The Git environment isolation removes netrc and client-certificate channels but retains credential-bearing proxy URLs and `GIT_HTTP_PROXY_AUTHMETHOD`. Consequently, the blanket “without any stored credential”/anonymous wording does not describe all transport authentication behavior.

This is narrower than the original netrc finding: the credential went to the **configured proxy**, not an arbitrary repository origin.

**Evidence:** Ran:

```powershell
python r4_proxy_basic.py
```

The experiment set only synthetic values:

- `HTTPS_PROXY` pointed to a loopback proxy with synthetic URL credentials.
- `GIT_HTTP_PROXY_AUTHMETHOD=basic` selected Git’s standard proxy-auth mechanism.
- The requested repository was the manifest’s public Microsoft skills repository.
- The proxy rejected CONNECT before contacting any external host.

Observed:

```text
git_sent_synthetic_proxy_password: true
proxy_requests: 1
proxy_result: network: git exit 128
```

The proxy received the matching Basic `Proxy-Authorization` header despite the empty Git home and disabled credential helper. Without the explicit proxy-auth setting, that header was not observed in this experiment.

**Suggested fix:** Define and enforce the boundary explicitly:

- For genuinely credential-free Git, sanitize proxy URL user information and constrain proxy-auth settings.
- If authenticated corporate proxies are intentionally supported, document the credential-bearing exception and ensure such calls are not described or supplied as credential-free agent operations.

No machine credential store, real credentials or signed-in tenant service was involved.
