targetScope = 'resourceGroup'

@description('Globally unique storage account name (3-24 lowercase letters and digits).')
@minLength(3)
@maxLength(24)
param storageAccountName string

@description('Azure region.')
param location string = resourceGroup().location

@description('Blob container that holds finops run artifacts.')
param containerName string = 'finops'

@description('Principal IDs (managed identities) that read and write run artifacts: the hosted agents.')
param writerPrincipalIds array = []

@description('Principal IDs that only read run artifacts: the dashboard app and any named users or groups.')
param readerPrincipalIds array = []

@description('Days after last modification before run artifacts move to the Cool tier.')
@minValue(7)
param coolAfterDays int = 30

@description('Days of soft delete retention for blobs and containers.')
@minValue(1)
@maxValue(365)
param softDeleteDays int = 14

@description('Tags applied to all resources.')
param tags object = {}

@description('Network default action. Hosted agents and App Service have no fixed IPs, so Allow relies on Entra RBAC (shared keys are disabled). Use Deny with a private endpoint for hardening.')
@allowed([
  'Allow'
  'Deny'
])
param networkDefaultAction string = 'Allow'

var storageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var storageBlobDataReader = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'

module storageAccount 'br/public:avm/res/storage/storage-account:0.33.1' = {
  name: 'finops-storage'
  params: {
    name: storageAccountName
    location: location
    tags: tags
    kind: 'StorageV2'
    skuName: 'Standard_GRS'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      defaultAction: networkDefaultAction
      bypass: 'AzureServices'
    }
    blobServices: {
      isVersioningEnabled: true
      deleteRetentionPolicyEnabled: true
      deleteRetentionPolicyDays: softDeleteDays
      containerDeleteRetentionPolicyEnabled: true
      containerDeleteRetentionPolicyDays: softDeleteDays
      containers: [
        {
          name: containerName
          publicAccess: 'None'
          roleAssignments: concat(
            map(writerPrincipalIds, id => {
              principalId: id
              principalType: 'ServicePrincipal'
              roleDefinitionIdOrName: storageBlobDataContributor
            }),
            map(readerPrincipalIds, id => {
              principalId: id
              roleDefinitionIdOrName: storageBlobDataReader
            })
          )
        }
      ]
    }
    managementPolicyRules: [
      {
        enabled: true
        name: 'cool-old-runs'
        type: 'Lifecycle'
        definition: {
          actions: {
            baseBlob: {
              tierToCool: {
                daysAfterModificationGreaterThan: coolAfterDays
              }
            }
          }
          filters: {
            blobTypes: [
              'blockBlob'
            ]
            prefixMatch: [
              '${containerName}/'
            ]
          }
        }
      }
    ]
  }
}

@description('Storage account resource ID.')
output storageAccountId string = storageAccount.outputs.resourceId

@description('Blob service endpoint.')
output blobEndpoint string = 'https://${storageAccountName}.blob.${environment().suffixes.storage}'

@description('Container name.')
output containerName string = containerName
