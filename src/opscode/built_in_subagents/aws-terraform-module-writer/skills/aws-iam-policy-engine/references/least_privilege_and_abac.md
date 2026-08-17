# Least Privilege Rules & Attribute-Based Access Control (ABAC)

## Least Privilege Principles for Resource Policies

A security guardrail pattern enforces mandatory security baselines (SSL enforcement, encryption standards, public access bans) using **Explicit Deny statements**. In AWS IAM, an explicit Deny overrides any Allow statement regardless of where it is attached.

---

## Standard Guardrail Statements

### 1. Mandatory TLS/SSL Enforcement (`aws:SecureTransport`)
All resource-based policies (S3, SQS, SNS, KMS, ECR) must contain an explicit Deny statement rejecting non-TLS traffic.

```hcl
data "aws_iam_policy_document" "ssl_guardrail" {
  statement {
    sid    = "DenyNonSSLRequests"
    effect = "Deny"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions   = ["*"]
    resources = [var.resource_arn, "${var.resource_arn}/*"]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}
```

---

### 2. Enforcing Encryption at Rest (`s3:x-amz-server-side-encryption`)
Enforce KMS server-side encryption for S3 object uploads:

```hcl
statement {
  sid    = "DenyUnencryptedObjectUploads"
  effect = "Deny"

  principals {
    type        = "AWS"
    identifiers = ["*"]
  }

  actions = ["s3:PutObject"]
  resources = ["${aws_s3_bucket.this.arn}/*"]

  condition {
    test     = "StringNotEquals"
    variable = "s3:x-amz-server-side-encryption"
    values   = ["aws:kms"]
  }
}
```

---

### 3. Preventing Unencrypted S3 Bucket Uploads (Null Check)
Deny uploads that omit server-side encryption header:

```hcl
statement {
  sid    = "DenyUnencryptedHeaderMissing"
  effect = "Deny"

  principals {
    type        = "AWS"
    identifiers = ["*"]
  }

  actions = ["s3:PutObject"]
  resources = ["${aws_s3_bucket.this.arn}/*"]

  condition {
    test     = "Null"
    variable = "s3:x-amz-server-side-encryption"
    values   = ["true"]
  }
}
```

---

## Attribute-Based Access Control (ABAC)

Attribute-Based Access Control authorizes access dynamically based on tags associated with either the principal (`aws:PrincipalTag/Key`) or the target resource (`aws:ResourceTag/Key`).

### ABAC Match Pattern: Principal Tag Matches Resource Tag
Allow access only when the principal's `CostCenter` tag matches the resource's `CostCenter` tag:

```hcl
data "aws_iam_policy_document" "abac_policy" {
  statement {
    sid    = "AllowAccessMatchingCostCenter"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::111122223333:root"]
    }

    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/CostCenter"
      values   = ["$${aws:PrincipalTag/CostCenter}"]
    }
  }
}
```

### Environment Tag Guardrail
Deny modification of production resources unless principal is tagged as Environment = Production:

```hcl
statement {
  sid    = "DenyNonProdAccessToProdResources"
  effect = "Deny"

  principals {
    type        = "AWS"
    identifiers = ["*"]
  }

  actions = [
    "s3:DeleteObject",
    "s3:DeleteBucket",
  ]

  resources = [aws_s3_bucket.this.arn, "${aws_s3_bucket.this.arn}/*"]

  condition {
    test     = "StringNotEquals"
    variable = "aws:PrincipalTag/Environment"
    values   = ["Production"]
  }
}
```

---

## Action Minimization Matrix

When defining allowed actions in resource policies, avoid wildcards like `s3:*` or `kms:*`. Limit actions strictly to required capabilities:

| Service | Read-Only Actions | Write Actions | Admin Actions |
|---|---|---|---|
| **S3** | `s3:GetObject`, `s3:ListBucket` | `s3:PutObject`, `s3:AbortMultipartUpload` | `s3:PutBucketPolicy`, `s3:DeleteBucket` |
| **KMS** | `kms:Decrypt`, `kms:DescribeKey` | `kms:Encrypt`, `kms:GenerateDataKey` | `kms:PutKeyPolicy`, `kms:ScheduleKeyDeletion` |
| **SQS** | `sqs:ReceiveMessage`, `sqs:GetQueueAttributes` | `sqs:SendMessage` | `sqs:SetQueueAttributes`, `sqs:DeleteQueue` |
| **SNS** | `sns:Subscribe` | `sns:Publish` | `sns:SetTopicAttributes`, `sns:DeleteTopic` |
| **ECR** | `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer` | `ecr:PutImage`, `ecr:InitiateLayerUpload` | `ecr:SetRepositoryPolicy`, `ecr:DeleteRepository` |
