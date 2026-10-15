#Requires -Modules @{ ModuleName = 'Pester'; ModuleVersion = '5.0.0' }

BeforeAll {
    # Stubs so the tests run without the Az modules installed; Mock replaces them per test.
    function Connect-AzAccount { param([switch] $Identity, $AccountId, $ErrorAction) }
    function Disable-AzContextAutosave { param($Scope) }
    function Invoke-AzRestMethod { param($Method, $Path, $Payload, $ErrorAction) }

    . (Join-Path $PSScriptRoot '..\runbooks\Invoke-FabricCapacityAutoPause.ps1')
}

Describe 'Get-AutoPauseDecision' {
    It 'pauses an Active capacity' {
        (Get-AutoPauseDecision -State 'Active' -Tags $null -ExcludeTagName 'autopause' -ExcludeTagValue 'skip').Action | Should -Be 'Pause'
    }

    It 'skips capacities that are already off' -ForEach @('Paused', 'Suspended') {
        (Get-AutoPauseDecision -State $_ -Tags $null -ExcludeTagName 'autopause' -ExcludeTagValue 'skip').Action | Should -Be 'Skip'
    }

    It 'awaits capacities whose pause is already in progress instead of calling them done' -ForEach @('Pausing', 'Suspending') {
        (Get-AutoPauseDecision -State $_ -Tags $null -ExcludeTagName 'autopause' -ExcludeTagValue 'skip').Action | Should -Be 'Await'
    }

    It 'defers transitional states to a later run' -ForEach @('Resuming', 'Scaling', 'Updating', 'Preparing', 'Provisioning') {
        (Get-AutoPauseDecision -State $_ -Tags $null -ExcludeTagName 'autopause' -ExcludeTagValue 'skip').Action | Should -Be 'Defer'
    }

    It 'warns on Failed, Deleting and unknown states' -ForEach @('Failed', 'Deleting', 'SomethingNew', '') {
        (Get-AutoPauseDecision -State $_ -Tags $null -ExcludeTagName 'autopause' -ExcludeTagValue 'skip').Action | Should -Be 'Warn'
    }

    It 'honours the exclusion tag from a hashtable (case-insensitive name and value)' {
        $d = Get-AutoPauseDecision -State 'Active' -Tags @{ AutoPause = 'SKIP' } -ExcludeTagName 'autopause' -ExcludeTagValue 'skip'
        $d.Action | Should -Be 'Excluded'
    }

    It 'honours the exclusion tag from parsed JSON (PSCustomObject)' {
        $tags = '{"autopause":"skip","env":"dev"}' | ConvertFrom-Json
        (Get-AutoPauseDecision -State 'Active' -Tags $tags -ExcludeTagName 'autopause' -ExcludeTagValue 'skip').Action | Should -Be 'Excluded'
    }

    It 'does not exclude when the tag value differs' {
        (Get-AutoPauseDecision -State 'Active' -Tags @{ autopause = 'keep' } -ExcludeTagName 'autopause' -ExcludeTagValue 'skip').Action | Should -Be 'Pause'
    }

    It 'excludes on tag presence alone when no value is configured' {
        (Get-AutoPauseDecision -State 'Active' -Tags @{ autopause = 'anything' } -ExcludeTagName 'autopause' -ExcludeTagValue '').Action | Should -Be 'Excluded'
    }

    It 'applies the exclusion before the state check' {
        (Get-AutoPauseDecision -State 'Paused' -Tags @{ autopause = 'skip' } -ExcludeTagName 'autopause' -ExcludeTagValue 'skip').Action | Should -Be 'Excluded'
    }
}

Describe 'New-GraphRequestBody' {
    It 'queries every capacity when no scope is given' {
        $b = New-GraphRequestBody
        $b.query | Should -Match "type =~ 'microsoft.fabric/capacities'"
        $b.Contains('subscriptions') | Should -BeFalse
        $b.Contains('managementGroups') | Should -BeFalse
    }

    It 'adds filters for resource group, name and id' {
        $id = '/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-one/providers/Microsoft.Fabric/capacities/cap01'
        $b = New-GraphRequestBody -ResourceGroupName 'rg-one' -CapacityName 'cap01' -CapacityResourceId $id
        $b.query | Should -Match "resourceGroup =~ 'rg-one'"
        $b.query | Should -Match "name =~ 'cap01'"
        $b.query | Should -Match ([regex]::Escape("id =~ '$id'"))
    }

    It 'splits comma-separated subscriptions' {
        $b = New-GraphRequestBody -SubscriptionIds '11111111-1111-1111-1111-111111111111, 22222222-2222-2222-2222-222222222222'
        $b.subscriptions.Count | Should -Be 2
    }

    It 'scopes to a management group' {
        (New-GraphRequestBody -ManagementGroupId 'mg-platform').managementGroups | Should -Be @('mg-platform')
    }

    It 'rejects subscriptions and management group together' {
        { New-GraphRequestBody -SubscriptionIds '11111111-1111-1111-1111-111111111111' -ManagementGroupId 'mg' } | Should -Throw '*not both*'
    }

    It 'rejects values that could break out of the KQL string' -ForEach @(
        @{ Param = 'CapacityName'; Value = "x' | take 1 //" }
        @{ Param = 'ResourceGroupName'; Value = "rg'; drop" }
        @{ Param = 'ManagementGroupId'; Value = "mg' or 1==1" }
        @{ Param = 'SubscriptionIds'; Value = 'not-a-guid' }
    ) {
        $splat = @{ $Param = $Value }
        { New-GraphRequestBody @splat } | Should -Throw '*Invalid*'
    }
}

Describe 'Invoke-FabricCapacityAutoPause' {
    BeforeEach {
        $script:calls = New-Object System.Collections.Generic.List[string]
        $script:states = @{}
        Mock Connect-AzAccount { [pscustomobject]@{ Context = 'test' } }
        Mock Disable-AzContextAutosave {}
        Mock Start-Sleep {}
        Mock Write-Log {}

        Mock Invoke-AzRestMethod {
            $script:calls.Add("$Method $Path")
            if ($Path -like '/providers/Microsoft.ResourceGraph/*') {
                $rows = $script:states.Keys | Sort-Object | ForEach-Object {
                    @{ id = "/subscriptions/s1/resourceGroups/rg/providers/Microsoft.Fabric/capacities/$_"; name = $_
                       subscriptionId = 's1'; resourceGroup = 'rg'; sku = 'F2'; state = $script:states[$_].State; tags = $null }
                }
                return [pscustomobject]@{ StatusCode = 200; Content = (@{ data = @($rows) } | ConvertTo-Json -Depth 6) }
            }
            if ($Method -eq 'POST' -and $Path -like '*/suspend*') {
                $name = ($Path -split '/capacities/')[1].Split('/')[0]
                if ($script:states[$name].Deny) {
                    return [pscustomobject]@{ StatusCode = 403; Content = '{"error":{"code":"AuthorizationFailed","message":"no suspend"}}' }
                }
                $script:states[$name].State = 'Paused'
                return [pscustomobject]@{ StatusCode = 202; Content = '' }
            }
            $name = ($Path -split '/capacities/')[1].Split('?')[0]
            $s = $script:states[$name]
            [pscustomobject]@{ StatusCode = 200; Content = (@{ properties = @{ state = $s.State }; tags = $s.Tags } | ConvertTo-Json -Depth 6) }
        }
    }

    It 'pauses only Active capacities when enforcing' {
        $script:states = @{
            capactive = @{ State = 'Active' }
            cappaused = @{ State = 'Paused' }
            capbusy   = @{ State = 'Resuming' }
        }
        $r = @(Invoke-FabricCapacityAutoPause -DryRun $false -ExcludeTagName 'autopause' -ExcludeTagValue 'skip' -PassThru)

        ($r | Where-Object Name -eq 'capactive').Result | Should -Be 'Paused'
        ($r | Where-Object Name -eq 'cappaused').Result | Should -Be 'Skipped'
        ($r | Where-Object Name -eq 'capbusy').Result | Should -Be 'Deferred'
        @($script:calls | Where-Object { $_ -like 'POST*suspend*' }).Count | Should -Be 1
    }

    It 'never calls suspend in dry-run mode' {
        $script:states = @{ capactive = @{ State = 'Active' } }
        $r = @(Invoke-FabricCapacityAutoPause -DryRun $true -ExcludeTagName 'autopause' -ExcludeTagValue 'skip' -PassThru)

        $r[0].Result | Should -Be 'WouldPause'
        @($script:calls | Where-Object { $_ -like 'POST*suspend*' }).Count | Should -Be 0
    }

    It 'leaves a tagged capacity running' {
        $script:states = @{ capkeep = @{ State = 'Active'; Tags = @{ autopause = 'skip' } } }
        $r = @(Invoke-FabricCapacityAutoPause -DryRun $false -ExcludeTagName 'autopause' -ExcludeTagValue 'skip' -PassThru)

        $r[0].Result | Should -Be 'Excluded'
        @($script:calls | Where-Object { $_ -like 'POST*suspend*' }).Count | Should -Be 0
    }

    It 'writes log lines to the output stream so they appear in the Automation job output' {
        Mock Write-Log { Write-Output $Message }
        $script:states = @{ capactive = @{ State = 'Active' } }
        $out = @(Invoke-FabricCapacityAutoPause -DryRun $true -ExcludeTagName 'autopause' -ExcludeTagValue 'skip')
        ($out -join "`n") | Should -Match 'DRY RUN'
        ($out -join "`n") | Should -Match 'Summary: WouldPause=1'
    }

    It 'returns nothing without -PassThru' {
        $script:states = @{ capactive = @{ State = 'Active' } }
        $out = @(Invoke-FabricCapacityAutoPause -DryRun $true -ExcludeTagName 'autopause' -ExcludeTagValue 'skip')
        $out.Count | Should -Be 0
    }
    It 'is a no-op when there are no capacities' {
        $script:states = @{}
        { Invoke-FabricCapacityAutoPause -DryRun $false } | Should -Not -Throw
    }

    It 'throws so the job fails when a capacity cannot be paused, but still pauses the others' {
        $script:states = @{
            capdenied = @{ State = 'Active'; Deny = $true }
            capok     = @{ State = 'Active' }
        }
        { Invoke-FabricCapacityAutoPause -DryRun $false -ExcludeTagName 'autopause' -ExcludeTagValue 'skip' } | Should -Throw '*capdenied*'
        $script:states['capok'].State | Should -Be 'Paused'
    }

    It 'reports an error when a pause never completes' {
        Mock Get-CapacityPowerState { 'Pausing' }
        $script:clock = [datetime]::new(2026, 1, 1, 0, 0, 0, [DateTimeKind]::Utc)
        Mock Get-UtcNow { $script:clock = $script:clock.AddSeconds(30); $script:clock }
        $script:states = @{ capslow = @{ State = 'Active' } }
        { Invoke-FabricCapacityAutoPause -DryRun $false -PauseTimeoutMinutes 1 } | Should -Throw '*capslow*'
    }

    It 'verifies a pause that is already in progress without sending a second suspend' {
        Mock Get-CapacityPowerState { 'Paused' }
        $script:states = @{ cappausing = @{ State = 'Pausing' } }
        $r = @(Invoke-FabricCapacityAutoPause -DryRun $false -PassThru)
        $r[0].Result | Should -Be 'Paused'
        @($script:calls | Where-Object { $_ -like 'POST*suspend*' }).Count | Should -Be 0
    }

    It 'fails the job when a pause already in progress never finishes' {
        Mock Get-CapacityPowerState { 'Pausing' }
        $script:clock = [datetime]::new(2026, 1, 1, 0, 0, 0, [DateTimeKind]::Utc)
        Mock Get-UtcNow { $script:clock = $script:clock.AddSeconds(30); $script:clock }
        $script:states = @{ capstuck = @{ State = 'Pausing' } }
        { Invoke-FabricCapacityAutoPause -DryRun $false -PauseTimeoutMinutes 1 } | Should -Throw '*capstuck*'
    }

    It 'fails when a specifically requested capacity is not found' {
        $script:states = @{}
        { Invoke-FabricCapacityAutoPause -DryRun $true -CapacityName 'doesnotexist' } | Should -Throw '*not found*'
    }

    It 'warns but succeeds when nothing is visible and no capacity was requested' {
        $script:states = @{}
        { Invoke-FabricCapacityAutoPause -DryRun $true } | Should -Not -Throw
    }
}

Describe 'Wait-CapacitiesPaused' {
    BeforeEach {
        Mock Start-Sleep {}
        $script:clock = [datetime]::new(2026, 1, 1, 0, 0, 0, [DateTimeKind]::Utc)
        Mock Get-UtcNow { $script:clock = $script:clock.AddSeconds(30); $script:clock }
        function New-PendingItem([string] $Name) {
            [pscustomobject]@{ Id = "/x/$Name"; Row = [pscustomobject]@{ Name = $Name; Result = 'PauseRequested'; Detail = '' } }
        }
    }

    It 'marks every capacity Paused once all report Paused' {
        Mock Get-CapacityPowerState { 'Paused' }
        $items = @((New-PendingItem 'a'), (New-PendingItem 'b'))
        Wait-CapacitiesPaused -Pending $items -TimeoutMinutes 5 -PollSeconds 1
        $items.Row.Result | Should -Be @('Paused', 'Paused')
    }

    It 'accepts the legacy Suspended state as paused' {
        Mock Get-CapacityPowerState { 'Suspended' }
        $items = @(New-PendingItem 'a')
        Wait-CapacitiesPaused -Pending $items -TimeoutMinutes 5 -PollSeconds 1
        $items[0].Row.Result | Should -Be 'Paused'
    }

    It 'resolves capacities independently: one pauses, one never does' {
        $script:polls = @{}
        Mock Get-CapacityPowerState {
            $script:polls[$ResourceId] = 1 + [int]$script:polls[$ResourceId]
            if ($ResourceId -eq '/x/fast' -and $script:polls[$ResourceId] -ge 2) { 'Paused' } else { 'Pausing' }
        }
        $items = @((New-PendingItem 'fast'), (New-PendingItem 'slow'))
        Wait-CapacitiesPaused -Pending $items -TimeoutMinutes 3 -PollSeconds 1
        ($items | Where-Object { $_.Row.Name -eq 'fast' }).Row.Result | Should -Be 'Paused'
        $slow = ($items | Where-Object { $_.Row.Name -eq 'slow' }).Row
        $slow.Result | Should -Be 'Error'
        $slow.Detail | Should -Match 'Did not reach Paused within 3 min'
        $slow.Detail | Should -Match 'last state: Pausing'
    }

    It 'uses ONE shared deadline, not one per capacity (3-hour sandbox limit)' {
        $script:polls = 0
        Mock Get-CapacityPowerState { $script:polls++; 'Pausing' }
        $items = 1..10 | ForEach-Object { New-PendingItem "c$_" }
        Wait-CapacitiesPaused -Pending $items -TimeoutMinutes 2 -PollSeconds 1
        # 10 items; the clock moves 30 s per Get-UtcNow call, so a shared 2-minute deadline allows only a few rounds.
        $script:polls | Should -BeLessThan 80
        @($items | Where-Object { $_.Row.Result -eq 'Error' }).Count | Should -Be 10
    }

    It 'treats an unreadable state as not-yet-paused and reports unknown' {
        Mock Get-CapacityPowerState { $null }
        $items = @(New-PendingItem 'a')
        Wait-CapacitiesPaused -Pending $items -TimeoutMinutes 1 -PollSeconds 1
        $items[0].Row.Result | Should -Be 'Error'
        $items[0].Row.Detail | Should -Match 'last state: unknown'
    }

    It 'does nothing for an empty list' {
        { Wait-CapacitiesPaused -Pending @() -TimeoutMinutes 1 -PollSeconds 1 } | Should -Not -Throw
    }
}

Describe 'Get-RetryAfterSeconds' {
    It 'reads a numeric Retry-After from a dictionary (case-insensitive)' {
        Get-RetryAfterSeconds ([pscustomobject]@{ Headers = @{ 'retry-after' = '60' } }) | Should -Be 60
    }

    It 'reads the first value when the header holds an array' {
        Get-RetryAfterSeconds ([pscustomobject]@{ Headers = @{ 'Retry-After' = @('30') } }) | Should -Be 30
    }

    It 'returns 0 when absent, malformed, negative or when there are no headers' {
        Get-RetryAfterSeconds ([pscustomobject]@{ Headers = @{} }) | Should -Be 0
        Get-RetryAfterSeconds ([pscustomobject]@{ Headers = @{ 'Retry-After' = 'soon' } }) | Should -Be 0
        Get-RetryAfterSeconds ([pscustomobject]@{ Headers = @{ 'Retry-After' = '-5' } }) | Should -Be 0
        Get-RetryAfterSeconds ([pscustomobject]@{ Headers = $null }) | Should -Be 0
        Get-RetryAfterSeconds ([pscustomobject]@{ StatusCode = 429 }) | Should -Be 0
    }
}

Describe 'Connect-AutoPauseIdentity' {
    BeforeEach {
        Mock Disable-AzContextAutosave {}
    }

    It 'fails with a clear message when sign-in returns no context' {
        Mock Connect-AzAccount { $null }
        { Connect-AutoPauseIdentity -ClientId 'x' } | Should -Throw '*returned no context*'
    }

    It 'signs in with the user-assigned identity client ID when given' {
        Mock Connect-AzAccount { [pscustomobject]@{ Context = 'ok' } }
        Connect-AutoPauseIdentity -ClientId '00000000-0000-0000-0000-000000000000'
        Should -Invoke Connect-AzAccount -Times 1 -ParameterFilter { $Identity -and $AccountId -eq '00000000-0000-0000-0000-000000000000' }
    }

    It 'uses the system-assigned identity when no client ID is given' {
        Mock Connect-AzAccount { [pscustomobject]@{ Context = 'ok' } }
        Connect-AutoPauseIdentity -ClientId ''
        Should -Invoke Connect-AzAccount -Times 1 -ParameterFilter { $Identity -and -not $AccountId }
    }
}

Describe 'ConvertTo-StrictBool' {
    It 'parses true-like values' -ForEach @('true', 'True', ' TRUE ', '1', 'yes', '$true') {
        ConvertTo-StrictBool -Value $_ | Should -BeTrue
    }

    It 'parses false-like values' -ForEach @('false', 'False', '0', 'no', '$false') {
        ConvertTo-StrictBool -Value $_ | Should -BeFalse
    }

    It 'passes real booleans through' {
        ConvertTo-StrictBool -Value $true | Should -BeTrue
        ConvertTo-StrictBool -Value $false | Should -BeFalse
    }

    It 'refuses ambiguous input so a typo can never cause a pause' -ForEach @('', 'maybe', 'flase', 'tru', '2', 'true;false') {
        { ConvertTo-StrictBool -Value $_ -Name 'DryRun' } | Should -Throw '*Invalid DryRun*'
    }
}

Describe 'Input hardening' {
    BeforeEach {
        Mock Connect-AzAccount { [pscustomobject]@{ Context = 'test' } }
        Mock Disable-AzContextAutosave {}
        Mock Write-Log {}
        Mock Invoke-AzRestMethod {
            [pscustomobject]@{ StatusCode = 200; Content = (@{ data = @() } | ConvertTo-Json -Depth 4) }
        }
    }

    It 'refuses an empty or whitespace exclusion tag name' -ForEach @('', '   ') {
        { Invoke-FabricCapacityAutoPause -ExcludeTagName $_ } | Should -Throw '*ExcludeTagName must not be empty*'
    }

    It 'rejects a trailing newline on identifiers' {
        { New-GraphRequestBody -CapacityName "cap01`n" } | Should -Throw '*Invalid*'
        { New-GraphRequestBody -ResourceGroupName "rg-one`n" } | Should -Throw '*Invalid*'
    }

    It 'rejects a subscription ID made of hyphens or the wrong shape' -ForEach @(
        ('-' * 36)
        '11111111-1111-1111-1111-11111111111'
        '11111111-1111-1111-1111-1111111111111'
        'gggggggg-1111-1111-1111-111111111111'
    ) {
        { New-GraphRequestBody -SubscriptionIds $_ } | Should -Throw '*Invalid*'
    }

    It 'accepts a well-formed subscription ID' {
        { New-GraphRequestBody -SubscriptionIds '11111111-1111-1111-1111-111111111111' } | Should -Not -Throw
    }

    It 'rejects non-ASCII characters in names' {
        $name = 'rg-caf' + [char]0x00E9
        { New-GraphRequestBody -ResourceGroupName $name } | Should -Throw '*Invalid ResourceGroupName*'
    }

    It 'rejects out-of-range polling and timeout values' {
        { Invoke-FabricCapacityAutoPause -PollSeconds -1 } | Should -Throw
        { Invoke-FabricCapacityAutoPause -PauseTimeoutMinutes 0 } | Should -Throw
        { Invoke-FabricCapacityAutoPause -PauseTimeoutMinutes 151 } | Should -Throw
    }
}

Describe 'Invoke-Arm retry behaviour' {
    BeforeEach {
        Mock Start-Sleep {}
    }

    It 'retries throttled requests and then succeeds' {
        $script:attempts = 0
        Mock Invoke-AzRestMethod {
            $script:attempts++
            if ($script:attempts -lt 3) { return [pscustomobject]@{ StatusCode = 429; Content = '' } }
            [pscustomobject]@{ StatusCode = 200; Content = '{"ok":true}' }
        }
        $r = Invoke-Arm -Method GET -Path '/x'
        $r.StatusCode | Should -Be 200
        $script:attempts | Should -Be 3
    }

    It 'does not retry client errors' {
        $script:attempts = 0
        Mock Invoke-AzRestMethod { $script:attempts++; [pscustomobject]@{ StatusCode = 403; Content = '{"error":{"code":"AuthorizationFailed","message":"m"}}' } }
        $r = Invoke-Arm -Method GET -Path '/x'
        $r.StatusCode | Should -Be 403
        $script:attempts | Should -Be 1
    }

    It 'waits at least as long as Retry-After before retrying a throttled request' {
        $script:attempts = 0
        Mock Invoke-AzRestMethod {
            $script:attempts++
            if ($script:attempts -eq 1) { return [pscustomobject]@{ StatusCode = 429; Content = ''; Headers = @{ 'Retry-After' = '90' } } }
            [pscustomobject]@{ StatusCode = 200; Content = '{}' }
        }
        $null = Invoke-Arm -Method GET -Path '/x'
        Should -Invoke Start-Sleep -Times 1 -ParameterFilter { $Seconds -ge 90 }
    }

    It 'caps an absurd Retry-After at two minutes' {
        $script:attempts = 0
        Mock Invoke-AzRestMethod {
            $script:attempts++
            if ($script:attempts -eq 1) { return [pscustomobject]@{ StatusCode = 503; Content = ''; Headers = @{ 'Retry-After' = '99999' } } }
            [pscustomobject]@{ StatusCode = 200; Content = '{}' }
        }
        $null = Invoke-Arm -Method GET -Path '/x'
        Should -Invoke Start-Sleep -Times 1 -ParameterFilter { $Seconds -eq 120 }
    }
}
