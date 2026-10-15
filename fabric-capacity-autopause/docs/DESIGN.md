# Design: Fabric Capacity Auto-Pause

Status: implemented and verified end to end against one live deployment (dry run, enforcement, idempotency, the exclusion tag, invalid input, a human resume followed by an automation re-pause, and a run fired by the Automation schedule itself). The behaviour confirmed live is in [Live-verified behaviour](#live-verified-behaviour); what is still unconfirmed is in [Open items](#open-items).

Back to the [README](../README.md). Related: [PRICING.md](PRICING.md), [API-REFERENCE.md](API-REFERENCE.md), [EXTENDING.md](EXTENDING.md), [../infra/README.md](../infra/README.md).

## Requirements and non-goals

| Id | Requirement |
|---|---|
| R1 | Pause Fabric capacities (F SKUs) at a configurable time every night, in a configurable time zone, with daylight saving handled |
| R2 | No secrets stored anywhere; authenticate with a managed identity |
| R3 | Least privilege: able to read and pause capacities, not resume or delete, and not scale unless `write` is deliberately added |
| R4 | Scope is explicit and narrowable: whole subscription, other subscriptions, a management group, a resource group, or a single capacity |
| R5 | Safe by default: dry-run until enforcement is enabled |
| R6 | Idempotent: running twice, or against an already paused capacity, is a no-op |
| R7 | Failures are visible: a failed job raises an alert |
| R8 | Reusable: nothing hard-coded to a tenant, subscription, or capacity |
| R9 | Time-based: pauses at the scheduled time; the only per-capacity opt-out is a tag |

Non-goals:

| Non-goal | Why |
|---|---|
| Auto-resume | Resuming restarts billing; users resume on demand. A scheduled resume is an opt-in extension that needs an extra permission (see [EXTENDING.md](EXTENDING.md)) |
| Trial, P SKU, or non-Azure capacities | Only `Microsoft.Fabric/capacities` resources can be paused through ARM |
| Fabric tenant-level configuration | The solution is Azure control plane only |
| Multi-tenant operation | One identity belongs to one Microsoft Entra tenant |

## Architecture

```
                     Deployer (az login)
                           |  scripts\deploy.ps1
                           v
        +------------------ subscription ----------------------------------+
        |  custom role definition   "Fabric Capacity AutoPause Operator"   |
        |  role assignment(s): identity -> role -> scope                   |
        |                                                                  |
        |  resource group rg-fabric-autopause                              |
        |    user-assigned managed identity   id-<prefix>                  |
        |    Automation account               aa-<prefix>   (Basic)        |
        |      runtime environment            PowerShell-74                |
        |      runbook                        Invoke-FabricCapacityAutoPause
        |      schedule  autopause-nightly    daily at ScheduleTime/TimeZone
        |      schedule  autopause-backstop   nightly + BackstopOffsetMinutes
        |    action group + metric alert      failed Automation jobs       |
        +------------------------------------------------------------------+

 Runtime (each scheduled job)
   Automation sandbox --(identity)--> Azure Resource Graph  (discover)
                       --(identity)--> ARM GET  capacity     (authoritative state, tags)
                       --(identity)--> ARM POST capacity/suspend, then GET until Paused
```

Resources created by `infra\main.bicep` (subscription scope) and its modules:

| Resource | Name | Notes |
|---|---|---|
| Resource group | `rg-fabric-autopause` (parameter) | Holds everything except the role definition and the subscription-scope assignment |
| User-assigned managed identity | `id-<prefix>` | The runbook's identity; attached to the Automation account |
| Automation account | `aa-<prefix>` | Basic SKU; local authentication disabled |
| Runtime environment | `PowerShell-74` | PowerShell 7.4. Declares `defaultPackages { Az: '<version>' }` (default `12.3.0`, `-AzPackageVersion`); without it the Az cmdlets are missing |
| Runbook | `Invoke-FabricCapacityAutoPause` | `runbookType` `PowerShell` bound to the runtime environment. Bicep creates an empty shell; `deploy.ps1` uploads and publishes the content and prints its SHA-256 |
| Schedules | `autopause-nightly`, `autopause-backstop` | Daily, with `timeZone` set. The backstop exists only when its start time is supplied |
| Job schedule links | nightly and backstop to the runbook | Created by `deploy.ps1`, not Bicep. Links cannot be updated, so every run deletes and recreates them, each with a **fresh** ID (Automation reserves a deleted link's ID, so re-using one fails with `A jobSchedule with same id already exists`). They carry the runbook parameters as strings: scope, exclusion tag, `UserAssignedIdentityClientId`, and `DryRun` (`true` unless `-EnableEnforcement`) |
| Action group `ag-<prefix>` and metric alert `alert-<prefix>-job-failure` | Only when `-AlertEmails` is given | Alert on unsuccessful jobs |
| Custom role definition and assignment | `Fabric Capacity AutoPause Operator` | The definition is created at the deployment subscription. The assignment to the identity is created at the subscription unless `-SkipSubscriptionRoleAssignment` is used; see [Authorization model](#authorization-model) |

`main.bicep` takes absolute ISO 8601 start times (`scheduleStartTime`, `backstopStartTime`) rather than a time of day. `deploy.ps1` computes them from `-ScheduleTime` and `-TimeZone` with `scripts\common.ps1`. Deploying the Bicep directly means supplying those values and doing the runbook upload and job schedule linking yourself; see [../infra/README.md](../infra/README.md).

## Identities

| Who / what | Type | Credential | Used for | Needs |
|---|---|---|---|---|
| Deployer | Entra user or service principal running `deploy.ps1` | Their own `az login`, one-time | Create the resource group and resources, the role definition and assignments; upload and publish the runbook | Owner, or Contributor plus User Access Administrator (or Role Based Access Control Administrator) at the subscription, and the same ability at any extra scope where it assigns the role |
| Managed identity `id-<prefix>` | User-assigned | None stored; Azure issues short-lived tokens to the sandbox on request | Every nightly run: sign in from the runbook, query Resource Graph, read and suspend capacities | The custom role at the chosen scope(s). Nothing else |
| Automation platform | Azure Automation service | None | Starts jobs on schedule, runs the runbook in the cloud sandbox, attaches the identity | No Azure permissions of its own; it only hands the identity to the job |
| Person who resumes capacities | A human, in the portal or CLI | Their own account | Resume a capacity in the morning (or whenever) | Whatever they already have. The automation can never resume |
| Action group | Email receivers (addresses, not identities) | None | Sends the failed-job alert | Nothing |

The deployer is only needed at deployment time. The managed identity never creates role assignments.

### What the nightly job runs as

- The job runs as the **user-assigned managed identity** `id-<prefix>` attached to the Automation account. **No password, key, certificate, or secret exists anywhere**: not in the runbook, the Automation account, the schedules, or the repository.
- The runbook signs in with `Connect-AzAccount -Identity -AccountId <identity client ID>`. The client ID reaches the runbook as the parameter `UserAssignedIdentityClientId`, set on the schedule link by `deploy.ps1`. It is an identifier, not a secret.
- The identity's only permissions are the custom role `Fabric Capacity AutoPause Operator`: `Microsoft.Fabric/capacities/read` and `Microsoft.Fabric/capacities/suspend/action`. No resume, no delete, and `write` only if you opt in. The role is assigned at subscription scope by default and can be narrowed (see [Scope ladder](#scope-ladder)).
- To see the identity: Automation account `aa-<prefix>` > Identity > User assigned, or Microsoft Entra ID > Managed identities. To audit it: `az role assignment list --assignee <principal-id> --all -o table`; the Activity Log records each pause as `Microsoft.Fabric/capacities/suspend/action` with the identity's principal ID as the caller.
- **Rotation: there is nothing to rotate.**

## Authorization model

Custom role `Fabric Capacity AutoPause Operator` (name is a parameter):

| Action | Purpose | Included |
|---|---|---|
| `Microsoft.Fabric/capacities/read` | Resource Graph visibility, ARM GET of state and tags | Always |
| `Microsoft.Fabric/capacities/suspend/action` | Pause | Always |
| `Microsoft.Fabric/capacities/write` | Listed in the Fabric pause documentation. Live testing showed suspend works **without** it. It also allows scaling a capacity and changing its capacity admins | Only with `-IncludeWritePermission`, kept as an optional fallback if a pause is ever denied |
| `Microsoft.Fabric/capacities/resume/action` | Resume | Deliberately omitted |

The Fabric documentation lists read, write, suspend, and resume as the actions for pausing and resuming, and recommends a custom role over built-in privileged roles. This solution applies that advice and drops resume (and, by default, write) so a compromised or misused identity cannot start billing or rescale a capacity. See [Pause and resume your Fabric capacity](https://learn.microsoft.com/fabric/enterprise/pause-resume).

The role definition's name is `guid(subscription().id, namePrefix, customRoleName)`, so two deployments in one subscription with different settings cannot overwrite each other's definition. **Upgrade note:** older deployments named the definition without `namePrefix`. Redeploying over one creates a second definition with the same display name, which Azure rejects. Delete the old role assignment and role definition first, or deploy with a new `-CustomRoleName`.

Scaling, resuming, or restarting a capacity are possible extensions that are **not enabled**: scale needs `Microsoft.Fabric/capacities/write`, resume needs `Microsoft.Fabric/capacities/resume/action`, and either is a deliberate widening of the blast radius. See [EXTENDING.md](EXTENDING.md).

### Scope ladder

The identity can only discover and pause capacities that its role assignments allow it to read. **By default that is every capacity in the deployment subscription.** Assign at the narrowest scope that covers the targets. `infra\modules\rbac.bicep` creates the subscription assignment unless `assignRoleAtSubscription` is false (`deploy.ps1 -SkipSubscriptionRoleAssignment`); every other scope is a manual `az role assignment create` (see the [README](../README.md#scope-recipes)).

| Scope | Assignment | Blast radius | Notes |
|---|---|---|---|
| Single capacity | Role at the capacity resource (manual), with `-SkipSubscriptionRoleAssignment` | One capacity | Use with `-ScopeCapacityName` or `-ScopeCapacityResourceId`. Without the switch the identity can still pause everything in the subscription. Discovery for a resource-scoped identity is an open item |
| Resource group | Role at the resource group (manual), with `-SkipSubscriptionRoleAssignment` | Capacities in that group | `-ScopeResourceGroupName`. Discovery for a resource-group-scoped identity is an open item |
| Subscription | Role at the subscription (default, created by the deployment) | All capacities in the subscription | |
| Several subscriptions | One manual assignment per subscription | Capacities in each | The role must list each scope in its assignable scopes (`-AdditionalAssignableScopes`) |
| Management group | Manual assignment at the management group | All capacities below it | Assignable scope at a management group is an open item |

A custom role can only be assigned at scopes listed in its assignable scopes. The definition is created at the deployment subscription with that subscription as its assignable scope; `-AdditionalAssignableScopes` adds the others (it creates no assignments). With `-SkipSubscriptionRoleAssignment` the deployment creates the definition but no assignment, so narrowed RBAC survives a redeploy; nothing can be paused until you assign the role yourself. An assignment left by an earlier run without the switch is not removed and must be deleted by hand.

### Targeting and narrowing

Narrowing is layered. Each layer can only remove capacities; none can add what RBAC does not allow. With no narrowing at all, **every `Active` capacity the identity can read that is not tagged to skip is paused**.

| Order | Layer | Mechanism | Effect |
|---|---|---|---|
| 1 | Azure RBAC | Role assignments on the identity | Defines what Resource Graph returns and what ARM will allow |
| 2 | Resource Graph scope | `SubscriptionIds` or `ManagementGroupId` (mutually exclusive) | Restricts which subscriptions or management group is queried. Omitted: everything the identity can read |
| 3 | Query filters | `ResourceGroupName`, `CapacityName`, `CapacityResourceId` | Added as `where` clauses; all inputs are validated against strict patterns before being placed in the query. A `CapacityName` or `CapacityResourceId` that matches nothing fails the job |
| 4 | Tag exclusion | `ExcludeTagName` / `ExcludeTagValue` (default `autopause` / `skip`) | Evaluated on the tags read from ARM at run time, before the state check. Case-insensitive. Empty value means tag presence alone excludes. An empty tag name is rejected |
| 5 | State | Capacity `properties.state` | Only `Active` capacities are paused |

## Runbook algorithm

`runbooks\Invoke-FabricCapacityAutoPause.ps1`. Everything runs through `Invoke-AzRestMethod`, so the code needs no Az module beyond Az.Accounts (not even Az.ResourceGraph); the runtime environment still installs the Az package so those cmdlets exist.

1. Validate input before any call. `DryRun` is a **string** (default `'true'`) parsed strictly: `true`/`false`/`1`/`0`/`yes`/`no`; anything else fails the job, so a typo can never cause a pause. `PauseTimeoutMinutes` must be 1 to 150 and `PollSeconds` 5 to 300. An empty `ExcludeTagName` is rejected, because it would silently disable every opt-out.
2. Log the mode: `DRY RUN` or `ENFORCING`.
3. Fail fast if `Disable-AzContextAutosave`, `Connect-AzAccount`, or `Invoke-AzRestMethod` is missing. A missing command is only a non-terminating error, which would let the job end `Completed` having done nothing.
4. `Connect-AzAccount -Identity` (with `-AccountId <client id>` when `UserAssignedIdentityClientId` is set), process-scoped context.
5. Build the Resource Graph request from the scope parameters; fail if both `SubscriptionIds` and `ManagementGroupId` are given. Every interpolated value is validated strictly (subscription IDs as GUIDs, resource group and management group names, capacity names, and capacity resource IDs against anchored patterns). Query `resources | where type =~ 'microsoft.fabric/capacities'` plus filters, page through `$skipToken` (`api-version` 2022-10-01).
6. If nothing is discovered: when a `CapacityName` or `CapacityResourceId` was requested, **fail** the job with `The requested capacity was not found, or the identity cannot read it.`; with no such filter, only warn.
7. For each result, `GET` the capacity from ARM (`api-version` 2023-11-01). The Resource Graph state is only used for discovery; the ARM read is authoritative. A failed read (401/403 `Denied`, other `Error`) is recorded and the loop continues.
8. Decide with the pure function `Get-AutoPauseDecision` (state + tags), see the table below.
9. For `Pause`: in dry-run record `WouldPause`; otherwise `POST .../suspend`. HTTP 200 or 202 records `PauseRequested`; 401/403 records `Denied`; anything else records `Error`. For `Await` (already `Pausing`/`Suspending`) no second suspend is sent; the row is `PauseInProgress`.
10. After all suspend requests are issued, poll **all** pending capacities round-robin against **one shared deadline** (`PauseTimeoutMinutes` from that moment, every `PollSeconds`) until each is `Paused` or `Suspended`. Success records `Paused`; any capacity still pending at the deadline records `Error` with its last seen state. One shared deadline keeps the whole job under the 3-hour sandbox limit, which would otherwise end the job as `Stopped` instead of `Failed`.
11. Print a table (name, resource group, SKU, prior state, action, result, detail) and a one-line summary of result counts.
12. If any row is `Error` or `Denied`, throw so the job ends `Failed`. Other rows are not failures.

ARM calls retry on HTTP 429 and 5xx, up to 4 attempts, with exponential backoff (5, 10, 20 seconds, capped at 60). Other 4xx responses are not retried.

### State and decision table

| State | Action | Result | Rationale |
|---|---|---|---|
| Tag excludes (any state) | `Excluded` | `Excluded` | Operator opted out; checked before state |
| `Active` | `Pause` | `WouldPause` (dry-run), then `PauseRequested`, then `Paused` | The target state |
| `Paused`, `Suspended` | `Skip` | `Skipped` | Already off |
| `Pausing`, `Suspending` | `Await` | `PauseInProgress`, then `Paused` | Already on its way: no second suspend is sent, but the pause is verified to finish within the shared deadline |
| `Resuming`, `Scaling`, `Updating`, `Preparing`, `Provisioning` | `Defer` | `Deferred` | Transitional; the backstop run retries |
| `Failed`, `Deleting`, unknown, empty | `Warn` | `Warning` | No action; visible in output. Does not fail the job |

The runbook never calls `resume`. Fabric's own API and portal report a paused capacity as `Inactive`; Azure Resource Manager reports it as `Paused`, which is what the runbook reads.

### Result values

| Result | Meaning | Fails the job |
|---|---|---|
| `Paused` | Suspend accepted (or already in progress) and state reached `Paused` | No |
| `WouldPause` | Dry-run: would have paused | No |
| `PauseRequested`, `PauseInProgress` | Interim: the suspend was accepted, or one was already running. Replaced by `Paused` or `Error` once verified | Only if it ends as `Error` |
| `Skipped` | Already paused | No |
| `Excluded` | Matched the exclusion tag | No |
| `Deferred` | Transitional state | No |
| `Warning` | `Failed`, `Deleting`, or unknown state | No |
| `Denied` | HTTP 401/403 reading or suspending | Yes |
| `Error` | Other failure, or the pause did not complete before the shared deadline | Yes |

ARM calls retry on HTTP 429 and 5xx, up to 4 attempts, with exponential backoff (5, 10, 20 seconds, capped at 60). A `Retry-After` header is honoured when it is longer than the backoff, capped at 120 seconds. Other 4xx responses are not retried.

## Scheduling

| Schedule | When | Purpose |
|---|---|---|
| `autopause-nightly` | Daily at `-ScheduleTime` in `-TimeZone` | Main pause |
| `autopause-backstop` | Nightly wall-clock time plus `-BackstopOffsetMinutes` (default 60; 0 disables), computed in the time zone so it keeps the intended local time across daylight-saving changes | Covers a late or failed first run and capacities that were transitioning |

| Fact | Detail |
|---|---|
| Time zones | Automation schedules accept IANA time zone IDs (for example `America/Chicago`, verified live) and adjust for daylight saving. Behaviour across a real clock change has not yet been observed (see [Open items](#open-items)) |
| First start time | `scripts\common.ps1` computes the next occurrence of the wall-clock time in the zone, handling the daylight-saving gap, and enforces a minimum lead time of 10 minutes, so a start less than about 10 minutes away moves to the next day (tested in `tests\common.Tests.ps1`) |
| Start SLA | A scheduled job can start up to 30 minutes late |
| Minimum interval | 1 hour, which is why the backstop is an offset and not a short retry |
| Job limit | 3-hour fair-share limit per job; a run normally takes minutes. The shared pause deadline (at most 150 minutes) keeps a run under it |
| Backstop side effect | It also re-pauses a capacity someone resumed between the two runs. Set the offset to 0 or tag the capacity to avoid this |
| Changing the schedule | Re-run `deploy.ps1` with a new `-TimeZone`, `-ScheduleTime`, and `-BackstopOffsetMinutes` (keep `-EnableEnforcement` if enforcement is on). Portal edits work but are overwritten by the next deploy. A test time left in place pauses capacities every day. See [Changing the schedule](../README.md#changing-the-schedule) |

Alternatives considered:

| Option | Why not |
|---|---|
| GitHub Actions cron | Cron schedules are UTC only, so daylight saving shifts the local time |
| Azure Functions timer trigger | `WEBSITE_TIME_ZONE` is not supported on Linux Consumption or Flex Consumption |
| Logic Apps recurrence | Works with an explicit time zone, but looping over capacities and unit-testing the logic is harder |
| Azure Automation (chosen) | Native time zone and DST-aware schedules, managed identity, a runbook that can be unit tested, near-zero cost |

Runtime notes: PowerShell 7.4 is available in Automation only through a runtime environment, which must declare `defaultPackages { Az: '<version>' }` (default `12.3.0`). Without it the Az cmdlets are missing and a job still ends `Completed` with only non-terminating errors, which is why the runbook fails fast. Source control integration does not support 7.4, so `deploy.ps1` uploads and publishes the runbook itself.

## Failure modes

The reason for a `Failed` job is in the Automation job's `properties.exception`, not in the output streams.

| Failure | Behaviour | Visible as |
|---|---|---|
| Invalid `DryRun` (not `true`/`false`/`1`/`0`/`yes`/`no`), empty `ExcludeTagName`, or an invalid identifier | The job fails before anything is paused | Job `Failed`, alert |
| Az commands missing from the runtime environment | `Required command '...' is not available`; nothing is paused | Job `Failed`, alert |
| Managed identity sign-in fails | `Connect-AzAccount` throws; nothing is paused | Job `Failed`, alert |
| Resource Graph returns an error | After retries on 429/5xx, throws `Resource Graph query failed`; nothing is paused | Job `Failed`, alert |
| Resource Graph returns no rows, no capacity requested | Job succeeds with `Discovered 0` and a warning | Output only; no alert (see future work) |
| A requested `CapacityName` / `CapacityResourceId` matches nothing | Job fails: `The requested capacity was not found, or the identity cannot read it.` | Job `Failed`, alert |
| ARM read denied for one capacity | Row `Denied`; other capacities still processed | Job `Failed` at the end |
| Suspend denied | Row `Denied`; others still processed | Job `Failed` at the end |
| Capacity changes state between read and suspend (non-2xx) | Row `Error` | Job `Failed`; the backstop retries |
| A pause does not complete before the shared deadline (`PauseTimeoutMinutes`) | Each capacity still pending gets row `Error` with its last state | Job `Failed`; the next run verifies or skips `Pausing` or `Paused` |
| Throttling or transient 5xx | Retried up to 4 attempts, honouring `Retry-After` (capped at 120 s) | Warning lines in output |
| First run starts late (up to 30 minutes) | Backstop run covers it | |
| Capacity in `Failed` or `Deleting` | `Warning`, no action | Output only |
| Someone resumes after the nightly run | Left running, unless the backstop runs afterwards or the next night | |
| Job exceeds the 3-hour fair-share limit | Job is interrupted; the work is idempotent, so a later run completes it. The shared deadline makes this unlikely | Job status |

## Observability

| Signal | Source |
|---|---|
| Per-run result table and summary | Automation job output stream |
| Reason for a `Failed` job | The Automation job's `properties.exception` (not the output streams) |
| Job failure alert | Metric alert (`alert-<prefix>-job-failure`) on the Automation account `TotalJob` metric, dimension `Status` in `Failed`, `Stopped`, `Suspended`. Evaluated every 15 minutes over a 1-hour window, severity 2, sent to the action group `ag-<prefix>`. Created only when `-AlertEmails` is given. Whether the email arrives is an [open item](#open-items) |
| Audit of pauses | Azure Activity Log: `Microsoft.Fabric/capacities/suspend/action` on each capacity, with the managed identity's principal ID as caller (verified live) |
| Job history | Automation account > Jobs |
| Next scheduled runs | `az rest` on the account's `schedules` collection (see [Changing the schedule](../README.md#changing-the-schedule)) |

Optional extras (not deployed): Automation diagnostic settings to Log Analytics, an Activity Log alert on suspend and resume, a budget on the resource group.

## Cost model

Automation and alerting cost is effectively zero for this workload: the free tier includes 500 job-minutes per month per subscription, and a run takes minutes. Two runs a night is about 60 jobs a month; if many capacities each wait up to `PauseTimeoutMinutes`, check your job-minute consumption against the free tier.

Savings:

```
daily saving = paused hours per day x CU of the SKU x price per CU-hour
```

Illustrative example (not a quote): retail pay-as-you-go was about $0.18 per CU-hour in a US region at the time of writing; check your region. An F8 has 8 CU.

```
F8, paused 12 hours a day:  8 CU x $0.18 x 12 h = $17.28 per day = about $518 per 30 days
```

| SKU | CU | Cost per hour at the example rate |
|---|---|---|
| F2 | 2 | $0.36 |
| F8 | 8 | $1.44 |
| F64 | 64 | $11.52 |

Caveats:

| Caveat | Detail |
|---|---|
| Paused hours depend on resume time | The solution pauses; users resume. Paused time is nightly pause time to the next manual resume |
| Remaining smoothed usage is billed at pause | Pausing bills the remaining smoothed usage and overage immediately, so a busy capacity saves less than the formula suggests |
| Storage is unaffected | OneLake storage keeps billing while paused |
| Billing model | The formula applies to pay-as-you-go billing; check how a reservation or other agreement treats paused hours |

See [Monitor a paused capacity](https://learn.microsoft.com/fabric/enterprise/monitor-paused-capacity). Detailed, sourced pricing numbers are in [PRICING.md](PRICING.md); all rates here are illustrative, so check current pricing for your region.

## Live-verified behaviour

Verified end to end against one live deployment: dry run, enforcement, idempotency, the exclusion tag, invalid input, and a human resume followed by an automation re-pause.

| Area | Verified fact |
|---|---|
| Runbook type | `runbookType` `PowerShell` bound to the `PowerShell-74` runtime environment works |
| Az packages | The runtime environment must declare `defaultPackages { Az: '12.3.0' }`. Without it the Az cmdlets are missing and the job still ends `Completed` with only non-terminating errors, which is why the runbook fails fast |
| Schedules | A schedule's `timeZone` accepts IANA IDs such as `America/Chicago` |
| Schedule parameters | Schedule parameter values are stored as strings, which is why `DryRun` is a string parsed strictly |
| Job-schedule links | Each link needs a fresh ID every time: Automation reserves a deleted link's ID (`A jobSchedule with same id already exists`). `deploy.ps1` creates a fresh ID per link |
| Sign-in | `Connect-AzAccount -Identity -AccountId <client ID>` works with the user-assigned identity |
| Discovery | Resource Graph discovers capacities for an identity that holds only the custom role at subscription scope |
| Permissions | Suspend works with only `Microsoft.Fabric/capacities/read` and `Microsoft.Fabric/capacities/suspend/action`. `write` was not needed in testing; `-IncludeWritePermission` stays as an optional fallback |
| Audit | The Activity Log records `Microsoft.Fabric/capacities/suspend/action` with the managed identity's principal ID as the caller |
| Timing | A real pause takes about 2 to 2.5 minutes end to end |
| States | Fabric's own API reports a paused capacity as `Inactive`; Azure Resource Manager reports it as `Paused` |
| Idempotency | Re-running on an already paused capacity is a no-op (`Skipped`) |
| Exclusion tag | A capacity tagged `autopause=skip` is `Excluded` and left running |
| Invalid input | An invalid `DryRun` value fails the job |
| Resume and re-pause | A human resume followed by an automation re-pause both work |
| Timer-fired run | A job started by the Automation schedule itself (job ID prefixed `SCH_`) started about 30 seconds after the scheduled time, ran as the managed identity with the schedule's parameters (`DryRun=false`), paused the capacity and completed in under 2 minutes |
| Changing the schedule | Re-running `deploy.ps1` with a different `-ScheduleTime` updates the existing schedules in both directions (tested: midnight to a time 14 minutes ahead, then back to midnight) and relinks them |
| Local auth disabled | `disableLocalAuth: true` on the Automation account does not interfere with runbook upload, publish, job start or schedule-triggered jobs |

## Open items

Not yet confirmed live. Each has a fallback or a way to check.

| # | Item | Why it matters / fallback |
|---|---|---|
| 1 | Resource Graph visibility for a narrowly scoped identity (resource-group or single-capacity role assignment only). Subscription-scope visibility is verified | If Resource Graph returns nothing without subscription-level read, pass `-ScopeSubscriptionIds`; if still empty, the runbook needs a direct ARM path for a known `CapacityResourceId` (not implemented) |
| 2 | `Connect-AzAccount -Identity` when the identity has only resource-level scope | It may fail to find a subscription for the context. Possible mitigation: `-SkipContextPopulation` (not implemented). The runbook uses absolute ARM paths, so a default subscription context is not otherwise needed |
| 3 | Daylight-saving recurrence: the schedules keep their local wall-clock time across a real clock change | Check Automation account > Schedules and the next run time after a change; re-run `deploy.ps1` if a schedule drifted |
| 4 | The failed-job alert fires and the email arrives | Test with a deliberately failing job |
| 5 | Custom role assignable at a management group and at other subscriptions via `-AdditionalAssignableScopes` | Needed for the multi-subscription and management group recipes |
| 6 | Role assignment propagation delay. A newly created assignment worked about 10 minutes after creation, but the minimum delay was not measured | Run a manual job after deployment before relying on the schedule |
| 7 | The `Start-AzAutomationRunbook` / `Get-AzAutomationJob` snippet in the README works against a runtime-environment runbook | Use the portal Start button, or the REST call shown in [API-REFERENCE.md](API-REFERENCE.md) |

## Future work

| Item | Notes |
|---|---|
| Fail or alert on zero discovered capacities and on `Warning` rows | Closes the silent-misconfiguration gap |
| Scheduled resume, scale, or restart | Explicitly opt-in and needs extra permissions; see [EXTENDING.md](EXTENDING.md) |
| Direct ARM fallback for a known `CapacityResourceId` | Avoids dependence on Resource Graph for resource-scoped identities |
| Time-boxed exclusion (for example a tag with an expiry date) | Hold a capacity open for a night without editing the schedule |
| Log Analytics diagnostics and Activity Log alert on suspend and resume | Longer history and notifications on every pause |
| CI job running the Pester tests | Tests exist; no pipeline is included |
