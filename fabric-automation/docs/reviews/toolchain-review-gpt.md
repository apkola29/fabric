# Review of the toolchain kit, slice A: the command line (GPT 6.1 Sol)

The reply as it came back, with the agent's own header removed, and with line references written as "file, lines N" (the document checks cannot resolve `file:line`). It reviewed the published commit `3494fe4223` from a clean clone, with 24 mutations of the command line. The author's checks and the dispositions are in [toolchain-review-findings.md](toolchain-review-findings.md).

## Baseline

`python -m unittest scripts.test_toolchain` passed **223 tests** in 10.575 seconds. Original `verify` returned 0 with four warnings. The clone remained unchanged. Experiments used scratch copies and fake homes; no authentication, tenant calls, or package installation occurred.

Below, `T` means this exact PowerShell function, run inside the specified project copy:

```powershell
function T { python -B .\scripts\toolchain.py @args }
```

Each reproduction used `HOME` and `USERPROFILE` pointing to its scratch `fake-home`. File locations are relative to `fabric-automation`.

## Findings

### R-A-1: High. An installed agent profile does not isolate its effective host configuration

**Where:** `scripts\toolchain.py`, lines 2383-2419 and 1904-1935

**Evidence:** In `user-scope-retention`, run:

```powershell
T install --profile dev-factory --host copilot-cli --scope user --skip-skills --apply
T install --profile agent-intake --host copilot-cli --scope user --skip-skills --apply
T verify --profile agent-intake --live --host copilot-cli
```

All returned 0. The supposedly empty agent configuration retained seven user-level servers, including credentialed, networked and writing variants.

Separately, rendering `dev-factory` to `.mcp.json`, then installing `agent-intake` for Copilot, left the former file untouched while `.github\mcp.json` became empty. Live verification still passed.

[GitHub's documentation](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers) states: "If both `.mcp.json` and `.github/mcp.json` exist in the same directory, `.mcp.json` takes precedence."

**Fix:** Require isolated configurations for non-dev modes. Reject unsafe inherited configuration and conflicting higher-priority files rather than deleting user-owned entries.

### R-A-2: High. Unattended preflight permits missing contract captures

**Where:** `scripts\toolchain.py`, lines 1198-1204 and 1949-1966

**Evidence:** On an unchanged copy:

```powershell
T verify --profile agent-planner --contracts
T verify --profile executor-sandbox-read --strict
```

Both returned 0. The former warned that `fabric-local/docs` was skipped; the latter reported zero warnings despite skipped contracts.

Consequently, missing contract evidence does not stop unattended work. V13 also performs no read-only assessment for these uncaptured contracts.

**Fix:** Require nonempty captured contracts matching the locked package and effective launch for agent/executor profiles. Missing captures, skipped checks and unavailable probes must fail those modes.

### R-A-3: High. Agent launch plans can install packages at runtime

**Where:** `scripts\toolchain.py`, lines 1026-1038 and 1271-1282

**Evidence:** `T render --profile agent-implementer --host load-plan` emits `npx -y` launches with pinned package versions, without an offline/no-install requirement.

The [npm execution documentation](https://docs.npmjs.com/cli/v11/commands/npm-exec) states: "The requested packages are installed to a folder in the npm cache, which is added to the `PATH` environment variable in the executed process."

A cold-cache launch can therefore download/install before the supposedly offline server starts. No download was performed during this review.

**Fix:** Non-dev plans should launch preprovisioned, integrity-checked executables from the immutable pack/image, not runtime package installers.

### R-A-4: Medium. The job load plan omits the required factory router

**Where:** `scripts\toolchain.py`, lines 1285-1299 and 2222-2231; `AGENTS.md`, line 8

**Evidence:** `T render --profile agent-planner --host load-plan` listed only `semantic-model-authoring` and `powerbi-report-cli`. It did not include `factory-router`, although that skill says it is required for every factory job.

`fetch` likewise selects only resolved upstream skills. Only `install` adds repository-owned skills.

**Fix:** Include repository-owned skills, with pinned digests, in both the load plan and fetched pack for applicable profiles. Preserve intentionally empty profiles.

### R-A-5: Medium. The inputs digest omits effective launches and security policy

**Where:** `scripts\toolchain.py`, lines 966-974 and 1043-1053

The digest covers whole skill-source declarations, declared packages, variant argument lists and quarantine, but not launch commands/base arguments, environments, mode policy or profiles.

**Evidence:** In `digest-launch`, change `fabric-local.launch.command` to `arbitrary-command`. `T verify --profile agent-planner` returned 0 and the load plan emitted that command.

In `mode-upper-bound`, replace `modes.agent.allow` with dev's allow-list and select `fabric-core/default` for `agent-intake`. Verification and rendering returned 0, with unchanged lock inputs, producing a hosted-server plan labelled `agent`.

**Fix:** Bind effective launches and security-sensitive profile/policy inputs into freshness checks. Enforce the hard mode ceilings independently of editable allow-lists.

### R-A-6: Medium. Offline lock refresh can bless unresolved source changes

**Where:** `scripts\toolchain.py`, lines 1468-1473 and 1813-1831

**Evidence:** In `offline-lock-launder`, change the Fabric source repository to `https://github.com/acme/other-skills.git`:

```powershell
T verify --profile agent-planner
T lock --no-network
T verify --profile agent-planner
```

Exit codes were **1, 0, 0**. The lock still contained the original Microsoft repository and commit.

**Fix:** Reject resolver-affecting changes during offline refresh, or invalidate affected entries. Verification should compare resolved source identity/path information with the manifest.

### R-A-7: Medium. Rendering and installation bypass V12/V13 failures

**Where:** `scripts\toolchain.py`, lines 1229-1258, 2127-2151 and 2422-2426

**Evidence:** In separate copies, add `fabric-local` to a locked plugin's bundled-server names, or give its captured docs contract a tool with `read_only:false`.

```powershell
T verify --profile agent-planner
T render --profile agent-planner --host load-plan
T install --profile agent-planner --host copilot-cli --skip-skills --apply
```

Exit codes were **1, 0, 0** in both cases. Deleting the contract entry also produced **1, 0, 0**.

**Fix:** Use one profile-scoped validation path for verification, rendering, fetching and installation, including package/contract coverage and V12/V13.

### R-A-8: Medium. A variant can bypass the license-default safeguard

**Where:** `scripts\toolchain.py`, lines 677-689 and 1033-1034

**Evidence:** In `license-variant-env`, override the offline Power BI variant's environment:

```json
"PBI_MODELING_MCP_ACCEPT_EULA": {
  "from_env": "REVIEW_LICENSE",
  "default": "true"
}
```

Verification returned 0. Copilot rendering emitted `${REVIEW_LICENSE:-true}`, which accepts the license when that variable is unset.

The [upstream README](https://raw.githubusercontent.com/microsoft/powerbi-modeling-mcp/main/README.md) specifies: "Set `PBI_MODELING_MCP_ACCEPT_EULA` to `true` in the server's environment."

**Fix:** Validate license variables after merging each variant's environment; prohibit acceptance flags/defaults that circumvent explicit operator consent.

### R-A-9: Medium. A syntactically valid marker authorizes deletion of foreign content

**Where:** `scripts\toolchain.py`, lines 1759-1773 and 2322-2342

**Evidence:** In `marker-removes-unmanaged`, create a personal `my-notes` skill. Create a marker listing it, with zero SHA-256 values for both lock and skill digest:

```powershell
T install --profile agent-intake --host copilot-cli --skip-mcp --apply
```

It returned 0 and deleted `my-notes`, without `--force`, although its bytes did not match the marker.

**Fix:** Validate ownership/provenance and compare actual content with the previously recorded digest before destructive changes. Otherwise report a conflict.

### R-A-10: Medium. Predictable staging names are deleted without ownership checks

**Where:** `scripts\toolchain.py`, lines 2266-2268

**Evidence:** In `unmanaged-staging-delete`, create user data at `.github\skills\.toolchain-new-factory-router\sentinel.txt`:

```powershell
T install --profile dev-docs --host copilot-cli --skip-mcp --apply
```

It returned 0 and deleted the sentinel.

**Fix:** Allocate unique staging directories exclusively. Never recursively remove an existing staging-shaped directory merely because its name matches.

### R-A-11: Medium. Installation follows a destination junction outside project scope

**Where:** `scripts\toolchain.py`, lines 2442-2445 and 2262-2276

**Evidence:** In `junction-parent`, make `.github\skills` a Windows junction to `R:\scratch-a\repros\junction-user-owned`. Run the same dev-docs install command above.

It returned 0 and created `factory-router\SKILL.md` in the junction target.

**Fix:** Check destination roots, ancestors and staging paths for symlinks/reparse points and resolved containment before writing.

### R-A-12: Medium. Skill replacement deletes the old directory before committing the new one

**Where:** `scripts\toolchain.py`, lines 2273-2275

**Evidence:** In `atomic-inline`, install dev-docs, change the router source, then inject a rename failure:

```powershell
python -B -c "from scripts import toolchain as t; from unittest.mock import patch; patch('os.replace', side_effect=OSError('rename fault')).start(); t.main(['install','--profile','dev-docs','--host','copilot-cli','--skip-mcp','--apply'])"
```

Exit code was 1. The installed router was gone and staging remained. Output had already said "applied."

**Fix:** Preserve the previous directory until commit succeeds, restore it on failure, clean staging and report completion only afterward.

### R-A-13: Medium. Live verification accepts an empty marker with missing required skills

**Where:** `scripts\toolchain.py`, lines 1877-1901

**Evidence:** In `empty-marker-live`, render agent-planner's project files and create a fresh-lock marker with `skills:{}`, but no installed skill folders:

```powershell
T verify --profile agent-planner --live --host copilot-cli
```

It returned 0. Actual installed skill count was zero.

**Fix:** Check required resolved skills and applicable repository-owned skills against installed state, not just whatever the marker lists.

### R-A-14: Medium. `doctor --offline` still performs credentialed account checks

**Where:** `scripts\toolchain.py`, lines 2560-2564

**Evidence:** A recording fake runner observed `gh auth status` and `az account show` during `doctor --offline`; no real credentialed commands were executed.

The [GitHub CLI documentation](https://cli.github.com/manual/gh_auth_status) states: "Any expired or near-expiry token that supports refreshing is refreshed automatically, unless `--no-refresh` is given."

Thus this ostensibly offline diagnostic can also refresh credentials.

**Fix:** Skip authentication checks offline. Make credentialed checks explicit opt-in operations; disable refresh for diagnostics.

### R-A-15: Low. Public-output sanitization permits private capture metadata

**Where:** `scripts\toolchain.py`, lines 209-214 and 1402-1438

**Evidence:** In `captured-label-leaks`, an injected probe returned a server name containing a drive path and a user-like folder name, and a version `build.private.example`. Capture accepted them; `T lock --no-network` and `T render --profile agent-planner --host load-plan` preserved both.

A boolean check also confirmed `safe_detail` preserves a synthetic token-shaped sentinel. No real token was used.

**Fix:** Scan or tightly whitelist upstream strings before persistence/output. Prefer known identifiers and reason codes over arbitrary diagnostic text.

## Mutation testing

Every mutant was an independent project-layout copy under `R:\scratch-a\mutations\Mxx`. Each ran:

```powershell
python -m unittest scripts.test_toolchain
```

**24 mutations: 21 caught, 3 survived.** Each survivor passed all 223 tests.

| Mutation | Result | Detecting test |
|---|---|---|
| M01 Remove network comparison | Caught | N |
| M02 Remove credentials comparison | Caught | C |
| M03 Remove access comparison | Caught | A |
| M04 Executor skips network comparison | Caught | E |
| M05 Executor skips credentials comparison | Caught | E |
| M06 Executor skips access comparison | Caught | E |
| M07 Disable unattended requirement | Caught | U |
| M08 Accept `unverified` as unattended | Caught | U |
| M09 Include quarantine in wildcard expansion | Caught | Q |
| M10 Ignore explicit quarantine selection | Caught | X |
| M11 Disable stale-lock loading refusal | Caught | S |
| M12 Disable verification's stale-lock check | Caught | V |
| M13 Dev unresolved package becomes failure | Caught | P |
| M14 Agent unresolved package becomes warning | Caught | P |
| M15 Executor unresolved package becomes warning | Caught | P |
| M16 Ignore unmanaged-folder ownership conflict | Caught | I |
| M17 Remove marker profile validation | **Survived** | None |
| M18 Remove marker lock-digest validation | **Survived** | None |
| M19 User merge discards existing content | Caught | M |
| M20 Overwrite user server without force | Caught | M |
| M21 Disable license default-false validation | Caught | L |
| M22 Accept `yes` as license consent | Caught | W |
| M23 Omit user MCP backup | Caught | M |
| M24 Delete installed destination before copy-digest validation | **Survived** | None |

Test identifiers, all in `scripts.test_toolchain`:

- N: `ModeRuleTests.test_a_networked_variant_is_refused_in_the_agent_mode`
- C: `ModeRuleTests.test_a_credentialed_variant_is_refused_in_the_agent_mode`
- A: `ModeRuleTests.test_a_write_variant_is_refused_in_the_agent_mode`
- E: `ModeRuleTests.test_the_executor_may_use_microsoft_cloud_and_azure_identity_but_nothing_more`
- U: `ModeRuleTests.test_a_variant_that_is_not_known_to_be_unattended_is_refused_where_unattended_is_required`
- Q: `QuarantineTests.test_a_wildcard_expands_to_the_plugin_minus_the_quarantine`
- X: `QuarantineTests.test_an_explicit_quarantined_name_is_an_error`
- S: `InstallTests.test_a_stale_lock_is_refused`
- V: `VerifyTests.test_v3_a_stale_lock_fails`
- P: `VerifyTests.test_v3_an_unresolved_package_is_a_warning_in_dev_and_a_failure_in_agent_and_executor`
- I: `InstallTests.test_an_unmanaged_folder_is_a_conflict_that_is_not_overwritten_without_force`
- M: `InstallTests.test_the_user_scope_merges_into_the_users_mcp_file`
- L: `SchemaTests.test_the_license_variable_must_be_passed_through_and_default_to_false`
- W: `HelperTests.test_a_license_is_accepted_only_by_the_exact_word_true`

## Checked and fine

- With unchanged policy, network/credentials/access and unattended comparisons reject prohibited variants.
- Wildcards exclude quarantine; explicit quarantine selections fail across modes. Identical skills from two plugins deduplicate; different digests fail.
- Ordinary unmanaged folders are preserved without force, including a differently cased folder on this Windows filesystem.
- Dev user-scope merging preserves unrelated servers/settings, backs up changes and is idempotent.
- Floating package versions fail. Covered-input changes produce stale-lock failures.
- Captured-contract tool additions/removals/schema or annotation changes fail contract comparison. V12 folds case; V13 rejects false/null read-only annotations in captured contracts.
- BOM/CRLF handling, normalized digests, LF generated files and individual JSON atomic writes held up.
- Simple traversal/absolute paths in manifest paths and locked skill paths were rejected.
- Three-host shapes and environment syntax matched current [VS Code](https://code.visualstudio.com/docs/agents/reference/mcp-configuration) and [Claude](https://code.claude.com/docs/en/mcp) documentation; Copilot entries have explicit `tools` arrays.
- Normal doctor (with faked external checks), verify, list, offline-lock and load-plan outputs did not expose private sentinels.

**UNVERIFIED:** Actual Linux execution, native host launch acceptance and tenant identity behavior. No whole-suite or live-authentication testing was performed.
