---
name: cloud-azure
description: "Azure CLI operations, ARM templates, Bicep, AKS, and App Service patterns"
domain: DevOps
compatibility: "az-cli >= 2.60"
allowed_tools:
  - execute
  - write_file
  - read_file
metadata:
  domain: cloud-azure
  difficulty: intermediate
---

# Microsoft Azure Cloud Skill

You are an expert Azure cloud engineer. Follow these guidelines for Azure CLI, Bicep, and Azure services.

## Azure CLI Patterns

```bash
# Create a resource group
az group create --name myResourceGroup --location eastus

# List resources with JMESPath
az vm list --resource-group myResourceGroup --query "[].{Name:name, Size:hardwareProfile.vmSize, State:powerState}" --output table

# Deploy a Bicep template
az deployment group create --resource-group myResourceGroup --template-file main.bicep --parameters env=prod
```

## Bicep (Recommended over ARM)

```bicep
@description('The environment name')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Location for all resources')
param location string = resourceGroup().location

var storageName = 'st${uniqueString(resourceGroup().id)}'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  tags: {
    Environment: environment
    ManagedBy: 'dcoder'
  }
}

output storageId string = storageAccount.id
```

- Use **Bicep** over raw ARM JSON — cleaner syntax, better tooling.
- Use `@allowed`, `@minLength`, `@maxLength` decorators for validation.
- Use `modules` for reusable components.
- Validate: `az bicep build --file main.bicep` and `az deployment group what-if`.

## Key Services

| Service | Use Case |
|---------|----------|
| AKS | Managed Kubernetes |
| App Service | Managed web apps |
| Azure Functions | Serverless compute |
| Azure SQL | Managed SQL databases |
| Blob Storage | Object storage |
| Key Vault | Secrets, keys, certificates |
| Container Registry | Docker image registry |
| Virtual Network | Network isolation |
| Azure DevOps | CI/CD pipelines |

## AKS Patterns

```bash
# Create AKS cluster with managed identity
az aks create --resource-group myRG --name myAKS \
  --node-count 3 --enable-managed-identity \
  --network-plugin azure --enable-oidc-issuer \
  --enable-workload-identity

# Get credentials
az aks get-credentials --resource-group myRG --name myAKS
```

## Security

- Use **Managed Identities** — avoid service principal secrets.
- Store secrets in **Azure Key Vault** with RBAC access policies.
- Enable **Microsoft Defender for Cloud** for security posture.
- Use **Private Endpoints** for PaaS services in VNets.
- Enable **diagnostic settings** for audit logging.
- Use **Azure Policy** for compliance guardrails.
