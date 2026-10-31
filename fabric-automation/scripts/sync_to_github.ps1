<#
.SYNOPSIS
Publishes this folder to the fabric-automation folder of the GitHub repository and proves GitHub matches it.

.DESCRIPTION
1. Checks the tools, and that gh is signed in as the repository owner and that every fetch and push address of origin is exactly that GitHub repository.
2. Runs the validator in strict mode and the validator's mutation tests.
3. Brings the local clone up to date with origin (fast-forward only) and checks that its earlier unpushed commits touch only the managed paths.
4. Stops if the mirror folder, the workflow folder, the folder above it, a workflow file or the README is a link, because a write or a
   delete through a link lands outside the clone. Mirrors this folder into <clone>\fabric-automation and copies the CI workflows,
   then scans the mirrored copy itself, so that what is committed is what was scanned even if the source changed while the tests ran.
   Only then are earlier unpushed local commits folded away (a mixed reset), so that a run that stops earlier leaves them alone.
5. Stages ONLY those paths, commits, checks that everything that would be pushed (earlier commits included)
   touches only those paths, and proves that the commit holds exactly the validated files (no extra, missing or
   different file, and nothing that is not a regular file) before anything leaves the machine. Then it pushes that
   commit by its SHA. It never force-pushes.
6. Compares the Git blob hash of every file with the one GitHub holds.
7. Optionally waits for the CI run on the pushed commit.

Nothing outside fabric-automation/ and the managed workflow files is staged, so other work in the clone is left alone.

.PARAMETER Message
Commit subject (the prefix "fabric-automation: " is added).

.PARAMETER CloneDir
The local clone of the repository. Defaults to ..\repo next to this project.

.PARAMETER DenyList
File of private terms that must never be published. Defaults to $env:FABRIC_AUTOMATION_DENYLIST, then to
private\denylist.txt in the project folder (Git, the mirror and the validators all ignore that folder), then
to private\denylist.txt next to the project. Publishing stops when no list is found, because the generic
leak patterns cannot see private terms. -NoDenylist overrides that for one run.

.PARAMETER NoDenylist
Publish without the private term check. Use only when the list really does not exist; the run prints a warning.

.PARAMETER NoPush
Do everything up to and including the local commit and the pre-push check of its tree, then stop. The clone is
changed (earlier unpushed commits are folded and a commit is made) but nothing is sent to GitHub and nothing is
verified there. A later run folds that commit away again, so this is a rehearsal, not a staging area.

.PARAMETER SkipTests
Skip the validator and fact checker unit tests (the validation itself still runs).

.PARAMETER IncludeReadme
Also stage the repository README.md (used once, to add the project row). The README is scanned for leaks first.

.PARAMETER WaitCi
Wait for the validate workflow on the pushed commit and fail if it fails.

.PARAMETER ProjectDir
The project folder to publish. Defaults to the folder above this script. The tests use it to publish a copy of the
project, so that a modified copy of this script can be tested from anywhere.
#>
[CmdletBinding()]
param(
    [string]$Message = 'update documents',
    [string]$CloneDir,
    [string]$Repo = 'apkola29/fabric',
    [string]$Branch = 'master',
    [string]$DenyList,
    [switch]$NoDenylist,
    [switch]$NoPush,
    [switch]$SkipTests,
    [switch]$IncludeReadme,
    [switch]$WaitCi,
    [string]$ProjectDir
)

$ErrorActionPreference = 'Stop'
# robocopy reports success with exit codes 1 to 7; it is checked by hand below.
$PSNativeCommandUseErrorActionPreference = $false

if ($Branch -notmatch '^[A-Za-z0-9][A-Za-z0-9._/-]*$') { throw "unsafe branch name '$Branch'" }

$Project = if ($ProjectDir) { (Resolve-Path -LiteralPath $ProjectDir).Path } else { Split-Path $PSScriptRoot -Parent }
$FabricDir = Split-Path $Project -Parent
$VerifyScript = Join-Path $Project 'scripts\verify_remote.py'
if (-not $CloneDir) { $CloneDir = Join-Path $FabricDir 'repo' }
if (-not $DenyList) { $DenyList = $env:FABRIC_AUTOMATION_DENYLIST }
if (-not $DenyList) {
    foreach ($candidate in @((Join-Path $Project 'private\denylist.txt'), (Join-Path $FabricDir 'private\denylist.txt'))) {
        if (Test-Path $candidate) { $DenyList = $candidate; break }
    }
}

$Workflows = @('fabric-automation-validate.yml', 'fabric-automation-facts.yml')
$WorkflowPaths = $Workflows | ForEach-Object { ".github/workflows/$_" }
$Paths = @('fabric-automation') + $WorkflowPaths
if ($IncludeReadme) { $Paths += 'README.md' }

function Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }

function Test-GitHubRemote([string]$Address, [string]$Repository) {
    # Only the two canonical forms of the one repository on github.com. A look-alike host, another repository
    # and an address with credentials in it are all refused.
    $name = [regex]::Escape($Repository)
    foreach ($pattern in @("^https://github\.com/$name(\.git)?/?$", "^git@github\.com:$name(\.git)?$", "^ssh://git@github\.com/$name(\.git)?/?$")) {
        if ($Address -match $pattern) { return $true }
    }
    return $false
}

function Invoke-Native {
    param([string]$Exe, [string[]]$Arguments, [switch]$AllowFailure)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    # Standard output and standard error are kept apart. A warning that a command wrote to standard error while it
    # succeeded is not part of its answer, and must not end up in a commit hash, a count or a login that is parsed.
    $out = New-Object System.Collections.Generic.List[string]
    $err = New-Object System.Collections.Generic.List[string]
    try {
        & $Exe @Arguments 2>&1 | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) { $err.Add("$_") } else { $out.Add("$_") }
        }
    } finally { $ErrorActionPreference = $previous }
    $code = $LASTEXITCODE
    if ($code -ne 0 -and -not $AllowFailure) { throw "$Exe $($Arguments -join ' ') failed ($code): $((@($err) + @($out)) -join ' ')" }
    [pscustomobject]@{ ExitCode = $code; Output = (($out -join "`n").Trim()); Errors = (($err -join "`n").Trim()) }
}

function Show-Result($Result) {
    if ($Result.Output) { Write-Host $Result.Output }
    if ($Result.Errors) { Write-Host $Result.Errors }
}

function Invoke-Git([string[]]$GitArgs, [switch]$AllowFailure) {
    Invoke-Native -Exe 'git' -Arguments (@('-C', $CloneDir) + $GitArgs) -AllowFailure:$AllowFailure
}

function Assert-ManagedPaths([string]$Range) {
    # Every commit in the range, not just the net diff, may touch only the managed paths and none may be a merge.
    # The comparison is case-sensitive, like the pathspecs that Git is given below, and the log is read without
    # quoting or signature lines, so that a user's git settings cannot change what is parsed.
    $merges = [int](Invoke-Git @('rev-list', '--merges', '--count', $Range)).Output
    if ($merges -gt 0) { throw "refusing to push: $Range holds $merges merge commit(s)" }
    $log = (Invoke-Git @('-c', 'core.quotePath=false', 'log', '--no-show-signature', '--format=', '--name-only', $Range)).Output
    $touched = @($log -split "`n" | Where-Object { $_ } | Sort-Object -Unique)
    $outside = @($touched | Where-Object {
        -not ($_.StartsWith('fabric-automation/', [System.StringComparison]::Ordinal) -or ($WorkflowPaths -ccontains $_) -or ($IncludeReadme -and $_ -ceq 'README.md'))
    })
    if ($outside.Count -gt 0) { throw "refusing to push: $($outside.Count) path(s) outside the managed set are in $Range, for example '$($outside[0])'" }
}

function Test-IsLink($Item) {
    # A junction or a symbolic link. Other reparse points, such as OneDrive placeholders, are ordinary files and folders.
    return ($Item.LinkType -eq 'Junction' -or $Item.LinkType -eq 'SymbolicLink')
}

function Assert-NotALink([string]$Path, [string]$What) {
    # A write or a delete through a link lands where the link points, which can be outside the clone.
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($item -and (Test-IsLink $item)) {
        throw "$What ($Path) is a link, so the script could write or delete through it. Replace it with a real folder or file by hand and run again"
    }
}

function Find-Links([string]$Folder) {
    # Walks a folder without ever entering a link, and returns the links it meets.
    foreach ($item in Get-ChildItem -LiteralPath $Folder -Force) {
        if (Test-IsLink $item) { $item.FullName; continue }
        if ($item.PSIsContainer) { Find-Links $item.FullName }
    }
}

function Remove-Leftovers([string]$Folder) {
    # Removes bytecode, test caches and private folders (at any depth, like the validator skips them) without ever walking through a link.
    foreach ($item in Get-ChildItem -LiteralPath $Folder -Force) {
        if (Test-IsLink $item) { continue }
        if ($item.PSIsContainer) {
            if (@('__pycache__', '.pytest_cache', 'private') -contains $item.Name) { Remove-Item -LiteralPath $item.FullName -Recurse -Force }
            else { Remove-Leftovers $item.FullName }
        } elseif ($item.Extension -eq '.pyc') {
            Remove-Item -LiteralPath $item.FullName -Force
        }
    }
}

Step 'Checking tools and accounts'
foreach ($tool in 'git', 'gh', 'python') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is not installed or not on PATH" }
}
if (-not (Test-Path (Join-Path $CloneDir '.git'))) { throw "$CloneDir is not a git clone" }
foreach ($direction in @('fetch', 'push')) {
    # git expands insteadOf rewrites here, so these are the addresses a fetch or a push really uses. A remote can
    # have several push addresses, and a push then goes to all of them, so every one has to be the repository.
    $addressArgs = if ($direction -eq 'push') { @('remote', 'get-url', '--push', '--all', 'origin') } else { @('remote', 'get-url', '--all', 'origin') }
    $addresses = @((Invoke-Git $addressArgs).Output -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($addresses.Count -eq 0) { throw "origin has no $direction address" }
    foreach ($address in $addresses) {
        if (-not (Test-GitHubRemote $address $Repo)) {
            throw "a $direction address of origin is '$($address -replace '(?<=://)[^/@]*@', '')'; expected only the GitHub repository $Repo as https://github.com/$Repo or git@github.com:$Repo, with no credentials in it"
        }
    }
}
$owner = $Repo.Split('/')[0]
$login = (Invoke-Native -Exe 'gh' -Arguments @('api', 'user', '--jq', '.login')).Output
if ($login -ne $owner) { throw "gh is signed in as '$login', not '$owner'. Run: gh auth switch -u $owner" }
$current = (Invoke-Git @('rev-parse', '--abbrev-ref', 'HEAD')).Output
if ($current -ne $Branch) { throw "the clone is on '$current', expected '$Branch'" }
Write-Host "    clone: $CloneDir ($Branch), account: $login"

Step 'Validating the documents (strict) and testing the validator'
$validator = Join-Path $Project 'scripts\validate_docs.py'
$denyArgs = @()
if ($DenyList -and (Test-Path $DenyList)) {
    $denyArgs = @('--denylist', $DenyList, '--require-denylist')
} elseif ($NoDenylist) {
    Write-Warning 'publishing without the private term check (-NoDenylist); only the generic leak patterns are applied'
} else {
    throw 'no private denylist found, and the generic leak patterns cannot see private terms. Set FABRIC_AUTOMATION_DENYLIST or pass -DenyList. Use -NoDenylist only if the list really does not exist.'
}
$readmeArgs = if ($IncludeReadme) { @('--scan-file', (Join-Path $CloneDir 'README.md')) } else { @() }
$arguments = @($validator, '--strict', '--quiet') + $denyArgs + $readmeArgs
$result = Invoke-Native -Exe 'python' -Arguments $arguments -AllowFailure
Show-Result $result
if ($result.ExitCode -ne 0) { throw 'validation failed; nothing was published' }
if (-not $SkipTests) {
    Push-Location $Project
    try { $tests = Invoke-Native -Exe 'python' -Arguments @('-m', 'unittest', 'discover', '-s', 'scripts', '-p', 'test_*.py') -AllowFailure } finally { Pop-Location }
    # unittest reports on standard error.
    Write-Host ((@($tests.Errors, $tests.Output) -join "`n") -split "`n" | Where-Object { $_.Trim() } | Select-Object -Last 3 | Out-String).TrimEnd()
    if ($tests.ExitCode -ne 0) { throw 'the validator tests failed; nothing was published' }
}

Step 'Bringing the clone up to date'
Invoke-Git @('fetch', 'origin') | Out-Null
$ahead = [int](Invoke-Git @('rev-list', '--count', "origin/$Branch..HEAD")).Output
$behind = [int](Invoke-Git @('rev-list', '--count', "HEAD..origin/$Branch")).Output
Write-Host "    ahead $ahead, behind $behind"
if ($behind -gt 0) {
    if ($ahead -gt 0) { throw 'the clone has diverged from origin; resolve that by hand first' }
    Invoke-Git @('merge', '--ff-only', "origin/$Branch") | Out-Null
    Write-Host '    fast-forwarded'
}
$fold = ($ahead -gt 0 -and $behind -eq 0)
if ($fold) { Assert-ManagedPaths "origin/$Branch..HEAD" }

Step 'Mirroring the folder into the clone'
$destination = Join-Path $CloneDir 'fabric-automation'
$workflowDir = Join-Path $CloneDir '.github\workflows'
# robocopy /MIR deletes what it finds in the destination and the source lacks, and the workflow files are written by
# path. Through a junction or a symbolic link that reaches what the link points to, even with /XJ, so none of the
# places that are written to may be a link: not the mirror folder, not the workflow folder or the folder above it,
# not the workflow files, not the README.
Assert-NotALink $destination 'the mirror folder'
Assert-NotALink (Join-Path $CloneDir '.github') 'the .github folder of the clone'
Assert-NotALink $workflowDir 'the workflow folder of the clone'
foreach ($name in $Workflows) { Assert-NotALink (Join-Path $workflowDir $name) "the workflow file $name" }
if ($IncludeReadme) { Assert-NotALink (Join-Path $CloneDir 'README.md') 'the README of the clone' }
# A bare name excludes folders of that name at any depth, like the validator, which skips private folders anywhere.
$exclude = @('private', (Join-Path $Project 'docs\research\local'), '__pycache__', '.pytest_cache')
if (Test-Path -LiteralPath $destination) {
    $links = @(Find-Links $destination)
    if ($links.Count -gt 0) { throw "the mirror holds a link ($($links[0])); robocopy /MIR could delete what it points to. Remove the link by hand and run again" }
    # robocopy /MIR also never deletes what it was told to exclude by name, so bytecode, caches and private folders
    # that an earlier run or a hand edit left in the clone are removed first. The pre-push check below would refuse them anyway.
    $localResearch = Join-Path $destination 'docs\research\local'
    if (Test-Path -LiteralPath $localResearch) { Remove-Item -LiteralPath $localResearch -Recurse -Force }
    Remove-Leftovers $destination
}
$null = robocopy $Project $destination /MIR /XD @exclude /XF '*.pyc' /XJ /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with exit code $LASTEXITCODE" }
New-Item -ItemType Directory -Force -Path $workflowDir | Out-Null
foreach ($name in $Workflows) {
    # Taken from the mirrored copy, so that the bytes written here are the bytes the scan below reads. Written with
    # LF endings on purpose: these two files are outside the folder that .gitattributes covers.
    $text = [System.IO.File]::ReadAllText((Join-Path $destination "ci\$name"), [System.Text.Encoding]::UTF8) -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText((Join-Path $workflowDir $name), $text, (New-Object System.Text.UTF8Encoding($false)))
}

Step 'Scanning the mirrored copy that will be committed'
# The first validation read the source folder, and it can change before the mirror is made (the tests above take
# minutes). This scan reads the copy itself, so what is committed is what was scanned.
$scan = Invoke-Native -Exe 'python' -Arguments (@($validator, '--root', $destination, '--strict', '--quiet') + $denyArgs + $readmeArgs) -AllowFailure
Show-Result $scan
if ($scan.ExitCode -ne 0) { throw 'the mirrored copy failed validation; nothing was committed' }

if ($fold) {
    # Commits left by an earlier run were not scanned by this run's validator. The mirror rebuilt their net effect from
    # the validated folder, so they are folded away instead of being pushed as they are. A mixed reset keeps the files
    # and drops the index of those commits, so a file that was force-added although .gitignore keeps it out does not
    # come back. It happens only now, so that a run that stops earlier leaves those commits where they were.
    Invoke-Git @('reset', '--mixed', "origin/$Branch") | Out-Null
    Write-Host "    folded $ahead earlier local commit(s) into this run"
}

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
$head = (Invoke-Git @('rev-parse', 'HEAD')).Output
if ($pending -gt 0) { Assert-ManagedPaths "origin/$Branch..HEAD" }

Step 'Checking that the commit holds exactly the validated files'
$treeArgs = @($VerifyScript, '--clone', $CloneDir, '--commit', $head, '--remote-path', 'fabric-automation', '--local', $Project)
foreach ($name in $Workflows) { $treeArgs += @('--extra', ".github/workflows/$name=ci/$name") }
if ($IncludeReadme) { $treeArgs += @('--extra', ('README.md=' + (Join-Path $CloneDir 'README.md'))) }
$tree = Invoke-Native -Exe 'python' -Arguments $treeArgs -AllowFailure
Show-Result $tree
if ($tree.ExitCode -ne 0) { throw 'the commit is not exactly the validated folder (see above); nothing was pushed' }

$pushed = $false
if ($NoPush) {
    Write-Host "    -NoPush given: $pending commit(s) stay local"
} elseif ($pending -gt 0) {
    Step "Pushing $pending commit(s)"
    Invoke-Git @('push', 'origin', "${head}:refs/heads/$Branch") | Out-Null
    $pushed = $true
} else {
    Write-Host '    nothing to push: GitHub already has this commit'
}

if ($NoPush) { Write-Host 'Stopped before verification because of -NoPush.'; return }

Step 'Verifying that GitHub holds exactly this content'
$verifyArgs = @($VerifyScript, '--repo', $Repo, '--ref', $Branch, '--remote-path', 'fabric-automation', '--local', $Project, '--commit', $head)
foreach ($name in $Workflows) { $verifyArgs += @('--extra', ".github/workflows/$name=ci/$name") }
if ($IncludeReadme) { $verifyArgs += @('--extra', ('README.md=' + (Join-Path $CloneDir 'README.md'))) }
$check = Invoke-Native -Exe 'python' -Arguments $verifyArgs -AllowFailure
Show-Result $check
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
    Write-Host ((@($ci.Output, $ci.Errors) -join "`n") -split "`n" | Where-Object { $_.Trim() } | Select-Object -Last 8 | Out-String).TrimEnd()
    if ($ci.ExitCode -ne 0) { throw "the CI run $runId failed" }
    Write-Host "    CI run $runId passed"
}

Write-Host ''
Write-Host "Done. https://github.com/$Repo/tree/$Branch/fabric-automation at $($head.Substring(0, 10))" -ForegroundColor Green
