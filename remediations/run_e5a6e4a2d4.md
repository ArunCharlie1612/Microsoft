# Disable Anonymous Blob Access in Storage Account

This PR addresses a high-severity security finding by disabling anonymous blob access in the storage account configuration. Unauthorized access to sensitive cloud storage data and secrets was identified, which could lead to data breaches and compromise of business operations. By setting `allowBlobPublicAccess` to `false`, we ensure that blobs cannot be accessed anonymously, mitigating the risk of unauthorized data exposure.

## Proposed Infrastructure-as-Code fix

```diff
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: 'myStorageAccount'
  location: 'eastus'
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
  }
}
```
