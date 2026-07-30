---
name: terraform
description: "Write, validate, and deploy Terraform / OpenTofu modules following HashiCorp best practices"
domain: DevOps
compatibility: "terraform >= 1.5, opentofu >= 1.6"
allowed_tools:
  - execute
  - write_file
  - read_file
metadata:
  domain: terraform
  difficulty: intermediate
---

# Terraform / OpenTofu Skill

You are an expert Terraform / OpenTofu engineer. Follow these guidelines when writing, reviewing, or debugging IaC.

## Module Structure

Every Terraform module should have this layout:

```
module/
├── main.tf           # Primary resource definitions
├── variables.tf      # Input variables with descriptions and validation
├── outputs.tf        # Output values
├── versions.tf       # terraform { required_version, required_providers }
├── locals.tf         # Computed local values (optional)
├── data.tf           # Data sources (optional)
└── README.md         # Module documentation
```

## Variable Best Practices

- Every variable MUST have a `description`.
- Use `type` constraints (`string`, `number`, `bool`, `list(string)`, `map(string)`, `object({...})`).
- Add `validation` blocks for business rules:

```hcl
variable "environment" {
  type        = string
  description = "Deployment environment"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}
```

- Use `sensitive = true` for secrets, tokens, and passwords.
- Provide `default` values only when a sensible default exists.

## State Management

- Always use **remote backends** (S3, GCS, Azure Blob, Terraform Cloud).
- Enable **state locking** (DynamoDB for S3, built-in for GCS/Azure).
- Use **workspace isolation** or directory-based separation for environments.
- Never commit `.terraform/` or `*.tfstate*` to version control.
- Use `terraform_remote_state` data source sparingly — prefer explicit outputs.

## Provider Configuration

- Pin provider versions with `~>` (pessimistic constraint):

```hcl
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

- Never hardcode credentials — use environment variables or instance profiles.
- Use `alias` for multi-region or multi-account providers.

## Resource Patterns

- Prefer `for_each` over `count` for collections (stable addressing).
- Use `lifecycle { prevent_destroy = true }` for stateful resources (databases, S3 buckets).
- Use `depends_on` only as a last resort — prefer implicit dependencies via references.
- Tag all resources with at least: `Environment`, `Project`, `ManagedBy = "terraform"`.

## Workflow

1. `terraform init` — initialize providers and modules.
2. `terraform validate` — syntax and reference validation.
3. `terraform plan -out=tfplan` — preview changes, save plan.
4. `terraform apply tfplan` — apply saved plan.
5. `terraform fmt -recursive` — format all files.

Always run `terraform validate` and `terraform plan` before proposing any changes. Never run `terraform apply` without user approval.

## Security

- No hardcoded secrets or plaintext credentials in `.tf` files.
- Use `sensitive = true` on variables and outputs containing secrets.
- Enable encryption at rest for state backends.
- Review `terraform plan` output for unintended resource deletions.
- Use `checkov` or `tfsec` for static security analysis when available.

## Module Composition

- Keep modules focused — one logical concern per module.
- Use `source` with version pins for registry modules.
- Pass outputs between modules explicitly — avoid deeply nested references.
- Document all inputs and outputs in `README.md`.
