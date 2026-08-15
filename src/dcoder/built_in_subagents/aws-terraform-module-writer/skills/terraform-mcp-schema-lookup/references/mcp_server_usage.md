# Using terraform-mcp-server for AWS Module Development

The `terraform-mcp-server` provides real-time access to Terraform provider documentation, resource schemas, argument specifications, and module registry metadata. Using `terraform-mcp-server` ensures all generated Terraform configurations strictly adhere to the exact AWS provider schema without guessing argument names or types.

---

## Key Capabilities & Workflows

### 1. Schema & Argument Inspection
Before writing any AWS resource configuration (e.g., `aws_s3_bucket`, `aws_vpc`, `aws_iam_role`), query the MCP server to inspect the resource schema:
- **Resource Search / Schema Lookup**: Search for AWS provider resources by name or keyword.
- **Argument Verification**: Verify required arguments, optional arguments, nested block structures, and default values.
- **Type Checking**: Confirm exact data types (e.g. `list(string)`, `map(string)`, `bool`, `object(...)`).

### 2. Attribute Export Verification
- Check resource attributes exported after creation (e.g., `.arn`, `.id`, `.endpoint`) to ensure `outputs.tf` references valid attributes.

### 3. Documentation & Deprecation Checks
- **Deprecation Warnings**: Check if a resource or argument is deprecated (e.g., inline `server_side_encryption_configuration` on `aws_s3_bucket` vs `aws_s3_bucket_server_side_encryption_configuration` resource).
- **AWS Provider V5 Updates**: Ensure usage conforms to AWS Provider v5+ breaking changes and resource separations.

---

## Recommended Step-by-Step Workflow

1. **Identify Required Resources**: List all AWS resources needed for the module (e.g., `aws_s3_bucket`, `aws_s3_bucket_versioning`, `aws_s3_bucket_public_access_block`, `aws_kms_key`).
2. **Query MCP Server**: Look up each resource schema to confirm:
   - Required vs. optional top-level arguments
   - Proper usage of child resources vs. inline blocks (e.g., S3 policies, lifecycle rules, bucket logging)
3. **Draft HCL**: Write Terraform code adhering to schema specifications.
4. **Verify References**: Confirm that attributes referenced in `outputs.tf` or cross-resource dependencies exist in the schema.
