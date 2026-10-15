#Requires -Modules @{ ModuleName='Pester'; ModuleVersion='5.0.0' }

BeforeAll {
    $script:harnessPath = Join-Path $PSScriptRoot 'Invoke-AutoPauseUat.ps1'
    $subscription = [guid]::NewGuid().ToString()
    $script:arguments = @{
        SubscriptionId = $subscription
        ResourceGroupName = 'test-group'
        AutomationAccountName = 'test-automation'
        CapacityResourceId = "/subscriptions/$subscription/resourceGroups/test-group/providers/Microsoft.Fabric/capacities/testcapacity"
        ResultPath = $PSScriptRoot
    }
    . $script:harnessPath @script:arguments

    function New-OfflineContext {
        $settings = $script:arguments.Clone()
        $settings.RunbookName = 'Invoke-FabricCapacityAutoPause'
        $settings.UserAssignedIdentityClientId = [guid]::NewGuid().ToString()
        $settings.ExpectedNightlySchedule = 'test-nightly'
        $settings.ExpectedTimeZone = ''
        $settings.ExpectedLocalTime = ''
        $settings.JobTimeoutMinutes = 1
        $settings.Scenarios = @('All')
        $settings.LeaveAsIs = $false
        $settings.IncludeScheduleTrigger = $true
        $settings.ScheduleLeadMinutes = 5
        $settings.SkipResumeScenarios = $false
        return New-UatContext $settings
    }

    function az { throw 'Offline test guard: Azure CLI must never execute.' }
}

Describe 'Offline UAT harness' {
BeforeEach {
    $script:clock = [DateTimeOffset]::Parse('2035-01-01T00:00:23.456+00:00')
    Mock Get-UatNow { $script:clock }
    Mock Wait-UatPoll { param($Seconds) $script:clock = $script:clock.AddSeconds($Seconds) }
    Mock Invoke-AzProcess { throw 'Offline test guard: no native processes.' }
    Mock Invoke-UatRest { throw 'Offline test guard: no ARM requests.' }
    Mock Invoke-FabricRead { throw 'Offline test guard: no Fabric requests.' }
    $script:context = New-OfflineContext
}

Describe 'Whole-minute UTC scheduling' {
    It 'rounds upward and preserves at least the minimum lead for <Instant>' -ForEach @(
        @{ Instant = '2035-01-01T00:00:00+00:00'; Lead = 5 }
        @{ Instant = '2035-01-01T00:00:00.001+00:00'; Lead = 8 }
        @{ Instant = '2035-01-01T23:59:59.999+00:00'; Lead = 5 }
        @{ Instant = '2035-01-01T12:34:59.999+05:30'; Lead = 1440 }
    ) {
        $now = [DateTimeOffset]::Parse($Instant)
        $start = Get-UatScheduleStartTime -Now $now -LeadMinutes $Lead
        ($start.Ticks % [TimeSpan]::TicksPerMinute) | Should -Be 0
        $start.Offset | Should -Be ([TimeSpan]::Zero)
        ($start - $now).TotalMinutes | Should -BeGreaterOrEqual $Lead
        ($start - $now.AddMinutes($Lead)).TotalSeconds | Should -BeLessThan 60
    }

    It 'uses the effective PUT/GET start for correlation (GET fallback: <ViaGet>) and removes both resources' -ForEach @(
        @{ ViaGet = $false }
        @{ ViaGet = $true }
    ) {
        $script:viaGet = $ViaGet
        $script:effective = $script:clock.AddMinutes(7)
        Mock Initialize-ActiveTestCapacity {}
        Mock Get-UatCollection { @() }
        Mock Find-UatScheduledJob { [pscustomobject]@{ JobId = 'scheduled-job' } }
        Mock Wait-RunbookJob { 'Completed' }
        Mock Get-UatSettledJobOutput { '[Output] Summary: Paused=1' }
        Mock Wait-CapacityState { 'Paused' }
        Mock Invoke-UatRest {
            param($Method, $Url, $Body)
            if ($Method -eq 'PUT' -and $Url -match '/schedules/') {
                $script:scheduleBody = $Body
                if ($script:viaGet) { return @{} }
            }
            if ($Method -in @('PUT', 'GET') -and $Url -match '/schedules/') {
                return @{ properties = @{ startTime = $script:effective.ToString('o') } }
            }
        }

        (Invoke-UatS11 $script:context).Status | Should -Be PASS
        $script:scheduleBody.name | Should -Match '^autopause-uat-'
        $script:scheduleBody.properties.frequency | Should -Be OneTime
        $script:scheduleBody.properties.timeZone | Should -Be UTC
        ([DateTimeOffset]::Parse($script:scheduleBody.properties.startTime).Ticks % [TimeSpan]::TicksPerMinute) | Should -Be 0
        $script:context.ScheduleStartTime | Should -Be $script:effective
        Should -Invoke Find-UatScheduledJob -Times 1 -Exactly -ParameterFilter { $NotBefore -eq $script:effective -and $IncludeQueued }
        Should -Invoke Invoke-UatRest -Times 1 -Exactly -ParameterFilter { $Method -eq 'DELETE' -and $Url -match '/jobSchedules/' }
        Should -Invoke Invoke-UatRest -Times 1 -Exactly -ParameterFilter { $Method -eq 'DELETE' -and $Url -match '/schedules/' }
        $script:context.TemporaryLink | Should -BeNullOrEmpty
        $script:context.TemporarySchedule | Should -BeNullOrEmpty
    }
}

Describe 'Scheduled job correlation and fail-closed reconciliation' {
    BeforeEach {
        $script:context.ScheduleStartTime = $script:clock.AddMinutes(-1)
        $script:context.ScheduleKnownIds = @()
    }

    It 'accepts the small timestamp tolerance, queued jobs, and missing parameters, but not another target or runbook' {
        Mock Get-UatCollection {
            foreach ($entry in @(
                @{ Id = 'within'; Seconds = -59; Runbook = $script:context.RunbookName }
                @{ Id = 'too-early'; Seconds = -61; Runbook = $script:context.RunbookName }
                @{ Id = 'other-target'; Seconds = 0; Runbook = $script:context.RunbookName }
                @{ Id = 'other-runbook'; Seconds = 0; Runbook = 'other-runbook' }
                @{ Id = 'queued'; Seconds = 0; Runbook = $script:context.RunbookName }
                @{ Id = 'known'; Seconds = 0; Runbook = $script:context.RunbookName }
            )) {
                $properties = @{
                    jobId = $entry.Id; runbook = @{ name = $entry.Runbook }
                    creationTime = $script:context.ScheduleStartTime.AddSeconds($entry.Seconds).ToString('o')
                }
                if ($entry.Id -ne 'queued') { $properties.startTime = $properties.creationTime }
                @{ properties = $properties }
            }
        }
        Mock Invoke-UatRest {
            param($Url)
            if ($Url -match '/jobs/other-target\?') { return @{ properties = @{ parameters = @{ CapacityResourceId = 'another-target' } } } }
            return @{ properties = @{} }
        }
        $ids = @(Find-UatScheduledJob -Context $script:context -NotBefore $script:context.ScheduleStartTime -KnownJobIds @('known') -IncludeQueued).JobId
        $ids.Count | Should -Be 2
        $ids | Should -Contain within
        $ids | Should -Contain queued
    }

    It 'polls through empty responses until the dispatched job is visible and terminal (<Terminal>)' -ForEach @(
        @{ Terminal = 'Completed' }; @{ Terminal = 'Failed' }
        @{ Terminal = 'Stopped' }; @{ Terminal = 'Suspended' }
    ) {
        $script:terminal = $Terminal
        $script:queries = 0
        Mock Find-UatScheduledJob {
            $script:queries++
            if ($script:queries -ge 3) { [pscustomobject]@{ JobId = 'late-job' } }
        }
        Mock Invoke-UatRest { @{ properties = @{ status = $script:terminal } } }
        { Wait-UatScheduledJobsSettled $script:context } | Should -Not -Throw
        $script:queries | Should -Be 3
        $script:context.Jobs[0].Status | Should -Be $Terminal
        Should -Invoke Wait-UatPoll -Times 2 -Exactly
    }

    It 'fails closed if dispatch stays invisible or a job cannot settle (<Case>)' -ForEach @(
        @{ Case = 'empty' }; @{ Case = 'list-error' }
        @{ Case = 'running' }; @{ Case = 'not-found' }
    ) {
        $script:failureCase = $Case
        Mock Find-UatScheduledJob {
            if ($script:failureCase -eq 'list-error') { throw 'List unavailable.' }
            if ($script:failureCase -in @('running', 'not-found')) { [pscustomobject]@{ JobId = 'unsettled-job' } }
        }
        Mock Invoke-UatRest {
            if ($script:failureCase -eq 'not-found') {
                $exception = [InvalidOperationException]::new('Not yet visible.')
                $exception.Data['NotFound'] = $true
                throw $exception
            }
            return @{ properties = @{ status = 'Running' } }
        }
        Mock Wait-RunbookJob { 'TimedOut' }
        { Wait-UatScheduledJobsSettled $script:context } | Should -Throw '*could not be accounted for*'
        ($script:clock - $script:context.ScheduleStartTime).TotalMinutes | Should -BeLessOrEqual 2.25
    }

    It 'does not infer dispatch before the trigger boundary' {
        $script:context.ScheduleStartTime = $script:clock.AddMinutes(1)
        Mock Find-UatScheduledJob { throw 'Must not poll before dispatch is possible.' }
        { Wait-UatScheduledJobsSettled $script:context } | Should -Not -Throw
        Should -Invoke Find-UatScheduledJob -Times 0 -Exactly
    }

    It 'withholds restoration, warns, deletes both resources, and returns nonzero after invisible dispatch' {
        $script:context.TemporarySchedule = 'test-schedule'
        $script:context.TemporaryLink = 'test-link'
        Mock Get-UatScenarioPlan { [pscustomobject]@{ Id = 'S01'; Name = 'Offline gate'; RequiresResume = $false } }
        Mock Invoke-UatS01 { param($Context) $Context.Validated = $true; New-UatResult S01 'Offline gate' }
        Mock New-Item {}
        Mock Set-Content {}
        Mock Test-Path { $false }
        Mock Invoke-UatRest {}
        Mock Find-UatScheduledJob {}
        Mock Restore-UatCapacity {}
        Mock Write-Warning {}
        Mock Write-UatReport {
            param($Context)
            'Offline report'
            if (@($Context.Results | Where-Object Status -eq FAIL).Count) { 1 } else { 0 }
        }
        Invoke-AutoPauseUat $script:context | Should -Be 1
        Should -Invoke Restore-UatCapacity -Times 0 -Exactly
        Should -Invoke Write-Warning -Times 1 -Exactly -ParameterFilter { $Message -like '*CAPACITY STATE UNCERTAIN*' }
        Should -Invoke Invoke-UatRest -Times 2 -Exactly -ParameterFilter { $Method -eq 'DELETE' }
        ($script:context.Results | Where-Object Id -eq CLEANUP).Status | Should -Be FAIL
        $script:context.TemporarySchedule | Should -BeNullOrEmpty
        $script:context.TemporaryLink | Should -BeNullOrEmpty
    }
}

Describe 'Job stream decoding and exact publication predicates' {
    It 'extracts properties.value safely (<Label>)' -ForEach @(
        @{ Label = 'plain'; Payload = 'Summary: Paused=1'; Expected = 'Summary: Paused=1' }
        @{ Label = 'JSON string'; Payload = '"Summary: Paused=1"'; Expected = 'Summary: Paused=1' }
        @{ Label = 'JSON object'; Payload = '{"Message":"Summary: Paused=1"}'; Expected = 'Summary: Paused=1' }
        @{ Label = 'Message'; Payload = @{ Message = 'message text' }; Expected = 'message text' }
        @{ Label = 'Text'; Payload = [pscustomobject]@{ Text = 'text value' }; Expected = 'text value' }
        @{ Label = 'nested value'; Payload = @{ value = @{ Text = 'nested text' } }; Expected = 'nested text' }
        @{ Label = 'array'; Payload = @(@{ Message = 'first' }, @{ Text = 'second' }); Expected = "first`nsecond" }
        @{ Label = 'JSON array'; Payload = '[{"Text":"first"},"second"]'; Expected = "first`nsecond" }
        @{ Label = 'null'; Payload = $null; Expected = '' }
    ) {
        $script:payload = $Payload
        Mock Get-UatCollection { @{ properties = @{ streamType = 'Output'; jobStreamId = 'stream' } } }
        Mock Invoke-UatRest {
            param($Url)
            if ($Url -match '/streams/') { return @{ properties = @{ value = $script:payload } } }
            return @{ properties = @{} }
        }
        $output = Get-RunbookJobOutput -Context $script:context -JobId 'job'
        $expectedOutput = if ($Expected) { "[Output] $Expected" } else { '' }
        $output | Should -Be $expectedOutput
    }

    It 'falls back to list properties.value and retains credential sanitization' {
        Mock Get-UatCollection { @{ properties = @{ streamType = 'Error'; jobStreamId = 'stream'; value = @{ Message = ('Bearer' + ' ' + 'offline-placeholder') } } } }
        Mock Invoke-UatRest { @{ properties = @{} } }
        $output = Get-RunbookJobOutput -Context $script:context -JobId 'job'
        $output | Should -Match '^\[Error\]'
        $output | Should -Not -Match 'offline-placeholder'
    }

    It 'waits past table words until the actual Summary line is published' {
        $script:reads = 0
        Mock Get-RunbookJobOutput {
            $script:reads++
            if ($script:reads -eq 1) { return '[Output] PriorState Active Result Paused WouldPause' }
            return '[Output] Summary: Paused=1'
        }
        Get-UatSettledJobOutput -Context $script:context -JobId 'job' | Should -Be '[Output] Summary: Paused=1'
        Should -Invoke Get-RunbookJobOutput -Times 2 -Exactly
    }

    It 'waits for the expected error even if a discovery/table message appears first' {
        $script:reads = 0
        Mock Get-RunbookJobOutput {
            $script:reads++
            if ($script:reads -eq 1) { return 'Discovered 0 Fabric capacities.' }
            return 'Invalid DryRun'
        }
        Get-UatSettledJobOutput -Context $script:context -JobId 'job' -OutputPattern 'Invalid DryRun' | Should -Be 'Invalid DryRun'
        Should -Invoke Get-RunbookJobOutput -Times 2 -Exactly
    }

    It 'bounds output polling when the Summary never arrives' {
        Mock Get-RunbookJobOutput { 'Result Paused' }
        Get-UatSettledJobOutput -Context $script:context -JobId 'job' | Should -Be 'Result Paused'
        Should -Invoke Wait-UatPoll -Times 12 -Exactly
    }
}

Describe 'Expected scenario outcomes' {
    BeforeEach {
        Mock Initialize-ActiveTestCapacity {}
        Mock Get-CapacityState { [pscustomobject]@{ State = 'Active' } }
        Mock Start-RunbookJob {
            param($Context, $Parameters)
            $script:submitted = New-RunbookParameters -Context $Context -Parameters $Parameters
            'scoped-job'
        }
        Mock Wait-RunbookJob { 'Failed' }
        Mock Get-RunbookJobOutput { 'The requested capacity was not found, or the identity cannot read it.' }
    }

    It 'passes S06 only on the expected Failed/error/no-summary outcome and preserves both scope filters' {
        (Invoke-UatS06 $script:context).Status | Should -Be PASS
        $script:submitted.CapacityResourceId | Should -Be $script:context.CapacityResourceId
        $script:submitted.CapacityName | Should -Not -Be $script:context.CapacityName
        $script:submitted.DryRun | Should -Be false
    }

    It 'rejects the former Completed/no-target S06 outcome' {
        Mock Wait-RunbookJob { 'Completed' }
        Mock Get-RunbookJobOutput { 'Discovered 0 Fabric capacities. Summary: nothing to do' }
        { Invoke-UatS06 $script:context } | Should -Throw
    }

    It 'rejects S06 when the capacity changed' {
        Mock Get-CapacityState { [pscustomobject]@{ State = 'Paused' } }
        { Invoke-UatS06 $script:context } | Should -Throw '*changed*'
    }

    It 'notes PauseInProgress in S04 without failing it' {
        Mock Invoke-ScenarioJob { [pscustomobject]@{ JobId = 'job'; Output = 'Summary: PauseInProgress=1' } }
        Mock Wait-CapacityState { 'Paused' }
        $result = Invoke-UatS04 $script:context
        $result.Status | Should -Be WARN
        $result.Evidence | Should -Match 'PauseInProgress=1'
    }

    It 'notes PauseInProgress during S05 setup but requires Skipped for the repeat job' {
        Mock Set-CapacityTags {}
        Mock Get-CapacityState {
            if ($script:context.Jobs.Count -eq 0) { return [pscustomobject]@{ State = 'Pausing' } }
            return [pscustomobject]@{ State = 'Paused' }
        }
        Mock Wait-CapacityState { 'Paused' }
        Mock Invoke-ScenarioJob {
            if ($script:context.Jobs.Count -eq 0) {
                Add-TrackedJob -Context $script:context -JobId 'setup'
                return [pscustomobject]@{ JobId = 'setup'; Output = 'Summary: PauseInProgress=1' }
            }
            return [pscustomobject]@{ JobId = 'repeat'; Output = 'Summary: Skipped=1' }
        }
        $result = Invoke-UatS05 $script:context
        $result.Status | Should -Be PASS
        $result.Evidence | Should -Match 'PauseInProgress.*Skipped=1'
        Mock Invoke-ScenarioJob { [pscustomobject]@{ JobId = 'repeat'; Output = 'Summary: PauseInProgress=1' } }
        { Invoke-UatS05 $script:context } | Should -Throw '*Skipped*'
    }
}

Describe 'Offline WhatIf' {
    It 'makes no az calls (mutating or otherwise) and performs no filesystem mutations' {
        Mock Get-UatNow { [DateTimeOffset]::UtcNow }
        Mock az { throw 'Azure CLI must not run.' }
        Mock Invoke-RestMethod { throw 'HTTP must not run.' }
        Mock New-Item { throw 'No directory creation allowed.' }
        Mock Set-Content { throw 'No file writes allowed.' }
        Mock Remove-Item { throw 'No deletion allowed.' }
        & $script:harnessPath @script:arguments -WhatIf | Out-Null
        Should -Invoke az -Times 0 -Exactly
        Should -Invoke Invoke-AzProcess -Times 0 -Exactly
        Should -Invoke Invoke-RestMethod -Times 0 -Exactly
        Should -Invoke New-Item -Times 0 -Exactly
        Should -Invoke Set-Content -Times 0 -Exactly
        Should -Invoke Remove-Item -Times 0 -Exactly
    }
}
}
