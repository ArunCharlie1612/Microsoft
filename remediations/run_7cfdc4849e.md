# Disable Anonymous Blob Access for Storage Account

This pull request addresses a high-severity security finding by disabling anonymous blob access for the specified storage account. Anonymous access to blobs can lead to unauthorized exposure of sensitive information, posing a significant risk to the confidentiality and integrity of the organization's cloud infrastructure.

### Changes:
- Updated the blob service properties to disable public access (`blobPublicAccess: false`).

### Rationale:
Disabling anonymous blob access ensures that sensitive data stored in the cloud cannot be accessed without proper authentication and authorization, mitigating the risk of unauthorized data exposure.

Please review and merge this PR to enhance the security posture of the storage account.

## Proposed Infrastructure-as-Code fix

```diff
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' existing = {
  name: 'yourStorageAccountName'
}

resource blobServiceProperties 'Microsoft.Storage/storageAccounts/blobServices@2022-09-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    isVersioningEnabled: true
    changeFeed: {
      enabled: true
    }
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    blobPublicAccess: false
  }
}
```
