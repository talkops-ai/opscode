# AWS Terraform Module Design & Structure Standards

This reference defines the architectural standards, file structure, naming conventions, and design patterns required for production-grade AWS Terraform modules. These patterns are service-agnostic and apply to any AWS resource module (S3, KMS, VPC, EKS, RDS, IAM, Lambda, DynamoDB, SQS, SNS, etc.).

---

## 1. Extended Directory & File Layout

Production modules go beyond the basic `main.tf + variables.tf + outputs.tf` structure. Each concern gets its own file:

```
module-root/
├── main.tf              # Primary resource declarations with for_each iteration
├── locals.tf            # ALL data transformations, mappings, guardrails, flattening
├── variables.tf         # Input variable definitions (map(any) primary, contextual vars)
├── outputs.tf           # Output definitions as map comprehensions
├── versions.tf          # Required Terraform version & provider constraints
├── central_tag.tf       # Central tagging module invocation with for_each
├── dependencies.tf      # terraform_remote_state & data source declarations
├── data.tf              # Data sources (aws_caller_identity, aws_region, CFn exports)
├── templates/           # IAM/resource policy templates (.tmpl files)
│   ├── basic.tmpl       # Default/simple access pattern
│   ├── cross_account.tmpl   # Cross-account access pattern
│   ├── external.tmpl        # External/vendor access pattern
│   └── ...                  # One template per access type/resource type
├── README.md            # Module documentation with usage examples
├── UPGRADE.md           # (Optional) Migration/upgrade guide between versions
├── [feature].tf         # Additional .tf files for isolated feature domains:
│                        #   vpc_endpoints.tf, event_notifications.tf,
│                        #   access_points.tf, replication.tf, etc.
└── [submodule_name]/    # Nested submodules for complex isolated features
    ├── main.tf
    ├── variables.tf     # (often named var.tf in simpler submodules)
    └── outputs.tf
```

### When to Add a Separate `.tf` File

Add a new `.tf` file when a feature:
- Has its own `for_each` iteration over a distinct data set
- Creates 2+ related resources that form a logical unit
- Has conditional creation logic (`count` or filtered `for_each`)
- Examples: VPC endpoint policy stacks, S3 event notifications, replication configuration, access points, CORS configuration

### When to Extract a Submodule

Extract to a nested submodule directory when:
- A feature needs its own independent `for_each` over a complex variable
- The feature has reusable, self-contained inputs and outputs
- The complexity warrants isolating the Terraform state surface
- Examples: S3 replication rules, access point configurations, cross-region replication

---

## 2. Map-Driven Variable Design

### Primary Input Variable

The core input is a `map(any)` or `map(object({...}))` that drives all resource creation:

```hcl
variable "resource_list" {
  description = "Map of resources to create. Each key is a unique identifier."
  type        = map(any)
}
```

Each map entry contains all configuration for one logical resource instance:
```hcl
# Example caller input:
resource_list = {
  "my-resource-alpha" = {
    type                  = "basic"
    encryption_enabled    = true
    versioning_enabled    = true
    lifecycle_enabled     = true
    cross_account_access  = []
    tags                  = {}
  }
  "my-resource-beta" = {
    type                  = "cross_account"
    encryption_enabled    = true
    cross_account_roles   = ["other-account/root"]
    tags                  = { team = "data-eng" }
  }
}
```

### Contextual Variables

Standard contextual variables that nearly every production module needs:

```hcl
variable "account_id"   { type = string }
variable "environment"  { type = string }       # dev, stg, rvw, prd
variable "region"       { type = string }
variable "account_name" { type = string }
variable "profile"      { type = string }
variable "project_name" { type = string, default = "myproject" }

variable "account_map" {
  type        = map(map(string))
  default     = {}
  description = "Cross-account ID map: account_name -> environment -> account_id"
}
```

### Variable Typing Rules

| Scenario | Type | Example |
|----------|------|---------|
| Primary resource map (complex, evolving schema) | `map(any)` | `var.resource_list` |
| Cross-account map | `map(map(string))` | `var.account_map` |
| Simple list inputs | `list(string)` | `var.allowed_cidrs` |
| Feature flags | `bool` | `var.enable_encryption` |
| Simple configuration | `string` | `var.kms_key_id` |
| Objects with stable schema | `object({...})` | Submodule variables |

Use `type = any` for primary inputs that have an evolving schema and rely heavily on `try()` for optional attributes. Use explicit types for stable, well-known inputs.

---

## 3. Naming Conventions

### Resource Naming in HCL

| Pattern | Convention | Example |
|---------|------------|---------|
| Single primary resource | `this` | `aws_kms_key.this` |
| Multiple via for_each (primary) | Descriptive plural or domain name | `aws_s3_bucket.bucket`, `aws_kms_key.keys` |
| Companion resources | Match the parent resource name | `aws_s3_bucket_policy.bucket` |
| Data sources | Descriptive of what is fetched | `data.aws_caller_identity.current` |
| Modules | Descriptive of the module purpose | `module.tagging`, `module.replication` |

### Resource Naming in AWS

Build AWS resource names dynamically using `join()` with project context:

```hcl
name = join("-", [
  var.project_name,
  substr(var.account_id, 8, 12),    # Last 4 digits of account ID
  var.environment,
  var.account_name,
  each.key,                          # Unique resource identifier from map key
  var.region_code                    # Short region code
])
```

### Segment-Based Mapping

When resources belong to logical segments (infra, apps, data, etc.), maintain a segment-to-config lookup:

```hcl
locals {
  segment_kms_map = {
    "infra"   = "project-infra-key"
    "apps"    = "project-apps-key"
    "data"    = "project-data-key"
  }
}

# Usage:
kms_key = lookup(local.segment_kms_map, split("-", each.key)[0])
```

---

## 4. Output Patterns

### Map Comprehension Outputs

Outputs from map-driven modules should return maps, not single values:

```hcl
# ARN map: resource_name -> ARN
output "resource_arns" {
  description = "Map of resource names to their ARNs"
  value = {
    for name, resource in aws_resource.this : name => resource.arn
  }
}

# ID map: resource_name -> ID
output "resource_ids" {
  description = "Map of resource names to their IDs"
  value = {
    for name, resource in aws_resource.this : name => resource.id
  }
}

# Merged outputs from multiple resource types
output "all_arns" {
  value = merge(
    { for k, v in aws_resource.type_a : v.name => { arn = v.arn, type = "a" } },
    { for k, v in aws_resource.type_b : v.name => { arn = v.arn, type = "b" } }
  )
}
```

---

## 5. AWS Security & Best Practices

### Encryption at Rest
All AWS resources storing data MUST enable encryption. Use KMS CMKs over AWS-managed keys:
- S3: `aws_s3_bucket_server_side_encryption_configuration` with `aws:kms`
- EBS: `encrypted = true` with `kms_key_id`
- RDS: `storage_encrypted = true` with `kms_key_id`
- DynamoDB: `server_side_encryption { enabled = true, kms_key_arn = ... }`
- SQS/SNS: `kms_master_key_id`
- Secrets Manager: `kms_key_id`
- EFS: `kms_key_id` in `aws_efs_file_system`

### KMS Key Rotation
Always enable automatic key rotation: `enable_key_rotation = true`

### Public Access
Default to blocking public access. For S3 use `aws_s3_bucket_public_access_block`. For RDS use `publicly_accessible = false`. For security groups restrict ingress.

### IAM Least Privilege
- Restrict policy statements to specific resource ARNs
- Use conditions (`StringEquals`, `ArnLike`, `Bool`) to scope access
- Separate read and write permissions into distinct policy statements

### Resource Separation (AWS Provider v5+)
Use standalone resources instead of inline blocks:
- `aws_s3_bucket_versioning` instead of `versioning {}` block
- `aws_s3_bucket_server_side_encryption_configuration` instead of `server_side_encryption_configuration {}`
- `aws_s3_bucket_lifecycle_configuration` instead of `lifecycle_rule {}`
- `aws_s3_bucket_logging` instead of `logging {}`
- `aws_s3_bucket_policy` instead of `policy = ...` argument

### Lifecycle Meta-Argument
Use `lifecycle { ignore_changes = [...] }` for attributes managed outside Terraform (e.g., CORS rules managed by applications, replication configs managed by separate resources).

### Dependency Management
Use explicit `depends_on` when resources have implicit ordering requirements that Terraform cannot infer from reference chains.
