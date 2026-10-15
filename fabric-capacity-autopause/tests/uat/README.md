# Live auto-pause acceptance tests

`Invoke-AutoPauseUat.ps1` is a reusable PowerShell 7+ harness for an **already deployed**
Azure Automation runbook. It submits actual jobs and pauses/resumes **one explicitly
specified TEST Microsoft Fabric F-SKU capacity**. Never select a production capacity.

## Prerequisites

- Run `scripts\deploy.ps1` first. Use its printed resource group, Automation account,
  runbook, and identity values. The same values are available in `infra\main.bicep`
  outputs: `resourceGroupName`, `automationAccountName`, `runbookName`,
  `identityClientId`, `identityPrincipalId`, and `nightlyScheduleName`.
- PowerShell 7+ and Azure CLI installed; `az login` completed in the appropriate cloud
  tenant. This harness supports public Azure endpoints.
- The signed-in CLI caller needs Contributor-or-better **capacity permissions including
  resume**, suspend, read, and tag updates. This is separate from the deployed runbook
  identity, which should have suspend but **not** resume permission.
- The caller also needs Automation account/runbook/schedule reads; job creation, reads,
  stream reads, and stop rights; schedule/job-schedule create/delete rights for S11;
  Activity Log read; and role-assignment/role-definition read. Contributor alone does
  not necessarily grant every read at every assignment scope.
- The runbook is Published; the expected nightly schedule is enabled and linked.
- A stable Active or Paused **F-SKU TEST capacity** in the same subscription as the
  Automation account. It may be in a different resource group.
- Coordinate a maintenance window: no users, scaling, other UAT runs, or overlapping
  nightly/backstop jobs should operate on the test capacity during testing.
- For optional S09, the signed-in caller must be able to obtain a Fabric API token
  and see the capacity in `GET https://api.fabric.microsoft.com/v1/capacities`.

## Usage

Run from the repository root. Replace every angle-bracket placeholder before execution.
The full resource ID has this form:

```text
/subscriptions/<subscription-id>/resourceGroups/<capacity-resource-group>/providers/Microsoft.Fabric/capacities/<test-capacity-name>
```

Start with the **offline plan**, which makes no CLI/API calls and writes no files:

```powershell
.\tests\uat\Invoke-AutoPauseUat.ps1 `
    -SubscriptionId '<subscription-id>' `
    -ResourceGroupName '<automation-resource-group>' `
    -AutomationAccountName '<automation-account>' `
    -CapacityResourceId '/subscriptions/<subscription-id>/resourceGroups/<capacity-resource-group>/providers/Microsoft.Fabric/capacities/<test-capacity-name>' `
    -WhatIf
```

Run all standard scenarios, skipping S11 unless explicitly enabled:

```powershell
.\tests\uat\Invoke-AutoPauseUat.ps1 `
    -SubscriptionId '<subscription-id>' `
    -ResourceGroupName '<automation-resource-group>' `
    -AutomationAccountName '<automation-account>' `
    -CapacityResourceId '/subscriptions/<subscription-id>/resourceGroups/<capacity-resource-group>/providers/Microsoft.Fabric/capacities/<test-capacity-name>' `
    -ExpectedTimeZone '<deployed-time-zone-id>' `
    -ExpectedLocalTime '<HH:mm>' `
    -ResultPath '.\uat-results'
```

Opt in to the actual one-time schedule trigger. Specify the attached identity client ID
if the account has more than one user-assigned identity:

```powershell
.\tests\uat\Invoke-AutoPauseUat.ps1 `
    -SubscriptionId '<subscription-id>' `
    -ResourceGroupName '<automation-resource-group>' `
    -AutomationAccountName '<automation-account>' `
    -CapacityResourceId '/subscriptions/<subscription-id>/resourceGroups/<capacity-resource-group>/providers/Microsoft.Fabric/capacities/<test-capacity-name>' `
    -UserAssignedIdentityClientId '<managed-identity-client-id>' `
    -RunbookName '<published-runbook-name>' `
    -ExpectedNightlySchedule '<nightly-schedule-name>' `
    -IncludeScheduleTrigger -ScheduleLeadMinutes 8 `
    -JobTimeoutMinutes 20 -ResultPath '.\uat-results\acceptance.json'
```

Choose scenarios (S01 is always included):

```powershell
.\tests\uat\Invoke-AutoPauseUat.ps1 `
    -SubscriptionId '<subscription-id>' `
    -ResourceGroupName '<automation-resource-group>' `
    -AutomationAccountName '<automation-account>' `
    -CapacityResourceId '/subscriptions/<subscription-id>/resourceGroups/<capacity-resource-group>/providers/Microsoft.Fabric/capacities/<test-capacity-name>' `
    -Scenarios S02,S03,S04,S05,S07,S10 -ResultPath '.\uat-results'
```

`-SkipResumeScenarios` reports S02/S03/S04/S06/S08/S09/S11 as SKIPPED rather than
preparing an Active capacity. S05 can pause an Active capacity to establish its
idempotency prerequisite; S07 validates the current state without changing it.
**Restoration can still resume an originally Active capacity.**

`-LeaveAsIs` intentionally leaves the final power state and test-modified autopause tag
in place. It does **not** retain the temporary schedule/link, request files, or unfinished
jobs. Omit this switch for ordinary acceptance testing.

Defaults: runbook `Invoke-FabricCapacityAutoPause`, nightly schedule `autopause-nightly`,
job timeout 20 minutes, schedule lead 8 minutes, all scenarios selected. Empty
`ExpectedTimeZone`/`ExpectedLocalTime` skip the respective checks. When only the local
time is supplied, it is checked in the schedule's actual time zone.

## Scenarios (executed in order)

| ID | Test | Acceptance / caveat |
|---|---|---|
| S01 | Preconditions | One F SKU, original state/tags captured, Automation account found, one attached identity selected, Published runbook, enabled/linked nightly schedule, optional zone/nextRun local-time checks. A failure blocks all other scenarios. |
| S02 | Dry run | Active; `DryRun=true`; Completed; `WouldPause=1`; remains Active. |
| S03 | Exclusion tag | Active; `autopause=skip`; enforcing job Completed with `Excluded=1`; remains Active; test tag removed afterward. |
| S04 | Enforcement | Active; enforcing job Completed with `Paused=1`; ARM Paused. `PauseInProgress=1` is acceptable and noted (WARN) once ARM is Paused; no new suspend event is required for an existing pause. Otherwise successful suspend is attributed to the identity principal/client GUID; log delay/unavailability becomes WARN after up to five minutes. |
| S05 | Idempotency | Paused (setup pauses it if necessary, noting acceptable `PauseInProgress`); repeat Completed with **only** `Skipped=1`; remains Paused. `PauseInProgress` is not an idempotency result. |
| S06 | Scope narrowing | Active; protected full `CapacityResourceId` **and** deliberately nonmatching `CapacityName`; **Failed**, output contains `The requested capacity was not found, or the identity cannot read it.`, no Summary line; remains Active. This expected job failure is a PASS. |
| S07 | Invalid input | `DryRun=maybe`; Failed with `Invalid DryRun`; state unchanged. This expected job failure is a PASS. |
| S08 | End-user flow | Establish Paused, resume to Active, enforcing job pauses it again. |
| S09 | Fabric visibility | Report Fabric capacity state/id after pause and after resume; ARM failures fail, inaccessible/missing Fabric snapshots WARN. Observation only, not a Fabric/ARM consistency guarantee. |
| S10 | Least privilege | Read assignments/definitions; an unconditional applicable suspend action must exist, and no listed action can contain `*`, resume, or delete. No destructive permission probes. |
| S11 | Schedule trigger | Only with `-IncludeScheduleTrigger`; Active; unique one-time UTC schedule submits a scoped enforcing job; Completed and Paused; link/schedule deleted in finally. |

Selected scenarios establish their own state and can create setup jobs. The final
job list includes those setup jobs. Failure injection is deliberately not included.

## Safety and cleanup

- A full capacity ID is mandatory. Invalid IDs, cross-subscription IDs, non-F SKUs,
  transitional original states, and failed S01 checks are rejected before mutations.
- Every job submitted by the harness, including the temporary schedule, includes the
  same `CapacityResourceId`, `SubscriptionIds`, and selected managed-identity client ID.
  Additional name filters only narrow this scope. Existing production schedules/links
  are inspected, never edited or invoked.
- Every Azure CLI call supplies `--subscription`; the script never calls
  `az account set` or changes the caller's global default subscription.
- The capacity **will pause and resume**. Workloads can be interrupted. Active periods
  incur several minutes of **F-SKU billing**, potentially longer during queueing,
  Activity Log waits, schedule tests, retries, and state transitions.
- The original `autopause` tag is temporarily removed when necessary for positive
  tests, even if it originally equals `skip`. The original tag value is restored in
  the outer finally block; if absent originally, it is removed. Other tags are merged
  and preserved. Do not concurrently edit this same tag.
- Finally restores Active via resume if originally Active, or Paused via suspend if
  originally Paused. Temporary schedule/link deletion and unfinished-job settlement
  happen first to avoid a late job racing restoration. Cleanup errors cause FAIL and
  nonzero exit. If a live job/schedule cannot be settled, power restoration is withheld
  with explicit manual-recovery instructions rather than falsely claiming success.
- After S11's effective trigger boundary, an empty jobs list is **not** evidence that
  dispatch did not occur. Cleanup polls for up to `JobTimeoutMinutes` for a matching
  job and confirms Completed/Failed/Stopped/Suspended before restoring. If dispatch
  remains unaccounted for (including persistent list/detail failures), restoration of
  power/tags is skipped, a loud **CAPACITY STATE UNCERTAIN** warning is printed, and
  the run exits nonzero. Schedule and link deletion is always attempted, including
  with `-LeaveAsIs`. In the Automation account Jobs view, inspect this runbook around
  the effective UTC start, include queued jobs, and stop/wait for all possible target
  jobs to settle. Verify both temporary resources are gone, then check ARM state and
  restore manually; do not resume while a dispatched job may still pause the capacity.
- A forcibly terminated process, lost credentials, machine shutdown, or revoked rights
  can prevent finally cleanup. Use printed job IDs and the JSON report to investigate
  and restore the test capacity manually.
- Request JSON uses unique files beside the result report, not command-line JSON
  quoting. Each file is removed in finally. Tokens are never written to request/report
  files or printed; CLI stderr is intentionally omitted from errors.

## Results

The final table contains `Id`, `Name`, `Status`, `Evidence`, and `Detail`, followed by
job IDs and a `UAT SUMMARY` line. Status is PASS, FAIL, WARN, or SKIPPED. The process exits
**1 for any FAIL**, including cleanup or persistence failures; otherwise **0**. WARN is
not full proof of acceptance: review propagation/visibility warnings before sign-off.

`-ResultPath` accepts a directory (unique timestamp/run-ID filename) or a `.json` file
(overwritten). Default is `$env:TEMP`, falling back to the current directory if unset.
The JSON contains scenario objects (`Id`, `Name`, `Passed`, `Status`, `Evidence`, `Detail`),
job IDs/status/sanitized streams, original state, counts, timestamps, and exit code.
`Passed` is true only for PASS; use `Status` to distinguish warnings and skipped tests.
Reports contain resource/identity/job GUIDs, not access tokens. Treat reports as
operational metadata. Read them with:

```powershell
$report = Get-Content -LiteralPath '.\uat-results\acceptance.json' -Raw | ConvertFrom-Json
$report.Results | Format-Table Id,Name,Status,Evidence,Detail -Wrap
$report.Jobs | Select-Object Scenario,JobId,Status
```

## Known limits / offline verification

- This harness intentionally does not run during development. Syntax parsing and
  `Get-Help .\tests\uat\Invoke-AutoPauseUat.ps1 -Full` require no Azure access.
- For unit tests, dot-source with the four mandatory parameters (use generated dummy
  GUIDs and a syntactically valid dummy capacity ID), then mock `Invoke-AzProcess`,
  `Invoke-UatRest`, `Invoke-FabricRead`, `Get-UatNow`, and `Wait-UatPoll` as appropriate.
  Dot-sourcing defines helpers only; it does not invoke the harness. No Az modules
  or additional test tools are required by the live harness.
- `Invoke-AutoPauseUat.Tests.ps1` uses **Pester 5** with mocked process/API, clock, and
  filesystem seams; it never submits live jobs. Run it with `Invoke-Pester -Path
  .\tests\uat\Invoke-AutoPauseUat.Tests.ps1 -Output Detailed` after importing Pester 5
  (not the older system Pester). It covers schedule rounding/correlation/cleanup,
  fail-closed restoration, expected failures, stream decoding, settled-output polling,
  idempotency and offline `-WhatIf`.
- ARM 429/5xx responses use bounded exponential retries. Job and capacity polling
  waits are bounded; resume/pause state waits default to 15 minutes. Process/network
  delays can extend wall-clock duration beyond the nominal polling timeout.
- Activity Log can lag; S04 retries for up to five minutes, then WARNs instead of
  failing an otherwise successful pause.
- S11 takes approximately `ScheduleLeadMinutes`, **plus** Automation queueing/job time.
  Minimum lead is five minutes; the requested UTC start is rounded **up** to a whole
  minute, so rounding can add almost a minute. The schedule PUT includes its top-level
  `name`, `frequency=OneTime`, and `timeZone=UTC`. The effective `startTime` is taken
  from the PUT response (or a GET fallback). Runtime is service-dependent.
- Job creation is assumed to accept the documented Automation `2024-10-23` PUT body
  with string-valued parameters; GET job streams/detail are assumed to return
  `jobStreamId`, `streamType`, and `streamText`/`summary`, with `properties.value`
  decoded as a fallback (text, JSON string/object, or array). Failed-input errors may
  appear in job `exception` rather than streams; both are checked. Stream publication
  is given up to 60 seconds after completion, waiting for a **Summary line**, not a
  result-table word, or the exact expected error text for S06/S07.
- The jobs API does not document a schedule-link ID on Job. S11 correlates new jobs
  by startTime at/after the **effective** schedule time minus a 60-second tolerance
  (creationTime for queued jobs), and runbook. Capacity ID, enforcing flag, and identity
  must match when returned; missing parameters are treated conservatively as possible
  matches, never as proof it is safe to restore. More than one match fails as ambiguous.
  Avoid all concurrent invocations; schedule attribution is not immutable provenance.
- S10 is conservative read-only inspection of listed subscription/inherited roles,
  not a deny-assignment, PIM, group, cross-subscription, or effective-access simulation.
  All listed action wildcards fail even when a NotActions exclusion would narrow
  them; management-group-only grants cannot establish the target ancestry here.
- Existing nightly schedules may be broader than this test scope; the harness does
  not alter them. Run outside their window. Resource Graph indexing may lag recent
  tag/resource changes; a missing/wrong runbook summary fails the relevant test.
- S09 uses the signed-in caller, not the runbook identity. Display-name matching may
  be unavailable if the Fabric display name differs from the ARM capacity name and
  ARM exposes no Fabric GUID. Fabric state labels/propagation may differ from ARM.

API references:
[Jobs](https://learn.microsoft.com/rest/api/automation/job/create?view=rest-automation-2024-10-23),
[streams](https://learn.microsoft.com/rest/api/automation/job-stream/get?view=rest-automation-2024-10-23),
[job schedules](https://learn.microsoft.com/rest/api/automation/job-schedule/create?view=rest-automation-2024-10-23),
[schedules](https://learn.microsoft.com/rest/api/automation/schedule/create-or-update?view=rest-automation-2024-10-23).
