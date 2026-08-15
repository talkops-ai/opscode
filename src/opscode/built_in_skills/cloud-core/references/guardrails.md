# Multi-Cloud CLI Execution Guardrails

## 1. Safety Principles & Execution Checklist

Before running any mutating multi-cloud CLI command (AWS, Azure, or GCP):

1. **Pre-flight Identity Check**: Verify active identity, account/subscription ID, and region/project.
   - AWS: `aws sts get-caller-identity`
   - Azure: `az account show`
   - GCP: `gcloud config list project`
2. **Dry-Run / Preview Execution**: Perform dry-runs or generate deployment previews (`--dry-run`, `what-if`, `terraform plan`, `pulumi preview`).
3. **No Unscoped Deletions**: Never execute commands with broad wildcards (`rm -rf`, bulk resource deletions) without explicit confirmation and resource filter scopes.
4. **Credential Isolation**: Never print plaintext keys, tokens, or private secrets in CLI logs or standard output.

---

## 2. Command Safety Matrix

| Cloud Provider | Pre-flight Command | Dry-run / Preview Flag | Destructive Commands (Require Confirmation) |
|---|---|---|---|
| **AWS** | `aws sts get-caller-identity` | `--dry-run` | `aws s3 rb`, `aws ec2 terminate-instances`, `aws rds delete-db-instance` |
| **Azure** | `az account show` | `--what-if` | `az group delete`, `az vm delete`, `az aks delete` |
| **GCP** | `gcloud config list project` | `--dry-run` | `gcloud projects delete`, `gcloud compute instances delete` |

---

## 3. Pre-Execution Script / Hook Pattern

When automating CLI execution in agent workflows, follow this pre-execution validation logic:

```bash
#!/usr/bin/env bash
# Example Multi-Cloud Pre-Flight Guardrail Check

set -euo pipefail

CLOUD_PROVIDER="${1:-aws}"

case "$CLOUD_PROVIDER" in
  aws)
    echo "Checking AWS Identity..."
    aws sts get-caller-identity --output json
    ;;
  azure)
    echo "Checking Azure Subscription..."
    az account show --output json
    ;;
  gcp)
    echo "Checking GCP Project..."
    gcloud config get-value project
    ;;
  *)
    echo "Unknown cloud provider: $CLOUD_PROVIDER"
    exit 1
    ;;
esac
```
