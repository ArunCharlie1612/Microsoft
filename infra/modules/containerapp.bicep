// Reusable Container App with system-assigned identity + ACR pull.
param name string
param location string
param tags object
param environmentId string
param targetPort int
param external bool = true

@description('Environment variables injected into the container at runtime.')
param env array = []

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      ingress: {
        external: external
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      // No ACR registry at provision time: the placeholder image is public (MCR), and
      // azd configures the ACR registry + system-identity pull during `azd deploy`.
      // Declaring an ACR registry here would fail because the system identity has no
      // AcrPull yet at creation (chicken-and-egg → revision provisioning times out).
    }
    template: {
      containers: [
        {
          name: name
          // Public placeholder for the initial provision (ACR image does not exist
          // yet). azd replaces this with the built image during `azd deploy`.
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: env
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 10 }
    }
  }
}

output uri string = 'https://${app.properties.configuration.ingress.fqdn}'
output identityPrincipalId string = app.identity.principalId
