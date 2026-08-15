---
name: terraform-iteration-patterns
description: >
  HCL iteration, transformation, and validation patterns for production Terraform modules.
  Covers map-driven for_each, flatten() for nested structures, dynamic blocks (conditional,
  iterated, nested), filtered for_each, ARN composition (join, lookup, formatlist),
  safe access with try()/can(), guardrail maps with plan-time filemd5() validation,
  locals as a data transformation layer, defaults merging, and event notification patterns.
  Use when: (1) authoring resources that iterate over map(any) inputs, (2) flattening
  nested list-of-objects into for_each-compatible maps, (3) implementing dynamic blocks
  with conditional rendering, (4) composing ARNs dynamically from account maps,
  (5) building guardrail validation that fails at plan time, (6) writing locals.tf
  transformations for data shaping, or (7) implementing defaults merging patterns.
  Do NOT use for module file layout (use terraform-module-layout), IAM policy construction
  (use aws-iam-policy-engine), or security enforcement (use aws-data-security-enforcement).
license: MIT
compatibility: designed for deepagents-code
---

# Terraform Iteration & Dynamic Patterns

Production-grade HCL iteration, transformation, and validation patterns for Terraform modules. These patterns are **service-agnostic** and apply to any AWS resource module.

---

## Core Principles

1. **Map-driven `for_each`**: Primary resources iterate over a `map(any)` variable. Each map key is a unique resource identifier. Never use `count` for resources that may be reordered.
2. **Locals as transformation layer**: All data shaping — flattening nested lists, composing ARNs, building lookup maps, applying guardrails — happens in `locals.tf`. Resources reference locals, never raw variable transformations inline.
3. **Guardrails at plan time**: Enforce input validation using locals-based guardrail maps that fail `terraform plan` with descriptive error messages, before any infrastructure is touched.
4. **Safe access defaults**: Use `try()` for optional attributes with fallback values and `can()` for conditional logic. Never let a missing optional attribute cause a plan failure.

---

## Execution Workflow

When implementing resource iteration or data transformation in a Terraform module, follow these steps:

### Step 1: Design the Map-Driven Variable

Define the primary `map(any)` input variable where each key represents a unique resource instance. All resource configuration for that instance lives as attributes within the map value.

```hcl
resource "aws_resource" "this" {
  for_each = var.resource_map    // map(any) - each key is unique name
  name     = each.value.name
  // ...
}
```

Companion resources iterate over the same map or the parent resource:

```hcl
resource "aws_kms_alias" "this" {
  for_each      = aws_kms_key.this
  name          = "alias/${each.key}"
  target_key_id = aws_kms_key.this[each.key].key_id
}
```

### Step 2: Build Locals for Data Transformation

Shape raw inputs into resource-ready structures in `locals.tf`:

- **Default values**: Use `try()` to supply defaults for optional attributes.
- **Flattening**: Convert nested list-of-objects into flat maps for `for_each`.
- **ARN composition**: Build ARNs from account maps, segments, and role names.
- **Segment mapping**: Map resource key prefixes to configuration values.

```hcl
locals {
  resources = {
    for k, v in var.resource_list : k => {
      name               = v.name
      type               = try(v.resource_type, "basic")
      versioning_enabled = try(v.versioning, true)
      custom_tags        = try(v.tags, {})
      access_points      = try(v.access_points, [])
    }
  }
}
```

For complete transformation patterns including flattening, ARN composition, segment mapping, and defaults merging, see [references/iteration_patterns.md](references/iteration_patterns.md).

---

### Step 3: Apply Filtered `for_each` and Dynamic Blocks

Use filtered `for_each` to conditionally create resources:

```hcl
resource "aws_resource" "filtered" {
  for_each = { for k, v in var.resource_map : k => v if v.feature_enabled }
}
```

Use dynamic blocks with conditional rendering:

```hcl
dynamic "block_name" {
  for_each = each.value.feature_enabled ? [true] : []
  content {
    // block content only rendered when enabled
  }
}
```

For iterated, nested, and conditional dynamic block patterns, see [references/iteration_patterns.md](references/iteration_patterns.md).

---

### Step 4: Implement Guardrail Validation

Define allowed values in guardrail maps:

```hcl
locals {
  guardrail = {
    allowed_types    = ["basic", "premium"]
    allowed_segments = ["data", "infra", "apps"]
    allowed_accounts = {
      "account_a" = {
        "prd" = { "account_b" = ["stg", "prd"] }
      }
    }
  }
}
```

Enforce guardrails at plan time using the `filemd5()` technique — it fails with a descriptive error message when the "file path" (actually the error message) doesn't exist:

```hcl
for_each = {
  for k, v in var.resources : k => v
  if (
    contains(local.guardrail.allowed_types, v.type)
    ? true
    : filemd5("\n==> FAIL: type '${v.type}' not allowed for '${k}'")
  )
}
```

Chain multiple guardrail checks with `&&` operators. Use `can()` and `try()` for graceful fallbacks on optional attribute checking.

For chained guardrails, cross-environment guardrails, and complete validation patterns, see [references/iteration_patterns.md](references/iteration_patterns.md).

---

## Quick Reference Map

| Pattern Domain | Reference Document | Key Concepts |
|---|---|---|
| **Map-driven for_each** | [iteration_patterns.md](references/iteration_patterns.md) §1-§2 | Primary resource, companion resource, simple/multi-condition/segment filters |
| **Flattening** | [iteration_patterns.md](references/iteration_patterns.md) §3 | Single/double nested `flatten()`, flatten+filter combos |
| **Dynamic Blocks** | [iteration_patterns.md](references/iteration_patterns.md) §4 | Conditional toggle, iterated, nested, conditional content |
| **ARN Composition** | [iteration_patterns.md](references/iteration_patterns.md) §5 | `join()`, `lookup()`, `formatlist()`, cross-account ARN resolution |
| **Safe Access** | [iteration_patterns.md](references/iteration_patterns.md) §6 | `try()` defaults, `can()` conditionals |
| **Guardrails** | [iteration_patterns.md](references/iteration_patterns.md) §7 | Guardrail maps, `filemd5()` plan-time failure, chained checks |
| **Defaults Merging** | [iteration_patterns.md](references/iteration_patterns.md) §8 | Org defaults + user input merging |
| **VPC Endpoint Stacking** | [iteration_patterns.md](references/iteration_patterns.md) §9 | CloudFormation stack dependency chaining |
| **Event Notifications** | [iteration_patterns.md](references/iteration_patterns.md) §10 | Multi-target Lambda/SQS dynamic notifications |
