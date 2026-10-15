# Auto-pause infrastructure

Subscription-scoped Bicep for a reusable Azure Automation deployment. No credentials,
capacity names, or subscription IDs are embedded.

## Files

| File | Purpose |
| --- | --- |
| `main.bicep` | Creates the resource group and deploys both modules; returns names, managed-identity IDs and the custom role's `roleDefinitionId` for the deployment script. |
| `modules\automation.bicep` | Creates the user-assigned identity, Basic Automation account, `PowerShell-74` runtime environment, empty runbook shell, daily schedules, and optional email/job-failure alerting. |
| `modules\rbac.bicep` | Defines a read/suspend custom role and, by default, assigns it to the identity at the current subscription scope. With `assignRoleAtSubscription = false` it creates the role definition only. |
| `main.parameters.example.json` | ARM parameter-file example; replace placeholders before use. |
| `README.md` | Parameter reference and offline validation instructions. |

## Parameters

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `location` | string | Required | Region for the resource group and regional resources. |
| `resourceGroupName` | string | `rg-fabric-autopause` | Resource group name; 1-90 characters. |
| `namePrefix` | string | `fabricautopause` | Shared name prefix; 3-47 alphanumeric characters or hyphens, starting with a letter. Also part of the custom role definition's name GUID (see [Role definition and assignment](#role-definition-and-assignment)). |
| `timeZone` | string | `UTC` | IANA schedule time zone, e.g. `America/Chicago`; governs daily local-time recurrence. |
| `scheduleStartTime` | string | Required | Future ISO-8601 time with offset, e.g. `2026-10-16T00:00:00-05:00`; choose a future date with sufficient lead time. |
| `backstopStartTime` | string | `''` | Optional future ISO-8601 time with offset; empty omits the backstop schedule. |
| `alertEmails` | array | `[]` | Email recipients, e.g. `ops@example.com`; empty omits both alerting resources. |
| `includeWritePermission` | bool | `false` | Adds `Microsoft.Fabric/capacities/write` only if suspension needs it. Besides suspending, `capacities/write` also lets the identity scale a capacity and change its capacity admins. Resume is never granted. |
| `assignRoleAtSubscription` | bool | `true` | Assigns the custom role to the identity at the whole subscription. `false` creates the role definition only; assign it yourself at a narrower scope (see below). |
| `customRoleName` | string | `Fabric Capacity AutoPause Operator` | Custom-role display name. Role names must be unique per tenant, so use a distinct name for independent role definitions. |
| `additionalAssignableScopes` | array | `[]` | Additional ARM scopes where the role may be assigned; does **not** grant access there. |
| `tags` | object | `{}` | Tags for the resource group and resources that support them. |
| `azPackageVersion` | string | `12.3.0` | Version of the Az PowerShell package installed in the `PowerShell-74` runtime environment. |

`scripts\deploy.ps1` maps these onto its own switches: `-IncludeWritePermission`,
`-SkipSubscriptionRoleAssignment` (sets `assignRoleAtSubscription = false`),
`-CustomRoleName`, `-AdditionalAssignableScopes`, `-Tags` and `-AzPackageVersion`
(a plain `x.y.z` version, default `12.3.0`).

## Role definition and assignment

The RBAC module's required `principalId` is wired to the Automation module's
identity output. The custom role grants only `Microsoft.Fabric/capacities/read` and
`Microsoft.Fabric/capacities/suspend/action`; resume is never granted. With
`includeWritePermission` it also gets `Microsoft.Fabric/capacities/write`, which
lets the identity scale a capacity and change its capacity admins as well, so
enable it only if suspension fails without it.

The role definition's name is `guid(subscription().id, namePrefix, customRoleName)`,
so two deployments in one subscription with different settings cannot overwrite
each other's role definition. The definition's `assignableScopes` always contain
the subscription plus `additionalAssignableScopes`. The `roleDefinitionId` output
returns its resource ID.

By default the identity receives the role at the **whole subscription**: it can
read and suspend every Fabric capacity there. For least privilege, set
`assignRoleAtSubscription = false` (`-SkipSubscriptionRoleAssignment`). Bicep then
creates the role definition but **no role assignment**, and **nothing can be
paused until you assign the role** at the narrowest scope that covers your
capacities. The scope must be inside the role's assignable scopes (the
subscription plus `additionalAssignableScopes`). Use the `identityPrincipalId`
output (the deployment summary prints it):

```powershell
# every capacity in one resource group
az role assignment create --assignee-object-id <principalId> --assignee-principal-type ServicePrincipal --role "Fabric Capacity AutoPause Operator" --scope /subscriptions/<subscription-id>/resourceGroups/<resource-group-name>

# a single capacity
az role assignment create --assignee-object-id <principalId> --assignee-principal-type ServicePrincipal --role "Fabric Capacity AutoPause Operator" --scope /subscriptions/<subscription-id>/resourceGroups/<resource-group-name>/providers/Microsoft.Fabric/capacities/<capacity-name>
```

Without the switch, check what the identity was granted with
`az role assignment list --assignee <principalId> --all -o table`.

Notes:

- The deployer needs permission to create the infrastructure and the custom role
  definition (`Microsoft.Authorization/roleDefinitions/write`) at the subscription
  and, unless the assignment is skipped, `Microsoft.Authorization/roleAssignments/write`
  there, plus rights on any additional assignable scopes.
- Re-running with `assignRoleAtSubscription = false` does **not** remove an
  assignment created by an earlier run; delete it with `az role assignment delete`.
- Because the role definition name now includes `namePrefix`, redeploying an
  older deployment (whose role definition was named without it) creates a second
  definition with the same display name, which Azure rejects. Remove the old role
  assignment and role definition first, or choose a new `customRoleName`.

## Runbook and schedules

The runbook shell is `Invoke-FabricCapacityAutoPause`. Bicep deliberately creates
neither runbook content nor `jobSchedules`: `scripts\deploy.ps1` uploads and
publishes the runbook (printing its SHA-256 so you can verify what was deployed),
then links `autopause-nightly` and optional `autopause-backstop`. The runbook's
identity parameter is `UserAssignedIdentityClientId` (use the `identityClientId`
output), and its `DryRun` parameter defaults to `true`; schedule links supply it
explicitly as the **string** `'true'` or `'false'`, like every other runbook
parameter they send. Discovery filters are runbook parameters, not infrastructure
parameters. The deploy script rejects an empty or whitespace `-ExcludeTagName`,
because a capacity can never carry an empty tag name and every opt-out would be
silently disabled.

The optional alert checks Automation's `TotalJob` metric for `Failed`, `Stopped`,
or `Suspended` jobs every 15 minutes over the last hour, at severity 2.

VERIFY ON FIRST DEPLOY: confirm the daily schedules keep their local wall-clock
time across a daylight-saving change; offline compilation cannot verify service
behavior.

## Build and lint (offline)

From the repository root, using Azure CLI and Bicep CLI 0.48.1:

```powershell
az bicep build --file infra\main.bicep --stdout > $null
az bicep lint --file infra\main.bicep
az bicep build --file infra\modules\automation.bicep --stdout > $null
az bicep build --file infra\modules\rbac.bicep --stdout > $null
```

These commands compile/lint locally without signing in or deploying resources.
They do not validate parameter values, permissions, regional availability, or
live Automation/Monitor API behavior.

References: [Automation runbooks](https://learn.microsoft.com/azure/templates/microsoft.automation/2024-10-23/automationaccounts/runbooks),
[runtime environments](https://learn.microsoft.com/azure/templates/microsoft.automation/2024-10-23/automationaccounts/runtimeenvironments),
[schedules](https://learn.microsoft.com/azure/templates/microsoft.automation/2024-10-23/automationaccounts/schedules).
