#Requires -Version 7.0

<#
.SYNOPSIS
    Runs live acceptance tests against one explicitly selected TEST Fabric capacity.
.DESCRIPTION
    Tests a previously deployed Azure Automation auto-pause runbook using Azure CLI and
    ARM REST APIs. Every submitted job is restricted to CapacityResourceId. This is a
    destructive, billable test: it pauses and resumes the selected F-SKU capacity.
    Original power state and the original autopause tag are restored in finally unless
    LeaveAsIs is specified or a dispatched schedule job cannot be confirmed settled.
    Uncertain job state withholds restoration and fails closed. Other tags are preserved.
    WhatIf prints an offline plan only: no CLI, API, directory or file operations.
    Dot-sourcing loads helpers without running acceptance tests.
.PARAMETER SubscriptionId
    Subscription containing the Automation account and TEST capacity. Always passed
    explicitly to Azure CLI; the current CLI subscription is never changed.
.PARAMETER ResourceGroupName
    Resource group containing the deployed Automation account.
.PARAMETER AutomationAccountName
    Deployed Automation account name, as printed by scripts\deploy.ps1.
.PARAMETER CapacityResourceId
    Mandatory full ARM ID of the only TEST capacity that may be changed. It must be
    Microsoft.Fabric/capacities, in SubscriptionId, and have an F SKU.
.PARAMETER RunbookName
    Published runbook name. Defaults to Invoke-FabricCapacityAutoPause.
.PARAMETER UserAssignedIdentityClientId
    Attached user-assigned identity client ID. If omitted, select the single attached
    identity from the Automation account ARM response. Multiple identities require a choice.
.PARAMETER ExpectedNightlySchedule
    Existing enabled nightly schedule, linked to RunbookName. Default autopause-nightly.
.PARAMETER ExpectedTimeZone
    Expected schedule time-zone ID. Empty skips equality validation. ExpectedLocalTime
    is checked in this zone, or the schedule's actual zone when this is empty.
.PARAMETER ExpectedLocalTime
    Expected HH:mm wall-clock time of nextRun. Empty skips this check.
.PARAMETER JobTimeoutMinutes
    Maximum wait for each job, including queue time. Default 20 minutes.
.PARAMETER Scenarios
    Scenario IDs S01 through S11, or All. Default All. S01 always runs as a safety gate.
    Selected scenarios establish their own required state; earlier scenarios are not required.
.PARAMETER LeaveAsIs
    Do not restore power state or the autopause tag. Temporary schedules, request files,
    and unfinished jobs created by this invocation are still cleaned up.
.PARAMETER IncludeScheduleTrigger
    Opt in to S11. Creates and removes a uniquely named, one-time UTC schedule.
.PARAMETER ScheduleLeadMinutes
    Minimum minutes until the temporary schedule starts, rounded up to a whole UTC
    minute. Default 8; minimum 5. The service's effective start time is read back.
.PARAMETER SkipResumeScenarios
    Skip scenarios requiring Active setup/resume: S02, S03, S04, S06, S08, S09, S11.
    S05 and S07 can run without resuming. Restoration can still resume an originally
    Active capacity; this switch is not a prohibition on finally-block restoration.
.PARAMETER ResultPath
    Results directory, or explicit .json filename. Default is the TEMP environment
    variable, falling back to the current directory when TEMP is not defined.
    Unique JSON request files are created beside the report and deleted in finally.
.EXAMPLE
    .\tests\uat\Invoke-AutoPauseUat.ps1 -SubscriptionId '<subscription-id>' `
        -ResourceGroupName '<automation-resource-group>' -AutomationAccountName '<automation-account>' `
        -CapacityResourceId '<test-capacity-arm-resource-id>' -WhatIf
.EXAMPLE
    .\tests\uat\Invoke-AutoPauseUat.ps1 -SubscriptionId '<subscription-id>' `
        -ResourceGroupName '<automation-resource-group>' -AutomationAccountName '<automation-account>' `
        -CapacityResourceId '<test-capacity-arm-resource-id>' -IncludeScheduleTrigger `
        -ResultPath '.\uat-results'
.NOTES
    Requires PowerShell 7+, az login, Automation job/schedule permissions, capacity
    read/write/suspend/resume rights, Activity Log read, and role-definition/assignment read.
    The caller's resume permission is distinct from the runbook identity's suspend-only role.
    No live API behavior is verified by simply parsing or dot-sourcing this script.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('\A[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\z')]
    [string] $SubscriptionId,

    [Parameter(Mandatory)]
    [ValidatePattern('\A[A-Za-z0-9_.()\-]{1,90}\z')]
    [string] $ResourceGroupName,

    [Parameter(Mandatory)]
    [ValidatePattern('\A[A-Za-z0-9_\-]{1,50}\z')]
    [string] $AutomationAccountName,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string] $CapacityResourceId,

    [ValidateNotNullOrEmpty()]
    [string] $RunbookName = 'Invoke-FabricCapacityAutoPause',

    [string] $UserAssignedIdentityClientId = '',
    [ValidateNotNullOrEmpty()]
    [string] $ExpectedNightlySchedule = 'autopause-nightly',
    [string] $ExpectedTimeZone = '',
    [ValidatePattern('\A(?:|(?:[01][0-9]|2[0-3]):[0-5][0-9])\z')]
    [string] $ExpectedLocalTime = '',
    [ValidateRange(1, 120)]
    [int] $JobTimeoutMinutes = 20,
    [ValidateSet('All', 'S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'S07', 'S08', 'S09', 'S10', 'S11')]
    [string[]] $Scenarios = @('All'),
    [switch] $LeaveAsIs,
    [switch] $IncludeScheduleTrigger,
    [ValidateRange(5, 1440)]
    [int] $ScheduleLeadMinutes = 8,
    [switch] $SkipResumeScenarios,
    [string] $ResultPath = $env:TEMP
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-UatValue {
    param($InputObject, [Parameter(Mandatory)] [string[]] $Path)
    $current = $InputObject
    foreach ($part in $Path) {
        if ($null -eq $current) { return $null }
        if ($current -is [System.Collections.IDictionary]) {
            if (-not $current.Contains($part)) { return $null }
            $current = $current[$part]
        }
        else {
            $property = $current.PSObject.Properties[$part]
            if ($null -eq $property) { return $null }
            $current = $property.Value
        }
    }
    return $current
}

function Get-UatNow { return [DateTimeOffset]::UtcNow }

function Get-UatScheduleStartTime {
    param(
        [ValidateRange(5, 1440)] [int] $LeadMinutes = 8,
        [DateTimeOffset] $Now = (Get-UatNow)
    )
    $earliest = $Now.ToUniversalTime().AddMinutes($LeadMinutes)
    $remainder = $earliest.Ticks % [TimeSpan]::TicksPerMinute
    if ($remainder) { $earliest = $earliest.AddTicks([TimeSpan]::TicksPerMinute - $remainder) }
    return $earliest
}

function Wait-UatPoll {
    param([int] $Seconds = 15)
    Start-Sleep -Seconds $Seconds
}

function Protect-UatText {
    param([AllowEmptyString()] [string] $Text)
    $safe = $Text -replace '(?i)Bearer\s+\S+', 'Bearer [REDACTED]'
    $safe = $safe -replace '(?i)((?:access[_-]?token|refresh[_-]?token|client[_-]?secret|password)\s*["'']?\s*[:=]\s*["'']?)[^"''\s,;}]+', '$1[REDACTED]'
    $safe = $safe -replace '\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b', '[REDACTED]'
    return $safe
}

function Assert-Uat {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function ConvertTo-UatTags {
    param($Tags)
    $table = @{}
    if ($null -eq $Tags) { return $table }
    if ($Tags -is [System.Collections.IDictionary]) {
        foreach ($key in $Tags.Keys) { $table[[string]$key] = [string]$Tags[$key] }
    }
    else {
        foreach ($property in $Tags.PSObject.Properties) { $table[$property.Name] = [string]$property.Value }
    }
    return $table
}

function Invoke-AzProcess {
    <# Only native-process seam. Do not expose CLI stderr: it may contain credentials. #>
    param([Parameter(Mandatory)] [string[]] $Arguments)
    $ErrorActionPreference = 'Continue'
    $PSNativeCommandUseErrorActionPreference = $false
    $lines = @(& az @Arguments 2>&1)
    $exitCode = $LASTEXITCODE
    return [pscustomobject]@{ ExitCode = $exitCode; Text = ($lines -join "`n") }
}

function Invoke-AzCli {
    param(
        [Parameter(Mandatory)] $Context,
        [Parameter(Mandatory)] [string[]] $Arguments,
        [int] $MaxAttempts = 5
    )
    Assert-Uat (-not ($Arguments -contains '--subscription')) 'Subscription is supplied by the CLI wrapper only.'
    $allArguments = @($Arguments) + @('--subscription', $Context.SubscriptionId, '--only-show-errors', '--output', 'json')
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        $response = Invoke-AzProcess -Arguments $allArguments
        if ($response.ExitCode -eq 0) {
            if ([string]::IsNullOrWhiteSpace($response.Text)) { return $null }
            try { return ($response.Text | ConvertFrom-Json -Depth 100) }
            catch { throw 'Azure CLI returned an invalid JSON response (response omitted).' }
        }
        $transient = $response.Text -match '(?i)(\b429\b|\b5[0-9]{2}\b|TooManyRequests|InternalServerError|BadGateway|ServiceUnavailable|GatewayTimeout)'
        if ($transient -and $attempt -lt $MaxAttempts) {
            Wait-UatPoll -Seconds ([int][Math]::Min(60, [Math]::Pow(2, $attempt)))
            continue
        }
        $exception = [InvalidOperationException]::new("Azure CLI request failed (exit $($response.ExitCode)); CLI output omitted.")
        $exception.Data['NotFound'] = ($response.Text -match '(?i)(\b404\b|ResourceNotFound|NotFound)')
        throw $exception
    }
}

function New-UatRequestFile {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] $Body)
    $path = Join-Path $Context.RequestDirectory ("request-{0}.json" -f [guid]::NewGuid().ToString('N'))
    try {
        $null = New-Item -ItemType Directory -Path $Context.RequestDirectory -Force
        $Body | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $path -Encoding utf8NoBOM
        return $path
    }
    catch {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
        throw
    }
}

function Invoke-UatRest {
    param(
        [Parameter(Mandatory)] $Context,
        [Parameter(Mandatory)] [ValidateSet('GET', 'PUT', 'POST', 'PATCH', 'DELETE')] [string] $Method,
        [Parameter(Mandatory)] [string] $Url,
        $Body
    )
    $uri = [uri]$Url
    Assert-Uat ($uri.Scheme -eq 'https' -and $uri.Host -eq 'management.azure.com') 'Unexpected ARM endpoint.'
    $arguments = @('rest', '--method', $Method, '--url', $Url)
    $file = $null
    try {
        if ($PSBoundParameters.ContainsKey('Body')) {
            $file = New-UatRequestFile -Context $Context -Body $Body
            $arguments += @('--headers', 'Content-Type=application/json', '--body', "@$file")
        }
        return Invoke-AzCli -Context $Context -Arguments $arguments
    }
    finally {
        if ($file -and (Test-Path -LiteralPath $file)) { Remove-Item -LiteralPath $file -Force }
    }
}

function Get-UatCollection {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] [string] $Url)
    $seen = @{}
    while ($Url) {
        Assert-Uat (-not $seen.ContainsKey($Url)) 'ARM returned a repeated pagination link.'
        $seen[$Url] = $true
        $page = Invoke-UatRest -Context $Context -Method GET -Url $Url
        foreach ($item in @(Get-UatValue $page @('value'))) {
            if ($null -ne $item) { Write-Output $item }
        }
        $Url = [string](Get-UatValue $page @('nextLink'))
    }
}

function Get-AutomationUrl {
    param([Parameter(Mandatory)] $Context, [string] $Child = '')
    return "https://management.azure.com$($Context.AutomationResourceId)$Child`?api-version=2024-10-23"
}

function Get-CapacityUrl {
    param([Parameter(Mandatory)] $Context, [string] $Action = '')
    return "https://management.azure.com$($Context.CapacityResourceId)$Action`?api-version=2023-11-01"
}

function Get-CapacityState {
    param([Parameter(Mandatory)] $Context)
    $capacity = Invoke-UatRest -Context $Context -Method GET -Url (Get-CapacityUrl $Context)
    Assert-Uat ([string](Get-UatValue $capacity @('id')) -ieq $Context.CapacityResourceId) 'ARM returned a different capacity resource ID.'
    $state = [string](Get-UatValue $capacity @('properties', 'state'))
    if ($state -ieq 'Suspended') { $state = 'Paused' }
    return [pscustomobject]@{
        State = $state
        Tags = ConvertTo-UatTags (Get-UatValue $capacity @('tags'))
        Sku = [string](Get-UatValue $capacity @('sku', 'name'))
        Name = [string](Get-UatValue $capacity @('name'))
        FabricId = [string](Get-UatValue $capacity @('properties', 'fabricCapacityId'))
    }
}

function Assert-TestCapacity {
    param([Parameter(Mandatory)] $Context)
    Assert-Uat $Context.Validated 'Preconditions have not authorized mutations on the TEST capacity.'
    $capacity = Get-CapacityState $Context
    Assert-Uat ($capacity.Sku -match '\AF[1-9][0-9]*\z') 'Refusing to change a non-F-SKU capacity.'
    return $capacity
}

function Set-CapacityTags {
    <# PATCH a merged tag map; only the named tag is changed or removed. #>
    param(
        [Parameter(Mandatory)] $Context,
        [string] $Name = 'autopause',
        [AllowEmptyString()] [string] $Value = '',
        [switch] $Remove
    )
    $capacity = Assert-TestCapacity $Context
    $tags = $capacity.Tags
    if ($Remove) {
        if (-not $tags.ContainsKey($Name)) { return }
        $tags.Remove($Name)
    }
    else { $tags[$Name] = $Value }
    $Context.TagTouched = $true
    $null = Invoke-UatRest -Context $Context -Method PATCH -Url (Get-CapacityUrl $Context) -Body @{ tags = $tags }
    $actual = (Get-CapacityState $Context).Tags
    if ($Remove) { Assert-Uat (-not $actual.ContainsKey($Name)) "Tag '$Name' was not removed." }
    else { Assert-Uat ($actual.ContainsKey($Name) -and $actual[$Name] -ceq $Value) "Tag '$Name' did not match after PATCH." }
}

function Wait-CapacityState {
    param(
        [Parameter(Mandatory)] $Context,
        [Parameter(Mandatory)] [ValidateSet('Active', 'Paused')] [string] $State,
        [double] $TimeoutMinutes = 15
    )
    $deadline = (Get-UatNow).AddMinutes($TimeoutMinutes)
    do {
        $actual = (Get-CapacityState $Context).State
        if ($actual -ieq $State) { return $actual }
        if ((Get-UatNow) -ge $deadline) { break }
        Wait-UatPoll
    } while ($true)
    throw "Capacity did not reach $State within $TimeoutMinutes minutes (last state: $actual)."
}

function Resume-Capacity {
    param([Parameter(Mandatory)] $Context)
    $capacity = Assert-TestCapacity $Context
    if ($capacity.State -eq 'Active') { return }
    if ($capacity.State -notin @('Paused', 'Resuming')) {
        $null = Wait-CapacityState -Context $Context -State Paused
        $capacity = Get-CapacityState $Context
    }
    if ($capacity.State -ne 'Resuming') {
        $null = Invoke-UatRest -Context $Context -Method POST -Url (Get-CapacityUrl $Context '/resume')
    }
    $null = Wait-CapacityState -Context $Context -State Active
}

function Suspend-Capacity {
    param([Parameter(Mandatory)] $Context)
    $capacity = Assert-TestCapacity $Context
    if ($capacity.State -eq 'Paused') { return }
    if ($capacity.State -notin @('Active', 'Pausing', 'Suspending')) {
        $null = Wait-CapacityState -Context $Context -State Active
        $capacity = Get-CapacityState $Context
    }
    if ($capacity.State -notin @('Pausing', 'Suspending')) {
        $null = Invoke-UatRest -Context $Context -Method POST -Url (Get-CapacityUrl $Context '/suspend')
    }
    $null = Wait-CapacityState -Context $Context -State Paused
}

function New-RunbookParameters {
    param([Parameter(Mandatory)] $Context, [hashtable] $Parameters = @{})
    $values = @{
        CapacityResourceId = $Context.CapacityResourceId
        SubscriptionIds = $Context.SubscriptionId
        UserAssignedIdentityClientId = $Context.IdentityClientId
        ExcludeTagName = 'autopause'
        ExcludeTagValue = 'skip'
        DryRun = 'true'
    }
    foreach ($key in $Parameters.Keys) {
        Assert-Uat ($key -notin @('CapacityResourceId', 'SubscriptionIds', 'UserAssignedIdentityClientId', 'ManagementGroupId')) "The job scope/identity parameter '$key' cannot be overridden."
        $values[$key] = [string]$Parameters[$key]
    }
    return $values
}

function Add-TrackedJob {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] [string] $JobId, [string] $Source = 'Manual')
    $existing = @($Context.Jobs | Where-Object { $_.JobId -eq $JobId })
    if ($existing.Count -eq 0) {
        $Context.Jobs.Add([pscustomobject]@{
            JobId = $JobId; Scenario = $Context.CurrentScenario; Source = $Source
            RequestedAt = (Get-UatNow).ToString('o'); Status = 'Unknown'; Output = ''
        })
    }
}

function Start-RunbookJob {
    param([Parameter(Mandatory)] $Context, [hashtable] $Parameters = @{})
    $null = Assert-TestCapacity $Context
    $values = New-RunbookParameters -Context $Context -Parameters $Parameters
    $jobId = [guid]::NewGuid().ToString()
    # Track before PUT: an accepted request may lose its response.
    Add-TrackedJob -Context $Context -JobId $jobId
    $body = @{ properties = @{ runbook = @{ name = $Context.RunbookName }; parameters = $values } }
    $null = Invoke-UatRest -Context $Context -Method PUT -Url (Get-AutomationUrl $Context "/jobs/$jobId") -Body $body
    Write-Information "Started $($Context.CurrentScenario) job $jobId" -InformationAction Continue
    return $jobId
}

function Wait-RunbookJob {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] [string] $JobId, [double] $TimeoutMinutes = $Context.JobTimeoutMinutes)
    $deadline = (Get-UatNow).AddMinutes($TimeoutMinutes)
    do {
        $job = Invoke-UatRest -Context $Context -Method GET -Url (Get-AutomationUrl $Context "/jobs/$JobId")
        $status = [string](Get-UatValue $job @('properties', 'status'))
        foreach ($tracked in $Context.Jobs) {
            if ($tracked.JobId -eq $JobId) { $tracked.Status = $status }
        }
        if ($status -in @('Completed', 'Failed', 'Stopped', 'Suspended')) { return $status }
        if ((Get-UatNow) -ge $deadline) { return 'TimedOut' }
        Wait-UatPoll
    } while ($true)
}

function ConvertFrom-UatStreamValue {
    param([AllowNull()] $Value, [int] $Depth = 0)
    if ($null -eq $Value -or $Depth -ge 16) { return '' }
    if ($Value -is [string]) {
        if ([string]::IsNullOrWhiteSpace($Value)) { return '' }
        try {
            $decoded = ConvertFrom-Json -InputObject $Value -Depth 32 -NoEnumerate -ErrorAction Stop
        }
        catch { return $Value }
        return ConvertFrom-UatStreamValue -Value $decoded -Depth ($Depth + 1)
    }
    if ($Value -is [System.Collections.IEnumerable] -and $Value -isnot [System.Collections.IDictionary]) {
        $parts = foreach ($item in $Value) { ConvertFrom-UatStreamValue -Value $item -Depth ($Depth + 1) }
        return ($parts -join "`n")
    }
    foreach ($field in @('Message', 'Text', 'value')) {
        $text = ConvertFrom-UatStreamValue -Value (Get-UatValue $Value @($field)) -Depth ($Depth + 1)
        if (-not [string]::IsNullOrWhiteSpace($text)) { return $text }
    }
    return ''
}

function Get-RunbookJobOutput {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] [string] $JobId)
    $texts = [System.Collections.Generic.List[string]]::new()
    $streams = @(Get-UatCollection -Context $Context -Url (Get-AutomationUrl $Context "/jobs/$JobId/streams"))
    foreach ($stream in $streams) {
        $properties = Get-UatValue $stream @('properties')
        $type = [string](Get-UatValue $properties @('streamType'))
        if ($type -notin @('Output', 'Warning', 'Error')) { continue }
        $streamId = [string](Get-UatValue $properties @('jobStreamId'))
        if (-not $streamId) { $streamId = [string](Get-UatValue $stream @('name')) }
        Assert-Uat (-not [string]::IsNullOrWhiteSpace($streamId)) 'Job stream ID is missing.'
        $detail = Invoke-UatRest -Context $Context -Method GET -Url (Get-AutomationUrl $Context "/jobs/$JobId/streams/$([uri]::EscapeDataString($streamId))")
        $text = [string](Get-UatValue $detail @('properties', 'streamText'))
        if ([string]::IsNullOrWhiteSpace($text)) { $text = [string](Get-UatValue $detail @('properties', 'summary')) }
        if ([string]::IsNullOrWhiteSpace($text)) { $text = [string](Get-UatValue $properties @('summary')) }
        if ([string]::IsNullOrWhiteSpace($text)) { $text = ConvertFrom-UatStreamValue (Get-UatValue $detail @('properties', 'value')) }
        if ([string]::IsNullOrWhiteSpace($text)) { $text = ConvertFrom-UatStreamValue (Get-UatValue $properties @('value')) }
        if ($text) { $texts.Add("[$type] $text") }
    }
    # Input validation can fail before any stream exists.
    $job = Invoke-UatRest -Context $Context -Method GET -Url (Get-AutomationUrl $Context "/jobs/$JobId")
    foreach ($field in @('exception', 'statusDetails')) {
        $text = [string](Get-UatValue $job @('properties', $field))
        if ($text) { $texts.Add($text) }
    }
    return Protect-UatText ($texts -join "`n")
}

function Get-UatSettledJobOutput {
    param(
        [Parameter(Mandatory)] $Context,
        [string] $JobId,
        [ValidateNotNullOrEmpty()] [string] $OutputPattern = '(?im)^\s*(?:\[Output\]\s*)?Summary:'
    )
    $deadline = (Get-UatNow).AddSeconds(60)
    do {
        $output = Get-RunbookJobOutput -Context $Context -JobId $JobId
        if ($output -match $OutputPattern -or (Get-UatNow) -ge $deadline) { break }
        Wait-UatPoll -Seconds 5
    } while ($true)
    foreach ($tracked in $Context.Jobs) {
        if ($tracked.JobId -eq $JobId) { $tracked.Output = $output }
    }
    return $output
}

function Invoke-ScenarioJob {
    param(
        [Parameter(Mandatory)] $Context,
        [hashtable] $Parameters = @{},
        [string] $ExpectedStatus = 'Completed',
        [ValidateNotNullOrEmpty()] [string] $OutputPattern = '(?im)^\s*(?:\[Output\]\s*)?Summary:'
    )
    $jobId = Start-RunbookJob -Context $Context -Parameters $Parameters
    $status = Wait-RunbookJob -Context $Context -JobId $jobId
    $output = Get-UatSettledJobOutput -Context $Context -JobId $jobId -OutputPattern $OutputPattern
    Assert-Uat ($status -eq $ExpectedStatus) "Job $jobId status $status; expected $ExpectedStatus."
    Assert-Uat ($output -match $OutputPattern) "Job $jobId output did not match '$OutputPattern'. See its recorded streams."
    return [pscustomobject]@{ JobId = $jobId; Status = $status; Output = $output }
}

function Get-ActivityLogEvents {
    param([Parameter(Mandatory)] $Context, [DateTimeOffset] $Since = (Get-UatNow).AddHours(-2))
    $events = @(Invoke-AzCli -Context $Context -Arguments @('monitor', 'activity-log', 'list', '--resource-id', $Context.CapacityResourceId, '--offset', '2h'))
    foreach ($logEvent in $events) {
        $operation = [string](Get-UatValue $logEvent @('operationName', 'value'))
        $timestamp = [string](Get-UatValue $logEvent @('eventTimestamp'))
        if ($operation -notmatch '(?i)(suspend|resume)' -or -not $timestamp) { continue }
        if ([DateTimeOffset]::Parse($timestamp) -lt $Since) { continue }
        $caller = [string](Get-UatValue $logEvent @('caller'))
        $claims = Get-UatValue $logEvent @('claims')
        $principal = [string](Get-UatValue $claims @('http://schemas.microsoft.com/identity/claims/objectidentifier'))
        if (-not $principal) { $principal = [string](Get-UatValue $claims @('oid')) }
        $application = [string](Get-UatValue $claims @('appid'))
        # Callers may be personal sign-in names; only report non-secret GUID identities.
        $callerGuid = ''
        $parsedGuid = [guid]::Empty
        if ([guid]::TryParse($caller, [ref]$parsedGuid)) { $callerGuid = $parsedGuid.ToString() }
        if (-not [guid]::TryParse($principal, [ref]$parsedGuid)) { $principal = '' }
        if (-not [guid]::TryParse($application, [ref]$parsedGuid)) { $application = '' }
        $attributable = ($callerGuid -in @($Context.IdentityPrincipalId, $Context.IdentityClientId)) -or
            ($principal -eq $Context.IdentityPrincipalId -and $principal) -or
            ($application -eq $Context.IdentityClientId -and $application)
        Write-Output ([pscustomobject]@{
            Operation = $operation; Timestamp = $timestamp; Caller = $callerGuid
            PrincipalId = $principal; ApplicationId = $application
            Status = [string](Get-UatValue $logEvent @('status', 'value'))
            Attributable = [bool]$attributable
        })
    }
}

function New-UatResult {
    param(
        [string] $Id, [string] $Name,
        [ValidateSet('PASS', 'FAIL', 'WARN', 'SKIPPED')] [string] $Status = 'PASS',
        [string] $Evidence = '', [string] $Detail = ''
    )
    return [pscustomobject]@{
        Id = $Id; Name = $Name; Passed = ($Status -eq 'PASS'); Status = $Status
        Evidence = Protect-UatText $Evidence; Detail = Protect-UatText $Detail
    }
}

function Get-UatScenarioPlan {
    return @(
        [pscustomobject]@{ Id = 'S01'; Name = 'Preconditions'; RequiresResume = $false }
        [pscustomobject]@{ Id = 'S02'; Name = 'Dry run'; RequiresResume = $true }
        [pscustomobject]@{ Id = 'S03'; Name = 'Exclusion tag'; RequiresResume = $true }
        [pscustomobject]@{ Id = 'S04'; Name = 'Enforcement'; RequiresResume = $true }
        [pscustomobject]@{ Id = 'S05'; Name = 'Idempotency'; RequiresResume = $false }
        [pscustomobject]@{ Id = 'S06'; Name = 'Scope narrowing'; RequiresResume = $true }
        [pscustomobject]@{ Id = 'S07'; Name = 'Invalid input is rejected'; RequiresResume = $false }
        [pscustomobject]@{ Id = 'S08'; Name = 'Resume and re-pause'; RequiresResume = $true }
        [pscustomobject]@{ Id = 'S09'; Name = 'Fabric-side visibility'; RequiresResume = $true }
        [pscustomobject]@{ Id = 'S10'; Name = 'Least privilege proof'; RequiresResume = $false }
        [pscustomobject]@{ Id = 'S11'; Name = 'Schedule trigger'; RequiresResume = $true }
    )
}

function Resolve-UatIdentity {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] $Account)
    $identities = ConvertTo-UatIdentityList (Get-UatValue $Account @('identity', 'userAssignedIdentities'))
    $selectedIdentities = @($identities | Where-Object {
        -not $Context.IdentityClientId -or $_.ClientId -ieq $Context.IdentityClientId
    })
    Assert-Uat ($selectedIdentities.Count -eq 1) 'Select exactly one attached user-assigned identity with -UserAssignedIdentityClientId.'
    $selected = $selectedIdentities[0]
    $parsedGuid = [guid]::Empty
    Assert-Uat ([guid]::TryParse($selected.ClientId, [ref]$parsedGuid)) 'Attached identity clientId is missing or invalid.'
    Assert-Uat ([guid]::TryParse($selected.PrincipalId, [ref]$parsedGuid)) 'Attached identity principalId is missing or invalid.'
    $Context.IdentityClientId = $selected.ClientId
    $Context.IdentityPrincipalId = $selected.PrincipalId
}

function ConvertTo-UatIdentityList {
    param($Identities)
    if ($null -eq $Identities) { return }
    $names = if ($Identities -is [System.Collections.IDictionary]) { @($Identities.Keys) } else { @($Identities.PSObject.Properties.Name) }
    foreach ($name in $names) {
        $identity = Get-UatValue $Identities @([string]$name)
        Write-Output ([pscustomobject]@{
            ClientId = [string](Get-UatValue $identity @('clientId'))
            PrincipalId = [string](Get-UatValue $identity @('principalId'))
        })
    }
}

function Invoke-UatS01 {
    param([Parameter(Mandatory)] $Context)
    $capacity = Get-CapacityState $Context
    Assert-Uat ($capacity.Sku -match '\AF[1-9][0-9]*\z') "TEST capacity must have an F SKU; found '$($capacity.Sku)'."
    Assert-Uat ($capacity.State -in @('Active', 'Paused')) "Capacity must initially be stable Active or Paused; found '$($capacity.State)'."
    $Context.OriginalCapacity = $capacity
    $account = Invoke-UatRest -Context $Context -Method GET -Url (Get-AutomationUrl $Context)
    Assert-Uat ($null -ne $account) 'Automation account was not found.'
    Resolve-UatIdentity -Context $Context -Account $account
    $runbook = Invoke-UatRest -Context $Context -Method GET -Url (Get-AutomationUrl $Context "/runbooks/$([uri]::EscapeDataString($Context.RunbookName))")
    Assert-Uat ([string](Get-UatValue $runbook @('properties', 'state')) -eq 'Published') 'Runbook must be Published.'
    $schedule = Invoke-UatRest -Context $Context -Method GET -Url (Get-AutomationUrl $Context "/schedules/$([uri]::EscapeDataString($Context.ExpectedNightlySchedule))")
    Assert-Uat ((Get-UatValue $schedule @('properties', 'isEnabled')) -eq $true) 'Nightly schedule must be enabled.'
    $links = @(Get-UatCollection -Context $Context -Url (Get-AutomationUrl $Context '/jobSchedules'))
    $linked = @($links | Where-Object {
        [string](Get-UatValue $_ @('properties', 'runbook', 'name')) -eq $Context.RunbookName -and
        [string](Get-UatValue $_ @('properties', 'schedule', 'name')) -eq $Context.ExpectedNightlySchedule
    })
    Assert-Uat ($linked.Count -gt 0) 'Nightly schedule is not linked to the runbook.'
    $zone = [string](Get-UatValue $schedule @('properties', 'timeZone'))
    if ($Context.ExpectedTimeZone) {
        Assert-Uat ($zone -ceq $Context.ExpectedTimeZone) "Nightly schedule time zone '$zone' does not match the expected zone."
    }
    $nextRun = [string](Get-UatValue $schedule @('properties', 'nextRun'))
    $localTime = ''
    if ($Context.ExpectedLocalTime) {
        Assert-Uat (-not [string]::IsNullOrWhiteSpace($nextRun)) 'Nightly schedule has no nextRun.'
        $timeZone = [TimeZoneInfo]::FindSystemTimeZoneById($zone)
        $localTime = [TimeZoneInfo]::ConvertTime([DateTimeOffset]::Parse($nextRun), $timeZone).ToString('HH:mm')
        Assert-Uat ($localTime -eq $Context.ExpectedLocalTime) "Nightly nextRun local time '$localTime' does not match the expected time."
    }
    $Context.Validated = $true
    return New-UatResult S01 'Preconditions' -Evidence "SKU=$($capacity.Sku); original=$($capacity.State); Published; enabled/linked schedule; zone=$zone; nextRun=$nextRun; local=$localTime"
}

function Initialize-ActiveTestCapacity {
    param([Parameter(Mandatory)] $Context)
    Resume-Capacity $Context
    Set-CapacityTags -Context $Context -Remove
}

function Assert-JobDecision {
    param([Parameter(Mandatory)] $Job, [string[]] $Decision)
    # Anchor on the runbook's summary so "Paused" cannot match "WouldPause"/"PriorState".
    $summary = [regex]::Match($Job.Output, '(?im)Summary:\s*[^\r\n]*').Value
    $counts = @([regex]::Matches($summary, '\b([A-Za-z]+)=([0-9]+)\b') | Where-Object { [int]$_.Groups[2].Value -gt 0 })
    Assert-Uat ($counts.Count -eq 1 -and $counts[0].Groups[1].Value -in $Decision -and $counts[0].Groups[2].Value -eq '1') "Job $($Job.JobId) did not report exactly one $($Decision -join '/') result."
    Assert-Uat ($Job.Output -notmatch '(?im)Summary:\s*[^\r\n]*\b(?:Error|Denied|Deferred|Warning)=[1-9]') "Job $($Job.JobId) reported an error, denial, deferral or warning."
}

function Invoke-UatS02 {
    param([Parameter(Mandatory)] $Context)
    Initialize-ActiveTestCapacity $Context
    $job = Invoke-ScenarioJob -Context $Context -Parameters @{ DryRun = 'true' }
    Assert-JobDecision $job WouldPause
    Assert-Uat ((Get-CapacityState $Context).State -eq 'Active') 'Dry run changed the capacity power state.'
    return New-UatResult S02 'Dry run' -Evidence "Job=$($job.JobId); Completed; WouldPause=1; still Active"
}

function Invoke-UatS03 {
    param([Parameter(Mandatory)] $Context)
    Initialize-ActiveTestCapacity $Context
    try {
        Set-CapacityTags -Context $Context -Value 'skip'
        $job = Invoke-ScenarioJob -Context $Context -Parameters @{ DryRun = 'false' }
        Assert-JobDecision $job Excluded
        Assert-Uat ((Get-CapacityState $Context).State -eq 'Active') 'Excluded capacity was not left Active.'
        return New-UatResult S03 'Exclusion tag' -Evidence "Job=$($job.JobId); Excluded=1; still Active"
    }
    finally { Set-CapacityTags -Context $Context -Remove }
}

function Invoke-UatS04 {
    param([Parameter(Mandatory)] $Context)
    Initialize-ActiveTestCapacity $Context
    $since = Get-UatNow
    $job = Invoke-ScenarioJob -Context $Context -Parameters @{ DryRun = 'false' }
    Assert-JobDecision $job @('Paused', 'PauseInProgress')
    $null = Wait-CapacityState -Context $Context -State Paused
    if ($job.Output -match '(?im)Summary:\s*[^\r\n]*\bPauseInProgress=1\b') {
        return New-UatResult S04 'Enforcement' -Status WARN -Evidence "Job=$($job.JobId); PauseInProgress=1; ARM=Paused" `
            -Detail 'An existing pause completed; no new suspend request or attributable event is required for PauseInProgress.'
    }
    $deadline = (Get-UatNow).AddMinutes(5)
    $logDetail = 'No attributable successful suspend event visible after five minutes.'
    do {
        try {
            $events = @(Get-ActivityLogEvents -Context $Context -Since $since | Where-Object {
                $_.Operation -match 'suspend' -and $_.Attributable -and $_.Status -eq 'Succeeded'
            })
            if ($events.Count -gt 0) {
                $logEvent = $events[0]
                return New-UatResult S04 'Enforcement' -Evidence "Job=$($job.JobId); Paused=1; ARM=Paused; caller=$($logEvent.Caller); principal=$($logEvent.PrincipalId); application=$($logEvent.ApplicationId)"
            }
        }
        catch { $logDetail = 'Activity Log could not be read; pause assertions succeeded. Check caller permissions and propagation.' }
        if ((Get-UatNow) -ge $deadline) { break }
        Wait-UatPoll -Seconds 30
    } while ($true)
    return New-UatResult S04 'Enforcement' -Status WARN -Evidence "Job=$($job.JobId); Paused=1; ARM=Paused" -Detail $logDetail
}

function Initialize-PausedTestCapacity {
    param([Parameter(Mandatory)] $Context, [switch] $PassThru)
    Set-CapacityTags -Context $Context -Remove
    $capacity = Get-CapacityState $Context
    if ($capacity.State -eq 'Paused') { return }
    Assert-Uat ($capacity.State -in @('Active', 'Pausing', 'Suspending')) 'Active, Paused or an in-progress pause is required for paused setup.'
    $job = Invoke-ScenarioJob -Context $Context -Parameters @{ DryRun = 'false' }
    Assert-JobDecision $job @('Paused', 'PauseInProgress')
    $null = Wait-CapacityState -Context $Context -State Paused
    if ($PassThru) {
        $decision = if ($job.Output -match '(?im)Summary:\s*[^\r\n]*\bPauseInProgress=1\b') { 'PauseInProgress (existing pause)' } else { 'Paused' }
        return "Setup job=$($job.JobId); result=$decision; ARM=Paused. "
    }
}

function Invoke-UatS05 {
    param([Parameter(Mandatory)] $Context)
    $setupEvidence = Initialize-PausedTestCapacity -Context $Context -PassThru
    $job = Invoke-ScenarioJob -Context $Context -Parameters @{ DryRun = 'false' }
    Assert-JobDecision $job Skipped
    Assert-Uat ((Get-CapacityState $Context).State -eq 'Paused') 'Idempotency job did not leave the capacity Paused.'
    return New-UatResult S05 'Idempotency' -Evidence "${setupEvidence}Job=$($job.JobId); Skipped=1; still Paused"
}

function Invoke-UatS06 {
    param([Parameter(Mandatory)] $Context)
    Initialize-ActiveTestCapacity $Context
    $nonMatch = 'zzznoexist'
    if ($Context.CapacityName -eq $nonMatch) { $nonMatch = 'zzznoexistother' }
    $errorText = 'The requested capacity was not found, or the identity cannot read it.'
    $job = Invoke-ScenarioJob -Context $Context -Parameters @{ DryRun = 'false'; CapacityName = $nonMatch } `
        -ExpectedStatus Failed -OutputPattern ([regex]::Escape($errorText))
    Assert-Uat ($job.Output -notmatch '(?im)Summary:') 'Scope-narrowing job unexpectedly reported a summary after target lookup failed.'
    Assert-Uat ((Get-CapacityState $Context).State -eq 'Active') 'Scope-narrowing job changed the test capacity.'
    return New-UatResult S06 'Scope narrowing' -Evidence "Job=$($job.JobId); Failed; $errorText No Summary; still Active"
}

function Invoke-UatS07 {
    param([Parameter(Mandatory)] $Context)
    $before = (Get-CapacityState $Context).State
    $job = Invoke-ScenarioJob -Context $Context -Parameters @{ DryRun = 'maybe' } -ExpectedStatus Failed -OutputPattern '(?i)Invalid\s+DryRun'
    Assert-Uat ((Get-CapacityState $Context).State -eq $before) 'Invalid input job changed the capacity state.'
    return New-UatResult S07 'Invalid input is rejected' -Evidence "Job=$($job.JobId); Failed; Invalid DryRun; state unchanged ($before)"
}

function Invoke-UatS08 {
    param([Parameter(Mandatory)] $Context)
    Initialize-PausedTestCapacity $Context
    Initialize-ActiveTestCapacity $Context
    $job = Invoke-ScenarioJob -Context $Context -Parameters @{ DryRun = 'false' }
    Assert-JobDecision $job Paused
    $null = Wait-CapacityState -Context $Context -State Paused
    return New-UatResult S08 'Resume and re-pause' -Evidence "Paused -> Active -> Paused; Job=$($job.JobId); Paused=1"
}

function Invoke-FabricRead {
    param([Parameter(Mandatory)] [string] $Url, [Parameter(Mandatory)] [string] $AccessToken)
    $uri = [uri]$Url
    Assert-Uat ($uri.Scheme -eq 'https' -and $uri.Host -eq 'api.fabric.microsoft.com') 'Unexpected Fabric endpoint.'
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            return Invoke-RestMethod -Method Get -Uri $Url -Headers @{ Authorization = "Bearer $AccessToken" } -TimeoutSec 60
        }
        catch {
            $response = Get-UatValue $_.Exception @('Response')
            $status = Get-UatValue $response @('StatusCode')
            if ($null -ne $status -and ([int]$status -eq 429 -or [int]$status -ge 500) -and $attempt -lt 5) {
                Wait-UatPoll -Seconds ([int][Math]::Pow(2, $attempt))
                continue
            }
            throw 'Fabric API unavailable or unauthorized (response omitted).'
        }
    }
}

function Get-FabricCapacityVisibility {
    param([Parameter(Mandatory)] $Context)
    $tokenResponse = Invoke-AzCli -Context $Context -Arguments @('account', 'get-access-token', '--resource', 'https://api.fabric.microsoft.com')
    $token = [string](Get-UatValue $tokenResponse @('accessToken'))
    Assert-Uat (-not [string]::IsNullOrEmpty($token)) 'Fabric access token was not returned.'
    $url = 'https://api.fabric.microsoft.com/v1/capacities'
    $seen = @{}
    try {
        do {
            Assert-Uat (-not $seen.ContainsKey($url)) 'Fabric returned a repeated continuation URI.'
            $seen[$url] = $true
            $page = Invoke-FabricRead -Url $url -AccessToken $token
            foreach ($capacity in @(Get-UatValue $page @('value'))) {
                if ($null -eq $capacity) { continue }
                $id = [string](Get-UatValue $capacity @('id'))
                $name = [string](Get-UatValue $capacity @('displayName'))
                if ($name -ieq $Context.CapacityName -or
                    ($Context.OriginalCapacity.FabricId -and $id -ieq $Context.OriginalCapacity.FabricId) -or
                    $id -ieq $Context.CapacityResourceId) {
                    return "Fabric state=$([string](Get-UatValue $capacity @('state'))); id=$id"
                }
            }
            $url = [string](Get-UatValue $page @('continuationUri'))
        } while ($url)
        throw 'TEST capacity not visible by displayName/id in Fabric API.'
    }
    finally { $token = $null; $tokenResponse = $null }
}

function Invoke-UatS09 {
    param([Parameter(Mandatory)] $Context)
    Initialize-PausedTestCapacity $Context
    $warnings = [System.Collections.Generic.List[string]]::new()
    $paused = ''
    $active = ''
    try { $paused = Get-FabricCapacityVisibility $Context }
    catch { $warnings.Add('Paused snapshot: Fabric API unreachable, unauthorized, or capacity not visible.') }
    Resume-Capacity $Context
    try { $active = Get-FabricCapacityVisibility $Context }
    catch { $warnings.Add('Resumed snapshot: Fabric API unreachable, unauthorized, or capacity not visible.') }
    $status = if ($warnings.Count) { 'WARN' } else { 'PASS' }
    return New-UatResult S09 'Fabric-side visibility' -Status $status -Evidence "After pause: $paused; after resume: $active; ARM=Active" -Detail ($warnings -join ' ')
}

function Test-UatRolePermissions {
    param([object[]] $Assignments, [string] $CapacityId)
    $suspend = 'Microsoft.Fabric/capacities/suspend/action'
    $hasSuspend = $false
    $unsafe = [System.Collections.Generic.List[string]]::new()
    $evidence = [System.Collections.Generic.List[string]]::new()
    foreach ($assignment in $Assignments) {
        $scope = [string]$assignment.Scope
        $applicable = $scope -and ($CapacityId -ieq $scope -or $CapacityId.StartsWith("$($scope.TrimEnd('/'))/", [StringComparison]::OrdinalIgnoreCase))
        if (-not $scope) { $unsafe.Add('Missing role-assignment scope.') }
        if ($assignment.Condition) { $unsafe.Add('Conditional assignment cannot prove unconditional suspend permission.') }
        foreach ($permission in @($assignment.Permissions)) {
            $actions = @(Get-UatValue $permission @('actions'))
            $notActions = @(Get-UatValue $permission @('notActions'))
            foreach ($action in $actions) {
                if (-not $action) { continue }
                if ($action -match '\*|(?:^|/)(?:resume|delete)(?:/|$)') { $unsafe.Add([string]$action) }
            }
            $denied = @($notActions | Where-Object { $_ -and $suspend -like $_ }).Count -gt 0
            if ($applicable -and $actions -contains $suspend -and -not $denied -and -not $assignment.Condition) { $hasSuspend = $true }
            $evidence.Add("Role=$($assignment.Name); scope=$scope; actions=[$($actions -join ',')]; notActions=[$($notActions -join ',')]")
        }
    }
    return [pscustomobject]@{ Passed = ($hasSuspend -and $unsafe.Count -eq 0); HasSuspend = $hasSuspend; Unsafe = @($unsafe); Evidence = $evidence -join ' | ' }
}

function Invoke-UatS10 {
    param([Parameter(Mandatory)] $Context)
    $roles = @(Invoke-AzCli -Context $Context -Arguments @('role', 'assignment', 'list', '--assignee', $Context.IdentityPrincipalId, '--all', '--include-inherited'))
    $definitions = @{}
    $assignments = [System.Collections.Generic.List[object]]::new()
    foreach ($role in $roles) {
        if ($null -eq $role) { continue }
        $definitionId = [string](Get-UatValue $role @('roleDefinitionId'))
        $definitionName = ($definitionId -split '/')[-1]
        Assert-Uat (-not [string]::IsNullOrWhiteSpace($definitionName)) 'Role assignment has no roleDefinitionId.'
        if (-not $definitions.ContainsKey($definitionId)) {
            $definition = @(Invoke-AzCli -Context $Context -Arguments @('role', 'definition', 'list', '--name', $definitionName))
            Assert-Uat ($definition.Count -eq 1) 'Could not resolve exactly one role definition.'
            $definitions[$definitionId] = $definition[0]
        }
        $definition = $definitions[$definitionId]
        $assignments.Add([pscustomobject]@{
            Name = [string](Get-UatValue $definition @('roleName'))
            Scope = [string](Get-UatValue $role @('scope'))
            Condition = [string](Get-UatValue $role @('condition'))
            Permissions = @(Get-UatValue $definition @('permissions'))
        })
    }
    $proof = Test-UatRolePermissions -Assignments @($assignments) -CapacityId $Context.CapacityResourceId
    $status = if ($proof.Passed) { 'PASS' } else { 'FAIL' }
    return New-UatResult S10 'Least privilege proof' -Status $status -Evidence $proof.Evidence -Detail "Applicable suspend grant=$($proof.HasSuspend); forbidden actions=[$($proof.Unsafe -join ',')]. Read-only definition inspection, not an effective-access simulation."
}

function Remove-UatSchedule {
    param([Parameter(Mandatory)] $Context)
    $errors = [System.Collections.Generic.List[string]]::new()
    foreach ($entry in @(
        @{ Key = 'TemporaryLink'; Child = 'jobSchedules' }
        @{ Key = 'TemporarySchedule'; Child = 'schedules' }
    )) {
        $name = [string]$Context[$entry.Key]
        if (-not $name) { continue }
        try {
            $null = Invoke-UatRest -Context $Context -Method DELETE -Url (Get-AutomationUrl $Context "/$($entry.Child)/$([uri]::EscapeDataString($name))")
            $Context[$entry.Key] = ''
        }
        catch {
            if ($_.Exception.Data['NotFound']) { $Context[$entry.Key] = '' }
            else { $errors.Add("Could not remove temporary $($entry.Child) '$name'.") }
        }
    }
    if ($errors.Count) { throw ($errors -join ' ') }
}

function Find-UatScheduledJob {
    param(
        [Parameter(Mandatory)] $Context,
        [Parameter(Mandatory)] [DateTimeOffset] $NotBefore,
        [string[]] $KnownJobIds = @(),
        [switch] $IncludeQueued
    )
    $candidates = [System.Collections.Generic.List[object]]::new()
    $jobs = @(Get-UatCollection -Context $Context -Url (Get-AutomationUrl $Context '/jobs'))
    foreach ($job in $jobs) {
        if ([string](Get-UatValue $job @('properties', 'runbook', 'name')) -ine $Context.RunbookName) { continue }
        $startTime = [string](Get-UatValue $job @('properties', 'startTime'))
        if (-not $startTime -and $IncludeQueued) { $startTime = [string](Get-UatValue $job @('properties', 'creationTime')) }
        if (-not $startTime -or [DateTimeOffset]::Parse($startTime) -lt $NotBefore.AddSeconds(-60)) { continue }
        $id = [string](Get-UatValue $job @('properties', 'jobId'))
        if (-not $id) { $id = [string](Get-UatValue $job @('name')) }
        if (-not $id -or $id -in $KnownJobIds) { continue }
        $detail = Invoke-UatRest -Context $Context -Method GET -Url (Get-AutomationUrl $Context "/jobs/$id")
        $parameters = Get-UatValue $detail @('properties', 'parameters')
        # Missing parameters must not hide a potentially dispatched job from cleanup.
        $capacityId = [string](Get-UatValue $parameters @('CapacityResourceId'))
        $dryRun = [string](Get-UatValue $parameters @('DryRun'))
        $identityId = [string](Get-UatValue $parameters @('UserAssignedIdentityClientId'))
        if ($capacityId -and $capacityId -ine $Context.CapacityResourceId) { continue }
        if ($dryRun -and $dryRun -ine 'false') { continue }
        if ($identityId -and $identityId -ine $Context.IdentityClientId) { continue }
        $candidates.Add([pscustomobject]@{ JobId = $id; Detail = $detail })
    }
    return $candidates.ToArray()
}

function Wait-UatScheduledJobsSettled {
    param(
        [Parameter(Mandatory)] $Context,
        [double] $TimeoutMinutes = $Context.JobTimeoutMinutes
    )
    if ($null -eq $Context.ScheduleStartTime -or (Get-UatNow) -lt $Context.ScheduleStartTime) { return }
    $deadline = (Get-UatNow).AddMinutes($TimeoutMinutes)
    do {
        try {
            $candidates = @(Find-UatScheduledJob -Context $Context -NotBefore $Context.ScheduleStartTime `
                -KnownJobIds $Context.ScheduleKnownIds -IncludeQueued)
            foreach ($candidate in $candidates) { Add-TrackedJob -Context $Context -JobId $candidate.JobId -Source 'OneTimeSchedule' }
            $scheduled = @($Context.Jobs | Where-Object { $_.Source -eq 'OneTimeSchedule' })
            if ($scheduled.Count -gt 0) {
                $remaining = [Math]::Max(0.001, ($deadline - (Get-UatNow)).TotalMinutes)
                Stop-UatOutstandingJobs -Context $Context -TimeoutMinutes ([Math]::Min(2, $remaining))
                if (@($scheduled | Where-Object { $_.Status -notin @('Completed', 'Failed', 'Stopped', 'Suspended') }).Count -eq 0) { return }
            }
        }
        catch {
            # Eventual consistency includes transient list/detail failures and 404s.
            # Only a positively identified, terminal job can release restoration.
        }
        if ((Get-UatNow) -ge $deadline) { break }
        Wait-UatPoll -Seconds 15
    } while ($true)
    throw 'One-time schedule crossed its trigger boundary, but its dispatched job could not be accounted for and confirmed Completed/Failed/Stopped/Suspended within the bounded cleanup wait.'
}

function Invoke-UatS11 {
    param([Parameter(Mandatory)] $Context)
    Initialize-ActiveTestCapacity $Context
    $knownIds = @(Get-UatCollection -Context $Context -Url (Get-AutomationUrl $Context '/jobs') | ForEach-Object {
        $id = [string](Get-UatValue $_ @('properties', 'jobId'))
        if (-not $id) { $id = [string](Get-UatValue $_ @('name')) }
        $id
    })
    $scheduleName = "autopause-uat-$([guid]::NewGuid().ToString('N'))"
    $linkId = [guid]::NewGuid().ToString()
    $startTime = Get-UatScheduleStartTime -LeadMinutes $Context.ScheduleLeadMinutes
    $Context.ScheduleStartTime = $startTime
    $Context.ScheduleKnownIds = $knownIds
    try {
        $Context.TemporarySchedule = $scheduleName
        $schedule = Invoke-UatRest -Context $Context -Method PUT -Url (Get-AutomationUrl $Context "/schedules/$scheduleName") -Body @{
            name = $scheduleName
            properties = @{ startTime = $startTime.ToString('o'); frequency = 'OneTime'; timeZone = 'UTC'; isEnabled = $true }
        }
        $effectiveStart = [string](Get-UatValue $schedule @('properties', 'startTime'))
        if (-not $effectiveStart) {
            $schedule = Invoke-UatRest -Context $Context -Method GET -Url (Get-AutomationUrl $Context "/schedules/$scheduleName")
            $effectiveStart = [string](Get-UatValue $schedule @('properties', 'startTime'))
        }
        Assert-Uat (-not [string]::IsNullOrWhiteSpace($effectiveStart)) 'The service did not return the schedule effective startTime; refusing to link it.'
        $startTime = [DateTimeOffset]::Parse($effectiveStart).ToUniversalTime()
        $Context.ScheduleStartTime = $startTime
        Assert-Uat ($startTime -gt (Get-UatNow)) 'The effective schedule startTime is not in the future; refusing to link it.'
        $Context.TemporaryLink = $linkId
        $null = Invoke-UatRest -Context $Context -Method PUT -Url (Get-AutomationUrl $Context "/jobSchedules/$linkId") -Body @{
            properties = @{
                runbook = @{ name = $Context.RunbookName }; schedule = @{ name = $scheduleName }
                parameters = New-RunbookParameters -Context $Context -Parameters @{ DryRun = 'false' }
            }
        }
        Write-Information "Waiting for one-time schedule at $($startTime.ToString('o')) (UTC)." -InformationAction Continue
        $deadline = $startTime.AddMinutes($Context.JobTimeoutMinutes)
        $scheduledJobs = @()
        do {
            $scheduledJobs = @(Find-UatScheduledJob -Context $Context -NotBefore $startTime -KnownJobIds $knownIds -IncludeQueued)
            foreach ($scheduledJob in $scheduledJobs) { Add-TrackedJob -Context $Context -JobId $scheduledJob.JobId -Source 'OneTimeSchedule' }
            if ($scheduledJobs.Count -gt 0 -or (Get-UatNow) -ge $deadline) { break }
            Wait-UatPoll
        } while ($true)
        Assert-Uat ($scheduledJobs.Count -gt 0) 'No matching one-time-schedule job appeared before the deadline.'
        Assert-Uat ($scheduledJobs.Count -eq 1) 'Multiple matching scheduled jobs appeared; attribution is ambiguous. Avoid concurrent runbook invocations.'
        $scheduled = $scheduledJobs[0]
        $remaining = [Math]::Max(0.01, ($deadline - (Get-UatNow)).TotalMinutes)
        $status = Wait-RunbookJob -Context $Context -JobId $scheduled.JobId -TimeoutMinutes $remaining
        $output = Get-UatSettledJobOutput -Context $Context -JobId $scheduled.JobId
        Assert-Uat ($status -eq 'Completed') "Scheduled job $($scheduled.JobId) ended with status $status."
        Assert-JobDecision ([pscustomobject]@{ JobId = $scheduled.JobId; Output = $output }) Paused
        $null = Wait-CapacityState -Context $Context -State Paused
        return New-UatResult S11 'Schedule trigger' -Evidence "Schedule=$scheduleName; UTC=$($startTime.ToString('o')); Job=$($scheduled.JobId); Completed; ARM=Paused"
    }
    finally {
        Remove-UatSchedule $Context
        # The outer finally reconciles dispatch visibility with bounded polling before restoration.
    }
}

function Stop-UatOutstandingJobs {
    param([Parameter(Mandatory)] $Context, [double] $TimeoutMinutes = 2)
    $errors = [System.Collections.Generic.List[string]]::new()
    $deadline = (Get-UatNow).AddMinutes($TimeoutMinutes)
    foreach ($tracked in $Context.Jobs) {
        if ($tracked.Status -in @('Completed', 'Failed', 'Stopped', 'Suspended')) { continue }
        try {
            $job = Invoke-UatRest -Context $Context -Method GET -Url (Get-AutomationUrl $Context "/jobs/$($tracked.JobId)")
            $status = [string](Get-UatValue $job @('properties', 'status'))
            if ($status -notin @('Completed', 'Failed', 'Stopped', 'Suspended')) {
                $null = Invoke-UatRest -Context $Context -Method POST -Url (Get-AutomationUrl $Context "/jobs/$($tracked.JobId)/stop")
                $remaining = [Math]::Max(0.001, ($deadline - (Get-UatNow)).TotalMinutes)
                $status = Wait-RunbookJob -Context $Context -JobId $tracked.JobId -TimeoutMinutes $remaining
            }
            Assert-Uat ($status -in @('Completed', 'Failed', 'Stopped', 'Suspended')) 'A UAT job may still be running.'
            $tracked.Status = $status
        }
        catch {
            if ($_.Exception.Data['NotFound'] -and $tracked.Source -ne 'OneTimeSchedule') { $tracked.Status = 'NotCreated' }
            else { $errors.Add("Job $($tracked.JobId) could not be confirmed stopped.") }
        }
    }
    if ($errors.Count) { throw ($errors -join ' ') }
}

function Restore-UatCapacity {
    param([Parameter(Mandatory)] $Context)
    if (-not $Context.Validated -or $Context.LeaveAsIs) { return }
    $errors = [System.Collections.Generic.List[string]]::new()
    try {
        if ($Context.OriginalCapacity.State -eq 'Active') { Resume-Capacity $Context }
        else { Suspend-Capacity $Context }
    }
    catch { $errors.Add("Power-state restoration failed: $($_.Exception.Message)") }
    try {
        if ($Context.TagTouched) {
            if ($Context.OriginalCapacity.Tags.ContainsKey('autopause')) {
                $originalTagName = @($Context.OriginalCapacity.Tags.Keys | Where-Object { $_ -ieq 'autopause' })[0]
                Set-CapacityTags -Context $Context -Name $originalTagName -Value $Context.OriginalCapacity.Tags['autopause']
            }
            else { Set-CapacityTags -Context $Context -Remove }
        }
    }
    catch { $errors.Add("Tag restoration failed: $($_.Exception.Message)") }
    if ($errors.Count) { throw ($errors -join ' ') }
}

function New-UatContext {
    param([Parameter(Mandatory)] [hashtable] $Settings)
    $pattern = '\A/subscriptions/(?<subscription>[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})/resourceGroups/(?<group>[A-Za-z0-9_.()\-]{1,90})/providers/Microsoft\.Fabric/capacities/(?<name>[A-Za-z][A-Za-z0-9]{2,62})\z'
    Assert-Uat ($Settings.CapacityResourceId -match $pattern) 'CapacityResourceId must be one full Microsoft.Fabric/capacities ARM ID.'
    $capacityName = $Matches.name
    Assert-Uat ($Matches.subscription -ieq $Settings.SubscriptionId) 'Capacity and Automation account must be in the explicit SubscriptionId.'
    $directory = $Settings.ResultPath
    if ([string]::IsNullOrWhiteSpace($directory)) { $directory = (Get-Location).Path }
    $path = [IO.Path]::GetFullPath($directory)
    $runId = [guid]::NewGuid().ToString('N')
    if ([IO.Path]::GetExtension($path) -ieq '.json') {
        $outputPath = $path
        $directory = Split-Path -Parent $path
    }
    else {
        $directory = $path
        $outputPath = Join-Path $directory ("autopause-uat-{0}-{1}.json" -f (Get-UatNow).ToString('yyyyMMddTHHmmssfffZ'), $runId)
    }
    return @{
        SubscriptionId = $Settings.SubscriptionId; ResourceGroupName = $Settings.ResourceGroupName
        AutomationAccountName = $Settings.AutomationAccountName; RunbookName = $Settings.RunbookName
        AutomationResourceId = "/subscriptions/$($Settings.SubscriptionId)/resourceGroups/$($Settings.ResourceGroupName)/providers/Microsoft.Automation/automationAccounts/$($Settings.AutomationAccountName)"
        CapacityResourceId = $Settings.CapacityResourceId; CapacityName = $capacityName
        IdentityClientId = $Settings.UserAssignedIdentityClientId; IdentityPrincipalId = ''
        ExpectedNightlySchedule = $Settings.ExpectedNightlySchedule
        ExpectedTimeZone = $Settings.ExpectedTimeZone; ExpectedLocalTime = $Settings.ExpectedLocalTime
        JobTimeoutMinutes = $Settings.JobTimeoutMinutes; Scenarios = $Settings.Scenarios
        IncludeScheduleTrigger = $Settings.IncludeScheduleTrigger; ScheduleLeadMinutes = $Settings.ScheduleLeadMinutes
        SkipResumeScenarios = $Settings.SkipResumeScenarios; LeaveAsIs = $Settings.LeaveAsIs
        Results = [System.Collections.Generic.List[object]]::new()
        Jobs = [System.Collections.Generic.List[object]]::new()
        RunId = $runId; StartedAt = (Get-UatNow).ToString('o'); CurrentScenario = 'S01'
        ResultDirectory = $directory; ResultFile = $outputPath
        RequestDirectory = Join-Path $directory ".autopause-uat-$runId"
        Validated = $false; TagTouched = $false; OriginalCapacity = $null
        TemporarySchedule = ''; TemporaryLink = ''
        ScheduleStartTime = $null; ScheduleKnownIds = @()
    }
}

function Write-UatReport {
    param([Parameter(Mandatory)] $Context)
    $failures = @($Context.Results | Where-Object { $_.Status -eq 'FAIL' }).Count
    $counts = @{}
    foreach ($status in @('PASS', 'FAIL', 'WARN', 'SKIPPED')) {
        $counts[$status] = @($Context.Results | Where-Object { $_.Status -eq $status }).Count
    }
    $exitCode = if ($failures) { 1 } else { 0 }
    $summary = "UAT SUMMARY: PASS=$($counts.PASS) FAIL=$($counts.FAIL) WARN=$($counts.WARN) SKIPPED=$($counts.SKIPPED); exit=$exitCode"
    $report = [ordered]@{
        SchemaVersion = 1; RunId = $Context.RunId; StartedAt = $Context.StartedAt; FinishedAt = (Get-UatNow).ToString('o')
        CapacityResourceId = $Context.CapacityResourceId; RunbookName = $Context.RunbookName
        LeaveAsIs = $Context.LeaveAsIs; OriginalState = Get-UatValue $Context.OriginalCapacity @('State')
        Results = @($Context.Results); Jobs = @($Context.Jobs); Counts = $counts; ExitCode = $exitCode; Summary = $summary
    }
    try {
        $report | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $Context.ResultFile -Encoding utf8NoBOM
    }
    catch {
        $Context.Results.Add((New-UatResult REPORT 'Persisting results' -Status FAIL -Detail 'Could not write the results JSON.'))
        $exitCode = 1
        $counts.FAIL++
        $summary = "UAT SUMMARY: PASS=$($counts.PASS) FAIL=$($counts.FAIL) WARN=$($counts.WARN) SKIPPED=$($counts.SKIPPED); REPORT WRITE FAILED; exit=1"
    }
    $table = $Context.Results | Select-Object Id, Name, Status, Evidence, Detail | Format-Table -AutoSize -Wrap | Out-String -Width 240
    Write-Output $table
    Write-Output 'Runbook jobs:'
    foreach ($job in $Context.Jobs) { Write-Output ("  {0} {1} {2} ({3})" -f $job.Scenario, $job.JobId, $job.Status, $job.Source) }
    Write-Output "Results JSON: $($Context.ResultFile)"
    Write-Output $summary
    return $exitCode
}

function Invoke-AutoPauseUat {
    param([Parameter(Mandatory)] $Context)
    $canContinue = $true
    try {
        $null = New-Item -ItemType Directory -Path $Context.ResultDirectory -Force
        # Detect an unwritable destination before touching Azure.
        '{"Status":"InProgress"}' | Set-Content -LiteralPath $Context.ResultFile -Encoding utf8NoBOM
        foreach ($scenario in Get-UatScenarioPlan) {
            $Context.CurrentScenario = $scenario.Id
            $selected = $scenario.Id -eq 'S01' -or 'All' -in $Context.Scenarios -or $scenario.Id -in $Context.Scenarios
            $skip = ''
            if (-not $selected) { $skip = 'Not selected.' }
            elseif (-not $canContinue) { $skip = 'Blocked by failed preconditions or an unfinished UAT job.' }
            elseif ($scenario.Id -eq 'S11' -and -not $Context.IncludeScheduleTrigger) { $skip = 'Requires -IncludeScheduleTrigger.' }
            elseif ($scenario.RequiresResume -and $Context.SkipResumeScenarios) { $skip = '-SkipResumeScenarios specified.' }
            if ($skip) {
                $Context.Results.Add((New-UatResult $scenario.Id $scenario.Name -Status SKIPPED -Detail $skip))
                continue
            }
            Write-Information "$($scenario.Id): $($scenario.Name)" -InformationAction Continue
            try {
                $result = & "Invoke-Uat$($scenario.Id)" -Context $Context
                $Context.Results.Add($result)
            }
            catch {
                $Context.Results.Add((New-UatResult $scenario.Id $scenario.Name -Status FAIL -Detail $_.Exception.Message))
                if ($scenario.Id -eq 'S01') { $canContinue = $false }
                if (@($Context.Jobs | Where-Object { $_.Status -notin @('Completed', 'Failed', 'Stopped', 'Suspended') }).Count) {
                    $canContinue = $false
                }
            }
        }
    }
    catch { $Context.Results.Add((New-UatResult HARNESS 'Harness execution' -Status FAIL -Detail $_.Exception.Message)) }
    finally {
        $cleanupErrors = [System.Collections.Generic.List[string]]::new()
        $jobsStopped = $true
        try { Remove-UatSchedule $Context } catch { $cleanupErrors.Add($_.Exception.Message) }
        try { Wait-UatScheduledJobsSettled $Context }
        catch { $jobsStopped = $false; $cleanupErrors.Add($_.Exception.Message) }
        try { Stop-UatOutstandingJobs $Context }
        catch { $jobsStopped = $false; $cleanupErrors.Add($_.Exception.Message) }
        if ($jobsStopped -and -not $Context.TemporarySchedule -and -not $Context.TemporaryLink) {
            try { Restore-UatCapacity $Context } catch { $cleanupErrors.Add($_.Exception.Message) }
        }
        else {
            $recovery = 'CAPACITY STATE UNCERTAIN: POWER/TAG RESTORATION SKIPPED. A dispatched job may still pause this capacity. In the Automation account Jobs view, check this runbook around the effective UTC schedule start (including queued jobs); stop/wait for every matching capacity job to reach Completed, Failed, Stopped or Suspended. Verify the temporary schedule AND link are deleted, then check the capacity ARM power state and restore it manually. Do not resume it until jobs are accounted for and settled.'
            Write-Warning $recovery -WarningAction Continue
            $cleanupErrors.Add($recovery)
        }
        try {
            if (Test-Path -LiteralPath $Context.RequestDirectory) { Remove-Item -LiteralPath $Context.RequestDirectory -Recurse -Force }
        }
        catch { $cleanupErrors.Add('Could not remove the invocation request directory.') }
        if ($cleanupErrors.Count) {
            $Context.Results.Add((New-UatResult CLEANUP 'Restoration and cleanup' -Status FAIL -Detail ($cleanupErrors -join ' ')))
        }
        else {
            $detail = if ($Context.LeaveAsIs) { 'Power/tag restoration intentionally skipped; temporary resources and unfinished jobs cleaned.' }
                elseif ($Context.Validated) { "Original power state $($Context.OriginalCapacity.State) and autopause tag restored; other tags preserved." }
                else { 'No capacity mutations authorized; temporary resources cleaned.' }
            $Context.Results.Add((New-UatResult CLEANUP 'Restoration and cleanup' -Evidence $detail))
        }
    }
    # Keep report display on the information stream so the function returns only an exit code.
    $lines = @(Write-UatReport $Context)
    foreach ($line in $lines[0..($lines.Count - 2)]) { Write-Information ([string]$line) -InformationAction Continue }
    return [int]$lines[-1]
}

if ($MyInvocation.InvocationName -ne '.') {
    $settings = @{
        SubscriptionId = $SubscriptionId; ResourceGroupName = $ResourceGroupName; AutomationAccountName = $AutomationAccountName
        CapacityResourceId = $CapacityResourceId; RunbookName = $RunbookName; UserAssignedIdentityClientId = $UserAssignedIdentityClientId
        ExpectedNightlySchedule = $ExpectedNightlySchedule; ExpectedTimeZone = $ExpectedTimeZone; ExpectedLocalTime = $ExpectedLocalTime
        JobTimeoutMinutes = $JobTimeoutMinutes; Scenarios = $Scenarios; LeaveAsIs = [bool]$LeaveAsIs
        IncludeScheduleTrigger = [bool]$IncludeScheduleTrigger; ScheduleLeadMinutes = $ScheduleLeadMinutes
        SkipResumeScenarios = [bool]$SkipResumeScenarios; ResultPath = $ResultPath
    }
    $context = New-UatContext $settings
    Write-Output 'Plan: live UAT changes ONLY the specified TEST F-SKU capacity; no other capacity is a job target.'
    Write-Output ("Target: {0}; original power state/autopause tag restored unless -LeaveAsIs." -f $CapacityResourceId)
    Get-UatScenarioPlan | Select-Object Id, Name, @{ Name = 'Planned'; Expression = {
        if ($_.Id -ne 'S01' -and 'All' -notin $Scenarios -and $_.Id -notin $Scenarios) { 'SKIPPED (not selected)' }
        elseif ($_.Id -eq 'S11' -and -not $IncludeScheduleTrigger) { 'SKIPPED (requires opt-in)' }
        elseif ($_.RequiresResume -and $SkipResumeScenarios) { 'SKIPPED (resume disabled)' }
        else { 'RUN' }
    } }, RequiresResume | Format-Table -AutoSize | Out-String | Write-Output
    if ($PSCmdlet.ShouldProcess($CapacityResourceId, 'Run live pause/resume UAT, modify autopause tag, submit scoped jobs, and restore')) {
        exit (Invoke-AutoPauseUat $context)
    }
}
