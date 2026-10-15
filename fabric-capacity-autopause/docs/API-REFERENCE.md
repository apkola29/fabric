# API reference

This project schedules a **time-based, nightly suspension of Microsoft Fabric F-SKU capacities** with an Azure Automation PowerShell runbook. It pauses at the scheduled time regardless of workload, and by default does not automatically resume capacities or scale them (see [EXTENDING.md](EXTENDING.md) for those optional extensions).

The reference follows `runbooks\Invoke-FabricCapacityAutoPause.ps1`, `scripts\deploy.ps1`, `infra\main.bicep`, `infra\modules\automation.bicep`, `infra\modules\rbac.bicep`, `infra\README.md`, and `tests\uat\Invoke-AutoPauseUat.ps1`. Public Microsoft Learn documentation was used to check contracts; no authenticated Azure API was called to write this document.

## Conventions and safety

| Convention | Meaning |
| --- | --- |
| Default behavior | `DryRun = 'true'`. Discovery and authoritative GETs run; a new suspend request requires `DryRun = 'false'`, normally selected with the deploy script's `-EnableEnforcement`. |
| Default authorization scope | Infrastructure assigns the managed identity's custom role at the subscription unless `-SkipSubscriptionRoleAssignment` is selected. Discovery parameters only narrow that access. |
| Examples | PowerShell 7 syntax for both Azure CLI and Az PowerShell. Replace every `<placeholder>` before use; authenticate the appropriate caller separately. Do not execute all examples as a script. |
| JSON request files | Save each request-body block to its indicated placeholder file before using the paired commands. CLI `--body '@<file>.json'` avoids Windows native-command JSON quoting problems. Files are local examples, not Automation assets. |
| ARM response wrapper | `Invoke-AzRestMethod` returns `StatusCode`, `Headers`, and string `Content`; use `ConvertFrom-Json` only when that content is JSON. |
| No body | Omit the body entirely for the documented GET, DELETE, suspend, resume, and publish requests. Do not send a fabricated `{}` requirement. |
| Observed live | Behavior supplied as prior project observations, not a new live test or a guarantee for every environment. |
| Default permissions | Capacity `read` and `suspend/action` only. `write` is opt-in; `resume/action` and `delete` are never granted by the custom role. |

Set these variables once for the ARM examples. The capacity and Automation account may be in different resource groups.

```powershell
$arm = 'https://management.azure.com'
$subscriptionPath = '/subscriptions/<subscription-id>'
$capacityPath = "$subscriptionPath/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>"
$accountPath = "$subscriptionPath/resourceGroups/<automation-resource-group>/providers/Microsoft.Automation/automationAccounts/<account>"
$runbookName = 'Invoke-FabricCapacityAutoPause'
$jobId = '<job-guid>'
$scheduleName = '<schedule-name>'
```

### Shared asynchronous-operation contract

| Response/header | Interpretation |
| --- | --- |
| `202 Accepted` | Request accepted, not proof the capacity is paused or the runbook is published. A resource PUT can also start asynchronous work with `201 Created`. |
| `Azure-AsyncOperation` | When returned, GET this exact URL to track the operation. Typical operation-status JSON exposes `status`, with terminal values `Succeeded`, `Failed`, or `Canceled`, and an `error` on failure. |
| `Location` | Follow this exact URL when `Azure-AsyncOperation` is absent. Response semantics depend on the operation; a polling response can remain `202`. |
| `Retry-After` | Wait the indicated seconds before polling/retrying. Do not synthesize polling URLs, strip their query parameters, or assume every operation returns every header. |
| Polling permissions | Provider operation-status URLs can require broader access than a single capacity. The runbook instead polls the capacity's own GET endpoint, using its existing `capacities/read` permission. |

**What this code actually does:** the runbook accepts suspend HTTP `200` or `202`, then polls `properties.state` until `Paused` or `Suspended`. Its wrapper does not return LRO headers to its caller. It does not follow `Azure-AsyncOperation` or `Location`, and does not use a successful POST body as a completion signal. The deploy script uploads draft content, retries publication, and polls runbook `properties.state = 'Published'`; it also does not follow the LRO headers.

## 1. Azure Resource Graph: discover capacities

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Discover capacity IDs and inventory fields visible to the runbook identity, across its selected scope. |
| HTTP | `POST https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01` |
| Permission | Read access to each returned resource: `Microsoft.Fabric/capacities/read`. The provider-operation catalog names the query operation `Microsoft.ResourceGraph/resources/read`; the project's role contains the resource read action, not a separate broad Resource Graph grant. |
| Scope | `subscriptions: ["<subscription-id>"]` **or** `managementGroups: ["<management-group-id>"]`. The runbook rejects using both. If neither is supplied, the query is tenant-scoped within the authenticated identity's readable resources, not an elevation to tenant-wide access. |
| Pagination | `options.resultFormat = "objectArray"` and `options.$top = 1000`. Reissue the same query and scopes with the response's opaque `$skipToken` in `options.$skipToken` until absent. |
| Fields read | Response `data[]`: `id`, `name`, `subscriptionId`, `resourceGroup`, `location`, `sku`, `state`, `tags`; response `$skipToken` drives paging. The inventory `state` is not authoritative for a pause decision. `count`, `totalRecords`, and `resultTruncated` are available but not used by this runbook. |
| Success/async | `200 OK`, JSON; no `202`/LRO polling. |
| Common errors | `400` invalid KQL or scope; `401` wrong/expired token; `403` authorization; `429` throttling. Missing resource read access can yield no matching rows rather than an error. |

Exact unfiltered KQL built by `New-GraphRequestBody`:

```kusto
resources
| where type =~ 'microsoft.fabric/capacities'
| project id, name, subscriptionId, resourceGroup, location, sku = tostring(sku.name), state = tostring(properties.state), tags
```

When supplied, these lines are inserted **between** the type filter and the projection, in this order. Values are validated before interpolation; comparisons are case-insensitive.

```kusto
| where resourceGroup =~ '<resource-group>'
| where name =~ '<capacity-name>'
| where id =~ '/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>'
```

Request body (`<graph-request>.json`); omit `$skipToken` on the first page, as shown:

```json
{
  "subscriptions": ["<subscription-id>"],
  "query": "resources\n| where type =~ 'microsoft.fabric/capacities'\n| project id, name, subscriptionId, resourceGroup, location, sku = tostring(sku.name), state = tostring(properties.state), tags",
  "options": {
    "resultFormat": "objectArray",
    "$top": 1000
  }
}
```

```powershell
# Azure CLI
az rest --method post --url "$arm/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01" --body '@<graph-request>.json'

# Az PowerShell
$response = Invoke-AzRestMethod -Path '/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01' -Method POST -Payload (Get-Content -LiteralPath '<graph-request>.json' -Raw)
$page = $response.Content | ConvertFrom-Json
$page.data
$page.'$skipToken'
```

An empty broad search logs a warning. An explicit `CapacityName` or `CapacityResourceId` that is not discovered fails the job. Resource Graph is an indexed inventory, so the runbook GETs each discovered resource again before considering its current state and opt-out tags.

## 2. Fabric capacity ARM API

All operations below use **`api-version=2023-11-01`**, ARM tokens, and the `Microsoft.Fabric/capacities` resource type. The capacity must already exist; this project's deployment does not create or delete capacities.

### 2.1 GET a capacity

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Authoritative state/tag read before deciding, and state polling after suspension. |
| HTTP | `GET https://management.azure.com/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>?api-version=2023-11-01` |
| RBAC | `Microsoft.Fabric/capacities/read` at the capacity or an ancestor. |
| Request body | None. |
| Fields read | Runbook: `properties.state`, `tags`. UAT additionally checks `id`, `name`, `sku.name`, `properties.fabricCapacityId`. This last field is distinct from the ARM resource ID. |
| Success/async | `200 OK`, JSON capacity resource; no LRO. `properties.provisioningState` is a separate field, not the runbook's power-state decision input. |
| Common errors | `401`/`403` denied; `404` wrong name/scope or deleted resource; `429`/`5xx` transient failures. Initial reads mark `Denied`/`Error`; polling read failures warn and are retried until the shared deadline. |

```powershell
az rest --method get --url "$arm${capacityPath}?api-version=2023-11-01"

$response = Invoke-AzRestMethod -Path "${capacityPath}?api-version=2023-11-01" -Method GET
$capacity = $response.Content | ConvertFrom-Json
$capacity.properties.state
$capacity.tags
```

### 2.2 List capacities by subscription or resource group

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Operator inventory alternative; the runbook uses Resource Graph instead. |
| Subscription HTTP | `GET https://management.azure.com/subscriptions/<subscription-id>/providers/Microsoft.Fabric/capacities?api-version=2023-11-01` |
| Resource-group HTTP | `GET https://management.azure.com/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities?api-version=2023-11-01` |
| RBAC | `Microsoft.Fabric/capacities/read` at the applicable scope. |
| Request body | None for either request. |
| Fields read | None by the runbook through these endpoints. Operator response is `value[]` of capacity resources and `nextLink` when another page exists. Follow `nextLink` unchanged. |
| Success/async | `200 OK`, JSON collection; no LRO. |
| Common errors | `401`, `403`, `404` for an invalid resource group, `429`, `5xx`. A list is not a substitute for the runbook's fresh GET. |

```powershell
# Subscription
az rest --method get --url "$arm${subscriptionPath}/providers/Microsoft.Fabric/capacities?api-version=2023-11-01"
Invoke-AzRestMethod -Path "${subscriptionPath}/providers/Microsoft.Fabric/capacities?api-version=2023-11-01" -Method GET

# Resource group
az rest --method get --url "$arm${subscriptionPath}/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities?api-version=2023-11-01"
Invoke-AzRestMethod -Path "${subscriptionPath}/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities?api-version=2023-11-01" -Method GET
```

### 2.3 Suspend: used only when enforcement is enabled

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Pause an `Active`, non-excluded capacity at the scheduled time. |
| HTTP | `POST https://management.azure.com/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>/suspend?api-version=2023-11-01` |
| RBAC | `Microsoft.Fabric/capacities/suspend/action`. The role also grants `read` for discovery and verification. `-IncludeWritePermission` optionally adds `Microsoft.Fabric/capacities/write` if required in an environment; it is not part of the minimum default grant. |
| Request body | None. |
| Fields read | HTTP status only from POST; no success-body fields. On failure, `error.code` and `error.message`, or raw text. Completion comes from subsequent GET `properties.state`. |
| Success/async | `200 OK` or `202 Accepted`. Learn documents `Location`/`Retry-After` and its example also returns `Azure-AsyncOperation`. Apply the shared LRO contract for manual clients; the runbook uses capacity GET polling instead. |
| Common errors | `403 AuthorizationFailed`; `404` missing capacity; `409` conflicting transition; `429` or `5xx`. Treat a concurrent operation as a reason to inspect state, not to repeatedly force suspension. |

**Mutating example: this can interrupt workloads.**

```powershell
az rest --method post --url "$arm${capacityPath}/suspend?api-version=2023-11-01"
Invoke-AzRestMethod -Path "${capacityPath}/suspend?api-version=2023-11-01" -Method POST
```

### 2.4 Resume: not used by the nightly runbook

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Explicit human restoration, or the opt-in UAT harness restoring its test capacity. No default morning-resume schedule exists. |
| HTTP | `POST https://management.azure.com/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>/resume?api-version=2023-11-01` |
| RBAC | `Microsoft.Fabric/capacities/resume/action`, plus `read` to verify state. This action is never in the project's custom role. |
| Request body | None. |
| Fields read | None by the nightly runbook. UAT verifies subsequent GET `properties.state = 'Active'`. |
| Success/async | `200` or `202`; `Location`, `Retry-After`, and example `Azure-AsyncOperation`. A `202` does not mean immediately active. |
| Common errors | `403` without resume permission; `404`; `409` conflicting state; `429`/`5xx`. Resuming also resumes capacity billing. |

```powershell
az rest --method post --url "$arm${capacityPath}/resume?api-version=2023-11-01"
Invoke-AzRestMethod -Path "${capacityPath}/resume?api-version=2023-11-01" -Method POST
```

### 2.5 PATCH/PUT capacity update: scaling is not used by default

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Operator-initiated SKU change, not auto-pause. UAT uses PATCH **tags**, not SKU changes, to test exclusions. |
| HTTP | `PATCH` or `PUT https://management.azure.com/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>?api-version=2023-11-01` |
| RBAC | `Microsoft.Fabric/capacities/write`; `read` is needed for preflight/polling. The write grant also permits changes such as capacity administration, so do not add it just to enable unrelated scaling. |
| Request | Use PATCH for a partial update: `{ "sku": { "name": "F16", "tier": "Fabric" } }`. PUT is the create-or-update contract and additionally requires `location` and `properties.administration`; do not send only the PATCH body as PUT. Preserve existing configuration deliberately. |
| Fields read | No scale responses are read by the project. Capacity responses expose `sku.name`, `sku.tier`, `properties.state`, and `properties.provisioningState`; UAT's tag PATCH is followed by state/tag GETs. |
| Success/async | PATCH: `200` or `202`, with `Location`/`Retry-After` on acceptance. PUT: documented `200` update or `201` create; `201` can include `Azure-AsyncOperation`/`Retry-After`. Poll any returned LRO and then re-read the capacity. |
| Common errors | `400` invalid SKU/body; `403`; `409` transition or availability constraints; `429`/`5xx`. Check regional SKU availability and cost before changing size. |

PATCH body (`<capacity-scale>.json`):

```json
{
  "sku": {
    "name": "F16",
    "tier": "Fabric"
  }
}
```

```powershell
az rest --method patch --url "$arm${capacityPath}?api-version=2023-11-01" --body '@<capacity-scale>.json'
Invoke-AzRestMethod -Path "${capacityPath}?api-version=2023-11-01" -Method PATCH -Payload (Get-Content -LiteralPath '<capacity-scale>.json' -Raw)
```

PUT body (`<capacity-put>.json`), only for an intentional full create-or-update:

```json
{
  "location": "<location>",
  "sku": { "name": "F16", "tier": "Fabric" },
  "properties": {
    "administration": {
      "members": ["<existing-capacity-admin>"]
    }
  },
  "tags": { "autopause": "skip" }
}
```

```powershell
az rest --method put --url "$arm${capacityPath}?api-version=2023-11-01" --body '@<capacity-put>.json'
Invoke-AzRestMethod -Path "${capacityPath}?api-version=2023-11-01" -Method PUT -Payload (Get-Content -LiteralPath '<capacity-put>.json' -Raw)
```

### 2.6 DELETE: never used by this project

| Item | Contract |
| --- | --- |
| Purpose | Destructive lifecycle operation documented for distinction from pause; neither deployment, runbook, nor UAT deletes a capacity. |
| HTTP | `DELETE https://management.azure.com/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>?api-version=2023-11-01` |
| RBAC | `Microsoft.Fabric/capacities/delete`; never granted by the custom role. |
| Request body / fields read | No body; no response fields read by the project. |
| Success/async | `202` deletion accepted, with `Location`/`Retry-After` and example `Azure-AsyncOperation`; `204` if the resource does not exist. |
| Common errors | `403`, resource-lock/policy denial, `409` conflicting work, `429`/`5xx`. Deleting is not pausing. |

**Reference only; do not use for nightly shutdown.**

```powershell
az rest --method delete --url "$arm${capacityPath}?api-version=2023-11-01"
Invoke-AzRestMethod -Path "${capacityPath}?api-version=2023-11-01" -Method DELETE
```

### 2.7 ARM state handling

These are the Learn `ResourceState` values under **`properties.state`**, not `properties.provisioningState`. Opt-out tags take precedence over every state: by default `autopause=skip` yields `Excluded`. An empty exclusion value means exclude on tag presence alone; the tag name cannot be empty.

| `properties.state` | Runbook decision | Result |
| --- | --- | --- |
| `Active` | `Pause` | `WouldPause` in dry-run; otherwise POST suspend, then verify. |
| `Suspended`, `Paused` | `Skip` | `Skipped`; already off. |
| `Suspending`, `Pausing` | `Await` | No duplicate POST; wait for off state. This verification also occurs in dry-run. |
| `Provisioning`, `Updating`, `Resuming`, `Scaling`, `Preparing` | `Defer` | `Deferred`; a later nightly/backstop run can reconsider it. |
| `Failed`, `Deleting` | `Warn` | `Warning`, no mutation. These do not alone fail the job. |
| Empty or an unrecognized future value | `Warn` | `Warning`, no mutation; do not reinterpret it as `Active`. |

All pending capacities are polled round-robin against **one shared wait deadline**: default 15 minutes, `PollSeconds = 15`; `PauseTimeoutMinutes` accepts 1–150. Only `Paused` or `Suspended` completes verification. Timeout sets `Error`, and any `Error` or `Denied` result makes the runbook throw so the Automation job fails. Discovery, submission, network retries, and individual calls add time outside/beyond the polling window; this is not a hard wall-clock bound on the entire job.

### 2.8 Fabric REST capacity visibility: a different API

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Optional UAT visibility check only; not discovery or suspension for the nightly runbook. |
| HTTP/version | `GET https://api.fabric.microsoft.com/v1/capacities`; version is the `/v1` path, **no ARM `api-version`**. |
| Authorization | A token for audience/resource `https://api.fabric.microsoft.com`, not `https://management.azure.com/`. Delegated scopes: `Capacity.Read.All` or `Capacity.ReadWrite.All`; Fabric access determines visibility. There is no equivalent ARM RBAC action that alone grants this Fabric API access. |
| Request body | None. |
| Fields read | UAT: `value[].id`, `displayName`, `state`, and `continuationUri`; matches the name or ARM `properties.fabricCapacityId`. Learn also returns `sku`, `region`, and `continuationToken`. |
| State distinction | Learn defines `Active` and `Inactive`. **Observed live:** an ARM-paused capacity remained visible here as `Inactive`. `Inactive` means unavailable, not a uniquely documented proof of an ARM pause; use ARM GET to verify suspension. |
| Success/async | `200` JSON; follow `continuationUri` unchanged. `429` includes `Retry-After`; no LRO. |
| Common errors | `401` wrong token audience, `403` insufficient Fabric access, `429`, `5xx`; absence from a user's capacity list is not proof the ARM resource was deleted. |

```powershell
# Azure CLI: select the Fabric token resource explicitly.
az rest --method get --url 'https://api.fabric.microsoft.com/v1/capacities' --resource 'https://api.fabric.microsoft.com'

# Az PowerShell: -Path is for ARM. Use -Uri/-ResourceId for a non-ARM audience.
Invoke-AzRestMethod -Uri 'https://api.fabric.microsoft.com/v1/capacities' -ResourceId 'https://api.fabric.microsoft.com' -Method GET
```

The UAT implementation obtains a Fabric-audience token and uses `Invoke-RestMethod`; it does not use the runbook's ARM wrapper for this check.

## 3. Azure Automation ARM API

Every path in this section is relative to:

```text
https://management.azure.com/subscriptions/<subscription-id>/resourceGroups/<automation-resource-group>/providers/Microsoft.Automation/automationAccounts/<account>
```

Each uses **`api-version=2024-10-23`**. Automation orchestration permissions belong to the deployer/operator, **not** to the capacity managed identity.

### 3.1 Create a job

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Manual/UAT execution of an already published runbook. Nightly jobs are created by the schedule service. |
| HTTP | `PUT <account-base>/jobs/<job-guid>?api-version=2024-10-23` |
| RBAC | `Microsoft.Automation/automationAccounts/jobs/write`. Additional GET/stream permissions are needed to inspect the job. |
| Request | `properties.runbook.name` and `properties.parameters`; **all parameter values are strings**, including booleans and integers. Omit `runOn` for the cloud runtime. |
| Fields read | UAT tracks the locally generated job GUID, then polls `properties.status`; job listings also expose `properties.jobId`, `runbook.name`, timestamps, and `parameters`. |
| Success/async | `201 Created`, JSON Job, commonly `status: "New"`. This is job submission, not a `202` ARM LRO; poll GET job for execution completion. |
| Common errors | `400` parameter validation, `403`, `404` runbook, unpublished runbook/conflicting job identifier, or runtime/package failures reported later by GET job. Use a fresh job GUID for each intended execution; do not blindly duplicate a submission after a lost response. |

Request body (`<job-request>.json`):

```json
{
  "properties": {
    "runbook": { "name": "Invoke-FabricCapacityAutoPause" },
    "parameters": {
      "SubscriptionIds": "<subscription-id>",
      "CapacityResourceId": "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>",
      "UserAssignedIdentityClientId": "<managed-identity-client-id>",
      "ExcludeTagName": "autopause",
      "ExcludeTagValue": "skip",
      "DryRun": "true",
      "PauseTimeoutMinutes": "15",
      "PollSeconds": "15"
    }
  }
}
```

```powershell
$jobId = [guid]::NewGuid().ToString()
az rest --method put --url "$arm${accountPath}/jobs/${jobId}?api-version=2024-10-23" --body '@<job-request>.json'

# Alternative submission; generate another GUID if this is a second intended job.
Invoke-AzRestMethod -Path "${accountPath}/jobs/${jobId}?api-version=2024-10-23" -Method PUT -Payload (Get-Content -LiteralPath '<job-request>.json' -Raw)
```

### 3.2 GET job and diagnose failures

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Track execution and retrieve terminal failure details. |
| HTTP | `GET <account-base>/jobs/<job-guid>?api-version=2024-10-23` |
| RBAC | `Microsoft.Automation/automationAccounts/jobs/read`. |
| Request body | None. |
| Fields read | `properties.status`, `properties.exception`, `properties.statusDetails`; UAT also uses job IDs, runbook, parameters, and timing fields to attribute scheduled jobs. |
| Success/async | `200 OK`, JSON; no ARM LRO. UAT treats `Completed`, `Failed`, `Stopped`, and `Suspended` as terminal outcomes. |
| Common errors | `403`, `404` wrong/newly submitted job, `429`/`5xx`. An HTTP `200` can describe a **Failed** job. |

| Job status | Meaning for this project |
| --- | --- |
| `New`, `Activating`, `Running` | Not finished; keep polling within the caller's deadline. |
| `Completed` | Script finished; also inspect its output and state checks. Completion is not by itself proof the intended action occurred. |
| `Failed` | Read `properties.exception` first, and then streams. |
| `Stopped`, `Suspended` | Unsuccessful terminal outcome for UAT and monitored by the optional failure alert. |
| Other documented states | `Blocked`, `Disconnected`, `Suspending`, `Stopping`, `Resuming`, `Removing`; the UAT wait loop keeps waiting until its deadline unless a terminal status above is reached. |

**Observed live:** a Failed job's actual validation failure reason was in `properties.exception`, **not in its streams**. Streams can be empty when execution fails before output starts. The UAT reader appends `exception` and `statusDetails`; do not diagnose solely from the `/output` endpoint.

```powershell
az rest --method get --url "$arm${accountPath}/jobs/${jobId}?api-version=2024-10-23" --query 'properties.{status:status,exception:exception,statusDetails:statusDetails}'

$response = Invoke-AzRestMethod -Path "${accountPath}/jobs/${jobId}?api-version=2024-10-23" -Method GET
($response.Content | ConvertFrom-Json).properties | Select-Object status, exception, statusDetails
```

### 3.3 Job streams: list and detail

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Retrieve structured Output, Warning, and Error records for UAT assertions and diagnostics. |
| List HTTP | `GET <account-base>/jobs/<job-guid>/streams?api-version=2024-10-23` |
| Detail HTTP | `GET <account-base>/jobs/<job-guid>/streams/<job-stream-id>?api-version=2024-10-23` |
| RBAC | `Microsoft.Automation/automationAccounts/jobs/streams/read` for both requests. |
| Request body | None. |
| Fields read | List: `value[].properties.jobStreamId`, `streamType`, `summary`, optional `value`, and collection `nextLink`. Detail: `properties.streamText`, `summary`, `value`. `jobStreamId` is the stream identifier; do not depend on top-level `name`. |
| Success/async | `200` JSON for both. Follow `nextLink`; URI-escape the stream ID. Streams can lag the job status; UAT allows up to 60 seconds for its expected output pattern to appear. |
| Common errors | `403`; `404` wrong job/stream; empty or incomplete streams; `429`/`5xx`. `summary` can be null/truncated and is not necessarily the full output. |

The UAT fallback order is detail `streamText`, detail `summary`, list `summary`, decoded detail `value`, decoded list `value`. A `value` can be an object, array, or serialized JSON; the reader looks for `Message`, `Text`, or `value`. It does not assume a single string field always exists.

```powershell
az rest --method get --url "$arm${accountPath}/jobs/${jobId}/streams?api-version=2024-10-23"
Invoke-AzRestMethod -Path "${accountPath}/jobs/${jobId}/streams?api-version=2024-10-23" -Method GET

$streamId = [uri]::EscapeDataString('<job-stream-id>')
az rest --method get --url "$arm${accountPath}/jobs/${jobId}/streams/${streamId}?api-version=2024-10-23"
Invoke-AzRestMethod -Path "${accountPath}/jobs/${jobId}/streams/${streamId}?api-version=2024-10-23" -Method GET
```

### 3.4 GET job output: plain text

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Simple manual output inspection; UAT uses structured streams and job exception instead. |
| HTTP | `GET <account-base>/jobs/<job-guid>/output?api-version=2024-10-23` |
| RBAC | `Microsoft.Automation/automationAccounts/jobs/output/read`. |
| Request body | None. |
| Fields read | No JSON fields. Return the raw `Content` string. |
| Success/async | `200`; Learn lists `text/plain` and `application/json` media types with a string result. **Observed live:** this endpoint returned plain text, not a JSON object. |
| Common errors | `403`, `404`, `429`/`5xx`; empty output before records arrive. Parsing a plain-text response with `ConvertFrom-Json` is a client error. |

```powershell
# CLI can print non-JSON response text; do not apply a JSON --query projection.
az rest --method get --url "$arm${accountPath}/jobs/${jobId}/output?api-version=2024-10-23"

$response = Invoke-AzRestMethod -Path "${accountPath}/jobs/${jobId}/output?api-version=2024-10-23" -Method GET
$response.Content
```

### 3.5 Runbook draft content upload

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Deploy the exact local runbook source into the runbook shell created by Bicep. The deploy script prints the local SHA-256. |
| HTTP | `PUT <account-base>/runbooks/<runbook-name>/draft/content?api-version=2024-10-23` |
| RBAC | `Microsoft.Automation/automationAccounts/runbooks/draft/content/write`. |
| Request body | The **raw PowerShell source file**, `Content-Type: text/plain`; not JSON `{ "content": ... }` and not a JSON-quoted script. |
| Fields read | No response-body fields; deployment proceeds to publication. |
| Success/async | `202 Accepted`; Learn documents `Azure-AsyncOperation`, `Location`, and `Retry-After`. Upload completion is asynchronous. |
| Common errors | `400` wrong content/media shape; `403`; `404` missing runbook shell; publication attempted before upload settles. |

Example request payload is the content of `runbooks\Invoke-FabricCapacityAutoPause.ps1` itself.

```powershell
# Exact transport used by scripts\deploy.ps1, runnable from PowerShell:
az rest --method put --url "$arm${accountPath}/runbooks/${runbookName}/draft/content?api-version=2024-10-23" --headers 'Content-Type=text/plain' --body '@runbooks\Invoke-FabricCapacityAutoPause.ps1'

# Az REST payload equivalent; see the media-type limitation immediately below.
$source = Get-Content -LiteralPath 'runbooks\Invoke-FabricCapacityAutoPause.ps1' -Raw
Invoke-AzRestMethod -Path "${accountPath}/runbooks/${runbookName}/draft/content?api-version=2024-10-23" -Method PUT -Payload $source
```

**Az PowerShell media-type limitation:** Learn's `Invoke-AzRestMethod` syntax exposes `-Payload`, but no `-ContentType` or arbitrary-header parameter. The latter example expresses the path, method, and raw payload but cannot explicitly enforce the documented `text/plain` header; compatibility of that variant was not verified. Use the `az rest` command above, including from PowerShell, for the project's documented text upload. Do not invent an `Invoke-AzRestMethod -ContentType` parameter.

### 3.6 Publish draft and GET runbook

| Operation | HTTP | RBAC | Request body | Response fields read | Success |
| --- | --- | --- | --- | --- | --- |
| Publish | `POST <account-base>/runbooks/<runbook-name>/publish?api-version=2024-10-23` | `Microsoft.Automation/automationAccounts/runbooks/publish/action` | None | None | `202`, with `Location`/`Retry-After`. |
| Verify | `GET <account-base>/runbooks/<runbook-name>?api-version=2024-10-23` | `Microsoft.Automation/automationAccounts/runbooks/read` | None | `properties.state`; deployment requires `Published`. Bicep links `properties.runtimeEnvironment` to the runtime environment. | `200` JSON. |

Common errors: `403`, `404`, transient publication conflicts while draft upload is finishing, `429`/`5xx`. `scripts\deploy.ps1` retries publishing up to six times with 5-second exponential delay capped at 30 seconds, then polls the runbook every 5 seconds for up to 180 seconds. Published means the script is published, not that it has successfully run.

```powershell
az rest --method post --url "$arm${accountPath}/runbooks/${runbookName}/publish?api-version=2024-10-23"
Invoke-AzRestMethod -Path "${accountPath}/runbooks/${runbookName}/publish?api-version=2024-10-23" -Method POST

az rest --method get --url "$arm${accountPath}/runbooks/${runbookName}?api-version=2024-10-23" --query properties.state
$response = Invoke-AzRestMethod -Path "${accountPath}/runbooks/${runbookName}?api-version=2024-10-23" -Method GET
($response.Content | ConvertFrom-Json).properties.state
```

### 3.7 Schedules: PUT and GET

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Define daily nightly and optional daily backstop start times. A schedule alone does not identify a runbook; a jobSchedule link does that. UAT creates an opt-in `OneTime` schedule. |
| HTTP | `PUT` / `GET <account-base>/schedules/<schedule-name>?api-version=2024-10-23` |
| RBAC | PUT: `Microsoft.Automation/automationAccounts/schedules/write`; GET: `Microsoft.Automation/automationAccounts/schedules/read`. UAT cleanup DELETE uses `schedules/delete`. |
| Request | `name`, `properties.frequency`, `interval`, `startTime`, `timeZone`; GET has no body. `startTime` is a future ISO 8601 timestamp with offset. |
| Fields read | `properties.startTime`, `timeZone`, `frequency`, `interval`, `isEnabled`, `nextRun`; UAT checks the effective returned `startTime` is still future before linking. |
| Success/async | PUT `201` create / `200` update; GET `200`. These return schedule JSON, not a `202` LRO. |
| Common errors | `400` invalid time/time zone/recurrence, start time too close or in the past, `403`, `404`, conflict updating an existing schedule, `429`/`5xx`. |

Request body (`<schedule-request>.json`):

```json
{
  "name": "<schedule-name>",
  "properties": {
    "description": "Nightly capacity auto-pause",
    "frequency": "Day",
    "interval": 1,
    "startTime": "2030-01-16T22:00:00-06:00",
    "timeZone": "America/Chicago"
  }
}
```

Replace the illustrative date with a sufficiently future date and an offset appropriate to that date and time zone. **Observed live:** the IANA name `America/Chicago` was accepted. The generic REST schema declares a time-zone string; it does not establish an exhaustive IANA compatibility list. Confirm local wall-clock recurrence across daylight-saving transitions on deployment. `nextRun` is the computed next occurrence, not a guarantee of exact execution start.

```powershell
az rest --method put --url "$arm${accountPath}/schedules/${scheduleName}?api-version=2024-10-23" --body '@<schedule-request>.json'
Invoke-AzRestMethod -Path "${accountPath}/schedules/${scheduleName}?api-version=2024-10-23" -Method PUT -Payload (Get-Content -LiteralPath '<schedule-request>.json' -Raw)

az rest --method get --url "$arm${accountPath}/schedules/${scheduleName}?api-version=2024-10-23"
Invoke-AzRestMethod -Path "${accountPath}/schedules/${scheduleName}?api-version=2024-10-23" -Method GET
```

### 3.8 jobSchedules: list, create link, delete link

| Operation | HTTP | RBAC | Request / response used | Success |
| --- | --- | --- | --- | --- |
| List | `GET <account-base>/jobSchedules?api-version=2024-10-23` | `Microsoft.Automation/automationAccounts/jobSchedules/read` | No body. Read `value[].properties.jobScheduleId`, `runbook.name`, `schedule.name`; follow `nextLink`. | `200` JSON. |
| Create link | `PUT <account-base>/jobSchedules/<new-link-guid>?api-version=2024-10-23` | `Microsoft.Automation/automationAccounts/jobSchedules/write` | `properties.schedule.name`, `runbook.name`, string-valued `parameters`; response exposes `properties.jobScheduleId`. | `201` JSON; not an execution LRO. |
| Delete link | `DELETE <account-base>/jobSchedules/<existing-link-guid>?api-version=2024-10-23` | `Microsoft.Automation/automationAccounts/jobSchedules/delete` | No body; deployment ignores the response body. Does not delete the runbook or schedule. | Documented `200`. |

Purpose: associate the published runbook and current parameters with each nightly/backstop schedule. Common errors: `400` invalid association/parameters, `403`, `404` missing schedule/runbook, duplicate-link-ID conflict, `429`/`5xx`.

**Observed live:** reusing a just-deleted link ID failed with **`A jobSchedule with same id already exists`**. The service retains the ID for an unspecified period. Always generate a **new GUID** for a replacement link, rather than deriving a stable ID or retrying the deleted one. `Set-JobScheduleLinks` deletes matching links and creates new ones; it does not update links in place. It reads **`properties.jobScheduleId`**, not top-level `name` (with `name` only as a defensive fallback).

Request body (`<job-schedule-request>.json`):

```json
{
  "properties": {
    "schedule": { "name": "<schedule-name>" },
    "runbook": { "name": "Invoke-FabricCapacityAutoPause" },
    "parameters": {
      "SubscriptionIds": "<subscription-id>",
      "UserAssignedIdentityClientId": "<managed-identity-client-id>",
      "ExcludeTagName": "autopause",
      "ExcludeTagValue": "skip",
      "DryRun": "true"
    }
  }
}
```

The deploy script sends all parameters as strings, omits empty scope filters, and always sends exclusion name/value. Additional filters such as `ResourceGroupName`, `CapacityName`, or `CapacityResourceId` are optional. Omitting all scope filters leaves discovery bounded by the managed identity's actual read grants.

```powershell
az rest --method get --url "$arm${accountPath}/jobSchedules?api-version=2024-10-23"
Invoke-AzRestMethod -Path "${accountPath}/jobSchedules?api-version=2024-10-23" -Method GET

# Choose ONE creation client, not both, for a particular link.
$linkId = [guid]::NewGuid().ToString()
az rest --method put --url "$arm${accountPath}/jobSchedules/${linkId}?api-version=2024-10-23" --body '@<job-schedule-request>.json'
Invoke-AzRestMethod -Path "${accountPath}/jobSchedules/${linkId}?api-version=2024-10-23" -Method PUT -Payload (Get-Content -LiteralPath '<job-schedule-request>.json' -Raw)

$existingLinkId = '<existing-link-guid>'
az rest --method delete --url "$arm${accountPath}/jobSchedules/${existingLinkId}?api-version=2024-10-23"
Invoke-AzRestMethod -Path "${accountPath}/jobSchedules/${existingLinkId}?api-version=2024-10-23" -Method DELETE
```

### 3.9 Runtime environments: PowerShell 7.4 and Az

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Supply the PowerShell runtime and Az commands used by the runbook. Bicep creates the environment and associates the runbook with it. |
| HTTP | `PUT <account-base>/runtimeEnvironments/<runtime-environment-name>?api-version=2024-10-23` |
| RBAC | Resource-type write action `Microsoft.Automation/automationAccounts/runtimeEnvironments/write` for the deployer; the public permissions catalog checked did not enumerate this newer action separately. |
| Request | `location`, `properties.runtime.language = "PowerShell"`, `version = "7.4"`, `defaultPackages = { "Az": "12.3.0" }`; tags/description optional. |
| Fields read | No runtime-environment response fields are read by the runbook/deploy script. Bicep uses the environment name to set runbook `properties.runtimeEnvironment`. |
| Status/async | The versioned Learn template schema and runtime-management guide verify the request shape, but do not specify this PUT's complete response/status-code contract. Do not assume `202`; inspect the actual status and follow LRO headers if supplied. |
| Common errors | `400` unsupported runtime/package version, `403`, `404` missing account, provisioning/package installation failures, `429`/`5xx`. A language version alone does not provide Az.Accounts commands. |

Request body (`<runtime-request>.json`):

```json
{
  "location": "<location>",
  "properties": {
    "runtime": {
      "language": "PowerShell",
      "version": "7.4"
    },
    "defaultPackages": {
      "Az": "12.3.0"
    }
  }
}
```

```powershell
az rest --method put --url "$arm${accountPath}/runtimeEnvironments/<runtime-environment-name>?api-version=2024-10-23" --body '@<runtime-request>.json'
Invoke-AzRestMethod -Path "${accountPath}/runtimeEnvironments/<runtime-environment-name>?api-version=2024-10-23" -Method PUT -Payload (Get-Content -LiteralPath '<runtime-request>.json' -Raw)
```

**Observed live before the dependency guard:** without Az, a job could finish `Completed` after only non-terminating command-not-found errors, having paused nothing. The **current** runbook explicitly checks `Disable-AzContextAutosave`, `Connect-AzAccount`, and `Invoke-AzRestMethod`, and throws if they are missing. Its execution function also sets `$ErrorActionPreference = 'Stop'`. The infrastructure explicitly installs Az 12.3.0 by default; the deployment parameter can select another version.

## 4. Azure Monitor Activity Log

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Audit who requested suspend/resume and when; UAT checks control-plane evidence. It is not the pause-completion mechanism. |
| HTTP | `GET https://management.azure.com/subscriptions/<subscription-id>/providers/Microsoft.Insights/eventtypes/management/values?api-version=2015-04-01&$filter=<url-encoded-filter>` |
| RBAC | `Microsoft.Insights/eventtypes/values/read` at an appropriate scope; no Activity Log read action is included in the runbook's custom role. |
| Request body | None. The `$filter` contains an event timestamp range and `resourceUri eq '<capacity-resource-id>'`. |
| Fields read | `value[].operationName.value`, `eventTimestamp`, `caller`, `claims`, `status.value`, `resourceId`; collection `nextLink` for REST paging. Claims can contain the object-identifier claim, `oid`, or `appid`. |
| Operation names | `Microsoft.Fabric/capacities/suspend/action` and `Microsoft.Fabric/capacities/resume/action`. Compare stable `operationName.value`, not localized display text. |
| Caller | **Observed live:** a managed identity appeared as its principal/object-ID GUID in `caller`. This is not its client ID or resource ID. Check identity claims as well; `caller` representation varies by identity. |
| Success/async | `200` JSON; follow `nextLink`. No LRO. Audit ingestion is asynchronous and separate from operation completion. |
| Common errors | `400` unsupported/unencoded filter, `403`, `429`/`5xx`; empty results due to delay or wrong time range. |

CLI example requested for the last hour:

```powershell
az monitor activity-log list --resource-id $capacityPath --offset 1h
```

REST equivalents, using a dynamically generated UTC range and properly encoded filter:

```powershell
$from = [DateTimeOffset]::UtcNow.AddHours(-1).ToString('yyyy-MM-ddTHH:mm:ssZ')
$to = [DateTimeOffset]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
$filter = "eventTimestamp ge '$from' and eventTimestamp le '$to' and resourceUri eq '$capacityPath'"
$encodedFilter = [uri]::EscapeDataString($filter)
$activityPath = "${subscriptionPath}/providers/Microsoft.Insights/eventtypes/management/values?api-version=2015-04-01&`$filter=$encodedFilter"

az rest --method get --url "$arm$activityPath"
Invoke-AzRestMethod -Path $activityPath -Method GET
```

Allow **a few minutes** for propagation; Learn describes typical availability in **3–20 minutes**. An immediate empty log does not prove no pause occurred. UAT queries a two-hour lookback and filters by its scenario timestamp/caller; do not confuse a `Started` event with a successful terminal operation.

## 5. Azure RBAC: custom role and assignments

Both resources use **`api-version=2022-04-01`**. `infra\modules\rbac.bicep` creates the custom role definition at subscription scope and, by default, assigns it at that subscription. Additional assignable scopes do not themselves grant access.

### 5.1 Role definitions

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Define the managed identity's permitted Fabric management operations. |
| HTTP | `PUT` / `GET https://management.azure.com/subscriptions/<subscription-id>/providers/Microsoft.Authorization/roleDefinitions/<role-definition-guid>?api-version=2022-04-01` |
| RBAC | PUT: `Microsoft.Authorization/roleDefinitions/write`, including the required rights over assignable scopes; GET: `Microsoft.Authorization/roleDefinitions/read`. Contributor alone does not grant role-definition/assignment writes. |
| Request | CustomRole properties shown below; the Bicep definition name is a deterministic GUID of subscription, name prefix, and custom-role name. |
| Fields read | Bicep outputs the definition resource ID. UAT resolves `roleName`, `permissions[].actions`, `notActions`; assignment verification also examines scopes/conditions. |
| Success/async | PUT documented `201`; GET `200` JSON. No `202` LRO in the documented contract. |
| Common errors | `403`, invalid assignable scope/action, duplicate role display name, custom-role quota or conflicting definition. Role names must be unique in the tenant. |

Request body (`<role-definition>.json`), matching the default module:

```json
{
  "properties": {
    "roleName": "<custom-role-name>",
    "description": "Read and suspend capacities; no resume or delete",
    "type": "CustomRole",
    "permissions": [
      {
        "actions": [
          "Microsoft.Fabric/capacities/read",
          "Microsoft.Fabric/capacities/suspend/action"
        ],
        "notActions": [],
        "dataActions": [],
        "notDataActions": []
      }
    ],
    "assignableScopes": ["/subscriptions/<subscription-id>"]
  }
}
```

```powershell
$rolePath = "${subscriptionPath}/providers/Microsoft.Authorization/roleDefinitions/<role-definition-guid>"
az rest --method put --url "$arm${rolePath}?api-version=2022-04-01" --body '@<role-definition>.json'
Invoke-AzRestMethod -Path "${rolePath}?api-version=2022-04-01" -Method PUT -Payload (Get-Content -LiteralPath '<role-definition>.json' -Raw)

az rest --method get --url "$arm${rolePath}?api-version=2022-04-01"
Invoke-AzRestMethod -Path "${rolePath}?api-version=2022-04-01" -Method GET
```

`-IncludeWritePermission` adds `Microsoft.Fabric/capacities/write`. It does **not** add resume/delete, but permits scaling and administration changes. The role is not a deny rule: other assignments can still grant broader rights. UAT's role inspection is not an effective-access simulation.

### 5.2 Role assignments

| Item | Contract and project behavior |
| --- | --- |
| Purpose | Bind that custom role to the user-assigned managed identity at the chosen scope. |
| HTTP | `PUT https://management.azure.com<scope>/providers/Microsoft.Authorization/roleAssignments/<assignment-guid>?api-version=2022-04-01`; list: `GET https://management.azure.com<scope>/providers/Microsoft.Authorization/roleAssignments?api-version=2022-04-01` |
| RBAC | PUT: `Microsoft.Authorization/roleAssignments/write` at the assignment scope; list: `Microsoft.Authorization/roleAssignments/read`. |
| Request | `properties.roleDefinitionId`, `principalId` (the identity's **principal/object ID**), and `principalType: "ServicePrincipal"`. A managed identity is a service principal for this purpose. |
| Fields read | Role ID, principal ID, scope, and condition; UAT checks applicable grants and disallowed wildcard/resume/delete actions. |
| Success/async | PUT `201` new / `200` existing, JSON; list `200` with `value[]`/`nextLink`. No execution LRO; access propagation is not instantaneous. |
| Common errors | `403`; `PrincipalNotFound` during directory propagation; `RoleAssignmentExists`; immutable assignment properties; role not assignable at the scope. Specifying `ServicePrincipal` avoids some directory lookup ambiguity. |

| Scope option | `<scope>` value |
| --- | --- |
| Entire subscription: default | `/subscriptions/<subscription-id>` |
| One resource group | `/subscriptions/<subscription-id>/resourceGroups/<resource-group>` |
| One capacity | `/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>` |

Request body (`<role-assignment>.json`):

```json
{
  "properties": {
    "roleDefinitionId": "/subscriptions/<subscription-id>/providers/Microsoft.Authorization/roleDefinitions/<role-definition-guid>",
    "principalId": "<managed-identity-principal-id>",
    "principalType": "ServicePrincipal"
  }
}
```

```powershell
# Select exactly one intended scope.
$scope = '/subscriptions/<subscription-id>/resourceGroups/<resource-group>'
$assignmentPath = "${scope}/providers/Microsoft.Authorization/roleAssignments/<assignment-guid>"
az rest --method put --url "$arm${assignmentPath}?api-version=2022-04-01" --body '@<role-assignment>.json'
Invoke-AzRestMethod -Path "${assignmentPath}?api-version=2022-04-01" -Method PUT -Payload (Get-Content -LiteralPath '<role-assignment>.json' -Raw)

az rest --method get --url "$arm${scope}/providers/Microsoft.Authorization/roleAssignments?api-version=2022-04-01"
Invoke-AzRestMethod -Path "${scope}/providers/Microsoft.Authorization/roleAssignments?api-version=2022-04-01" -Method GET

# Required verification command; inspect inherited/broader grants as well.
az role assignment list --assignee '<principal-id>' --all
```

Use `-SkipSubscriptionRoleAssignment` before creating only a narrower manual assignment. Re-running deployment with that switch does **not** remove an older subscription-wide assignment. RBAC, not a KQL filter, is the security boundary.

## 6. Managed identity authentication: conceptual only

| Item | Behavior |
| --- | --- |
| Purpose | Authenticate the runbook without a stored password, client secret, certificate, or manually maintained token. |
| Runbook entry | `Disable-AzContextAutosave -Scope Process`; then `Connect-AzAccount -Identity`, with `-AccountId <managed-identity-client-id>` when the user-assigned identity is selected. Infrastructure uses a user-assigned identity. |
| Token audience | ARM requests target `https://management.azure.com/`. A Fabric REST check needs a separate `https://api.fabric.microsoft.com` audience. Tokens for one audience are not interchangeable. |
| Identity identifiers | Client ID selects a user-assigned identity for sign-in; principal/object ID is used for RBAC and audit attribution; resource ID identifies the Azure identity resource. |
| HTTP/body/version | Az.Accounts and the Automation host perform token acquisition. There is no application-owned token URL, request body, or pinned token `api-version` in this project. Do not hard-code a VM IMDS endpoint for Automation. |
| RBAC | Token acquisition is not a capacity-management grant. The identity must separately have capacity read/suspend rights. The deployer also needs rights to create/attach the identity. |
| Fields read | Sign-in must return a context; the runbook does not parse, print, or store access-token fields. |
| Status/errors | Host/SDK-managed, not an ARM LRO. Missing Az.Accounts, unavailable/misattached identity, wrong client ID, or no usable context fails sign-in; later `403` errors indicate authorization, not necessarily token acquisition failure. |

No direct token HTTP, `az rest`, or `Invoke-AzRestMethod` example is provided here: token acquisition is intentionally conceptual and delegated to managed-identity authentication.

## 7. CLI and PowerShell equivalents

The project deliberately uses raw ARM requests so the runbook needs **Az.Accounts**, not Az.Fabric or an Azure CLI extension. The following convenience commands are **verified on Learn**, not verified as installed in the Automation runtime. SDK/CLI versions can select different API versions from this reference; use `az rest`/`Invoke-AzRestMethod` above when exact versions matter.

`az fabric capacity` belongs to the **`microsoft-fabric`** Azure CLI extension (Learn requires Azure CLI 2.61.0 or later). Do not substitute `az powerbi embedded-capacity`; that manages a different resource type.

| Operation | Azure CLI equivalent | Az PowerShell equivalent | Verification |
| --- | --- | --- | --- |
| Resource Graph query | `az graph query -q '<KQL>'` (`resource-graph` extension) | ARM POST in section 1 | [CLI verified on Learn](https://learn.microsoft.com/cli/azure/graph#az-graph-query). |
| Get capacity | `az fabric capacity show --resource-group '<resource-group>' --capacity-name '<capacity-name>'` | `Get-AzFabricCapacity -ResourceGroupName '<resource-group>' -CapacityName '<capacity-name>'` | [CLI](https://learn.microsoft.com/cli/azure/fabric/capacity), [Az.Fabric](https://learn.microsoft.com/powershell/module/az.fabric/get-azfabriccapacity): verified on Learn. |
| List subscription / resource group | `az fabric capacity list` / `az fabric capacity list --resource-group '<resource-group>'` | `Get-AzFabricCapacity` / `Get-AzFabricCapacity -ResourceGroupName '<resource-group>'` | Same references: verified on Learn. Set the intended subscription context explicitly. |
| Suspend | `az fabric capacity suspend --resource-group '<resource-group>' --capacity-name '<capacity-name>'` | `Suspend-AzFabricCapacity -ResourceGroupName '<resource-group>' -CapacityName '<capacity-name>'` | [CLI](https://learn.microsoft.com/cli/azure/fabric/capacity), [cmdlet](https://learn.microsoft.com/powershell/module/az.fabric/suspend-azfabriccapacity): verified on Learn. |
| Resume | `az fabric capacity resume --resource-group '<resource-group>' --capacity-name '<capacity-name>'` | `Resume-AzFabricCapacity -ResourceGroupName '<resource-group>' -CapacityName '<capacity-name>'` | [CLI](https://learn.microsoft.com/cli/azure/fabric/capacity), [cmdlet](https://learn.microsoft.com/powershell/module/az.fabric/resume-azfabriccapacity): verified on Learn. Not scheduled by this project. |
| Scale / PATCH | `az fabric capacity update --resource-group '<resource-group>' --capacity-name '<capacity-name>' --sku '{name:F16,tier:Fabric}'` | `Update-AzFabricCapacity -ResourceGroupName '<resource-group>' -CapacityName '<capacity-name>' -SkuName F16` | [CLI](https://learn.microsoft.com/cli/azure/fabric/capacity), [cmdlet](https://learn.microsoft.com/powershell/module/az.fabric/update-azfabriccapacity): verified on Learn. No fictitious `/scale` action or `-SkuTier` parameter. |
| PUT full capacity / DELETE | Section 2.5 / `az fabric capacity delete --resource-group '<resource-group>' --capacity-name '<capacity-name>'` | Section 2.5 / `Remove-AzFabricCapacity -ResourceGroupName '<resource-group>' -CapacityName '<capacity-name>'` | [CLI](https://learn.microsoft.com/cli/azure/fabric/capacity), [cmdlet](https://learn.microsoft.com/powershell/module/az.fabric/remove-azfabriccapacity): verified on Learn. Delete is never used by the project. |
| Fabric REST capacity list | Section 2.8 `az rest`, Fabric audience | Section 2.8 non-ARM `-Uri` form | [Fabric list API](https://learn.microsoft.com/rest/api/fabric/core/capacities/list-capacities), [Az REST audience selection](https://learn.microsoft.com/powershell/module/az.accounts/invoke-azrestmethod): verified on Learn. |
| Create Automation job | Section 3.1 `az rest` | `Start-AzAutomationRunbook -ResourceGroupName '<automation-resource-group>' -AutomationAccountName '<account>' -Name Invoke-FabricCapacityAutoPause -Parameters @{ DryRun = 'true' }` | [Cmdlet verified on Learn](https://learn.microsoft.com/powershell/module/az.automation/start-azautomationrunbook). Supply identity/scope parameters when required. |
| Get job / list streams / stream detail | Sections 3.2–3.3 `az rest` | Same `Invoke-AzRestMethod -Path` forms | [Job](https://learn.microsoft.com/rest/api/automation/job/get?view=rest-automation-2024-10-23), [streams](https://learn.microsoft.com/rest/api/automation/job-stream/list-by-job?view=rest-automation-2024-10-23): verified on Learn. |
| Read job output records | Section 3.3 streams or section 3.4 raw text | `Get-AzAutomationJobOutput -ResourceGroupName '<automation-resource-group>' -AutomationAccountName '<account>' -Id '<job-guid>' -Stream Any` | [Cmdlet verified on Learn](https://learn.microsoft.com/powershell/module/az.automation/get-azautomationjoboutput). Returns stream records; do not confuse this with raw REST `/output` text. |
| Upload draft / publish / GET runbook | Sections 3.5–3.6 | Sections 3.5–3.6; use CLI for an explicit upload `text/plain` header | [Draft](https://learn.microsoft.com/rest/api/automation/runbook-draft/replace-content?view=rest-automation-2024-10-23), [publish](https://learn.microsoft.com/rest/api/automation/runbook/publish?view=rest-automation-2024-10-23): verified on Learn; Az REST header limitation noted above. |
| Create daily schedule | Section 3.7 `az rest` | `New-AzAutomationSchedule -ResourceGroupName '<automation-resource-group>' -AutomationAccountName '<account>' -Name '<schedule-name>' -StartTime '<future-ISO-8601-start-with-offset>' -DayInterval 1 -TimeZone 'America/Chicago'` | [Cmdlet verified on Learn](https://learn.microsoft.com/powershell/module/az.automation/new-azautomationschedule); specific IANA acceptance is a prior live observation. |
| GET schedule | Section 3.7 `az rest` | Section 3.7 `Invoke-AzRestMethod -Path` | [GET schedule verified on Learn](https://learn.microsoft.com/rest/api/automation/schedule/get?view=rest-automation-2024-10-23). |
| Link schedule | Section 3.8 `az rest` | `Register-AzAutomationScheduledRunbook -ResourceGroupName '<automation-resource-group>' -AutomationAccountName '<account>' -RunbookName Invoke-FabricCapacityAutoPause -ScheduleName '<schedule-name>' -Parameters @{ DryRun = 'true' }` | [Cmdlet verified on Learn](https://learn.microsoft.com/powershell/module/az.automation/register-azautomationscheduledrunbook). REST provides explicit fresh GUID control. |
| List/delete jobSchedule links | Section 3.8 `az rest` | Section 3.8 `Invoke-AzRestMethod -Path` | [List](https://learn.microsoft.com/rest/api/automation/job-schedule/list-by-automation-account?view=rest-automation-2024-10-23), [delete](https://learn.microsoft.com/rest/api/automation/job-schedule/delete?view=rest-automation-2024-10-23): verified on Learn. |
| PUT runtime environment | Section 3.9 `az rest` | Section 3.9 `Invoke-AzRestMethod -Path` | [Runtime guide](https://learn.microsoft.com/azure/automation/manage-runtime-environment): request verified on Learn; response-code contract not established there. |
| Read Activity Log | `az monitor activity-log list --resource-id '<capacity-resource-id>' --offset 1h` | Section 4 `Invoke-AzRestMethod -Path` | [CLI](https://learn.microsoft.com/cli/azure/monitor/activity-log#az-monitor-activity-log-list), [REST](https://learn.microsoft.com/rest/api/monitor/activity-logs/list?view=rest-monitor-2015-04-01): verified on Learn. |
| Role definition/assignment PUT or GET | Section 5 `az rest` | Section 5 `Invoke-AzRestMethod -Path` | [Role definitions](https://learn.microsoft.com/rest/api/authorization/role-definitions/create-or-update?view=rest-authorization-2022-04-01), [assignments](https://learn.microsoft.com/rest/api/authorization/role-assignments/create?view=rest-authorization-2022-04-01): verified on Learn. |
| Verify role assignments | `az role assignment list --assignee '<principal-id>' --all` | Section 5.2 scope-list REST form | [CLI verified on Learn](https://learn.microsoft.com/cli/azure/role/assignment#az-role-assignment-list). |

## 8. Limits, throttling, and scheduling expectations

| Limit/behavior | Documented guidance | What this project does |
| --- | --- | --- |
| ARM request limits | Regional token buckets apply per principal/subscription and also at tenant scope, with additional aggregate/provider limits. Learn's baseline table lists reads: bucket 250/refill 25 per second; writes and deletes: bucket 200/refill 10 per second. These are not guaranteed Fabric throughput rates. | Sequential submission and state GETs; handles returned `429` and `500–599` through `Invoke-Arm`. |
| `Retry-After` | `429` responses say how long to wait. Calls sent too early can be throttled again. Honor the full server delay in manual clients. | Four total attempts by default. Delay is `min(120, max(min(60, 5 * 2^(attempt-1)), RetryAfterSeconds))`; ordinary retry delays are 5, 10, 20 seconds. |
| Retry implementation boundary | Response-header and exception handling depend on the client. | Reads positive integer delta-seconds only, not HTTP-date `Retry-After`. Ignores that header on successful `202` state polling. A delay over 120 seconds is capped, so it can retry earlier than the service requested. Exceptions thrown by `Invoke-AzRestMethod` are not retried inside `Invoke-Arm`; callers handle them as errors or polling warnings. |
| Resource Graph | Per-caller quota is dynamic; Learn illustrates 15 queries per 5-second window, not a universal guarantee. Headers include `x-ms-user-quota-remaining` and `x-ms-user-quota-resets-after`. `$top` maximum is 1,000. | Uses 1,000-row object-array pages and `$skipToken`. Uses ARM-style transient retry, but does not proactively consume ARG quota/reset headers. |
| ARG scope/access | Only readable resources are returned; tenant/management-group query subscription limits and partial-scope behavior also apply. | Does not set `allowPartialScopes`; do not treat an empty/narrow result as proof that no capacity exists outside the caller's visibility. |
| Automation cloud fair share | Jobs running longer than three hours can be stopped/unloaded; ordinary PowerShell jobs do not automatically resume from checkpoints. Hybrid-worker rules differ. | Uses one shared 15-minute default pause-verification deadline, configurable up to 150 minutes, instead of a full timeout per capacity. Total execution must still leave time for discovery, calls, and retries. |
| Schedule recurrence | Minimum recurrence interval for one Automation schedule is **one hour**. | Daily nightly schedule, plus an optional second daily backstop (default offset 60 minutes). These are two schedules, not a sub-hour recurrence. |
| Scheduled start SLA | Learn states **99.9% of runbooks start within 30 minutes** of planned start. This is a start-time SLA, not a completion or exact-minute guarantee. | Choose a shutdown window that tolerates delayed dispatch. A scheduled start does not prove capacity suspension completed. |
| Activity Log | Typical availability is 3–20 minutes after the event. | Audit after propagation; capacity GET is the operational completion test. |
| Job output | Stream records can appear after job status becomes terminal. | UAT polls for expected output for up to 60 seconds, and separately reads the job exception. |

## 9. Which calls need which permission

`Microsoft.Automation/automationAccounts/` is abbreviated below as **`AA/`** only to keep the table readable. Expand it literally when creating a role. Default means the standard deployment plus its dry-run nightly schedule; **gated** means enforcement must be explicitly enabled.

| Operation | HTTP | RBAC action | Identity | Enabled by default? |
| --- | --- | --- | --- | --- |
| Discover readable capacities | POST Resource Graph | Resource access: `Microsoft.Fabric/capacities/read`; query catalog operation: `Microsoft.ResourceGraph/resources/read` | Managed identity | Yes; resource read is in the custom role. |
| Read capacity / poll pause | GET capacity | `Microsoft.Fabric/capacities/read` | Managed identity | Yes. |
| List capacities directly | GET capacity collection | `Microsoft.Fabric/capacities/read` | Deployer / operator | No; runbook uses ARG. |
| Suspend capacity | POST `/suspend` | `Microsoft.Fabric/capacities/suspend/action` | Managed identity | Permission yes; call gated by `DryRun = 'false'`. |
| Resume capacity | POST `/resume` | `Microsoft.Fabric/capacities/resume/action` | Human resumer; separate UAT operator | No; never granted to runbook identity by this role. |
| Scale / edit tags or admins | PATCH / PUT capacity | `Microsoft.Fabric/capacities/write` | Human operator / deployer for UAT tag changes | No; optional `-IncludeWritePermission`, but no scaling logic. |
| Delete capacity | DELETE capacity | `Microsoft.Fabric/capacities/delete` | Separately authorized human | Never. |
| Fabric REST visibility | GET `/v1/capacities` | Not an ARM RBAC action; Fabric access and appropriate token/scopes | Human / authorized UAT caller | No; optional UAT read. |
| Create Automation job | PUT `/jobs/<guid>` | `AA/jobs/write` | Deployer / UAT operator | Manual/UAT only; schedule service dispatches nightly. |
| Read job status/exception | GET `/jobs/<guid>` | `AA/jobs/read` | Deployer / UAT operator | Diagnostics/UAT; not called by nightly runbook. |
| Read stream list/detail | GET `/jobs/<guid>/streams[/<id>]` | `AA/jobs/streams/read` | Deployer / UAT operator | Diagnostics/UAT. |
| Read raw output | GET `/jobs/<guid>/output` | `AA/jobs/output/read` | Deployer / operator | Manual diagnostics. |
| Upload draft source | PUT `/runbooks/<name>/draft/content` | `AA/runbooks/draft/content/write` | Deployer | Yes, during deployment. |
| Publish runbook | POST `/runbooks/<name>/publish` | `AA/runbooks/publish/action` | Deployer | Yes, during deployment. |
| Verify published state | GET `/runbooks/<name>` | `AA/runbooks/read` | Deployer | Yes, during deployment. |
| Create/read daily schedule | PUT / GET `/schedules/<name>` | `AA/schedules/write` / `AA/schedules/read` | Deployer | Yes; optional backstop. |
| Delete temporary UAT schedule | DELETE `/schedules/<name>` | `AA/schedules/delete` | UAT operator | No; opt-in UAT cleanup. |
| List/create/delete schedule links | GET / PUT / DELETE `/jobSchedules[/<guid>]` | `AA/jobSchedules/read`, `write`, `delete` respectively | Deployer | Yes; replaces matching links with fresh GUIDs. |
| Create runtime environment | PUT `/runtimeEnvironments/<name>` | `AA/runtimeEnvironments/write` (catalog verification caveat in section 3.9) | Deployer | Yes, through Bicep. |
| Read audit trail | GET Activity Log | `Microsoft.Insights/eventtypes/values/read` | Deployer / UAT operator / human resumer | No runbook grant; diagnostics only. |
| Create/read custom role | PUT / GET roleDefinition | `Microsoft.Authorization/roleDefinitions/write` / `read` | Deployer | Definition created by default. |
| Create/read assignment | PUT / GET roleAssignment(s) | `Microsoft.Authorization/roleAssignments/write` / `read` | Deployer | Subscription assignment yes unless explicitly skipped. |
| Managed-identity sign-in | Host/SDK token acquisition | No capacity permission conferred by sign-in | Managed identity | Yes; secretless. |

The deployment also needs the ordinary create/update permissions for resource groups, nested deployments, the Automation account/runbook shell, and the user-assigned identity; optional alerting additionally needs action-group/metric-alert rights. Those provisioning resources do not expand the nightly identity's capacity permissions.

## Sources

Operation-specific links are provided in the equivalents table. Principal Learn references:

- [Resource Graph REST, 2022-10-01](https://learn.microsoft.com/rest/api/azureresourcegraph/resourcegraph/resources/resources?view=rest-azureresourcegraph-resourcegraph-2022-10-01), [read visibility](https://learn.microsoft.com/azure/governance/resource-graph/overview#permissions-in-azure-resource-graph), and [throttling](https://learn.microsoft.com/azure/governance/resource-graph/concepts/guidance-for-throttled-requests).
- [Fabric capacity GET and state definitions](https://learn.microsoft.com/rest/api/microsoftfabric/fabric-capacities/get?view=rest-microsoftfabric-2023-11-01), [suspend](https://learn.microsoft.com/rest/api/microsoftfabric/fabric-capacities/suspend?view=rest-microsoftfabric-2023-11-01), and [partial update](https://learn.microsoft.com/rest/api/microsoftfabric/fabric-capacities/update?view=rest-microsoftfabric-2023-11-01).
- [Fabric REST list capacities](https://learn.microsoft.com/rest/api/fabric/core/capacities/list-capacities).
- [Automation job create](https://learn.microsoft.com/rest/api/automation/job/create?view=rest-automation-2024-10-23), [job GET](https://learn.microsoft.com/rest/api/automation/job/get?view=rest-automation-2024-10-23), and [job output](https://learn.microsoft.com/rest/api/automation/job/get-output?view=rest-automation-2024-10-23).
- [Automation runtime management](https://learn.microsoft.com/azure/automation/manage-runtime-environment) and [versioned runtime schema](https://learn.microsoft.com/azure/templates/microsoft.automation/2024-10-23/automationaccounts/runtimeenvironments).
- [Schedules](https://learn.microsoft.com/azure/automation/shared-resources/schedules), [30-minute start SLA](https://learn.microsoft.com/troubleshoot/azure/automation/runbooks/job-not-start-as-expected), and [cloud execution/fair share](https://learn.microsoft.com/azure/automation/automation-runbook-execution).
- [ARM asynchronous operations](https://learn.microsoft.com/azure/azure-resource-manager/management/async-operations) and [ARM limits/throttling](https://learn.microsoft.com/azure/azure-resource-manager/management/request-limits-and-throttling).
- [Activity Log REST](https://learn.microsoft.com/rest/api/monitor/activity-logs/list?view=rest-monitor-2015-04-01) and [ingestion delay](https://learn.microsoft.com/azure/azure-monitor/platform/activity-log).
- [RBAC role-definition contract](https://learn.microsoft.com/rest/api/authorization/role-definitions/create-or-update?view=rest-authorization-2022-04-01), [assignment contract](https://learn.microsoft.com/rest/api/authorization/role-assignments/create?view=rest-authorization-2022-04-01), and [Fabric actions](https://learn.microsoft.com/azure/role-based-access-control/permissions/analytics#microsoftfabric).
- [Automation/Resource Graph actions](https://learn.microsoft.com/azure/role-based-access-control/permissions/management-and-governance), [Monitor actions](https://learn.microsoft.com/azure/role-based-access-control/permissions/monitor#microsoftinsights), and [user-assigned identity authentication](https://learn.microsoft.com/azure/automation/add-user-assigned-identity).

### Verification boundaries

- No Azure/Fabric live request was made for this document. Prior live observations about `Inactive`, `exception`, IANA time zones, link-ID reservation, and missing Az are labeled rather than represented as new tests.
- The exact duration of a deleted jobSchedule ID reservation is not documented here; fresh GUIDs avoid relying on it.
- Runtime-environment PUT response codes and its separately enumerated RBAC action could not be confirmed from a dedicated public Learn operation reference. Request schema, API version, PowerShell 7.4, and Az 12.3.0 were confirmed in the Learn template/runtime guide.
- Strict `text/plain` upload through `Invoke-AzRestMethod` could not be verified because its documented parameter surface has no content-type/header override. The deploy script's explicit-header `az rest` upload is the recommended example.
- Convenience command names and syntax are documented on Learn; availability in a particular installed CLI/Az version and daylight-saving recurrence behavior require deployment-time checks.
