# Terraform & TFLint Error Catalog & Remediation Guide

This catalog provides diagnostic patterns and surgical remediation instructions for errors emitted by `terraform validate`, `terraform plan`, and `tflint`.

---

## 1. `terraform validate` Diagnostic Patterns

### 1.1 Syntax and HCL Parsing Errors

#### Error Pattern
```
Error: Unclosed configuration block
  on main.tf line 42, in resource "aws_s3_bucket" "example":
  42: resource "aws_s3_bucket" "example" {

There is no closing "}" for this block.
```
```
Error: Argument or block definition required
  on variables.tf line 12:
  12: variable "environment"

An argument or block definition is required here. To set an argument, use the equals sign "=" to introduce the argument value.
```

#### Diagnostic Strategy
- Identify exact file and line number from the error output.
- Check bracket/brace balance (`{}` and `[]`) in the specified block and adjacent blocks.
- Verify block headers have valid structure: `block_type "label1" "label2" { ... }`.

#### Surgical Remediation
- **Do not** re-write the entire file or resource block.
- Locate the target block boundaries and insert the missing closing brace or assignment operator directly at the line identified.

---

### 1.2 Undeclared Reference Errors

#### Error Pattern
```
Error: Reference to undeclared resource
  on main.tf line 18, in resource "aws_instance" "web":
  18:   subnet_id = aws_subnet.public.id

A managed resource "aws_subnet" "public" has not been declared in the root module.
```
```
Error: Reference to undeclared input variable
  on main.tf line 5, in resource "aws_vpc" "main":
  5:   cidr_block = var.vpc_cidr

An input variable with the name "vpc_cidr" has not been declared.
```

#### Diagnostic Strategy
1. **Typo check**: Search HCL files for similar resource or variable names (e.g. `aws_subnet.public_subnet` vs `aws_subnet.public`).
2. **Missing declaration**: Check if `var.vpc_cidr` exists in `variables.tf`.
3. **Plural vs Singular / Count mismatch**: Check if resource was declared with `count` or `for_each` (e.g., `aws_subnet.public[0].id` vs `aws_subnet.public.id`).

#### Surgical Remediation
- **If typo**: Fix the reference line to match the existing declaration name.
- **If missing variable**: Append the variable definition block to `variables.tf`:
  ```hcl
  variable "vpc_cidr" {
    type        = string
    description = "CIDR block for the VPC"
  }
  ```
- **If missing resource reference due to `count`/`for_each`**: Update reference to index or splat operator (`aws_subnet.public[0].id` or `aws_subnet.public[*].id`).

---

### 1.3 Unsupported Attribute & Schema Mismatches

#### Error Pattern
```
Error: Unsupported attribute
  on main.tf line 25, in resource "aws_instance" "web":
  25:   vpc_security_group_id = aws_security_group.web.id

This object has no argument, nested block, or exported attribute named "vpc_security_group_id". Did you mean "vpc_security_group_ids"?
```

#### Diagnostic Strategy
- Read the suggestion in Terraform output ("Did you mean...").
- Check AWS provider argument vs attribute naming:
  - `vpc_security_group_ids` (plural list) vs `vpc_security_group_id` (invalid singular on aws_instance).
  - Single block vs argument: e.g., `bucket` vs `bucket_prefix`.

#### Surgical Remediation
- Rename attribute directly at the target line without modifying other arguments in the block:
  ```hcl
  # Before
  vpc_security_group_id = [aws_security_group.web.id]
  # After
  vpc_security_group_ids = [aws_security_group.web.id]
  ```

---

### 1.4 Missing Required Arguments

#### Error Pattern
```
Error: Missing required argument
  on main.tf line 30, in resource "aws_s3_bucket_server_side_encryption_configuration" "example":
  30: resource "aws_s3_bucket_server_side_encryption_configuration" "example" {

The argument "bucket" is required, but no definition was found.
```

#### Diagnostic Strategy
- Extract required argument name from failure output (`bucket`).
- Determine source resource to link (e.g., `aws_s3_bucket.example.id`).

#### Surgical Remediation
- Add only the required argument line inside the block, preserving existing configuration:
  ```hcl
  resource "aws_s3_bucket_server_side_encryption_configuration" "example" {
    bucket = aws_s3_bucket.example.id
    # existing blocks preserved...
  }
  ```

---

### 1.5 Circular Dependencies (Cycles)

#### Error Pattern
```
Error: Cycle: aws_security_group_rule.ingress, aws_security_group.web, aws_security_group_rule.ingress
```

#### Diagnostic Strategy
- Trace cross-references between the listed resources.
- Common cause: Inline rules in `aws_security_group` combined with separate `aws_security_group_rule` resources referencing each other.

#### Surgical Remediation
- Decouple dependency: Remove inline `ingress`/`egress` blocks from `aws_security_group` and convert exclusively to standalone `aws_vpc_security_group_ingress_rule` / `aws_vpc_security_group_egress_rule` resources.

---

## 2. `tflint` Diagnostic Patterns & Rule Violations

### 2.1 Unused Declarations (`terraform_unused_declarations`)

#### Failure Output
```
Warning: variable "unused_var" is declared but not used (terraform_unused_declarations)
  on variables.tf line 15:
  15: variable "unused_var" {
```

#### Diagnostic & Remediation
- If variable is required by interface spec, wire it into a resource block.
- If redundant, remove the exact `variable "unused_var" { ... }` block cleanly without leaving dangling comments.

---

### 2.2 Deprecated Syntax (`terraform_deprecated_syntax` / AWS Rules)

#### Failure Output
```
Warning: "aws_s3_bucket" acl attribute is deprecated (aws_s3_bucket_deprecated_acl)
  on main.tf line 10:
  10:   acl = "private"
```

#### Diagnostic Strategy
- AWS provider v4+ deprecated monolithic `aws_s3_bucket` arguments (`acl`, `server_side_encryption_configuration`, `versioning`, `website`, `cors_rule`).

#### Surgical Remediation
- Remove deprecated attribute from `aws_s3_bucket`.
- Add separate resource block (e.g. `aws_s3_bucket_ownership_controls` and `aws_s3_bucket_acl`):
  ```hcl
  resource "aws_s3_bucket_ownership_controls" "example" {
    bucket = aws_s3_bucket.example.id
    rule {
      object_ownership = "BucketOwnerEnforced"
    }
  }
  ```

---

### 2.3 Invalid Module / Instance Types (`aws_instance_invalid_type`)

#### Failure Output
```
Error: "t2.micro" is an invalid instance type (aws_instance_invalid_type)
  on main.tf line 8:
  8:   instance_type = "t2.micro"
```

#### Remediation
- Update attribute string to valid instance type for region/architecture (e.g. `t3.micro` or `t4g.micro`).

---

## 3. General Remediation Protocol Matrix

| Error Type | Detection Command | Primary Root Cause | Surgical Fix Pattern |
|------------|-------------------|--------------------|----------------------|
| HCL Syntax | `terraform validate` | Missing brace/quote, illegal char | Line-level syntax adjustment |
| Reference Error | `terraform validate` | Typo or missing `variable`/`resource` | Align attribute name or declare missing block |
| Type Mismatch | `terraform validate` | String vs List, map vs object | Adjust data structure wrapper (`[...]` / `toset()`) |
| Deprecated Schema | `tflint` / `terraform plan` | Provider major version upgrade | Refactor into separate resource extension block |
| Invalid Variable Value | `tflint` | Schema condition / hardcoded illegal value | Parameterize or correct literal value |
