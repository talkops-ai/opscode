# Azure Baseline Primitives & Guardrails

## 1. RBAC Least-Privilege Policies

### Guiding Principles
- Avoid standard `Owner` or `Contributor` role assignments at subscription or resource group scope.
- Use custom Azure RBAC role definitions scoped strictly to required Data Actions and Control Plane Actions.
- Assign roles to Managed Identities (User-Assigned or System-Assigned) rather than Service Principals with secrets.

### Example Custom Role Definition (App Contributor)
```json
{
  "Name": "App Service & Storage Data Contributor Scoped",
  "IsCustom": true,
  "Description": "Allows managing App Service instances and accessing Blob storage data.",
  "Actions": [
    "Microsoft.Web/sites/read",
    "Microsoft.Web/sites/restart/action",
    "Microsoft.Storage/storageAccounts/blobServices/containers/read"
  ],
  "NotActions": [],
  "DataActions": [
    "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read",
    "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write"
  ],
  "NotDataActions": [],
  "AssignableScopes": [
    "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-prod-app"
  ]
}
```

---

## 2. VNet Networking Topology

### Standard Multi-Subnet VNet Architecture
- **VNet Address Space**: e.g., `10.1.0.0/16`.
- **GatewaySubnet**: `/27` dedicated for VPN Gateway / ExpressRoute.
- **Frontend / Ingress Subnet**: `/24` for Application Gateway / Azure Firewall.
- **AppSubnet**: `/22` for App Services, Virtual Machine Scale Sets, or AKS Worker Nodes.
- **DatabaseSubnet**: `/24` for Azure SQL / Cosmos DB delegated private endpoints.

### Network Security Groups (NSGs)
- Associate NSGs to every Subnet (not individual Network Interfaces).
- Default Rule: Deny all incoming traffic except explicit rules for application ports.
- Service Tags: Use `AzureLoadBalancer`, `VirtualNetwork`, and `AppService` service tags instead of broad IP ranges.

---

## 3. Secure Compute

### Managed Identity & Authentication
- Use User-Assigned Managed Identity (`UserAssigned`) for workloads needing multi-resource access.
- Disable Password / Key authentication on Azure VMs in favor of SSH public keys or Microsoft Entra ID SSH login (`AzureADLoginForLinux`).
- Enforce Private Endpoints for PaaS dependencies (Storage Accounts, Key Vaults, Azure SQL).

---

## 4. Azure CLI Guardrails

### Dry-Run & What-If Execution
- Use `az deployment group create --what-if ...` or `az deployment sub create --what-if ...` to preview template deployments before applying changes.
- Test RBAC assignments using `az role assignment list --assignee <identity-id>`.

### High-Risk Command Interceptions
- **Destructive Commands**: Intercept `az group delete`, `az vm delete`, `az aks delete`, `az storage account delete` and require confirmation.
- **Identity Check**: Always verify the current active subscription via `az account show` before running administrative commands.
