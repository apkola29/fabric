<#
.SYNOPSIS
Publishes this folder to the fabric-automation folder of the GitHub repository and proves GitHub matches it.

.DESCRIPTION
1. Checks the tools, and that gh is signed in as the repository owner.
2. Runs the validator in strict mode and the validator's mutation tests.
3. Brings the local clone up to date with origin (fast-forward only).
4. Mirrors this folder into <clone>\fabric-automation and copies the CI workflows.
5. Stages ONLY those paths, commits and pushes.
6. Compares the Git blob hash of every file with the one GitHub holds.
7. Optionally waits for the CI run on the pushed commit.

Nothing outside fabric-automation/ and the managed workflow files is staged, so other work in the clone is left alone.

.PARAMETER Message
Commit subject (the prefix "fabric-automation: " is added).

.PARAMETER CloneDir
The local clone of the repository. Defaults to ..\repo next to this project.

.PARAMETER DenyList
File of private terms that must never be published. Defaults to $env:FABRIC_AUTOMATION_DENYLIST, then to
the private folder next to the project if it exists.

.PARAMETER IncludeReadme
Also stage the repository README.md (used once, to add the project row).

.PARAMETER WaitCi
Wait for the validate workflow on the pushed commit and fail if it fails.
#>
[CmdletBinding()]
param(
    [string]$Message = 'update documents',
    [string]$CloneDir,
    [string]$Repo = 'apkola29/fabric',
    [string]$Branch = 'master',
    [string]$DenyList,
    [switch]$NoPush,
    [switch]$SkipTests,
    [switch]$IncludeReadme,
    [switch]$WaitCi,
    [switch]$AllowOtherCommits
)

$ErrorActionPreference = 'Stop'

$Project = Split-Path $PSScriptRoot -Parent
$FabricDir = Split-Path $Project -Parent
if (-not $CloneDir) { $CloneDir = Join-Path $FabricDir 'repo' }
if (-not $DenyList) { $DenyList = $env:FABRIC_AUTOMATION_DENYLIST }
if (-not $DenyList) {
    $candidate = Join-Path (Split-Path $FabricDir -Parent) 'fabric-code-factory\private\denylist.txt'
    if (Test-Path $candidate) { $DenyList = $candidate }
}

$Workflows = @('fabric-automation-validate.yml', 'fabric-automation-facts.yml')
$Paths = @('fabric-automation') + ($Workflows | ForEach-Object { ".github/workflows/$_" })
if ($IncludeReadme) { $Paths += 'README.md' }

function Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }

function Invoke-Native {
    param([string]$Exe, [string[]]$Arguments, [switch]$AllowFailure)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $output = & $Exe @Arguments 2>&1 | ForEach-Object { "$_" } } finally { $ErrorActionPreference = $previous }
    $code = $LASTEXITCODE
    if ($code -ne 0 -and -not $AllowFailure) { throw "$Exe $($Arguments -join ' ') failed ($code): $($output -join ' ')" }
    [pscustomobject]@{ ExitCode = $code; Output = (($output -join "`n").Trim()) }
}

function Invoke-Git([string[]]$GitArgs, [switch]$AllowFailure) {
    Invoke-Native -Exe 'git' -Arguments (@('-C', $CloneDir) + $GitArgs) -AllowFailure:$AllowFailure
}

Step 'Checking tools and accounts'
foreach ($tool in 'git', 'gh', 'python') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is not installed or not on PATH" }
}
if (-not (Test-Path (Join-Path $CloneDir '.git'))) { throw "$CloneDir is not a git clone" }
$origin = (Invoke-Git @('remote', 'get-url', 'origin')).Output
if ($origin -notmatch [regex]::Escape($Repo)) { throw "origin is $origin, expected $Repo" }
$owner = $Repo.Split('/')[0]
$login = (Invoke-Native -Exe 'gh' -Arguments @('api', 'user', '--jq', '.login')).Output
if ($login -ne $owner) { throw "gh is signed in as '$login', not '$owner'. Run: gh auth switch -u $owner" }
$current = (Invoke-Git @('rev-parse', '--abbrev-ref', 'HEAD')).Output
if ($current -ne $Branch) { throw "the clone is on '$current', expected '$Branch'" }
Write-Host "    clone: $CloneDir ($Branch), account: $login"

Step 'Validating the documents (strict) and testing the validator'
$validator = Join-Path $Project 'scripts\validate_docs.py'
$arguments = @($validator, '--strict', '--quiet')
if ($DenyList -and (Test-Path $DenyList)) { $arguments += @('--denylist', $DenyList) } else { Write-Warning 'no private denylist found; only the generic leak patterns are checked' }
$result = Invoke-Native -Exe 'python' -Arguments $arguments -AllowFailure
Write-Host $result.Output
if ($result.ExitCode -ne 0) { throw 'validation failed; nothing was published' }
if (-not $SkipTests) {
    Push-Location $Project
    try { $tests = Invoke-Native -Exe 'python' -Arguments @('-m', 'unittest', 'discover', '-s', 'scripts', '-p', 'test_*.py') -AllowFailure } finally { Pop-Location }
    Write-Host ($tests.Output -split "`n" | Select-Object -Last 3 | Out-String).TrimEnd()
    if ($tests.ExitCode -ne 0) { throw 'the validator tests failed; nothing was published' }
}

Step 'Bringing the clone up to date'
Invoke-Git @('fetch', 'origin') | Out-Null
$ahead = [int](Invoke-Git @('rev-list', '--count', "origin/$Branch..HEAD")).Output
$behind = [int](Invoke-Git @('rev-list', '--count', "HEAD..origin/$Branch")).Output
Write-Host "    ahead $ahead, behind $behind"
if ($ahead -gt 0) {
    $subjects = (Invoke-Git @('log', '--format=%s', "origin/$Branch..HEAD")).Output -split "`n"
    $foreign = @($subjects | Where-Object { $_ -notlike 'fabric-automation:*' })
    if ($foreign.Count -gt 0 -and -not $AllowOtherCommits) { throw "the clone has $($foreign.Count) unpushed commit(s) that are not mine ($($foreign[0])); push or review them first, or use -AllowOtherCommits" }
}
if ($behind -gt 0) {
    if ($ahead -gt 0) { throw 'the clone has diverged from origin; resolve that by hand first' }
    Invoke-Git @('merge', '--ff-only', "origin/$Branch") | Out-Null
    Write-Host '    fast-forwarded'
}

Step 'Mirroring the folder into the clone'
$destination = Join-Path $CloneDir 'fabric-automation'
$exclude = @((Join-Path $Project 'private'), (Join-Path $Project 'docs\research\local'), '__pycache__', '.pytest_cache')
$null = robocopy $Project $destination /MIR /XD @exclude /XF '*.pyc' /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with exit code $LASTEXITCODE" }
$workflowDir = Join-Path $CloneDir '.github\workflows'
New-Item -ItemType Directory -Force -Path $workflowDir | Out-Null
foreach ($name in $Workflows) { Copy-Item (Join-Path $Project "ci\$name") (Join-Path $workflowDir $name) -Force }

Step 'Staging only this project'
Invoke-Git (@('add', '-A', '--') + $Paths) | Out-Null
$changed = (Invoke-Git (@('diff', '--cached', '--name-status', '--') + $Paths)).Output
if (-not $changed) {
    Write-Host '    nothing new to commit'
} else {
    Write-Host (($changed -split "`n" | Select-Object -First 15) -join "`n")
    $stat = (Invoke-Git (@('diff', '--cached', '--shortstat', '--') + $Paths)).Output
    $body = "$stat`n`nPublished by fabric-automation/scripts/sync_to_github.ps1 after the strict validation and the validator tests passed.`n`nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    $messageFile = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($messageFile, "fabric-automation: $Message`n`n$body`n", (New-Object System.Text.UTF8Encoding($false)))
        Step 'Committing'
        Invoke-Git (@('commit', '-F', $messageFile, '--') + $Paths) | Out-Null
    } finally { Remove-Item $messageFile -Force -ErrorAction SilentlyContinue }
}

$pending = [int](Invoke-Git @('rev-list', '--count', "origin/$Branch..HEAD")).Output
$pushed = $false
if ($NoPush) {
    Write-Host "    -NoPush given: $pending commit(s) stay local"
} elseif ($pending -gt 0) {
    Step "Pushing $pending commit(s)"
    Invoke-Git @('push', 'origin', "HEAD:$Branch") | Out-Null
    $pushed = $true
} else {
    Write-Host '    nothing to push: GitHub already has this commit'
}

if ($NoPush) { Write-Host 'Stopped before verification because of -NoPush.'; return }

Step 'Verifying that GitHub holds exactly this content'
$head = (Invoke-Git @('rev-parse', 'HEAD')).Output
$verify = Join-Path $Project 'scripts\verify_remote.py'
$verifyArgs = @($verify, '--repo', $Repo, '--ref', $Branch, '--remote-path', 'fabric-automation', '--local', $Project, '--commit', $head)
foreach ($name in $Workflows) { $verifyArgs += @('--extra', ".github/workflows/$name=ci/$name") }
$check = Invoke-Native -Exe 'python' -Arguments $verifyArgs -AllowFailure
Write-Host $check.Output
if ($check.ExitCode -ne 0) { throw 'GitHub does not match the local folder' }
$readme = (Invoke-Native -Exe 'gh' -Arguments @('api', "repos/$Repo/contents/README.md?ref=$head", '-H', 'Accept: application/vnd.github.raw')).Output
if ($readme -notmatch '\]\(fabric-automation/\)') { Write-Warning 'the repository README has no row for fabric-automation/ (run once with -IncludeReadme after adding it)' }

if ($WaitCi -and $pushed) {
    Step 'Waiting for the CI run'
    $runId = $null
    $deadline = (Get-Date).AddMinutes(5)
    while (-not $runId -and (Get-Date) -lt $deadline) {
        $runs = (Invoke-Native -Exe 'gh' -Arguments @('run', 'list', '--repo', $Repo, '--workflow', 'fabric-automation-validate.yml', '--branch', $Branch, '--limit', '10', '--json', 'databaseId,headSha')).Output | ConvertFrom-Json
        $match = $runs | Where-Object { $_.headSha -eq $head } | Select-Object -First 1
        if ($match) { $runId = $match.databaseId } else { Start-Sleep -Seconds 5 }
    }
    if (-not $runId) { throw "no CI run appeared for commit $head" }
    $ci = Invoke-Native -Exe 'gh' -Arguments @('run', 'watch', "$runId", '--repo', $Repo, '--exit-status') -AllowFailure
    Write-Host ($ci.Output -split "`n" | Select-Object -Last 8 | Out-String).TrimEnd()
    if ($ci.ExitCode -ne 0) { throw "the CI run $runId failed" }
    Write-Host "    CI run $runId passed"
}

Write-Host ''
Write-Host "Done. https://github.com/$Repo/tree/$Branch/fabric-automation at $($head.Substring(0, 10))" -ForegroundColor Green
