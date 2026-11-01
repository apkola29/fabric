param(
    [Parameter(Mandatory = $true)][string]$Sha,
    [string]$CloneDir = (Join-Path $env:TEMP 'fabric-acceptance-clone'),
    [string]$Repo = 'apkola29/fabric'
)
# First-run acceptance from a fresh clone of the public repository at $Sha (a scratch tool, not part of the kit).
# It runs the commands that a person starts with, with a scratch home folder, and needs the open internet for fetch.
$ErrorActionPreference = 'Continue'
$results = [System.Collections.Generic.List[string]]::new()
function Check($name, [bool]$ok, $detail = '') {
    $flag = if ($ok) { 'PASS' } else { 'FAIL' }
    $line = "[{0}] {1}{2}" -f $flag, $name, $(if ($detail) { ' | ' + $detail } else { '' })
    $results.Add($line); Write-Output $line
}
if (Test-Path $CloneDir) { Remove-Item $CloneDir -Recurse -Force }
git clone --quiet "https://github.com/$Repo.git" $CloneDir 2>&1 | Out-Null
git -C $CloneDir checkout --quiet $Sha 2>&1 | Out-Null
$head = (git -C $CloneDir rev-parse HEAD).Trim()
Check 'clone at the published commit' ($head.StartsWith($Sha)) $head.Substring(0, 12)
$proj = Join-Path $CloneDir 'fabric-automation'
$scratchHome = Join-Path $env:TEMP 'fabric-acceptance-home'
if (Test-Path $scratchHome) { Remove-Item $scratchHome -Recurse -Force }
New-Item -ItemType Directory -Path $scratchHome | Out-Null
$env:HOME = $scratchHome; $env:USERPROFILE = $scratchHome; $env:PYTHONDONTWRITEBYTECODE = '1'
Set-Location $proj
function Run($argsList) { $o = & python scripts\toolchain.py @argsList 2>&1; return @{ Code = $LASTEXITCODE; Text = ($o -join "`n") } }

$r = Run @('doctor')
Check 'doctor exits 0' ($r.Code -eq 0) ("{0} warning line(s)" -f ([regex]::Matches($r.Text, '\[WARN\]')).Count)
$r = Run @('install')
Check 'install (plan) exits 0 and changes nothing' ($r.Code -eq 0 -and $r.Text -match 'nothing was changed') (($r.Text -split "`n")[-2])
$r = Run @('install', '--apply')
Check 'install --apply exits 0 with no conflict' ($r.Code -eq 0 -and $r.Text -match '0 conflict') (($r.Text -split "`n")[-1])
$r = Run @('install', '--apply')
Check 'a second install changes nothing' ($r.Code -eq 0 -and $r.Text -match '0 to add, 0 to change') (($r.Text -split "`n")[-1])
$r = Run @('verify', '--live')
Check 'verify --live has no failure' ($r.Code -eq 0 -and $r.Text -match '0 failure') (($r.Text -split "`n")[-1])
$r = Run @('list')
Check 'list shows the profiles' ($r.Code -eq 0 -and $r.Text -match 'dev-factory') ''
$r = Run @('lock', '--no-network', '--check')
Check 'the lock is current without the network' ($r.Code -eq 0 -and $r.Text -match 'current') (($r.Text -split "`n")[-1])
$lockJson = Get-Content (Join-Path $proj 'toolchain\toolchain.lock.json') -Raw | ConvertFrom-Json
$captured = @($lockJson.contracts.PSObject.Properties | Where-Object { $_.Value.status -eq 'captured' })
$bicep = $lockJson.contracts.'bicep-mcp/default'
Check 'the lock holds at least 6 captured contracts, the Bicep one with at least 14 tools' ($captured.Count -ge 6 -and $bicep.status -eq 'captured' -and @($bicep.tools.PSObject.Properties).Count -ge 14) ("{0} captured, bicep {1}" -f $captured.Count, $bicep.package_version)
foreach ($h in 'copilot-cli', 'vscode', 'claude-code') {
    $r = Run @('render', '--host', $h)
    Check "render --host $h" ($r.Code -eq 0 -and $r.Text.Length -gt 200) ("{0} chars" -f $r.Text.Length)
}
$r = Run @('render', '--host', 'load-plan', '--profile', 'agent-planner')
Check 'load plan of agent-planner (offline server, pinned tool)' ($r.Code -eq 0 -and $r.Text -match 'powerbi-report-author') ''
$r = Run @('render', '--host', 'load-plan', '--profile', 'agent-implementer')
Check 'load plan of agent-implementer is refused (Power BI contract never captured)' ($r.Code -ne 0) ''
$r = Run @('render', '--host', 'copilot-cli', '--profile', 'dev-azure')
Check 'dev-azure renders the Bicep server through dotnet tool exec with its environment' ($r.Code -eq 0 -and $r.Text -match '"tool"' -and $r.Text -match 'DOTNET_CLI_TELEMETRY_OPTOUT') ''
$skill = Join-Path $proj '.github\skills\factory-router\SKILL.md'
Add-Content -Path $skill -Value "`n<!-- tamper -->"
$r = Run @('install', '--apply')
Check 'a tampered skill is refused without --force' ($r.Code -ne 0 -and $r.Text -match 'modified since it was installed') ''
$r = Run @('install', '--apply', '--force')
Check 'and replaced with --force' ($r.Code -eq 0 -and $r.Text -match '0 conflict') ''
$r = Run @('fetch', '--profile', 'agent-planner')
Check 'fetch --profile agent-planner (real sources)' ($r.Code -eq 0 -and $r.Text -match 'fetched') (($r.Text -split "`n")[-1])
$o = & python scripts\validate_docs.py --strict 2>&1
Check 'validate_docs --strict passes after the install' ($LASTEXITCODE -eq 0 -and ($o -join "`n") -match '0 error') (($o | Select-Object -Last 1) -join '')
$bad = @($results | Where-Object { $_ -like '[[]FAIL]*' }).Count
Write-Output ("`nacceptance: {0} check(s), {1} failed" -f $results.Count, $bad)
exit $(if ($bad -eq 0) { 0 } else { 1 })
