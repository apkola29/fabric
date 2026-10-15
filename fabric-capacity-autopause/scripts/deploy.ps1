<#
.SYNOPSIS
    Deploys nightly auto-pause of Microsoft Fabric capacities with Azure Automation.

.DESCRIPTION
    Runs these steps in order, and is safe to re-run (idempotent):

      1. Preflight        Azure CLI, Bicep, sign-in, subscription, schedule inputs.
      2. Schedule times   First nightly start and (optionally) a backstop start, as future timestamps.
      3. Infrastructure   Subscription-level Bicep deployment (infra\main.bicep).
      4. Runbook          Uploads runbooks\Invoke-FabricCapacityAutoPause.ps1, prints its SHA-256, and publishes it.
      5. Schedule links   Links the nightly and backstop schedules to the runbook with its parameters.
      6. Summary          Resources, schedules, enforcement mode, role-assignment status and next steps.

    The deployment is SAFE BY DEFAULT: the runbook runs with DryRun = true (it only logs what it would
    pause) until you rerun this script with -EnableEnforcement.

    The -Scope* parameters only NARROW what the runbook looks at. The real scope is whatever the
    managed identity can read through Azure RBAC (see infra\README.md). By default the identity gets the
    custom role at the WHOLE SUBSCRIPTION; use -SkipSubscriptionRoleAssignment to assign it yourself at a
    narrower scope instead.

    Supports -WhatIf and -Confirm. With -WhatIf nothing is created or changed in Azure; only read-only
    preflight checks run. Requires PowerShell 7+ and the Azure CLI (az) signed in with `az login`.

.PARAMETER SubscriptionId
    Subscription that receives the resource group, Automation account and managed identity.

.PARAMETER Location
    Azure region for the resource group and its resources, for example eastus2. A subscription-level
    deployment name is tied to one location, so keep it the same on re-runs.

.PARAMETER ResourceGroupName
    Resource group to create or update. Default: rg-fabric-autopause.

.PARAMETER NamePrefix
    Prefix for resource names (3-47 letters, digits or hyphens, starting with a letter).

.PARAMETER TimeZone
    IANA time zone of the schedules, for example UTC or America/Chicago. Default: UTC.

.PARAMETER ScheduleTime
    Wall-clock time (HH:mm, 24-hour) of the nightly run in -TimeZone. Default: 00:00.

.PARAMETER BackstopOffsetMinutes
    Minutes after the nightly run for a second daily run that catches capacities that were
    transitioning. 0 disables the backstop schedule. Default: 60.

.PARAMETER AlertEmails
    Addresses that receive an alert when a runbook job fails. Empty disables alerting.

.PARAMETER ScopeSubscriptionIds
    Comma-separated subscription IDs the runbook searches. Each entry must be a GUID. Empty searches
    everything the identity can read. Mutually exclusive with -ScopeManagementGroupId.

.PARAMETER ScopeManagementGroupId
    Management group ID (not display name) the runbook searches.

.PARAMETER ScopeResourceGroupName
    Only consider capacities in this resource group.

.PARAMETER ScopeCapacityName
    Only consider the capacity with this name.

.PARAMETER ScopeCapacityResourceId
    Only consider the capacity with this full resource ID.

.PARAMETER ExcludeTagName
    Capacities carrying this tag are never paused. Default: autopause. Must not be empty or whitespace:
    an empty tag name could never match, which would silently disable every opt-out.

.PARAMETER ExcludeTagValue
    Tag value that excludes a capacity. Default: skip. Pass an empty string to exclude on tag presence
    alone (an empty value is sent to the runbook as-is, not omitted).

.PARAMETER EnableEnforcement
    Makes the schedules pause capacities (runbook DryRun = false). Without it the runbook only reports.

.PARAMETER IncludeWritePermission
    Adds Microsoft.Fabric/capacities/write to the custom role, only if suspension needs it. Besides
    suspending, capacities/write also lets the identity scale a capacity and change its capacity admins.
    Resume permission is never granted (see infra\README.md).

.PARAMETER SkipSubscriptionRoleAssignment
    Creates the custom role definition but NO role assignment (Bicep assignRoleAtSubscription = false), so
    you can assign it at a narrower scope by hand: a resource group or a single capacity. The summary
    prints ready-to-run `az role assignment create` examples. NOTHING CAN BE PAUSED until you assign the
    role. An assignment from an earlier run without this switch is not removed. Without the switch the
    identity is assigned the role at the whole subscription.

.PARAMETER CustomRoleName
    Display name of the custom role created for the identity. Role names must be unique per tenant.

.PARAMETER AdditionalAssignableScopes
    Extra scopes where the custom role may be assigned (subscription, resource group or management group).
    This does not create assignments there.

.PARAMETER AzPackageVersion
    Version of the Az PowerShell package installed in the Automation runtime environment (x.y.z).
    Default: 12.3.0.

.PARAMETER Tags
    Tags applied to the resource group and the resources that support tags.

.EXAMPLE
    ./scripts/deploy.ps1 -SubscriptionId 00000000-0000-0000-0000-000000000000 -Location eastus2 -WhatIf

.EXAMPLE
    ./scripts/deploy.ps1 -SubscriptionId 00000000-0000-0000-0000-000000000000 -Location eastus2 `
        -TimeZone America/Chicago -ScheduleTime 22:00 -AlertEmails ops@example.com

.EXAMPLE
    ./scripts/deploy.ps1 -SubscriptionId 00000000-0000-0000-0000-000000000000 -Location eastus2 `
        -EnableEnforcement -IncludeWritePermission

.EXAMPLE
    # Least privilege: create the role but assign it yourself at a resource group or capacity.
    ./scripts/deploy.ps1 -SubscriptionId 00000000-0000-0000-0000-000000000000 -Location eastus2 `
        -SkipSubscriptionRoleAssignment
#>

#Requires -Version 7.0
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\z', ErrorMessage = 'SubscriptionId must be a GUID.')]
    [string] $SubscriptionId,

    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z][A-Za-z0-9 ]{1,40}$', ErrorMessage = 'Location must be an Azure region name such as eastus2.')]
    [string] $Location,

    [ValidatePattern('^(?!.*\.$)[\w\-\.\(\)]{1,90}$', ErrorMessage = 'ResourceGroupName must be 1-90 letters, digits, ''-'', ''_'', ''.'' or parentheses and must not end with a period.')]
    [string] $ResourceGroupName = 'rg-fabric-autopause',

    [ValidatePattern('^[A-Za-z][A-Za-z0-9-]{2,46}$', ErrorMessage = 'NamePrefix must be 3-47 letters, digits or hyphens and begin with a letter.')]
    [string] $NamePrefix = 'fabricautopause',

    [ValidateNotNullOrEmpty()]
    [string] $TimeZone = 'UTC',

    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$', ErrorMessage = 'ScheduleTime must be a 24-hour time in HH:mm format.')]
    [string] $ScheduleTime = '00:00',

    [ValidateRange(0, 1439)]
    [int] $BackstopOffsetMinutes = 60,

    [string[]] $AlertEmails = @(),

    [string] $ScopeSubscriptionIds = '',
    [string] $ScopeManagementGroupId = '',
    [string] $ScopeResourceGroupName = '',
    [string] $ScopeCapacityName = '',
    [string] $ScopeCapacityResourceId = '',

    [string] $ExcludeTagName = 'autopause',
    [string] $ExcludeTagValue = 'skip',

    [switch] $EnableEnforcement,
    [switch] $IncludeWritePermission,
    [switch] $SkipSubscriptionRoleAssignment,

    [ValidateNotNullOrEmpty()]
    [string] $CustomRoleName = 'Fabric Capacity AutoPause Operator',

    [string[]] $AdditionalAssignableScopes = @(),

    [hashtable] $Tags = @{},

    [ValidatePattern('\A\d+\.\d+\.\d+\z', ErrorMessage = 'AzPackageVersion must be a version such as 12.3.0.')]
    [string] $AzPackageVersion = '12.3.0'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

#region Small helpers

function Get-AutomationApiVersion { return '2024-10-23' }

function Get-ArmEndpoint { return 'https://management.azure.com' }

function Write-Message {
    <# Single output seam for the whole script; mockable in tests. #>
    param([string] $Text = '', [ConsoleColor] $Color)
    if ($PSBoundParameters.ContainsKey('Color')) { Write-Host $Text -ForegroundColor $Color }
    else { Write-Host $Text }
}

function Write-Step {
    param([int] $Number, [int] $Total, [string] $Title)
    Write-Message ''
    Write-Message ('=' * 72) -Color DarkCyan
    Write-Message "Step $Number/${Total}: $Title" -Color Cyan
    Write-Message ('=' * 72) -Color DarkCyan
}

function Get-NestedValue {
    <# Null-safe property walk that works for PSCustomObject and dictionaries under strict mode. #>
    param($InputObject, [Parameter(Mandatory)] [string[]] $Path)
    $current = $InputObject
    foreach ($segment in $Path) {
        if ($null -eq $current) { return $null }
        if ($current -is [System.Collections.IDictionary]) {
            if (-not $current.Contains($segment)) { return $null }
            $current = $current[$segment]
        }
        else {
            $property = $current.PSObject.Properties[$segment]
            if ($null -eq $property) { return $null }
            $current = $property.Value
        }
    }
    return $current
}

function Format-ScheduleDisplay {
    param([Parameter(Mandatory)] [DateTimeOffset] $Value)
    return '{0} ({1} UTC)' -f $Value.ToString('yyyy-MM-dd HH:mm zzz', [cultureinfo]::InvariantCulture),
    $Value.UtcDateTime.ToString('yyyy-MM-dd HH:mm', [cultureinfo]::InvariantCulture)
}

function New-TempJsonFile {
    <# Writes UTF-8 (no BOM) JSON to a unique temp file. The caller removes it in a finally block. #>
    param([Parameter(Mandatory)] $InputObject)
    $path = Join-Path ([IO.Path]::GetTempPath()) ("autopause-{0}.json" -f [guid]::NewGuid().ToString('N'))
    $json = $InputObject | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($path, $json, [Text.UTF8Encoding]::new($false))
    return $path
}

function Remove-TempFile {
    param([string] $Path)
    if ($Path -and (Test-Path -LiteralPath $Path)) { Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue }
}

function Invoke-WithRetry {
    <# Runs an action, retrying failures with exponential backoff (capped). Rethrows after the last attempt. #>
    param(
        [Parameter(Mandatory)] [scriptblock] $Action,
        [string] $Description = 'operation',
        [ValidateRange(1, 20)] [int] $MaxAttempts = 6,
        [int] $InitialDelaySeconds = 5,
        [int] $MaxDelaySeconds = 30
    )

    $delay = $InitialDelaySeconds
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            return (& $Action)
        }
        catch {
            if ($attempt -ge $MaxAttempts) {
                throw "$Description failed after $MaxAttempts attempt(s): $($_.Exception.Message)"
            }
            Write-Message "  $Description failed (attempt $attempt/$MaxAttempts): $($_.Exception.Message)" -Color Yellow
            Write-Message "  Retrying in $delay s..." -Color Yellow
            Start-Sleep -Seconds $delay
            $delay = [Math]::Min($delay * 2, $MaxDelaySeconds)
        }
    }
}

#endregion

#region Azure CLI wrappers

function Test-AzCliInstalled {
    return [bool](Get-Command -Name az -ErrorAction SilentlyContinue)
}

function Invoke-Az {
    <#
        Runs `az` and returns the parsed JSON (or trimmed text with -AsText). Throws on a non-zero exit
        code with stderr in the message. Warnings on stderr never pollute the parsed output.
    #>
    param(
        [Parameter(Mandatory)] [string[]] $Arguments,
        [switch] $AsText
    )

    $extra = @('--only-show-errors')
    if (-not $AsText) { $extra += @('--output', 'json') }

    $global:LASTEXITCODE = 0
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $raw = @(& az @Arguments @extra 2>&1) }
    finally { $ErrorActionPreference = $previousPreference }
    $exitCode = $global:LASTEXITCODE

    $stdout = @($raw | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] } | ForEach-Object { [string]$_ })
    $stderr = @($raw | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } | ForEach-Object { $_.ToString() })

    if ($exitCode -ne 0) {
        $label = (@($Arguments | Where-Object { $_ -notmatch '^-' } | Select-Object -First 3)) -join ' '
        $detail = (($stderr + $stdout) -join [Environment]::NewLine).Trim()
        throw "az $label failed (exit code $exitCode). $detail"
    }

    $text = ($stdout -join [Environment]::NewLine).Trim()
    if ($AsText) { return $text }
    if (-not $text) { return $null }
    try { return ($text | ConvertFrom-Json -Depth 50) }
    catch { throw "az returned output that is not valid JSON: $text" }
}

function Invoke-AzRest {
    <#
        Thin wrapper over `az rest`. Request bodies always travel through a temp file (--body @file) so no
        shell quoting is involved. Mutating methods are refused while -WhatIf is in effect.
    #>
    param(
        [Parameter(Mandatory)] [ValidateSet('get', 'put', 'post', 'delete')] [string] $Method,
        [Parameter(Mandatory)] [string] $Uri,
        $Body,
        [string] $BodyFile,
        [string] $ContentType = 'application/json'
    )

    if ($Method -ne 'get' -and $WhatIfPreference) {
        throw "Refusing to send a $Method request to '$Uri' while -WhatIf is in effect."
    }

    $arguments = @('rest', '--method', $Method, '--url', $Uri)
    $tempFile = $null
    try {
        $file = $BodyFile
        if (-not $file -and $PSBoundParameters.ContainsKey('Body')) {
            $tempFile = New-TempJsonFile -InputObject $Body
            $file = $tempFile
        }
        if ($file) {
            $arguments += @('--headers', "Content-Type=$ContentType", '--body', "@$file")
        }
        return (Invoke-Az -Arguments $arguments)
    }
    finally { Remove-TempFile -Path $tempFile }
}

#endregion

#region Settings and validation

function Resolve-DeploymentSettings {
    <# Validates cross-field rules and normalises the script parameters into one settings object. #>
    param(
        [Parameter(Mandatory)] [System.Collections.IDictionary] $Values,
        [Parameter(Mandatory)] [string] $RepoRoot
    )

    $required = 'SubscriptionId', 'Location', 'ResourceGroupName', 'NamePrefix', 'TimeZone', 'ScheduleTime',
    'BackstopOffsetMinutes', 'AlertEmails', 'ScopeSubscriptionIds', 'ScopeManagementGroupId', 'ScopeResourceGroupName',
    'ScopeCapacityName', 'ScopeCapacityResourceId', 'ExcludeTagName', 'ExcludeTagValue', 'EnableEnforcement',
    'IncludeWritePermission', 'SkipSubscriptionRoleAssignment', 'CustomRoleName', 'AdditionalAssignableScopes', 'Tags',
    'AzPackageVersion'
    foreach ($key in $required) {
        if (-not $Values.Contains($key)) { throw "Missing deployment setting '$key'." }
    }

    # \A...\z (not ^...$): '$' would also accept a trailing newline.
    $guid = '\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\z'
    $safeName = '^[\w\-\.\(\)]{1,90}$'

    $excludeTagName = ([string]$Values.ExcludeTagName).Trim()
    if ([string]::IsNullOrWhiteSpace($excludeTagName)) {
        throw 'ExcludeTagName must not be empty or whitespace: a capacity can never carry an empty tag name, so every opt-out would be disabled and all capacities would be paused. Use the default (autopause) or another tag name.'
    }

    $azPackageVersion = ([string]$Values.AzPackageVersion).Trim()
    if ($azPackageVersion -notmatch '\A\d+\.\d+\.\d+\z') {
        throw "AzPackageVersion '$azPackageVersion' is not a version such as 12.3.0."
    }

    $subscriptions = @(([string]$Values.ScopeSubscriptionIds) -split '[,;\s]+' | Where-Object { $_ })
    foreach ($id in $subscriptions) {
        if ($id -notmatch $guid) { throw "ScopeSubscriptionIds contains '$id', which is not a subscription GUID." }
    }
    $managementGroup = ([string]$Values.ScopeManagementGroupId).Trim()
    if ($subscriptions.Count -gt 0 -and $managementGroup) {
        throw 'Specify either -ScopeSubscriptionIds or -ScopeManagementGroupId, not both.'
    }
    if ($managementGroup -and $managementGroup -notmatch $safeName) {
        throw "ScopeManagementGroupId '$managementGroup' is not a valid management group ID."
    }

    $scopeResourceGroup = ([string]$Values.ScopeResourceGroupName).Trim()
    if ($scopeResourceGroup -and $scopeResourceGroup -notmatch $safeName) {
        throw "ScopeResourceGroupName '$scopeResourceGroup' is not a valid resource group name."
    }
    $capacityName = ([string]$Values.ScopeCapacityName).Trim()
    if ($capacityName -and $capacityName -notmatch '^[A-Za-z][A-Za-z0-9]{2,62}$') {
        throw "ScopeCapacityName '$capacityName' is not a valid Fabric capacity name (3-63 letters or digits, starting with a letter)."
    }
    $capacityId = ([string]$Values.ScopeCapacityResourceId).Trim()
    if ($capacityId -and $capacityId -notmatch '^/subscriptions/[0-9a-fA-F\-]{36}/resourceGroups/[\w\-\.\(\)]+/providers/Microsoft\.Fabric/capacities/[A-Za-z][A-Za-z0-9]+$') {
        throw "ScopeCapacityResourceId '$capacityId' is not a Microsoft.Fabric/capacities resource ID."
    }

    $emails = @($Values.AlertEmails | Where-Object { $_ } | ForEach-Object { ([string]$_).Trim() })
    foreach ($email in $emails) {
        if ($email -notmatch '^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$') { throw "AlertEmails contains '$email', which is not an email address." }
    }

    $assignableScopes = @($Values.AdditionalAssignableScopes | Where-Object { $_ } | ForEach-Object { ([string]$_).Trim() })
    foreach ($scope in $assignableScopes) {
        if ($scope -notmatch '^/(subscriptions|providers/Microsoft\.Management/managementGroups)/[^/\s]+(/resourceGroups/[^/\s]+)?$') {
            throw "AdditionalAssignableScopes contains '$scope', which is not a subscription, resource group or management group scope."
        }
    }

    $tagTable = [ordered]@{}
    foreach ($key in $Values.Tags.Keys) { $tagTable[[string]$key] = [string]$Values.Tags[$key] }

    return [pscustomobject]@{
        SubscriptionId             = ([string]$Values.SubscriptionId).ToLowerInvariant()
        Location                   = [string]$Values.Location
        ResourceGroupName          = [string]$Values.ResourceGroupName
        NamePrefix                 = [string]$Values.NamePrefix
        TimeZone                   = [string]$Values.TimeZone
        ScheduleTime               = [string]$Values.ScheduleTime
        BackstopOffsetMinutes      = [int]$Values.BackstopOffsetMinutes
        AlertEmails                = [string[]]$emails
        ScopeSubscriptionIds       = ($subscriptions -join ',')
        ScopeManagementGroupId     = $managementGroup
        ScopeResourceGroupName     = $scopeResourceGroup
        ScopeCapacityName          = $capacityName
        ScopeCapacityResourceId    = $capacityId
        ExcludeTagName             = $excludeTagName
        ExcludeTagValue            = [string]$Values.ExcludeTagValue
        EnableEnforcement          = [bool]$Values.EnableEnforcement
        IncludeWritePermission     = [bool]$Values.IncludeWritePermission
        SkipSubscriptionRoleAssignment = [bool]$Values.SkipSubscriptionRoleAssignment
        CustomRoleName             = [string]$Values.CustomRoleName
        AdditionalAssignableScopes = [string[]]$assignableScopes
        Tags                       = $tagTable
        AzPackageVersion           = $azPackageVersion
        RepoRoot                   = $RepoRoot
        TemplatePath               = Join-Path $RepoRoot 'infra' 'main.bicep'
        RunbookPath                = Join-Path $RepoRoot 'runbooks' 'Invoke-FabricCapacityAutoPause.ps1'
        DeploymentName             = "deploy-$($Values.NamePrefix)"
    }
}

#endregion

#region Pure builders

function Get-ScheduleStartTimes {
    <#
        First nightly start and, when -BackstopOffsetMinutes > 0, the backstop start.
        The backstop is the nightly WALL-CLOCK time plus the offset, so it rolls over midnight correctly
        and keeps the intended local time across daylight-saving changes (a time that does not exist is
        moved forward one hour, like Get-NextOccurrence does).
    #>
    param(
        [Parameter(Mandatory)] [string] $TimeZoneId,
        [Parameter(Mandatory)] [string] $TimeOfDay,
        [int] $BackstopOffsetMinutes = 0,
        [datetime] $NowUtc = [datetime]::UtcNow
    )

    $nightly = Get-NextOccurrence -TimeZoneId $TimeZoneId -TimeOfDay $TimeOfDay -NowUtc $NowUtc
    $backstop = $null
    if ($BackstopOffsetMinutes -gt 0) {
        $zone = [TimeZoneInfo]::FindSystemTimeZoneById($TimeZoneId)
        $wallClock = [datetime]::SpecifyKind($nightly.DateTime.AddMinutes($BackstopOffsetMinutes), [DateTimeKind]::Unspecified)
        while ($zone.IsInvalidTime($wallClock)) { $wallClock = $wallClock.AddHours(1) }
        $backstop = [DateTimeOffset]::new($wallClock, $zone.GetUtcOffset($wallClock))
    }

    return [pscustomobject]@{
        Nightly      = $nightly
        Backstop     = $backstop
        NightlyText  = Format-ScheduleTime $nightly
        BackstopText = if ($backstop) { Format-ScheduleTime $backstop } else { '' }
    }
}

function New-InfraParameterFileContent {
    <# ARM parameters file for infra\main.bicep. Values keep their JSON types (arrays, bool, object). #>
    param(
        [Parameter(Mandatory)] $Settings,
        [Parameter(Mandatory)] [string] $ScheduleStartTime,
        [string] $BackstopStartTime = ''
    )

    return [ordered]@{
        '$schema'      = 'https://schema.management.azure.com/schemas/2018-05-01/subscriptionDeploymentParameters.json#'
        contentVersion = '1.0.0.0'
        parameters     = [ordered]@{
            location                   = @{ value = $Settings.Location }
            resourceGroupName          = @{ value = $Settings.ResourceGroupName }
            namePrefix                 = @{ value = $Settings.NamePrefix }
            timeZone                   = @{ value = $Settings.TimeZone }
            scheduleStartTime          = @{ value = $ScheduleStartTime }
            backstopStartTime          = @{ value = $BackstopStartTime }
            alertEmails                = @{ value = @($Settings.AlertEmails) }
            includeWritePermission     = @{ value = [bool]$Settings.IncludeWritePermission }
            assignRoleAtSubscription   = @{ value = -not [bool]$Settings.SkipSubscriptionRoleAssignment }
            customRoleName             = @{ value = $Settings.CustomRoleName }
            additionalAssignableScopes = @{ value = @($Settings.AdditionalAssignableScopes) }
            tags                       = @{ value = $Settings.Tags }
            azPackageVersion           = @{ value = $Settings.AzPackageVersion }
        }
    }
}

function New-JobScheduleParameterMap {
    <#
        Runbook parameter dictionary for a job-schedule link. Keys match the runbook parameter names and
        every value is a string. Empty scope values are omitted so the runbook defaults apply.
        ExcludeTagName/ExcludeTagValue are always sent: their defaults are non-empty, so an empty value
        can only be a deliberate choice (for example "exclude on tag presence alone").
    #>
    param(
        [Parameter(Mandatory)] $Settings,
        [Parameter(Mandatory)] [AllowEmptyString()] [string] $IdentityClientId
    )

    $map = [ordered]@{}
    $scope = [ordered]@{
        SubscriptionIds    = $Settings.ScopeSubscriptionIds
        ManagementGroupId  = $Settings.ScopeManagementGroupId
        ResourceGroupName  = $Settings.ScopeResourceGroupName
        CapacityName       = $Settings.ScopeCapacityName
        CapacityResourceId = $Settings.ScopeCapacityResourceId
    }
    foreach ($key in $scope.Keys) {
        $value = [string]$scope[$key]
        if (-not [string]::IsNullOrWhiteSpace($value)) { $map[$key] = $value.Trim() }
    }
    $map['ExcludeTagName'] = [string]$Settings.ExcludeTagName
    $map['ExcludeTagValue'] = [string]$Settings.ExcludeTagValue
    if (-not [string]::IsNullOrWhiteSpace($IdentityClientId)) { $map['UserAssignedIdentityClientId'] = $IdentityClientId.Trim() }
    $map['DryRun'] = if ($Settings.EnableEnforcement) { 'false' } else { 'true' }
    return $map
}

function Get-AutomationUrl {
    param(
        [Parameter(Mandatory)] $Target,
        [string] $Path = '',
        [string] $ApiVersion = (Get-AutomationApiVersion)
    )
    $base = '{0}/subscriptions/{1}/resourceGroups/{2}/providers/Microsoft.Automation/automationAccounts/{3}' -f
    (Get-ArmEndpoint), $Target.SubscriptionId, $Target.ResourceGroupName, $Target.AutomationAccountName
    return "${base}${Path}?api-version=${ApiVersion}"
}

function Get-DeploymentOutputs {
    <# Reads and checks the outputs of infra\main.bicep from the deployment JSON. #>
    param([Parameter(Mandatory)] $Deployment)

    $outputs = Get-NestedValue $Deployment 'properties', 'outputs'
    $read = {
        param([string] $Name, [bool] $Required)
        $value = Get-NestedValue $outputs $Name, 'value'
        if ($Required -and [string]::IsNullOrWhiteSpace([string]$value)) {
            throw "The deployment finished but did not return the output '$Name'. Is infra\main.bicep out of date?"
        }
        return [string]$value
    }

    return [pscustomobject]@{
        ResourceGroupName      = & $read 'resourceGroupName' $true
        AutomationAccountName  = & $read 'automationAccountName' $true
        RunbookName            = & $read 'runbookName' $true
        RuntimeEnvironmentName = & $read 'runtimeEnvironmentName' $false
        IdentityClientId       = & $read 'identityClientId' $true
        IdentityPrincipalId    = & $read 'identityPrincipalId' $true
        NightlyScheduleName    = & $read 'nightlyScheduleName' $true
        BackstopScheduleName   = & $read 'backstopScheduleName' $false
        RoleDefinitionId       = & $read 'roleDefinitionId' $false
    }
}

#endregion

#region Steps

function Assert-Preflight {
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)] $Settings)

    if (-not (Test-AzCliInstalled)) {
        throw "The Azure CLI ('az') was not found on PATH. Install it from https://learn.microsoft.com/cli/azure/install-azure-cli and re-run."
    }
    Write-Message '  Azure CLI found.'

    try { $bicep = Invoke-Az -Arguments @('bicep', 'version') -AsText }
    catch { throw "Bicep is not available through the Azure CLI. Run 'az bicep install' and re-run. Details: $($_.Exception.Message)" }
    Write-Message "  Bicep available: $bicep"

    try { $null = Invoke-Az -Arguments @('account', 'show') }
    catch { throw "You are not signed in to the Azure CLI. Run 'az login' and re-run. Details: $($_.Exception.Message)" }

    try { $null = Invoke-Az -Arguments @('account', 'show', '--subscription', $Settings.SubscriptionId) }
    catch { throw "Subscription '$($Settings.SubscriptionId)' is not available to the signed-in account. Check the ID or run 'az login' with the right account. Details: $($_.Exception.Message)" }

    if ($PSCmdlet.ShouldProcess("Azure CLI context", "Set the active subscription to $($Settings.SubscriptionId)")) {
        $null = Invoke-Az -Arguments @('account', 'set', '--subscription', $Settings.SubscriptionId)
        Write-Message "  Active subscription set to $($Settings.SubscriptionId)."
    }

    foreach ($path in $Settings.TemplatePath, $Settings.RunbookPath) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required file not found: $path" }
    }

    try { $null = Get-NextOccurrence -TimeZoneId $Settings.TimeZone -TimeOfDay $Settings.ScheduleTime }
    catch { throw "Invalid schedule: -TimeZone '$($Settings.TimeZone)' / -ScheduleTime '$($Settings.ScheduleTime)'. Use an IANA time zone (for example America/Chicago) and HH:mm. Details: $($_.Exception.Message)" }
    Write-Message "  Schedule inputs are valid ($($Settings.ScheduleTime) $($Settings.TimeZone))."

    if ($Settings.SkipSubscriptionRoleAssignment) {
        Write-Warning '-SkipSubscriptionRoleAssignment: the custom role will be created but NOT assigned. No capacity can be paused until you assign it at a resource group or capacity scope (commands are printed in the summary).'
    }
}

function Invoke-InfraDeployment {
    <# Runs the subscription-level Bicep deployment and returns its validated outputs ($null when skipped). #>
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)] $Settings,
        [Parameter(Mandatory)] [string] $ScheduleStartTime,
        [string] $BackstopStartTime = ''
    )

    if (-not $PSCmdlet.ShouldProcess("subscription $($Settings.SubscriptionId)", "Deploy resource group '$($Settings.ResourceGroupName)' and Automation resources from infra\main.bicep")) {
        return $null
    }

    $parameterFile = $null
    try {
        $parameterFile = New-TempJsonFile -InputObject (New-InfraParameterFileContent -Settings $Settings -ScheduleStartTime $ScheduleStartTime -BackstopStartTime $BackstopStartTime)
        Write-Message "  Deployment '$($Settings.DeploymentName)' (this can take a few minutes)..."
        $deployment = Invoke-Az -Arguments @(
            'deployment', 'sub', 'create',
            '--name', $Settings.DeploymentName,
            '--location', $Settings.Location,
            '--template-file', $Settings.TemplatePath,
            '--parameters', "@$parameterFile"
        )
    }
    finally { Remove-TempFile -Path $parameterFile }

    $outputs = Get-DeploymentOutputs -Deployment $deployment
    Write-Message "  Deployed resource group '$($outputs.ResourceGroupName)', Automation account '$($outputs.AutomationAccountName)'."
    return $outputs
}

function Wait-RunbookPublished {
    param(
        [Parameter(Mandatory)] $Target,
        [int] $TimeoutSeconds = 180,
        [int] $PollSeconds = 5
    )

    $url = Get-AutomationUrl -Target $Target -Path "/runbooks/$($Target.RunbookName)"
    $state = 'Unknown'
    for ($waited = 0; $waited -le $TimeoutSeconds; $waited += $PollSeconds) {
        $runbook = Invoke-AzRest -Method get -Uri $url
        $state = [string](Get-NestedValue $runbook 'properties', 'state')
        if ($state -eq 'Published') { return $state }
        Write-Message "  Runbook state: $state; waiting..."
        Start-Sleep -Seconds $PollSeconds
    }
    throw "Runbook '$($Target.RunbookName)' did not reach state 'Published' within $TimeoutSeconds s (last state: $state)."
}

function Publish-Runbook {
    <# Uploads the runbook script as the draft, publishes it (retrying: the upload is asynchronous), waits for Published. #>
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)] $Target,
        [Parameter(Mandatory)] [string] $RunbookPath,
        [int] $PublishAttempts = 6,
        [int] $TimeoutSeconds = 180,
        [int] $PollSeconds = 5
    )

    $name = $Target.RunbookName
    if (-not $PSCmdlet.ShouldProcess("runbook '$name' in Automation account '$($Target.AutomationAccountName)'", 'Upload content and publish')) {
        return $false
    }

    Write-Message "  Uploading $(Split-Path -Leaf $RunbookPath) as the draft of '$name'..."
    $hash = (Get-FileHash -LiteralPath $RunbookPath -Algorithm SHA256).Hash
    Write-Message "  Runbook file SHA-256: $hash"
    Write-Message '  (Compare with Get-FileHash -Algorithm SHA256 on the runbook file to verify what was deployed.)'
    $null = Invoke-AzRest -Method put -Uri (Get-AutomationUrl -Target $Target -Path "/runbooks/$name/draft/content") `
        -BodyFile $RunbookPath -ContentType 'text/plain'

    $publishUrl = Get-AutomationUrl -Target $Target -Path "/runbooks/$name/publish"
    Write-Message "  Publishing '$name'..."
    $null = Invoke-WithRetry -Description 'Publishing the runbook' -MaxAttempts $PublishAttempts -InitialDelaySeconds 5 -MaxDelaySeconds 30 -Action {
        Invoke-AzRest -Method post -Uri $publishUrl
    }

    $null = Wait-RunbookPublished -Target $Target -TimeoutSeconds $TimeoutSeconds -PollSeconds $PollSeconds
    Write-Message "  Runbook '$name' is Published." -Color Green
    return $true
}

function Get-JobScheduleLinks {
    param([Parameter(Mandatory)] $Target)

    $links = @()
    $url = Get-AutomationUrl -Target $Target -Path '/jobSchedules'
    while ($url) {
        $page = Invoke-AzRest -Method get -Uri $url
        $links += @(Get-NestedValue $page 'value' | Where-Object { $_ })
        $url = [string](Get-NestedValue $page 'nextLink')
    }
    return $links
}

function Set-JobScheduleLinks {
    <#
        Job-schedule links cannot be updated, so any existing link between this runbook and one of our
        schedules is deleted and recreated with the current parameters. Each new link gets a fresh ID
        because Automation will not let a just-deleted link ID be reused.
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)] $Target,
        [Parameter(Mandatory)] [string[]] $ScheduleNames,
        [Parameter(Mandatory)] [System.Collections.IDictionary] $Parameters
    )

    $runbook = $Target.RunbookName
    $linked = New-Object System.Collections.Generic.List[string]

    foreach ($link in @(Get-JobScheduleLinks -Target $Target)) {
        $linkRunbook = Get-NestedValue $link 'properties', 'runbook', 'name'
        $linkSchedule = Get-NestedValue $link 'properties', 'schedule', 'name'
        if ($linkRunbook -ieq $runbook -and $ScheduleNames -contains $linkSchedule) {
            $linkId = Get-NestedValue $link 'properties', 'jobScheduleId'
            if (-not $linkId) { $linkId = Get-NestedValue $link 'name' }
            if ($PSCmdlet.ShouldProcess("schedule link '$linkSchedule' -> '$runbook'", 'Delete existing link')) {
                Write-Message "  Removing existing link '$linkSchedule' -> '$runbook'..."
                $null = Invoke-AzRest -Method delete -Uri (Get-AutomationUrl -Target $Target -Path "/jobSchedules/$linkId")
            }
        }
    }

    foreach ($schedule in $ScheduleNames) {
        # A fresh ID every time: Automation keeps a deleted link's ID reserved for a while, so re-using a
        # stable ID fails with 'A jobSchedule with same id already exists' on any re-run.
        $linkId = [guid]::NewGuid().ToString()
        $url = Get-AutomationUrl -Target $Target -Path "/jobSchedules/$linkId"
        $body = @{
            properties = @{
                schedule   = @{ name = $schedule }
                runbook    = @{ name = $runbook }
                parameters = $Parameters
            }
        }
        if ($PSCmdlet.ShouldProcess("schedule '$schedule'", "Link to runbook '$runbook'")) {
            Write-Message "  Linking schedule '$schedule' -> '$runbook'..."
            $null = Invoke-WithRetry -Description "Linking schedule '$schedule'" -MaxAttempts 3 -InitialDelaySeconds 5 -MaxDelaySeconds 15 -Action {
                Invoke-AzRest -Method put -Uri $url -Body $body
            }
            $linked.Add($schedule)
        }
    }
    return , $linked.ToArray()
}

function Get-RoleAssignmentCommands {
    <#
        Azure CLI commands for assigning the custom role by hand (used with -SkipSubscriptionRoleAssignment) and for
        verifying the assignment (default). The resource group and capacity names are placeholders to fill in.
    #>
    param(
        [Parameter(Mandatory)] [string] $PrincipalId,
        [Parameter(Mandatory)] [string] $RoleName,
        [Parameter(Mandatory)] [string] $SubscriptionId
    )

    $subscriptionScope = "/subscriptions/$SubscriptionId"
    $resourceGroupScope = "$subscriptionScope/resourceGroups/<resource-group-name>"
    $capacityScope = "$resourceGroupScope/providers/Microsoft.Fabric/capacities/<capacity-name>"
    $create = 'az role assignment create --assignee-object-id {0} --assignee-principal-type ServicePrincipal --role "{1}" --scope {2}'

    return [pscustomobject]@{
        ResourceGroupScope  = $resourceGroupScope
        CapacityScope       = $capacityScope
        AssignResourceGroup = $create -f $PrincipalId, $RoleName, $resourceGroupScope
        AssignCapacity      = $create -f $PrincipalId, $RoleName, $capacityScope
        Verify              = "az role assignment list --assignee $PrincipalId --all -o table"
    }
}

function Write-DeploymentSummary {
    param(
        [Parameter(Mandatory)] $Settings,
        [Parameter(Mandatory)] $Result
    )

    $dryRun = -not $Settings.EnableEnforcement
    $skipAssignment = [bool]$Settings.SkipSubscriptionRoleAssignment
    $roleDefinitionId = [string](Get-NestedValue $Result 'RoleDefinitionId')
    $roleCommands = Get-RoleAssignmentCommands -PrincipalId $Result.IdentityPrincipalId -RoleName $Settings.CustomRoleName -SubscriptionId $Settings.SubscriptionId
    Write-Message ''
    Write-Message "  Resource group     : $($Result.ResourceGroupName)"
    Write-Message "  Automation account : $($Result.AutomationAccountName)"
    Write-Message "  Runbook            : $($Result.RunbookName)"
    Write-Message "  Managed identity   : principal $($Result.IdentityPrincipalId), client $($Result.IdentityClientId)"
    Write-Message "  Custom role        : $($Settings.CustomRoleName)$(if ($roleDefinitionId) { " ($roleDefinitionId)" })"
    if ($skipAssignment) {
        Write-Message '  Role assignment    : NONE (-SkipSubscriptionRoleAssignment) - assign the role yourself, see below' -Color Red
    }
    else {
        Write-Message "  Role assignment    : whole subscription (/subscriptions/$($Settings.SubscriptionId))"
    }
    Write-Message "  Nightly schedule   : $($Result.NightlyScheduleName), first run $(Format-ScheduleDisplay $Result.NightlyStart) [$($Settings.TimeZone)]"
    if ($Result.BackstopStart) {
        Write-Message "  Backstop schedule  : $($Result.BackstopScheduleName), first run $(Format-ScheduleDisplay $Result.BackstopStart) [$($Settings.TimeZone)]"
    }
    else {
        Write-Message '  Backstop schedule  : disabled'
    }
    if ($Settings.AlertEmails.Count -gt 0) {
        Write-Message "  Failure alerts     : $($Settings.AlertEmails -join ', ')"
    }
    Write-Message ''

    if ($dryRun) {
        Write-Message 'Mode: DRY RUN - nothing will be paused until you rerun with -EnableEnforcement' -Color Yellow
        Write-Message '      (add -IncludeWritePermission if the identity must be granted the optional write permission).' -Color Yellow
    }
    else {
        Write-Message 'Mode: ENFORCING - capacities discovered by the runbook WILL be paused at the scheduled times.' -Color Red
    }

    Write-Message ''
    if ($skipAssignment) {
        Write-Message 'IMPORTANT: the managed identity has NO role assignment, so NOTHING CAN BE PAUSED (it cannot even see capacities) until you assign the role.' -Color Red
        Write-Message "Assign '$($Settings.CustomRoleName)' at the narrowest scope that covers your capacities. The scope must be inside the role's assignable"
        Write-Message 'scopes (this subscription plus -AdditionalAssignableScopes); replace the <placeholders> and the subscription ID if the capacities live elsewhere.'
        Write-Message '  # every capacity in one resource group'
        Write-Message "  $($roleCommands.AssignResourceGroup)"
        Write-Message '  # a single capacity'
        Write-Message "  $($roleCommands.AssignCapacity)"
        Write-Message 'Role assignments can take a few minutes to take effect.'
    }
    else {
        Write-Message 'Verify the role assignment of the managed identity:'
        Write-Message "  $($roleCommands.Verify)"
    }
    $account = $Result.AutomationAccountName
    $group = $Result.ResourceGroupName
    $runbook = $Result.RunbookName
    $dryRunText = if ($dryRun) { '$true' } else { '$false' }
    Write-Message ''
    Write-Message 'Next steps'
    Write-Message '  1. Start a manual test job (dry run, nothing is paused). Portal: Automation account > Runbooks >'
    Write-Message "     $runbook > Start; set UserAssignedIdentityClientId = $($Result.IdentityClientId) and DryRun = True. Or with the Az module:"
    Write-Message "       Start-AzAutomationRunbook -ResourceGroupName '$group' -AutomationAccountName '$account' -Name '$runbook' ``"
    Write-Message "         -Parameters @{ UserAssignedIdentityClientId = '$($Result.IdentityClientId)'; DryRun = `$true }"
    Write-Message '  2. Read the output. Portal: Automation account > Jobs > select the job > Output / All Logs. Or:'
    Write-Message "       Get-AzAutomationJobOutput -ResourceGroupName '$group' -AutomationAccountName '$account' -Id <job-id> -Stream Any"
    if ($dryRun) {
        Write-Message '  3. When the dry-run output lists the capacities you expect, rerun this script with -EnableEnforcement.'
    }
    else {
        Write-Message "  3. Confirm the first scheduled run in Automation account > Jobs (the runbook is running with DryRun = $dryRunText)."
    }
    Write-Message '  4. To exclude a capacity from pausing, tag it with the exclusion tag:'
    Write-Message "       $($Settings.ExcludeTagName) = $($Settings.ExcludeTagValue)"
}

#endregion

function Invoke-Deployment {
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)] $Settings,
        [datetime] $NowUtc = [datetime]::UtcNow
    )

    $totalSteps = 6
    $dryRun = -not $Settings.EnableEnforcement
    if ($WhatIfPreference) {
        Write-Message 'WhatIf: only read-only checks run; nothing is created or changed in Azure.' -Color Yellow
    }

    Write-Step 1 $totalSteps 'Preflight checks'
    Assert-Preflight -Settings $Settings

    Write-Step 2 $totalSteps 'Compute schedule start times'
    $times = Get-ScheduleStartTimes -TimeZoneId $Settings.TimeZone -TimeOfDay $Settings.ScheduleTime `
        -BackstopOffsetMinutes $Settings.BackstopOffsetMinutes -NowUtc $NowUtc
    Write-Message "  Nightly : $(Format-ScheduleDisplay $times.Nightly) [$($Settings.TimeZone)]"
    if ($times.Backstop) { Write-Message "  Backstop: $(Format-ScheduleDisplay $times.Backstop) [$($Settings.TimeZone)]" }
    else { Write-Message '  Backstop: disabled' }

    Write-Step 3 $totalSteps 'Deploy infrastructure (Bicep)'
    $outputs = Invoke-InfraDeployment -Settings $Settings -ScheduleStartTime $times.NightlyText -BackstopStartTime $times.BackstopText

    if ($null -eq $outputs) {
        Write-Message ''
        Write-Message 'The infrastructure deployment did not run (-WhatIf or declined), so runbook upload, publishing and schedule linking are skipped.' -Color Yellow
        Write-Step 4 $totalSteps 'Upload and publish runbook (skipped)'
        Write-Step 5 $totalSteps 'Link schedules to the runbook (skipped)'
        Write-Step 6 $totalSteps 'Summary'
        Write-Message "  Would deploy resource group '$($Settings.ResourceGroupName)' in $($Settings.Location) (name prefix '$($Settings.NamePrefix)')."
        Write-Message "  Role assignment: $(if ($Settings.SkipSubscriptionRoleAssignment) { "custom role '$($Settings.CustomRoleName)' would be created but NOT assigned (-SkipSubscriptionRoleAssignment); nothing can be paused until you assign it" } else { "custom role '$($Settings.CustomRoleName)' would be assigned at the whole subscription" })"
        Write-Message "  Enforcement mode: $(if ($dryRun) { 'DRY RUN - nothing will be paused until you rerun with -EnableEnforcement' } else { 'ENFORCING (runbook DryRun = false)' })"
        return [pscustomobject]@{ Deployed = $false; DryRun = $dryRun; NightlyStart = $times.Nightly; BackstopStart = $times.Backstop }
    }

    $target = [pscustomobject]@{
        SubscriptionId        = $Settings.SubscriptionId
        ResourceGroupName     = $outputs.ResourceGroupName
        AutomationAccountName = $outputs.AutomationAccountName
        RunbookName           = $outputs.RunbookName
    }

    Write-Step 4 $totalSteps 'Upload and publish runbook'
    $published = Publish-Runbook -Target $target -RunbookPath $Settings.RunbookPath

    Write-Step 5 $totalSteps 'Link schedules to the runbook'
    $scheduleNames = @($outputs.NightlyScheduleName)
    if ($times.Backstop -and $outputs.BackstopScheduleName) { $scheduleNames += $outputs.BackstopScheduleName }
    $parameterMap = New-JobScheduleParameterMap -Settings $Settings -IdentityClientId $outputs.IdentityClientId
    $linked = Set-JobScheduleLinks -Target $target -ScheduleNames $scheduleNames -Parameters $parameterMap

    $result = [pscustomobject]@{
        Deployed                   = $true
        RunbookPublished           = $published
        LinkedSchedules            = $linked
        DryRun                     = $dryRun
        ResourceGroupName          = $outputs.ResourceGroupName
        AutomationAccountName      = $outputs.AutomationAccountName
        RunbookName                = $outputs.RunbookName
        RuntimeEnvironmentName     = $outputs.RuntimeEnvironmentName
        IdentityClientId           = $outputs.IdentityClientId
        IdentityPrincipalId        = $outputs.IdentityPrincipalId
        RoleDefinitionId           = $outputs.RoleDefinitionId
        RoleAssignedAtSubscription = -not [bool]$Settings.SkipSubscriptionRoleAssignment
        NightlyScheduleName        = $outputs.NightlyScheduleName
        BackstopScheduleName       = $outputs.BackstopScheduleName
        NightlyStart               = $times.Nightly
        BackstopStart              = $times.Backstop
        RunbookParameters          = $parameterMap
    }

    Write-Step 6 $totalSteps 'Summary'
    Write-DeploymentSummary -Settings $Settings -Result $result
    return $result
}

# Dot-sourcing (for unit tests) loads the functions without deploying anything.
if ($MyInvocation.InvocationName -ne '.') {
    $settings = Resolve-DeploymentSettings -RepoRoot (Split-Path -Parent $PSScriptRoot) -Values @{
        SubscriptionId             = $SubscriptionId
        Location                   = $Location
        ResourceGroupName          = $ResourceGroupName
        NamePrefix                 = $NamePrefix
        TimeZone                   = $TimeZone
        ScheduleTime               = $ScheduleTime
        BackstopOffsetMinutes      = $BackstopOffsetMinutes
        AlertEmails                = $AlertEmails
        ScopeSubscriptionIds       = $ScopeSubscriptionIds
        ScopeManagementGroupId     = $ScopeManagementGroupId
        ScopeResourceGroupName     = $ScopeResourceGroupName
        ScopeCapacityName          = $ScopeCapacityName
        ScopeCapacityResourceId    = $ScopeCapacityResourceId
        ExcludeTagName             = $ExcludeTagName
        ExcludeTagValue            = $ExcludeTagValue
        EnableEnforcement          = [bool]$EnableEnforcement
        IncludeWritePermission     = [bool]$IncludeWritePermission
        SkipSubscriptionRoleAssignment = [bool]$SkipSubscriptionRoleAssignment
        CustomRoleName             = $CustomRoleName
        AdditionalAssignableScopes = $AdditionalAssignableScopes
        Tags                       = $Tags
        AzPackageVersion           = $AzPackageVersion
    }
    $null = Invoke-Deployment -Settings $settings
}
