// ─────────────────────────────────────────────────────────────
// BreachSim — root Bicep deployment (subscription scope)
// Provisions the full Microsoft-stack platform for the agent swarm.
// ─────────────────────────────────────────────────────────────
targetScope = 'subscription'

@minLength(1)
@description('Environment name (azd) used to derive resource names')
param environmentName string

@description('Primary Azure region')
param location string = 'eastus2'

@description('Region for the Azure OpenAI account. Defaults to a region with gpt-4o Standard quota.')
param openAiLocation string = 'eastus2'

@description('GPT-4o model deployment capacity (TPM in thousands)')
param gptCapacity int = 30

@description('Deploy Azure OpenAI. Set "false" to skip when OpenAI access is not yet approved (app runs in stub mode).')
param deployOpenAi string = 'false'

@description('Azure AI Search SKU. "free" (~$0, 1 per sub) for demos; "basic" for production.')
param searchSku string = 'free'

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var prefix = 'bsim'
var tags = { 'azd-env-name': environmentName, app: 'breachsim' }

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module platform 'modules/platform.bicep' = {
  name: 'platform'
  scope: rg
  params: {
    location: location
    prefix: prefix
    resourceToken: resourceToken
    gptCapacity: gptCapacity
    openAiLocation: openAiLocation
    deployOpenAi: toLower(deployOpenAi) == 'true'
    searchSku: searchSku
    tags: tags
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_OPENAI_ENDPOINT string = platform.outputs.openAiEndpoint
output AZURE_SEARCH_ENDPOINT string = platform.outputs.searchEndpoint
output COSMOS_ENDPOINT string = platform.outputs.cosmosEndpoint
output EVENTGRID_TOPIC_ENDPOINT string = platform.outputs.eventGridEndpoint
output AZURE_KEY_VAULT_URI string = platform.outputs.keyVaultUri
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = platform.outputs.acrLoginServer
output API_URI string = platform.outputs.apiUri
output WEB_URI string = platform.outputs.webUri
