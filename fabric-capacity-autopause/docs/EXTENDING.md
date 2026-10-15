# Extending the capacity runbook: resume, scale, and restart

> **Extension pattern, not tested in the default release.** These examples are comments, not enabled functionality. The default runbook remains suspend-only. Local edits do not update or publish the deployed runbook. Do not upload, publish, or run the deployment script against the existing deployment while developing this extension.

## 1. Choose the operation and its guardrails

| Operation | Change | Required starting state | Completion condition | Default release |
| --- | --- | --- | --- | --- |
| `Suspend` | Existing POST `/suspend` | Active; an in-progress pause is awaited | Paused or Suspended | Supported |
| `Resume` | Add POST `/resume` | Paused or Suspended; skip if already Active | Active | Commented example only |
| `Scale` | Add PATCH of the capacity's top-level `sku` | Active, current and target F SKUs; skip if already at target | Active **and** `sku.name` equals `TargetSku` | Commented example only |
| `Restart` | Compose suspend, wait, resume, wait; there is no `/restart` call | Active | Paused/Suspended, then Active | Commented example only |

| Safety rule | Why it matters |
| --- | --- |
| Preserve `autopause=skip`, or your configured exclusion tag, for **every** operation | Resume and scale must not bypass an operator's opt-out. An excluded capacity is never mutated. Check fresh ARM tags before dispatch and again before restart's resume leg. An empty configured exclusion value means exclude on tag presence. |
| Preserve strict `DryRun` parsing and default `'true'` | Scheduled parameters arrive as strings. A typo must fail closed, not authorize a mutation. |
| Scale only an Active F SKU | Scaling can interrupt running work. The sample rejects non-F current/target SKUs and a non-Fabric tier. F-shaped names still require regional SKU availability and quota validation by the operator. |
| Treat resume as a billing decision | Resume restarts billing; restart includes downtime and a new billing-active period. |
| Budget for the three-hour Automation sandbox limit | Use a shared deadline across targets and both restart legs; leave headroom for discovery, retries, and network calls. Smaller batches are safer than a full timeout per capacity. |
| Prevent overlapping schedules and manual jobs | A scale, pause, and resume race is not an orchestration strategy. Existing backstop schedules also need review. |
| Fail on unverified completion | HTTP 200/202 is acceptance, not proof of the desired final state. If restart resumes unsuccessfully, the capacity can remain Paused; inspect and recover deliberately. |

The default custom role deliberately omits write and resume permissions. Wider permissions and new schedules are explicit operator decisions, not changes activated by this document.

## 2. Adapt a separate development copy

1. Start with a separate local copy or branch and an isolated test runbook/identity. Leave the existing published copy unchanged.
2. Open `runbooks\Invoke-FabricCapacityAutoPause.ps1`. Find the exact end-of-file heading:

   ```powershell
   # ===== EXTENDING (commented examples - NOT ENABLED) =====
   ```

3. Read the numbered fragments there. Remove **one leading `#`** only from the specific code being transferred. Do not uncomment the whole tail: it follows the entry-point guard, so helpers placed there would be defined too late for a normal run.
4. Move the complete `Invoke-CapacityResume` and `Invoke-CapacityScale` examples above `Invoke-FabricCapacityAutoPause`. Splice the decision and switch fragments into the named functions.
5. Apply this key interface diff, preserving the original parameter commas and the existing string-to-boolean boundary:

   ```diff
   # In both the top-level param block and Invoke-FabricCapacityAutoPause's param block:
   + [ValidateSet('Suspend','Resume','Scale','Restart')] [string] $Operation = 'Suspend',
   + [string] $TargetSku,

   # In the entry-point invocation:
   + -Operation $Operation -TargetSku $TargetSku

   # In Get-AutoPauseDecision's parameters:
   + [ValidateSet('Suspend','Resume','Scale','Restart')] [string] $Operation = 'Suspend',
   + [string] $CurrentSku,
   + [string] $TargetSku

   # In its per-capacity call, using the existing authoritative ARM GET:
   + -Operation $Operation -CurrentSku ([string]$get.Body.sku.name) -TargetSku $TargetSku
   ```

6. Insert the operation-aware decision fragment **after** the original exclusion check and **before** its state switch. Leave the Suspend path intact. Add the new switch arms without deleting existing `Excluded`, `Skip`, `Defer`, `Await`, or error handling.
7. Add the early Scale parameter validation and the shared `$operationDeadline` shown in the block. Keep the non-empty exclusion-name guard, result rows, pause queue, final failure aggregation, and managed-identity authentication. Update banner/log wording to identify the chosen operation.

| Existing seam | Extension responsibility |
| --- | --- |
| `Invoke-Arm` | Reuse its status/result shape and transient retry behavior; do not duplicate authentication or introduce secrets. |
| `Get-CapacityPowerState` | Verify resume reaches Active, not merely that POST was accepted. |
| `Wait-CapacitiesPaused` | Verify the first restart leg before issuing resume; use the remaining shared time budget. |
| `Get-AutoPauseDecision` | Exclusion first for all operations; state eligibility, idempotent skips, and deferral for unsafe transitions. |
| `Write-Log` | Record intent, accepted requests, verified completion, and DryRun decisions. |
| Existing per-capacity catch and final aggregation | A failed read, permission denial, or polling timeout must fail the job rather than report false success. |

The Scale body was checked against [Microsoft Learn: Fabric Capacities - Update, API 2023-11-01](https://learn.microsoft.com/rest/api/microsoftfabric/fabric-capacities/update?view=rest-microsoftfabric-2023-11-01). It is a PATCH to the capacity resource, not an action subpath:

```json
{"sku":{"name":"<TargetSku>","tier":"Fabric"}}
```

`sku` is top-level, **not** under `properties`. Do not send tags or administration members for a SKU-only change. The commented helper generates this body with `ConvertTo-Json`, accepts only 200/202, and polls until both state and SKU match. The [Resume REST reference](https://learn.microsoft.com/rest/api/microsoftfabric/fabric-capacities/resume?view=rest-microsoftfabric-2023-11-01) likewise specifies POST and 200/202.

## 3. Add permissions deliberately

All operations need `Microsoft.Fabric/capacities/read`. The table lists the additional capacity actions; these are managed-identity permissions, not the operator's permissions to administer Automation or RBAC.

| Use case | Operation/parameters | Capacity actions beyond read | Default custom role grants them? |
| --- | --- | --- | --- |
| Pause nightly | `Operation=Suspend` | `Microsoft.Fabric/capacities/suspend/action` | Yes |
| Resume before business hours | `Operation=Resume` | `Microsoft.Fabric/capacities/resume/action` | No |
| Scale down at night or weekends | `Operation=Scale TargetSku=F2` | `Microsoft.Fabric/capacities/write` | No |
| Scale up for month-end | `Operation=Scale TargetSku=F16` | `Microsoft.Fabric/capacities/write` | No |
| Restart an Active capacity with stuck work | `Operation=Restart` | `Microsoft.Fabric/capacities/suspend/action` and `Microsoft.Fabric/capacities/resume/action` | Suspend only; resume is absent |

Restart is not a repair for arbitrary provisioning, scaling, or other transitional states; the sample defers those states. Confirm an outage window and diagnose the incident first.

### Checked repository controls

`infra\modules\rbac.bicep` exposes the following parameters:

| Parameter | Default/behavior | Extension consequence |
| --- | --- | --- |
| `principalId` | Required managed-identity principal/object ID | Assignment identity; do not substitute its client ID. |
| `namePrefix` | Required; participates in deterministic role-definition identity | Preserve the deployed value when maintaining that definition. |
| `customRoleName` | Existing default role display name | Preserve the intended role identity/name, or create a deliberately separate extension role. |
| `includeWritePermission` | `false`; adds only `Microsoft.Fabric/capacities/write` when true | Scale opt-in; also allows changing capacity admins. |
| `assignRoleAtSubscription` | `true` | Use `false` for a dedicated extension deployment and assign at a capacity or resource group. |
| `additionalAssignableScopes` | `[]`; extends assignable scopes only | Does **not** create assignments. |

There is **no resume-permission parameter**. `scripts\deploy.ps1 -IncludeWritePermission` maps to `includeWritePermission`; `-SkipSubscriptionRoleAssignment` maps to `assignRoleAtSubscription=false`. The script also uploads/publishes the runbook, so **do not run it merely to adjust RBAC on the existing published deployment**. Use the targeted role-definition update below instead. Neither the switch nor the template grants `resume/action`.

### Targeted custom-role update

The following commands are a manual, approval-gated how-to, **not commands executed by this change**. The operator needs appropriate `Microsoft.Authorization/roleDefinitions/write` permission; assigning a role also needs `Microsoft.Authorization/roleAssignments/write` at the chosen scope.

1. Inspect the intended role and **all existing assignments** before widening it. Updating a definition affects every assignment of that role, including any older subscription-wide assignment:

   ```powershell
   az role definition list --name '<custom-role-definition-id>' --output json
   az role assignment list --role '<custom-role-definition-id>' --all --output table
   ```

2. Export and construct an editable role-definition file, preserving existing permissions and assignable scopes. Add **only** the selected extension actions:

   ```powershell
   $existingJson = az role definition list --name '<custom-role-definition-id>' --query '[0]' --output json
   if ($LASTEXITCODE -ne 0) { throw 'Cannot read custom role.' }
   $existing = $existingJson | ConvertFrom-Json
   if ($null -eq $existing -or $existing.roleType -ne 'CustomRole') { throw 'Expected an existing custom role.' }
   # Choose only what the approved operations need; delete unneeded entries.
   $extraActions = @(
       'Microsoft.Fabric/capacities/write'
       'Microsoft.Fabric/capacities/resume/action'
   )
   $role = @{
       Name = $existing.roleName
       Id = $existing.name
       IsCustom = $true
       Description = $existing.description
       Actions = @(@($existing.permissions | ForEach-Object { $_.actions }) + $extraActions | Select-Object -Unique)
       NotActions = @($existing.permissions | ForEach-Object { $_.notActions })
       DataActions = @($existing.permissions | ForEach-Object { $_.dataActions })
       NotDataActions = @($existing.permissions | ForEach-Object { $_.notDataActions })
       AssignableScopes = @($existing.assignableScopes)
   }
   $role | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath '.\extension-role.json' -Encoding utf8
   ```

   Resume's JSON action is `"Microsoft.Fabric/capacities/resume/action"`; Restart also keeps `"Microsoft.Fabric/capacities/suspend/action"`. Scale needs `"Microsoft.Fabric/capacities/write"`. Review `NotActions` as well: an action excluded there is not granted by adding it to `Actions`. Stop and review manually if the existing role has multiple permission blocks or conditional restrictions.

3. Review the local JSON, obtain approval, then apply only that role change:

   ```powershell
   az role definition update --role-definition '.\extension-role.json'
   if ($LASTEXITCODE -ne 0) { throw 'Role update failed.' }
   az role definition list --name '<custom-role-definition-id>' --output json
   ```

4. Prefer a dedicated extension role/identity if the existing role has broad assignments. Assign it to the specific capacity, or deliberately to its resource group:

   ```powershell
   az role assignment create --assignee-object-id '<managed-identity-principal-id>' `
       --assignee-principal-type ServicePrincipal --role '<custom-role-definition-id>' `
       --scope '/subscriptions/<subscription-id>/resourceGroups/<capacity-resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>'
   ```

Adding a narrow assignment does **not** remove a previous broad assignment. Review/remove unintended broad assignments through your normal change process. Permissions widen the blast radius; `CapacityResourceId` is a filter, not an RBAC boundary. Manual definition changes may be overwritten by a later template deployment, so reconcile the approved extension permissions into your separate maintained infrastructure before redeploying; the default template remains unchanged here.

## 4. Create additional schedules for the same adapted runbook

Do this only after the separate extension test copy is adapted and approved for testing. The unchanged default runbook does **not** accept `Operation` or `TargetSku`. Do not bind these examples to the existing published default runbook.

| Schedule | Parameters, all string values | Example time | Ordering |
| --- | --- | --- | --- |
| Existing evening policy | `Operation='Suspend'; DryRun='true'` | Daily 22:00 UTC | Keep or replace its existing link; do not duplicate it. |
| Second: morning | `Operation='Resume'; DryRun='true'` | Daily 07:00 UTC | Allow time to reach Active before work starts. |
| Third: weekend | `Operation='Scale'; TargetSku='F2'; DryRun='true'` | Saturday 06:00 UTC | Scale only while Active; a paused capacity is not implicitly resumed. |

These are alternative policies to reconcile, not a ready-made combined timetable. If nightly pause is enabled, move the weekend scale to an Active window, omit that pause, or resume and verify Active separately first. Review backstop schedules and avoid overlap. A default morning schedule also resumes on weekends unless you intentionally configure weekday recurrence.

The end-of-file block contains the complete loop for all three examples. This is the same request shape for **one** schedule/link; repeat with the table's operation, a distinct name, the appropriate recurrence, and a **fresh GUID for every new link**:

```powershell
$accountId = '/subscriptions/<subscription-id>/resourceGroups/<automation-resource-group>/providers/Microsoft.Automation/automationAccounts/<automation-account>'
$capacityId = '/subscriptions/<subscription-id>/resourceGroups/<capacity-resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>'
$scheduleName = '<morning-schedule>'
$scheduleBody = @{
    name = $scheduleName
    properties = @{
        startTime = '<future-date>T07:00:00Z'
        frequency = 'Day'
        interval = 1
        timeZone = 'UTC'
    }
}
$scheduleBody | ConvertTo-Json -Depth 6 | Set-Content '.\extension-schedule.json' -Encoding utf8
az rest --method put --url "https://management.azure.com${accountId}/schedules/${scheduleName}?api-version=2024-10-23" `
    --headers 'Content-Type=application/json' --body '@extension-schedule.json'
if ($LASTEXITCODE -ne 0) { throw 'Schedule PUT failed.' }

$jobScheduleId = [guid]::NewGuid().ToString()
$jobScheduleBody = @{
    properties = @{
        runbook = @{ name = '<extension-test-runbook-name>' }
        schedule = @{ name = $scheduleName }
        parameters = @{
            Operation = 'Resume'
            DryRun = 'true'
            CapacityResourceId = $capacityId
            ExcludeTagName = 'autopause'
            ExcludeTagValue = 'skip'
        }
    }
}
$jobScheduleBody | ConvertTo-Json -Depth 6 | Set-Content '.\extension-jobSchedule.json' -Encoding utf8
az rest --method put --url "https://management.azure.com${accountId}/jobSchedules/${jobScheduleId}?api-version=2024-10-23" `
    --headers 'Content-Type=application/json' --body '@extension-jobSchedule.json'
if ($LASTEXITCODE -ne 0) { throw 'Job-schedule PUT failed.' }
```

| Adaptation | Exact property/parameter change |
| --- | --- |
| Evening | Set `parameters.Operation='Suspend'` and choose the evening future `startTime`. |
| Weekend | Set `properties.frequency='Week'`, `properties.advancedSchedule=@{ weekDays=@('Saturday') }`, choose a future Saturday `startTime`, and set `parameters.Operation='Scale'` and `parameters.TargetSku='F2'`. |
| Local business time | Use a supported IANA `properties.timeZone` and a matching offset in `startTime`; review daylight-saving behavior. |
| Strings | Keep `DryRun='true'`, SKU values, IDs, and any timeout/poll parameters as strings in `properties.parameters`. Schedule `interval` itself is numeric. |
| Reruns | Inventory existing `jobSchedules` first. Fresh GUIDs are required for new associations, but blindly rerunning creation can duplicate executions. |

Replace every placeholder, including dates, before running anything. Schedule starts must be sufficiently in the future (allow at least five minutes). The JSON files above are local request bodies, avoiding shell-dependent inline JSON escaping. The commands create schedule definitions and associations, not immediate jobs.

Reference request contracts: [Schedule - Create Or Update, 2024-10-23](https://learn.microsoft.com/rest/api/automation/schedule/create-or-update?view=rest-automation-2024-10-23) and [Job Schedule - Create, 2024-10-23](https://learn.microsoft.com/rest/api/automation/job-schedule/create?view=rest-automation-2024-10-23).

## 5. Test safely before enabling anything

| Stage | Check | Pass condition |
| --- | --- | --- |
| Offline | Parse the adapted file; add mocked tests for new decisions, helpers, and dispatch. | Existing Suspend behavior passes; new operation tests pass without Azure calls. |
| Negative cases | Excluded tags, empty exclusion name, invalid/non-F SKU, paused Scale, transitional states, permission denial, timeout, and restart resume failure. | No mutation for excluded/unsafe states; errors surface in final job status. |
| DryRun | Run the isolated extension copy with `-Operation Resume`, `Scale`, or `Restart` and **`-DryRun 'true'`**. Start with `-CapacityResourceId '<capacity-resource-id>'`. | Correct `WouldResume`, `WouldScale`, or `WouldRestart`; no POST/PATCH. Read-only discovery/state requests still occur. |
| One capacity | With explicit operator approval, run only the isolated test copy against one non-excluded test `CapacityResourceId`, changing to `-DryRun 'false'`. | Correct state transitions and final SKU; do not broaden scope yet. |
| Activity Log | Open the test capacity's Azure Activity Log and correlate the managed identity, operation, timestamps, and result with Automation job output. | Only intended suspend/resume/write operations at the approved capacity; no unexpected admin or tag changes. Allow for log ingestion delay. |
| Schedule rehearsal | Keep every added link at `DryRun='true'` for its first scheduled execution. | Expected time zone, target filter, operation, and exclusion behavior. |
| Approval | Review billing, interruption window, polling budgets, and narrow RBAC. | Only then change the intended link to `'false'`; keep other links dry-run. |

The default Pester suite validates the shipped suspend-only implementation, **not** these commented extension examples. Passing it does not certify resume, scale, or restart. Extend test coverage and use an isolated non-production capacity before adopting the pattern; no extension is enabled or deployed by this documentation.
