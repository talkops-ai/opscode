// ============================================================
// locals.tf — Data transformations, guardrails, ARN composition
// ============================================================
// Pattern: ALL data shaping happens here. Resources reference
// locals, never raw variable transformations inline.
// ============================================================

locals {
  // ---- Account Identity ----
  account_id = data.aws_caller_identity.current.account_id

  // ---- Resource Transformation ----
  // Normalize the primary input map, applying defaults via try()
  resources = {
    for key, spec in var.resource_list : key => {
      resource_name  = join("-", [var.project_name, substr(var.account_id, 8, 12), var.environment, var.account_name, key, var.region_code])
      segment        = split("-", key)[0]
      resource_type  = try(spec.resource_type, "basic")
      encryption_key = lookup(local.segment_kms_map, split("-", key)[0], null)
      versioning     = try(spec.versioning, true)
      rules_enabled  = try(spec.lifecycle_enabled, true)
      expiration_days        = try(spec.expiration_days, null)
      feature_enabled        = try(spec.feature_enabled, false)
      cross_account_roles    = try(spec.cross_account_roles, [])
      cross_account_users    = try(spec.cross_account_users, [])
      trusted_aws_services   = try(spec.trusted_aws_services, local.default_service_principals)
      trusted_aws_roles      = try(spec.trusted_aws_roles, [])
      custom_tags            = try(spec.tags, {})
    }
  }

  // ---- Segment-Based Mappings ----
  // Map resource segments to encryption keys, roles, tags, etc.
  segment_kms_map = {
    "infra" = "project-infra-key"
    "apps"  = "project-apps-key"
    "data"  = "project-data-key"
    // Add segments as needed
  }

  segment_tag_map = {
    "infra" = "infrastructure"
    "apps"  = "application"
    "data"  = "data-platform"
  }

  // ---- Default Principals ----
  default_service_principals = ["s3.amazonaws.com"]
  root_principal             = ["arn:aws:iam::${local.account_id}:root"]
  role_arn_prefix            = "arn:aws:iam::${local.account_id}:"

  // ---- Defaults Merging ----
  // Merge user-provided config with organization defaults
  default_grant_roles = [
    "arn:aws:iam::${local.account_id}:role/Infra-Provisioner",
    "arn:aws:iam::${local.account_id}:role/Admin-IAM",
  ]

  default_grant_services = [
    "rds.*.amazonaws.com",
    "eks.*.amazonaws.com",
    "lambda.*.amazonaws.com",
  ]

  merged_grant_config = {
    for key, value in var.resource_list : key => {
      grant_roles = distinct(concat(
        try(value.custom_grant_roles, []),
        local.default_grant_roles
      ))
      grant_services = distinct(concat(
        try(value.custom_grant_services, []),
        local.default_grant_services
      ))
    }
  }

  // ---- Guardrails ----
  guardrail = {
    allowed_types    = ["basic", "premium", "external"]
    allowed_segments = ["infra", "apps", "data"]
    // Add account/environment guardrails as needed
  }

  // ---- Flattening Nested Structures ----
  // Convert nested list-of-objects to flat maps for for_each
  flat_metrics = flatten([
    for k, v in var.resource_list : [
      for metric in try(v.metrics_prefix, []) : {
        resource_key  = k
        resource_name = local.resources[k].resource_name
        metric_name   = metric.name
        metric_prefix = metric.prefix
      }
    ]
  ])

  // ---- Cross-Account ARN Resolution ----
  // Resolve account_name/role references to full ARNs
  // See references/cross_account_patterns.md for details

  // ---- Central Tagging Map ----
  sub_env = {
    prd = "pp"
    dev = "dd"
    stg = "ss"
    rvw = "rr"
  }

  tagging_map = {
    for key, value in var.resource_list : key => {
      "standard_tags" = {
        financial_tags = lookup(value, "financial_tags", null)
        common_tags = {
          "automation"  = "terraform"
          "unique_name" = key
          "region"      = var.region_code
          "sub_env"     = lookup(local.sub_env, var.environment, var.environment)
          "cost_track"  = lookup(local.segment_tag_map, split("-", key)[0], split("-", key)[0])
        }
      }
    }
  }
}

// ** END ** //
