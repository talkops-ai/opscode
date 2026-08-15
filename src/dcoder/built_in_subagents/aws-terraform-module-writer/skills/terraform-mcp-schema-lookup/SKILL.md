---
name: terraform-mcp-schema-lookup
description: >
  Workflow for querying terraform-mcp-server to inspect AWS provider resource schemas,
  verify required vs optional arguments, check exported attributes, and detect deprecated
  arguments before writing or editing Terraform HCL code. Use when: (1) writing any new
  AWS resource block and need to confirm exact argument names and types, (2) adding outputs
  and need to verify exported resource attributes (.arn, .id, .endpoint), (3) checking
  whether an argument or inline block is deprecated in AWS Provider v5+, (4) verifying
  nested block structures and default values, or (5) resolving Terraform validation errors
  caused by incorrect argument names or types. Do NOT use for non-AWS providers (GCP, Azure),
  Terraform state operations, or CI/CD pipeline configuration.
license: MIT
compatibility: designed for deepagents-code
---

# Terraform MCP Schema Lookup

Query `terraform-mcp-server` for real-time provider schema inspection before writing or editing any AWS Terraform resource. This ensures generated configurations strictly adhere to the exact provider schema without guessing argument names, types, or deprecated usage.

---

## Core Principles

1. **Schema-First**: Never write an AWS resource block without first querying the MCP server for its schema. Guessing argument names leads to `terraform validate` failures.
2. **Attribute Verification**: Before adding outputs to `outputs.tf`, verify that the exported attributes actually exist in the resource schema.
3. **Deprecation Awareness**: Always check for deprecated arguments and AWS Provider v5+ resource separations (e.g., inline `versioning {}` → standalone `aws_s3_bucket_versioning`).
4. **Type Safety**: Confirm exact data types (`list(string)`, `map(string)`, `bool`, `object(...)`) to avoid type mismatch errors.

---

## Execution Workflow

### Step 1: Identify Required Resources

List all AWS resources needed for the module. For example, an S3 module might need:
- `aws_s3_bucket`
- `aws_s3_bucket_versioning`
- `aws_s3_bucket_server_side_encryption_configuration`
- `aws_s3_bucket_public_access_block`
- `aws_s3_bucket_policy`
- `aws_kms_key`

### Step 2: Query MCP Server for Each Resource Schema

For each resource, query `terraform-mcp-server` to inspect:

1. **Resource Search / Schema Lookup**: Search for AWS provider resources by exact name (e.g., `aws_s3_bucket`, `aws_vpc`, `aws_iam_role`).
2. **Required Arguments**: Identify mandatory fields that must be specified.
3. **Optional Arguments**: Identify optional fields with their defaults.
4. **Nested Block Structures**: Understand which arguments are nested blocks vs simple attributes.
5. **Type Checking**: Confirm data types — `list(string)`, `map(string)`, `bool`, `object(...)`.

### Step 3: Check Deprecations & Breaking Changes

Before using any argument or inline block:

- **Deprecated Arguments**: Check if the argument is deprecated. Common examples:
  - S3: Inline `server_side_encryption_configuration {}` → use `aws_s3_bucket_server_side_encryption_configuration`
  - S3: Inline `versioning {}` → use `aws_s3_bucket_versioning`
  - S3: Inline `lifecycle_rule {}` → use `aws_s3_bucket_lifecycle_configuration`
  - S3: Inline `logging {}` → use `aws_s3_bucket_logging`
  - S3: Inline `policy = ...` → use `aws_s3_bucket_policy`
  - IAM: Inline `inline_policy {}` → use dedicated `aws_iam_role_policy` attachments

- **AWS Provider v5+ Updates**: Verify usage conforms to Provider v5+ breaking changes and resource separations.

### Step 4: Verify Exported Attributes for Outputs

Before adding any output to `outputs.tf`, query the schema to confirm the attribute is exported:

- Common exports: `.arn`, `.id`, `.endpoint`, `.domain_name`, `.hosted_zone_id`
- Verify the exact attribute name (e.g., `arn` vs `key_arn`, `id` vs `key_id`)

### Step 5: Draft & Validate HCL

Write Terraform code adhering to the verified schema, then run `terraform validate` to confirm correctness.

For detailed MCP query patterns and examples, see [references/mcp_server_usage.md](references/mcp_server_usage.md).

---

## Quick Reference Map

| Workflow Step | What to Check | MCP Query |
|---|---|---|
| **Schema Lookup** | Full resource schema | Search by resource name (e.g., `aws_s3_bucket`) |
| **Argument Verification** | Required vs optional fields | Read resource argument specs |
| **Type Checking** | Data types, nested blocks | Inspect argument type definitions |
| **Deprecation Check** | Deprecated args, v5 changes | Check deprecation warnings in schema |
| **Output Verification** | Exported attributes | Read resource attribute exports |
