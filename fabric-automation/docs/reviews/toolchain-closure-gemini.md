# Closure review of the toolchain kit, slice B: the helper modules (Gemini 4 Argon)

The reply as it came back, with the agent's own header and its own top heading removed. A profile path, three example tokens, one example address, one four-part version, the user information of two example web addresses and one example password are spelled out, because the document checks would read them as leaks. It reviewed the published commit `a7932d1bf9` from a clean clone: whether the fixes of the first review closed the findings on the helper modules (R-B-1 to R-B-10 and R-C-11), eight new findings (R-N2-1 to R-N2-8) and 84 mutations, 5 of which survived. The author's checks and the dispositions are in [toolchain-closure-findings.md](toolchain-closure-findings.md).

**Baseline & Live MCP Probe:**
- Repository: `R:\cl2-b` at commit `a7932d1bf9815db54a6ce685a5b0f4b98774b7d2` (left completely untouched; all mutations and reproductions ran in `R:\cl2-b-scratch`).
- Test suite (`python -m unittest scripts.test_toolchain_io scripts.test_toolchain_mcp scripts.test_toolchain_sources` from `R:\cl2-b\fabric-automation`): **388 tests, 1 skipped** (`test_a_symbolic_link_counts_as_a_file_holding_its_target`, as this Windows account cannot create symbolic links), **OK in 260.1s**.
- Live probe of local `fabmcp` (`%USERPROFILE%\.dotnet\tools\fabmcp.cmd`, version 1.5.0):
  ```powershell
  python -c "import sys; sys.path.insert(0,'scripts'); import toolchain_mcp as m; r=m.probe_stdio(['fabmcp','server','start','--mode','all','--namespace','docs'], timeout=120, cwd=r'R:\cl2-b-scratch'); print(r['era'], r['protocol'], r['server'], len(r['tools']))"
  ```
  Observed output: `modern 2026-07-28 {'name': 'Fabric MCP Server', 'version': '1.5.0'} 6`. It answered `server/discover` with the modern era (`2026-07-28`) and returned 6 tools.

---

## 1. CLOSURE OF EARLIER FINDINGS

| ID | Decision | What was inspected, run, and observed |
|---|---|---|
| **R-B-1** | **Closed** | `scripts/toolchain_io.py`, lines 187-206 (`_system_taskkill`, `_taskkill`). Resolves `taskkill.exe` strictly as an existing file under an absolute `SystemRoot`, `windir`, or `C:\Windows` (`System32\taskkill.exe`). Tried prepending a directory with a decoy `taskkill.cmd` to `PATH` and `os.chdir` into it before calling `kill_tree(proc)` on a child+grandchild tree: `C:\WINDOWS\System32\taskkill.exe` ran, both processes died, and the decoy marker was not created. |
| **R-B-2** | **Partly closed** | `scripts/toolchain_sources.py`, lines 163-191 (`_git_env`, `_network_argv`). Global (`GIT_CONFIG_GLOBAL=os.devnull`), system (`GIT_CONFIG_NOSYSTEM=1`), and env-injected configs (`GIT_CONFIG_COUNT`, `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_KEY_*`/`VALUE_*`), `protocol.ext.allow=never`, `credential.helper=`, and `GIT_ALLOW_PROTOCOL` (`https` or `https:file`) block the original global/env reproduction (`fetch_git` against `invalid.invalid` with hostile `GIT_CONFIG_GLOBAL`, `HOME`, `GIT_CONFIG_SYSTEM`, `GIT_CONFIG_COUNT`, and `GIT_CONFIG_PARAMETERS` returned `network: dns` and never ran the `ext::` helper). **However**, `resolve_git_ref` runs `git ls-remote` without `--git-dir`, so Git discovers and loads `.git/config` in the current working directory (or `GIT_DIR`), and `fetch_git` loads `<dest>/config` on a pre-existing cache folder; for `file://` URLs this still allows arbitrary command execution via `remote.<url>.uploadpack` (see **R-N2-1**), and on Windows `which("git")` resolves `.\git.cmd` from the working directory (see **R-N2-2**). |
| **R-B-3** | **Closed** | `scripts/toolchain_mcp.py`, lines 55-68 and 147-187 (`ENV_ALLOW_LIST`, `ENV_ALLOW_NPM`, `ENV_ADDRESS_NAMES`, `_without_credentials`, `capture_env`). Tested `capture_env(None, parent)` with `npm_config_//registry.npmjs.org/:_authToken`, `NPM_CONFIG__AUTH`, `GITHUB_TOKEN`, `NPM_TOKEN`, `AZURE_CLIENT_SECRET`, `npm_config_registry="https://user:<password>@registry.npmjs.org/"`, and `HTTPS_PROXY="http://alice:<password>@proxy.example.com:8080"`. All token variables were stripped and both URLs were sanitised to `'https://registry.npmjs.org/'` and `'http://proxy.example.com:8080'`. |
| **R-B-4** | **Partly closed** | `scripts/toolchain_sources.py`, lines 492-558 (`_npm_cli`, `_npm_registry`, `_resolve_npm`). `_npm_cli` runs in `tempfile.mkdtemp(prefix="toolchain-npm-")` and cross-checks with `https://registry.npmjs.org/`. Tested a spoofed `npm view` returning `9.9.9` while the registry returned `1.3.0`: `resolve_package` rejected it with `{'status': 'unresolved', 'reason': 'unresolved', 'detail': 'mismatch'}`. **However**, two bypasses remain: (1) if `registry.npmjs.org` returns HTTP 404 (`"notfound"`) or a packument with no `dist-tags.latest` (`"bad"`), `_resolve_npm` only rejects `registry_failure[1] == "absent"` and accepts the spoofed `cli` result; (2) `npm` walks up parent directories from `tempfile.mkdtemp()` and loads `<TEMP>/.npmrc` if `<TEMP>/package.json` exists (see **R-N2-4**). |
| **R-B-5** | **Closed** | `scripts/toolchain_sources.py`, lines 148-160 (`_check_url`). Tested `file://invalid.invalid/share/repo.git`, `file://localhost/repo.git`, `file:////server/share/repo.git`, `file:///C:\repo.git`, `file:///repo.git?q=1`, and `file:///repo.git#frag`; all raised `SourceError("unresolved: unsupported repository url")` before Git was called. |
| **R-B-6** | **Closed** | `scripts/toolchain_sources.py`, lines 84-100 (`_junction`, `_entry_is_link`, `_walk`). Created a skill folder with `SKILL.md` and a Windows junction (`mklink /J leak <outside>`) pointing to an outside directory containing `secret.txt` (`pip install evil-pkg`). `digest_tree` returned `files: 2` (hashing the junction target string, not the outside file) and `lint_skill` returned `install_hints: 0`. |
| **R-B-7** | **Closed** | `scripts/toolchain_mcp.py`, lines 365-378 and 441-458 (`_discover`, `_probe`). `server/discover` is sent first; `-32022` (`UNSUPPORTED_VERSION`) raises `protocol-error: no mutually supported protocol version` without falling back to `initialize`; silent/exiting servers are restarted on a fresh process before `initialize`. Verified against stand-in servers and live `fabmcp`. (See **R-N2-5** for a new flaw in `_initialize` version comparison.) |
| **R-B-8** | **Partly closed** | `scripts/toolchain_io.py`, lines 66-99 (`safe_detail`). Tested Grok's three inputs (`failed connecting to 2001:db8:85a3::8a2e:370:7334` -> `'failed connecting to'`, `basic alice:s3cret-token rejected` -> `'basic rejected'`, `cannot open Users\alice\secrets\token.txt` -> `'cannot open'`) plus `ghp_...` tokens; all were stripped. **However**, `_token_like` requires both a letter and a digit, so 24+ character pure-letter/hyphen/underscore secrets (`password=<24 letters>`) and pure-digit tokens survive `safe_detail`, and `toolchain_mcp._server_info` does not run `_token_like` or `_host_like` at all (see **R-N2-7**). |
| **R-B-9** | **Closed** | `scripts/toolchain_sources.py`, lines 518-558 and 578-621 (`_npm_cli`, `_npm_registry`, `_resolve_nuget`, `_nupkg_integrity`). jsDelivr was removed; missing integrity returns `unresolved`; NuGet requires exact case-insensitive string equality against the pin (`1.0.0` against `["1.0.0 with a fourth part", "1.0.0+build", "1.0.0-beta"]` returned `{'status': 'unresolved', 'reason': 'unresolved', 'detail': 'version not found'}`) and computes `sha256-<base64>` by streaming `.nupkg` through `http_hash` with a 200 MB cap. |
| **R-B-10** | **Closed** | `scripts/toolchain_io.py`, lines 254-275 (`_effective_port`, `_redirect_allowed`). Tested `_redirect_allowed` and live loopback HTTP redirects across ports: `http://127.0.0.1:8000/a` -> `http://127.0.0.1:8001/b` returned `False` (HTTP 302 not followed); default-port HTTP-to-HTTPS upgrade (`80` to `443`) is allowed; HTTPS-to-HTTP downgrade is refused. |
| **R-C-11** | **Closed** | `scripts/toolchain_sources.py`, lines 397-443 (`_is_text`, `_count_hints`, `_lint_files`, `lint_skill`). Tested a skill with `run.ts` (`npm install evil`) and a 2 MB + 10 byte `huge.txt`: `lint_skill` returned `install_hints: 1` and `findings: ['file too large to scan: huge.txt']`. |

---

## 2. NEW DEFECTS (RANKED BY IMPACT)

### R-N2-1 (High): `resolve_git_ref` and `fetch_git` read local repository config (`.git/config`, `GIT_DIR`, `<dest>/config`), allowing URL rewriting and command execution
- **Where:** `scripts/toolchain_sources.py`, lines 170-191 (`_git_env`, `_network_argv`) and lines 281-333 (`_ls_remote`, `fetch_git`)
- **What is wrong:** `_git_env` sets `GIT_CONFIG_GLOBAL` to `os.devnull` and `GIT_CONFIG_NOSYSTEM=1`, and drops `GIT_CONFIG_COUNT` and `GIT_CONFIG_PARAMETERS`, but it does not clear `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, or `GIT_EXEC_PATH`, and `resolve_git_ref` runs `git ls-remote` without `--git-dir`. Consequently, Git discovers `.git/config` in the current working directory (or `GIT_DIR`), and `fetch_git` reads `<dest>/config` if `dest` already exists. A local `.git/config`, `GIT_DIR/config`, or `<dest>/config` can rewrite any `https://` repository URL to an attacker-controlled `https://` server via `url.<evil>.insteadOf`, and for `file://` URLs executes arbitrary commands via `remote.<url>.uploadpack`.
- **Evidence:** Ran in `R:\cl2-b-scratch`:
  ```powershell
  python -c "import os, subprocess, sys; from pathlib import Path; sys.path.insert(0, r'R:\cl2-b\fabric-automation\scripts'); import toolchain_sources as ts; tmp=Path(r'R:\cl2-b-scratch\repro1'); repo=tmp/'repo'; bare=tmp/'bare.git'; marker=tmp/'pwn.txt'; hlp=tmp/'pwn.py'; subprocess.run(['git','init','--quiet',str(repo)],check=True); subprocess.run(['git','init','--bare','--quiet',str(bare)],check=True); hlp.write_text(f'open({str(marker)!r},\"w\").write(\"pwn\")\n'); u=bare.as_uri(); subprocess.run(['git','-C',str(repo),'config',f'remote.{u}.url',u],check=True); subprocess.run(['git','-C',str(repo),'config',f'remote.{u}.uploadpack',f'\"{Path(sys.executable).as_posix()}\" \"{hlp.as_posix()}\"'],check=True); os.chdir(repo); ts.resolve_git_ref(u,{'kind':'tag','pattern':'v*'})"
  ```
  Observed: `pwn.txt` was created (`marker.exists() == True`), proving arbitrary command execution during `resolve_git_ref`. Separately, setting `url.https://rewritten-from-dest-config.invalid/.insteadOf = https://github.com/` in `<dest>/config` (or `GIT_DIR`) caused `fetch_git("https://github.com/microsoft/skills-for-fabric.git", ...)` and `resolve_git_ref` to connect to `rewritten-from-dest-config.invalid`.
- **Suggested fix:** In `_git_env`, also drop `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, and `GIT_EXEC_PATH` (set to `None`). Run `ls-remote` in an empty temporary directory or with `--git-dir` pointed at an empty newly initialised directory, and in `fetch_git` pass `-c remote.origin.uploadpack=` / overwrite `<dest>/config` on init so untrusted local config keys cannot take effect.

### R-N2-2 (High): `toolchain_io.which` resolves `.cmd`/`.bat`/`.exe` in the current working directory on Windows when `cwd` is not passed or differs
- **Where:** `scripts/toolchain_io.py`, lines 123-133 (`which`) and lines 140-151 (`resolve_command`)
- **What is wrong:** While `_system_taskkill` fixed `PATH`/CWD hijacking for `taskkill.exe` (R-B-1), `toolchain_io.which(name)` calls `shutil.which(name)`. On Windows with Python 3.11, `shutil.which` prepends `os.curdir` (`.`) to the search path before `PATH`. Every call to `SystemRunner.run` or `popen_tree` with a bare command name (`"git"`, `"npm"`, `"npx"`) resolves `.\<name>.cmd` / `.\<name>.exe` in the parent process's `os.getcwd()` — even when `popen_tree` is given a clean `cwd=work` (as in `_npm_cli` or `probe_stdio`), because `resolve_command` calls `shutil.which` before changing directory.
- **Evidence:** Ran in `R:\cl2-b-scratch`:
  ```powershell
  python -c "import os, sys; from pathlib import Path; sys.path.insert(0, r'R:\cl2-b\fabric-automation\scripts'); import toolchain_io, toolchain_sources; tmp=Path(r'R:\cl2-b-scratch\attack-git-cwd'); tmp.mkdir(parents=True, exist_ok=True); m=tmp/'ran.txt'; (tmp/'git.cmd').write_text(f'@echo off\necho ran > \"{m}\"\n'); os.chdir(tmp); print('which:', toolchain_io.which('git')); toolchain_sources.resolve_git_ref('https://github.com/microsoft/skills-for-fabric.git', {'kind':'tag','pattern':'v*'})"
  ```
  Observed: `which: .\git.CMD`, and `ran.txt` was created when `resolve_git_ref` executed `.\git.CMD` from the working directory.
- **Suggested fix:** Strip empty entries and `.` (`os.curdir`) from the `PATH` passed to `shutil.which(name, path=...)`, and ensure `which` always returns an absolute path from `PATH` rather than searching `os.curdir`.

### R-N2-3 (High): `vendor_skills` does not check `store`, `store/skills`, or `store/<shared>` for Windows junctions or symlinks, writing and deleting outside `store`
- **Where:** `scripts/toolchain_sources.py`, lines 803-848 (`vendor_skills`) and lines 756-783 (`_Swap`)
- **What is wrong:** `vendor_skills` checks `if target.is_dir() and not _is_link(target):` on individual skill/shared targets during the fast-path digest check, and refuses `120000` git entries inside `_shared_entries_of` during `read_plugin`. However:
  1. `vendor_skills` never checks whether `store` or `skills_dir` (`store / "skills"`) is itself a junction or symlink. If `store / "skills"` is a junction to an outside directory, `swap.put` writes staged skills into the outside directory and the cleanup loop (`for child in list(skills_dir.iterdir()): if child.name not in picked ... swap.put(None, child)`) deletes every existing subdirectory inside the outside target.
  2. `_stage` (lines 740-753) calls `_tree_entries` directly rather than `_shared_entries_of`, so if a lock has a shared folder whose git tree contains a `120000` symlink entry, `vendor_skills` stages and writes it without error.
  3. On a second run, `vendor_skills` checks `not _is_link(target)` on the top-level `store / name` folder, but `digest_tree(target)` hashes nested junctions/symlinks inside `store / <shared>` as link entries instead of refusing them.
- **Evidence:** Ran in `R:\cl2-b-scratch`:
  ```powershell
  python -c "import subprocess, sys; from pathlib import Path; sys.path.insert(0, r'R:\cl2-b\fabric-automation\scripts'); import toolchain_sources as ts, test_toolchain_sources as tts; tmp=Path(r'R:\cl2-b-scratch\repro-junc'); fx=tts.Fixture(tmp); r=tts.IsolatedRunner(); lock=tts.lock_for(fx, r); store=tmp/'pack'; out=tmp/'outside'; (out/'victim').mkdir(parents=True); (out/'victim'/'f.txt').write_text('keep'); store.mkdir(parents=True); subprocess.run(['cmd','/c','mklink','/J',str(store/'skills'),str(out)],check=True,capture_output=True); ts.vendor_skills(lock,[('fx','alpha','good-skill')],store,r); print('outside good-skill:', (out/'good-skill'/'SKILL.md').exists(), 'victim exists:', (out/'victim').exists())"
  ```
  Observed: `outside good-skill: True victim exists: False`.
- **Suggested fix:** Before staging or swapping in `vendor_skills`, refuse if `store`, any ancestor up to project root, or `store / "skills"` is a link (`_is_link`). In `_stage` (when `kind == "shared"`) and in the fast-path check for shared folders, refuse any link entry (`mode == "120000"` or `is_link` in `_walk`).

### R-N2-4 (Medium): `_resolve_npm` accepts spoofed CLI results when `registry.npmjs.org` returns HTTP 404 or lacks `latest`, and `npm view` reads `<TEMP>/.npmrc`
- **Where:** `scripts/toolchain_sources.py`, lines 492-558 (`_npm_cli`, `_npm_registry`, `_resolve_npm`)
- **What is wrong:**
  1. In `_resolve_npm` (lines 544-546):
     ```python
     if cli:
         return _unresolved("unresolved", "mismatch") if registry_failure[1] == "absent" else cli
     ```
     `_npm_registry` returns `"absent"` only when `registry.npmjs.org` returns HTTP 200 for the package AND `pin` is set (or `tags.get("latest")` is a valid version string) AND `version not in versions`. If a package does not exist on `registry.npmjs.org` at all (HTTP 404, so `registry_failure` is `("registry not found", "notfound")`), or if `track == "latest"` and the official packument has no `dist-tags.latest` (`registry_failure` is `("registry bad answer", "bad")`), `registry_failure[1]` is not `"absent"`, so `_resolve_npm` trusts the unverified `cli` answer.
  2. `_npm_cli` creates `work = tempfile.mkdtemp(prefix="toolchain-npm-")`, but `npm` walks up parent directories looking for `package.json` / `.npmrc`. If `%TEMP%` (or any parent directory above it) contains `package.json` and `.npmrc`, `npm view` loads that `.npmrc` as its project configuration.
- **Evidence:** Ran in `R:\cl2-b-scratch`:
  ```powershell
  python -c "import json, sys; sys.path.insert(0, r'R:\cl2-b\fabric-automation\scripts'); import toolchain_io as tio, toolchain_sources as ts; r=type('R',(),{'run':lambda s,a,**k:tio.CommandResult(0,json.dumps({'version':'9.9.9','dist.integrity':'sha512-'+'A'*86+'=='}),''),'http':lambda s,m,u,**k:tio.HttpResult(404,{},b'',None)})(); print(ts.resolve_package('npm','@microsoft/fabric-mcp','latest',r))"
  ```
  Observed: `{'status': 'resolved', 'version': '9.9.9', 'integrity': 'sha512-...', 'via': 'npm-cli'}` despite `registry.npmjs.org` returning HTTP 404. Also verified with real `npm config list` in a subfolder of `R:\cl2-b-scratch\attack-npm2\mytemp` containing `package.json` and `.npmrc`: `npm` reported `; "project" config from R:\cl2-b-scratch\attack-npm2\mytemp\.npmrc` (`registry = "http://127.0.0.1:1/"`).
- **Suggested fix:** In `_resolve_npm`, reject `cli` whenever `registry_failure[1] in ("absent", "notfound", "bad", "noint")` (only allow `cli` alone when `registry_failure[1] == "network"`). In `_npm_cli`, write an empty `.npmrc` and `{}` `package.json` into `work` so `npm` stops walking up parent directories.

### R-N2-5 (Medium): `toolchain_mcp._initialize` treats any version `>= "2026-07-28"` (including unsupported future versions or error dates) as mutually supported `2026-07-28`
- **Where:** `scripts/toolchain_mcp.py`, lines 89-109 (`_named_versions`) and lines 404-422 (`_initialize`)
- **What is wrong:** In `_initialize` (lines 413-414):
  ```python
  if any(version >= MODERN_VERSION for version in named):
      return _modern(server, deadline, _identify(server, deadline, answered) or _server_info(None))
  ```
  Unlike `_modern_answer` (which checks `if MODERN_VERSION in versions:` and raises `protocol-error: no mutually supported protocol version` when the server only supports `["2027-01-01"]`), `_initialize` uses `version >= MODERN_VERSION`. Because `server/discover` is optional in MCP `2026-07-28`, a server that replies `-32601 Method not found` to `server/discover` (`answered=True`) and then replies `-32022 Unsupported protocol version` with `{"supported": ["2027-01-01"]}` to `initialize` is falsely accepted as supporting `"2026-07-28"` (`_identify` returns `None` when `answered=True`, falling back to `_server_info(None)`). Furthermore, if a legacy server fails `initialize` with an error message containing `"version"` or `"support"` and a current date `>= 2026-07-28` (e.g. `"2026-10-31: unsupported flag"`), `_named_versions` extracts `"2026-10-31"` and `_initialize` switches to modern `tools/list`.
- **Evidence:** Ran in `R:\cl2-b-scratch`:
  ```powershell
  python -c "import sys, time; sys.path.insert(0, r'R:\cl2-b\fabric-automation\scripts'); import toolchain_mcp as m, test_toolchain_mcp as tm; s=tm.ScriptedServer(tm.NAMES_OTHERS, tm.TOOLS_ANSWER); print(m._initialize(s, time.monotonic()+10, answered=True))"
  ```
  Observed: `{'era': 'modern', 'protocol': '2026-07-28', 'server': {'name': 'unknown', 'version': 'unknown'}, 'tools': ...}` when the server's error explicitly stated `{"supported": ["2027-01-01"]}`.
- **Suggested fix:** In `_initialize`, check `if MODERN_VERSION in named:` instead of `any(version >= MODERN_VERSION for version in named)`. When `named` contains only unsupported future versions (`all(v not in HANDSHAKE_VERSIONS and v != MODERN_VERSION for v in named)`), raise `_fail("protocol-error", "no mutually supported protocol version")`.

### R-N2-6 (Low): `toolchain_mcp._legacy` accepts non-string `protocolVersion` values (booleans, integers, lists, arbitrary text)
- **Where:** `scripts/toolchain_mcp.py`, lines 384-390 (`_legacy`)
- **What is wrong:** `_legacy` extracts the negotiated protocol version via:
  ```python
  protocol = safe_detail(result.get("protocolVersion"), 32) if isinstance(result, dict) else ""
  ```
  Because `safe_detail` coerces any non-`None` argument with `str(text)`, a malformed `initialize` result with `"protocolVersion": True`, `"protocolVersion": 123`, or `"protocolVersion": ["2025-06-18"]` is turned into `"True"`, `"123"`, or `"2025-06-18"` instead of raising `protocol-error`.
- **Evidence:** Ran in `R:\cl2-b-scratch`:
  ```powershell
  python -c "import sys, time; sys.path.insert(0, r'R:\cl2-b\fabric-automation\scripts'); import toolchain_mcp as m, test_toolchain_mcp as tm; s=tm.ScriptedServer({'result':{'protocolVersion':True}}, tm.TOOLS_ANSWER); print(m._legacy(s, time.monotonic()+10, {'result':{'protocolVersion':True}}))"
  ```
  Observed: `{'era': 'legacy', 'protocol': 'True', 'server': {'name': 'unknown', 'version': 'unknown'}, 'tools': ...}`.
- **Suggested fix:** Require `isinstance(result.get("protocolVersion"), str)` and validate it against `_DATE` (or `_SERVER_VERSION`) before accepting it in `_legacy`.

### R-N2-7 (Low): `toolchain_mcp._server_info` does not redact tokens, hostnames, or IPv4 addresses, and `safe_detail` misses 24+ char tokens without digits
- **Where:** `scripts/toolchain_mcp.py`, lines 73-74 and 285-292 (`_SERVER_NAME`, `_SERVER_VERSION`, `_server_info`); `scripts/toolchain_io.py`, lines 70 and 81-83 (`_TOKEN`, `_token_like`); `scripts/toolchain.py`, lines 236-241 (`safe_detail`)
- **What is wrong:**
  1. `_server_info` in `toolchain_mcp.py` (and `_server_label` in `toolchain.py`) only checks `_SERVER_NAME` (`[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}`) and `_SERVER_VERSION` (`[0-9A-Za-z][0-9A-Za-z.+_~-]{0,63}`). It never calls `_token_like`, `_host_like`, or `_IPV4`. Consequently, a token (`ghp_<28 letters and digits>`), an internal FQDN (`internal.contoso.corp`), or an internal IPv4 address (`10.x.y.z`) in `serverInfo.name` or `serverInfo.version` passes straight through into the lock and load plan.
  2. `toolchain.py` defines its own copy of `safe_detail` (lines 236-241) that was not updated when `toolchain_io.safe_detail` was rewritten (it lacks IPv4, IPv6, `user:secret`, and `_token_like` filtering).
- **Evidence:** Ran in `R:\cl2-b-scratch`:
  ```powershell
  python -c "import sys; sys.path.insert(0, r'R:\cl2-b\fabric-automation\scripts'); import toolchain_mcp as m; print(m._server_info({'name': 'Server ghp_<28 letters and digits>', 'version': 'internal.contoso.corp'}))"
  ```
  Observed: `{'name': 'Server ghp_<28 letters and digits>', 'version': 'internal.contoso.corp'}`.
- **Suggested fix:** In `_label` (`toolchain_mcp.py`) and `_server_label` (`toolchain.py`), reject values where any whitespace-separated word (or `+`/`-`-separated build tag) satisfies `_token_like` or `_host_like` (for `name`), and delegate `toolchain.safe_detail` to `toolchain_io.safe_detail`.

### R-N2-8 (Low): `lint_skill` skips links on disk while `read_plugin` lints git symlink blobs as text files
- **Where:** `scripts/toolchain_sources.py`, lines 422-424 (`lint_skill`) vs lines 498-520 (`read_plugin`)
- **What is wrong:** In `lint_skill(root)` (line 423), `if is_link: continue` skips every symbolic link or junction on disk: links are not counted toward `MAX_TREE_FILES` / `MAX_TREE_BYTES`, are not checked for install hints, and if `SKILL.md` is a link on disk `lint_skill` reports `"no SKILL.md"`. Conversely, `read_plugin` reads git `120000` entries as blobs and passes them to `_lint_files`, and `vendor_skills` writes `120000` skill entries as regular files on disk. Thus `lint_skill` on a checkout with symlinks/junctions disagrees with `read_plugin` on the git tree and with `lint_skill` on the vendored copy.
- **Evidence:** On `plugins/alpha/skills/link-skill` in the test fixture, adding a `120000` entry `"install.sh" -> "pip install foo"` causes `read_plugin` to record `install_hints: 1`, whereas `lint_skill` on a directory with a symlink/junction skips it (`install_hints: 0`).
- **Suggested fix:** Either refuse links inside skills (`mode == "120000"` and `is_link` in `lint_skill`), or have `lint_skill` read link targets via `_read_entry(path, is_link)` the same way `digest_tree` and `read_plugin` do.

---

## 3. MUTATION TESTING RESULTS

Ran **84 targeted mutations** on scratch copies in `R:\cl2-b-scratch\mut-work` across `toolchain_io.py`, `toolchain_mcp.py`, and `toolchain_sources.py`. **79 were caught; 5 survived** (exited 0 across the entire module test suite).

### Mutations that SURVIVED (no test noticed)

| # | Safeguard Area | File & Lines | Mutation Applied | Why No Test Caught It |
|---|---|---|---|---|
| **M-1** | Server label & version token sanitising | `scripts/toolchain_mcp.py`, lines 73-74, 285-292 | Allow token-shaped strings (`ghp_...`) or hostnames in `_server_info` (or widen `_SERVER_NAME` / omit token check) | `ServerInfoTests` (`test_toolchain_mcp.py`, lines 435-456) tests `"build.private.example"` as an **allowed** version and never tests a 24+ char token in `serverInfo.name` or `serverInfo.version`. |
| **M-2** | Size/page caps (`MAX_PAGES` in MCP `tools/list`) | `scripts/toolchain_mcp.py`, line 311 | Replace `for _ in range(MAX_PAGES):` with `while True:` | `StdioTests.test_a_cursor_that_never_ends_is_a_protocol_error` (`test_toolchain_mcp.py`, line 322) returns the same cursor `"same"` on page 1, which is caught by `cursor in seen` on iteration 2. No test returns distinct cursors (`c1`, `c2`, ...) past `MAX_PAGES` (200). |
| **M-3** | Child termination in `_Server.close()` | `scripts/toolchain_mcp.py`, line 277 | Replace `kill_tree(self.proc)` in `_Server.close()` with `pass` | On Windows, `terminate_tree(self.proc)` at line 272 already calls `kill_tree(self.proc)` (`toolchain_io.py`, line 229). No test mocks `terminate_tree` or tests a process that survives `terminate_tree` until line 277's `kill_tree`. |
| **M-4** | URL scheme check in `_check_url` | `scripts/toolchain_sources.py`, line 155 | Allow `http://` in `_check_url`: change `parts.scheme not in ("https", "file")` to `parts.scheme not in ("http", "https", "file")` | `ResolveGitRefTests.test_other_url_schemes_never_reach_git` (`test_toolchain_sources.py`, line 552) tests `"ext::..."`, `"git://..."`, `"ssh://..."`, and `"http-not-a-url"`, but never tests an `"http://..."` URL! |
| **M-5** | Link refusal in `vendor_skills` fast-path | `scripts/toolchain_sources.py`, line 817 | Change `if target.is_dir() and not _is_link(target):` to `if target.is_dir():` | No test in `VendorTests` (`test_toolchain_sources.py`) places a symlink or Windows junction at `store / "skills" / <name>` or `store / <shared>` before calling `vendor_skills`. |

### Summary of the 79 Caught Mutations by Safeguard Category

1. **Shim character class (`toolchain_io.py`, line 137):** Mutated each character one at a time (`&`, `|`, `<`, `>`, `^`, `%`, `"`, `\r`, `\n`), restricted check to `argv[1:2]`, dropped `.bat`, and made `.cmd`/`.bat` case-sensitive (12 mutations) — **all 12 caught** by `ShimTests.test_each_shell_metacharacter_is_refused_on_its_own_in_any_argument_position` and `test_the_refusal_covers_bat_files_and_any_letter_case_of_the_ending`.
2. **Tree kill (`toolchain_io.py`, lines 177-222):** Replaced `_system_taskkill()` with `shutil.which("taskkill")`, allowed relative `SystemRoot`, removed `/T`, and made `_taskkill` a no-op (4 mutations) — **all 4 caught** by `TaskkillTests` and `KillTreeTests`.
3. **`safe_detail` (`toolchain_io.py`, lines 66-99):** Dropped each branch of `_GLUED` (`\`, `/`, `@`, `.:.`, `^~`), disabled `_UNSAFE`, `_host_like`, `_IPV4`, `_ipv6_like`, `_token_like`, changed `{24,}` to `{25,}`, dropped `isdigit()` / `isalpha()` from `_token_like`, and removed `[:limit]` (14 mutations) — **all 14 caught** by `SafeDetailTests`.
4. **Redirect rules (`toolchain_io.py`, lines 254-275):** Allowed `https` -> `http`, cross-host redirects, arbitrary port changes, and forbade `80` -> `443` upgrade (4 mutations) — **all 4 caught** by `HttpTests.test_redirect_rule` and `test_a_redirect_keeps_the_port`.
5. **HTTP & source size caps (`toolchain_io.py`, `toolchain_sources.py`, `toolchain_mcp.py`):** Disabled `MAX_BODY` in `_collect`, `Content-Length > max_bytes`, streaming `total > max_bytes`, `>` vs `>=` off-by-one, and `total != declared` in `_hash_body`; disabled `MAX_LINE` and `cursor in seen` in `toolchain_mcp.py`; disabled `MAX_TREE_BYTES`/`MAX_TREE_FILES` in `_tree_entries`, `lint_skill`, and `_shared_entries_of`, and `MAX_LINT_FILE` in `_lint_files`/`_count_hints` (12 mutations) — **all 12 caught**. (Note: mutating `size > MAX_LINT_FILE` in `lint_skill` alone without mutating `_lint_files` is redundant because `_lint_files` re-checks `len(data) > MAX_LINT_FILE` in memory.)
6. **File-URL rules (`toolchain_sources.py`, lines 148-160):** Allowed non-empty `netloc`, relative path, `//` path, `\`, `query`, and `fragment` one by one (6 mutations) — **all 6 caught** by `ResolveGitRefTests.test_a_file_url_with_a_host_is_a_network_path_and_never_reaches_git`.
7. **Private Git environment (`toolchain_sources.py`, lines 163-191):** Omitted `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM`, `GIT_TERMINAL_PROMPT`, kept `GIT_CONFIG_COUNT`, `GIT_CONFIG_PARAMETERS`, numbered `GIT_CONFIG_KEY_*/VALUE_*`, `GIT_ASKPASS`, `GIT_SSH`, `GIT_SSH_COMMAND`, `SSH_ASKPASS`, widened `GIT_ALLOW_PROTOCOL` to `"https:file"` for `https`, omitted `-c protocol.ext.allow=never` and `-c credential.helper=`, and always passed `-c protocol.file.allow=always` (14 mutations) — **all 14 caught** by `PrivateGitSettingsTests`, `HostileGitConfigurationTests`, and `ExtHelperTests`.
8. **Environment allow-list (`toolchain_mcp.py`, lines 55-68, 147-187):** Allowed all parent vars, added `GITHUB_TOKEN` to `ENV_ALLOW_LIST`, added `_authToken` to `ENV_ALLOW_NPM`, dropped `cache` from `ENV_ALLOW_NPM`, kept `user:password@` or `?query#frag` in `_without_credentials`, kept unparseable proxy URLs, dropped `HTTP_PROXY` / `npm_config_registry` from `ENV_ADDRESS_NAMES`, and set `inherit=True` in `_Server` (10 mutations) — **all 10 caught** by `CaptureEnvTests` and `StdioTests`.
9. **npm cross-check, NuGet cap/hash, PyPI sorting (`toolchain_sources.py`, lines 492-621):** Skipped registry agreement check, compared only version or only integrity, accepted CLI when registry returned `"absent"`, rejected CLI when registry was unreachable, accepted CLI or registry without integrity, ran `npm view` with `cwd=None`, left temp folder behind, disabled `MAX_NUPKG` in both HTTP paths, matched NuGet pin by `_version_key`, skipped `.nupkg` hash, and removed PyPI filename sorting (14 mutations) — **all 14 caught** by `NpmTests`, `NugetTests`, and `PypiTests`.
10. **Link refusal, staging, digest check, and rollback (`toolchain_sources.py`):** Disabled symlink and junction checks in `_walk`, allowed `120000` in `_shared_entries_of`, allowed `160000` submodules in `_tree_entries`, disabled digest check in `_stage`, disabled `swap.rollback()` on `OSError` and `BaseException`, and removed `work` when `swap.restored` is `False` (8 mutations) — **all 8 caught** by `WalkTests`, `GitDigestTests`, `ReadPluginTests`, and `VendorTests`.
11. **MCP probe era decisions (`toolchain_mcp.py`):** Dropped `_VERSION_WORDS` guard, accepted any version in `_modern_answer`, fell back to `initialize` on `-32022`, did not restart silent server before `initialize`, skipped second `discover` after refused `initialize`, asked `discover` again even when first `discover` was answered, checked deadline only on empty queue, and omitted `session.close()` (8 mutations) — **all 8 caught** by `ModernAnswerTests`, `InitializeTests`, `ProbeDecisionTests`, `DeadlineTests`, and `StdioTests`.

---

## 4. CHECKED AND FINE

- **CRLF/LF normalisation & binary preservation:** `digest_tree`, `digest_git_tree`, `read_plugin`, `read_shared_entries`, and `vendor_skills` produce identical SHA-256 digests across LF and CRLF checkouts while preserving binary files (any file containing `\x00`) untouched.
- **Catastrophic backtracking (ReDoS) in `safe_detail`:** Tested `_NAME_RUN`, `_GLUED`, `_IPV4`, `_TOKEN`, and `_host_like` on 200,000-character adversarial inputs (`"a." * 100000`, `"a-" * 100000`, `"ab-cd.ef-" * 50000`); completed in `< 0.2s` (linear time).
- **Loopback HTTP streaming & deadlines (`SystemRunner.http` and `http_hash`):** Verified `read1` chunked streaming against trickling servers (`/dribble`), early connection close (`incomplete`), `MAX_BODY` (5 MB) and `MAX_HASHED` (200 MB) cutoffs, and loopback proxy bypass (`_is_loopback`).
- **Windows `.cmd`/`.bat` argument guard (`_SHIM_UNSAFE`):** Refuses `& | < > ^ % " \r \n` in every argument position (`argv[1:]`) across `.cmd` and `.bat` regardless of letter case before invoking `subprocess.Popen`.
- **Transactional swap and rollback (`_Swap` in `vendor_skills`):** Verified that failures on any move step (including `KeyboardInterrupt`) roll back all replaced/removed skills and shared folders, and preserve the backup under `.staging-*/old` if rollback itself encounters an `OSError`.
