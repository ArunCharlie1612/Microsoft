// ─────────────────────────────────────────────────────────────
// BreachSim platform module — all resources in the resource group.
// ─────────────────────────────────────────────────────────────
param location string
param prefix string
param resourceToken string
param gptCapacity int
param tags object

@description('Region for the Azure OpenAI account (separate from primary region to satisfy gpt-4o quota).')
param openAiLocation string = location

@description('Deploy Azure OpenAI. Set false to skip when OpenAI access is not yet approved; the app then runs in stub mode.')
param deployOpenAi bool = false

@description('Azure AI Search SKU. "free" is ~$0 (1 per subscription) for demos; "basic" for production.')
param searchSku string = 'free'

@description('GitHub repo (owner/name) the Remediation agent opens PRs against. Empty disables real PRs.')
param githubRemediationRepo string = ''

@description('Base branch for remediation PRs.')
param githubBaseBranch string = 'main'

// ── Log Analytics + App Insights (observability) ──────────────
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs-${resourceToken}'
  location: location
  tags: tags
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 90 }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${prefix}-ai-${resourceToken}'
  location: location
  tags: tags
  kind: 'web'
  properties: { Application_Type: 'web', WorkspaceResourceId: logs.id }
}

// ── Key Vault (secrets) ───────────────────────────────────────
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${prefix}kv${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
  }
}

// ── Azure OpenAI (GPT-4o reasoning + embeddings) ──────────────
// Optional: skipped when deployOpenAi=false (e.g. OpenAI access not yet approved).
// The backend falls back to deterministic stub mode without it.
resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' = if (deployOpenAi) {
  name: '${prefix}-aoai-${resourceToken}'
  location: openAiLocation
  tags: tags
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: { customSubDomainName: '${prefix}-aoai-${resourceToken}', publicNetworkAccess: 'Enabled' }
}

resource gpt4o 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (deployOpenAi) {
  parent: openAi
  name: 'gpt-4o'
  sku: { name: 'Standard', capacity: gptCapacity }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-4o', version: '2024-11-20' }
  }
}

resource embed 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (deployOpenAi) {
  parent: openAi
  name: 'text-embedding-3-large'
  dependsOn: [gpt4o]
  sku: { name: 'Standard', capacity: 10 }
  properties: { model: { format: 'OpenAI', name: 'text-embedding-3-large', version: '1' } }
}

// ── Azure AI Search (CVE vector index) ────────────────────────
// Free tier (~$0, 1 per subscription) does not support semantic ranking, so it is
// disabled unless a paid SKU is used.
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: '${prefix}-search-${resourceToken}'
  location: location
  tags: tags
  sku: { name: searchSku }
  properties: {
    replicaCount: 1
    partitionCount: 1
    semanticSearch: searchSku == 'free' ? 'disabled' : 'standard'
  }
}

// ── Cosmos DB (threat graph + audit) ──────────────────────────
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: '${prefix}-cosmos-${resourceToken}'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [{ locationName: location, failoverPriority: 0 }]
    capabilities: [{ name: 'EnableServerless' }]
  }
}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: cosmos
  name: 'breachsim'
  properties: { resource: { id: 'breachsim' } }
}

var containers = [
  { name: 'findings', pk: '/run_id' }
  { name: 'agent_events', pk: '/run_id' }
  { name: 'threat_graph', pk: '/run_id' }
  { name: 'audit_log', pk: '/run_id' }
  { name: 'runs', pk: '/runId' }
]

resource cosmosContainers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = [
  for c in containers: {
    parent: cosmosDb
    name: c.name
    properties: {
      resource: {
        id: c.name
        partitionKey: { paths: [c.pk], kind: 'Hash' }
      }
    }
  }
]

// ── Event Grid (agent message bus) ────────────────────────────
resource eventGrid 'Microsoft.EventGrid/topics@2024-06-01-preview' = {
  name: '${prefix}-egt-${resourceToken}'
  location: location
  tags: tags
  properties: { inputSchema: 'CloudEventSchemaV1_0' }
}

// ── Container Registry + Apps environment ─────────────────────
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: '${prefix}acr${resourceToken}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource acaEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-aca-env-${resourceToken}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

// Deterministic public FQDNs (derived from the ACA env default domain) so the api
// and web apps can reference each other's URL without a circular dependency.
var apiUrl = 'https://${prefix}-api-${resourceToken}.${acaEnv.properties.defaultDomain}'
var webUrl = 'https://${prefix}-web-${resourceToken}.${acaEnv.properties.defaultDomain}'

// Azure OpenAI env (managed-identity auth, no key) — only when OpenAI is deployed.
var openAiEnv = deployOpenAi ? [
  { name: 'AZURE_OPENAI_ENDPOINT', value: openAi.properties.endpoint }
  { name: 'AZURE_OPENAI_DEPLOYMENT', value: 'gpt-4o' }
  { name: 'AZURE_OPENAI_EMBED_DEPLOYMENT', value: 'text-embedding-3-large' }
] : []

// GitHub remediation PR target (non-secret). The PAT itself is set out-of-band as a
// Container App secret (GITHUB_TOKEN) so it never lands in source or template state.
var githubEnv = empty(githubRemediationRepo) ? [] : [
  { name: 'GITHUB_REMEDIATION_REPO', value: githubRemediationRepo }
  { name: 'GITHUB_BASE_BRANCH', value: githubBaseBranch }
]

var apiEnv = concat([
  // APP_ENV=local bypasses Entra auth so the public demo UI works without an
  // app registration. Switch to 'prod' once Entra ID is wired (see go-live doc).
  { name: 'APP_ENV', value: 'local' }
  { name: 'BREACHSIM_DEMO_PACING_MS', value: '600' }
  { name: 'CORS_ORIGINS', value: webUrl }
  // Cosmos persistence via managed identity (no key) — runs/findings/graph survive restarts.
  { name: 'COSMOS_ENDPOINT', value: cosmos.properties.documentEndpoint }
], openAiEnv, githubEnv)

module api 'containerapp.bicep' = {
  name: 'api-app'
  params: {
    name: '${prefix}-api-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'api' })
    environmentId: acaEnv.id
    targetPort: 8000
    external: true
    env: apiEnv
  }
}

module web 'containerapp.bicep' = {
  name: 'web-app'
  params: {
    name: '${prefix}-web-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'web' })
    environmentId: acaEnv.id
    targetPort: 3000
    external: true
    env: [
      { name: 'NEXT_PUBLIC_API_BASE', value: apiUrl }
    ]
  }
}

// Grant each container app's managed identity permission to pull from ACR.
var acrPullRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

resource apiAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, 'api', acrPullRoleId)
  scope: acr
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: api.outputs.identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource webAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, 'web', acrPullRoleId)
  scope: acr
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: web.outputs.identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB data-plane access (Built-in Data Contributor) for the API identity so it
// can read/write documents using its managed identity (no account key needed).
resource cosmosDataContributor 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  parent: cosmos
  name: guid(cosmos.id, 'api', 'data-contributor')
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: api.outputs.identityPrincipalId
    scope: cosmos.id
  }
}

// Azure OpenAI data-plane access (Cognitive Services OpenAI User) for the API identity.
var openAiUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
)

resource apiOpenAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployOpenAi) {
  name: guid(openAi.id, 'api', openAiUserRoleId)
  scope: openAi
  properties: {
    roleDefinitionId: openAiUserRoleId
    principalId: api.outputs.identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output openAiEndpoint string = deployOpenAi ? openAi.properties.endpoint : ''
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output cosmosEndpoint string = cosmos.properties.documentEndpoint
output eventGridEndpoint string = eventGrid.properties.endpoint
output keyVaultUri string = keyVault.properties.vaultUri
output acrLoginServer string = acr.properties.loginServer
output apiUri string = api.outputs.uri
output webUri string = web.outputs.uri
