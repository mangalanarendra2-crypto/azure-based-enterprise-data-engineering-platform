// Core infrastructure for the Azure Enterprise Data Engineering Platform.
// Deploy:
//   az group create -n rg-dataplatform-dev -l centralindia
//   az deployment group create -g rg-dataplatform-dev -f infra/main.bicep \
//       -p sqlAdminPassword='<StrongPassword!>'

@description('Short prefix for resource names (3-8 lowercase letters/numbers).')
@minLength(3)
@maxLength(8)
param prefix string = 'dplat'

@description('Environment tag / suffix.')
param env string = 'dev'

param location string = resourceGroup().location

@description('Synapse SQL admin login.')
param sqlAdminLogin string = 'sqladminuser'

@secure()
@description('Synapse SQL admin password.')
param sqlAdminPassword string

var suffix = uniqueString(resourceGroup().id)
var storageName = toLower('${prefix}${env}${take(suffix, 6)}')
var tags = {
  project: 'azure-data-platform'
  environment: env
}

// ---------------------------------------------------------------- Data Lake (ADLS Gen2)
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: true // hierarchical namespace => ADLS Gen2
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

var containers = [ 'landing', 'bronze', 'silver', 'gold', 'synapse' ]

resource lakeContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [for c in containers: {
  parent: blobService
  name: c
}]

// ---------------------------------------------------------------- Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${prefix}-${env}-${take(suffix, 5)}'
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
  }
}

// ---------------------------------------------------------------- Data Factory
resource adf 'Microsoft.DataFactory/factories@2018-06-01' = {
  name: 'adf-${prefix}-${env}-${take(suffix, 5)}'
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
}

// ---------------------------------------------------------------- Databricks
resource databricks 'Microsoft.Databricks/workspaces@2024-05-01' = {
  name: 'dbw-${prefix}-${env}-${take(suffix, 5)}'
  location: location
  tags: tags
  sku: { name: 'premium' }
  properties: {
    managedResourceGroupId: subscriptionResourceId('Microsoft.Resources/resourceGroups', 'rg-dbw-${prefix}-${env}-managed')
  }
}

// ---------------------------------------------------------------- Synapse (serverless SQL)
resource synapse 'Microsoft.Synapse/workspaces@2021-06-01' = {
  name: 'syn-${prefix}-${env}-${take(suffix, 5)}'
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    defaultDataLakeStorage: {
      accountUrl: 'https://${storage.name}.dfs.${environment().suffixes.storage}'
      filesystem: 'synapse'
    }
    sqlAdministratorLogin: sqlAdminLogin
    sqlAdministratorLoginPassword: sqlAdminPassword
  }
  dependsOn: [ lakeContainers ]
}

// ---------------------------------------------------------------- RBAC: managed identities -> data lake
var storageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var storageBlobDataReader = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'

resource adfLakeAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, adf.id, storageBlobDataContributor)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributor)
    principalId: adf.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource synapseLakeAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, synapse.id, storageBlobDataReader)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataReader)
    principalId: synapse.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output storageAccountName string = storage.name
output dataFactoryName string = adf.name
output databricksWorkspaceUrl string = 'https://${databricks.properties.workspaceUrl}'
output keyVaultName string = keyVault.name
output synapseWorkspaceName string = synapse.name
