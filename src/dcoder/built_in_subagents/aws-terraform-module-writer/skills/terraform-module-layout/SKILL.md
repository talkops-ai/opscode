---
name: terraform-module-layout
description: >
  Standardized architecture, file layout, variable conventions, formatting rules,
  cross-account dependency patterns, remote state integration, central tagging,
  submodule extraction rules, and end-to-end module authoring workflow for
  production-grade Terraform modules. Use when: (1) creating, scaffolding, or
  structuring Terraform modules, (2) setting up main.tf/locals.tf/variables.tf/
  outputs.tf/versions.tf/central_tag.tf/dependencies.tf, (3) defining variable
  declaration standards and map(any) primary inputs, (4) configuring provider
  requirements, (5) implementing AWS resource tagging via central tagging modules,
  (6) wiring terraform_remote_state dependencies and cross-account account maps,
  (7) deciding when to extract submodules vs domain-specific .tf files, or
  (8) orchestrating the end-to-end module authoring workflow across skills.
  Do NOT use for HCL iteration patterns (use terraform-iteration-patterns),
  IAM policy construction (use aws-iam-policy-engine), security enforcement
  (use aws-data-security-enforcement), or VPC networking (use aws-vpc-network-patterns).
license: MIT
compatibility: designed for deepagents-code
---

# Terraform Module Layout & Architectural Standards

Guidance and standards for structuring production-ready Terraform modules.

---

## End-to-End Module Authoring Workflow

When creating a new Terraform module from scratch, follow this 5-phase workflow. Each phase maps to a specific skill in the decomposed skill set:

```
1. Module Requirements & Resource Planning
   ├── Identify all AWS services needed
   ├── Determine security, encryption, and tagging requirements
   ├── Identify access patterns: same-account, cross-account, cross-env, external
   └── Determine if resource policies or IAM policies are needed
2. Schema & Argument Inspection  →  use terraform-mcp-schema-lookup skill
   ├── Query provider resource schemas via MCP server
   ├── Confirm required vs optional arguments and attribute exports
   ├── Verify AWS Provider v5 resource separations
   └── Check deprecated arguments and breaking changes
3. Module Architecture Design  →  use THIS skill (terraform-module-layout)
   ├── Design file layout and variable structure
   ├── Plan locals.tf transformations
   ├── Determine if submodules are needed
   ├── Wire central tagging and remote-state dependencies
   └── Plan domain-specific .tf file separation
4. Module Implementation  →  use terraform-iteration-patterns skill
   ├── Implement map-driven for_each resources in main.tf
   ├── Build locals.tf with transformations, flattening, ARN composition
   ├── Add guardrail validation maps
   ├── Create dynamic blocks and filtered iterations
   └── Apply IAM policies (aws-iam-policy-engine) and security (aws-data-security-enforcement)
5. Verification & Repair  →  use terraform-repair-loop skill
   ├── Run terraform validate for syntax/schema checks
   ├── Run tflint for provider-specific linting
   ├── Diagnose and remediate errors iteratively
   └── Generate usage guide and input/output tables in README.md
```

## Standard Directory Architecture

Every Terraform module must adhere to a standardized root file structure. Production modules go beyond the basic `main.tf + variables.tf + outputs.tf` to separate concerns:

```
module-root/
├── main.tf              # Primary resource declarations with for_each iteration
├── locals.tf            # ALL data transformations, mappings, guardrails, flattening
├── variables.tf         # Input variable definitions (map(any) primary, contextual vars)
├── outputs.tf           # Output definitions as map comprehensions
├── versions.tf          # Required Terraform version & provider constraints
├── providers.tf         # Provider configuration & alias declarations (if needed)
├── central_tag.tf       # Central tagging module invocation with for_each
├── dependencies.tf      # terraform_remote_state & data source declarations
├── data.tf              # Data sources (aws_caller_identity, aws_region, CFn exports)
├── templates/           # IAM/resource policy templates (.tmpl files)
│   ├── basic.tmpl       # Default/simple access pattern
│   ├── cross_account.tmpl   # Cross-account access pattern
│   └── ...                  # One template per access type/resource type
├── README.md            # Module documentation with usage examples
├── [feature].tf         # Additional .tf files for isolated feature domains:
│                        #   vpc_endpoints.tf, event_notifications.tf,
│                        #   access_points.tf, replication.tf, etc.
└── [submodule_name]/    # Nested submodules for complex isolated features
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```

### When to Add a Separate `.tf` File

Add a new `.tf` file when a feature:
- Has its own `for_each` iteration over a distinct data set
- Creates 2+ related resources that form a logical unit
- Has conditional creation logic (`count` or filtered `for_each`)
- Examples: VPC endpoint policy stacks, S3 event notifications, replication configuration, access points

### When to Extract a Submodule

Extract to a nested submodule directory when:
- A feature needs its own independent `for_each` over a complex variable
- The feature has reusable, self-contained inputs and outputs
- The complexity warrants isolating the Terraform state surface
- Examples: S3 replication rules, access point configurations, cross-region replication

For complete structure guidelines, naming conventions, and output patterns, see [references/module-structure.md](references/module-structure.md).

---

## File Responsibilities

### 1. `versions.tf`
Defines core Terraform CLI version constraints and provider requirements:
- Always lock minimum Terraform version (`>= 1.5.0`).
- Always specify required providers with explicit version ranges using pessimistic constraint operator (`~>`).

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

### 2. `variables.tf`
Declares all module inputs following strict variable conventions.

#### Mandatory Variable Rules:
1. **Explicit Type Definitions**: Every variable MUST explicitly define its type (`string`, `bool`, `number`, `list(string)`, `map(string)`, `object({...})`). Do not rely on implicit typing or bare `any` unless dynamically required.
2. **Mandatory Descriptions**: Every variable MUST include a clear, meaningful `description` field explaining its intent and expected values.
3. **Explicit Default Handling**:
   - **Required variables**: Omit the `default` argument.
   - **Optional variables**: Supply an explicit `default` argument.
4. **Validation Blocks**: Use `validation` blocks for constrained values (e.g., environment names, CIDR ranges, naming patterns).

```hcl
variable "environment" {
  type        = string
  description = "Deployment environment name (e.g., dev, staging, prod)."

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "tags" {
  type        = map(string)
  description = "A map of custom tags to append to all created resources."
  default     = {}
}
```

For comprehensive variable patterns, see [references/variable-conventions.md](references/variable-conventions.md).

### 3. `outputs.tf`
Exports resource attributes created by the module.

#### Mandatory Output Rules:
1. Every output MUST include a `description`.
2. Mark sensitive outputs with `sensitive = true`.
3. Export resource IDs, ARNs, and relevant operational endpoints.

```hcl
output "resource_id" {
  type        = string # optional in HCL2, but description is mandatory
  description = "The unique identifier of the created resource."
  value       = aws_s3_bucket.this.id
}
```

### 4. `main.tf`
Contains resource definitions and local values.

- Use `locals` blocks to compute common names, tags, and standard prefix strings.
- Standard resource naming convention: Use `this` for primary single resources (e.g., `aws_s3_bucket.this`), or descriptive singular names for multiple resources.

### 5. `providers.tf`
Required only when configuring multi-provider setups or module provider aliases (`configuration_aliases`).

### 6. `dependencies.tf`
Declares `terraform_remote_state` data sources to consume outputs from other modules:

```hcl
data "terraform_remote_state" "kms" {
  backend = "s3"
  config = {
    bucket  = var.kms_state_bucket
    key     = var.kms_state_key
    region  = var.region
    profile = var.profile
  }
}
```

Consume remote state outputs in locals or resources:

```hcl
kms_key_arn = lookup(
  data.terraform_remote_state.kms.outputs.key_arns,
  lookup(local.segment_kms_map, each.value.segment)
)
```

### 7. `data.tf`
Data sources for account identity and region:

```hcl
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
```

---

## Cross-Account Dependencies & Account Maps

Production modules operating across multiple AWS accounts use an **account map** variable:

```hcl
variable "account_map" {
  type        = map(map(string))
  default     = {}
  description = "Map of account names to environments to AWS account IDs"
}

// Lookup: get account ID for account_a in current environment
lookup(lookup(var.account_map, "account_a"), var.environment)
```

Standard contextual variables that nearly every production module needs:

```hcl
variable "account_id"   { type = string }
variable "environment"  { type = string }       # dev, stg, rvw, prd
variable "region"       { type = string }
variable "account_name" { type = string }
variable "profile"      { type = string }
variable "project_name" { type = string, default = "myproject" }
```

For complete cross-account ARN resolution, replication patterns, environment-aware grouping, and IAM role name mapping, see [references/cross-account-patterns.md](references/cross-account-patterns.md).

---

## Formatting & Code Style Standards

- **Formatting**: Run `terraform fmt` on all `.tf` files to enforce canonical 2-space indentation and alignment.
- **Naming Conventions**: Use `snake_case` for all resource names, variable names, local values, and outputs.
- **Block Alignment**: Align equal signs (`=`) in attribute arguments within a block.
- **Resource Naming**: Do not repeat the resource type in the resource name (e.g., prefer `aws_iam_role.this` or `aws_iam_role.app` over `aws_iam_role.app_iam_role`).

---

## AWS Resource Tagging Strategy

All AWS resources supporting tags MUST adhere to the standard tagging policy.

### Simple Tagging (Small Modules)

For simple modules with a small number of resources, use `local.default_tags` merging:

```hcl
locals {
  default_tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Module      = "terraform-aws-module"
  }

  tags = merge(local.default_tags, var.tags)
}

resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name
  tags   = local.tags
}
```

### Central Tagging Module (Production Modules)

For production map-driven modules with many resources, invoke a **central tagging module** with `for_each`:

```hcl
# central_tag.tf
module "tagging" {
  for_each       = local.tagging_map
  source         = "path/to/centralized-tagging-module"
  standard_tags  = each.value["standard_tags"]
}
```

Build the `tagging_map` in `locals.tf` by iterating over the primary resource map and extracting tag-relevant attributes per resource. Then reference tags on resources via `module.tagging[each.key].output_tags`.

For detailed tagging strategies and policy examples, see [references/tagging-strategy.md](references/tagging-strategy.md).

---

## Boilerplate Module Starter

A complete starter template with standard boilerplate files is available in [assets/module-template/](assets/module-template/):

- [main.tf](assets/module-template/main.tf) — Map-driven resource creation with `for_each`
- [locals.tf](assets/module-template/locals.tf) — Data transformations, guardrails, ARN composition
- [variables.tf](assets/module-template/variables.tf) — Common input variables including `map(any)` primary input
- [outputs.tf](assets/module-template/outputs.tf) — Map comprehension output structure
- [versions.tf](assets/module-template/versions.tf) — Required providers constraint
- [providers.tf](assets/module-template/providers.tf) — Provider configuration
- [central_tag.tf](assets/module-template/central_tag.tf) — Central tagging module invocation
- [dependencies.tf](assets/module-template/dependencies.tf) — Remote state data source pattern
- [templates/policy.tmpl](assets/module-template/templates/policy.tmpl) — Sample resource policy template

---

## Related Skills

| Skill | Use For |
|---|---|
| **terraform-mcp-schema-lookup** | Schema inspection before writing resource blocks |
| **terraform-iteration-patterns** | for_each, dynamic blocks, guardrails, flattening, ARN composition |
| **aws-iam-policy-engine** | IAM and resource policy construction |
| **aws-data-security-enforcement** | Encryption, public access blocking, TLS enforcement |
| **aws-vpc-network-patterns** | VPC topology, subnets, routing, security groups |
| **terraform-repair-loop** | Automated validation and error remediation |
