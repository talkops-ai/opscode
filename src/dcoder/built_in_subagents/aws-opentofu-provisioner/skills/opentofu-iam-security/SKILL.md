---
name: opentofu-iam-security
description: >
  Comprehensive IAM security patterns for OpenTofu AWS modules covering service
  roles, instance profiles, policy document authoring, exclusive policy management,
  permissions boundaries, and resource-based policies (S3, KMS, SNS). Use when:
  (1) creating EC2 service roles with the IAM role/instance profile/instance trinity,
  (2) authoring IAM policies using aws_iam_policy_document data sources,
  (3) handling AWS runtime variable interpolation with &{...} syntax,
  (4) preventing ClickOps drift via aws_iam_role_policies_exclusive,
  (5) enforcing least privilege with permissions_boundary,
  (6) writing S3 bucket policies with ACL deprecation and public access blocking,
  (7) preventing KMS key root lockout, or (8) protecting against Confused Deputy
  attacks in SNS topic policies. Do NOT use for network security groups or VPC
  endpoints (use opentofu-vpc-networking).
license: MIT
compatibility: designed for deepagents-code
---

# OpenTofu IAM Security & Policy Architecture

Production-grade IAM security patterns, service role orchestration, and resource-based policy authoring for OpenTofu AWS modules.

---

## Core Principles

1. **Native HCL Policy Documents Only**: Always use `aws_iam_policy_document` data sources. **Never** use inline JSON strings, heredoc syntax (`<<EOF`), or `jsonencode()` for IAM policies.
2. **Exclusive Policy Management**: Use `aws_iam_role_policies_exclusive` to prevent out-of-band ClickOps drift. OpenTofu must have authoritative, total ownership of role attachments.
3. **Permissions Boundaries**: Apply `permissions_boundary` on all high-privilege roles to enforce least privilege even if excessive permissions are inadvertently granted.
4. **Confused Deputy Protection**: When granting access to AWS service principals (`type = "Service"`), always enforce `aws:SourceArn` and `aws:SourceAccount` conditions.
5. **No Hardcoded Credentials**: Never hardcode long-lived AWS access keys onto compute instances. Always use IAM roles with assume-role trust policies.

---

## Execution Workflow

### Step 1: Author EC2 Service Roles & Instance Profiles

When provisioning EC2, the agent must orchestrate the complete IAM lifecycle — a tightly coupled **trinity** of resources:

1. **`aws_iam_role`** — with a trust policy allowing `ec2.amazonaws.com` to assume the role
2. **`aws_iam_instance_profile`** — acts as a container for the IAM role (EC2 cannot assume roles directly)
3. **`aws_instance`** — references the instance profile via `iam_instance_profile`

```hcl
data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name               = "${var.project_name}-app-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
  permissions_boundary = var.permissions_boundary_arn
}

resource "aws_iam_instance_profile" "app" {
  name = "${var.project_name}-app-profile"
  role = aws_iam_role.app.name
}

resource "aws_instance" "app" {
  ami                  = var.ami_id
  instance_type        = var.instance_type
  iam_instance_profile = aws_iam_instance_profile.app.name
  # ...
}
```

---

### Step 2: Author IAM Policies with `aws_iam_policy_document`

**Critical Syntax Rule — AWS Runtime Variable Interpolation:**

AWS IAM policies support internal runtime variables such as `${aws:username}` or `${aws:PrincipalTag/Department}`. Because OpenTofu uses the same `${...}` syntax for local string interpolation, these conflict and will cause compilation failures or incorrect value injection.

**Use `&{...}` syntax** for interpolations that must be processed by AWS at runtime rather than by OpenTofu during the plan phase:

```hcl
data "aws_iam_policy_document" "user_self_manage" {
  statement {
    effect    = "Allow"
    actions   = ["iam:ChangePassword"]
    resources = ["arn:aws:iam::*:user/&{aws:username}"]
  }
}
```

---

### Step 3: Enforce Exclusive Policy Management

The standard `aws_iam_role_policy_attachment` ignores out-of-band attachments made via the AWS Console, leaving security backdoors open. Use `aws_iam_role_policies_exclusive` to force OpenTofu to take authoritative ownership:

```hcl
resource "aws_iam_role_policies_exclusive" "app" {
  role_name   = aws_iam_role.app.name
  policy_arns = [
    aws_iam_policy.app_permissions.arn,
  ]
}
```

If an unmanaged, manually attached policy is discovered during `tofu plan`, OpenTofu will proactively remove that attachment, forcing all IAM changes through the authorised CI/CD pipeline.

---

### Step 4: Apply Resource-Based Policies

#### S3 Bucket Policies (ACL Deprecation)

ACLs are a **deprecated security paradigm**. The agent must:
1. Disable ACLs via `aws_s3_bucket_ownership_controls` → `BucketOwnerEnforced`
2. Block public access via `aws_s3_bucket_public_access_block` (all 4 settings `true`)
3. Order resources with `depends_on` — public access block must be provisioned before the bucket policy to prevent race conditions

```hcl
resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "this" {
  bucket     = aws_s3_bucket.this.id
  policy     = data.aws_iam_policy_document.bucket_policy.json
  depends_on = [aws_s3_bucket_public_access_block.this]
}
```

#### KMS Key Policies (Root Lockout Prevention)

KMS keys do **not** default to trusting the account's IAM permissions. If the agent authors a key policy without granting admin access to the account root, the key becomes **permanently unmanageable** ("orphaned") — requiring AWS Support escalation.

**Always** query `aws_caller_identity` and inject a root access statement:

```hcl
data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "kms_key_policy" {
  # Root access — prevents key orphaning
  statement {
    sid       = "EnableRootAccountAccess"
    effect    = "Allow"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }

  # Key administrators
  statement {
    sid    = "AllowKeyAdministration"
    effect = "Allow"
    actions = [
      "kms:Create*", "kms:Describe*", "kms:Enable*",
      "kms:List*", "kms:Put*", "kms:Update*",
      "kms:Revoke*", "kms:Disable*", "kms:Get*",
      "kms:Delete*", "kms:TagResource", "kms:UntagResource",
      "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion"
    ]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = var.kms_admin_arns
    }
  }
}
```

#### SNS Topic Policies (Confused Deputy Protection)

When AWS services publish to SNS topics (e.g., S3 event notifications), enforce **both** `aws:SourceAccount` and `aws:SourceArn` conditions:

```hcl
data "aws_iam_policy_document" "sns_policy" {
  statement {
    effect    = "Allow"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.notifications.arn]

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = [aws_s3_bucket.this.arn]
    }
  }
}
```

This guarantees a malicious actor cannot use an arbitrary S3 bucket in another AWS account to trigger your internal SNS topics.
