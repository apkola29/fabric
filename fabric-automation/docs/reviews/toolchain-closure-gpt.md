# Closure review of the toolchain kit, slice C: the data, the documents and the first run (GPT 6.1 Sol)

The reply as it came back, with the agent's own header and its own top heading removed. It reviewed the published commit `a7932d1bf9` from a clean clone: whether the fixes of the first review closed the findings on the data, the documents and the first run (R-C-1, R-C-2, R-C-3, R-C-5, R-C-7, R-C-10 and R-A-8), five new findings (R-N3-1 to R-N3-5) and 13 mutants of the publish script, 4 of which survived. It also recomputed every skill digest and the digest of the shared folder from the pinned Git objects. The author's checks and the dispositions are in [toolchain-closure-findings.md](toolchain-closure-findings.md).

Reviewed commit **a7932d1bf9815db54a6ce685a5b0f4b98774b7d2**. The original clone remains unchanged. Experiments used scratch copies; first-run `HOME` and `USERPROFILE` were scratch folders. No sign-in, tenant-data query, real push, or license acceptance occurred. Doctor’s HTTP probes were anonymous.

Clean-copy baseline:

```powershell
python -m unittest scripts.test_toolchain scripts.test_sync_flow scripts.test_sync_script scripts.test_verify_facts scripts.test_validate_docs
```

**696 tests passed; 7 skipped.**

## 1. Closure

| Earlier finding | Decision | Independent evidence |
|---|---|---|
| **R-C-1 — missing shared references** | **Closed** | Default `install --apply` and explicit Claude installation produced 57 skills and 25 common files per host. All **619 common-file links** resolved in each installed tree. Temporarily moving `.github\common` away, then running `python scripts\toolchain.py verify --live --host copilot-cli --profile dev-factory`, returned **1**, reporting `[FAIL] V9: shared folder .github/common is missing`. Restoring it restored the installation. |
| **R-C-2 — scheduled execution of latest packages** | **Partly closed** | An independent dependency adapter supplied candidate version `9.9.9` while preserving the actual pinned Git sources. Production `update --check` launched **zero** stdio servers; `verify --contracts` selected **five locked-version launches**. Manual `lock --contracts` selected six candidate-version launches. The top-level separation works, but unpinned transitive dependencies remain: **R-N3-2**. |
| **R-C-3 — router/preamble versus skill surfaces** | **Closed for the reported surface errors** | Checked all **13 router rows** against the pinned skill/plugin texts. SQL database uses `sqlcmd`/REST, Warehouse uses the SQL MCP surface, Spark/Osmos use their helpers/REST, and report authoring uses its CLI. The Azure-cost endpoint/header matches the pinned plugin. Alias translation handles the renamed kit servers. The SQL tool-name disagreement remains explicitly disclosed, not guessed away. This was a static check, not authenticated execution. |
| **R-C-5 — `dnx --yes` and .NET 10** | **Not closed; runtime UNVERIFIED** | Minimum SDK 10 and the `--yes` launch remain. [Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-tool-exec) still says: **“Available starting with .NET 11.”** [NuGet’s package page](https://www.nuget.org/packages/Azure.Bicep.McpServer/0.48.1) emits a `dnx … --yes` template for a net10.0 tool; that is not proof that SDK 10 accepts the flag. This machine has SDK 9, so I could not settle runtime compatibility. Admitting uncertainty is honest, but does not close compatibility. |
| **R-C-7 — first-run instructions and hints** | **Partly closed** | Trust prompts, starting-folder behavior, and 56-upstream-plus-router counts are now explained. The Claude MCP hint correctly includes `--host claude-code`. However, after default installation, `doctor --offline` still reports missing `.claude/skills` with **`run: python scripts/toolchain.py install --apply`**—which does not install Claude. Repeating that command changed nothing and left the warning. Remaining fix: include the host in the skills hint, in `scripts/toolchain.py, lines 3058–3061`. |
| **R-C-10 — facts** | **Closed** | `fab` wording now identifies the Git-integration skill; the report-author CLI is declared and detected. The authoring page confirms **“DAX query execution tools have a hard limit of 100,000 rows.”** The ontology page confirms **“The old experience of ontology retires on Jan 31, 2027.”** Quarantine wording now distinguishes the documented experience from the design’s interpretation. The `uv` minimum needs no change. CLI pin enforcement is a separate defect below. |
| **R-A-8 — license-default override** | **Closed** | In a copy, set the offline variant’s `PBI_MODELING_MCP_ACCEPT_EULA` mapping to `{"from_env":"REVIEW_LICENSE","default":"true"}`. `verify --profile agent-implementer` and `render --profile agent-implementer --host copilot-cli` both returned **1**. V1 rejects setting the license variable at variant level. |

## 2. New defects

### R-N3-1 — Medium — Installing the kit breaks document validation and publishing

**Where:** `scripts/validate_docs.py, lines 72–78 and 496–506`; `scripts/sync_to_github.ps1, lines 235–241`.

**Wrong:** Generated, Git-ignored material is still read by the validator’s document context. Installed skills/common files produce structural, link, hygiene, and leak findings. Nested ignored `.gitignore` files also provoke rejection. Publishing validates the source **before** applying mirror exclusions, so the new publish exclusions cannot rescue the run.

**Reproduction:**

```powershell
python scripts\toolchain.py install --apply
python scripts\validate_docs.py --strict --quiet
```

Immediately after default installation: **exit 1, 2,237 errors, 6 warnings**. With Claude installed too: **3,355 errors, 9 warnings**. Findings include `.github/common/DATAFLOWS-AUTHORING-CORE.md` and ignored installed skill files. The untouched clean copy returned **0 errors, 0 warnings**.

**Fix:** Use the existing publishable-file/ignore model consistently when collecting documents and inspecting nested ignore files. Do not weaken leak or hygiene checks globally. Add an install-then-validate/publish integration regression.

### R-N3-2 — Medium — Scheduled RTI probing can execute newly resolved dependency code

**Where:** `.github/workflows/fabric-automation-facts.yml, lines 80–83`; `toolchain/toolchain.lock.json, lines 629–633`.

**Wrong:** The server wheel is pinned, but its dependency environment is not. The scheduled command selects:

```text
uvx microsoft-fabric-rti-mcp@0.6.2
```

Public [PyPI metadata](https://pypi.org/pypi/microsoft-fabric-rti-mcp/0.6.2/json) declares ranges including:

```text
fastmcp<4,>=3.0
azure-identity<2,>=1.24.0
msal<2,>=1.32.0
```

[uv’s documentation](https://docs.astral.sh/uv/guides/tools/) states: **“Tools are installed into temporary, isolated environments when using uvx.”**

A fresh hosted runner can therefore resolve and import dependency versions absent from the reviewed lock. Contract comparison happens **after code execution**. This preserves part of C-2’s supply-chain risk and conflicts with HR-9.

**Evidence:** The independent scheduled-path reproduction selected the exact locked RTI argv above; the dependency ranges were read directly from PyPI. No unreviewed package was executed during this review.

**Fix:** Provision a complete transitive, hash-locked environment and run it offline for scheduled checks. Keep newest-version capture explicitly opt-in.

### R-N3-3 — Medium — CLI package pins are not enforced or supplied to loaders

**Where:** `toolchain/toolchain.json, lines 83–84`; `scripts/toolchain.py, lines 3013–3029 and 1428–1459`.

**Wrong:** The lock pins report authoring to **0.5.0** and `fab` to **1.8.0**, but doctor checks only minimum versions. Live verification does not check these executables, and load plans omit their package pins.

**Reproduction:** Put scratch `.cmd` wrappers for `fab` and `powerbi-report-author` first on `PATH`, each printing `99.0.0`, then run:

```powershell
python scripts\toolchain.py doctor --offline
python scripts\toolchain.py verify --live
python scripts\toolchain.py render --profile agent-planner --host load-plan
```

Doctor returned **0** and marked both version **99.0.0 PASS**. Live verification returned **0**. The plan contained neither CLI package/pin. Thus the new lock entries do not constrain what the owning CLI skills execute.

**Fix:** Declare profile CLI dependencies, include their pins/integrities in load plans, and check provisioned CLI versions against the lock—not just compatibility minima.

### R-N3-4 — Low — A tracked sibling guide contains resource identifiers

**Where:** `fabric-monitoring-guides/capacity-metrics-app/README.md, lines 772`.

**Wrong:** A prose table contains a pasted deep-link fragment with **two complete GUIDs**, including an explicitly labelled dataset identifier. This is outside the kit, but inside the requested “any tracked file” exposure check.

**Reproduction, from the clone root:**

```powershell
Select-String -LiteralPath 'fabric-monitoring-guides\capacity-metrics-app\README.md' -Pattern 'pedetails/|dataset/'
```

It returns line 772, containing `pedetails/<GUID>/dataset/<GUID>/` embedded in “Daily metrics … per item”.

**UNVERIFIED:** Ownership, tenant, and whether those resources remain live. Exposure of the strings is verified; no access entitlement or secret was demonstrated.

**Fix:** Remove the pasted fragment. If identifiers are intended examples, replace them with explicit synthetic placeholders.

### R-N3-5 — Low — Four publish-exclusion safeguards have no effective regression coverage

**Where:** `scripts/test_sync_flow.py, lines 310–353`; `scripts/sync_to_github.ps1, lines 276–288`.

**Wrong:** Removing the source exclusions for research-local files, Python cache folders, pytest cache folders, or loose bytecode does not make the full publishing suite fail.

**Evidence:** Each separate mutant ran:

```powershell
python -m unittest scripts.test_sync_flow
```

Each returned **0: 55 tests, 2 skipped**. The tests cover destination cleanup, but do not seed all these source cases.

**Fix:** Seed each source category before publishing and assert it never appears in the mirror. These are test-suite holes—not evidence that the intact script currently publishes these files.

## 3. Mutation results

**13 mutants: 9 killed, 4 survived.**

| Safeguard removed/disabled | Result |
|---|---|
| `private` exclusion | Killed; full 55-test run |
| `.factory` exclusion | Killed; full 55-test run |
| `docs\research\local` exclusion | **Survived; full 55-test run** |
| `.github\skills` exclusion | Killed |
| `.github\common` exclusion | Killed |
| `.claude\skills` exclusion | Killed |
| `.claude\common` exclusion | Killed |
| `__pycache__` exclusion | **Survived; full 55-test run** |
| `.pytest_cache` exclusion | **Survived; full 55-test run** |
| `/XF '*.pyc'` | **Survived; full 55-test run** |
| `/XF '.mcp.json'` | Killed |
| V12 collision rejection | Killed; 413 tests, 13 failures |
| V13 writing-tool rejection | Killed; 413 tests, 9 failures |

For the five generated-path/file mutants, the detecting test was run first, followed by the module selector with `--failfast`:

```powershell
python -m unittest scripts.test_sync_flow.SyncFlowTests.test_what_the_toolchain_generates_for_a_machine_is_not_mirrored_but_its_committed_mcp_files_are scripts.test_sync_flow --failfast
```

Each failed that first test. Every reported survivor completed the **whole module**.

With intact code, renaming `fabric-sql` to bundled name `fabric-sqlendpoint` caused V12 failure; a writing annotation in `fabric-local/docs` caused V13 failure. With only the respective check disabled—and otherwise consistent data/generated files—**verify passed with either defect present**. The tests noticed both disabled checks.

An initial mutation run had unrelated Microsoft Store Python self-launch failures. It was discarded after a clean control failed; the final matrix used a passing control and isolated configuration.

## 4. Checked and fine

- **All 58 locked skill entries were independently recomputed from pinned Git objects. No digest, file-count, or byte-count mismatch.** The calculation sorted relative paths and hashed path, NUL, and normalized-content digest.
- Shared `common` matches **25 files, 435,667 bytes**, digest `sha256:d5d756d2ab4c9fe79e54c6946773de54ae9bef484cf1934f85e34f056e350f88`. Power BI’s three common files are byte-identical members of it.
- Both installed hosts’ **619 common-file references resolve**. The five disclosed upstream missing targets were independently confirmed absent at the locked commit; `mcp-setup` exists only at repository root.
- Lock integrity encodings are correct: four npm SHA-512 values decode to 64 bytes; NuGet SHA-256 decodes to 32 bytes; two PyPI hashes contain 64 hex digits. Binary package hashes were not all re-downloaded here.
- First-run `doctor`, install plan/application, `verify`, `verify --live`, `list`, all four renderers, and `fetch` succeeded. Repeat installation reported **62 unchanged**. Fetch reported **56 skills, 1,335 files, one shared folder**.
- Explicit Claude installation verified successfully; subsequent Copilot live verification also passed with the same-profile Claude file present.
- The lock’s five captured contracts have **6, 34, 62, 70, and 39 tools**, matching Limits. All three documented Power BI-dependent unattended plans were refused. No license was accepted.
- Router owners and alias translations matched the pinned sources. The cost endpoint/header is correct; its conservative read-write/dev-only declaration is appropriate. Git 2.32’s documentation contains the private-configuration environment variables the kit relies on.
- Both workflows pin Actions by SHA, use `contents: read`, disable checkout credential persistence, and avoid privileged pull-request triggers. The boolean capture input is not interpolated into shell code. Capture remains manual-only.
- **A hostile package is not sandboxed by environment scrubbing:** it can modify same-job checkout/output files and forge a candidate artifact. Neither workflow automatically commits or promotes that artifact; it must remain untrusted review input.
- Scanned **267 tracked files**, including visual inspection and raw-string checks of all five JPEGs. No authentication secret was found. Expected test placeholders, public GitHub identities, and redacted screenshots were distinguished from the identifier exposure above.

**Bottom line:** shared installation, alias guards, and license-default closure hold. Closure is incomplete for scheduled dependency pinning, .NET compatibility, and the remaining Claude hint. The first-run validator regression and four surviving exclusion mutations need attention.
