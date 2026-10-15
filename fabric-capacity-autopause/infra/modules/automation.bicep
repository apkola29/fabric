targetScope = 'resourceGroup'

@description('Azure region for the Automation account, runtime environment, runbook, and managed identity.')
@minLength(1)
param location string

@description('Shared resource-name prefix. Use 3-47 alphanumeric characters or hyphens, beginning with a letter.')
@minLength(3)
@maxLength(47)
param namePrefix string = 'fabricautopause'

@description('IANA time zone for both daily schedules, for example UTC or America/Chicago.')
@minLength(1)
param timeZone string = 'UTC'

@description('Future nightly start time in ISO-8601 format with an explicit offset.')
@minLength(20)
param scheduleStartTime string

@description('Future backstop start time in ISO-8601 format with an explicit offset. Empty disables the backstop schedule.')
param backstopStartTime string = ''

@description('Email addresses that receive job-failure alerts. Empty disables both alerting resources.')
param alertEmails array = []

@description('Tags applied to resources that support tags.')
param tags object = {}

@description('Version of the Az PowerShell package installed in the runtime environment (the Microsoft Learn example uses 12.3.0).')
@minLength(1)
param azPackageVersion string = '12.3.0'

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${namePrefix}'
  location: location
  tags: tags
}

resource account 'Microsoft.Automation/automationAccounts@2024-10-23' = {
  name: 'aa-${namePrefix}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    sku: {
      name: 'Basic'
    }
    publicNetworkAccess: true
    disableLocalAuth: true
  }
}

resource runtimeEnvironment 'Microsoft.Automation/automationAccounts/runtimeEnvironments@2024-10-23' = {
  parent: account
  name: 'PowerShell-74'
  location: location
  tags: tags
  properties: {
    description: 'PowerShell 7.4 runtime for the Fabric capacity auto-pause runbook.'
    runtime: {
      language: 'PowerShell'
      version: '7.4'
    }
    // Declared explicitly: without it the environment has no Az modules and the runbook cannot sign in.
    defaultPackages: {
      Az: azPackageVersion
    }
  }
}

resource runbook 'Microsoft.Automation/automationAccounts/runbooks@2024-10-23' = {
  parent: account
  name: 'Invoke-FabricCapacityAutoPause'
  location: location
  tags: tags
  properties: {
    description: 'Discovers and suspends active Fabric capacities visible to the managed identity.'
    runbookType: 'PowerShell'
    runtimeEnvironment: runtimeEnvironment.name
    draft: {}
    logProgress: false
    logVerbose: false
  }
}

resource nightlySchedule 'Microsoft.Automation/automationAccounts/schedules@2024-10-23' = {
  parent: account
  name: 'autopause-nightly'
  properties: {
    description: 'Daily nightly Fabric capacity auto-pause.'
    frequency: 'Day'
    interval: 1
    startTime: scheduleStartTime
    timeZone: timeZone
  }
}

resource backstopSchedule 'Microsoft.Automation/automationAccounts/schedules@2024-10-23' = if (!empty(backstopStartTime)) {
  parent: account
  name: 'autopause-backstop'
  properties: {
    description: 'Daily backstop for capacities that were transitioning during the nightly run.'
    frequency: 'Day'
    interval: 1
    startTime: backstopStartTime
    timeZone: timeZone
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (!empty(alertEmails)) {
  name: 'ag-${namePrefix}'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: take(namePrefix, 12)
    enabled: true
    emailReceivers: [for (email, index) in alertEmails: {
      name: 'email-${index}'
      emailAddress: email
      useCommonAlertSchema: true
    }]
  }
}

resource jobFailureAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (!empty(alertEmails)) {
  name: 'alert-${namePrefix}-job-failure'
  location: 'global'
  tags: tags
  properties: {
    description: 'Alerts when an Automation job is Failed, Stopped, or Suspended within the last hour.'
    severity: 2
    enabled: true
    scopes: [
      account.id
    ]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
    autoMitigate: true
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'UnsuccessfulJobs'
          metricNamespace: 'Microsoft.Automation/automationAccounts'
          metricName: 'TotalJob'
          dimensions: [
            {
              name: 'Status'
              operator: 'Include'
              values: [
                'Failed'
                'Stopped'
                'Suspended'
              ]
            }
          ]
          timeAggregation: 'Total'
          operator: 'GreaterThan'
          threshold: 0
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

output accountName string = account.name
output identityClientId string = identity.properties.clientId
output identityPrincipalId string = identity.properties.principalId
output identityResourceId string = identity.id
output runtimeEnvironmentName string = runtimeEnvironment.name
output runbookName string = runbook.name
