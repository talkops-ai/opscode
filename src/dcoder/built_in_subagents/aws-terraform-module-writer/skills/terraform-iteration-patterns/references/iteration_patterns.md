# Iteration & Dynamic Block Patterns

This reference covers all iteration, transformation, and validation patterns used in production Terraform modules. These patterns are service-agnostic.

---

## 1. Map-Driven `for_each`

### Primary Resource Pattern

The top-level resource always iterates over the primary map variable:

```hcl
resource "aws_kms_key" "this" {
  for_each = length(var.key_list) > 0 ? var.key_list : {}

  description             = "Encryption KMS key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  key_usage               = "ENCRYPT_DECRYPT"

  tags       = module.tagging[each.key].output_tags
  depends_on = [module.tagging]
}
```

### Companion Resource Pattern

Companion resources (aliases, policies, configurations) iterate over the same map or the parent resource:

```hcl
resource "aws_kms_alias" "this" {
  for_each      = aws_kms_key.this
  name          = "alias/${each.key}"
  target_key_id = aws_kms_key.this[each.key].key_id
  depends_on    = [aws_kms_key.this]
}
```

---

## 2. Filtered `for_each`

### Simple Filter

Create resources only when a condition is true:

```hcl
resource "aws_s3_bucket_public_access_block" "this" {
  for_each = { for k, v in var.resource_list : k => v if try(v.block_public_access, true) }
  bucket   = each.value.name
  // ...
}
```

### Multi-Condition Filter

Combine multiple filter conditions:

```hcl
resource "aws_s3_bucket_logging" "this" {
  for_each = { for k, v in local.resources : k => v if v.logging_enabled && v.environment != "dev" }
  // ...
}
```

### Segment-Based Filter

Filter based on extracting the segment from the resource key:

```hcl
locals {
  pii_resources = flatten([
    for k, v in var.resource_list : [
      for item in v.access_points : {
        // ...
      }
    ] if split("-", k)[0] == "piidata" && v.resource_type == "pii"
  ])
}
```

---

## 3. Flattening Nested Structures

### List of Objects from Map of Lists

Convert a map containing nested lists into a flat list for `for_each`:

```hcl
locals {
  flat_metrics = flatten([
    for k, v in var.resource_list : [
      for metric in v.metrics_prefix : {
        resource_name = k
        metric_name   = metric.name
        metric_prefix = metric.prefix
      }
    ]
  ])
}

resource "aws_s3_bucket_metric" "this" {
  for_each = {
    for item in local.flat_metrics : "${item.resource_name}-${item.metric_prefix}" => item
  }
  bucket = each.value.resource_name
  name   = each.value.metric_name
  filter {
    prefix = each.value.metric_prefix
  }
}
```

### Double-Nested Flattening

For structures like resources → sub-resources → items:

```hcl
locals {
  flat_rules = flatten([
    for resource_key, resource in var.resource_list : [
      for dest in resource.destinations : [
        for rule_key, rule in dest.rules : {
          resource_key = resource_key
          dest_key     = rule_key
          dest_bucket  = rule.destination_bucket
          priority     = index(sort(keys(dest.rules)), rule_key)
          // ...
        }
      ]
    ]
  ])
}
```

### Flatten + Filter Combo

```hcl
locals {
  ext_access_points = flatten([
    for k, v in var.resource_list : [
      for ap in v.access_points : {
        resource_key = k
        vendor       = ap.vendor
        iam_arns     = distinct(compact(concat(ap.ext_iam_arns)))
        read_paths   = distinct(compact(concat(try(ap.allow_paths.read, []))))
        write_paths  = distinct(compact(concat(try(ap.allow_paths.write, []))))
      }
    ] if v.resource_type == "external_access"
  ])
}
```

---

## 4. Dynamic Blocks

### Conditional Dynamic Block (Toggle Feature)

Enable/disable an entire block based on a boolean:

```hcl
dynamic "lifecycle_rule" {
  for_each = each.value.lifecycle_enabled ? [true] : []
  content {
    enabled = true
    // ...
  }
}
```

### Iterated Dynamic Block

Create multiple instances of a nested block:

```hcl
dynamic "cors_rule" {
  for_each = each.value.cors_rules
  content {
    allowed_methods = cors_rule.value.allowed_methods
    allowed_origins = cors_rule.value.allowed_origins
    allowed_headers = cors_rule.value.allowed_headers
    expose_headers  = cors_rule.value.expose_headers
    max_age_seconds = cors_rule.value.max_age_seconds
  }
}
```

### Nested Dynamic Blocks

Dynamic blocks inside dynamic blocks:

```hcl
dynamic "replication_configuration" {
  for_each = each.value.destinations
  content {
    role = local.replication_role_arn

    dynamic "rules" {
      for_each = try(replication_configuration.value.rule_list, {})
      content {
        id     = rules.key
        status = "Enabled"
        destination {
          bucket     = rules.value.dest_bucket_arn
          account_id = rules.value.dest_account_id
          access_control_translation {
            owner = "Destination"
          }
        }
        source_selection_criteria {
          sse_kms_encrypted_objects {
            enabled = true
          }
        }
      }
    }
  }
}
```

### Conditional Content Inside Dynamic Block

```hcl
dynamic "expiration" {
  for_each = try(each.value.object_expiration_days, null) != null ? [true] : []
  content {
    days = each.value.object_expiration_days
  }
}

dynamic "noncurrent_version_expiration" {
  for_each = try(each.value.noncurrent_version_days, null) != null ? [true] : []
  content {
    days = each.value.noncurrent_version_days
  }
}
```

---

## 5. ARN Composition Patterns

### Basic ARN from Parts

```hcl
locals {
  role_arn = join(":", [
    "arn", "aws", "iam", "", var.account_id,
    join("/", ["role", lookup(local.role_map, each.value.segment)])
  ])
}
```

### Cross-Account ARN Resolution

Resolve human-readable account references to full ARNs:

```hcl
locals {
  resolved_arns = [
    for ref in each.value.cross_account_refs :
      can(regex("^arn:aws:", ref))
      ? ref                    # Already a full ARN, pass through
      : reverse(split("/", ref))[0] != "root"
        ? format("arn:aws:iam::%s:role/%s",
            lookup(lookup(var.account_map, split("/", ref)[0]), var.environment),
            join("/", slice(split("/", ref), 1, length(split("/", ref))))
          )
        : format("arn:aws:iam::%s:root",
            lookup(lookup(var.account_map, split("/", ref)[0]), var.environment)
          )
  ]
}
```

### Batch ARN Generation with `formatlist()`

```hcl
locals {
  account_root_arns = formatlist("arn:aws:iam::%s:root", local.account_id_list)
  replication_role_arns = formatlist(
    "arn:aws:iam::%s:role/${local.replication_role_name}",
    [for acct in local.source_accounts : lookup(lookup(var.account_map, acct), var.environment)]
  )
}
```

---

## 6. Safe Access with `try()` and `can()`

### Default Values for Optional Attributes

```hcl
locals {
  resources = {
    for k, v in var.resource_list : k => {
      name               = v.name
      type               = try(v.resource_type, "basic")       # Default to "basic"
      versioning_enabled = try(v.versioning, true)              # Default to true
      lifecycle_enabled  = try(v.lifecycle_enabled, true)       # Default to true
      custom_tags        = try(v.tags, {})                      # Default to empty map
      access_points      = try(v.access_points, [])             # Default to empty list
      expiration_days    = try(v.expiration.days, null)          # Nested default
      bucket_key_enabled = try(v.bucket_key_enabled, true)      # Default to true
    }
  }
}
```

### Conditional Logic with `can()`

```hcl
# Check if a string matches a regex
can(regex("^(prefix-elb-accesslogs){1}.*$", each.key))

# Check if an attribute exists in a nested structure
can(v.access_points)

# Use with ternary for conditional values
name = can(regex("^iceberg-", k)) ? "${var.project_name}-${k}-${var.env}" : "${var.project_name}-${k}"
```

---

## 7. Guardrail Validation Patterns

### Guardrail Maps

Define allowed combinations in locals:

```hcl
locals {
  guardrail = {
    allowed_types    = ["basic", "premium", "external"]
    allowed_segments = ["data", "infra", "apps", "platform"]
    allowed_accounts = {
      "hubdata" = {
        "prd" = { "hubdata" = ["stg"], "hubdata2" = ["stg"] }
        "rvw" = { "hubdata" = ["dev"], "dataexpl" = ["dev"] }
      }
    }
  }
}
```

### Plan-Time Failure with `filemd5()`

Force a plan failure with a descriptive error message. This works because `filemd5()` fails when the "file path" (actually an error message) doesn't exist:

```hcl
for_each = {
  for k, v in var.resources : k => v
  if (
    contains(local.guardrail.allowed_segments, split("-", k)[0])
    ? true
    : filemd5("\n==> FAIL: GUARDRAIL CHECK: Segment '${split("-", k)[0]}' not allowed for resource '${k}'.\n Allowed: ${join(", ", local.guardrail.allowed_segments)}")
  )
}
```

### Chained Guardrail Checks

Use `&&` to chain multiple guardrail conditions:

```hcl
locals {
  validated_items = flatten([
    for k, v in var.resources : [
      for item in v.items : item
      if can(item.account)
      && (contains(local.guardrail.allowed_accounts[var.account_name][var.environment][item.account], item.env)
          ? true
          : filemd5("\n==> FAIL: Account access not allowed: ${item.account}-${item.env}"))
      && (contains(local.guardrail.allowed_segments, split("-", k)[0])
          ? true
          : filemd5("\n==> FAIL: Segment not allowed: ${split("-", k)[0]}"))
      && (contains(local.guardrail.allowed_types, v.type)
          ? true
          : filemd5("\n==> FAIL: Type not allowed: ${v.type}"))
    ] if length(try(v.items, [])) > 0
  ])
}
```

---

## 8. Defaults Merging Pattern

### Merge User Inputs with Organization Defaults

```hcl
locals {
  org_defaults = {
    create_grant_roles = [
      "arn:aws:iam::${local.account_id}:role/Infra-Provisioner",
      "arn:aws:iam::${local.account_id}:role/Admin-IAM",
      "arn:aws:iam::${local.account_id}:role/EKS-*-EBS-CSI-Driver-Role"
    ]
    create_grant_services = [
      "rds.*.amazonaws.com",
      "eks.*.amazonaws.com",
      "elasticache.*.amazonaws.com",
      "lambda.*.amazonaws.com"
    ]
  }

  merged_config = {
    for key, value in var.resource_list : key => {
      grant_roles = distinct(concat(
        try(value.custom_grant_roles, []),
        local.org_defaults.create_grant_roles
      ))
      grant_services = distinct(concat(
        try(value.custom_grant_services, []),
        local.org_defaults.create_grant_services
      ))
    }
  }
}
```

---

## 9. VPC Endpoint Policy Stacking

When VPC endpoint policies need multiple stacks (internal, cross-account, external, SSM agent), use CloudFormation stacks with `depends_on` chaining:

```hcl
resource "aws_cloudformation_stack" "vpc_ep_internal" {
  name          = join("-", [var.project_name, "s3-internal", var.region_code])
  template_body = file("${path.module}/templates/vpc_endpoint.yaml.tmpl")
  on_failure    = "DELETE"
  parameters    = { BucketName = "${var.project_name}-*" }
}

resource "aws_cloudformation_stack" "vpc_ep_cross_account" {
  name          = join("-", [var.project_name, "s3-cross-account", var.region_code])
  template_body = file("${path.module}/templates/vpc_endpoint.yaml.tmpl")
  on_failure    = "DELETE"
  parameters    = { BucketName = "${var.project_name}-*-${var.environment}-*" }
  depends_on    = [aws_cloudformation_stack.vpc_ep_internal]
}

resource "aws_cloudformation_stack" "vpc_ep_external" {
  count = length(local.ext_buckets) > 0 ? 1 : 0
  name  = join("-", [var.project_name, "s3-external", var.region_code])
  template_body = templatefile("${path.module}/templates/vpc_ext_endpoint.yaml.tmpl", {
    actions       = local.ext_write_actions
    buckets       = local.ext_rw_buckets
    access_points = local.ext_rw_access_points
  })
  on_failure = "DELETE"
  depends_on = [aws_cloudformation_stack.vpc_ep_cross_account]
}
```

The `depends_on` chain ensures CloudFormation stacks are applied in order, avoiding VPC endpoint policy conflicts.

---

## 10. Event Notification Patterns

### Multi-Target Event Notifications

```hcl
resource "aws_s3_bucket_notification" "this" {
  for_each = local.resources_with_notifications
  bucket   = each.value.name

  dynamic "lambda_function" {
    for_each = [
      for k, v in each.value.event_notifications : merge(v, {
        key          = k
        function_arn = can(regex("^arn:aws:lambda:", v.function_name))
          ? v.function_name
          : "arn:aws:lambda:${var.region}:${var.account_id}:function:${v.function_name}"
      }) if try(v.function_name, null) != null
    ]
    content {
      id                  = "lambda_${lambda_function.value.function_name}_${lambda_function.value.key}"
      lambda_function_arn = lambda_function.value.function_arn
      events              = lambda_function.value.events
      filter_prefix       = try(lambda_function.value.filter_prefix, null)
      filter_suffix       = try(lambda_function.value.filter_suffix, null)
    }
  }

  dynamic "queue" {
    for_each = [
      for k, v in each.value.event_notifications : merge(v, {
        key       = k
        queue_arn = can(regex("^arn:aws:sqs:", v.queue_name))
          ? v.queue_name
          : "arn:aws:sqs:${var.region}:${var.account_id}:${v.queue_name}"
      }) if try(v.queue_name, null) != null
    ]
    content {
      id        = "sqs_${queue.value.queue_name}_${queue.value.key}"
      queue_arn = queue.value.queue_arn
      events    = queue.value.events
    }
  }
}
```
