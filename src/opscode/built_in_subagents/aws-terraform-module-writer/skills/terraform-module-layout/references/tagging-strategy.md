# AWS Resource Tagging Strategy & Standards

Standard guidelines for implementing consistent tagging across Terraform AWS modules.

## Table of Contents
1. [Tagging Overview](#tagging-overview)
2. [Mandatory Standard Tags](#mandatory-standard-tags)
3. [Module Tag Implementation Pattern](#module-tag-implementation-pattern)
4. [Provider Default Tags](#provider-default-tags)
5. [Tag Propagation Rules](#tag-propagation-rules)

---

## Tagging Overview

Resource tagging is required for cost allocation, ownership tracking, compliance, automation, and operational management. All Terraform modules creating AWS resources must implement standardized tagging.

---

## Mandatory Standard Tags

Every AWS resource created by a module must include the following core metadata tags:

| Tag Key | Format / Example | Description |
|---|---|---|
| `Environment` | `dev`, `staging`, `prod` | Deployment stage environment |
| `ManagedBy` | `Terraform` | Tool managing the infrastructure |
| `Project` | `aws-orchestrator` | Project or workload name |
| `Owner` | `platform-team` | Responsible team or email |
| `Module` | `terraform-aws-<module-name>` | Terraform module identifier |

---

## Module Tag Implementation Pattern

Inside the module's `main.tf`, establish a standardized `locals` block that constructs default tags and merges user-provided custom tags.

### 1. Define Tag Input Variable (`variables.tf`)
```hcl
variable "tags" {
  type        = map(string)
  description = "A map of custom tags to append to all created resources."
  default     = {}
}
```

### 2. Merge Tags in Locals (`main.tf`)
```hcl
locals {
  default_tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
    Module      = "terraform-aws-module"
  }

  # User-supplied tags override or extend default tags
  tags = merge(local.default_tags, var.tags)
}
```

### 3. Apply Local Tags to Resources
```hcl
resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name
  tags   = local.tags
}
```

---

## Provider Default Tags

When consuming modules in root configurations, provider-level `default_tags` can automatically apply baseline tags across all resources:

```hcl
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      ManagedBy   = "Terraform"
      Repository  = "https://github.com/org/repo"
    }
  }
}
```

> **Note**: Module-level explicit tags override provider default tags when key conflicts occur.

---

## Tag Propagation Rules

Ensure tags propagate correctly to nested resources:
- **Auto Scaling Groups**: Use `dynamic "tag"` blocks or `launch_template` tag specifications with `propagate_at_launch = true`.
- **ECS Tasks & Services**: Set `enable_ecs_managed_tags = true` and `propagate_tags = "SERVICE"`.
- **EKS Worker Nodes**: Ensure EC2 instances receive cluster tags.
