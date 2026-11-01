# Closure check of the toolchain kit after the third review, slice C: the data, the documents and the first run (Grok 4.7)

The reply as it came back, with the agent's own header removed. It checked the published commit `2231f55f7a` from a clean clone: whether the fixes closed R-D3-1, R-D3-2 and R-C-5, a cold read of the new documents and their numbers, a first run of the kit (doctor, install, a second install, verify, list, the renderings, fetch twice and the validator), the two workflows, and one new finding (R-E3-1). The author's checks and the dispositions are in [toolchain-recheck-findings.md](toolchain-recheck-findings.md).

## Closure

**R-D3-1 — closed.** `bicep-mcp` now launches `dotnet tool exec Azure.Bicep.McpServer@0.48.1 --yes` and declares the four `DOTNET_*` variables with defaults. The workflow comment no longer says the image ships the SDK "for dnx". The manifest summary, README Limits, and `t10` section 7 match what I could run. `dnx.cmd` is next to `dotnet` in the official 10.0.403 Windows zip. Render of `dev-azure`: Copilot CLI and Claude Code pass `${DOTNET_NOLOGO:-1}` and the other three defaults; VS Code does not (finding below).

**R-D3-2 — closed.** The Limits sentence now says the weekly check bounds servers it launches and does not install the two CLIs. `bounded_environment` is still called only from `verify --contracts` (`toolchain.py`, line 2614). The facts workflow does not install `fab` or `powerbi-report-author`.

**R-C-5 — closed for `--yes`; banner half UNVERIFIED.** Official zip `https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.403/dotnet-sdk-10.0.403-win-x64.zip`, `dotnet --version` 10.0.403. Help of `dotnet tool exec` and `dnx` lists neither `--yes` nor `-y`. A local tool that prints its arguments, from a local feed: `dotnet tool exec PKG@1.0.0 --yes` and `--yes` before the package both printed `ARGS:` with nothing after it. `dnx.cmd` did the same for `--yes` after, `--yes` before, and `-y` before. `--bogus-option` after the package printed `ARGS:--bogus-option`. Without `--yes`, empty stdin, the tool ran at once (exit 0). A fresh home and no `DOTNET_*` variables produced empty stderr and only `NuGet.Config`. This machine already has .NET 6 and 9, so I do not treat that as a refutation of the author's banner and certificate observation.

## Cold read and numbers

`def test_` counts are 628, 118, 146, and 307. Helper total 571 matches the findings file. The replay script is not in the tree; 51 = 38 + 13 is the author's record, not re-run here. Run 41292342224 is this commit (`2231f55f7a`), success: `Ran 1525 tests in 214.218s`, `OK (skipped=86)`, validator 0 errors, `verify` 0 failures and 6 warnings. Probe 41290137534 is branch `ci-probe`, not this SHA: `Ran 1525 tests in 150.693s`, `OK (skipped=86)`. The log's "151 seconds" is that figure rounded. Facts run 41253985240 is `abe6b9d614`, and Loop 11 says so. No secret, tenant, workspace id, personal path, or token in the new review text, the toolchain README, or the two workflows.

The probe-revision sentence matches `toolchain_mcp.py`: `DISCOVER_WAIT = 20.0`, and an `initialize` answer whose revision this client does not speak is left before `tools/list`. Section 3.13 was not edited; agent and executor profiles still do not launch `bicep-mcp`, so "npx or uvx and offline" still holds for those planes.

## First run

Scratch copy. `doctor --offline` exit 0 (dotnet 9.0.320 is below the minimum 10; sign-in skipped). `install` plan: 60 to add, 0 conflicts. `install --apply` exit 0. Second apply: 0 to add, 0 to change, 62 unchanged; the store was already current. `verify --live` exit 0: report CLI at 0.5.0, `fab` missing (warning). `agent-planner` load plan carries that tool with its sha512 integrity, `preinstalled`, and the Fabric server args start with `--offline`.

`fetch --profile agent-planner` twice while the pack already matched: both exit 0, and markers planted in `.factory/pack/.cache` were still there. After deleting `powerbi-report-cli` from the pack, the next fetch removed the cache folder of the commit it needed (`PLANTED.txt` gone, folder recreated) and left the other commit's cache. That matches "when it needs a commit", not "on every fetch". `validate_docs.py --strict` after that: 0 errors, 0 warnings. `verify --live` for `dev-factory` then warned that the pack no longer lists the other skills, because a profile-scoped fetch rewrites the store to the selection.

## Workflows

Both files: `contents: read`, checkout and upload-artifact pinned by SHA, `persist-credentials: false`, `inputs.capture` only in `if:`. The new limit is `timeout-minutes: 20` on the validate job (it was 10). This commit's run finished in about four minutes, so the extra time is headroom, not a change to what is checked. The date bound is still applied by `verify --contracts`, not by a workflow input. The facts comment now says the image has the SDK and no `dnx` on PATH, which matches the image readme and the zip layout.

## New finding

**R-E3-1. Low.** `scripts/toolchain.py`, lines 1528–1530, and the VS Code rendering of `dev-azure`. Copilot CLI and Claude Code get `${DOTNET_NOLOGO:-1}` and the other three defaults. VS Code gets `${env:DOTNET_NOLOGO}` with no default, and the same for the other three. An unset variable therefore does not opt out of telemetry or skip the certificate when VS Code starts the server. The kit's own probe path still applies the defaults. Suggested fix: write the literal defaults into the VS Code `env` block, or document that this host does not receive them.
