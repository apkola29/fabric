# Fabric Capacity Auto-Pause

Pauses Microsoft Fabric capacities (F SKUs) every night at a fixed, time-based schedule, so a capacity that was left running does not keep billing. An Azure Automation runbook (PowerShell 7.4) runs on a schedule, signs in with a user-assigned managed identity (no secrets), discovers capacities with Azure Resource Graph, and calls the Azure Resource Manager `suspend` action on each one that is `Active`. Everything happens on the Azure control plane: no Fabric tenant settings, capacity-admin role, or workspace access is required. It never resumes a capacity, and it ships in dry-run mode so you can see what it would do before it pauses anything.

> Status: verified end to end against one live deployment: dry run, enforcement, idempotency, the exclusion tag, invalid input, a human resume followed by an automation re-pause, and a run fired by the Automation schedule itself. Still open: daylight-saving recurrence across a clock change, the failed-job email alert actually arriving, and narrowly scoped identities (resource-group or single-capacity scope) discovering capacities through Resource Graph. See [Live-verified behaviour](docs/DESIGN.md#live-verified-behaviour) and [Open items](docs/DESIGN.md#open-items).

## Who this is for

Not every organisation needs a large always-on capacity, and not every organisation can commit to a reservation. Fabric F SKUs are billed pay-as-you-go (a reservation is optional) and a paused capacity stops compute billing, so pausing on a schedule is a practical cost control for:

- test, dev, demo, and training environments
- variable or spiky workloads
- workloads that need capacity only periodically: nightly loads, weekly or month-end refreshes, scheduled reports
- small teams and proofs of concept
- partner and consulting demo tenants

It is **not** the target for a steady 24x7 production load, where a reservation usually wins.

Illustrative savings. The formula is `paused hours per day x CU x hourly rate per CU`. Assumptions: about $0.18 per CU-hour pay-as-you-go (illustrative; check current pricing for your region), a 30-day month, and the paused hours shown. Storage, which keeps billing while paused, and any usage billed at the moment of pausing are ignored.

| Scenario | SKU (CU) | Paused per day | Approximate saving per 30 days |
|---|---|---|---|
| Developer sandbox | F2 (2) | 12 h | 2 x $0.18 x 12 x 30 = about $130 |
| Training lab | F4 (4) | 16 h | 4 x $0.18 x 16 x 30 = about $346 |
| Test environment | F8 (8) | 12 h | 8 x $0.18 x 12 x 30 = about $518 |
| Capacity needed only for periodic loads | F64 (64) | 20 h | 64 x $0.18 x 20 x 30 = about $6,912 |

The solution pauses; people (or your own process) resume, so real paused hours depend on when the capacity is resumed. See [docs/PRICING.md](docs/PRICING.md) for detailed, sourced numbers.

## What gets paused

> [!WARNING]
> **What gets paused.** By default, **every** `Microsoft.Fabric/capacities` resource that the managed identity can read (whatever its role assignment covers: the **whole subscription** by default) that is `Active` and **not** tagged `autopause=skip` is paused at the scheduled time, every day. The default deployment is a dry run, so nothing is paused until you deploy with `-EnableEnforcement`. Decide the scope first, using the table below.

Targeting:

| Goal | What you set | RBAC step |
|---|---|---|
| Whole subscription (default) | Nothing | None: the role is assigned at the deployment subscription |
| Several subscriptions | `-AdditionalAssignableScopes /subscriptions/<other-subscription-id>` and `-ScopeSubscriptionIds "<subscription-id>,<other-subscription-id>"` | Assign the role in each other subscription |
| A management group | `-AdditionalAssignableScopes /providers/Microsoft.Management/managementGroups/<management-group-id>` and `-ScopeManagementGroupId <management-group-id>` (mutually exclusive with `-ScopeSubscriptionIds`) | Assign the role at the management group |
| One resource group | `-ScopeResourceGroupName <resource-group>` | Recommended: `-SkipSubscriptionRoleAssignment`, then assign the role at the resource group |
| **One specific capacity** | `-ScopeCapacityName <capacity-name>` or `-ScopeCapacityResourceId <capacity-resource-id>` | Deploy with `-SkipSubscriptionRoleAssignment` and assign the role at the capacity, so the identity cannot see any other capacity |
| Keep a capacity running | Tag it `autopause=skip` ([exclusion tag](#exclusion-tag)) | None |

The `-Scope*` parameters only narrow what the runbook looks at; the role assignment is the real boundary. Commands and details are in [Scope recipes](#scope-recipes). To change the time of day, see [Changing the schedule](#changing-the-schedule).

## How it works

```
 Automation schedules (time zone aware)       Azure Automation account  aa-<prefix>
 ---------------------------------------      -------------------------------------------
 autopause-nightly   00:00 <time zone>  --->  runbook Invoke-FabricCapacityAutoPause
 autopause-backstop  +60 min (optional) --->  (PowerShell-74 runtime environment, Az 12.3.0)
                                                        |
                                    signs in as user-assigned managed identity  id-<prefix>
                                                        |
                                                        v
                                    Azure Resource Graph: type microsoft.fabric/capacities
                                    (only what the identity's RBAC roles can read)
                                                        |
                                                        v   for each capacity
                                    ARM GET (state + tags, api-version 2023-11-01)
                                                        |
                          Active and not excluded by tag?  -- no --> log and move on
                                                        | yes
                                                        v
                                    ARM POST .../suspend  ->  poll until Paused
                                    (DryRun = true: log "WouldPause" and stop here)
```

| Behaviour | Detail |
|---|---|
| Time-based only | It pauses at the scheduled time, every night, whatever else is happening. The only per-capacity opt-out is the exclusion tag |
| Safe by default | `DryRun` is `true` unless you deploy with `-EnableEnforcement`. The runbook parses it strictly (`true`/`false`/`1`/`0`/`yes`/`no`); any other value fails the job, so a typo can never pause anything |
| Scope = RBAC | The identity can only see and pause capacities its Azure role assignments cover; runbook parameters narrow further |
| Idempotent | Paused capacities are skipped, and one that is already pausing is only verified to finish (no second suspend); a second run an hour later is a harmless backstop |
| Never resumes | The custom role does not include `resume/action` |
| Bounded run time | One shared deadline (`PauseTimeoutMinutes`, 1 to 150) polls every pending capacity round-robin, so the job stays under the 3-hour Automation sandbox limit |
| Fails loudly | The job fails if any capacity cannot be read or paused, if a requested `CapacityName` / `CapacityResourceId` matches nothing, or if the Az commands are missing, so a job-failed alert fires. With no filter and nothing visible it only warns |
| Retries | Throttling (429) and 5xx responses are retried up to 4 attempts; a `Retry-After` header is honoured (capped at 120 s) |

State handling (full table in [docs/DESIGN.md](docs/DESIGN.md#state-and-decision-table)):

| Capacity state | Action |
|---|---|
| `Active` | Pause (unless tagged to skip) |
| `Paused`, `Suspended` | Skip (`Skipped`) |
| `Pausing`, `Suspending` | Await: no second suspend; verified to finish (`PauseInProgress`, then `Paused`) |
| `Resuming`, `Scaling`, `Updating`, `Preparing`, `Provisioning` | Defer to the next run (the backstop) |
| `Failed`, `Deleting`, anything else | Warn, no action |

What pausing does (per the [Fabric documentation](https://learn.microsoft.com/fabric/enterprise/pause-resume)): it cancels running work, bills any remaining smoothed usage and overage immediately, and does not stop OneLake storage charges. Only F SKU capacities that exist as `Microsoft.Fabric/capacities` Azure resources are handled (not Trial or P SKUs). Fabric's own API and portal report a paused capacity as `Inactive`; in Azure Resource Manager it is `Paused`.

## Credentials and identity - what the nightly job runs as

The job runs as a **user-assigned managed identity** (`id-<prefix>`) attached to the Automation account.

- It has **no password, key, certificate, or secret** anywhere: not in the runbook, the Automation account, the schedules, or this repository. Azure issues short-lived tokens to the Automation sandbox on request.
- The runbook signs in with `Connect-AzAccount -Identity -AccountId <identity client ID>`. The client ID reaches the runbook as the parameter `UserAssignedIdentityClientId`, set by the schedule link. It is an identifier, not a secret.
- Its only permissions come from the custom role **Fabric Capacity AutoPause Operator**: `Microsoft.Fabric/capacities/read` and `Microsoft.Fabric/capacities/suspend/action`. No resume, no delete, and no write unless you opt in with `-IncludeWritePermission`.
- The role is assigned at **subscription scope by default**. You can narrow it with `-SkipSubscriptionRoleAssignment` plus a narrower assignment (see [Scope recipes](#scope-recipes)).
- **Rotation: there is nothing to rotate.** No credential exists to expire or leak.

| Who / what | Credential | Used for | Permissions |
|---|---|---|---|
| The person running `deploy.ps1` | Their own `az login`, one-time | Create the resource group, identity, Automation account, role definition and role assignment; upload and publish the runbook | Owner, or Contributor plus User Access Administrator (to create the role and assignment) |
| The managed identity `id-<prefix>` | None stored; short-lived tokens issued by Azure | The nightly runbook, every run: Resource Graph discovery, read, suspend | Custom role `read` + `suspend/action` at the assigned scope. Nothing else |
| The Automation platform | None | Starts the schedule and runs the runbook in its sandbox | No Azure permissions of its own; it only hands the identity to the job |
| The person who resumes capacities | Their own account | Resume a capacity in the morning (or whenever) | Whatever they already have. The automation can never resume |

See the identity in the portal under Automation account `aa-<prefix>` > Identity > User assigned, or under Microsoft Entra ID > Managed identities (Enterprise applications, filtered to Managed Identities).

Audit what it can do and what it did:

```powershell
az role assignment list --assignee <principal-id> --all -o table
```

The Azure Activity Log records each pause as `Microsoft.Fabric/capacities/suspend/action` with the managed identity's principal ID as the caller.

## Prerequisites

| Requirement | Notes |
|---|---|
| Azure CLI | Signed in with `az login` |
| Bicep | `az bicep install` (or standalone) |
| PowerShell 7+ | Runs `scripts\deploy.ps1` |
| Azure permissions to deploy | At the target subscription: Owner, or Contributor plus User Access Administrator (or Role Based Access Control Administrator). The deployment creates a custom role definition and role assignment |
| An existing Fabric capacity | One or more F SKU capacities as Azure resources. Not needed to deploy, only to see results |
| Pester 5+ | Only to run the unit tests |

## Quick start

> [!WARNING]
> **What gets paused.** By default, **every** `Microsoft.Fabric/capacities` resource that the managed identity can read (whatever its role assignment covers: the **whole subscription** by default) that is `Active` and **not** tagged `autopause=skip` is paused at the scheduled time, every day, once you enable enforcement. To limit it to one resource group or one capacity, use the [targeting table](#what-gets-paused) **before** you enable enforcement.

1. Sign in and deploy in **dry-run** mode (nothing is paused):

   ```powershell
   az login
   .\scripts\deploy.ps1 -SubscriptionId <subscription-id> -Location <region> -TimeZone America/Chicago -ScheduleTime 00:00 -AlertEmails ops@example.com
   ```

   Add `-WhatIf` to preview: it runs the read-only checks (Azure CLI, Bicep, sign-in, subscription, schedule inputs), prints the computed schedule start times, and deploys nothing. The script also sets the Azure CLI active subscription to `-SubscriptionId`.

2. [Run a manual test job](#run-a-manual-test-job) and check that the output lists the capacities you expect with `WouldPause` or `Skipped`.

3. Once the dry-run output is right, redeploy with enforcement on:

   ```powershell
   .\scripts\deploy.ps1 -SubscriptionId <subscription-id> -Location <region> -TimeZone America/Chicago -ScheduleTime 00:00 -AlertEmails ops@example.com -EnableEnforcement
   ```

   The script prints a warning when `-EnableEnforcement` is used without `-IncludeWritePermission`. That is expected: the role grants only `read` and `suspend/action`, and live testing showed pausing works with just those two. `-IncludeWritePermission` is an optional fallback if a pause is ever denied; note that `write` also allows scaling a capacity and changing its capacity admins.

   Re-running the script is safe: the Bicep deployment is incremental, and the schedule-to-runbook links (which cannot be updated) are deleted and recreated, each with a fresh ID. Keep the same `-Location` and `-NamePrefix` on re-runs, because the subscription-level deployment (`deploy-<prefix>`) is tied to one location.

   Upgrading from an older deployment: the custom role definition's ID now includes `-NamePrefix`. Redeploying over an older deployment creates a second role definition with the same display name, which Azure rejects. Delete the old role assignment and role definition first (see [Uninstall](#uninstall)), or deploy with a new `-CustomRoleName`.

By default the nightly schedule runs at `-ScheduleTime` in `-TimeZone`, and a backstop schedule runs `-BackstopOffsetMinutes` (60) later. Automation can start a scheduled job up to 30 minutes late, which is why the backstop exists. If someone resumes a capacity between the two runs, the backstop pauses it again: set `-BackstopOffsetMinutes 0` to disable it, or tag the capacity (see [exclusion tag](#exclusion-tag)). To change the time, see [Changing the schedule](#changing-the-schedule).

The script prints the SHA-256 of the runbook file it uploads. Compare it with `Get-FileHash -Algorithm SHA256 runbooks\Invoke-FabricCapacityAutoPause.ps1` to confirm what was deployed.

### Run a manual test job

Manual jobs do not inherit the schedule's parameters, so pass the identity's client ID yourself (the runbook otherwise tries a system-assigned identity, which this deployment does not create), plus any scope parameters you set at deploy time. `deploy.ps1` prints the client ID in its summary; you can also read it with:

```powershell
$clientId = az identity show --resource-group <resource-group> --name id-<prefix> --query clientId --output tsv
```

Portal: Automation account `aa-<prefix>` > Runbooks > `Invoke-FabricCapacityAutoPause` > Start. Set `UserAssignedIdentityClientId` to the client ID and `DryRun` to `true` (or `false` to enforce for this run only), then open the job and read the Output tab. `DryRun` is a string; anything other than `true`/`false`/`1`/`0`/`yes`/`no` fails the job.

PowerShell with the Az.Automation module (not yet verified):

```powershell
$aa = @{ ResourceGroupName = '<resource-group>'; AutomationAccountName = 'aa-<prefix>' }
$job = Start-AzAutomationRunbook @aa -Name Invoke-FabricCapacityAutoPause -Parameters @{ UserAssignedIdentityClientId = $clientId; DryRun = 'true' }
do { Start-Sleep 10; $job = Get-AzAutomationJob @aa -Id $job.JobId } until ($job.Status -in 'Completed', 'Failed', 'Stopped', 'Suspended')
$job.Status
Get-AzAutomationJobOutput @aa -Id $job.JobId -Stream Any | ForEach-Object Summary
```

`Summary` can be truncated for long output; the portal Output tab shows everything. If the job ends `Failed`, the reason is in the job's `properties.exception`, not in the output streams (see [Troubleshooting](#troubleshooting)).

Illustrative output (names are placeholders):

```
Fabric capacity auto-pause: DRY RUN (no changes will be made)
Discovered 2 Fabric capacities.

Name      ResourceGroup  Sku PriorState Action   Result     Detail
----      -------------  --- ---------- ------   ------     ------
capdev01  rg-fabric-dev  F8  Active     Pause    WouldPause Capacity is Active.
capprod01 rg-fabric-prod F64 Active     Excluded Excluded   Tag 'autopause' excludes this capacity.

Summary: Excluded=1, WouldPause=1
```

`Result` values: `WouldPause`, `Paused`, `Skipped`, `Excluded`, `Deferred`, `Warning`, `Denied`, `Error`. `PauseRequested` and `PauseInProgress` are interim: they become `Paused` once the runbook has verified the pause, or `Error` if it did not finish before the deadline. The job fails (status `Failed`) when any row is `Denied` or `Error`.

## Changing the schedule

1. **The normal way: re-run `deploy.ps1`.** Use the same parameters as before, plus the new time zone, time, and backstop:

   ```powershell
   .\scripts\deploy.ps1 -SubscriptionId <subscription-id> -Location <region> -AlertEmails ops@example.com -TimeZone <IANA-time-zone-id> -ScheduleTime HH:mm -BackstopOffsetMinutes N -EnableEnforcement
   ```

   `-TimeZone` is an IANA ID such as `America/Chicago`. `-ScheduleTime` is a 24-hour wall-clock time in that zone. `-BackstopOffsetMinutes 0` means no backstop. The script is idempotent. Keep `-EnableEnforcement` if enforcement is on: omitting it returns the schedules to dry-run.

2. **What you get.** Shutdown is **daily** at `-ScheduleTime` in the chosen time zone, and the schedule is daylight-saving aware (the first real clock change is still an [open item](docs/DESIGN.md#open-items)). The backstop runs `-BackstopOffsetMinutes` later and does nothing if the capacity is already paused.

3. **Test recipe.** To test now, pick a time about 15 minutes ahead (the first start must be at least about 10 minutes in the future, otherwise the first run is tomorrow) and deploy with your usual parameters plus a test time (`-BackstopOffsetMinutes 0` just avoids a second run an hour later):

   ```powershell
   .\scripts\deploy.ps1 -SubscriptionId <subscription-id> -Location <region> -ScheduleTime 14:15 -EnableEnforcement -BackstopOffsetMinutes 0
   ```

   Make sure the target capacity is `Active`, wait for the time, then check Automation account > Jobs and the capacity state. This pauses every capacity in scope, so narrow the scope or tag the others first (see [What gets paused](#what-gets-paused)). Then **re-run `deploy.ps1` with the real time** (for example `-ScheduleTime 00:00`) and your usual `-BackstopOffsetMinutes`.

   > [!WARNING]
   > A test time left in place pauses capacities at that time every day. Always re-run `deploy.ps1` with the real schedule when the test is done.

4. **Portal edits.** Changing a schedule in the Automation account > Schedules blade works, but the next `deploy.ps1` run overwrites it.

5. **Turn it off temporarily.** Disable the schedules (Automation account > Schedules), or tag a capacity `autopause=skip` so only that capacity is left alone. Re-enable the schedules afterwards. To see the next runs:

   ```powershell
   az rest --method get --url https://management.azure.com/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Automation/automationAccounts/aa-<prefix>/schedules?api-version=2024-10-23 --query "value[].{name:name,tz:properties.timeZone,next:properties.nextRun,enabled:properties.isEnabled}" -o table
   ```

## Scope recipes

The identity's Azure role assignments are the real scope; see the [targeting table](#what-gets-paused). By default the deployment assigns the custom role to the identity at the deployment subscription (`infra\modules\rbac.bicep`). The `-Scope*` parameters narrow what the runbook looks at; they do not change that assignment. To narrow RBAC itself, deploy with `-SkipSubscriptionRoleAssignment` (see [Restrict RBAC below the subscription](#restrict-rbac-below-the-subscription)). Use the narrowest scope that works.

The custom role can only be assigned at scopes listed in its assignable scopes, which is why `-AdditionalAssignableScopes` is needed for anything outside the deployment subscription. It adds assignable scopes only; it does not create assignments there. Assignment at a management group and in other subscriptions has not yet been verified live (see [Open items](docs/DESIGN.md#open-items)).

Look up the managed identity's principal ID (also the `identityPrincipalId` deployment output), then create the extra assignment:

```powershell
$principalId = az identity show --resource-group <resource-group> --name id-<prefix> --query principalId --output tsv

# Another subscription
az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
  --role "Fabric Capacity AutoPause Operator" --scope /subscriptions/<other-subscription-id>

# A management group
az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
  --role "Fabric Capacity AutoPause Operator" --scope /providers/Microsoft.Management/managementGroups/<management-group-id>

# A resource group
az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
  --role "Fabric Capacity AutoPause Operator" --scope /subscriptions/<subscription-id>/resourceGroups/<resource-group>

# A single capacity
az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
  --role "Fabric Capacity AutoPause Operator" `
  --scope /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>
```

If you used `-CustomRoleName`, use that name for `--role`. The identity and the target must be in the same Microsoft Entra tenant.

### Restrict RBAC below the subscription

For a resource group or a single capacity, deploy with `-SkipSubscriptionRoleAssignment`. That creates the custom role definition but **no role assignment**, so **nothing can be paused until you assign the role** at the narrower scope (resource group or capacity commands above; `deploy.ps1` also prints them in its summary):

```powershell
.\scripts\deploy.ps1 -SubscriptionId <subscription-id> -Location <region> -ScopeCapacityName <capacity-name> -SkipSubscriptionRoleAssignment
```

Then assign the role at the capacity (or resource group), and check what the identity holds:

```powershell
az role assignment list --assignee $principalId --all -o table
```

- Without the switch, a deployment assigns the role at the whole subscription again.
- With the switch, an assignment created by an earlier run is **not** removed. If you are narrowing an existing deployment, delete the old subscription-scope assignment yourself, otherwise the identity can still pause every capacity in the subscription even though the runbook parameters filter them out:

  ```powershell
  az role assignment delete --assignee $principalId --role "Fabric Capacity AutoPause Operator" --scope /subscriptions/<subscription-id>
  ```

- Not yet verified live: whether an identity with only a resource-group or single-capacity assignment discovers capacities through Resource Graph. If discovery returns nothing, see [Troubleshooting](#troubleshooting).

### Exclusion tag

The runbook reads the tag on every run, so no redeploy is needed. Tag name and value matching is case-insensitive:

```powershell
az tag update --resource-id <capacity-resource-id> --operations Merge --tags autopause=skip
```

A tagged capacity is reported as `Excluded` and never paused. Change the tag name or value with `-ExcludeTagName` / `-ExcludeTagValue`; an empty `-ExcludeTagValue` excludes on tag presence alone. An empty `-ExcludeTagName` is rejected (it would silently disable every opt-out). The exclusion tag was verified live.

## deploy.ps1 parameters

| Parameter | Default | Description |
|---|---|---|
| `-SubscriptionId` | required | Subscription to deploy into |
| `-Location` | required | Azure region name for the resource group and resources, for example `eastus2`. Keep it the same on re-runs |
| `-ResourceGroupName` | `rg-fabric-autopause` | Resource group created for the solution |
| `-NamePrefix` | `fabricautopause` | Used in resource names: `id-<prefix>`, `aa-<prefix>`. 3 to 47 letters, digits or hyphens, starting with a letter. Also part of the custom role definition's ID (see the upgrade note in [Quick start](#quick-start)) |
| `-TimeZone` | `UTC` | IANA time zone ID for the schedules, for example `America/Chicago` |
| `-ScheduleTime` | `00:00` | Nightly run time, 24-hour `HH:mm`, in `-TimeZone` |
| `-BackstopOffsetMinutes` | `60` | Minutes after the nightly wall-clock time for a second, idempotent run (0 to 1439). `0` disables it |
| `-AlertEmails` | none | One or more email addresses (array) for the failed-job alert. Omit to skip the action group and alert |
| `-ScopeSubscriptionIds` | none | Runbook `SubscriptionIds`: comma-separated subscription IDs (GUIDs) to search. Quote the value when listing several. Mutually exclusive with `-ScopeManagementGroupId` |
| `-ScopeManagementGroupId` | none | Runbook `ManagementGroupId`: management group ID (not display name) to search |
| `-ScopeResourceGroupName` | none | Runbook `ResourceGroupName`: only this resource group |
| `-ScopeCapacityName` | none | Runbook `CapacityName`: only this capacity |
| `-ScopeCapacityResourceId` | none | Runbook `CapacityResourceId`: only this capacity (full resource ID) |
| `-ExcludeTagName` | `autopause` | Tag name that excludes a capacity. Must not be empty or whitespace |
| `-ExcludeTagValue` | `skip` | Tag value that excludes a capacity. An empty string excludes on tag presence alone |
| `-EnableEnforcement` | off (dry-run) | Switch. Sets the schedules' `DryRun` to `false` so capacities are actually paused. Omitting it on a later run returns the schedules to dry-run |
| `-IncludeWritePermission` | off | Switch. Adds `Microsoft.Fabric/capacities/write` to the custom role. Live testing showed suspend works without it, so use it only as a fallback if a pause is denied. Besides suspending, `write` also allows scaling a capacity and changing its capacity admins. Resume is never granted |
| `-SkipSubscriptionRoleAssignment` | off | Switch. Creates the custom role definition but **no role assignment**, so you can assign it at a narrower scope (a resource group or one capacity). Nothing can be paused until you assign the role. An assignment from an earlier run without the switch is not removed. Without the switch the role is assigned at the whole subscription. See [Restrict RBAC below the subscription](#restrict-rbac-below-the-subscription) |
| `-CustomRoleName` | `Fabric Capacity AutoPause Operator` | Name of the custom role definition. Role names must be unique per tenant |
| `-AdditionalAssignableScopes` | none | Extra scopes (subscription, resource group, management group) the custom role can be assigned at. Creates no assignments |
| `-AzPackageVersion` | `12.3.0` | Version (`x.y.z`) of the Az PowerShell package installed in the Automation runtime environment |
| `-Tags` | none | Hashtable of tags for the resource group and resources, for example `@{ owner = 'platform-team' }` |
| `-WhatIf` | | Standard PowerShell preview: read-only checks run, nothing is deployed |

The script prints the SHA-256 of the runbook it uploads. The scripts and Bicep templates are authoritative: if this table and `scripts\deploy.ps1` disagree, trust the script.

## Runbook parameters

Set on the schedules by `deploy.ps1` (as strings, which is how Automation stores schedule parameter values), or supplied when starting a job manually.

| Parameter | Default | Description |
|---|---|---|
| `SubscriptionIds` | all readable | Comma-separated subscription IDs to search. Not combinable with `ManagementGroupId` |
| `ManagementGroupId` | none | Management group ID (not display name) to search |
| `ResourceGroupName` | none | Only capacities in this resource group |
| `CapacityName` | none | Only the capacity with this name. If it matches nothing, the job fails |
| `CapacityResourceId` | none | Only the capacity with this resource ID. If it matches nothing, the job fails |
| `ExcludeTagName` | `autopause` | Capacities with this tag are never paused. Must not be empty |
| `ExcludeTagValue` | `skip` | Tag value that excludes. Empty excludes on tag presence alone |
| `UserAssignedIdentityClientId` | none | Client ID of the user-assigned identity to sign in with. Omit for a system-assigned identity |
| `DryRun` | `true` | A **string**: `true`/`false`/`1`/`0`/`yes`/`no`. When true, log what would happen and pause nothing. Any other value fails the job, so a typo can never pause |
| `PauseTimeoutMinutes` | `15` | 1 to 150. ONE shared deadline, started after the suspend requests, for all pending capacities to reach `Paused`; they are polled round-robin, so the job stays under the 3-hour sandbox limit. A capacity still pending at the deadline is reported as an error |
| `PollSeconds` | `15` | 5 to 300. Seconds between state checks while waiting |

Values interpolated into the Resource Graph query (names, IDs) are validated against strict patterns before use: subscription IDs must be GUIDs, a capacity name 3 to 63 letters or digits starting with a letter, and a capacity resource ID must have the full `/subscriptions/.../providers/Microsoft.Fabric/capacities/<name>` form. Anything else fails the job.

## Beyond pausing: scale and restart

The same runbook pattern can do more than pause. With the same schedules, identity, and discovery, a runbook can:

- **scale** a capacity (change its F SKU) on a schedule, for example down overnight and up in the morning
- **resume** ("start") a capacity before work begins
- **restart** a capacity (suspend, then resume)

> [!IMPORTANT]
> These are **not enabled**, and the default role does **not** allow them. Scaling needs `Microsoft.Fabric/capacities/write`; resuming (and so restarting) needs `Microsoft.Fabric/capacities/resume/action`. Add a permission only deliberately: broader permissions mean a bigger blast radius, and a resume restarts billing.

The runbook contains **commented example sections** (a block headed `EXTENDING`) that show where each operation would go. [docs/EXTENDING.md](docs/EXTENDING.md) has the how-to, and [docs/API-REFERENCE.md](docs/API-REFERENCE.md) lists the Azure and Fabric calls involved.

## Run the tests

The unit tests cover the decision logic, query building, retry behaviour, and schedule helpers. They stub the Az cmdlets, so no Azure sign-in is needed. Requires Pester 5 or later.

```powershell
Install-Module Pester -MinimumVersion 5.0.0 -Scope CurrentUser    # if needed
Invoke-Pester -Path .\tests -Output Detailed
```

Run from the project root. Run a single file with `Invoke-Pester -Path .\tests\common.Tests.ps1`.

## Repository layout

```
fabric-capacity-autopause/
  README.md
  docs/
    DESIGN.md                  architecture, identities, RBAC, algorithm, failure modes, live-verified behaviour, open items
    PRICING.md                 cost model with sourced pricing
    API-REFERENCE.md           Azure and Fabric API calls used
    EXTENDING.md               how to add scale, resume, or restart
  infra/
    README.md                  Bicep parameter reference and offline build/lint
    main.bicep                 subscription-scope entry point (resource group + modules)
    main.parameters.example.json
    modules/
      automation.bicep         identity, Automation account, runtime environment, runbook shell, schedules, alert
      rbac.bicep               custom role definition and role assignment
  runbooks/
    Invoke-FabricCapacityAutoPause.ps1
  scripts/
    deploy.ps1                 deploys infra, uploads and publishes the runbook
    common.ps1                 helpers for deploy.ps1 (schedule start times)
  tests/
    Invoke-FabricCapacityAutoPause.Tests.ps1
    common.Tests.ps1
    deploy.Tests.ps1
    uat/
      README.md                optional live acceptance harness
      Invoke-AutoPauseUat.ps1
      Invoke-AutoPauseUat.Tests.ps1
```

## Troubleshooting

When a job ends `Failed`, the reason is in the Automation job's `properties.exception`, **not** in the output streams (the Output tab can look normal or empty). Open the failed job in Automation account > Jobs, or read it directly:

```powershell
az rest --method get --url "https://management.azure.com/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Automation/automationAccounts/aa-<prefix>/jobs/<job-id>?api-version=2024-10-23" --query properties.exception -o tsv
```

| Symptom | Likely cause | What to do |
|---|---|---|
| Output shows `Denied` / `AuthorizationFailed` on read; job `Failed` | Role assignment missing, at the wrong scope, or not yet propagated | `az role assignment list --assignee <principal-id> --all`; confirm the custom role is assigned at or above the capacity; wait a few minutes and re-run |
| `Denied` on pause (read works) | Role lacks `Microsoft.Fabric/capacities/suspend/action` | Check the role definition. If suspend still fails with `read` + `suspend/action`, redeploy with `-IncludeWritePermission` (live testing needed only `read` + `suspend/action`) |
| `Resource Graph query failed (403)` | Identity cannot read the subscription or management group named in `SubscriptionIds` / `ManagementGroupId` | Assign the role at that scope; check the scope IDs |
| Job `Failed`: `The requested capacity was not found, or the identity cannot read it.` | A `CapacityName` / `CapacityResourceId` matched nothing: wrong name or ID, other subscription, or the role assignment does not cover it. This fails on purpose so a typo cannot look like success | Check the spelling, the subscription, and `az role assignment list --assignee <principal-id> --all` |
| `Discovered 0 Fabric capacities.` and a warning (job succeeds) | No filter was given and the identity sees nothing: no read access, capacity in a subscription not covered, a Trial or P SKU, or a very new capacity not yet in Resource Graph | Check role assignments and `-Scope*` values; for a narrowly scoped identity try `-ScopeSubscriptionIds` (not yet verified live) |
| Job `Failed`: `Required command '...' is not available` (for example `Connect-AzAccount`) | The runtime environment has no Az package. Without `defaultPackages { Az: '12.3.0' }` the Az cmdlets are missing, and a job would otherwise still end `Completed` with only non-terminating errors, which is why the runbook fails fast | Redeploy (the template declares the package; see `-AzPackageVersion`) and check the runtime environment's packages |
| Job `Failed`: `Invalid DryRun '...': expected true or false.` | The value is not `true`/`false`/`1`/`0`/`yes`/`no` | Fix the value; this fails on purpose so a typo can never pause |
| Job `Failed`: `Invalid ... '...'` or `ExcludeTagName must not be empty` | A scope parameter failed strict validation, or the exclusion tag name is empty | Correct the value (see [Runbook parameters](#runbook-parameters)) |
| Job fails at sign-in (`Connect-AzAccount`) | Manual job started without `UserAssignedIdentityClientId`, identity not attached to the Automation account, wrong client ID, or an identity with only resource-level scope (not yet verified live) | Pass the identity's client ID; check the identity on the Automation account and the client ID the schedule passes |
| Schedule did not fire | Schedule disabled or expired, start time in the past at creation, time zone mismatch, or start delayed (Automation can start a job up to 30 minutes late) | Check Automation account > Schedules and the runbook's linked schedules, and the Jobs list; the backstop run covers short delays |
| Capacity shows `Deferred` | It was `Resuming`, `Scaling`, `Updating`, `Preparing`, or `Provisioning` at run time | The backstop run retries; or re-run manually |
| `Did not reach Paused within N min` | Pause is slow or stuck, or the shared deadline passed before every pending capacity finished | Check the capacity state and Activity Log; raise `PauseTimeoutMinutes` (up to 150); the next run sees `Pausing` or `Paused` and verifies or skips it. A real pause took about 2 to 2.5 minutes in live testing |
| Capacity paused again after someone resumed it after midnight | Backstop run | Set `-BackstopOffsetMinutes 0`, or tag the capacity `autopause=skip` |
| Users cannot reach Fabric content in the morning | Capacities are never auto-resumed | Resume the capacity in the Azure portal (Microsoft Fabric > capacity > Resume) |
| Deployment fails creating the role definition or assignment | Deployer lacks `Microsoft.Authorization/roleDefinitions/write` or `roleAssignments/write` | Use Owner, or Contributor plus User Access Administrator / Role Based Access Control Administrator |
| Deployment fails because a role definition with the same name exists | Redeploying over an older deployment: the role definition's ID now includes `-NamePrefix`, so a second definition with the same display name is created and Azure rejects it | Delete the old role assignment and role definition first (see [Uninstall](#uninstall)), or deploy with a new `-CustomRoleName` |
| `A jobSchedule with same id already exists` | Automation reserves a deleted job-schedule link's ID for a while | `deploy.ps1` uses a fresh ID for every link, so re-run it; if you link by hand, use a new GUID each time |

## Security notes

- No secrets: the runbook authenticates as a managed identity. Nothing sensitive is stored in the Automation account or this repository.
- Least privilege: the custom role grants `read` and `suspend/action` on Fabric capacities. It cannot resume or delete a capacity, and it cannot scale one unless you opt into `-IncludeWritePermission` (`write` also allows scaling and changing capacity admins).
- The Automation account has local authentication disabled and is managed through Azure RBAC and the managed identity only.
- Anyone who can edit the runbook or start jobs on the Automation account can use the identity to pause capacities in its scope. Restrict access to the resource group and keep the role assignment as narrow as possible.
- Pausing cancels running work. Announce the schedule to capacity users and use the exclusion tag for anything that must run overnight.
- Always start in dry-run and review the output before enabling enforcement.
- The deployer needs rights to create role definitions and assignments; the runtime identity does not.

## Uninstall

1. Note the identity's principal ID and list its assignments (they outlive the identity if you delete the resource group first):

   ```powershell
   $principalId = az identity show --resource-group <resource-group> --name id-<prefix> --query principalId --output tsv
   az role assignment list --assignee $principalId --all --output table
   ```

2. Delete each role assignment listed (default subscription assignment and any you added):

   ```powershell
   az role assignment delete --assignee $principalId --role "Fabric Capacity AutoPause Operator" --scope <scope-from-the-list>
   ```

3. Delete the resource group (removes the identity, Automation account, schedules, action group, and alert):

   ```powershell
   az group delete --name <resource-group>
   ```

4. Delete the custom role definition once it has no assignments:

   ```powershell
   az role definition delete --name "Fabric Capacity AutoPause Operator"
   ```

Capacities that were paused stay paused; resume them if needed.

## Documentation

| Document | Contents |
|---|---|
| [docs/DESIGN.md](docs/DESIGN.md) | Requirements, architecture, identities, authorization, algorithm, scheduling, failure modes, live-verified behaviour, open items |
| [docs/PRICING.md](docs/PRICING.md) | Detailed, sourced cost model: what pausing saves and what it does not |
| [docs/API-REFERENCE.md](docs/API-REFERENCE.md) | The Azure Resource Manager, Resource Graph, and Fabric calls the runbook makes |
| [docs/EXTENDING.md](docs/EXTENDING.md) | How to add scale, resume, or restart (not enabled by default) |
| [infra/README.md](infra/README.md) | Bicep parameters, role definition and assignment, offline build and lint |
| [tests/uat/README.md](tests/uat/README.md) | The live acceptance harness. Optional: it pauses and resumes the one test capacity you point it at, so never aim it at production |

## Disclaimer

These scripts are provided **as-is** with no warranty of any kind. They are intended for learning and experimentation purposes. Use at your own risk. Pausing a capacity cancels running work. See the parent repository [LICENSE](../LICENSE).
