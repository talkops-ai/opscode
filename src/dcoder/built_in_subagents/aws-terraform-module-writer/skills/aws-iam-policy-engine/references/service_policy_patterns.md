# Service-Specific Resource Policy Production Patterns

This reference contains production-grade HCL examples using `aws_iam_policy_document` for AWS S3, KMS, SNS, SQS, ECR, and Secrets Manager.

---

## 1. AWS S3 Bucket Policy Pattern

A production S3 policy combines SSL enforcement, restricted cross-account access, and optional AWS Organization restrictions.

```hcl
data "aws_iam_policy_document" "s3_bucket_policy" {
  # 1. SSL Guardrail (Mandatory)
  statement {
    sid    = "EnforceTLS"
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

  # 2. Allow Read/Write within AWS Organization
  statement {
    sid    = "AllowOrgAccess"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions = [
      "s3:GetObject",
      "s3:ListBucket",
      "s3:PutObject",
    ]

    resources = [
      aws_s3_bucket.this.arn,
      "${aws_s3_bucket.this.arn}/*",
    ]

    condition {
      test     = "StringEquals"
      variable = "aws:PrincipalOrgID"
      values   = [var.aws_organization_id]
    }
  }
}

resource "aws_s3_bucket_policy" "this" {
  bucket = aws_s3_bucket.this.id
  policy = data.aws_iam_policy_document.s3_bucket_policy.json
}
```

---

## 2. AWS KMS Key Policy Pattern

KMS Key Policies are critical: if you do not grant administrative permission to the account root, the KMS key can become permanently unmanageable.

### Key Policy Structure Requirements
1. **Enable IAM User / Root Delegation**: Essential so IAM policies within the account can grant access to the key.
2. **Separate Key Admin vs Key User Roles**: Admin manages key policies/rotation; Users perform Encrypt/Decrypt/GenerateDataKey.

```hcl
data "aws_iam_policy_document" "kms_key_policy" {
  # 1. Enable Account Root Delegation (MANDATORY)
  statement {
    sid    = "EnableRootIAMUserPermissions"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }

  # 2. Key Administrator Rights
  statement {
    sid    = "AllowKeyAdministration"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = var.kms_admin_role_arns
    }

    actions = [
      "kms:Create*",
      "kms:Describe*",
      "kms:Enable*",
      "kms:List*",
      "kms:Put*",
      "kms:Update*",
      "kms:Revoke*",
      "kms:Disable*",
      "kms:Get*",
      "kms:Delete*",
      "kms:ScheduleKeyDeletion",
      "kms:CancelKeyDeletion",
    ]

    resources = ["*"]
  }

  # 3. Key Usage Rights (Encrypt / Decrypt)
  statement {
    sid    = "AllowKeyUsage"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = var.kms_user_role_arns
    }

    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]

    resources = ["*"]
  }
}

resource "aws_kms_key" "this" {
  description             = "Customer Managed KMS Key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms_key_policy.json
}
```

---

## 3. AWS SNS Topic & SQS Queue Policy Pattern

When allowing AWS S3 or EventBridge to send events to SNS/SQS, protect against Confused Deputy using `aws:SourceArn`.

```hcl
data "aws_iam_policy_document" "sqs_policy" {
  # SSL Transport Guardrail
  statement {
    sid    = "DenyNonSSLRequests"
    effect = "Deny"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions   = ["sqs:*"]
    resources = [aws_sqs_queue.this.arn]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  # Allow S3 Notifications with Confused Deputy Guardrail
  statement {
    sid    = "AllowS3Notifications"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.this.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_s3_bucket.event_source.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}
```

---

## 4. AWS ECR Repository Policy Pattern

Grant cross-account or Organization-wide pull access to Docker images:

```hcl
data "aws_iam_policy_document" "ecr_policy" {
  statement {
    sid    = "AllowOrgReadImages"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    condition {
      test     = "StringEquals"
      variable = "aws:PrincipalOrgID"
      values   = [var.aws_organization_id]
    }
  }
}

resource "aws_ecr_repository_policy" "this" {
  repository = aws_ecr_repository.this.name
  policy     = data.aws_iam_policy_document.ecr_policy.json
}
```
