<#
.SYNOPSIS
    Pauses (suspends) every Active Microsoft Fabric capacity the running identity can see.

.DESCRIPTION
    Intended to run as an Azure Automation runbook (PowerShell 7.4 runtime environment) on a nightly
    schedule, signed in with a managed identity. It only uses the Azure control plane:

      1. Azure Resource Graph  - discover Microsoft.Fabric/capacities (nothing is hard-coded)
      2. ARM GET               - read the authoritative state of each capacity
      3. ARM POST /suspend     - pause capacities that are Active

    Anything the identity cannot read is invisible to discovery, so the Azure RBAC role assignments
    on the identity are the real scope of this runbook. The parameters below only narrow it further.

    Safe by default: DryRun defaults to true and only logs what it would do.

.PARAMETER SubscriptionIds
    Comma-separated subscription GUIDs to search. Omit to search everything the identity can read.
    Mutually exclusive with ManagementGroupId.

.PARAMETER ManagementGroupId
    Management group ID (not display name) to search. Mutually exclusive with SubscriptionIds.

.PARAMETER ResourceGroupName
    Only consider capacities in this resource group.

.PARAMETER CapacityName
    Only consider the capacity with this name (use for single-capacity mode).

.PARAMETER CapacityResourceId
    Only consider the capacity with this full ARM resource ID.

.PARAMETER ExcludeTagName
    Capacities carrying this tag are never paused. Default: autopause.

.PARAMETER ExcludeTagValue
    Tag value that excludes a capacity. Default: skip. Set to empty to exclude on tag presence alone.

.PARAMETER UserAssignedIdentityClientId
    Client ID of a user-assigned managed identity. Omit to use the system-assigned identity.

.PARAMETER DryRun
    'true' (default) reports what would be paused and changes nothing; 'false' pauses for real.
    Accepted as a string because Azure Automation passes schedule parameter values as strings. Any
    value other than true/false/1/0/yes/no fails the job, so a typo can never cause a pause.

.PARAMETER PauseTimeoutMinutes
    How long to wait for each capacity to reach Paused before reporting a failure.

.PARAMETER PollSeconds
    Seconds between state checks while waiting for a pause to complete.

.NOTES
    The runbook fails (throws) if any capacity could not be read or paused, so Azure Automation
    reports the job as Failed and a job-status alert can fire.
#>
[CmdletBinding()]
param(
    # Extension examples are at the end: EXTENDING (commented examples - NOT ENABLED).
    # See docs\EXTENDING.md before adapting parameters, helpers, permissions, or schedules.
    [string] $SubscriptionIds,
    [string] $ManagementGroupId,
    [string] $ResourceGroupName,
    [string] $CapacityName,
    [string] $CapacityResourceId,
    [string] $ExcludeTagName = 'autopause',
    [string] $ExcludeTagValue = 'skip',
    [string] $UserAssignedIdentityClientId,
    [string] $DryRun = 'true',
    [ValidateRange(1, 150)] [int] $PauseTimeoutMinutes = 15,
    [ValidateRange(5, 300)] [int] $PollSeconds = 15
)

$script:FabricApiVersion = '2023-11-01'
$script:GraphApiVersion = '2022-10-01'

# Anchored with \A and \z (a trailing newline can slip past '$'), ASCII classes only.
$script:GuidPattern = '\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\z'
$script:NamePattern = '\A[A-Za-z0-9_\-\.\(\)]{1,90}\z'
$script:CapacityNamePattern = '\A[A-Za-z][A-Za-z0-9]{2,62}\z'
$script:CapacityIdPattern = '\A/subscriptions/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/resourceGroups/[A-Za-z0-9_\-\.\(\)]{1,90}/providers/Microsoft\.Fabric/capacities/[A-Za-z][A-Za-z0-9]{2,62}\z'

function Test-SafeIdentifier {
    param([string] $Value, [string] $Pattern, [string] $Label)
    if ($Value -notmatch $Pattern) {
        throw "Invalid $Label '$Value'."
    }
}

function ConvertTo-StrictBool {
    <# Fail-safe boolean parser: ambiguous input throws instead of guessing. #>
    param([Parameter(Mandatory)] $Value, [string] $Name = 'value')
    if ($Value -is [bool]) { return $Value }
    switch -Regex ([string]$Value) {
        '\A\s*(true|1|yes|\$true)\s*\z'  { return $true }
        '\A\s*(false|0|no|\$false)\s*\z' { return $false }
        default { throw "Invalid $Name '$Value': expected true or false." }
    }
}

function ConvertTo-TagTable {
    param($Tags)
    $table = @{}
    if ($null -eq $Tags) { return $table }
    if ($Tags -is [System.Collections.IDictionary]) {
        foreach ($key in $Tags.Keys) { $table[[string]$key] = $Tags[$key] }
    }
    else {
        foreach ($prop in $Tags.PSObject.Properties) { $table[$prop.Name] = $prop.Value }
    }
    return $table
}

function Get-AutoPauseDecision {
    <# Pure decision function: capacity state + tags -> what to do. No I/O. #>
    param(
        [string] $State,
        $Tags,
        [string] $ExcludeTagName,
        [string] $ExcludeTagValue
    )

    $tagTable = ConvertTo-TagTable $Tags
    if ($ExcludeTagName -and $tagTable.ContainsKey($ExcludeTagName)) {
        if ([string]::IsNullOrEmpty($ExcludeTagValue) -or ([string]$tagTable[$ExcludeTagName]) -ieq $ExcludeTagValue) {
            return [pscustomobject]@{ Action = 'Excluded'; Reason = "Tag '$ExcludeTagName' excludes this capacity." }
        }
    }

    switch -Regex ($State) {
        '^Active$' {
            return [pscustomobject]@{ Action = 'Pause'; Reason = 'Capacity is Active.' }
        }
        '^(Paused|Suspended)$' {
            return [pscustomobject]@{ Action = 'Skip'; Reason = "Already off ($State)." }
        }
        '^(Pausing|Suspending)$' {
            return [pscustomobject]@{ Action = 'Await'; Reason = "Pause already in progress ($State); verifying it completes." }
        }
        '^(Resuming|Scaling|Updating|Preparing|Provisioning)$' {
            return [pscustomobject]@{ Action = 'Defer'; Reason = "Transitional state ($State); a later run will retry." }
        }
        default {
            return [pscustomobject]@{ Action = 'Warn'; Reason = "Unexpected state '$State'; no action taken." }
        }
    }
}

function New-GraphRequestBody {
    <# Builds the Resource Graph request, validating every value that is interpolated into KQL. #>
    param(
        [string] $SubscriptionIds,
        [string] $ManagementGroupId,
        [string] $ResourceGroupName,
        [string] $CapacityName,
        [string] $CapacityResourceId
    )

    if ($SubscriptionIds -and $ManagementGroupId) {
        throw 'Specify either SubscriptionIds or ManagementGroupId, not both.'
    }

    $filters = @()
    if ($ResourceGroupName) {
        Test-SafeIdentifier $ResourceGroupName $script:NamePattern 'ResourceGroupName'
        $filters += "| where resourceGroup =~ '$ResourceGroupName'"
    }
    if ($CapacityName) {
        Test-SafeIdentifier $CapacityName $script:CapacityNamePattern 'CapacityName'
        $filters += "| where name =~ '$CapacityName'"
    }
    if ($CapacityResourceId) {
        Test-SafeIdentifier $CapacityResourceId $script:CapacityIdPattern 'CapacityResourceId'
        $filters += "| where id =~ '$CapacityResourceId'"
    }

    $query = @(
        'resources'
        "| where type =~ 'microsoft.fabric/capacities'"
        $filters
        '| project id, name, subscriptionId, resourceGroup, location, sku = tostring(sku.name), state = tostring(properties.state), tags'
    ) -join "`n"

    $body = [ordered]@{ query = $query }

    if ($SubscriptionIds) {
        $subs = @($SubscriptionIds -split '[,;\s]+' | Where-Object { $_ })
        foreach ($s in $subs) { Test-SafeIdentifier $s $script:GuidPattern 'subscription ID' }
        $body['subscriptions'] = $subs
    }
    elseif ($ManagementGroupId) {
        Test-SafeIdentifier $ManagementGroupId $script:NamePattern 'ManagementGroupId'
        $body['managementGroups'] = @($ManagementGroupId)
    }

    return $body
}

function Get-RetryAfterSeconds {
    <# Reads a Retry-After header (delta-seconds) from an Invoke-AzRestMethod response; 0 when absent. #>
    param($Response)
    try {
        $headers = $Response.Headers
        if ($null -eq $headers) { return 0 }
        $raw = $null
        if ($headers -is [System.Collections.IDictionary]) {
            foreach ($key in $headers.Keys) {
                if ([string]$key -ieq 'Retry-After') { $raw = @($headers[$key])[0]; break }
            }
        }
        elseif ($headers.PSObject.Methods['GetValues']) {
            $raw = @($headers.GetValues('Retry-After'))[0]
        }
        $seconds = 0
        if ($raw -and [int]::TryParse([string]$raw, [ref]$seconds) -and $seconds -gt 0) { return $seconds }
    }
    catch { }
    return 0
}

function Invoke-Arm {
    <# Thin wrapper over Invoke-AzRestMethod with retry on throttling and transient server errors. #>
    param(
        [Parameter(Mandatory)] [string] $Method,
        [Parameter(Mandatory)] [string] $Path,
        [string] $Payload,
        [int] $MaxAttempts = 4
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        $request = @{ Method = $Method; Path = $Path }
        if ($Payload) { $request['Payload'] = $Payload }
        $response = Invoke-AzRestMethod @request -ErrorAction Stop

        $code = [int]$response.StatusCode
        $transient = ($code -eq 429) -or ($code -ge 500 -and $code -le 599)
        if ($transient -and $attempt -lt $MaxAttempts) {
            # Requests sent before Retry-After expires are not processed, so wait at least that long.
            $backoff = [Math]::Min(60, 5 * [Math]::Pow(2, $attempt - 1))
            $delay = [Math]::Min(120, [Math]::Max($backoff, (Get-RetryAfterSeconds $response)))
            Write-Warning "ARM $Method returned $code; retry $attempt/$($MaxAttempts - 1) in $delay s."
            Start-Sleep -Seconds $delay
            continue
        }

        $parsed = $null
        if ($response.Content) {
            try { $parsed = $response.Content | ConvertFrom-Json -ErrorAction Stop } catch { $parsed = $null }
        }
        return [pscustomobject]@{ StatusCode = $code; Body = $parsed; Raw = $response.Content }
    }
}

function Get-ErrorText {
    param($Response)
    if ($Response.Body -and $Response.Body.error) {
        return "$($Response.Body.error.code): $($Response.Body.error.message)"
    }
    return [string]$Response.Raw
}

function Get-FabricCapacityTargets {
    param(
        [string] $SubscriptionIds,
        [string] $ManagementGroupId,
        [string] $ResourceGroupName,
        [string] $CapacityName,
        [string] $CapacityResourceId
    )

    $body = New-GraphRequestBody -SubscriptionIds $SubscriptionIds -ManagementGroupId $ManagementGroupId `
        -ResourceGroupName $ResourceGroupName -CapacityName $CapacityName -CapacityResourceId $CapacityResourceId

    $targets = @()
    $skipToken = $null
    do {
        $options = @{ resultFormat = 'objectArray'; '$top' = 1000 }
        if ($skipToken) { $options['$skipToken'] = $skipToken }
        $body['options'] = $options

        $response = Invoke-Arm -Method POST -Path "/providers/Microsoft.ResourceGraph/resources?api-version=$script:GraphApiVersion" `
            -Payload ($body | ConvertTo-Json -Depth 6 -Compress)
        if ($response.StatusCode -ge 400) {
            throw "Resource Graph query failed ($($response.StatusCode)): $(Get-ErrorText $response)"
        }

        $targets += @($response.Body.data)
        $skipToken = $response.Body.'$skipToken'
    } while ($skipToken)

    return , @($targets | Where-Object { $_ })
}

function Get-UtcNow {
    <# Clock seam so deadline logic can be tested without waiting. #>
    return [datetime]::UtcNow
}

function Get-CapacityPowerState {
    <# Current ARM state of a capacity, or $null if it could not be read this time. #>
    param([Parameter(Mandatory)] [string] $ResourceId)
    try {
        $response = Invoke-Arm -Method GET -Path "${ResourceId}?api-version=$script:FabricApiVersion"
        if ($response.StatusCode -lt 400) { return [string]$response.Body.properties.state }
        Write-Warning "State check returned $($response.StatusCode); will retry."
    }
    catch {
        Write-Warning "State check failed, will retry: $($_.Exception.Message)"
    }
    return $null
}

function Wait-CapacitiesPaused {
    <#
    Polls every pending capacity round-robin against ONE shared deadline, so total wait time is bounded
    (Azure Automation stops jobs after 3 hours, which would end the job as Stopped instead of Failed).
    Each item needs: Row (result row) and Id (ARM resource ID).
    #>
    param(
        [Parameter(Mandatory)] [AllowEmptyCollection()] [object[]] $Pending,
        [int] $TimeoutMinutes = 15,
        [int] $PollSeconds = 15
    )

    $deadline = (Get-UtcNow).AddMinutes($TimeoutMinutes)
    $open = @($Pending)
    $lastState = @{}

    while ($open.Count -gt 0) {
        $stillOpen = @()
        foreach ($item in $open) {
            $state = Get-CapacityPowerState -ResourceId $item.Id
            if ($state) { $lastState[$item.Id] = $state }
            if ($state -match '^(Paused|Suspended)$') {
                $item.Row.Result = 'Paused'
            }
            else {
                $stillOpen += $item
            }
        }
        $open = @($stillOpen)
        if ($open.Count -eq 0 -or (Get-UtcNow) -ge $deadline) { break }
        Start-Sleep -Seconds $PollSeconds
    }

    foreach ($item in $open) {
        $item.Row.Result = 'Error'
        $item.Row.Detail = "Did not reach Paused within $TimeoutMinutes min (last state: $(if ($lastState[$item.Id]) { $lastState[$item.Id] } else { 'unknown' }))."
    }
}

function Connect-AutoPauseIdentity {
    param([string] $ClientId)

    # A missing command is only a non-terminating error by default, which would let the job report
    # success without doing anything. Check up front and fail with a message that says how to fix it.
    foreach ($command in 'Disable-AzContextAutosave', 'Connect-AzAccount', 'Invoke-AzRestMethod') {
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
            throw "Required command '$command' is not available. The Azure Automation runtime environment must include the Az PowerShell package (Az.Accounts)."
        }
    }

    Disable-AzContextAutosave -Scope Process | Out-Null
    $connect = @{ Identity = $true }
    if ($ClientId) { $connect['AccountId'] = $ClientId }
    $connection = Connect-AzAccount @connect -ErrorAction Stop
    if ($null -eq $connection) {
        throw 'Sign-in with the managed identity returned no context.'
    }
}

function Write-Log {
    <# Single logging seam: Write-Output so lines appear in the Automation job output; mockable in tests. #>
    param([string] $Message)
    Write-Output $Message
}

function Invoke-FabricCapacityAutoPause {
    param(
        [string] $SubscriptionIds,
        [string] $ManagementGroupId,
        [string] $ResourceGroupName,
        [string] $CapacityName,
        [string] $CapacityResourceId,
        [string] $ExcludeTagName = 'autopause',
        [string] $ExcludeTagValue = 'skip',
        [string] $UserAssignedIdentityClientId,
        [bool]   $DryRun = $true,
        [ValidateRange(1, 150)] [int] $PauseTimeoutMinutes = 15,
        [ValidateRange(0, 300)] [int] $PollSeconds = 15,
        [switch] $PassThru
    )

    # Any unexpected error must fail the job; otherwise it can finish "Completed" having done nothing.
    $ErrorActionPreference = 'Stop'

    # An empty tag name would silently disable every exclusion, so refuse it.
    if ([string]::IsNullOrWhiteSpace($ExcludeTagName)) {
        throw 'ExcludeTagName must not be empty: the exclusion tag is the per-capacity opt-out.'
    }

    $mode = if ($DryRun) { 'DRY RUN (no changes will be made)' } else { 'ENFORCING' }
    Write-Log "Fabric capacity auto-pause: $mode"

    Connect-AutoPauseIdentity -ClientId $UserAssignedIdentityClientId

    $targets = Get-FabricCapacityTargets -SubscriptionIds $SubscriptionIds -ManagementGroupId $ManagementGroupId `
        -ResourceGroupName $ResourceGroupName -CapacityName $CapacityName -CapacityResourceId $CapacityResourceId
    Write-Log "Discovered $(@($targets).Count) Fabric capacit$(if (@($targets).Count -eq 1) { 'y' } else { 'ies' })."

    if (@($targets).Count -eq 0) {
        # A named target that cannot be found is a misconfiguration (or missing RBAC), not "nothing to do".
        if ($CapacityName -or $CapacityResourceId) {
            throw 'The requested capacity was not found, or the identity cannot read it.'
        }
        Write-Warning 'No Fabric capacities are visible to this identity. If capacities exist, check its role assignment.'
    }

    $results = New-Object System.Collections.Generic.List[object]
    $pending = New-Object System.Collections.Generic.List[object]

    foreach ($target in $targets) {
        $row = [pscustomobject]@{
            Name           = $target.name
            ResourceGroup  = $target.resourceGroup
            SubscriptionId = $target.subscriptionId
            Sku            = $target.sku
            PriorState     = $target.state
            Action         = ''
            Result         = ''
            Detail         = ''
        }

        try {
            $get = Invoke-Arm -Method GET -Path "$($target.id)?api-version=$script:FabricApiVersion"
            if ($get.StatusCode -ge 400) {
                $row.Action = 'Read'
                $row.Result = if ($get.StatusCode -in 401, 403) { 'Denied' } else { 'Error' }
                $row.Detail = Get-ErrorText $get
                $results.Add($row); continue
            }

            $row.PriorState = [string]$get.Body.properties.state
            $decision = Get-AutoPauseDecision -State $row.PriorState -Tags $get.Body.tags `
                -ExcludeTagName $ExcludeTagName -ExcludeTagValue $ExcludeTagValue
            $row.Action = $decision.Action
            $row.Detail = $decision.Reason

            switch ($decision.Action) {
                'Pause' {
                    if ($DryRun) { $row.Result = 'WouldPause'; break }
                    $post = Invoke-Arm -Method POST -Path "$($target.id)/suspend?api-version=$script:FabricApiVersion"
                    if ($post.StatusCode -in 200, 202) {
                        $row.Result = 'PauseRequested'
                        $pending.Add([pscustomobject]@{ Row = $row; Id = $target.id })
                    }
                    else {
                        $row.Result = if ($post.StatusCode -in 401, 403) { 'Denied' } else { 'Error' }
                        $row.Detail = Get-ErrorText $post
                    }
                }
                'Await' {
                    # Another pause is already running; do not send a second request, just verify it finishes.
                    $row.Result = 'PauseInProgress'
                    $pending.Add([pscustomobject]@{ Row = $row; Id = $target.id })
                }
                'Skip'     { $row.Result = 'Skipped' }
                'Excluded' { $row.Result = 'Excluded' }
                'Defer'    { $row.Result = 'Deferred' }
                'Warn'     { $row.Result = 'Warning' }
            }
        }
        catch {
            $row.Result = 'Error'
            $row.Detail = $_.Exception.Message
        }
        $results.Add($row)
    }

    if ($pending.Count -gt 0) {
        Wait-CapacitiesPaused -Pending $pending.ToArray() -TimeoutMinutes $PauseTimeoutMinutes -PollSeconds $PollSeconds
    }

    if ($results.Count -gt 0) {
        Write-Log ($results | Format-Table Name, ResourceGroup, Sku, PriorState, Action, Result, Detail -AutoSize -Wrap | Out-String -Width 220)
    }

    $counts = $results | Group-Object Result | ForEach-Object { "$($_.Name)=$($_.Count)" }
    Write-Log ("Summary: " + $(if ($counts) { $counts -join ', ' } else { 'nothing to do' }))

    $failed = @($results | Where-Object { $_.Result -in 'Error', 'Denied' })
    if ($failed.Count -gt 0) {
        throw "$($failed.Count) capacit$(if ($failed.Count -eq 1) { 'y' } else { 'ies' }) could not be processed: $(($failed | ForEach-Object { $_.Name }) -join ', ')."
    }

    if ($PassThru) { return $results.ToArray() }
}

# Dot-sourcing (for unit tests) loads the functions without running the runbook.
# Output is deliberately not captured here so the log lines reach the Automation job output.
if ($MyInvocation.InvocationName -ne '.') {
    $dryRunValue = ConvertTo-StrictBool -Value $DryRun -Name 'DryRun'
    Invoke-FabricCapacityAutoPause `
        -SubscriptionIds $SubscriptionIds `
        -ManagementGroupId $ManagementGroupId `
        -ResourceGroupName $ResourceGroupName `
        -CapacityName $CapacityName `
        -CapacityResourceId $CapacityResourceId `
        -ExcludeTagName $ExcludeTagName `
        -ExcludeTagValue $ExcludeTagValue `
        -UserAssignedIdentityClientId $UserAssignedIdentityClientId `
        -DryRun $dryRunValue `
        -PauseTimeoutMinutes $PauseTimeoutMinutes `
        -PollSeconds $PollSeconds
}
# ===== EXTENDING (commented examples - NOT ENABLED) =====
# These are an extension pattern, NOT tested in the default release. Nothing below executes.
# Do not uncomment this entire tail in place: the entry-point guard above has already run.
# Move/adapt helpers ABOVE Invoke-FabricCapacityAutoPause, and splice the indicated fragments
# into the existing functions. Keep the deployed/published runbook unchanged during development.
# Full procedure and permissions: docs\EXTENDING.md.
#
# 1. Add these parameters to BOTH the script param block and Invoke-FabricCapacityAutoPause:
# [ValidateSet('Suspend','Resume','Scale','Restart')] [string] $Operation = 'Suspend',
# [string] $TargetSku, # Example: 'F16'; required only for Scale.
# Forward -Operation $Operation -TargetSku $TargetSku in the entry-point guard's invocation.
# Keep the existing string DryRun parameter and ConvertTo-StrictBool at that boundary.
#
# Add these parameters to Get-AutoPauseDecision:
# [ValidateSet('Suspend','Resume','Scale','Restart')] [string] $Operation = 'Suspend',
# [string] $CurrentSku,
# [string] $TargetSku
# AFTER its existing exclusion-tag check, BEFORE its existing switch -Regex ($State), insert:
# if ($Operation -ne 'Suspend') {
#     $action = 'Defer'
#     $reason = "Operation $Operation is unsafe in state '$State'; no change."
#     switch ($Operation) {
#         'Resume' {
#             if ($State -eq 'Active') { $action = 'Skip'; $reason = 'Already Active.' }
#             elseif ($State -match '^(Paused|Suspended)$') {
#                 $action = 'Resume'; $reason = 'Capacity is paused.'
#             }
#         }
#         'Scale' {
#             if ($TargetSku -cnotmatch '\AF[1-9][0-9]*\z' -or
#                 $CurrentSku -cnotmatch '\AF[1-9][0-9]*\z') {
#                 throw 'Scale requires current and target F SKUs, such as F16.'
#             }
#             if ($State -eq 'Active') {
#                 if ($CurrentSku -ceq $TargetSku) {
#                     $action = 'Skip'; $reason = "Already at $TargetSku."
#                 }
#                 else { $action = 'Scale'; $reason = "Scale $CurrentSku to $TargetSku." }
#             }
#         }
#         'Restart' {
#             if ($State -eq 'Active') {
#                 $action = 'Restart'; $reason = 'Suspend, verify Paused, resume, verify Active.'
#             }
#         }
#     }
#     return [pscustomobject]@{ Action = $action; Reason = $reason }
# }
# Leave the original Suspend/Pause decision path unchanged. Excluded must win for EVERY operation.
#
# In Invoke-FabricCapacityAutoPause, validate BEFORE authentication/discovery:
# if ($Operation -eq 'Scale' -and $TargetSku -cnotmatch '\AF[1-9][0-9]*\z') {
#     throw 'Specify an F-series TargetSku, for example F16.'
# }
# Set ONE shared deadline before the per-capacity loop; do not grant every target a fresh timeout:
# $operationDeadline = (Get-UtcNow).AddMinutes($PauseTimeoutMinutes)
# Extend the existing Get-AutoPauseDecision call (which uses fresh ARM tags/state) with:
#     -Operation $Operation -CurrentSku ([string]$get.Body.sku.name) -TargetSku $TargetSku
# Keep the existing non-empty ExcludeTagName guard, result rows, per-target try/catch, summary,
# pending-pause batch, and final Error/Denied aggregation. Update log wording to name $Operation.
#
# 2. Complete internal helpers. Call ONLY from the tag-checked per-capacity decision below.
# The caller must honor ExcludeTagName/ExcludeTagValue (default autopause=skip) for Resume/Scale too.
# Never invoke these helpers as an alternate path around the exclusion check or scope filters.
#
# function Invoke-CapacityResume {
#     param(
#         [Parameter(Mandatory)] [string] $ResourceId,
#         [bool] $DryRun = $true,
#         [datetime] $Deadline = (Get-UtcNow).AddMinutes(15),
#         [ValidateRange(5, 300)] [int] $PollSeconds = 15
#     )
#     $state = Get-CapacityPowerState -ResourceId $ResourceId
#     if ($state -eq 'Active') { Write-Log "Already Active: $ResourceId"; return }
#     if ($state -notmatch '^(Paused|Suspended)$') {
#         throw "Resume refused in state '$state': $ResourceId"
#     }
#     if ($DryRun) { Write-Log "DRY RUN: would resume $ResourceId"; return }
#     if ((Get-UtcNow) -ge $Deadline) { throw 'Resume job deadline exceeded.' }
#     $post = Invoke-Arm -Method POST -Path "${ResourceId}/resume?api-version=2023-11-01"
#     if ($post.StatusCode -notin 200, 202) {
#         throw "Resume failed ($($post.StatusCode)): $(Get-ErrorText $post)"
#     }
#     Write-Log "Resume accepted; waiting for Active: $ResourceId"
#     while ((Get-UtcNow) -lt $Deadline) {
#         if ((Get-CapacityPowerState -ResourceId $ResourceId) -eq 'Active') {
#             Write-Log "Active: $ResourceId"
#             return
#         }
#         Start-Sleep -Seconds $PollSeconds
#     }
#     throw "Resume did not reach Active before the shared deadline: $ResourceId"
# }
#
# function Invoke-CapacityScale {
#     param(
#         [Parameter(Mandatory)] [string] $ResourceId,
#         [Parameter(Mandatory)] [string] $TargetSku,
#         [bool] $DryRun = $true,
#         [datetime] $Deadline = (Get-UtcNow).AddMinutes(15),
#         [ValidateRange(5, 300)] [int] $PollSeconds = 15
#     )
#     if ($TargetSku -cnotmatch '\AF[1-9][0-9]*\z') { throw 'Refusing a non-F target SKU.' }
#     $get = Invoke-Arm -Method GET -Path "${ResourceId}?api-version=2023-11-01"
#     if ($get.StatusCode -ne 200) { throw "Scale preflight failed: $(Get-ErrorText $get)" }
#     $currentSku = [string]$get.Body.sku.name
#     if ($currentSku -cnotmatch '\AF[1-9][0-9]*\z' -or $get.Body.sku.tier -ne 'Fabric') {
#         throw 'Refusing to scale a capacity that is not an F SKU in the Fabric tier.'
#     }
#     if ($get.Body.properties.state -ne 'Active') {
#         throw "Scale requires Active; current state is '$($get.Body.properties.state)'."
#     }
#     if ($currentSku -ceq $TargetSku) {
#         Write-Log "Already at $TargetSku; no PATCH: $ResourceId"
#         return
#     }
#     if ($DryRun) { Write-Log "DRY RUN: would scale $ResourceId to $TargetSku"; return }
#     if ((Get-UtcNow) -ge $Deadline) { throw 'Scale job deadline exceeded.' }
#     # Verified against Microsoft Learn, Fabric Capacities - Update (2023-11-01):
#     # https://learn.microsoft.com/rest/api/microsoftfabric/fabric-capacities/update?view=rest-microsoftfabric-2023-11-01
#     # Top-level sku, NOT properties.sku. Send only {"sku":{"name":"<TargetSku>","tier":"Fabric"}}.
#     $payload = @{ sku = @{ name = $TargetSku; tier = 'Fabric' } } |
#         ConvertTo-Json -Depth 3 -Compress
#     $patch = Invoke-Arm -Method PATCH -Path "${ResourceId}?api-version=2023-11-01" -Payload $payload
#     if ($patch.StatusCode -notin 200, 202) {
#         throw "Scale failed ($($patch.StatusCode)): $(Get-ErrorText $patch)"
#     }
#     Write-Log "Scale accepted; waiting for Active and sku.name=${TargetSku}: $ResourceId"
#     while ((Get-UtcNow) -lt $Deadline) {
#         $check = Invoke-Arm -Method GET -Path "${ResourceId}?api-version=2023-11-01"
#         if ($check.StatusCode -eq 200 -and $check.Body.properties.state -eq 'Active' -and
#             $check.Body.sku.name -ceq $TargetSku) {
#             Write-Log "Active at ${TargetSku}: $ResourceId"
#             return
#         }
#         if ($check.StatusCode -ge 400 -and $check.StatusCode -ne 429 -and $check.StatusCode -lt 500) {
#             throw "Scale verification failed: $(Get-ErrorText $check)"
#         }
#         Start-Sleep -Seconds $PollSeconds
#     }
#     throw "Scale did not reach Active at ${TargetSku} before the shared deadline: $ResourceId"
# }
#
# 3. Add these arms to switch ($decision.Action) in Invoke-FabricCapacityAutoPause.
# The original ARM GET + Get-AutoPauseDecision exclusion check MUST run before this switch.
# 'Resume' {
#     if ($DryRun) { $row.Result = 'WouldResume'; break }
#     Invoke-CapacityResume -ResourceId $target.id -DryRun $DryRun `
#         -Deadline $operationDeadline -PollSeconds $PollSeconds
#     $row.Result = 'Resumed'
# }
# 'Scale' {
#     if ($DryRun) { $row.Result = 'WouldScale'; break }
#     Invoke-CapacityScale -ResourceId $target.id -TargetSku $TargetSku -DryRun $DryRun `
#         -Deadline $operationDeadline -PollSeconds $PollSeconds
#     $row.Result = 'Scaled'
# }
# 'Restart' {
#     if ($DryRun) { $row.Result = 'WouldRestart'; break }
#     Write-Log "Restart sequence: suspend -> Paused -> resume -> Active: $($target.id)"
#     # Reserve enough remaining time BEFORE sending suspend; do not leave no time to verify.
#     $remainingMinutes = [int][Math]::Floor(($operationDeadline - (Get-UtcNow)).TotalMinutes)
#     if ($remainingMinutes -lt 1) { throw 'Restart job deadline exceeded before suspend.' }
#     $post = Invoke-Arm -Method POST -Path "$($target.id)/suspend?api-version=2023-11-01"
#     if ($post.StatusCode -notin 200, 202) { throw "Restart suspend failed: $(Get-ErrorText $post)" }
#     $row.Result = 'PauseRequested'
#     $restartPending = @([pscustomobject]@{ Row = $row; Id = $target.id })
#     $remainingMinutes = [int][Math]::Floor(($operationDeadline - (Get-UtcNow)).TotalMinutes)
#     if ($remainingMinutes -lt 1) { throw 'Restart deadline exceeded after suspend; inspect capacity.' }
#     Wait-CapacitiesPaused -Pending $restartPending -TimeoutMinutes $remainingMinutes -PollSeconds $PollSeconds
#     if ($row.Result -ne 'Paused') { throw "Restart aborted before resume: $($row.Detail)" }
#     # Re-read tags before the SECOND mutation: an excluded capacity is never changed again.
#     $fresh = Invoke-Arm -Method GET -Path "$($target.id)?api-version=2023-11-01"
#     if ($fresh.StatusCode -ne 200) { throw 'Cannot recheck exclusion tags; refusing restart resume.' }
#     $resumeDecision = Get-AutoPauseDecision -State ([string]$fresh.Body.properties.state) `
#         -Tags $fresh.Body.tags -ExcludeTagName $ExcludeTagName -ExcludeTagValue $ExcludeTagValue -Operation 'Resume'
#     if ($resumeDecision.Action -eq 'Excluded') { $row.Result = 'Excluded'; break }
#     Invoke-CapacityResume -ResourceId $target.id -DryRun $DryRun `
#         -Deadline $operationDeadline -PollSeconds $PollSeconds
#     $row.Result = 'Restarted'
# }
# A restart is a recipe, NOT a native /restart API. If resume fails after suspend, the capacity
# may remain Paused: fail the job, inspect Activity Log, and recover deliberately; do not hide it.
#
# 4. SECOND/THIRD schedules: the SAME adapted runbook, different string parameter values.
# Existing evening schedule: Operation=Suspend. Second/morning: Operation=Resume.
# Third/weekend: Operation=Scale TargetSku=F2. An optional month-end schedule can target F16.
# These are ALTERNATIVE policies: Scale is Active-only, so do not scale after an evening pause.
# Run weekend scale before pause, keep that window Active, or resume/verify Active separately.
# Never overlap operations, and account for any existing nightly/backstop schedule.
# Commands below are documentation ONLY; run manually only against an approved extension test copy.
# Replace placeholders; choose future start times at least five minutes ahead. UTC avoids DST
# ambiguity; use a supported IANA timeZone and matching startTime offset if adapting local time.
#
# $accountId = '/subscriptions/<subscription-id>/resourceGroups/<automation-resource-group>/providers/Microsoft.Automation/automationAccounts/<automation-account>'
# $capacityId = '/subscriptions/<subscription-id>/resourceGroups/<capacity-resource-group>/providers/Microsoft.Fabric/capacities/<capacity-name>'
# $runbookName = '<extension-test-runbook-name>'
# $scheduleSpecs = @(
#     @{ Name = '<morning-schedule>'; Operation = 'Resume'; Start = '<future-date>T07:00:00Z'; Frequency = 'Day' },
#     @{ Name = '<evening-schedule>'; Operation = 'Suspend'; Start = '<future-date>T22:00:00Z'; Frequency = 'Day' },
#     @{ Name = '<weekend-schedule>'; Operation = 'Scale'; TargetSku = 'F2'; Start = '<future-saturday>T06:00:00Z'; Frequency = 'Week' }
# )
# foreach ($spec in $scheduleSpecs) {
#     $properties = @{
#         startTime = $spec.Start; frequency = $spec.Frequency; interval = 1; timeZone = 'UTC'
#     }
#     if ($spec.Frequency -eq 'Week') { $properties.advancedSchedule = @{ weekDays = @('Saturday') } }
#     @{ name = $spec.Name; properties = $properties } | ConvertTo-Json -Depth 6 |
#         Set-Content -LiteralPath '.\extension-schedule.json' -Encoding utf8
#     az rest --method put --url "https://management.azure.com${accountId}/schedules/$($spec.Name)?api-version=2024-10-23" `
#         --headers 'Content-Type=application/json' --body '@extension-schedule.json'
#     if ($LASTEXITCODE -ne 0) { throw 'Schedule PUT failed; do not create its link.' }
#     $parameters = @{
#         Operation = [string]$spec.Operation; DryRun = 'true'; CapacityResourceId = $capacityId
#         ExcludeTagName = 'autopause'; ExcludeTagValue = 'skip'
#     }
#     if ($spec.Operation -eq 'Scale') { $parameters.TargetSku = [string]$spec.TargetSku }
#     $jobScheduleId = [guid]::NewGuid().ToString() # FRESH GUID for EACH new association.
#     @{ properties = @{
#         runbook = @{ name = $runbookName }; schedule = @{ name = $spec.Name }; parameters = $parameters
#     } } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath '.\extension-jobSchedule.json' -Encoding utf8
#     az rest --method put --url "https://management.azure.com${accountId}/jobSchedules/${jobScheduleId}?api-version=2024-10-23" `
#         --headers 'Content-Type=application/json' --body '@extension-jobSchedule.json'
#     if ($LASTEXITCODE -ne 0) { throw 'Job-schedule PUT failed.' }
# }
# This creates links, not immediate jobs. Never blindly rerun: list existing jobSchedules and
# remove/replace the intended link deliberately, or fresh GUIDs can create duplicate executions.
#
# 5. RBAC / operational safety:
# All operations need Microsoft.Fabric/capacities/read for discovery and state verification.
# Suspend: Microsoft.Fabric/capacities/suspend/action (already in the DEFAULT custom role).
# Scale: Microsoft.Fabric/capacities/write; the DEFAULT custom role does NOT grant it.
# Resume: Microsoft.Fabric/capacities/resume/action; the DEFAULT custom role does NOT grant it.
# Restart: Microsoft.Fabric/capacities/suspend/action PLUS Microsoft.Fabric/capacities/resume/action.
# scripts\deploy.ps1 -IncludeWritePermission adds write only; it NEVER adds resume/action.
# write also permits changing capacity admins: widening permissions increases the blast radius.
# Scope role assignments to specific capacities or resource groups, not the whole subscription.
# The exclusion tag remains mandatory for EVERY operation; an excluded capacity is never touched.
# Keep DryRun true until verified; test with -DryRun 'true' first, then one CapacityResourceId.
# Scaling an F SKU can interrupt running work. Resume restarts billing. Restart includes downtime.
# Respect the Azure Automation 3-hour sandbox limit: shared deadlines, small batches, retry budget,
# and enough headroom for discovery/network calls; do not serially spend 150 minutes per target.
# ===== END EXTENDING =====
