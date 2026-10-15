targetScope = 'subscription'

@description('Object/principal ID of the user-assigned managed identity that will run the runbook.')
@minLength(36)
@maxLength(36)
param principalId string

@description('Shared name prefix of this deployment. It is part of the role-definition name GUID so two deployments in one subscription that use different settings cannot overwrite each other.')
@minLength(3)
@maxLength(47)
param namePrefix string

@description('Display name of the custom Fabric capacity read/suspend role. Role names must be unique per tenant.')
@minLength(1)
@maxLength(512)
param customRoleName string = 'Fabric Capacity AutoPause Operator'

@description('Opt in to Microsoft.Fabric/capacities/write if suspension needs it. Beyond suspending, capacities/write also lets the identity scale a capacity and change its capacity admins. Resume (capacities/resume/action) is never granted.')
param includeWritePermission bool = false

@description('Create the role assignment at the current subscription. Set to false to create only the role definition, then assign it by hand at a narrower scope (resource group or single capacity).')
param assignRoleAtSubscription bool = true

@description('Additional ARM scopes where the role can be assigned (added to assignableScopes). No assignment is created at these scopes.')
param additionalAssignableScopes array = []

var actions = concat([
  'Microsoft.Fabric/capacities/read'
  'Microsoft.Fabric/capacities/suspend/action'
], includeWritePermission ? [
  'Microsoft.Fabric/capacities/write'
] : [])

var roleDescription = includeWritePermission
  ? 'Read and suspend Fabric capacities. Also grants capacities/write, which allows scaling a capacity and changing its capacity admins. Resuming remains a human action.'
  : 'Read and suspend Fabric capacities. Resuming remains a human action.'

resource operatorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(subscription().id, namePrefix, customRoleName)
  properties: {
    roleName: customRoleName
    description: roleDescription
    type: 'CustomRole'
    permissions: [
      {
        actions: actions
        notActions: []
        dataActions: []
        notDataActions: []
      }
    ]
    assignableScopes: concat([
      subscription().id
    ], additionalAssignableScopes)
  }
}

resource operatorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (assignRoleAtSubscription) {
  name: guid(subscription().id, principalId, operatorRole.id)
  properties: {
    roleDefinitionId: operatorRole.id
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output roleDefinitionId string = operatorRole.id
