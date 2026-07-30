---
name: terragrunt
description: "Write DRY Terragrunt configurations with include blocks, dependencies, and run-all workflows"
domain: DevOps
compatibility: "terragrunt >= 0.55"
allowed_tools:
  - execute
  - write_file
  - read_file
metadata:
  domain: terragrunt
  difficulty: advanced
---

# Terragrunt Configuration Layering Skill

You are an expert Terragrunt engineer. Follow these guidelines when writing DRY infrastructure configurations.

## Directory Structure

```
infrastructure/
├── terragrunt.hcl              # Root config (remote state, provider defaults)
├── _envcommon/                  # Shared module configs
│   ├── vpc.hcl
│   ├── eks.hcl
│   └── rds.hcl
├── dev/
│   ├── env.hcl                 # Environment-specific vars
│   ├── vpc/
│   │   └── terragrunt.hcl
│   └── eks/
│       └── terragrunt.hcl
├── staging/
│   └── ...
└── prod/
    └── ...
```

## Root Configuration

```hcl
# Root terragrunt.hcl
remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    bucket         = "myorg-terraform-state"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = var.aws_region
}
EOF
}
```

## Include Blocks

```hcl
# dev/vpc/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

include "envcommon" {
  path   = "${dirname(find_in_parent_folders())}/_envcommon/vpc.hcl"
  expose = true
}

inputs = {
  environment = "dev"
  cidr_block  = "10.0.0.0/16"
}
```

## Dependency Blocks

```hcl
dependency "vpc" {
  config_path = "../vpc"
  mock_outputs = {
    vpc_id     = "vpc-mock"
    subnet_ids = ["subnet-mock"]
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  vpc_id     = dependency.vpc.outputs.vpc_id
  subnet_ids = dependency.vpc.outputs.subnet_ids
}
```

Always provide `mock_outputs` so `terragrunt validate` and `terragrunt plan` work without deploying dependencies first.

## Generate Blocks

Use `generate` to create boilerplate files (providers, backends) — keep DRY.

## Workflow

1. `terragrunt run-all validate` — validate all modules.
2. `terragrunt run-all plan` — plan across all modules respecting dependency order.
3. `terragrunt run-all apply` — apply in dependency order.
4. `terragrunt graph-dependencies` — visualise dependency DAG.

Always run `run-all plan` before proposing changes. Never run `run-all apply` without user approval.

## Best Practices

- Use `path_relative_to_include()` for state keys — guarantees unique paths.
- Keep leaf `terragrunt.hcl` files minimal — push shared logic to `_envcommon/`.
- Use `expose = true` on includes to reference parent values.
- Pin Terraform and Terragrunt versions in root config.
- Use `prevent_destroy = true` on stateful modules.
