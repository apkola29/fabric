#Requires -Modules @{ ModuleName = 'Pester'; ModuleVersion = '5.0.0' }

BeforeDiscovery {
    $contractCases = @(
        @{ Name = 'SubscriptionId'; Type = 'String'; Mandatory = $true; Default = $null }
        @{ Name = 'Location'; Type = 'String'; Mandatory = $true; Default = $null }
        @{ Name = 'ResourceGroupName'; Type = 'String'; Mandatory = $false; Default = "'rg-fabric-autopause'" }
        @{ Name = 'NamePrefix'; Type = 'String'; Mandatory = $false; Default = "'fabricautopause'" }
        @{ Name = 'TimeZone'; Type = 'String'; Mandatory = $false; Default = "'UTC'" }
        @{ Name = 'ScheduleTime'; Type = 'String'; Mandatory = $false; Default = "'00:00'" }
        @{ Name = 'BackstopOffsetMinutes'; Type = 'Int32'; Mandatory = $false; Default = '60' }
        @{ Name = 'AlertEmails'; Type = 'String[]'; Mandatory = $false; Default = '@()' }
        @{ Name = 'ScopeSubscriptionIds'; Type = 'String'; Mandatory = $false; Default = "''" }
        @{ Name = 'ScopeManagementGroupId'; Type = 'String'; Mandatory = $false; Default = "''" }
        @{ Name = 'ScopeResourceGroupName'; Type = 'String'; Mandatory = $false; Default = "''" }
        @{ Name = 'ScopeCapacityName'; Type = 'String'; Mandatory = $false; Default = "''" }
        @{ Name = 'ScopeCapacityResourceId'; Type = 'String'; Mandatory = $false; Default = "''" }
        @{ Name = 'ExcludeTagName'; Type = 'String'; Mandatory = $false; Default = "'autopause'" }
        @{ Name = 'ExcludeTagValue'; Type = 'String'; Mandatory = $false; Default = "'skip'" }
        @{ Name = 'EnableEnforcement'; Type = 'SwitchParameter'; Mandatory = $false; Default = $null }
        @{ Name = 'IncludeWritePermission'; Type = 'SwitchParameter'; Mandatory = $false; Default = $null }
        @{ Name = 'SkipSubscriptionRoleAssignment'; Type = 'SwitchParameter'; Mandatory = $false; Default = $null }
        @{ Name = 'CustomRoleName'; Type = 'String'; Mandatory = $false; Default = "'Fabric Capacity AutoPause Operator'" }
        @{ Name = 'AdditionalAssignableScopes'; Type = 'String[]'; Mandatory = $false; Default = '@()' }
        @{ Name = 'Tags'; Type = 'Hashtable'; Mandatory = $false; Default = '@{}' }
        @{ Name = 'AzPackageVersion'; Type = 'String'; Mandatory = $false; Default = "'12.3.0'" }
    )

    $invalidArgumentCases = @(
        @{ Label = 'a SubscriptionId that is not a GUID'; Splat = @{ SubscriptionId = 'not-a-guid'; Location = 'eastus' } }
        @{ Label = 'an empty Location'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = '' } }
        @{ Label = 'a Location with punctuation'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'east_us!' } }
        @{ Label = 'a ResourceGroupName ending in a period'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; ResourceGroupName = 'rg.' } }
        @{ Label = 'a NamePrefix that starts with a digit'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; NamePrefix = '1bad' } }
        @{ Label = 'a NamePrefix that is too short'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; NamePrefix = 'ab' } }
        @{ Label = 'a ScheduleTime of 24:00'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; ScheduleTime = '24:00' } }
        @{ Label = 'a ScheduleTime without leading zeros'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; ScheduleTime = '9:5' } }
        @{ Label = 'a negative BackstopOffsetMinutes'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; BackstopOffsetMinutes = -1 } }
        @{ Label = 'a BackstopOffsetMinutes of a full day'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; BackstopOffsetMinutes = 1440 } }
        @{ Label = 'an empty TimeZone'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; TimeZone = '' } }
        @{ Label = 'an empty CustomRoleName'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; CustomRoleName = '' } }
        @{ Label = 'a SubscriptionId with a trailing newline'; Splat = @{ SubscriptionId = "11111111-1111-1111-1111-111111111111`n"; Location = 'eastus' } }
        @{ Label = 'an AzPackageVersion of latest'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; AzPackageVersion = 'latest' } }
        @{ Label = 'an AzPackageVersion without a patch number'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; AzPackageVersion = '12.3' } }
        @{ Label = 'an AzPackageVersion with a suffix'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; AzPackageVersion = '12.3.0-rc1' } }
        @{ Label = 'an AzPackageVersion with a trailing newline'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; AzPackageVersion = "12.3.0`n" } }
        @{ Label = 'an empty AzPackageVersion'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; AzPackageVersion = '' } }
        @{ Label = 'an empty ExcludeTagName'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; ExcludeTagName = '' } }
        @{ Label = 'a whitespace-only ExcludeTagName'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; ExcludeTagName = '   ' } }
        @{ Label = 'a ScopeSubscriptionIds entry that is not a GUID'; Splat = @{ SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus'; ScopeSubscriptionIds = '11111111-1111-1111-1111-111111111111,not-a-guid' } }
    )
}

BeforeAll {
    $script:DeployPath = Join-Path $PSScriptRoot '..' 'scripts' 'deploy.ps1'
    $script:DeploySource = Get-Content -LiteralPath $script:DeployPath -Raw
    $script:InfraPath = Join-Path $PSScriptRoot '..' 'infra'
    . $script:DeployPath -SubscriptionId '00000000-0000-0000-0000-000000000000' -Location 'eastus'

    function New-TestSettings {
        param([hashtable] $Override = @{}, [string] $RepoRoot = $TestDrive)
        $values = @{
            SubscriptionId             = '11111111-1111-1111-1111-111111111111'
            Location                   = 'eastus2'
            ResourceGroupName          = 'rg-test'
            NamePrefix                 = 'fabricautopause'
            TimeZone                   = 'UTC'
            ScheduleTime               = '00:00'
            BackstopOffsetMinutes      = 60
            AlertEmails                = @()
            ScopeSubscriptionIds       = ''
            ScopeManagementGroupId     = ''
            ScopeResourceGroupName     = ''
            ScopeCapacityName          = ''
            ScopeCapacityResourceId    = ''
            ExcludeTagName             = 'autopause'
            ExcludeTagValue            = 'skip'
            EnableEnforcement          = $false
            IncludeWritePermission     = $false
            SkipSubscriptionRoleAssignment = $false
            CustomRoleName             = 'Fabric Capacity AutoPause Operator'
            AdditionalAssignableScopes = @()
            Tags                       = @{}
            AzPackageVersion           = '12.3.0'
        }
        foreach ($key in $Override.Keys) { $values[$key] = $Override[$key] }
        return Resolve-DeploymentSettings -Values $values -RepoRoot $RepoRoot
    }

    function Get-JsonParameterString {
        # ConvertFrom-Json would turn ISO timestamps into DateTime values, so read the raw string instead.
        param([Parameter(Mandatory)] [string] $Json, [Parameter(Mandatory)] [string] $Name)
        $document = [System.Text.Json.JsonDocument]::Parse($Json)
        try { return $document.RootElement.GetProperty('parameters').GetProperty($Name).GetProperty('value').GetString() }
        finally { $document.Dispose() }
    }

    function New-StubRepo {
        param([Parameter(Mandatory)] [string] $Root)
        $null = New-Item -ItemType Directory -Path (Join-Path $Root 'infra'), (Join-Path $Root 'runbooks') -Force
        Set-Content -LiteralPath (Join-Path $Root 'infra' 'main.bicep') -Value 'targetScope = ''subscription'''
        Set-Content -LiteralPath (Join-Path $Root 'runbooks' 'Invoke-FabricCapacityAutoPause.ps1') -Value 'Write-Output ''stub runbook'''
    }

    function New-DeploymentJson {
        param([string] $BackstopScheduleName = 'autopause-backstop', [string] $RoleDefinitionId = '/subscriptions/11111111-1111-1111-1111-111111111111/providers/Microsoft.Authorization/roleDefinitions/44444444-4444-4444-4444-444444444444')
        return @"
{
  "properties": {
    "provisioningState": "Succeeded",
    "outputs": {
      "resourceGroupName": { "type": "String", "value": "rg-test" },
      "automationAccountName": { "type": "String", "value": "aa-test" },
      "runbookName": { "type": "String", "value": "Invoke-FabricCapacityAutoPause" },
      "runtimeEnvironmentName": { "type": "String", "value": "pwsh74" },
      "identityClientId": { "type": "String", "value": "22222222-2222-2222-2222-222222222222" },
      "identityPrincipalId": { "type": "String", "value": "33333333-3333-3333-3333-333333333333" },
      "roleDefinitionId": { "type": "String", "value": "$RoleDefinitionId" },
      "nightlyScheduleName": { "type": "String", "value": "autopause-nightly" },
      "backstopScheduleName": { "type": "String", "value": "$BackstopScheduleName" }
    }
  }
}
"@ | ConvertFrom-Json
    }
}

Describe 'deploy.ps1' {
BeforeEach {
    $script:Messages = [System.Collections.Generic.List[string]]::new()
    Mock Write-Message { $script:Messages.Add([string]$Text) }
    Mock Write-Warning { $script:Messages.Add("WARNING: $Message") }
    Mock Start-Sleep { }
}

Describe 'deploy.ps1 parameter contract' {
    BeforeAll {
        $script:ParseErrors = $null
        $script:Tokens = $null
        $script:Ast = [System.Management.Automation.Language.Parser]::ParseFile(
            (Resolve-Path $script:DeployPath).Path, [ref]$script:Tokens, [ref]$script:ParseErrors)
        $script:Source = Get-Content -LiteralPath $script:DeployPath -Raw
    }

    It 'parses with no errors' {
        @($script:ParseErrors).Count | Should -Be 0
    }

    It 'enables strict mode and stop-on-error, and supports ShouldProcess' {
        $script:Source | Should -Match '(?m)^Set-StrictMode -Version Latest\s*$'
        $script:Source | Should -Match "(?m)^\`$ErrorActionPreference = 'Stop'\s*$"
        $script:Source | Should -Match '(?m)^#Requires -Version 7'
        $binding = $script:Ast.ParamBlock.Attributes | Where-Object { $_.TypeName.Name -eq 'CmdletBinding' }
        @($binding.NamedArguments | Where-Object { $_.ArgumentName -eq 'SupportsShouldProcess' }).Count | Should -Be 1
    }

    It 'declares exactly the documented parameters' {
        $declared = @($script:Ast.ParamBlock.Parameters | ForEach-Object { $_.Name.VariablePath.UserPath })
        $declared | Should -Be @(
            'SubscriptionId', 'Location', 'ResourceGroupName', 'NamePrefix', 'TimeZone', 'ScheduleTime', 'BackstopOffsetMinutes',
            'AlertEmails', 'ScopeSubscriptionIds', 'ScopeManagementGroupId', 'ScopeResourceGroupName', 'ScopeCapacityName',
            'ScopeCapacityResourceId', 'ExcludeTagName', 'ExcludeTagValue', 'EnableEnforcement', 'IncludeWritePermission',
            'SkipSubscriptionRoleAssignment', 'CustomRoleName', 'AdditionalAssignableScopes', 'Tags', 'AzPackageVersion')
    }

    It 'declares -<Name> as <Type> (Mandatory=<Mandatory>, default <Default>)' -ForEach $contractCases {
        $parameter = $script:Ast.ParamBlock.Parameters | Where-Object { $_.Name.VariablePath.UserPath -eq $Name }
        $parameter | Should -Not -BeNullOrEmpty
        $parameter.StaticType.Name | Should -Be $Type
        ($parameter.Extent.Text -match 'Mandatory') | Should -Be $Mandatory
        if ($null -ne $Default) { $parameter.DefaultValue.Extent.Text | Should -Be $Default }
        else { $parameter.DefaultValue | Should -BeNullOrEmpty }
    }

    It 'contains no real identifiers (only all-zero placeholder GUIDs and example.com addresses)' {
        $guids = [regex]::Matches($script:Source, '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}') | ForEach-Object { $_.Value }
        @($guids | Where-Object { $_ -notmatch '^[0-]+$' }) | Should -BeNullOrEmpty
        $emails = [regex]::Matches($script:Source, '[\w\.\-]+@[\w\-]+\.[\w\.\-]+') | ForEach-Object { $_.Value }
        @($emails | Where-Object { $_ -notmatch '@example\.com$' }) | Should -BeNullOrEmpty
    }

    It 'documents -<Name> in the comment-based help' -ForEach $contractCases {
        $help = Get-Help -Name (Resolve-Path $script:DeployPath).Path -Parameter $Name
        (@($help.description | ForEach-Object { $_.Text }) -join ' ').Trim() | Should -Not -BeNullOrEmpty
    }

    It 'documents the least-privilege, tag and hash behaviour in the comment-based help' {
        $script:Source | Should -Match '(?s)\.PARAMETER SkipSubscriptionRoleAssignment.*?NOTHING CAN BE PAUSED'
        $script:Source | Should -Match '(?s)\.PARAMETER IncludeWritePermission.*?scale a capacity and change its capacity admins'
        $script:Source | Should -Match '(?s)\.PARAMETER ExcludeTagName.*?must not be empty or whitespace'
        $script:Source | Should -Match '(?s)\.PARAMETER AzPackageVersion.*?Default: 12\.3\.0'
        $script:Source | Should -Match 'prints its SHA-256'
    }
}

Describe 'deploy.ps1 argument validation' {
    It 'rejects <Label> before doing any work' -ForEach $invalidArgumentCases {
        $callArgs = $Splat
        { & $script:DeployPath @callArgs -WhatIf } | Should -Throw
    }

    It 'explains an invalid SubscriptionId' {
        { & $script:DeployPath -SubscriptionId 'nope' -Location 'eastus' -WhatIf } | Should -Throw '*SubscriptionId must be a GUID*'
    }

    It 'explains an invalid AzPackageVersion' {
        { & $script:DeployPath -SubscriptionId '11111111-1111-1111-1111-111111111111' -Location 'eastus' -AzPackageVersion 'latest' -WhatIf } | Should -Throw '*AzPackageVersion must be a version such as 12.3.0*'
    }

    It 'explains that an empty ExcludeTagName would disable every opt-out' {
        { & $script:DeployPath -SubscriptionId '11111111-1111-1111-1111-111111111111' -Location 'eastus' -ExcludeTagName '  ' -WhatIf } | Should -Throw '*ExcludeTagName must not be empty or whitespace*'
    }

    It 'reports the offending scope subscription entry' {
        { & $script:DeployPath -SubscriptionId '11111111-1111-1111-1111-111111111111' -Location 'eastus' -ScopeSubscriptionIds 'oops' -WhatIf } | Should -Throw "*ScopeSubscriptionIds contains 'oops'*"
    }
}

Describe 'Resolve-DeploymentSettings' {
    It 'builds paths and a stable deployment name' {
        $s = New-TestSettings
        $s.DeploymentName | Should -Be 'deploy-fabricautopause'
        $s.TemplatePath | Should -Be (Join-Path $TestDrive 'infra' 'main.bicep')
        $s.RunbookPath | Should -Be (Join-Path $TestDrive 'runbooks' 'Invoke-FabricCapacityAutoPause.ps1')
    }

    It 'normalises the comma separated subscription list' {
        $s = New-TestSettings @{ ScopeSubscriptionIds = ' 11111111-1111-1111-1111-111111111111, 22222222-2222-2222-2222-222222222222;33333333-3333-3333-3333-333333333333 ' }
        $s.ScopeSubscriptionIds | Should -Be '11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222,33333333-3333-3333-3333-333333333333'
    }

    It 'rejects a scope subscription that is not a GUID' {
        { New-TestSettings @{ ScopeSubscriptionIds = 'abc' } } | Should -Throw '*not a subscription GUID*'
    }

    It 'rejects subscription IDs together with a management group' {
        { New-TestSettings @{ ScopeSubscriptionIds = '11111111-1111-1111-1111-111111111111'; ScopeManagementGroupId = 'mg-root' } } | Should -Throw '*not both*'
    }

    It 'rejects an invalid capacity name' {
        { New-TestSettings @{ ScopeCapacityName = 'bad name;' } } | Should -Throw '*ScopeCapacityName*'
    }

    It 'rejects a capacity resource ID that is not a Fabric capacity' {
        { New-TestSettings @{ ScopeCapacityResourceId = '/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1' } } | Should -Throw '*ScopeCapacityResourceId*'
    }

    It 'accepts a valid capacity resource ID' {
        $id = '/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-fabric/providers/Microsoft.Fabric/capacities/cap01'
        (New-TestSettings @{ ScopeCapacityResourceId = $id }).ScopeCapacityResourceId | Should -Be $id
    }

    It 'rejects an invalid alert email' {
        { New-TestSettings @{ AlertEmails = @('ops@example.com', 'not-an-email') } } | Should -Throw '*not an email*'
    }

    It 'rejects an assignable scope that is not a subscription, resource group or management group' {
        { New-TestSettings @{ AdditionalAssignableScopes = @('/providers/Microsoft.Compute/foo') } } | Should -Throw '*AdditionalAssignableScopes*'
    }

    It 'accepts subscription, resource group and management group assignable scopes' {
        $scopes = @(
            '/subscriptions/11111111-1111-1111-1111-111111111111'
            '/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-one'
            '/providers/Microsoft.Management/managementGroups/mg-one'
        )
        (New-TestSettings @{ AdditionalAssignableScopes = $scopes }).AdditionalAssignableScopes | Should -Be $scopes
    }

    It 'stringifies tag values' {
        $s = New-TestSettings @{ Tags = @{ owner = 'team'; costCenter = 42 } }
        $s.Tags['costCenter'] | Should -BeOfType [string]
        $s.Tags['costCenter'] | Should -Be '42'
    }

    It 'throws when a setting is missing' {
        { Resolve-DeploymentSettings -Values @{ SubscriptionId = 'x' } -RepoRoot $TestDrive } | Should -Throw "*Missing deployment setting*"
    }

    It 'requires the <Key> setting' -ForEach @(@{ Key = 'SkipSubscriptionRoleAssignment' }, @{ Key = 'AzPackageVersion' }) {
        $values = @{
            SubscriptionId = '11111111-1111-1111-1111-111111111111'; Location = 'eastus2'; ResourceGroupName = 'rg-test'; NamePrefix = 'fabricautopause'
            TimeZone = 'UTC'; ScheduleTime = '00:00'; BackstopOffsetMinutes = 60; AlertEmails = @(); ScopeSubscriptionIds = ''
            ScopeManagementGroupId = ''; ScopeResourceGroupName = ''; ScopeCapacityName = ''; ScopeCapacityResourceId = ''
            ExcludeTagName = 'autopause'; ExcludeTagValue = 'skip'; EnableEnforcement = $false; IncludeWritePermission = $false
            SkipSubscriptionRoleAssignment = $false; CustomRoleName = 'r'; AdditionalAssignableScopes = @(); Tags = @{}; AzPackageVersion = '12.3.0'
        }
        $values.Remove($Key)
        { Resolve-DeploymentSettings -Values $values -RepoRoot $TestDrive } | Should -Throw "*Missing deployment setting '$Key'*"
    }

    It 'rejects an ExcludeTagName of <Label>, because an empty tag name would disable every opt-out' -ForEach @(
        @{ Label = 'an empty string'; Value = '' }
        @{ Label = 'a space'; Value = ' ' }
        @{ Label = 'a tab'; Value = "`t" }
        @{ Label = 'mixed whitespace'; Value = " `t`r`n " }
        @{ Label = 'null'; Value = $null }
    ) {
        { New-TestSettings @{ ExcludeTagName = $Value } } | Should -Throw '*ExcludeTagName must not be empty or whitespace*'
    }

    It 'trims whitespace around a valid ExcludeTagName and leaves ExcludeTagValue alone' {
        $s = New-TestSettings @{ ExcludeTagName = '  nopause ' ; ExcludeTagValue = ' keep ' }
        $s.ExcludeTagName | Should -Be 'nopause'
        $s.ExcludeTagValue | Should -Be ' keep '
    }

    It 'still allows an empty ExcludeTagValue (exclude on tag presence alone)' {
        (New-TestSettings @{ ExcludeTagValue = '' }).ExcludeTagValue | Should -Be ''
    }

    It 'validates scope subscription IDs with a strict, anchored GUID pattern (\A...\z, not ^...$)' {
        $script:DeploySource | Should -Match ([regex]::Escape("`$guid = '\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\z'"))
        $script:DeploySource | Should -Not -Match '(?m)^\s*\$guid = ''\^'
    }

    It 'rejects a scope subscription entry that is <Label>' -ForEach @(
        @{ Label = 'a GUID with a prefix'; Value = 'x11111111-1111-1111-1111-111111111111' }
        @{ Label = 'a GUID with a suffix'; Value = '11111111-1111-1111-1111-1111111111112' }
        @{ Label = 'a GUID in braces'; Value = '{11111111-1111-1111-1111-111111111111}' }
        @{ Label = 'a GUID without dashes'; Value = '11111111111111111111111111111111' }
        @{ Label = 'a GUID with a non-hex character'; Value = '1111111g-1111-1111-1111-111111111111' }
        @{ Label = 'a valid GUID followed by a junk entry'; Value = '11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-22222222222' }
    ) {
        { New-TestSettings @{ ScopeSubscriptionIds = $Value } } | Should -Throw '*not a subscription GUID*'
    }

    It 'accepts upper-case scope subscription GUIDs' {
        (New-TestSettings @{ ScopeSubscriptionIds = 'AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE' }).ScopeSubscriptionIds | Should -Be 'AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE'
    }

    It 'keeps the Az package version and the subscription-role-assignment choice in the settings' {
        $default = New-TestSettings
        $default.AzPackageVersion | Should -Be '12.3.0'
        $default.SkipSubscriptionRoleAssignment | Should -BeFalse
        $custom = New-TestSettings @{ AzPackageVersion = '13.0.1'; SkipSubscriptionRoleAssignment = $true }
        $custom.AzPackageVersion | Should -Be '13.0.1'
        $custom.SkipSubscriptionRoleAssignment | Should -BeTrue
    }

    It 'rejects an AzPackageVersion that is not x.y.z' -ForEach @(
        @{ Value = 'latest' }, @{ Value = '12.3' }, @{ Value = '12.3.0.1' }, @{ Value = '12.3.0-rc1' }, @{ Value = '' }, @{ Value = 'v12.3.0' }
    ) {
        { New-TestSettings @{ AzPackageVersion = $Value } } | Should -Throw '*AzPackageVersion*is not a version such as 12.3.0*'
    }
}

Describe 'Get-ScheduleStartTimes' {
    It 'returns tonight and one hour later in UTC' {
        $now = [datetime]::new(2026, 10, 15, 20, 0, 0, [DateTimeKind]::Utc)
        $t = Get-ScheduleStartTimes -TimeZoneId 'UTC' -TimeOfDay '00:00' -BackstopOffsetMinutes 60 -NowUtc $now
        $t.NightlyText | Should -Be '2026-10-16T00:00:00+00:00'
        $t.BackstopText | Should -Be '2026-10-16T01:00:00+00:00'
    }

    It 'rolls the backstop over midnight when the nightly run is late in the evening' {
        $now = [datetime]::new(2026, 10, 15, 20, 0, 0, [DateTimeKind]::Utc)
        $t = Get-ScheduleStartTimes -TimeZoneId 'UTC' -TimeOfDay '23:30' -BackstopOffsetMinutes 60 -NowUtc $now
        $t.NightlyText | Should -Be '2026-10-15T23:30:00+00:00'
        $t.BackstopText | Should -Be '2026-10-16T00:30:00+00:00'
    }

    It 'keeps the backstop after the nightly run when the nightly run itself rolls to tomorrow' {
        $now = [datetime]::new(2026, 10, 15, 23, 25, 0, [DateTimeKind]::Utc)
        $t = Get-ScheduleStartTimes -TimeZoneId 'UTC' -TimeOfDay '23:30' -BackstopOffsetMinutes 60 -NowUtc $now
        $t.NightlyText | Should -Be '2026-10-16T23:30:00+00:00'
        $t.BackstopText | Should -Be '2026-10-17T00:30:00+00:00'
        ($t.Backstop - $t.Nightly).TotalMinutes | Should -Be 60
    }

    It 'supports offsets that cross midnight by more than an hour and the maximum offset' {
        $now = [datetime]::new(2026, 10, 15, 20, 0, 0, [DateTimeKind]::Utc)
        (Get-ScheduleStartTimes -TimeZoneId 'UTC' -TimeOfDay '23:30' -BackstopOffsetMinutes 150 -NowUtc $now).BackstopText | Should -Be '2026-10-16T02:00:00+00:00'
        (Get-ScheduleStartTimes -TimeZoneId 'UTC' -TimeOfDay '23:30' -BackstopOffsetMinutes 1439 -NowUtc $now).BackstopText | Should -Be '2026-10-16T23:29:00+00:00'
    }

    It 'disables the backstop when the offset is 0' {
        $now = [datetime]::new(2026, 10, 15, 20, 0, 0, [DateTimeKind]::Utc)
        $t = Get-ScheduleStartTimes -TimeZoneId 'UTC' -TimeOfDay '00:00' -BackstopOffsetMinutes 0 -NowUtc $now
        $t.Backstop | Should -BeNullOrEmpty
        $t.BackstopText | Should -Be ''
    }

    It 'uses the zone offset on the day of each run (America/Chicago, daylight time)' {
        $now = [datetime]::new(2026, 7, 1, 12, 0, 0, [DateTimeKind]::Utc)
        $t = Get-ScheduleStartTimes -TimeZoneId 'America/Chicago' -TimeOfDay '23:30' -BackstopOffsetMinutes 60 -NowUtc $now
        $t.NightlyText | Should -Be '2026-07-01T23:30:00-05:00'
        $t.BackstopText | Should -Be '2026-07-02T00:30:00-05:00'
    }

    It 'moves a backstop that lands in the spring-forward gap to the first valid hour' {
        $now = [datetime]::new(2026, 3, 7, 12, 0, 0, [DateTimeKind]::Utc)
        $t = Get-ScheduleStartTimes -TimeZoneId 'America/Chicago' -TimeOfDay '01:30' -BackstopOffsetMinutes 60 -NowUtc $now
        $t.NightlyText | Should -Be '2026-03-08T01:30:00-06:00'
        $t.BackstopText | Should -Be '2026-03-08T03:30:00-05:00'
    }

    It 'rejects an unknown time zone' {
        { Get-ScheduleStartTimes -TimeZoneId 'Not/AZone' -TimeOfDay '00:00' -BackstopOffsetMinutes 60 } | Should -Throw
    }
}

Describe 'New-JobScheduleParameterMap' {
    It 'defaults to DryRun true and omits empty scope values' {
        $map = New-JobScheduleParameterMap -Settings (New-TestSettings) -IdentityClientId '22222222-2222-2222-2222-222222222222'
        @($map.Keys) | Should -Be @('ExcludeTagName', 'ExcludeTagValue', 'UserAssignedIdentityClientId', 'DryRun')
        $map['DryRun'] | Should -Be 'true'
        $map['ExcludeTagName'] | Should -Be 'autopause'
        $map['ExcludeTagValue'] | Should -Be 'skip'
        $map['UserAssignedIdentityClientId'] | Should -Be '22222222-2222-2222-2222-222222222222'
    }

    It 'sets DryRun false when enforcement is enabled' {
        $map = New-JobScheduleParameterMap -Settings (New-TestSettings @{ EnableEnforcement = $true }) -IdentityClientId 'cid'
        $map['DryRun'] | Should -Be 'false'
    }

    It 'includes every scope value that is set, using the runbook parameter names' {
        $id = '/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-fabric/providers/Microsoft.Fabric/capacities/cap01'
        $s = New-TestSettings @{
            ScopeSubscriptionIds    = '11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222'
            ScopeResourceGroupName  = 'rg-fabric'
            ScopeCapacityName       = 'cap01'
            ScopeCapacityResourceId = $id
        }
        $map = New-JobScheduleParameterMap -Settings $s -IdentityClientId 'cid'
        $map['SubscriptionIds'] | Should -Be '11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222'
        $map['ResourceGroupName'] | Should -Be 'rg-fabric'
        $map['CapacityName'] | Should -Be 'cap01'
        $map['CapacityResourceId'] | Should -Be $id
        $map.Contains('ManagementGroupId') | Should -BeFalse
    }

    It 'passes the management group when it is the only scope' {
        $map = New-JobScheduleParameterMap -Settings (New-TestSettings @{ ScopeManagementGroupId = 'mg-one' }) -IdentityClientId 'cid'
        $map['ManagementGroupId'] | Should -Be 'mg-one'
        $map.Contains('SubscriptionIds') | Should -BeFalse
    }

    It 'sends every value as a string' {
        $s = New-TestSettings @{ EnableEnforcement = $true; ScopeResourceGroupName = 'rg-fabric' }
        $map = New-JobScheduleParameterMap -Settings $s -IdentityClientId 'cid'
        foreach ($value in $map.Values) { $value | Should -BeOfType [string] }
    }

    It 'serialises every runbook parameter as a JSON string (no booleans or numbers on the wire)' -ForEach @(@{ Enforce = $false }, @{ Enforce = $true }) {
        $id = '/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-fabric/providers/Microsoft.Fabric/capacities/cap01'
        $s = New-TestSettings @{
            EnableEnforcement       = $Enforce
            IncludeWritePermission  = $true
            ScopeSubscriptionIds    = '11111111-1111-1111-1111-111111111111'
            ScopeResourceGroupName  = 'rg-fabric'
            ScopeCapacityName       = 'cap01'
            ScopeCapacityResourceId = $id
        }
        $map = New-JobScheduleParameterMap -Settings $s -IdentityClientId '22222222-2222-2222-2222-222222222222'
        $json = @{ properties = @{ schedule = @{ name = 's' }; runbook = @{ name = 'r' }; parameters = $map } } | ConvertTo-Json -Depth 10
        $document = [System.Text.Json.JsonDocument]::Parse($json)
        try {
            $parameters = $document.RootElement.GetProperty('properties').GetProperty('parameters')
            $count = 0
            foreach ($property in $parameters.EnumerateObject()) {
                $count++
                $property.Value.ValueKind.ToString() | Should -Be 'String' -Because "runbook parameter '$($property.Name)' must be sent as a string"
            }
            $count | Should -Be 8
            $parameters.GetProperty('DryRun').GetString() | Should -Be $(if ($Enforce) { 'false' } else { 'true' })
        }
        finally { $document.Dispose() }
    }

    It 'only uses runbook parameter names that the runbook declares' {
        $runbook = Get-Content -LiteralPath (Join-Path $PSScriptRoot '..' 'runbooks' 'Invoke-FabricCapacityAutoPause.ps1') -Raw
        $s = New-TestSettings @{
            ScopeSubscriptionIds    = '11111111-1111-1111-1111-111111111111'
            ScopeResourceGroupName  = 'rg-fabric'
            ScopeCapacityName       = 'cap01'
            ScopeCapacityResourceId = '/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-fabric/providers/Microsoft.Fabric/capacities/cap01'
        }
        foreach ($name in (New-JobScheduleParameterMap -Settings $s -IdentityClientId 'cid').Keys) {
            $runbook | Should -Match "\[string\]\s+\`$$name\b" -Because "the runbook must declare a [string] parameter named $name"
        }
    }

    It 'keeps an explicitly empty exclusion tag value so tag presence alone excludes a capacity' {
        $map = New-JobScheduleParameterMap -Settings (New-TestSettings @{ ExcludeTagValue = '' }) -IdentityClientId 'cid'
        $map.Contains('ExcludeTagValue') | Should -BeTrue
        $map['ExcludeTagValue'] | Should -Be ''
    }

    It 'omits the identity client ID when it is empty' {
        $map = New-JobScheduleParameterMap -Settings (New-TestSettings) -IdentityClientId ''
        $map.Contains('UserAssignedIdentityClientId') | Should -BeFalse
    }
}

Describe 'New-InfraParameterFileContent' {
    It 'serialises every infra parameter with the right JSON types' {
        $s = New-TestSettings @{
            AlertEmails                = @('ops@example.com')
            IncludeWritePermission     = $true
            AdditionalAssignableScopes = @('/subscriptions/11111111-1111-1111-1111-111111111111')
            Tags                       = @{ owner = 'team' }
        }
        $json = New-InfraParameterFileContent -Settings $s -ScheduleStartTime '2026-10-16T00:00:00+00:00' -BackstopStartTime '2026-10-16T01:00:00+00:00' | ConvertTo-Json -Depth 10
        $json | Should -Match '"alertEmails":\s*\{\s*"value":\s*\[\s*"ops@example.com"\s*\]'
        $json | Should -Match '"additionalAssignableScopes":\s*\{\s*"value":\s*\[\s*"/subscriptions/11111111-1111-1111-1111-111111111111"\s*\]'
        $p = ($json | ConvertFrom-Json).parameters
        @($p.PSObject.Properties.Name) | Should -Be @('location', 'resourceGroupName', 'namePrefix', 'timeZone', 'scheduleStartTime', 'backstopStartTime', 'alertEmails', 'includeWritePermission', 'assignRoleAtSubscription', 'customRoleName', 'additionalAssignableScopes', 'tags', 'azPackageVersion')
        $p.location.value | Should -Be 'eastus2'
        Get-JsonParameterString -Json $json -Name 'scheduleStartTime' | Should -Be '2026-10-16T00:00:00+00:00'
        Get-JsonParameterString -Json $json -Name 'backstopStartTime' | Should -Be '2026-10-16T01:00:00+00:00'
        $p.includeWritePermission.value | Should -BeTrue
        $p.assignRoleAtSubscription.value | Should -BeTrue
        $p.azPackageVersion.value | Should -Be '12.3.0'
        $p.tags.value.owner | Should -Be 'team'
    }

    It 'maps -SkipSubscriptionRoleAssignment to assignRoleAtSubscription = false (a JSON boolean)' {
        $json = New-InfraParameterFileContent -Settings (New-TestSettings @{ SkipSubscriptionRoleAssignment = $true }) -ScheduleStartTime '2026-10-16T00:00:00+00:00' | ConvertTo-Json -Depth 10
        $json | Should -Match '"assignRoleAtSubscription":\s*\{\s*"value":\s*false'
        ($json | ConvertFrom-Json).parameters.assignRoleAtSubscription.value | Should -BeOfType [bool]
    }

    It 'assigns the role at the subscription by default' {
        $json = New-InfraParameterFileContent -Settings (New-TestSettings) -ScheduleStartTime '2026-10-16T00:00:00+00:00' | ConvertTo-Json -Depth 10
        $json | Should -Match '"assignRoleAtSubscription":\s*\{\s*"value":\s*true'
    }

    It 'passes -AzPackageVersion to Bicep as the azPackageVersion string' {
        $json = New-InfraParameterFileContent -Settings (New-TestSettings @{ AzPackageVersion = '13.1.0' }) -ScheduleStartTime '2026-10-16T00:00:00+00:00' | ConvertTo-Json -Depth 10
        Get-JsonParameterString -Json $json -Name 'azPackageVersion' | Should -Be '13.1.0'
    }

    It 'only emits parameters that infra\main.bicep declares' {
        $declared = [regex]::Matches((Get-Content -LiteralPath (Join-Path $script:InfraPath 'main.bicep') -Raw), '(?m)^param\s+(\w+)\s') | ForEach-Object { $_.Groups[1].Value }
        $emitted = (New-InfraParameterFileContent -Settings (New-TestSettings) -ScheduleStartTime '2026-10-16T00:00:00+00:00').parameters.Keys
        foreach ($name in $emitted) { $declared | Should -Contain $name }
        foreach ($name in $declared) { @($emitted) | Should -Contain $name }
    }

    It 'serialises empty collections as an empty array and object, and a disabled backstop as an empty string' {
        $json = New-InfraParameterFileContent -Settings (New-TestSettings) -ScheduleStartTime '2026-10-16T00:00:00+00:00' | ConvertTo-Json -Depth 10
        $json | Should -Match '"alertEmails":\s*\{\s*"value":\s*\[\s*\]'
        $json | Should -Match '"additionalAssignableScopes":\s*\{\s*"value":\s*\[\s*\]'
        $json | Should -Match '"tags":\s*\{\s*"value":\s*\{\s*\}'
        $json | Should -Match '"backstopStartTime":\s*\{\s*"value":\s*""'
        $json | Should -Match '"includeWritePermission":\s*\{\s*"value":\s*false'
    }
}

Describe 'Get-AutomationUrl' {
    It 'builds the ARM URL with the pinned API version' {
        $t = [pscustomobject]@{ SubscriptionId = 'sub'; ResourceGroupName = 'rg'; AutomationAccountName = 'acct'; RunbookName = 'rb' }
        Get-AutomationUrl -Target $t -Path '/runbooks/rb/draft/content' |
            Should -Be 'https://management.azure.com/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Automation/automationAccounts/acct/runbooks/rb/draft/content?api-version=2024-10-23'
    }
}

Describe 'Get-DeploymentOutputs' {
    It 'reads all outputs' {
        $o = Get-DeploymentOutputs -Deployment (New-DeploymentJson)
        $o.ResourceGroupName | Should -Be 'rg-test'
        $o.AutomationAccountName | Should -Be 'aa-test'
        $o.RunbookName | Should -Be 'Invoke-FabricCapacityAutoPause'
        $o.IdentityClientId | Should -Be '22222222-2222-2222-2222-222222222222'
        $o.IdentityPrincipalId | Should -Be '33333333-3333-3333-3333-333333333333'
        $o.NightlyScheduleName | Should -Be 'autopause-nightly'
        $o.BackstopScheduleName | Should -Be 'autopause-backstop'
        $o.RoleDefinitionId | Should -Be '/subscriptions/11111111-1111-1111-1111-111111111111/providers/Microsoft.Authorization/roleDefinitions/44444444-4444-4444-4444-444444444444'
    }

    It 'treats the role definition ID as optional' {
        $d = New-DeploymentJson
        $d.properties.outputs.PSObject.Properties.Remove('roleDefinitionId')
        (Get-DeploymentOutputs -Deployment $d).RoleDefinitionId | Should -Be ''
    }

    It 'allows an empty backstop schedule name' {
        (Get-DeploymentOutputs -Deployment (New-DeploymentJson -BackstopScheduleName '')).BackstopScheduleName | Should -Be ''
    }

    It 'fails clearly when a required output is missing' {
        $d = New-DeploymentJson
        $d.properties.outputs.PSObject.Properties.Remove('identityClientId')
        { Get-DeploymentOutputs -Deployment $d } | Should -Throw "*output 'identityClientId'*"
    }

    It 'fails when the deployment has no outputs at all' {
        { Get-DeploymentOutputs -Deployment ([pscustomobject]@{ properties = [pscustomobject]@{} }) } | Should -Throw '*did not return the output*'
    }
}

Describe 'Invoke-WithRetry' {
    It 'returns the result without sleeping when the first attempt succeeds' {
        Invoke-WithRetry -Action { 'ok' } | Should -Be 'ok'
        Should -Invoke Start-Sleep -Times 0 -Exactly
    }

    It 'retries with doubling, capped delays until the action succeeds' {
        $state = @{ Calls = 0 }
        $result = Invoke-WithRetry -Description 'flaky call' -MaxAttempts 6 -InitialDelaySeconds 5 -MaxDelaySeconds 30 -Action {
            $state.Calls++
            if ($state.Calls -lt 6) { throw 'not yet' }
            'done'
        }
        $result | Should -Be 'done'
        $state.Calls | Should -Be 6
        Should -Invoke Start-Sleep -Times 5 -Exactly
        Should -Invoke Start-Sleep -Times 1 -Exactly -ParameterFilter { $Seconds -eq 5 }
        Should -Invoke Start-Sleep -Times 1 -Exactly -ParameterFilter { $Seconds -eq 10 }
        Should -Invoke Start-Sleep -Times 1 -Exactly -ParameterFilter { $Seconds -eq 20 }
        Should -Invoke Start-Sleep -Times 2 -Exactly -ParameterFilter { $Seconds -eq 30 }
    }

    It 'throws with the description after the last attempt' {
        $state = @{ Calls = 0 }
        { Invoke-WithRetry -Description 'flaky call' -MaxAttempts 3 -Action { $state.Calls++; throw 'still broken' } } |
            Should -Throw '*flaky call failed after 3 attempt(s)*still broken*'
        $state.Calls | Should -Be 3
        Should -Invoke Start-Sleep -Times 2 -Exactly
    }
}

Describe 'Invoke-Az' {
    BeforeEach { $script:AzArgs = $null }

    It 'returns parsed JSON and asks for json output without warnings' {
        function az { $script:AzArgs = $args; $global:LASTEXITCODE = 0; '{"name":"x","items":[1,2]}' }
        $r = Invoke-Az -Arguments @('account', 'show')
        $r.name | Should -Be 'x'
        @($r.items).Count | Should -Be 2
        $script:AzArgs | Should -Contain '--only-show-errors'
        $script:AzArgs | Should -Contain 'json'
    }

    It 'returns trimmed text with -AsText and does not request json' {
        function az { $script:AzArgs = $args; $global:LASTEXITCODE = 0; "Bicep CLI version 1.2.3`n" }
        Invoke-Az -Arguments @('bicep', 'version') -AsText | Should -Be 'Bicep CLI version 1.2.3'
        $script:AzArgs | Should -Not -Contain '--output'
    }

    It 'ignores stderr warnings when the command succeeds' {
        function az { $global:LASTEXITCODE = 0; Write-Error 'WARNING: a newer version is available'; '{"ok":true}' }
        (Invoke-Az -Arguments @('account', 'show')).ok | Should -BeTrue
    }

    It 'returns null for empty output' {
        function az { $global:LASTEXITCODE = 0 }
        Invoke-Az -Arguments @('account', 'set', '--subscription', 'x') | Should -BeNullOrEmpty
    }

    It 'throws with the exit code and stderr on failure' {
        function az { $global:LASTEXITCODE = 3; Write-Error 'ERROR: the resource was not found' }
        { Invoke-Az -Arguments @('deployment', 'sub', 'create') } | Should -Throw '*az deployment sub create failed (exit code 3)*the resource was not found*'
    }

    It 'throws when the output is not JSON' {
        function az { $global:LASTEXITCODE = 0; 'definitely not json' }
        { Invoke-Az -Arguments @('account', 'show') } | Should -Throw '*not valid JSON*'
    }
}

Describe 'Invoke-AzRest' {
    BeforeEach {
        $script:RestArgs = $null
        $script:BodyPath = $null
        $script:BodyText = $null
        Mock Invoke-Az {
            $script:RestArgs = $Arguments
            $i = [array]::IndexOf($Arguments, '--body')
            if ($i -ge 0) {
                $script:BodyPath = $Arguments[$i + 1].Substring(1)
                $script:BodyText = Get-Content -LiteralPath $script:BodyPath -Raw
            }
            [pscustomobject]@{ ok = $true }
        }
    }

    It 'sends a GET without a body' {
        $null = Invoke-AzRest -Method get -Uri 'https://example.invalid/x?api-version=1'
        ($script:RestArgs -join ' ') | Should -Be 'rest --method get --url https://example.invalid/x?api-version=1'
    }

    It 'sends JSON bodies through a temp file that is removed afterwards' {
        $null = Invoke-AzRest -Method put -Uri 'https://example.invalid/x' -Body @{ properties = @{ a = 1 } }
        $script:RestArgs | Should -Contain 'Content-Type=application/json'
        $script:BodyPath | Should -Not -BeNullOrEmpty
        ($script:BodyText | ConvertFrom-Json).properties.a | Should -Be 1
        Test-Path -LiteralPath $script:BodyPath | Should -BeFalse
    }

    It 'removes the temp file even when az fails' {
        Mock Invoke-Az { $i = [array]::IndexOf($Arguments, '--body'); $script:BodyPath = $Arguments[$i + 1].Substring(1); throw 'az failed' }
        { Invoke-AzRest -Method put -Uri 'https://example.invalid/x' -Body @{ a = 1 } } | Should -Throw '*az failed*'
        Test-Path -LiteralPath $script:BodyPath | Should -BeFalse
    }

    It 'uploads a caller-supplied file as text/plain and never deletes it' {
        $file = Join-Path $TestDrive 'runbook.ps1'
        Set-Content -LiteralPath $file -Value 'Write-Output hi'
        $null = Invoke-AzRest -Method put -Uri 'https://example.invalid/x' -BodyFile $file -ContentType 'text/plain'
        $script:RestArgs | Should -Contain 'Content-Type=text/plain'
        $script:RestArgs | Should -Contain "@$file"
        Test-Path -LiteralPath $file | Should -BeTrue
    }

    It 'refuses mutating methods while -WhatIf is in effect, but still allows reads' {
        { & { $WhatIfPreference = $true; Invoke-AzRest -Method put -Uri 'https://example.invalid/x' -Body @{ a = 1 } } } | Should -Throw '*-WhatIf*'
        { & { $WhatIfPreference = $true; Invoke-AzRest -Method delete -Uri 'https://example.invalid/x' } } | Should -Throw '*-WhatIf*'
        { & { $WhatIfPreference = $true; Invoke-AzRest -Method get -Uri 'https://example.invalid/x' } } | Should -Not -Throw
    }
}

Describe 'Wait-RunbookPublished and Publish-Runbook' {
    BeforeAll {
        $script:Target = [pscustomobject]@{ SubscriptionId = 'sub'; ResourceGroupName = 'rg'; AutomationAccountName = 'acct'; RunbookName = 'rb' }
    }

    BeforeEach {
        $script:RestCalls = [System.Collections.Generic.List[object]]::new()
        $script:States = [System.Collections.Generic.Queue[string]]::new()
        $script:PublishFailures = 0
        Mock Invoke-AzRest {
            $script:RestCalls.Add([pscustomobject]@{ Method = $Method; Uri = $Uri; BodyFile = $BodyFile; ContentType = $ContentType; MessageCount = $script:Messages.Count })
            if ($Method -eq 'post' -and $script:PublishFailures -gt 0) {
                $script:PublishFailures--
                throw 'Runbook is not in a state that can be published yet.'
            }
            if ($Method -eq 'get') {
                $state = if ($script:States.Count -gt 0) { $script:States.Dequeue() } else { 'Published' }
                return [pscustomobject]@{ properties = [pscustomobject]@{ state = $state } }
            }
            return $null
        }
    }

    It 'polls until the runbook is Published' {
        'Edit', 'Edit', 'Published' | ForEach-Object { $script:States.Enqueue($_) }
        Wait-RunbookPublished -Target $script:Target -TimeoutSeconds 60 -PollSeconds 5 | Should -Be 'Published'
        @($script:RestCalls | Where-Object Method -eq 'get').Count | Should -Be 3
        Should -Invoke Start-Sleep -Times 2 -Exactly
    }

    It 'times out when the runbook never reaches Published' {
        1..20 | ForEach-Object { $script:States.Enqueue('Edit') }
        { Wait-RunbookPublished -Target $script:Target -TimeoutSeconds 10 -PollSeconds 5 } | Should -Throw "*did not reach state 'Published'*last state: Edit*"
        @($script:RestCalls | Where-Object Method -eq 'get').Count | Should -Be 3
    }

    It 'uploads the draft as text/plain, publishes, then waits for Published' {
        $file = Join-Path $TestDrive 'rb.ps1'
        Set-Content -LiteralPath $file -Value 'x'
        Publish-Runbook -Target $script:Target -RunbookPath $file | Should -BeTrue

        $script:RestCalls.Count | Should -Be 3
        $script:RestCalls[0].Method | Should -Be 'put'
        $script:RestCalls[0].Uri | Should -Be 'https://management.azure.com/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Automation/automationAccounts/acct/runbooks/rb/draft/content?api-version=2024-10-23'
        $script:RestCalls[0].BodyFile | Should -Be $file
        $script:RestCalls[0].ContentType | Should -Be 'text/plain'
        $script:RestCalls[1].Method | Should -Be 'post'
        $script:RestCalls[1].Uri | Should -Be 'https://management.azure.com/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Automation/automationAccounts/acct/runbooks/rb/publish?api-version=2024-10-23'
        $script:RestCalls[2].Method | Should -Be 'get'
    }

    It 'prints the SHA-256 of the uploaded runbook file before the upload happens' {
        $file = Join-Path $TestDrive 'rb-hash.ps1'
        Set-Content -LiteralPath $file -Value 'Write-Output ''hash me'''
        $expected = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
        $expected | Should -Match '\A[0-9A-F]{64}\z'

        $null = Publish-Runbook -Target $script:Target -RunbookPath $file

        $hashMessages = @($script:Messages | Where-Object { $_ -like '*SHA-256*' })
        $hashMessages.Count | Should -Be 1
        $hashMessages[0] | Should -BeLike "*SHA-256: $expected*"
        $script:Messages.IndexOf($hashMessages[0]) | Should -BeLessThan $script:RestCalls[0].MessageCount
        $script:RestCalls[0].Method | Should -Be 'put'
    }

    It 'prints a different SHA-256 when the runbook content differs' {
        $first = Join-Path $TestDrive 'rb-a.ps1'
        $second = Join-Path $TestDrive 'rb-b.ps1'
        Set-Content -LiteralPath $first -Value 'a'
        Set-Content -LiteralPath $second -Value 'b'
        $null = Publish-Runbook -Target $script:Target -RunbookPath $first
        $null = Publish-Runbook -Target $script:Target -RunbookPath $second
        $hashes = @($script:Messages | Where-Object { $_ -like '*SHA-256:*' })
        $hashes.Count | Should -Be 2
        $hashes[0] | Should -Not -Be $hashes[1]
    }

    It 'retries the publish call while the draft upload is still being processed' {
        $script:PublishFailures = 2
        $file = Join-Path $TestDrive 'rb.ps1'
        Set-Content -LiteralPath $file -Value 'x'
        Publish-Runbook -Target $script:Target -RunbookPath $file | Should -BeTrue
        @($script:RestCalls | Where-Object Method -eq 'post').Count | Should -Be 3
        Should -Invoke Start-Sleep -Times 1 -Exactly -ParameterFilter { $Seconds -eq 5 }
        Should -Invoke Start-Sleep -Times 1 -Exactly -ParameterFilter { $Seconds -eq 10 }
    }

    It 'gives up after six failed publish attempts' {
        $script:PublishFailures = 99
        $file = Join-Path $TestDrive 'rb.ps1'
        Set-Content -LiteralPath $file -Value 'x'
        { Publish-Runbook -Target $script:Target -RunbookPath $file } | Should -Throw '*Publishing the runbook failed after 6 attempt(s)*'
        @($script:RestCalls | Where-Object Method -eq 'post').Count | Should -Be 6
        @($script:RestCalls | Where-Object Method -eq 'get').Count | Should -Be 0
    }

    It 'makes no calls and prints no hash with -WhatIf' {
        Publish-Runbook -Target $script:Target -RunbookPath (Join-Path $TestDrive 'rb.ps1') -WhatIf | Should -BeFalse
        $script:RestCalls.Count | Should -Be 0
        @($script:Messages | Where-Object { $_ -like '*SHA-256*' }).Count | Should -Be 0
    }
}

Describe 'Set-JobScheduleLinks' {
    BeforeAll {
        $script:Target = [pscustomobject]@{ SubscriptionId = 'sub'; ResourceGroupName = 'rg'; AutomationAccountName = 'acct'; RunbookName = 'rb' }
        $script:Map = [ordered]@{ ExcludeTagName = 'autopause'; ExcludeTagValue = 'skip'; UserAssignedIdentityClientId = 'cid'; DryRun = 'true' }
    }

    BeforeEach {
        $script:RestCalls = [System.Collections.Generic.List[object]]::new()
        $script:ListPages = [System.Collections.Generic.Queue[object]]::new()
        Mock Invoke-AzRest {
            $script:RestCalls.Add([pscustomobject]@{ Method = $Method; Uri = $Uri; Body = $Body })
            if ($Method -eq 'get') { return $script:ListPages.Dequeue() }
            return $null
        }
    }

    It 'deletes only our existing links for this runbook, then recreates them under fresh IDs' {
        $script:ListPages.Enqueue(('{"value":[
            {"name":"link-a","properties":{"jobScheduleId":"id-a","runbook":{"name":"rb"},"schedule":{"name":"autopause-nightly"}}},
            {"name":"link-b","properties":{"jobScheduleId":"id-b","runbook":{"name":"other-runbook"},"schedule":{"name":"autopause-nightly"}}},
            {"name":"link-c","properties":{"jobScheduleId":"id-c","runbook":{"name":"rb"},"schedule":{"name":"custom-schedule"}}},
            {"name":"link-d","properties":{"runbook":{"name":"RB"},"schedule":{"name":"AUTOPAUSE-BACKSTOP"}}}
        ]}' | ConvertFrom-Json))

        $linked = Set-JobScheduleLinks -Target $script:Target -ScheduleNames @('autopause-nightly', 'autopause-backstop') -Parameters $script:Map
        $linked | Should -Be @('autopause-nightly', 'autopause-backstop')

        $deletes = @($script:RestCalls | Where-Object Method -eq 'delete')
        $deletes.Count | Should -Be 2
        $deletes[0].Uri | Should -BeLike '*/automationAccounts/acct/jobSchedules/id-a?api-version=2024-10-23'
        $deletes[1].Uri | Should -BeLike '*/automationAccounts/acct/jobSchedules/link-d?api-version=2024-10-23'

        $puts = @($script:RestCalls | Where-Object Method -eq 'put')
        $puts.Count | Should -Be 2
        $ids = @()
        foreach ($put in $puts) {
            $put.Uri | Should -Match '/jobSchedules/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\?api-version=2024-10-23$'
            $ids += ($put.Uri -replace '^.*/jobSchedules/', '' -replace '\?.*$', '')
            $put.Body.properties.runbook.name | Should -Be 'rb'
            $put.Body.properties.parameters['DryRun'] | Should -Be 'true'
            $put.Body.properties.parameters['UserAssignedIdentityClientId'] | Should -Be 'cid'
        }
        ($puts.Body.properties.schedule.name | Sort-Object) | Should -Be @('autopause-backstop', 'autopause-nightly')

        # Never reuse a deleted link's ID (Automation reserves it), and never reuse one across links.
        ($ids | Select-Object -Unique).Count | Should -Be 2
        $ids | Should -Not -Contain 'id-a'

        # Deletes happen before any create.
        $script:RestCalls.FindIndex({ param($c) $c.Method -eq 'put' }) | Should -BeGreaterThan $script:RestCalls.FindLastIndex({ param($c) $c.Method -eq 'delete' })
    }

    It 'uses different link IDs on every run' {
        $script:ListPages.Enqueue(('{"value":[]}' | ConvertFrom-Json))
        $null = Set-JobScheduleLinks -Target $script:Target -ScheduleNames @('autopause-nightly') -Parameters $script:Map
        $first = (@($script:RestCalls | Where-Object Method -eq 'put')[0].Uri)
        $script:RestCalls.Clear()
        $script:ListPages.Enqueue(('{"value":[]}' | ConvertFrom-Json))
        $null = Set-JobScheduleLinks -Target $script:Target -ScheduleNames @('autopause-nightly') -Parameters $script:Map
        $second = (@($script:RestCalls | Where-Object Method -eq 'put')[0].Uri)
        $second | Should -Not -Be $first
    }

    It 'follows paging when listing existing links' {
        $script:ListPages.Enqueue(('{"value":[],"nextLink":"https://management.azure.com/next-page"}' | ConvertFrom-Json))
        $script:ListPages.Enqueue(('{"value":[{"name":"link-z","properties":{"jobScheduleId":"id-z","runbook":{"name":"rb"},"schedule":{"name":"autopause-nightly"}}}]}' | ConvertFrom-Json))

        $null = Set-JobScheduleLinks -Target $script:Target -ScheduleNames @('autopause-nightly') -Parameters $script:Map

        @($script:RestCalls | Where-Object Method -eq 'get').Uri | Should -Contain 'https://management.azure.com/next-page'
        @($script:RestCalls | Where-Object Method -eq 'delete').Count | Should -Be 1
    }

    It 'creates links without deleting anything on a first deployment' {
        $script:ListPages.Enqueue(('{"value":[]}' | ConvertFrom-Json))
        $null = Set-JobScheduleLinks -Target $script:Target -ScheduleNames @('autopause-nightly') -Parameters $script:Map
        @($script:RestCalls | Where-Object Method -eq 'delete').Count | Should -Be 0
        @($script:RestCalls | Where-Object Method -eq 'put').Count | Should -Be 1
    }

    It 'makes no mutating calls with -WhatIf' {
        $script:ListPages.Enqueue(('{"value":[{"name":"link-a","properties":{"jobScheduleId":"id-a","runbook":{"name":"rb"},"schedule":{"name":"autopause-nightly"}}}]}' | ConvertFrom-Json))
        $null = Set-JobScheduleLinks -Target $script:Target -ScheduleNames @('autopause-nightly') -Parameters $script:Map -WhatIf
        @($script:RestCalls | Where-Object Method -ne 'get').Count | Should -Be 0
    }
}

Describe 'Assert-Preflight' {
    BeforeEach {
        New-StubRepo -Root $TestDrive
        $script:AzCalls = [System.Collections.Generic.List[string]]::new()
        $script:AzFail = @{}
        Mock Test-AzCliInstalled { $true }
        Mock Invoke-Az {
            $command = $Arguments -join ' '
            $script:AzCalls.Add($command)
            foreach ($rule in $script:AzFail.Keys) { if ($command -like $rule) { throw $script:AzFail[$rule] } }
            if ($command -eq 'bicep version') { return 'Bicep CLI version 0.0.0' }
            return [pscustomobject]@{ ok = $true }
        }
    }

    It 'passes and sets the active subscription when everything is available' {
        { Assert-Preflight -Settings (New-TestSettings) } | Should -Not -Throw
        $script:AzCalls | Should -Contain 'bicep version'
        $script:AzCalls | Should -Contain 'account show'
        $script:AzCalls | Should -Contain 'account show --subscription 11111111-1111-1111-1111-111111111111'
        $script:AzCalls | Should -Contain 'account set --subscription 11111111-1111-1111-1111-111111111111'
    }

    It 'does not change the Azure CLI context with -WhatIf' {
        Assert-Preflight -Settings (New-TestSettings) -WhatIf
        @($script:AzCalls | Where-Object { $_ -like 'account set*' }).Count | Should -Be 0
        $script:AzCalls | Should -Contain 'account show --subscription 11111111-1111-1111-1111-111111111111'
    }

    It 'stops when the Azure CLI is missing' {
        Mock Test-AzCliInstalled { $false }
        { Assert-Preflight -Settings (New-TestSettings) } | Should -Throw '*Azure CLI*was not found*'
    }

    It 'stops with install guidance when Bicep is unavailable' {
        $script:AzFail['bicep *'] = 'Bicep CLI not found'
        { Assert-Preflight -Settings (New-TestSettings) } | Should -Throw "*az bicep install*"
    }

    It 'tells the user to run az login when not signed in' {
        $script:AzFail['account show'] = 'Please run az login'
        { Assert-Preflight -Settings (New-TestSettings) } | Should -Throw "*az login*"
        @($script:AzCalls | Where-Object { $_ -like 'account set*' }).Count | Should -Be 0
    }

    It 'stops when the subscription is not available to the account' {
        $script:AzFail['account show --subscription *'] = 'Subscription not found'
        { Assert-Preflight -Settings (New-TestSettings) } | Should -Throw "*Subscription '11111111-1111-1111-1111-111111111111' is not available*"
    }

    It 'stops on an unknown time zone' {
        { Assert-Preflight -Settings (New-TestSettings @{ TimeZone = 'Not/AZone' }) } | Should -Throw '*Invalid schedule*'
    }

    It 'stops when the Bicep template is missing' {
        Remove-Item -LiteralPath (Join-Path $TestDrive 'infra' 'main.bicep')
        { Assert-Preflight -Settings (New-TestSettings) } | Should -Throw '*Required file not found*main.bicep*'
    }

    It 'does not warn about the write permission: the default role (read + suspend) is enough' {
        Assert-Preflight -Settings (New-TestSettings @{ EnableEnforcement = $true })
        @($script:Messages | Where-Object { $_ -like 'WARNING:*IncludeWritePermission*' }).Count | Should -Be 0
    }

    It 'warns loudly that nothing can be paused when the subscription role assignment is skipped' {
        Assert-Preflight -Settings (New-TestSettings @{ SkipSubscriptionRoleAssignment = $true })
        @($script:Messages | Where-Object { $_ -like 'WARNING:*SkipSubscriptionRoleAssignment*NOT assigned*No capacity can be paused*' }).Count | Should -Be 1
    }

    It 'does not warn about role assignment by default' {
        Assert-Preflight -Settings (New-TestSettings)
        @($script:Messages | Where-Object { $_ -like 'WARNING:*SkipSubscriptionRoleAssignment*' }).Count | Should -Be 0
    }
}

Describe 'Get-RoleAssignmentCommands' {
    BeforeAll {
        $script:Commands = Get-RoleAssignmentCommands -PrincipalId '33333333-3333-3333-3333-333333333333' -RoleName 'Fabric Capacity AutoPause Operator' -SubscriptionId '11111111-1111-1111-1111-111111111111'
    }

    It 'builds a ready-to-run resource group assignment for the service principal' {
        $script:Commands.AssignResourceGroup | Should -Be 'az role assignment create --assignee-object-id 33333333-3333-3333-3333-333333333333 --assignee-principal-type ServicePrincipal --role "Fabric Capacity AutoPause Operator" --scope /subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/<resource-group-name>'
    }

    It 'builds a single-capacity assignment' {
        $script:Commands.AssignCapacity | Should -Be 'az role assignment create --assignee-object-id 33333333-3333-3333-3333-333333333333 --assignee-principal-type ServicePrincipal --role "Fabric Capacity AutoPause Operator" --scope /subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/<resource-group-name>/providers/Microsoft.Fabric/capacities/<capacity-name>'
    }

    It 'builds the verification command for the identity' {
        $script:Commands.Verify | Should -Be 'az role assignment list --assignee 33333333-3333-3333-3333-333333333333 --all -o table'
    }

    It 'quotes the role name so names with spaces survive copy and paste' {
        (Get-RoleAssignmentCommands -PrincipalId 'p' -RoleName 'My Custom Role' -SubscriptionId 's').AssignCapacity | Should -BeLike '*--role "My Custom Role" --scope *'
    }
}

Describe 'Invoke-Deployment' {
    BeforeEach {
        New-StubRepo -Root $TestDrive
        $script:Now = [datetime]::new(2026, 10, 15, 20, 0, 0, [DateTimeKind]::Utc)
        $script:AzCalls = [System.Collections.Generic.List[string]]::new()
        $script:RestCalls = [System.Collections.Generic.List[object]]::new()
        $script:ParamFilePath = $null
        $script:ParamFileText = $null
        $script:DeploymentResult = New-DeploymentJson
        $script:DeployFails = $false

        Mock Test-AzCliInstalled { $true }
        Mock Invoke-Az {
            $command = $Arguments -join ' '
            $script:AzCalls.Add($command)
            if ($command -like 'deployment sub create*') {
                $i = [array]::IndexOf($Arguments, '--parameters')
                $script:ParamFilePath = $Arguments[$i + 1].Substring(1)
                $script:ParamFileText = Get-Content -LiteralPath $script:ParamFilePath -Raw
                if ($script:DeployFails) { throw 'InvalidTemplateDeployment' }
                return $script:DeploymentResult
            }
            if ($command -eq 'bicep version') { return 'Bicep CLI version 0.0.0' }
            return [pscustomobject]@{ ok = $true }
        }
        Mock Invoke-AzRest {
            $script:RestCalls.Add([pscustomobject]@{ Method = $Method; Uri = $Uri; Body = $Body; BodyFile = $BodyFile; ContentType = $ContentType })
            if ($Method -eq 'get' -and $Uri -like '*/jobSchedules?*') {
                return ('{"value":[{"name":"old-link","properties":{"jobScheduleId":"old-id","runbook":{"name":"Invoke-FabricCapacityAutoPause"},"schedule":{"name":"autopause-nightly"}}}]}' | ConvertFrom-Json)
            }
            if ($Method -eq 'get') { return [pscustomobject]@{ properties = [pscustomobject]@{ state = 'Published' } } }
            return $null
        }
    }

    It 'deploys, publishes the runbook and links both schedules (dry run by default)' {
        $r = Invoke-Deployment -Settings (New-TestSettings @{ TimeZone = 'UTC'; ScheduleTime = '00:00'; BackstopOffsetMinutes = 60 }) -NowUtc $script:Now

        $r.Deployed | Should -BeTrue
        $r.DryRun | Should -BeTrue

        $deployCall = $script:AzCalls | Where-Object { $_ -like 'deployment sub create*' }
        $deployCall | Should -BeLike "deployment sub create --name deploy-fabricautopause --location eastus2 --template-file $(Join-Path $TestDrive 'infra' 'main.bicep') --parameters @*"

        Get-JsonParameterString -Json $script:ParamFileText -Name 'scheduleStartTime' | Should -Be '2026-10-16T00:00:00+00:00'
        Get-JsonParameterString -Json $script:ParamFileText -Name 'backstopStartTime' | Should -Be '2026-10-16T01:00:00+00:00'
        Get-JsonParameterString -Json $script:ParamFileText -Name 'resourceGroupName' | Should -Be 'rg-test'
        Test-Path -LiteralPath $script:ParamFilePath | Should -BeFalse

        ($script:RestCalls | ForEach-Object { $_.Method }) | Should -Be @('put', 'post', 'get', 'get', 'delete', 'put', 'put')
        $script:RestCalls[0].Uri | Should -BeLike '*/automationAccounts/aa-test/runbooks/Invoke-FabricCapacityAutoPause/draft/content?api-version=2024-10-23'
        $script:RestCalls[0].BodyFile | Should -Be (Join-Path $TestDrive 'runbooks' 'Invoke-FabricCapacityAutoPause.ps1')
        $script:RestCalls[4].Uri | Should -BeLike '*/jobSchedules/old-id?api-version=2024-10-23'

        $puts = @($script:RestCalls | Where-Object Method -eq 'put' | Select-Object -Skip 1)
        $puts.Count | Should -Be 2
        foreach ($put in $puts) {
            $put.Body.properties.parameters['DryRun'] | Should -Be 'true'
            $put.Body.properties.parameters['UserAssignedIdentityClientId'] | Should -Be '22222222-2222-2222-2222-222222222222'
            $put.Body.properties.runbook.name | Should -Be 'Invoke-FabricCapacityAutoPause'
        }
        @($puts | ForEach-Object { $_.Body.properties.schedule.name }) | Should -Be @('autopause-nightly', 'autopause-backstop')
    }

    It 'prints a loud dry-run warning in the summary' {
        $null = Invoke-Deployment -Settings (New-TestSettings) -NowUtc $script:Now
        $script:Messages | Should -Contain 'Mode: DRY RUN - nothing will be paused until you rerun with -EnableEnforcement'
        ($script:Messages -join "`n") | Should -Match 'Start-AzAutomationRunbook'
        ($script:Messages -join "`n") | Should -Match 'Jobs'
        ($script:Messages -join "`n") | Should -Match 'principal 33333333-3333-3333-3333-333333333333, client 22222222-2222-2222-2222-222222222222'
    }

    It 'assigns the role at the subscription by default and prints a verification command instead of manual assignment steps' {
        $r = Invoke-Deployment -Settings (New-TestSettings) -NowUtc $script:Now
        $text = $script:Messages -join "`n"
        ($script:ParamFileText | ConvertFrom-Json).parameters.assignRoleAtSubscription.value | Should -BeTrue
        $r.RoleAssignedAtSubscription | Should -BeTrue
        $text | Should -Match 'Role assignment    : whole subscription \(/subscriptions/11111111-1111-1111-1111-111111111111\)'
        $script:Messages | Should -Contain 'Verify the role assignment of the managed identity:'
        $script:Messages | Should -Contain '  az role assignment list --assignee 33333333-3333-3333-3333-333333333333 --all -o table'
        $text | Should -Not -Match 'az role assignment create'
        $text | Should -Not -Match 'NOTHING CAN BE PAUSED'
        $text | Should -Match 'Custom role        : Fabric Capacity AutoPause Operator \(/subscriptions/11111111-1111-1111-1111-111111111111/providers/Microsoft.Authorization/roleDefinitions/44444444-4444-4444-4444-444444444444\)'
    }

    It 'with -SkipSubscriptionRoleAssignment sends assignRoleAtSubscription = false and prints ready-to-run assignment commands' {
        $r = Invoke-Deployment -Settings (New-TestSettings @{ SkipSubscriptionRoleAssignment = $true }) -NowUtc $script:Now
        $text = $script:Messages -join "`n"
        ($script:ParamFileText | ConvertFrom-Json).parameters.assignRoleAtSubscription.value | Should -BeFalse
        $r.RoleAssignedAtSubscription | Should -BeFalse
        $text | Should -Match 'Role assignment    : NONE \(-SkipSubscriptionRoleAssignment\)'
        $script:Messages | Should -Contain '  az role assignment create --assignee-object-id 33333333-3333-3333-3333-333333333333 --assignee-principal-type ServicePrincipal --role "Fabric Capacity AutoPause Operator" --scope /subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/<resource-group-name>'
        $script:Messages | Should -Contain '  az role assignment create --assignee-object-id 33333333-3333-3333-3333-333333333333 --assignee-principal-type ServicePrincipal --role "Fabric Capacity AutoPause Operator" --scope /subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/<resource-group-name>/providers/Microsoft.Fabric/capacities/<capacity-name>'
        $text | Should -Match 'NOTHING CAN BE PAUSED'
        $text | Should -Match 'until you assign the role'
        $text | Should -Not -Match 'az role assignment list'
        $text | Should -Not -Match 'Verify the role assignment'
    }

    It 'prints the loud skipped-assignment note in red' {
        $null = Invoke-Deployment -Settings (New-TestSettings @{ SkipSubscriptionRoleAssignment = $true }) -NowUtc $script:Now
        Should -Invoke Write-Message -ParameterFilter { $Text -like 'IMPORTANT:*NOTHING CAN BE PAUSED*' -and $Color -eq [ConsoleColor]::Red } -Times 1 -Exactly
    }

    It 'still reports the enforcement mode when the subscription role assignment is skipped' {
        $null = Invoke-Deployment -Settings (New-TestSettings @{ SkipSubscriptionRoleAssignment = $true; EnableEnforcement = $true }) -NowUtc $script:Now
        $text = $script:Messages -join "`n"
        $text | Should -Match 'ENFORCING'
        $text | Should -Match 'NOTHING CAN BE PAUSED'
    }

    It 'passes -AzPackageVersion to the Bicep deployment' {
        $null = Invoke-Deployment -Settings (New-TestSettings @{ AzPackageVersion = '13.1.0' }) -NowUtc $script:Now
        Get-JsonParameterString -Json $script:ParamFileText -Name 'azPackageVersion' | Should -Be '13.1.0'
    }

    It 'sends the default Az package version when none is chosen' {
        $null = Invoke-Deployment -Settings (New-TestSettings) -NowUtc $script:Now
        Get-JsonParameterString -Json $script:ParamFileText -Name 'azPackageVersion' | Should -Be '12.3.0'
    }

    It 'prints the SHA-256 of the runbook file in the upload step' {
        $null = Invoke-Deployment -Settings (New-TestSettings) -NowUtc $script:Now
        $expected = (Get-FileHash -LiteralPath (Join-Path $TestDrive 'runbooks' 'Invoke-FabricCapacityAutoPause.ps1') -Algorithm SHA256).Hash
        $step4 = $script:Messages.FindIndex({ param($m) $m -like 'Step 4/6:*' })
        $step5 = $script:Messages.FindIndex({ param($m) $m -like 'Step 5/6:*' })
        $hashIndex = $script:Messages.FindIndex({ param($m) $m -like "*SHA-256: $expected*" })
        $hashIndex | Should -BeGreaterThan $step4
        $hashIndex | Should -BeLessThan $step5
    }

    It 'says in WhatIf mode whether the role would be assigned' {
        $null = Invoke-Deployment -Settings (New-TestSettings) -NowUtc $script:Now -WhatIf
        ($script:Messages -join "`n") | Should -Match "would be assigned at the whole subscription"
        $script:Messages.Clear()
        $null = Invoke-Deployment -Settings (New-TestSettings @{ SkipSubscriptionRoleAssignment = $true }) -NowUtc $script:Now -WhatIf
        ($script:Messages -join "`n") | Should -Match 'would be created but NOT assigned'
    }

    It 'links the schedules with DryRun false when enforcement is enabled' {
        $r = Invoke-Deployment -Settings (New-TestSettings @{ EnableEnforcement = $true; IncludeWritePermission = $true }) -NowUtc $script:Now
        $r.DryRun | Should -BeFalse
        $puts = @($script:RestCalls | Where-Object Method -eq 'put' | Select-Object -Skip 1)
        foreach ($put in $puts) { $put.Body.properties.parameters['DryRun'] | Should -Be 'false' }
        ($script:ParamFileText | ConvertFrom-Json).parameters.includeWritePermission.value | Should -BeTrue
        ($script:Messages -join "`n") | Should -Not -Match 'DRY RUN - nothing will be paused'
        ($script:Messages -join "`n") | Should -Match 'ENFORCING'
    }

    It 'links only the nightly schedule when the backstop is disabled' {
        $script:DeploymentResult = New-DeploymentJson -BackstopScheduleName ''
        $r = Invoke-Deployment -Settings (New-TestSettings @{ BackstopOffsetMinutes = 0 }) -NowUtc $script:Now
        ($script:ParamFileText | ConvertFrom-Json).parameters.backstopStartTime.value | Should -Be ''
        @($script:RestCalls | Where-Object Method -eq 'put').Count | Should -Be 2
        $r.BackstopStart | Should -BeNullOrEmpty
        ($script:Messages -join "`n") | Should -Match 'Backstop schedule  : disabled'
    }

    It 'passes the scope values to the linked schedules' {
        $s = New-TestSettings @{ ScopeResourceGroupName = 'rg-fabric'; ScopeSubscriptionIds = '44444444-4444-4444-4444-444444444444' }
        $null = Invoke-Deployment -Settings $s -NowUtc $script:Now
        $put = @($script:RestCalls | Where-Object Method -eq 'put' | Select-Object -Skip 1)[0]
        $put.Body.properties.parameters['ResourceGroupName'] | Should -Be 'rg-fabric'
        $put.Body.properties.parameters['SubscriptionIds'] | Should -Be '44444444-4444-4444-4444-444444444444'
        $put.Body.properties.parameters.Contains('CapacityName') | Should -BeFalse
    }

    It 'prints a banner for each of the six steps' {
        $null = Invoke-Deployment -Settings (New-TestSettings) -NowUtc $script:Now
        $banners = @($script:Messages | Where-Object { $_ -match '^Step \d/6: ' })
        $banners.Count | Should -Be 6
        $banners[0] | Should -Match 'Preflight'
        $banners[5] | Should -Match 'Summary'
    }

    It 'makes no mutating calls with -WhatIf' {
        $r = Invoke-Deployment -Settings (New-TestSettings) -NowUtc $script:Now -WhatIf

        $r.Deployed | Should -BeFalse
        $script:RestCalls.Count | Should -Be 0
        Should -Invoke Invoke-AzRest -Times 0 -Exactly
        @($script:AzCalls | Where-Object { $_ -like 'deployment*' -or $_ -like 'account set*' }).Count | Should -Be 0
        $script:ParamFilePath | Should -BeNullOrEmpty
        ($script:Messages -join "`n") | Should -Match 'WhatIf'
    }

    It 'does not publish or link when the deployment fails, and still removes the temp parameters file' {
        $script:DeployFails = $true
        { Invoke-Deployment -Settings (New-TestSettings) -NowUtc $script:Now } | Should -Throw '*InvalidTemplateDeployment*'
        $script:RestCalls.Count | Should -Be 0
        Test-Path -LiteralPath $script:ParamFilePath | Should -BeFalse
    }

    It 'fails clearly when the deployment outputs are incomplete' {
        $script:DeploymentResult.properties.outputs.PSObject.Properties.Remove('runbookName')
        { Invoke-Deployment -Settings (New-TestSettings) -NowUtc $script:Now } | Should -Throw "*output 'runbookName'*"
        $script:RestCalls.Count | Should -Be 0
    }
}

Describe 'infra Bicep and parameter-file contract (offline text checks)' {
    BeforeAll {
        $script:MainBicep = Get-Content -LiteralPath (Join-Path $script:InfraPath 'main.bicep') -Raw
        $script:RbacBicep = Get-Content -LiteralPath (Join-Path $script:InfraPath 'modules' 'rbac.bicep') -Raw
        $script:ParametersExample = Get-Content -LiteralPath (Join-Path $script:InfraPath 'main.parameters.example.json') -Raw
        $script:InfraReadme = Get-Content -LiteralPath (Join-Path $script:InfraPath 'README.md') -Raw
    }

    Context 'modules\rbac.bicep' {
        It 'includes the name prefix in the role-definition name so deployments cannot overwrite each other' {
            $script:RbacBicep | Should -Match '(?m)^param namePrefix string\s*$'
            $script:RbacBicep | Should -Match '(?m)^\s+name: guid\(subscription\(\)\.id, namePrefix, customRoleName\)\s*$'
            $script:RbacBicep | Should -Not -Match 'guid\(subscription\(\)\.id, customRoleName\)'
        }

        It 'declares assignRoleAtSubscription (default true) and makes only the assignment conditional on it' {
            $script:RbacBicep | Should -Match '(?m)^param assignRoleAtSubscription bool = true\s*$'
            $script:RbacBicep | Should -Match "(?m)^resource operatorAssignment 'Microsoft\.Authorization/roleAssignments@[\d-]+' = if \(assignRoleAtSubscription\) \{"
            $script:RbacBicep | Should -Match "(?m)^resource operatorRole 'Microsoft\.Authorization/roleDefinitions@[\d-]+' = \{"
        }

        It 'always scopes the role definition to the subscription plus the additional assignable scopes' {
            $script:RbacBicep | Should -Match '(?s)assignableScopes: concat\(\[\s*subscription\(\)\.id\s*\], additionalAssignableScopes\)'
        }

        It 'grants only read and suspend, plus write only on opt-in, and never resume or wildcards' {
            $actionsBlock = [regex]::Match($script:RbacBicep, '(?s)var actions = concat\(.*?\] : \[\]\)').Value
            $actionsBlock | Should -Not -BeNullOrEmpty
            $actionsBlock | Should -Match "'Microsoft\.Fabric/capacities/read'"
            $actionsBlock | Should -Match "'Microsoft\.Fabric/capacities/suspend/action'"
            $actionsBlock | Should -Match "(?s)includeWritePermission \? \[\s*'Microsoft\.Fabric/capacities/write'\s*\] : \[\]"
            $actionsBlock | Should -Not -Match '(?i)resume'
            $actionsBlock | Should -Not -Match '\*'
            @([regex]::Matches($actionsBlock, "'Microsoft\.Fabric/[^']+'")).Count | Should -Be 3
            $script:RbacBicep | Should -Match '(?m)^\s+actions: actions\s*$'
            $script:RbacBicep | Should -Match '(?m)^\s+notActions: \[\]\s*$'
            $script:RbacBicep | Should -Match '(?m)^\s+dataActions: \[\]\s*$'
        }

        It 'says plainly that capacities/write also allows scaling and changing capacity admins' {
            $script:RbacBicep | Should -Match "(?s)@description\('[^']*capacities/write also lets the identity scale a capacity and change its capacity admins[^']*'\)\s*param includeWritePermission"
            $script:RbacBicep | Should -Match 'which allows scaling a capacity and changing its capacity admins'
        }

        It 'returns the role definition ID' {
            $script:RbacBicep | Should -Match '(?m)^output roleDefinitionId string = operatorRole\.id\s*$'
        }
    }

    Context 'main.bicep' {
        It 'declares assignRoleAtSubscription (default true) and passes it, with namePrefix, to the rbac module' {
            $script:MainBicep | Should -Match '(?m)^param assignRoleAtSubscription bool = true\s*$'
            $rbacModule = [regex]::Match($script:MainBicep, "(?s)module rbac '\./modules/rbac\.bicep' = \{.*?\n\}").Value
            $rbacModule | Should -Not -BeNullOrEmpty
            $rbacModule | Should -Match '(?m)^\s+namePrefix: namePrefix\s*$'
            $rbacModule | Should -Match '(?m)^\s+assignRoleAtSubscription: assignRoleAtSubscription\s*$'
            $rbacModule | Should -Match '(?m)^\s+includeWritePermission: includeWritePermission\s*$'
            $rbacModule | Should -Match '(?m)^\s+additionalAssignableScopes: additionalAssignableScopes\s*$'
        }

        It 'keeps azPackageVersion (default 12.3.0) and passes it to the automation module' {
            $script:MainBicep | Should -Match "(?m)^param azPackageVersion string = '12\.3\.0'\s*$"
            $automationModule = [regex]::Match($script:MainBicep, "(?s)module automation '\./modules/automation\.bicep' = \{.*?\n\}").Value
            $automationModule | Should -Match '(?m)^\s+azPackageVersion: azPackageVersion\s*$'
        }

        It 'outputs the role definition ID' {
            $script:MainBicep | Should -Match '(?m)^output roleDefinitionId string = rbac\.outputs\.roleDefinitionId\s*$'
        }

        It 'describes the write permission honestly' {
            $script:MainBicep | Should -Match 'capacities/write also lets the identity scale a capacity and change its capacity admins'
        }

        It 'emits every output that deploy.ps1 reads' {
            foreach ($name in 'resourceGroupName', 'automationAccountName', 'runbookName', 'runtimeEnvironmentName', 'identityClientId', 'identityPrincipalId', 'roleDefinitionId', 'nightlyScheduleName', 'backstopScheduleName') {
                $script:MainBicep | Should -Match "(?m)^output $name string" -Because "deploy.ps1 reads the '$name' output"
            }
        }
    }

    Context 'main.parameters.example.json' {
        It 'is valid JSON that sets every main.bicep parameter with placeholders only' {
            $document = $script:ParametersExample | ConvertFrom-Json
            $declared = [regex]::Matches($script:MainBicep, '(?m)^param\s+(\w+)\s') | ForEach-Object { $_.Groups[1].Value }
            foreach ($name in $declared) { @($document.parameters.PSObject.Properties.Name) | Should -Contain $name }
            @($document.parameters.PSObject.Properties.Name).Count | Should -Be @($declared).Count
            $document.parameters.assignRoleAtSubscription.value | Should -BeTrue
            $document.parameters.azPackageVersion.value | Should -Be '12.3.0'
            $document.parameters.includeWritePermission.value | Should -BeFalse
        }

        It 'contains no real identifiers (only all-zero GUIDs and example.com addresses)' {
            $guids = [regex]::Matches($script:ParametersExample, '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}') | ForEach-Object { $_.Value }
            @($guids | Where-Object { $_ -notmatch '^[0-]+$' }) | Should -BeNullOrEmpty
            $emails = [regex]::Matches($script:ParametersExample, '[\w\.\-]+@[\w\-]+\.[\w\.\-]+') | ForEach-Object { $_.Value }
            @($emails | Where-Object { $_ -notmatch '@example\.com$' }) | Should -BeNullOrEmpty
        }
    }

    Context 'every infra file stays generic' {
        It 'contains no real identifiers in <File>' -ForEach @(
            @{ File = 'main.bicep' }, @{ File = 'README.md' }, @{ File = 'modules\rbac.bicep' }, @{ File = 'modules\automation.bicep' }
        ) {
            $text = Get-Content -LiteralPath (Join-Path $script:InfraPath $File) -Raw
            $guids = [regex]::Matches($text, '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}') | ForEach-Object { $_.Value }
            @($guids | Where-Object { $_ -notmatch '^[0-]+$' }) | Should -BeNullOrEmpty
            $emails = [regex]::Matches($text, '[\w\.\-]+@[\w\-]+\.[\w\.\-]+') | ForEach-Object { $_.Value }
            @($emails | Where-Object { $_ -notmatch '@example\.com$' }) | Should -BeNullOrEmpty
        }
    }

    Context 'infra\README.md' {
        It 'documents the new parameters, the manual assignment path and the role-definition naming' {
            $script:InfraReadme | Should -Match '`assignRoleAtSubscription`'
            $script:InfraReadme | Should -Match '`azPackageVersion`'
            $script:InfraReadme | Should -Match '-SkipSubscriptionRoleAssignment'
            $script:InfraReadme | Should -Match '-AzPackageVersion'
            $script:InfraReadme | Should -Match 'az role assignment create --assignee-object-id'
            $script:InfraReadme | Should -Match 'roleDefinitionId'
            $script:InfraReadme | Should -Match 'scale a capacity and change its capacity admins'
        }

        It 'no longer carries the VERIFY ON FIRST DEPLOY items that were confirmed live' {
            $script:InfraReadme | Should -Not -Match "(?s)VERIFY ON FIRST DEPLOY[^\n]*runbookType"
            $script:InfraReadme | Should -Not -Match "(?s)VERIFY ON FIRST DEPLOY[^\n]*PowerShell-74"
            $script:InfraReadme | Should -Not -Match "(?s)VERIFY ON FIRST DEPLOY[^\n]*supplies the default Az package"
            $script:InfraReadme | Should -Not -Match "(?s)VERIFY ON FIRST DEPLOY[^\n]*IANA"
        }
    }
}
}
