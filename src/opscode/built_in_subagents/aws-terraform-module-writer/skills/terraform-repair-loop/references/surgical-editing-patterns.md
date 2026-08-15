# Surgical Code Editing Patterns for Terraform Remediation Turns

In an automated agent repair loop, **surgical editing** refers to applying targeted, minimal HCL modifications that fix specific validation/linting failures without causing collateral regressions or modifying unrelated code.

---

## Core Principles of Surgical Remediation

### 1. Scope Containment
- **Target Line Precision**: Edit only the specific lines flagged by `terraform validate` or `tflint`.
- **Avoid Global Re-writes**: Never re-create an entire `.tf` file to fix a single attribute error or missing variable.

### 2. AST and Formatting Integrity
- **Preserve Indentation**: Match standard HCL formatting (2 spaces).
- **Preserve Surrounding Comments**: Do not strip existing documentation or `# tfsec:ignore` comments.
- **Maintain Block Structure**: Ensure opening and closing braces remain balanced.

### 3. One Failure Category per Turn
- Do not attempt to fix unrelated linter warnings while resolving a blocking `terraform validate` syntax error.
- Fix compiler errors first (`terraform validate`), then linter errors (`tflint`).

---

## Surgical Pattern Anti-Patterns vs Best Practices

### Pattern A: Fixing an Unsupported Attribute

#### ❌ Anti-Pattern (Destructive / Cascading Edit)
```hcl
# Replacing entire resource block when only one attribute is invalid
# BEFORE:
resource "aws_s3_bucket" "logs" {
  bucket        = "my-app-logs-12345"
  acl           = "private"
  force_destroy = true
  tags          = local.common_tags
}

# BAD EDIT (re-wrote block, dropped force_destroy and tags):
resource "aws_s3_bucket" "logs" {
  bucket = "my-app-logs-12345"
}
```

#### ✅ Best Practice (Surgical Edit)
```hcl
# Locate target line (acl) and move deprecated argument to dedicated resource without touching surrounding attributes
# AFTER:
resource "aws_s3_bucket" "logs" {
  bucket        = "my-app-logs-12345"
  force_destroy = true
  tags          = local.common_tags
}

resource "aws_s3_bucket_ownership_controls" "logs" {
  bucket = aws_s3_bucket.logs.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}
```

---

### Pattern B: Adding a Missing Input Variable Declaration

#### ❌ Anti-Pattern
Inline editing `main.tf` and hardcoding a value instead of defining the declared parameter in `variables.tf`.

#### ✅ Best Practice
Append the minimal required variable declaration block to `variables.tf`:
```hcl
variable "environment" {
  type        = string
  description = "Deployment environment name (e.g. dev, prod)"
}
```

---

### Pattern C: Fixing Type Mismatches (String vs List)

#### Error
`Inappropriate value for attribute "subnet_ids": string required, list of string given.`

#### ✅ Surgical Fix
Change only the right-hand expression without replacing the variable or resource argument key:
```hcl
# Before
subnet_id = var.subnet_ids

# After (if subnet_id expects a single string)
subnet_id = var.subnet_ids[0]
```

---

## Self-Healing Turn Execution Workflow

```
┌─────────────────────────────────────────┐
│ 1. Capture Failure Output               │
│    (terraform validate / tflint)        │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ 2. Isolate Line & File Location         │
│    (file_path:line_number)              │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ 3. Select Minimal HCL Fix Pattern       │
│    (from error-catalog.md)              │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ 4. Apply Surgical Edit (edit_file)      │
│    (Exact string replacement)           │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ 5. Re-run Validation / Lint Check       │
│    (Verify error cleared, no new ones)  │
└─────────────────────────────────────────┘
```
