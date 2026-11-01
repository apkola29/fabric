param(
    [string]$Project = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$Branch = 'ci-probe',
    [string]$CloneDir = (Join-Path $env:TEMP 'fabric-ci-probe'),
    [string]$Repo = 'apkola29/fabric'
)
# Runs the validate workflow on a throw-away branch with the current project files, so that the Linux result is known before master is touched.
# A scratch tool, not part of the kit: it never touches the publish clone or the main branch, and it deletes the branch when it is done.
# It needs a signed-in gh that may push to the repository.
$ErrorActionPreference = 'Stop'
if (Test-Path $CloneDir) { Remove-Item $CloneDir -Recurse -Force }
git clone --quiet "https://github.com/$repo.git" $CloneDir 2>&1 | Out-Null
Set-Location $CloneDir
git config core.autocrlf true | Out-Null
$login = (gh api user --jq '.login' 2>$null)
$id = (gh api user --jq '.id' 2>$null)
git config user.name $login | Out-Null
git config user.email "$id+$login@users.noreply.github.com" | Out-Null
git checkout -q -b $Branch
$target = Join-Path $CloneDir 'fabric-automation'
robocopy $Project $target /MIR /XD private .factory __pycache__ .pytest_cache local /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $CloneDir '.github\workflows') | Out-Null
foreach ($name in 'fabric-automation-validate.yml', 'fabric-automation-facts.yml') {
    Copy-Item (Join-Path $Project "ci\$name") (Join-Path $CloneDir ".github\workflows\$name") -Force
}
git add -A fabric-automation .github/workflows
$changed = (git diff --cached --name-only | Measure-Object -Line).Lines
"files changed against master: $changed"
git commit -q -m 'ci probe: the current project files, to see the Linux result before master is touched' 2>&1 | Out-Null
git push -q origin $Branch 2>&1 | Out-Null
$sha = (git rev-parse HEAD).Trim()
"pushed $Branch at $($sha.Substring(0,10))"
Start-Sleep -Seconds 5
gh workflow run fabric-automation-validate.yml --repo $repo --ref $Branch 2>&1 | Out-Null
Start-Sleep -Seconds 10
$filter = '[.[] | select(.headSha == "' + $sha + '")] | sort_by(.createdAt) | reverse | .[0].databaseId'
$run = gh run list --repo $repo --workflow 'fabric-automation validate' --branch $Branch --limit 5 --json databaseId,headSha,status,event,createdAt --jq $filter
if (-not $run) { $run = (gh run list --repo $repo --branch $Branch --limit 1 --json databaseId --jq '.[0].databaseId') }
"run: $run"
$deadline = (Get-Date).AddMinutes(25)
do {
    Start-Sleep -Seconds 20
    $state = gh run view $run --repo $repo --json status,conclusion --jq '.status + "/" + .conclusion'
} while ((($state -like 'in_progress*') -or ($state -like 'queued*') -or ($state -like 'waiting*')) -and ((Get-Date) -lt $deadline))
"state: $state"
$log = gh run view $run --repo $repo --log 2>&1
$log | Select-String -CaseSensitive -Pattern 'Z (Ran \d+ tests? in|OK( \(|$)|FAILED \()' | ForEach-Object { ($_.Line -replace '^\S+\s+[^\t]+\t\S+\s*', '').Trim() }
$log | Select-String -CaseSensitive -Pattern '^validate\t.*\b(ERROR|FAIL): ' | Select-Object -First 20 | ForEach-Object { $_.Line.Substring(0, [Math]::Min(260, $_.Line.Length)) }
$log | Out-File (Join-Path $env:TEMP 'fabric-ci-probe.log') -Encoding utf8
git push -q origin --delete $Branch 2>&1 | Out-Null
"branch $Branch deleted"
exit $(if ($state -eq 'completed/success') { 0 } else { 1 })
