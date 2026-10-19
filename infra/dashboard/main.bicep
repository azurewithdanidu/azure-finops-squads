targetScope = 'resourceGroup'

@description('Web app name (globally unique; becomes <name>.azurewebsites.net).')
@minLength(2)
@maxLength(50)
param appName string

@description('Azure region.')
param location string = resourceGroup().location

@description('App Service plan SKU. Streamlit needs WebSockets, which Basic and above support.')
@allowed([
  'B1'
  'B2'
  'S1'
  'P0v3'
])
param skuName string = 'B1'

@description('Existing storage account that holds the run artifacts.')
param storageAccountName string

@description('Blob container with run artifacts.')
param containerName string = 'finops'

@description('Client (application) ID of the Entra app registration used for sign-in.')
param entraClientId string

@description('Entra tenant ID.')
param tenantId string = tenant().tenantId

@description('Object IDs of the users or groups allowed to sign in. Everyone else is rejected.')
@minLength(1)
param allowedPrincipalObjectIds array

@description('Responses endpoint of the finops-orchestrator hosted agent (chat page).')
param agentEndpoint string

@description('Tags applied to all resources.')
param tags object = {}

var storageBlobDataReader = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
var ficSettingName = 'OVERRIDE_USE_MI_FIC_ASSERTION_CLIENTID'

module identity 'br/public:avm/res/managed-identity/user-assigned-identity:0.6.0' = {
  name: 'dashboard-identity'
  params: {
    name: 'id-${appName}'
    location: location
    tags: tags
  }
}

module plan 'br/public:avm/res/web/serverfarm:0.7.0' = {
  name: 'dashboard-plan'
  params: {
    name: 'asp-${appName}'
    location: location
    tags: tags
    skuName: skuName
    kind: 'linux'
    reserved: true
  }
}

module site 'br/public:avm/res/web/site:0.24.0' = {
  name: 'dashboard-site'
  params: {
    name: appName
    location: location
    tags: tags
    kind: 'app,linux'
    serverFarmResourceId: plan.outputs.resourceId
    httpsOnly: true
    managedIdentities: {
      userAssignedResourceIds: [
        identity.outputs.resourceId
      ]
    }
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      appCommandLine: 'python -m streamlit run scripts/dashboard.py --server.port 8000 --server.address 0.0.0.0 --server.headless true --server.enableCORS false'
      webSocketsEnabled: true
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
    }
    configs: [
      {
        name: 'appsettings'
        properties: {
          SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
          WEBSITES_PORT: '8000'
          AZURE_CLIENT_ID: identity.outputs.clientId
          FINOPS_STORAGE_ACCOUNT_URL: 'https://${storageAccountName}.blob.${environment().suffixes.storage}'
          FINOPS_STORAGE_CONTAINER: containerName
          FINOPS_AGENT_ENDPOINT: agentEndpoint
          '${ficSettingName}': identity.outputs.clientId
        }
      }
      {
        name: 'authsettingsV2'
        properties: {
          platform: {
            enabled: true
          }
          globalValidation: {
            requireAuthentication: true
            unauthenticatedClientAction: 'RedirectToLoginPage'
            redirectToProvider: 'azureactivedirectory'
          }
          identityProviders: {
            azureActiveDirectory: {
              enabled: true
              login: {
                // Foundry hosted agents require the signed-in user's token, so request it at sign-in.
                loginParameters: [
                  'scope=openid profile offline_access https://ai.azure.com/user_impersonation'
                ]
              }
              registration: {
                openIdIssuer: '${environment().authentication.loginEndpoint}${tenantId}/v2.0'
                clientId: entraClientId
                clientSecretSettingName: ficSettingName
              }
              validation: {
                defaultAuthorizationPolicy: {
                  allowedPrincipals: {
                    identities: allowedPrincipalObjectIds
                  }
                }
              }
            }
          }
          login: {
            tokenStore: {
              enabled: true
            }
          }
        }
      }
    ]
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource readerAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, appName, storageBlobDataReader)
  scope: storageAccount
  properties: {
    principalId: identity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataReader)
  }
}

@description('Dashboard URL.')
output url string = 'https://${site.outputs.defaultHostname}'

@description('Web app name.')
output siteName string = site.outputs.name

@description('Principal (object) ID of the dashboard managed identity (Storage Blob Data Reader).')
output identityPrincipalId string = identity.outputs.principalId

@description('Client ID of the dashboard managed identity, used by the federated credential on the app registration.')
output identityClientId string = identity.outputs.clientId
