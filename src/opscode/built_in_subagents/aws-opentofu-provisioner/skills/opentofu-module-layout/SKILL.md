---
name: opentofu-module-layout
description: >
  Standardised architecture, file layout, variable conventions, provider configuration,
  tagging standards, OCI registry module distribution, and end-to-end module authoring
  workflow for production-grade OpenTofu modules. Use when: (1) creating, scaffolding,
  or structuring OpenTofu modules, (2) setting up versions.tf/provider.tf/variables.tf/
  outputs.tf/main.tf, (3) defining variable declarations with type, description,
  validation, and sensitive attributes, (4) configuring the AWS provider with
  default_tags, (5) sourcing modules from OCI registries (oci:// scheme), or
  (6) decomposing complex modules into logical file splits. Do NOT use for HCL
  iteration patterns, IAM policy construction, security enforcement, VPC networking,
  state management, or testing.
license: MIT
compatibility: designed for opscode
---

# OpenTofu Module Layout & Architectural Standards

Guidance and standards for structuring production-ready OpenTofu modules targeting AWS infrastructure.

---

## End-to-End Module Authoring Workflow

When creating a new OpenTofu module from scratch, follow this 7-phase workflow. Each phase maps to a specific skill:

```
1. Module Requirements & Resource Planning
   ├── Identify all AWS services needed
   ├── Determine security, encryption, and tagging requirements
   ├── Identify access patterns and IAM policy scope
   └── Determine state management strategy (encryption, locking)
2. Schema & Argument Inspection  →  use opentofu-mcp-schema-lookup skill
   ├── Call search-opentofu-registry for provider discovery
   ├── Call get-resource-docs for each AWS resource
   ├── Call get-datasource-docs for data sources
   └── Call get-provider-details for provider config
3. Module Architecture Design  →  use THIS skill (opentofu-module-layout)
   ├── Design file layout and variable structure
   ├── Configure provider with default_tags
   ├── Plan module decomposition for complex configs
   └── Source enterprise modules from OCI registries
4. IAM & Policy Implementation  →  use opentofu-iam-security skill
   ├── Author aws_iam_policy_document data sources
   ├── Implement service roles and instance profiles
   ├── Apply resource-based policies (S3, KMS, SNS)
   └── Enforce exclusive policy management
5. Security & Encryption  →  use opentofu-data-security skill
   ├── Enforce KMS encryption at rest
   ├── Apply public access blocking
   └── Disable deprecated ACLs
6. State Configuration  →  use opentofu-state-management skill
   ├── Configure client-side state encryption
   ├── Enable native S3 locking (use_lockfile)
   └── Plan key rotation with fallback blocks
7. Testing & Validation  →  use opentofu-testing-validation skill
   ├── Author .tftest.hcl test files
   ├── Embed preconditions and postconditions
   ├── Run tofu validate and tofu test
   └── Integrate OPA/Conftest policy checks
```

---

## Standard Filesystem Topology

Every OpenTofu module must decompose infrastructure into discrete, logically separated files:

```
module-root/
├── versions.tf      # terraform block: OpenTofu version, provider constraints, backend config
├── provider.tf      # Provider initialisation with default_tags block
├── variables.tf     # Input variable declarations with type, description, validation
├── outputs.tf       # Exported identifiers (ARNs, IDs, endpoints) with descriptions
├── main.tf          # Primary resource orchestration
├── [network.tf]     # Optional: VPC, subnets, endpoints (for complex modules)
├── [compute.tf]     # Optional: EC2, ECS, Lambda (for complex modules)
├── [security.tf]    # Optional: Security groups, IAM roles (for complex modules)
├── [locals.tf]      # Optional: Data transformations and computed values
├── README.md        # Documentation with usage examples
└── tests/           # OpenTofu test files
    └── main.tftest.hcl
```

> **Anti-Pattern**: Generating a monolithic `main.tf` is a severe anti-pattern that inhibits readability, complicates state management, and expands the blast radius of changes. If a module is complex, decompose `main.tf` into logical components.

---

## File Responsibilities

### 1. `versions.tf`

Strictly used for the `terraform` block. The agent must:
- Specify required OpenTofu version constraints
- Pin provider constraints using the pessimistic constraint operator (`~>`)
- Define backend configuration

```hcl
terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket       = "my-state-bucket"
    key          = "modules/my-module/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true   # Native S3 locking — no DynamoDB required
  }
}
```

### 2. `provider.tf`

Contains provider initialisations. The agent must utilise the `default_tags` block to ensure universal tagging across all spawned resources:

```hcl
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Environment = var.environment
      ManagedBy   = "OpenTofu"
      Module      = var.module_name
    }
  }
}
```

### 3. `variables.tf`

Declares all module inputs following strict conventions:

- **Explicit `type`**: Every variable MUST define its type. Do not rely on implicit typing.
- **Mandatory `description`**: Every variable MUST include a clear, meaningful description.
- **`validation` blocks**: Use for constrained values (environment names, CIDR ranges, naming patterns).
- **`sensitive = true`**: Append to any variable handling credentials, API keys, or encryption materials.

```hcl
variable "environment" {
  type        = string
  description = "Deployment environment name (e.g., dev, staging, prod)."

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "db_password" {
  type        = string
  description = "Database master password."
  sensitive   = true
}
```

### 4. `outputs.tf`

Exports critical identifiers for cross-module dependency linking:

- Every output MUST include a `description`.
- Mark outputs as `sensitive = true` if they expose secrets or encryption materials.
- Export resource ARNs, IDs, and primary endpoints.

```hcl
output "bucket_arn" {
  description = "ARN of the created S3 bucket."
  value       = aws_s3_bucket.this.arn
}

output "kms_key_id" {
  description = "ID of the KMS encryption key."
  value       = aws_kms_key.this.key_id
  sensitive   = true
}
```

### 5. `main.tf`

Reserved for primary resource orchestrations. Use `locals` blocks to compute common names, tags, and prefix strings.

---

## OCI Registry Module Distribution

OpenTofu 1.10+ natively supports **Open Container Initiative (OCI) registries** for module sourcing. The agent must favour OCI registries for internal enterprise modules.

### Source Syntax

```hcl
module "vpc" {
  source  = "oci://123456789012.dkr.ecr.us-east-1.amazonaws.com/terraform-modules/vpc:v1.2.0"

  cidr_block  = var.vpc_cidr
  environment = var.environment
}
```

### Key Points

- Use the `oci://` scheme pointing to the registry URL with a semantic version tag.
- Authentication uses ambient container credentials (`aws ecr get-login-password` or `docker login`).
- OpenTofu CLI pulls module packages as ZIP archives into `.terraform/modules/` cache.
- OCI registries provide built-in RBAC, vulnerability scanning, and immutable versioning.
- Prefer OCI over generic Git URLs or the public registry for proprietary modules.

---

## Formatting & Code Style

- **Formatting**: Run `tofu fmt` on all `.tf` files to enforce canonical 2-space indentation and alignment.
- **Naming Conventions**: Use `snake_case` for all resource names, variable names, local values, and outputs.
- **Resource Naming**: Use `this` for primary single resources (e.g., `aws_s3_bucket.this`), or descriptive names for multiple resources. Do not repeat the resource type in the resource name.

---

## Related Skills

| Skill | Use For |
|---|---|
| **opentofu-mcp-schema-lookup** | Schema inspection before writing resource blocks |
| **opentofu-iam-security** | IAM roles, policies, instance profiles, resource-based policies |
| **opentofu-data-security** | Encryption, public access blocking, ACL deprecation |
| **opentofu-vpc-networking** | VPC endpoints, private connectivity, security groups |
| **opentofu-state-management** | Client-side encryption, native S3 locking, key rotation |
| **opentofu-testing-validation** | .tftest.hcl, preconditions/postconditions, OPA/Conftest |
