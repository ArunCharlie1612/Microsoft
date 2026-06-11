# Disable Anonymous Blob Access for Storage Accounts

This change addresses a high-severity finding related to unauthorized access to sensitive secrets and cloud storage data. By disabling anonymous blob access, we mitigate the risk of data breaches and unauthorized extraction of sensitive information. The configuration ensures secure-by-default settings for storage accounts, reducing the attack surface and preventing exploitation of public access vulnerabilities.

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
