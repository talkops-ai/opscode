# AWS IAM Access Scoping & Organization Guardrails

## Access Scoping Architecture

When designing service-level resource policies (S3, KMS, SNS, SQS, ECR, Secrets Manager), access must be evaluated across three boundary tiers:

1. **Same-Account Access**: Access from principals within the same AWS account holding the resource.
2. **Cross-Account Access**: Explicitly permitted access to trusted external AWS accounts.
3. **Outside Organization Access**: Public or third-party access restricted by AWS Organizations (`aws:PrincipalOrgID`).

---

## Principal Types & Scoping Rules

Resource policies require an explicit `principals` block in HCL. Always scope principal identifiers strictly according to the access tier:

### 1. Account / IAM Principals (`type = "AWS"`)
- **Same Account / Internal**: `arn:aws:iam::111122223333:root` or specific role/user ARNs (`arn:aws:iam::111122223333:role/MyRole`).
- **Cross-Account**: Specify the foreign account root (`arn:aws:iam::444455556666:root`) to delegate authorization to the foreign account's IAM policies, OR specify the exact foreign role ARN (`arn:aws:iam::444455556666:role/CrossAccountRole`).

### 2. Service Principals (`type = "Service"`)
- Used when AWS services interact directly with the resource (e.g., `s3.amazonaws.com`, `sns.amazonaws.com`, `events.amazonaws.com`).
- **CRITICAL**: Service principals bypass IAM permission checks. Never use `type = "Service"` without mandatory `aws:SourceArn` or `aws:SourceAccount` condition keys to prevent Confused Deputy vulnerabilities.

### 3. Federated Principals (`type = "Federated"`)
- SAML or Web Identity providers (`cognito-identity.amazonaws.com`, `arn:aws:iam::111122223333:saml-provider/MyProvider`).

---

## Confused Deputy Prevention

When granting access to an AWS service principal, enforce account and resource boundary conditions.

### Standard Confused Deputy Guardrail Pattern (HCL)
```hcl
data "aws_iam_policy_document" "sqs_eventbridge_policy" {
  statement {
    sid    = "AllowEventBridgeToPublish"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.this.arn]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.this.arn]
    }
  }
}
```

---

## AWS Organizations Guardrails (`aws:PrincipalOrgID`)

To allow access to any account inside your AWS Organization while automatically denying all accounts outside the Organization:

### Org-Wide Access Condition Pattern
```hcl
data "aws_iam_policy_document" "s3_org_read" {
  statement {
    sid    = "AllowOrgReadAccess"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.shared.arn,
      "${aws_s3_bucket.shared.arn}/*",
    ]

    condition {
      test     = "StringEquals"
      variable = "aws:PrincipalOrgID"
      values   = [var.aws_organization_id]
    }
  }
}
```

### Organizational Unit Scoping (`aws:PrincipalOrgPaths`)
For finer-grained restriction to specific OUs within an organization:
```hcl
condition {
  test     = "ForAnyValue:StringLike"
  variable = "aws:PrincipalOrgPaths"
  values   = ["o-a1b2c3d4e5/r-ab12/ou-ab12-11111111/*"]
}
```

---

## Decision Matrix: Evaluating Cross-Account Access

| Scenario | Principal `type` | Principal `identifiers` | Required Condition Keys |
|---|---|---|---|
| Same Account Role | `"AWS"` | `[arn:aws:iam::ACCOUNT:role/RoleName]` | Optional (`aws:PrincipalTag`) |
| Cross-Account Trusted Account | `"AWS"` | `[arn:aws:iam::FOREIGN_ACCOUNT:root]` | `aws:PrincipalAccount` or `aws:PrincipalTag` |
| Organization-wide Sharing | `"AWS"` | `["*"]` | `aws:PrincipalOrgID` (Mandatory) |
| AWS Service Notification | `"Service"` | `["sns.amazonaws.com"]` | `aws:SourceAccount` and/or `aws:SourceArn` |
