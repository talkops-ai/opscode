# Cross-Account, Cross-Environment & Dependency Patterns

This reference covers patterns for multi-account AWS organizations, inter-module dependencies, replication, and cross-environment access. These patterns are service-agnostic.

---

## 1. Account Map Structure

### Variable Definition

The account map is a nested map that resolves human-readable account names + environments to AWS account IDs:

```hcl
variable "account_map" {
  type        = map(map(string))
  default     = {}
  description = "Map of account names to environments to AWS account IDs"
}
```

### Example Caller Input

```hcl
account_map = {
  "hubdata" = {
    "dev" = "111111111111"
    "stg" = "222222222222"
    "prd" = "333333333333"
  }
  "hubdata2" = {
    "dev" = "444444444444"
    "stg" = "555555555555"
    "prd" = "666666666666"
  }
  "sharedsvc" = {
    "dev" = "777777777777"
    "prd" = "888888888888"
  }
}
```

### Lookup Patterns

```hcl
# Get account ID for a specific account in the current environment
lookup(lookup(var.account_map, "hubdata"), var.environment)
# => "111111111111" (when environment = "dev")

# Get account ID for a specific account in a specific environment
lookup(lookup(var.account_map, "hubdata"), "prd")
# => "333333333333"

# Build root ARN for cross-account access
format("arn:aws:iam::%s:root",
  lookup(lookup(var.account_map, "hubdata"), var.environment)
)
```

### Building Cross-Account ARN Lists

```hcl
locals {
  # From a list of account names, build root ARNs
  cross_account_root_arns = [
    for acct_name in var.cross_account_list :
      format("arn:aws:iam::%s:root",
        lookup(lookup(var.account_map, acct_name), var.environment)
      )
  ]

  # From a list of "account_name/role_name" strings, build role ARNs
  cross_account_role_arns = [
    for ref in var.cross_account_roles :
      can(regex("^arn:aws:iam:", ref))
      ? ref
      : format("arn:aws:iam::%s:role/%s",
          lookup(lookup(var.account_map, split("/", ref)[0]), var.environment),
          join("/", slice(split("/", ref), 1, length(split("/", ref))))
        )
  ]
}
```

---

## 2. Remote State Dependencies

### Pattern: Consuming Outputs from Other Modules

```hcl
# dependencies.tf
data "terraform_remote_state" "kms" {
  backend = "s3"
  config = {
    bucket  = var.kms_state_bucket
    key     = var.kms_state_key
    region  = var.region
    profile = var.profile
  }
}

data "terraform_remote_state" "iam" {
  backend = "s3"
  config = {
    bucket  = var.iam_state_bucket
    key     = var.iam_state_key
    region  = "us-west-2"          # Can be hardcoded if state is always in one region
    profile = var.profile
  }
}
```

### Consuming Remote State Outputs

```hcl
# Get a KMS key ARN from the KMS module's output map
kms_key_arn = lookup(
  data.terraform_remote_state.kms.outputs.key_arns,
  lookup(local.segment_kms_map, each.value.segment)
)

# Get a role ARN from the IAM module
role_arn = lookup(
  data.terraform_remote_state.iam.outputs.role_arns,
  "My-Service-Role"
)
```

### Variables for Remote State

```hcl
variable "kms_state_bucket" {
  type        = string
  description = "S3 bucket containing the KMS module state file"
}

variable "kms_state_key" {
  type        = string
  description = "S3 key for the KMS module state file"
}
```

---

## 3. Data Sources

### AWS Account & Identity

```hcl
# data.tf
data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

# Usage
local.account_id = data.aws_caller_identity.current.account_id
```

### CloudFormation Exports

For resources created outside Terraform (e.g., legacy CFn stacks):

```hcl
data "aws_cloudformation_export" "legacy_key_arn" {
  name = "my-kms-key-arn-export-name"
}

data "aws_cloudformation_export" "legacy_key_alias" {
  name = "my-kms-key-alias-export-name"
}

# Merge legacy keys with Terraform-managed keys
locals {
  legacy_key_map = tomap({
    split("/", data.aws_cloudformation_export.legacy_key_alias.value)[1] :
    data.aws_cloudformation_export.legacy_key_arn.value
  })
}
```

### Service-Specific Data Sources

```hcl
# ELB service account (for S3 access logging)
data "aws_elb_service_account" "elb" {}

# Current partition (for GovCloud, China regions)
data "aws_partition" "current" {}
```

---

## 4. Cross-Account Replication

### S3 Replication Configuration

```hcl
# replications/main.tf (submodule)
resource "aws_s3_bucket_replication_configuration" "this" {
  for_each = var.replication_rules

  bucket = each.key
  role   = each.value.replication_role_arn

  dynamic "rule" {
    for_each = try(flatten([each.value.rules]), [])

    content {
      id       = rule.value.id
      priority = rule.value.priority
      status   = title(try(rule.value.status, "Enabled"))

      dynamic "delete_marker_replication" {
        for_each = [try(rule.value.delete_marker_replication, "Disabled")]
        content {
          status = title(delete_marker_replication.value) == "Enabled" ? "Enabled" : "Disabled"
        }
      }

      dynamic "source_selection_criteria" {
        for_each = try(rule.value.sse_kms_encrypted, null) != null ? [rule.value] : []
        content {
          dynamic "sse_kms_encrypted_objects" {
            for_each = try([source_selection_criteria.value.sse_kms_encrypted], [])
            content {
              status = sse_kms_encrypted_objects.value
            }
          }
        }
      }

      dynamic "destination" {
        for_each = [rule.value.destination]
        content {
          bucket  = destination.value.bucket_arn
          account = destination.value.account_id

          access_control_translation {
            owner = "Destination"
          }

          dynamic "encryption_configuration" {
            for_each = try(destination.value.kms_key_id, null) != null ? [destination.value.kms_key_id] : []
            content {
              replica_kms_key_id = encryption_configuration.value
            }
          }

          dynamic "replication_time" {
            for_each = title(try(destination.value.replication_time, "Enabled")) != "Disabled" ? [{ status = "Enabled", minutes = 15 }] : []
            content {
              status = replication_time.value.status
              time { minutes = replication_time.value.minutes }
            }
          }

          dynamic "metrics" {
            for_each = title(try(destination.value.metrics, "Enabled")) != "Disabled" ? [{ status = "Enabled", minutes = 15 }] : []
            content {
              status = metrics.value.status
              event_threshold { minutes = metrics.value.minutes }
            }
          }
        }
      }

      dynamic "filter" {
        for_each = [rule.value.filter_prefix]
        content {
          prefix = try(filter.value == "/" ? null : filter.value, null)
        }
      }
    }
  }
}
```

### Replication Rule Building in Locals

```hcl
locals {
  replication_config = {
    "${local.resource_name}" = {
      replication_role_arn = format("arn:aws:iam::%s:role/%s",
        var.account_id,
        lookup(local.replication_role_map, each.value.segment)
      )
      rules = [
        for i, r in flatten(concat([
          for rule in var.replication_rules : [
            for prefix in try(rule.filter_prefix, ["/"]) :
              merge(rule, {
                id            = "${md5(prefix)}_${rule.dest_bucket}_${prefix}"
                filter_prefix = prefix
              })
          ]
        ])) : {
          id                       = r.id
          status                   = try(r.status, "Enabled")
          priority                 = try(r.priority, i)
          delete_marker_replication = try(r.delete_marker_replication, "Disabled")
          sse_kms_encrypted        = try(r.sse_kms_encrypted, null)
          destination = {
            bucket_arn       = "arn:aws:s3:::${r.dest_bucket}"
            account_id       = lookup(lookup(var.account_map, try(r.dest_account, split("-", r.dest_bucket)[3])), var.environment)
            kms_key_id       = try(r.dest_kms_key_id, null)
            replication_time = try(r.replication_time, "Enabled")
            metrics          = try(r.metrics, "Enabled")
          }
          filter_prefix = r.filter_prefix
        }
      ]
    }
  }
}
```

---

## 5. Cross-Environment Guardrails

### Guardrail Structure

```hcl
locals {
  cross_env_guardrail = {
    allowed_types    = ["basic"]
    allowed_segments = ["appsconfig"]
    allowed_resources = ["appsconfig-table-metadata"]
    allowed_accounts = {
      "hubdata" = {
        "dev" = { "dataexpl" = ["prd"] }
        "stg" = { "dataexpl" = ["prd"] }
        "rvw" = { "dataexpl" = ["prd"] }
      }
      "infrasvc" = {
        "rvw" = { "dataexpl" = ["dev"] }
        "dev" = { "infrasvc" = ["rvw"] }
      }
    }
  }
}
```

### Applying Guardrails in Dynamic Blocks

```hcl
dynamic "rules" {
  for_each = try(length(config.value.cross_env_rules), 0) > 0 ? {
    for key, rule in config.value.cross_env_rules : key => rule if (
      contains(local.cross_env_guardrail.allowed_resources, each.key) &&
      lookup(local.cross_env_guardrail.allowed_accounts, var.account_name, null) != null &&
      lookup(local.cross_env_guardrail.allowed_accounts[var.account_name], var.environment, null) != null &&
      contains(
        local.cross_env_guardrail.allowed_accounts[var.account_name][var.environment][rule.target_account],
        rule.target_env
      )
    )
  } : {}

  content {
    // ... only creates rules that pass all guardrail checks
  }
}
```

---

## 6. Environment-Aware Account Grouping

When you need to group accounts by environment for per-env access control:

```hcl
locals {
  envs = ["dev", "rvw", "stg", "prd"]

  filtered_account_map = {
    for k, v in var.account_map : k => v
    if contains(var.allowed_accounts, k)
  }

  # Build per-env account ID lists
  env_account_map = {
    for env in local.envs :
    env => sort(distinct([
      for k, v in local.filtered_account_map :
      lookup(v, env, "")
      if lookup(v, env, "") != ""
    ]))
  }

  # Full flat list of all account IDs across all environments
  all_account_ids = sort(distinct(flatten([
    for env, ids in local.env_account_map : ids
  ])))
}
```

---

## 7. IAM Role Name Mapping

### Segment-Based Role Resolution

Map resource segments to IAM role names for replication, access, etc.:

```hcl
locals {
  role_name_map = {
    "isolated" = {
      "dataraw"   = "Isolated-S3-Svc-Replication"
      "dataclean" = "Isolated-S3-Svc-Replication"
      "databus"   = "Isolated-S3-Svc-Replication"
    }
    "standard" = {
      "dataraw"      = "S3-Svc-Dataraw-Replication"
      "dataclean"    = "S3-Svc-Dataclean-Replication"
      "databus"      = "S3-Svc-Databus-Replication"
      "appsconfig"   = "S3-Svc-Appsconfig-Replication"
      "appscontent"  = "S3-Svc-Appscontent-Replication"
    }
  }
}

# Resolve the role
role = join(":", [
  "arn", "aws", "iam", "", var.account_id,
  join("/", [
    "role",
    lookup(
      lookup(local.role_name_map, each.value.isolation_mode),
      split("-", each.key)[0]
    )
  ])
])
```

---

## 8. CloudFormation for VPC Endpoint Policy Stacking

AWS VPC endpoint policies can only be applied one-at-a-time and conflict when applied concurrently. Use CloudFormation stacks with dependency chaining:

```hcl
# Stack 1: Internal bucket access
resource "aws_cloudformation_stack" "vpc_ep_internal" {
  name          = "${var.project_name}-s3-allow-internal-${var.region_code}"
  template_body = file("${path.module}/templates/vpc_endpoint_policy.yaml.tmpl")
  on_failure    = "DELETE"
  parameters    = {
    BucketName = "${var.project_name}-${local.ac_short}-${var.environment}-${var.account_name}-*-${var.region_code}"
  }
}

# Stack 2: SSM agent access (depends on stack 1)
resource "aws_cloudformation_stack" "vpc_ep_ssm" {
  name          = "${var.project_name}-s3-allow-ssm-${var.region_code}"
  template_body = file("${path.module}/templates/vpc_endpoint_ssm.yaml.tmpl")
  on_failure    = "DELETE"
  depends_on    = [aws_cloudformation_stack.vpc_ep_internal]
}

# Stack 3: Cross-account access (depends on stack 2)
resource "aws_cloudformation_stack" "vpc_ep_cross_account" {
  name          = "${var.project_name}-x-s3-allow-${var.region_code}"
  template_body = file("${path.module}/templates/vpc_endpoint_policy.yaml.tmpl")
  on_failure    = "DELETE"
  parameters    = {
    BucketName = "${var.project_name}-*-${var.environment}-*"
  }
  depends_on = [aws_cloudformation_stack.vpc_ep_ssm]
}

# Stack 4: External bucket access (conditional, depends on stack 3)
resource "aws_cloudformation_stack" "vpc_ep_external" {
  count = (length(local.ext_rw_buckets) > 0 || length(local.ext_rw_access_points) > 0) ? 1 : 0
  name  = "${var.project_name}-ext-s3-access-${var.region_code}"
  template_body = templatefile("${path.module}/templates/vpc_ext_endpoint.yaml.tmpl", {
    actions       = local.ext_write_actions
    buckets       = local.ext_rw_buckets
    access_points = local.ext_rw_access_points
  })
  on_failure = "DELETE"
  depends_on = [aws_cloudformation_stack.vpc_ep_cross_account]
}
```
