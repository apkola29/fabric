<#
.SYNOPSIS
  One-time identity setup for HiCRM, run by a Microsoft Entra admin. Creating a service account needs Application
  Administrator (or Cloud Application Administrator); -GrantPlatformAppCreation grants a Microsoft Graph application
  permission, which needs Privileged Role Administrator (or Global Administrator).

.DESCRIPTION
  Creates the customer's service account "<customer>sa" (for example "fabrikamsa"): an app registration and service
  principal that becomes Admin of that one customer's Fabric workspace and nothing else. The platform runs every
  customer-facing call as this account, so one customer's requests can never reach another customer's workspace.

  How the account signs in (-Credential), best first:
    Federated    The app trusts the platform's user-assigned managed identity (-ManagedIdentityObjectId): nothing is
                 created that could leak or expire. For the platform hosted in Azure.
    Certificate  (default) A self-signed certificate. Entra ID keeps only its public part; the private key goes from a
                 file only this user can read straight into the platform's encrypted credential store, and the file is
                 deleted. Microsoft recommends certificates over secrets.
    Secret       A client secret, for development. It is never printed: it's handed over in this PowerShell session
                 only (HICRM_SA_SECRET) and stored encrypted.

  Optionally (-GrantPlatformAppCreation), grants the platform's own app the Microsoft Graph permission
  Application.ReadWrite.OwnedBy. With it the platform creates service accounts for new customers by itself, and can
  only manage the apps it created. Then set TENANT_IDENTITY_AUTO_CREATE=true and this script is no longer needed.

.EXAMPLE
  az login --tenant <tenant-id>
  ./scripts/bootstrap-identities.ps1 -Customer Fabrikam -WorkspaceId <workspace-id> -Register

.EXAMPLE
  ./scripts/bootstrap-identities.ps1 -Customer Fabrikam -Credential Federated -ManagedIdentityObjectId <object-id> -Register

.EXAMPLE
  ./scripts/bootstrap-identities.ps1 -GrantPlatformAppCreation -PlatformAppId <platform-app-client-id>
#>
[CmdletBinding()]
param(
  [string] $Customer,
  [string] $TenantId,
  [string] $WorkspaceId,
  [string] $FabricApiGroupId,
  [string] $PlatformAppId,
  [switch] $GrantPlatformAppCreation,
  [switch] $Register,
  [ValidateSet('Certificate', 'Federated', 'Secret')] [string] $Credential = 'Certificate',
  [string] $ManagedIdentityObjectId,
  [ValidateRange(1, 2)] [int] $CertificateYears = 1,
  [ValidateRange(30, 730)] [int] $SecretDays = 180,
  [string] $ProductName = 'HiCRM'
)

$ErrorActionPreference = 'Stop'
$GraphAppId = '00000003-0000-0000-c000-000000000000'

function Invoke-Az {
  $output = & az @args
  if ($LASTEXITCODE -ne 0) { throw "az $($args -join ' ') failed (exit code $LASTEXITCODE)." }
  return $output
}

# az rest bodies go through a file: quoting JSON for native commands differs between PowerShell versions.
function Invoke-AzRest([string] $Method, [string] $Uri, [hashtable] $Body, [string] $Resource) {
  $file = New-TemporaryFile
  try {
    $Body | ConvertTo-Json -Depth 5 -Compress | Set-Content -Path $file -Encoding utf8
    $arguments = @('rest', '--method', $Method, '--uri', $Uri, '--headers', 'Content-Type=application/json', '--body', "@$file")
    if ($Resource) { $arguments += @('--resource', $Resource) }
    return Invoke-Az @arguments
  } finally {
    Remove-Item $file -ErrorAction SilentlyContinue
  }
}

if (-not $Customer -and -not $GrantPlatformAppCreation) { throw 'Give -Customer <name>, -GrantPlatformAppCreation, or both.' }

$account = Invoke-Az account show --output json | ConvertFrom-Json
if ($TenantId -and $account.tenantId -ne $TenantId) { throw "Signed in to tenant $($account.tenantId). Run: az login --tenant $TenantId" }
Write-Host "Signed in as $($account.user.name) in tenant $($account.tenantId)."

if ($GrantPlatformAppCreation) {
  if (-not $PlatformAppId) { throw '-GrantPlatformAppCreation needs -PlatformAppId (the platform app''s client ID).' }
  $graph = Invoke-Az ad sp show --id $GraphAppId --output json | ConvertFrom-Json
  $role = $graph.appRoles | Where-Object { $_.value -eq 'Application.ReadWrite.OwnedBy' }
  $platform = Invoke-Az ad sp show --id $PlatformAppId --output json | ConvertFrom-Json
  $existing = Invoke-Az rest --method GET --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$($platform.id)/appRoleAssignments" --output json | ConvertFrom-Json
  if ($existing.value | Where-Object { $_.appRoleId -eq $role.id }) {
    Write-Host 'The platform app already has Application.ReadWrite.OwnedBy.'
  } else {
    Invoke-AzRest POST "https://graph.microsoft.com/v1.0/servicePrincipals/$($platform.id)/appRoleAssignments" @{ principalId = $platform.id; resourceId = $graph.id; appRoleId = $role.id } | Out-Null
    Write-Host 'Granted Application.ReadWrite.OwnedBy to the platform app. Set TENANT_IDENTITY_AUTO_CREATE=true on the platform.'
  }
}

if (-not $Customer) { return }

$name = (($Customer.ToLowerInvariant()) -replace '[^a-z0-9]', '') + 'sa'
$display = "$ProductName service account - $Customer ($name)"

$app = Invoke-Az ad app list --display-name $display --output json | ConvertFrom-Json | Select-Object -First 1
if ($app) { Write-Host "Using the existing app registration $display ($($app.appId))." }
else {
  $app = Invoke-Az ad app create --display-name $display --sign-in-audience AzureADMyOrg --output json | ConvertFrom-Json
  Write-Host "Created app registration $display ($($app.appId))."
}

$sp = Invoke-Az ad sp list --filter "appId eq '$($app.appId)'" --output json | ConvertFrom-Json | Select-Object -First 1
if (-not $sp) { $sp = Invoke-Az ad sp create --id $app.appId --output json | ConvertFrom-Json }
Write-Host "Service principal $name has object ID $($sp.id)."

# The account's credential. --append keeps any it already has, so a rerun can't lock it out.
$pemFile = $null
$registerCredential = @()
switch ($Credential) {
  'Federated' {
    if ($ManagedIdentityObjectId -notmatch '^[0-9a-fA-F-]{36}$') { throw '-Credential Federated needs -ManagedIdentityObjectId: the object (principal) ID of the platform''s user-assigned managed identity.' }
    $trust = @{
      name = 'platform-managed-identity'
      issuer = "https://login.microsoftonline.com/$($account.tenantId)/v2.0"
      subject = $ManagedIdentityObjectId
      audiences = @('api://AzureADTokenExchange')
      description = "$ProductName platform runtime (managed identity)"
    }
    $existing = Invoke-Az ad app federated-credential list --id $app.appId --output json | ConvertFrom-Json
    if ($existing | Where-Object { $_.subject -eq $ManagedIdentityObjectId }) { Write-Host 'The app already trusts that managed identity.' }
    else {
      $file = New-TemporaryFile
      try {
        $trust | ConvertTo-Json -Depth 3 | Set-Content -Path $file -Encoding utf8
        Invoke-Az ad app federated-credential create --id $app.appId --parameters "@$file" --output none | Out-Null
      } finally { Remove-Item $file -ErrorAction SilentlyContinue }
      Write-Host "The app now trusts managed identity $ManagedIdentityObjectId (federated credential). Nothing secret was created."
    }
    $registerCredential = @('--federated')
  }
  'Certificate' {
    $made = Invoke-Az ad app credential reset --id $app.appId --append --create-cert --years $CertificateYears --display-name "$ProductName platform" --output json | ConvertFrom-Json
    $pemFile = $made.fileWithCertAndPrivateKey
    if (-not $pemFile -or -not (Test-Path $pemFile)) { throw 'The Azure CLI did not return the certificate file.' }
    Write-Host "Created a certificate valid for $CertificateYears year(s). Its private key is in a file only you can read until the platform stores it."
    $registerCredential = @('--certificate-file', $pemFile)
  }
  'Secret' {
    $endDate = (Get-Date).AddDays($SecretDays).ToString('yyyy-MM-dd')
    $secret = Invoke-Az ad app credential reset --id $app.appId --append --display-name "$ProductName platform" --end-date $endDate --output json | ConvertFrom-Json
    $env:HICRM_SA_SECRET = $secret.password
    Write-Host "Created a client secret that expires $endDate (not shown). Use a certificate or a federated credential outside development."
    $registerCredential = @('--secret-env', 'HICRM_SA_SECRET')
  }
}

if ($FabricApiGroupId) {
  # Needed when the Fabric tenant setting "Service principals can use Fabric APIs" is limited to a security group.
  $members = Invoke-Az ad group member check --group $FabricApiGroupId --member-id $sp.id --output json | ConvertFrom-Json
  if (-not $members.value) { Invoke-Az ad group member add --group $FabricApiGroupId --member-id $sp.id | Out-Null }
  Write-Host "$name is in the Fabric API security group."
}

if ($WorkspaceId) {
  # The platform also does this when it provisions; doing it here helps when the platform identity has handed over.
  try {
    Invoke-AzRest POST "https://api.fabric.microsoft.com/v1/workspaces/$WorkspaceId/roleAssignments" @{ principal = @{ id = $sp.id; type = 'ServicePrincipal' }; role = 'Admin' } 'https://api.fabric.microsoft.com' | Out-Null
    Write-Host "$name is Admin of workspace $WorkspaceId."
  } catch {
    Write-Warning "Couldn't add $name to the workspace (it may already have a role): $($_.Exception.Message)"
  }
}

# --env-file-if-exists: the deployment's settings (.env), as "npm run cli" reads them.
$registerArgs = @('--env-file-if-exists=.env', 'scripts/platform-cli.js', 'identity-register', $Customer, '--app-id', $app.appId, '--object-id', $sp.id) + $registerCredential
if ($Register) {
  Push-Location (Join-Path $PSScriptRoot '..')
  try {
    # The CLI asks for the platform credential and the credential-store key if they aren't in the environment.
    & node @registerArgs
    if ($LASTEXITCODE -ne 0) { throw 'Registering the service account with the platform failed.' }
    & node --env-file-if-exists=.env scripts/platform-cli.js provision $Customer
  } finally {
    Pop-Location
    Remove-Item Env:HICRM_SA_SECRET -ErrorAction SilentlyContinue
    # The platform keeps the certificate encrypted now; the clear-text copy goes.
    if ($pemFile) { Remove-Item $pemFile -ErrorAction SilentlyContinue }
  }
} else {
  Write-Host ''
  Write-Host 'Register it with the platform from this same PowerShell window, then delete the certificate file if there is one:'
  Write-Host "  node $($registerArgs -join ' ')"
  Write-Host "  node --env-file-if-exists=.env scripts/platform-cli.js provision $Customer"
}
