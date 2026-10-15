targetScope = 'subscription'

@description('Azure region for the resource group, Automation account, and managed identity.')
@minLength(1)
param location string

@description('Name of the resource group that contains the auto-pause infrastructure.')
@minLength(1)
@maxLength(90)
param resourceGroupName string = 'rg-fabric-autopause'

@description('Shared resource-name prefix. Use 3-47 alphanumeric characters or hyphens, beginning with a letter.')
@minLength(3)
@maxLength(47)
param namePrefix string = 'fabricautopause'

@description('IANA time zone for both daily schedules, for example UTC or America/Chicago.')
@minLength(1)
param timeZone string = 'UTC'

@description('Future nightly start time in ISO-8601 format with an explicit offset, for example 2026-10-16T00:00:00-05:00.')
@minLength(20)
param scheduleStartTime string

@description('Future backstop start time in ISO-8601 format with an explicit offset. Empty disables the backstop schedule.')
param backstopStartTime string = ''

@description('Email addresses that receive job-failure alerts. Empty disables both the action group and metric alert.')
param alertEmails array = []

@description('Opt in to Microsoft.Fabric/capacities/write if suspension needs it. Beyond suspending, capacities/write also lets the identity scale a capacity and change its capacity admins. Resume (capacities/resume/action) is never granted.')
param includeWritePermission bool = false

@description('Create the custom-role assignment at the whole subscription. Set to false to create only the role definition and assign it by hand at a narrower scope (resource group or single capacity); nothing can be paused until an assignment exists.')
param assignRoleAtSubscription bool = true

@description('Display name of the custom Fabric capacity read/suspend role. Role names must be unique per tenant.')
@minLength(1)
@maxLength(512)
param customRoleName string = 'Fabric Capacity AutoPause Operator'

@description('Additional ARM scopes where the custom role can be assigned (added to assignableScopes). Does not create assignments at those scopes.')
param additionalAssignableScopes array = []

@description('Tags applied to the resource group and resources that support tags.')
param tags object = {}

@description('Version of the Az PowerShell package installed in the Automation runtime environment.')
@minLength(1)
param azPackageVersion string = '12.3.0'

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module automation './modules/automation.bicep' = {
  name: 'automation-${namePrefix}'
  scope: resourceGroup
  params: {
    location: location
    namePrefix: namePrefix
    timeZone: timeZone
    scheduleStartTime: scheduleStartTime
    backstopStartTime: backstopStartTime
    alertEmails: alertEmails
    tags: tags
    azPackageVersion: azPackageVersion
  }
}

module rbac './modules/rbac.bicep' = {
  name: 'rbac-${namePrefix}'
  scope: subscription()
  params: {
    principalId: automation.outputs.identityPrincipalId
    namePrefix: namePrefix
    customRoleName: customRoleName
    includeWritePermission: includeWritePermission
    assignRoleAtSubscription: assignRoleAtSubscription
    additionalAssignableScopes: additionalAssignableScopes
  }
}

output resourceGroupName string = resourceGroup.name
output automationAccountName string = automation.outputs.accountName
output runbookName string = automation.outputs.runbookName
output runtimeEnvironmentName string = automation.outputs.runtimeEnvironmentName
output identityClientId string = automation.outputs.identityClientId
output identityPrincipalId string = automation.outputs.identityPrincipalId
output identityResourceId string = automation.outputs.identityResourceId
output roleDefinitionId string = rbac.outputs.roleDefinitionId
output nightlyScheduleName string = 'autopause-nightly'
output backstopScheduleName string = empty(backstopStartTime) ? '' : 'autopause-backstop'
