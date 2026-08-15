# Constructing HCL Policy Documents in Terraform

## Why Use `aws_iam_policy_document` Over Raw JSON

When authoring Terraform code for AWS service policies, **always use the `aws_iam_policy_document` data source** instead of raw JSON strings, `jsonencode()`, or heredoc template files (`templatefile`).

### Advantages of HCL Data Sources
1. **Type Checking & Linting**: Terraform validates policy structure (actions, principals, condition block syntax) at `terraform plan` time.
2. **Composability**: Native merging of base policies and custom overrides using `source_policy_documents` and `override_policy_documents`.
3. **Dynamic Logic**: Full support for `dynamic "statement"` and `dynamic "condition"` blocks driven by module variables.
4. **Refactoring Safety**: Terraform automatically handles ARN references (`aws_s3_bucket.this.arn`) without string interpolation errors.

---

## Basic Policy Document Structure

```hcl
data "aws_iam_policy_document" "example" {
  statement {
    sid    = "AllowSpecificActions"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [var.principal_arn]
    }

    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]

    resources = [
      "${aws_s3_bucket.this.arn}/*",
    ]

    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms"]
    }
  }
}
```

---

## HCL Composability: Merging and Overriding Policies

Terraform allows combining multiple policy documents using `source_policy_documents` and `override_policy_documents`.

### 1. Combining Base + Supplemental Policies (`source_policy_documents`)
Appends statements from external documents into a single resulting JSON policy.

```hcl
data "aws_iam_policy_document" "combined" {
  source_policy_documents = [
    data.aws_iam_policy_document.base_s3_policy.json,
    data.aws_iam_policy_document.ssl_enforcement_policy.json,
  ]
}
```

### 2. Overriding Existing Statements (`override_policy_documents`)
Replaces or overrides statements matching the same `sid`.

```hcl
data "aws_iam_policy_document" "customized" {
  source_policy_documents = [
    data.aws_iam_policy_document.base_policy.json
  ]

  override_policy_documents = [
    data.aws_iam_policy_document.custom_override.json
  ]
}
```

---

## Dynamic Statement Construction (`dynamic "statement"`)

Use HCL `dynamic "statement"` blocks to conditionally include policy statements based on input variables.

### Example: Conditional Policy Statements
```hcl
variable "enable_cross_account_access" {
  type    = bool
  default = false
}

variable "cross_account_arns" {
  type    = list(string)
  default = []
}

data "aws_iam_policy_document" "dynamic_s3_policy" {
  # Base SSL enforcement statement (always present)
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions   = ["s3:*"]
    resources = [aws_s3_bucket.this.arn, "${aws_s3_bucket.this.arn}/*"]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  # Conditionally added cross-account read statement
  dynamic "statement" {
    for_each = var.enable_cross_account_access && length(var.cross_account_arns) > 0 ? [1] : []

    content {
      sid    = "AllowCrossAccountRead"
      effect = "Allow"

      principals {
        type        = "AWS"
        identifiers = var.cross_account_arns
      }

      actions = [
        "s3:GetObject",
        "s3:ListBucket",
      ]

      resources = [
        aws_s3_bucket.this.arn,
        "${aws_s3_bucket.this.arn}/*",
      ]
    }
  }
}
```

---

## Condition Block Operators & Type Reference

Always pair the correct condition evaluation operator with the target variable type:

| Operator | Use Case | Target Variable Example |
|---|---|---|
| `StringEquals` / `StringNotEquals` | Exact string match | `aws:PrincipalAccount`, `s3:x-amz-server-side-encryption` |
| `StringLike` / `StringNotLike` | Wildcard match | `aws:PrincipalArn`, `aws:RequestTag/*` |
| `ArnEquals` / `ArnLike` | Amazon Resource Name matching | `aws:SourceArn` |
| `Bool` | Boolean comparison (`"true"` / `"false"`) | `aws:SecureTransport`, `aws:ViaAWSService` |
| `Null` | Check key presence in request | `s3:x-amz-server-side-encryption` |
| `NumericEquals` / `NumericLessThan` | TLS version, IP limits | `aws:MultiFactorAuthAge` |

### Multi-Value Modifiers
- `ForAnyValue:StringEquals`: True if any entry in request key matches any specified value.
- `ForAllValues:StringEquals`: True if every entry in request key matches specified values.
