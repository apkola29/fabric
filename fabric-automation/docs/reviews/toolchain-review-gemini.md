# Review of the toolchain kit, slice C: data, documents, workflows and the first run (Gemini 4 Argon)

The reply as it came back, with the agent's own header removed, line references written as "file, lines N" (the document checks cannot resolve `file:line`), one symbol replaced by plain text, and one sentence reworded so that it does not repeat the author's user name. It reviewed the published commit `3494fe4223` from a clean clone. The author's checks and the dispositions are in [toolchain-review-findings.md](toolchain-review-findings.md).

## Findings (ranked by impact)

### R-C-1: High. Vendored `skills-for-fabric` skills lose their required `common/` directory when installed, breaking 498 mandatory reference links

* **Where:** `fabric-automation/scripts/toolchain_sources.py` (lines 390-396, `read_plugin`; lines 613-623, `vendor_skills`), `toolchain/toolchain.lock.json` (lines 331-594)
* **What is wrong:** `read_plugin()` groups files exclusively under `skills/<name>/...` (`if parts[0] == "skills" and len(parts) >= 3`), ignoring the sibling `common/` directory in `plugins/fabric-skills/common/` (28 files) and `plugins/powerbi-authoring/common/` (3 files). When `fetch` or `install --apply` vendors skills into `.factory/pack/skills/<name>` and copies them into `.github/skills/<name>` and `.claude/skills/<name>`, every relative link to `../../common/COMMON-CLI.md`, `../../common/COMMON-CORE.md`, `../../common/EVENTHOUSE-CONSUMPTION-CORE.md`, etc. points to a non-existent `.github/common/` or `.factory/pack/common/` folder. Almost every Fabric skill (`activator-cli`, `dataflows-cli`, `deployment-pipelines-authoring-cli`, `eventhouse-cli`, `eventstream-cli`, `fabriciq`, `semantic-model-authoring`, `spark-cli`, `sqldb-cli`, `sqldw-cli`, etc.) states in its `SKILL.md` that reading `../../common/COMMON-CLI.md` or `../../common/COMMON-CORE.md` is **Mandatory** before acting.
* **Evidence:**
  Reproduced in `R:\scratch-c\fabric-automation`:
  ```powershell
  git --git-dir .factory\pack\.cache\4c3986d2e5b4 ls-tree -r 4c3986d2e5b498ce2d6e6025533b94b5e5bb2ccd:plugins/fabric-skills | Select-String "common/"
  # Lists 28 files under common/ (COMMON-CLI.md, COMMON-CORE.md, EVENTHOUSE-CONSUMPTION-CORE.md, etc.)
  Get-ChildItem -Recurse .factory\pack\skills\*.md | Select-String "\.\./\.\./common/" | Measure-Object
  # Count: 498 matches across 22 skills and their references/ subdirectories
  Test-Path .factory\pack\common; Test-Path .github\common; Test-Path .claude\common
  # False, False, False
  ```
* **Suggested fix:** Vendor each plugin's `common/` directory alongside `skills/` (into `.factory/pack/common/`, `.github/common/`, and `.claude/common/` with digest tracking in `toolchain.lock.json` and `.toolchain-managed.json`), or rewrite/inline `../../common/` into each vendored skill tree and compute digests over the self-contained tree.

---

### R-C-2: High. Scheduled CI workflow (`fabric-automation-facts.yml`) executes unpinned upstream `latest` code on every Monday run (`npx`, `uvx`, `dnx`)

* **Where:** `.github/workflows/fabric-automation-facts.yml` (lines 53-62), `fabric-automation/ci/fabric-automation-facts.yml` (lines 53-62), `fabric-automation/toolchain/toolchain.json` (lines 139, 191, 254, 269, 289)
* **What is wrong:** All five local MCP server packages in `toolchain.json` have `"track": "latest"`. In the weekly `toolchain` job of `fabric-automation-facts.yml`, both `python3 scripts/toolchain.py update --check --contracts` and `python3 scripts/toolchain.py lock --contracts` call `build_lock(..., contracts=True)`. `build_lock()` first resolves the latest version of every package from npm, PyPI, and NuGet (`toolchain.py`, line 669), and then immediately calls `capture_contract()` (line 685), which spawns `npx -y <pkg>@<new_latest>`, `uvx <pkg>@<new_latest>`, and `dnx <pkg>@<new_latest> --yes` inside the runner before any human has reviewed the new version. If any of those upstream packages is compromised on npm/PyPI/NuGet, arbitrary attacker code executes in the GitHub Actions runner during the scheduled run, can poison `$RUNNER_TEMP/toolchain-update.md` (`$GITHUB_STEP_SUMMARY`) and `fabric-automation/toolchain/toolchain.lock.json`, and uploads a forged `toolchain-lock-candidate` artifact (including fabricated `read_only: true` tool annotations that bypass V13).
* **Evidence:**
  In `scripts/toolchain.py` (lines 669-686), `build_lock()` populates `packages[key]` from `deps.resolve_package(..., package["track"])` (where `track` is `"latest"`) and passes the newly resolved `packages` map into `capture_contract(manifest, packages, server, variant, deps)`, which runs `probe_stdio([launch["command"]] + launch["args"])`.
* **Suggested fix:** Separate version discovery from contract execution, or pin `"track"` in `toolchain.json` to reviewed versions and have `update --check` only query registry metadata without spawning newly published versions until a PR updates the version pin; or run contract capture inside an isolated network-jailed container after package download.

---

### R-C-3: High. Fundamental contradiction between `factory-preamble.md` / `factory-router` ("MCP-only, never swap in CLI/REST, never rename tools") and the pinned skills and MCP servers

* **Where:** `fabric-automation/toolchain/skills/factory-router/SKILL.md` (lines 27-44), `fabric-automation/toolchain/instructions/factory-preamble.md` (lines 13-16), `fabric-automation/AGENTS.md` (lines 13-16)
* **What is wrong:** `factory-preamble.md` ("How to work" 1 and 4) and `factory-router` ("Pick the owner" and "Run it" 1) instruct the agent: *"Run its live steps with the MCP tool that the skill and your profile name. Do not quietly swap in a script, the Fabric CLI or a REST call for a missing MCP tool. Say what is missing and stop that step."* and *"Do not guess a new name."* Inspecting the actual pinned skills at `microsoft/skills-for-fabric@v0.3.20` and `microsoft/azure-skills@v1.2.109` reveals five direct collisions that force a compliant agent to dead-stop on routine tasks:
  1. **SQL Database (`sqldb-cli`):** `factory-router` maps `"Warehouse or lakehouse SQL | sqldw-cli, sqldb-cli | fabric-sql"`. However, `sqldb-cli/SKILL.md` states: *"use `sqldb-cli` ONLY for a Fabric SQL database item (the OLTP, SQL Server engine). A Warehouse, a Lakehouse SQL endpoint or a Mirrored Database is `sqldw-cli`"* and executes T-SQL exclusively via `sqlcmd -Q`/`-i` and `az rest` (`0` mentions of MCP). Furthermore, the `fabric-sql` MCP server only supports Fabric Data Warehouses and Lakehouse SQL analytics endpoints, not OLTP SQL Databases.
  2. **SQL Warehouse (`sqldw-cli`):** `sqldw-cli/SKILL.md` (lines 75-83) instructs the agent to invoke `fabric-sqlendpoint-execute_query` from the `fabric-sqlendpoint` server, whereas the kit renames the server to `fabric-sql` (to satisfy V12) and the live server exposes `executeSQL` (per Learn). Under preamble rule 4 (*"If a tool is missing, renamed... stop. Do not guess a new name"*), the agent must stop.
  3. **Spark and Osmos (`spark-cli`, `project-osmos`):** `factory-router` pairs `spark-cli` and `project-osmos` with `fabric-local`. Neither `spark-cli` nor `project-osmos` contains a single reference to MCP (`0` matches); both execute exclusively via `az rest` and bundled Python helpers, and `fabric-local` has zero Spark, Livy, MLV, or Osmos tools (only `docs`, `core`, `onelake`, and `datafactory`).
  4. **Real-Time Intelligence (`eventhouse-cli`, `eventstream-cli`, `activator-cli`):** `factory-router` pairs these with `fabric-rti-local`. In `v0.3.20`, all three are CLI skills built around `az rest`; `eventstream-cli` has `0` mentions of MCP, `eventhouse-cli` mentions a different server name (`fabric-kql`), and `activator-cli` mentions only the remote per-item Activator MCP (`get_activations_for_rule`), never `fabric-rti-local`'s `kusto_*`, `eventstream_*`, or `activator_*` tools.
  5. **Azure Cost (`cost-analysis`, `cost-estimation`, `cost-governance`, `cost-optimization`) and Azure (`azure-*`):** Loaded by `dev-azure` and `dev-factory`. All four `cost-*` skills require `azure-resource-manager-mcp` (`https://mcp.management.azure.com`, tools `query_costs`, `forecast_costs`, `query_aks_costs`), which is not in `toolchain.json` at all. And `azure-*` skills call `mcp__azure__*` (server id `azure`) and `mcp_bicep_*` (server id `bicep`), whereas `toolchain.json` registers `azure-mcp` and `bicep-mcp`.
* **Evidence:**
  ```powershell
  foreach ($s in @("sqldw-cli","sqldb-cli","spark-cli","eventhouse-cli","eventstream-cli","activator-cli","project-osmos")) {
    $m = Get-ChildItem -Recurse ".factory\pack\skills\$s" | Select-String "mcp"
    "$s : $($m.Count) matches"
  }
  # sqldw-cli : 92, sqldb-cli : 0, spark-cli : 0, eventhouse-cli : 3, eventstream-cli : 0, activator-cli : 13, project-osmos : 0
  ```
* **Suggested fix:** Align `factory-router/SKILL.md` and `factory-preamble.md` with what the `*-cli` skills actually do: document that in `skills-for-fabric@v0.3.20` most workload skills are CLI/REST skills (hence their `-cli` suffix) while MCP servers provide complementary or alternative surfaces; explicitly map the tool/server name translations (`fabric-sql` / `executeSQL`, `azure-mcp`, `bicep-mcp`); fix the `sqldb-cli` row in `factory-router`; and either add `azure-resource-manager-mcp` or document that `cost-*` skills use their REST fallback.

---

### R-C-4: High. Unresolved `nuget:Azure.Bicep.McpServer` in committed `toolchain.lock.json` breaks `fetch`, `render`, and `install` for `dev-azure` (and `fetch` with no arguments)

* **Where:** `fabric-automation/toolchain/toolchain.lock.json` (lines 634-638), `fabric-automation/scripts/toolchain.py` (lines 451-458, 566-588, 979-999)
* **What is wrong:** `toolchain.lock.json` ships with `"nuget:Azure.Bicep.McpServer": {"status": "unresolved", "reason": "network", "detail": "tls"}`. While `verify` downgrades an unresolved package in `dev` mode to a `WARN` (V3), `resolve_profile()` unconditionally calls `server_launch()` → `package_spec()`, which raises `ToolchainError("package nuget:Azure.Bicep.McpServer is unresolved in the lock")`. Consequently:
  1. `python scripts/toolchain.py fetch` (with no arguments, as instructed in `toolchain/README.md`, line 91) iterates over all profiles that select skills, hits `dev-azure`, and crashes with exit code 1 before fetching anything.
  2. `python scripts/toolchain.py install --profile dev-azure` and `python scripts/toolchain.py render --profile dev-azure --host copilot-cli` fail with exit code 1.
  3. `python scripts/toolchain.py verify --live --profile dev-azure` silently skips all V9 live checks for `dev-azure` (`except ToolchainError: continue` at `toolchain.py`, lines 813-815) and exits `0` with `[INFO] V9: live checks done for 3 host(s)`.
* **Evidence:**
  Reproduced in `R:\scratch-c\fabric-automation`:
  ```powershell
  python scripts/toolchain.py fetch
  # error: package nuget:Azure.Bicep.McpServer is unresolved in the lock (exit code 1)
  python scripts/toolchain.py install --profile dev-azure
  # error: package nuget:Azure.Bicep.McpServer is unresolved in the lock (exit code 1)
  python scripts/toolchain.py verify --live --profile dev-azure
  # Result: 0 failure(s), 1 warning(s) (exit code 0: silently skipped V9!)
  ```
* **Suggested fix:**
  1. Resolve `nuget:Azure.Bicep.McpServer` on a runner with NuGet access and commit the resolved lock.
  2. In `cmd_fetch()`, use `select_skills(manifest, lock, profile)` instead of `resolve_profile()` so an unresolved MCP package does not block skill vendoring.
  3. In `_check_live()`, record a `FAIL` (or `WARN` in `dev` mode) on V9 when `resolve_profile()` raises `ToolchainError`, instead of silently continuing.

---

### R-C-5: Medium. `bicep-mcp` launch arguments (`dnx Azure.Bicep.McpServer@<ver> --yes`) are invalid on .NET 10 SDK (`--yes` requires .NET 11)

* **Where:** `fabric-automation/toolchain/toolchain.json` (lines 58, 289-290)
* **What is wrong:** `toolchain.json` declares `dotnet` with `"min": "10", "needed_for": "the Bicep MCP server (dnx)"` and configures `bicep-mcp` with `"launch": {"command": "dnx", "args": ["{package}", "--yes"]}`. According to Microsoft Learn's official `dotnet tool exec` (`dnx`) documentation, the `-y|--yes` option is **only available starting with .NET 11**, not .NET 10. Furthermore, in `dnx` syntax, options not preceded by `--` are parsed by `dotnet tool exec` itself; on .NET 10, passing `--yes` to `dnx` fails as an unrecognized option.
* **Evidence:**
  Primary source: https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-tool-exec, under **Options**:
  > `-y|--yes`: Accepts all confirmation prompts, including the prompt to download and run the tool package. Use this option only with packages and package sources that you trust. **Available starting with .NET 11.**
* **Suggested fix:** Remove `"--yes"` from `bicep-mcp`'s `launch.args` for .NET 10 compatibility (or check how `dnx` on .NET 10 invokes tools without `--yes`), or update the minimum .NET requirement and documentation accordingly.

---

### R-C-6: Medium. `install --apply` on a machine with Claude Code writes `.mcp.json`, which hijacks Copilot CLI and VS Code and breaks `git status`

* **Where:** `fabric-automation/scripts/toolchain.py` (lines 934, 1045-1088), `fabric-automation/.gitignore` (lines 21-26), `fabric-automation/toolchain/README.md` (lines 10-12)
* **What is wrong:**
  1. `fabric-automation/.gitignore` has `/.mcp.json` with a leading slash. Because this `.gitignore` is inside the `fabric-automation/` subfolder (not the repo root), `/.mcp.json` ignores `fabric-automation/.mcp.json`. However, the comment in `.gitignore` (lines 21-22) explicitly warns: *"`# .mcp.json is the Claude Code file; Copilot CLI would also read it first, so it is never committed.`"*
  2. When a user has `claude` on `PATH` (as on our test machine) and runs `python scripts/toolchain.py install --apply` (Step 3 of "Start from scratch" in `toolchain/README.md`), `cmd_install` auto-detects all installed hosts (`copilot-cli`, `vscode`, `claude-code`) and writes `.mcp.json` in `fabric-automation/`.
  3. Because `.mcp.json` now exists on disk, **Copilot CLI and VS Code read `.mcp.json` in precedence over `.github/mcp.json`**, loading the Claude Code rendering (which lacks the explicit `"tools": ["*"]` allow-list on every server and uses `"type": "stdio"` instead of `"type": "local"`).
  4. In addition, `install --apply` installs all 57 skills into **both** `.github/skills` and `.claude/skills`. Both VS Code and Copilot CLI scan both `.github/skills` and `.claude/skills` (per `t10-toolchain-grounding.md` section 6 and VS Code docs: *"Project skills, stored in your repository: `.github/skills/`, `.claude/skills/`, `.agents/skills/`"*), causing duplicate skill discovery in VS Code.
* **Evidence:**
  Reproduced in `R:\scratch-c\fabric-automation`:
  ```powershell
  python scripts/toolchain.py install --apply
  # Writes .mcp.json, .github/skills/*, and .claude/skills/*
  $env:COPILOT_HOME = "R:\scratch-c\home\.copilot"
  copilot mcp list --json
  # Shows fabric-local, powerbi-authoring-local, azure-mcp with type="stdio" (from .mcp.json) instead of type="local" (from .github/mcp.json)!
  ```
  And primary source https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers:
  > *"If both `.mcp.json` and `.github/mcp.json` exist in the same directory, `.mcp.json` takes precedence."*
* **Suggested fix:** Require an explicit `--host` when multiple incompatible hosts are on `PATH` (or default to not writing `.mcp.json` and `.claude/skills` when `copilot-cli`/`vscode` are also targeted unless `--host claude-code` is explicitly requested), and include `"tools": ["*"]` or avoid writing `.mcp.json` alongside `.github/mcp.json`.

---

### R-C-7: Medium. First-run experience gaps: Copilot CLI and Claude Code silently ignore project MCP servers until workspace trust / server approval is granted

* **Where:** `fabric-automation/toolchain/README.md` (lines 9-15, "Start from scratch")
* **What is wrong:** Following "Start from scratch" step by step on a clean machine:
  1. **Folder trust / server approval omitted:** Step 6 says *"Start your host inside the `fabric-automation` folder... `AGENTS.md` and the `factory-router` skill route Fabric, Power BI and Azure tasks to the owning skill and MCP server"*. In reality, on a clean machine (`HOME` pointed to a fresh folder), `copilot mcp list` in `fabric-automation` **silently omits all 7 workspace MCP servers** until the folder is trusted interactively (or via `trusted_folders`), and Claude Code leaves all `.mcp.json` servers in a pending-approval state until approved. `t10-toolchain-grounding.md` section 6 notes both facts, but `toolchain/README.md` never mentions them in "Start from scratch".
  2. **False claim about starting in `fabric-automation`:** Step 6 claims: *"Start your host inside the `fabric-automation` folder (Copilot CLI reads the project's MCP files from the folder it starts in and the folders above it, up to the repository root, never from folders below)"*. Because the git repository root is the parent folder (`R:\clone-c`) and `.github/mcp.json` is inside `R:\clone-c\fabric-automation\.github\mcp.json`, starting Copilot CLI in any subfolder below `fabric-automation` (e.g. `fabric-automation\docs`) **does** walk up through `fabric-automation` to the repo root and load `fabric-automation\.github\mcp.json`. Conversely, starting Copilot CLI at the repository root (`R:\clone-c`) does **not** find `fabric-automation\.github\mcp.json`.
  3. **`doctor` remediation hint for `claude-code` fails to fix the warning:** Before `install --apply`, `python scripts/toolchain.py doctor` prints:
     `[WARN] host claude-code mcp: .mcp.json is missing (run: python scripts/toolchain.py render --write-project)`
     Running `python scripts/toolchain.py render --write-project` only writes `.github/mcp.json` and `.vscode/mcp.json` (`PROJECT_HOSTS = ("copilot-cli", "vscode")` at `toolchain.py`, line 55), leaving `.mcp.json` missing and the `doctor` warning unresolved!
  4. **Count discrepancy in `install` output vs README:** `toolchain/README.md` (line 127) says `57 project skills` and `list` says `dev-factory ... 57`, whereas `install` prints `+ store .factory/pack: fetch 56 skill(s)` because 56 come from the upstream pack and the 57th (`factory-router`) is copied from `toolchain/skills/factory-router`.
* **Evidence:**
  Reproduced in `R:\scratch-c\fabric-automation`:
  ```powershell
  python scripts/toolchain.py doctor
  # [WARN] host claude-code mcp: .mcp.json is missing (run: python scripts/toolchain.py render --write-project)
  python scripts/toolchain.py render --write-project
  # unchanged .github/mcp.json (profile dev-factory)
  # unchanged .vscode/mcp.json (profile dev-factory)
  Test-Path .mcp.json
  # False
  ```
* **Suggested fix:**
  1. In `_doctor_hosts()` (`toolchain.py`, line 1135) and `_check_live()` (line 822), when `host not in PROJECT_HOSTS`, print `run: python scripts/toolchain.py install --apply` (or `render --host claude-code --output .mcp.json`) instead of `RENDER_HINT`.
  2. Add a bullet in "Start from scratch" Step 6 noting that Copilot CLI and Claude Code require accepting the workspace trust / server approval prompt on first launch before project MCP servers appear.
  3. Clarify Step 6's wording on directory traversal: starting at the repo root (`R:\clone-c`) misses `fabric-automation/.github/mcp.json`, so start in `fabric-automation` (or a folder inside it).

---

### R-C-8: Medium. `doctor` and `verify --live` miss stale/wrong-profile skills and repo-owned skills on zero-upstream-skill profiles

* **Where:** `fabric-automation/scripts/toolchain.py` (lines 791-834, `_check_skills_dir` and `_check_live`; lines 1141-1149, `_doctor_hosts`)
* **What is wrong:** Three verification blind spots in `V9` (`verify --live`) and `doctor`:
  1. **`verify --live` never checks `marker["profile"]`:** In `_check_skills_dir()` (lines 799-808), `verify --live` checks `marker["lock"] != lock_digest(lock)` and loops over `marker["skills"].items()`, **never checking whether `marker["profile"] == resolved["name"]` or whether every skill in `resolved["skills"]` is actually present in `marker["skills"]`**. If a user ran `install --profile dev-docs --apply` (which installs only `factory-router` into `.github/skills`), and `.github/mcp.json` is restored to `dev-factory`, `python scripts/toolchain.py verify --live` (for `dev-factory`, which requires 57 skills) passes with **0 failures** even though 56 of the 57 skills are missing from `.github/skills`!
  2. **`doctor` only checks `marker["lock"]`:** In `_doctor_hosts()` (lines 1141-1149), `doctor` only checks `read_marker(marker)["lock"] != resolved["lock"]`. If `marker["profile"]` is from another profile (`dev-docs`) or if skill folders inside `.github/skills/` were deleted after install, `doctor` still prints `[PASS] host copilot-cli skills: the managed skills in .github/skills match the lock`.
  3. **Duplicate `V9` failure lines and skipped `dev-docs` check:** When `copilot-cli` and `vscode` are both checked in `_check_live()`, both point to `.github/skills`, so any failure in `.github/skills` is printed **twice**. And for `dev-docs` (which has 0 upstream skills, `has_skills = False`, even though `install` installs `factory-router` into `.github/skills`), if `.github/skills` is deleted, `verify --live --profile dev-docs` and `doctor --profile dev-docs` both report `PASS` because `has_skills` only checks `bool(resolved["skills"])` and ignores `repo_skills(project)`.
* **Evidence:**
  Reproduced in `R:\scratch-c\fabric-automation`:
  ```powershell
  python scripts/toolchain.py install --profile dev-docs --apply
  python scripts/toolchain.py render --write-project
  Remove-Item .mcp.json
  python scripts/toolchain.py verify --live --host copilot-cli vscode
  # Result: 0 failure(s), even though .github/skills only has 1 skill (factory-router) instead of dev-factory's 57 skills!
  ```
* **Suggested fix:** In `_check_skills_dir()` and `_doctor_hosts()`, verify `marker["profile"] == resolved["name"]` and verify that the set of skill names in `marker["skills"]` equals the union of `resolved["skills"]` and `repo_skills(project)` (when `resolved["skills"]` or `resolved["mcp"]` is non-empty); deduplicate `(directory, label)` across hosts in `_check_live()`; and set `has_skills = bool(resolved["skills"] or (resolved["mcp"] and repo_skills(project)))`.

---

### R-C-9: Medium. `factory-router` is invisible to `list`, `verify` (V8), and `render --host load-plan` (K9 job loader never receives `factory-router`)

* **Where:** `fabric-automation/scripts/toolchain.py` (lines 576-588, `resolve_profile`; lines 604-618, `_load_plan`), `fabric-automation/AGENTS.md` (line 8), `fabric-automation/toolchain/README.md` (lines 83-85)
* **What is wrong:** `AGENTS.md` (Step 2) and `factory-router/SKILL.md` ("Use first for any Fabric, Power BI or Azure task in the fabric-automation repository and for every factory job") state that every session and every factory job uses `factory-router`. However, `factory-router` is only injected as a special case inside `skill_ops()` during `install` (`toolchain.py`, lines 983-987). It is **not** included in `resolve_profile()`, `_load_plan()`, `cmd_list()`, or `run_verify()` (V8 lint check). As a result:
  1. `python scripts/toolchain.py render --profile agent-implementer --host load-plan` omits `factory-router` completely, and `python scripts/toolchain.py fetch` never copies `factory-router` into `.factory/pack/skills/`. A factory job using the load plan and `.factory/pack` (per `toolchain/README.md`, lines 83-85) never receives `factory-router`.
  2. `python scripts/toolchain.py list --profile dev-factory` reports `Skills: 57` because `fabric-skills` and `powerbi-authoring` both contain `semantic-model-authoring` and `_skill_count` counts `select_skills` before deduplication (it lists `semantic-model-authoring` twice, and `factory-router` is not listed at all).
  3. `python scripts/toolchain.py verify` never runs `lint_skill` (V8) on `toolchain/skills/factory-router`.
* **Evidence:**
  Reproduced in `R:\scratch-c\fabric-automation`:
  ```powershell
  python scripts/toolchain.py list
  # dev-factory  dev  57  7  Working on the factory itself
  python scripts/toolchain.py list --profile dev-factory
  # Skills: 57 (lists semantic-model-authoring twice: once from fabric-skills, once from powerbi-authoring; factory-router is not listed at all!)
  python scripts/toolchain.py render --profile agent-implementer --host load-plan | Select-String "factory-router"
  # (no output)
  ```
* **Suggested fix:** Include repo-owned skills (`toolchain/skills/*`) in `resolve_profile()` (for non-empty profiles), `vendor_skills()` (`.factory/pack/skills/`), and `run_verify()` (V8 lint), and deduplicate `select_skills()` by skill name so `semantic-model-authoring` is not counted twice in `list`.

---

### R-C-10: Low. Fact-check findings against primary sources (`toolchain.json`, `toolchain/README.md`, `t10-toolchain-grounding.md`)

* **Where:**
  1. `fabric-automation/toolchain/toolchain.json` (line 59, `uv` minimum version)
  2. `fabric-automation/toolchain/toolchain.json` (line 60) and `toolchain/README.md` (line 9) (`fab` needed by "many Fabric skills")
  3. `fabric-automation/docs/research/raw/t10-toolchain-grounding.md` (line 95, Power BI Authoring 100,000-row limit claim)
  4. `fabric-automation/toolchain/toolchain.json` (line 103) and `toolchain/README.md` (line 60) (`fabriciq-ontology-cli` quarantine rationale)
* **What is wrong:**
  1. **`uv` minimum version `0.4` vs `0.13.6`:** `toolchain.json` sets `"min": "0.4"` for `uv`, while the facts workflow installs `uv==0.13.6`. (`uvx` was introduced in `uv` 0.4.0, which holds up, though `0.4` is from 2024).
  2. **`fab` ("the Fabric CLI that many Fabric skills call"):** `toolchain.json` claims `fab` is needed for `"the Fabric CLI that many Fabric skills call"`. Across all 24 skills in `microsoft/skills-for-fabric@v0.3.20`, **only 1 skill** (`git-integration-operations-cli`) invokes `fab`; the other 23 use `az rest`, `sqlcmd`, `powerbi-report-author`, or MCP tools. Conversely, `powerbi-report-author` (`@microsoft/powerbi-report-authoring-cli`), which `powerbi-report-cli` and `factory-router` ("plus the skill's own CLI") directly rely on, is **not** checked by `doctor` or listed in `toolchain.json` `tools`.
  3. **100,000-row limit claim in `t10-toolchain-grounding.md`:** it states: *"(A row cap on the DAX execution tools is not stated on the current README or Learn page; an old release note speaks of 100,000, which this note does not rely on.)"* That is false: the cited Learn page (`https://learn.microsoft.com/en-us/power-bi/developer/mcp/power-bi-authoring-mcp`) explicitly states under **Considerations and limitations**: *"DAX query execution tools have a hard limit of 100,000 rows."*
  4. **`fabriciq-ontology-cli` quarantine description:** `toolchain.json` says `"It authors the ontology entity-JSON format that retires on 2027-01-31"`. The Learn Ontology overview page (`https://learn.microsoft.com/en-us/fabric/iq/ontology/overview`) states *"The old experience of ontology retires on Jan 31, 2027"*, while `fabriciq-ontology-cli` uses the Fabric REST API (`POST /v1/workspaces/{ws}/items` / `updateDefinition` with `definition.json` and `EntityTypes/*.json`). Quarantining the skill until Stage 2 / S6 is a sound design choice, but the Learn page calls it "the old experience of ontology", not "the ontology entity-JSON format".
* **Evidence:**
  - `https://learn.microsoft.com/en-us/power-bi/developer/mcp/power-bi-authoring-mcp`, Considerations and limitations: `"DAX query execution tools have a hard limit of 100,000 rows."`
  - `https://learn.microsoft.com/en-us/fabric/iq/ontology/overview`: `"The old experience of ontology retires on Jan 31, 2027. For more, see Migrate from old experience."`
  - Grep across `.factory/pack/skills/*`: `\bfab\s+` matches only `git-integration-operations-cli` (58 matches; 0 in the other 23 Fabric skills).
* **Suggested fix:** Change the `fab` entry of `toolchain.json` to `"the Fabric CLI that git-integration-operations-cli calls"`, add `powerbi-report-author` (`@microsoft/powerbi-report-authoring-cli`) to `toolchain.json` `tools` (optional), and update `t10-toolchain-grounding.md`.

---

### R-C-11: Low. Skill lint (`_lint_files`) only scans 8 file extensions and skips files > 2 MB, allowing uncounted install hints in other scripts

* **Where:** `fabric-automation/scripts/toolchain_sources.py` (lines 265, 332-338, 418)
* **What is wrong:** `_count_hints()` only scans files ending in `(".md", ".txt", ".json", ".py", ".ps1", ".sh", ".yml", ".yaml")` and silently skips any file larger than `MAX_LINT_FILE` (2 MB) or with other extensions (e.g., `.ts`, `.js`, `.cs`, `.cmd`, `.bat`, `Dockerfile`, `Makefile`). In the locked skills today, 31 files have other extensions (e.g., `.ts`, `.cs`, `.bicep`, `.tf`, `Dockerfile.*`). If an upstream skill puts an `npm install` or `npx` command in a `.js`/`.ts`/`.cmd` script or a file > 2 MB, `install_hints` and `findings` remain `0` and V8 will not warn or fail.
* **Evidence:**
  In `toolchain_sources.py` (lines 265, 332-336):
  ```python
  _HINT_ENDINGS = (".md", ".txt", ".json", ".py", ".ps1", ".sh", ".yml", ".yaml")
  ```
  And in `lint_skill()` (line 372): `if rel != "SKILL.md" and os.path.getsize(path) > MAX_LINT_FILE: continue`.
* **Suggested fix:** Scan all text files (any file without a NUL byte, matching `_normalise()`) up to the tree limit, and record a lint `finding` (rather than silently skipping) if any file in a skill exceeds `MAX_LINT_FILE`.

---

## Checked and fine

The following areas were inspected against primary sources, the codebase, and live execution in `R:\scratch-c` and held up:

1. **Public exposure and secret/PII hygiene (Slice C item 3):**
   - Ran `python scripts/validate_docs.py --strict` in `R:\clone-c\fabric-automation`: 0 errors, 0 warnings across 88 text files, 200 tables, 140 links, and 136 file references.
   - Scanned all tracked files in `R:\clone-c\fabric-automation` and both workflow files for the author's user name, local paths (Windows user folders, `/Users/`, `/home/`, synced-folder names), Microsoft internal domains/hosts, tenant/subscription/workspace/item GUIDs, e-mail addresses, and tokens. Zero leaks found in any tracked file of `fabric-automation` or the two workflow files.
   - Checked `toolchain.py` and `toolchain_io.py` (`safe_detail`, `display_path`): error details and paths written into `toolchain.lock.json` or printed by `doctor`/`verify` strip hostnames, URLs, IPv4 addresses, e-mail addresses, and replace the user's home directory with `$HOME`.

2. **GitHub Actions workflow structure and baseline security (Slice C item 2):**
   - Both workflow files under `.github/workflows/` are byte-for-byte identical to `fabric-automation/ci/fabric-automation-*.yml` (enforced in CI by `diff -u`).
   - All third-party/GitHub actions (`actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`, `actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9`) are pinned to full 40-character commit SHAs with `persist-credentials: false`.
   - Workflow-level permissions are `contents: read` on both workflows.
   - No untrusted GitHub event context (`${{ github.event.issue.title }}`, PR body, branch name, commit message, etc.) is interpolated into any `run:` script block, so there is no Actions expression script injection.
   - `capture_env()` in `toolchain_mcp.py` (lines 113-131) strips environment variables down to `ENV_ALLOW_LIST` before spawning any stdio MCP server, preventing ambient secrets (`GITHUB_TOKEN`, `AZURE_*` unless declared) from leaking to child processes during contract capture.

3. **Lock file integrity and consistency with manifest and profiles (Slice C item 5):**
   - `inputs_digest` matches `inputs_digest(manifest)`.
   - Both upstream git commits (`microsoft/azure-skills` tag `v1.2.109` → `fbda857c484a85c7ce644f56809b7f204471fb69`; `microsoft/skills-for-fabric` tag `v0.3.20` → `4c3986d2e5b498ce2d6e6025533b94b5e5bb2ccd`) resolve on GitHub and match the tags.
   - Fetched all 56 non-quarantined upstream skills into `R:\scratch-c\fabric-automation\.factory\pack\skills` and recomputed `digest_tree()` on every skill folder: all 56 SHA-256 digests, file counts, and normalised byte counts in `toolchain.lock.json` matched 100%.
   - Checked `semantic-model-authoring` in both `fabric-skills` and `powerbi-authoring`: identical digest (14 files, 225,505 bytes).
   - Verified all 5 resolved package versions and SHA-512/SHA-256 hashes in `toolchain.lock.json` (`@azure/mcp@4.0.0-beta.4`, `@microsoft/fabric-mcp@1.6.0`, `@microsoft/powerbi-modeling-mcp@1.0.0`, `microsoft-fabric-rti-mcp@0.6.2`, `ms-fabric-cli@1.8.0`) live against npm and PyPI: all 5 hashes and versions match upstream.
   - Verified `bundled_mcp` names in `toolchain.lock.json` (`azure`, `azure-resource-manager-mcp`, `FabricIQ`, `fabric-sqlendpoint`, `powerbi-modeling-mcp`) against the upstream `.mcp.json` files at the locked commits: exact match, and V12 properly prevents project server ID collisions with them.

4. **Mode rules and hard-rule enforcement across the 14 profiles (HR-3, HR-9, HR-12, K4/K6/K7/K9/K10):**
   - Verified that `agent-*` profiles only load `credentials: "none"`, `network: "none"`, `access: "read"`, `unattended: true` variants (`fabric-local/docs` and `powerbi-authoring-local/offline-readonly`), and that `agent-intake` and `agent-verifier` are empty.
   - Verified that `executor-*` profiles only load `access: "read"`, `unattended: true` variants with `none` or `azure-identity` credentials, and never load `fabric-rti-local` (`unattended: "unverified"`) or any `entra-delegated` / hosted server.
   - Verified that `.github/mcp.json` and `.vscode/mcp.json` exactly match `render` output for `dev-factory` (V5), and that `PBI_MODELING_MCP_ACCEPT_EULA` defaults to `false` in `.github/mcp.json` and is never set to `true` by the kit.

5. **Primary-source verification of server URLs, headers, flags, and statuses (Slice C item 1):**
   - `fabric-local` (`@microsoft/fabric-mcp@1.6.0`): `server start --mode all`, `--read-only`, `--namespace docs`, Node.js 22+ requirement, and Public Preview status verified against `microsoft/mcp` `servers/Fabric.Mcp.Server/README.md` and Learn.
   - `fabric-core` (`https://api.fabric.microsoft.com/v1/mcp/core`), `fabric-iq` (`https://fabriciq.svc.cloud.microsoft/v1/mcp/fabriciq` with header `X-VARIANTS: Fabric.Routing.FabricIQ.V1`, GA, delegated-only, 6 read-only tools), `powerbi-authoring-remote` (`https://api.fabric.microsoft.com/v1/mcp/powerbi/authoring`, preview), `powerbi-authoring-local` (`@microsoft/powerbi-modeling-mcp@1.0.0`, GA, `--start`, `--readonly`, `--authmode=serviceprincipal`, `PBI_MODELING_MCP_ACCEPT_EULA`, `accept_eula` tool), `fabric-sql` (`https://api.fabric.microsoft.com/v1/mcp/dataPlane/sqlEndpoint`, tool `executeSQL` on Learn vs `execute_query` in `.github/plugin/marketplace.json`), `fabric-rti-local` (`microsoft-fabric-rti-mcp@0.6.2`, `uvx`, Public Preview, `DefaultAzureCredential`), `azure-mcp` (`@azure/mcp@4.0.0-beta.4`, `server start --read-only`), and `microsoft-learn` (`https://learn.microsoft.com/api/mcp`, 3 tools, no auth) all verified against their primary Learn pages and upstream GitHub READMEs.
