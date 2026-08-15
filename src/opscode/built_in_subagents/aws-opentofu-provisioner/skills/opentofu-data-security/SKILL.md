---
name: opentofu-data-security
description: >
  Data protection enforcement patterns for OpenTofu AWS modules covering KMS
  encryption at rest, S3 ACL deprecation with BucketOwnerEnforced ownership,
  public access blocking at account and resource level, and encryption defaults
  for storage, messaging, and database services. Use when: (1) enforcing KMS CMK
  encryption across S3, RDS, EBS, DynamoDB, SQS, and Secrets Manager,
  (2) disabling deprecated S3 ACLs via aws_s3_bucket_ownership_controls,
  (3) implementing aws_s3_bucket_public_access_block with all 4 settings,
  (4) ordering resource creation with depends_on to prevent race conditions,
  or (5) ensuring all storage and data plane resources default to encryption.
  Do NOT use for IAM policy authoring (use opentofu-iam-security) or VPC network
  isolation (use opentofu-vpc-networking).
license: MIT
compatibility: designed for opscode
---

# OpenTofu Data Security Enforcement

Architectural guardrails and HCL patterns for enforcing data protection across AWS storage and data plane services in OpenTofu.

---

## Core Security Pillars

1. **Encryption at Rest (KMS CMK)**: Enforce KMS Customer Managed Keys across all data-storing resources with automatic key rotation.
2. **ACL Deprecation**: Actively disable S3 ACLs — route all access control through bucket policies exclusively.
3. **Public Access Prevention**: Block public exposure at account and resource level.
4. **Resource Ordering**: Use `depends_on` to prevent race conditions between security controls and policies.

---

## Execution Workflow

### Step 1: Disable Deprecated ACLs

ACLs are a deprecated security paradigm. When provisioning S3 buckets, actively disable them:

```hcl
resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}
```

This forces all access control through `aws_s3_bucket_policy` exclusively, eliminating ACL-based auditing complexity.

---

### Step 2: Block Public Access

Apply multi-layered isolation to prevent public exposure:

```hcl
resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

**Critical — Resource Ordering**: The public access block must be fully provisioned **before** the bucket policy is applied. Use `depends_on` to prevent race conditions:

```hcl
resource "aws_s3_bucket_policy" "this" {
  bucket     = aws_s3_bucket.this.id
  policy     = data.aws_iam_policy_document.bucket.json
  depends_on = [aws_s3_bucket_public_access_block.this]
}
```

---

### Step 3: Enforce KMS Encryption at Rest

All resources storing data MUST enable encryption using KMS Customer Managed Keys with automatic rotation:

```hcl
resource "aws_kms_key" "this" {
  description         = "Encryption key for ${var.project_name}"
  enable_key_rotation = true
}
```

Apply per-service encryption:

| Service | Resource / Attribute | Configuration |
|---|---|---|
| **S3** | `aws_s3_bucket_server_side_encryption_configuration` | `sse_algorithm = "aws:kms"`, `bucket_key_enabled = true` |
| **RDS / Aurora** | `aws_db_instance` / `aws_rds_cluster` | `storage_encrypted = true`, `kms_key_id` |
| **EBS** | `aws_ebs_encryption_by_default` + `aws_ebs_volume` | `encrypted = true`, `kms_key_id` |
| **DynamoDB** | `aws_dynamodb_table` | `server_side_encryption { enabled = true, kms_key_arn }` |
| **SQS** | `aws_sqs_queue` | `kms_master_key_id` |
| **Secrets Manager** | `aws_secretsmanager_secret` | `kms_key_id` |
| **EFS** | `aws_efs_file_system` | `kms_key_id` |

### Step 4: Enforce KMS Root Access

When creating KMS keys, always include a root access statement to prevent key orphaning. Use `aws_caller_identity` to dynamically inject the account ID. See **opentofu-iam-security** skill for the full KMS key policy pattern.

---

## Default Security Posture

> **All storage, messaging, and database resources must default to KMS encryption at rest, TLS encryption in transit, and public access blocks.** The agent should never produce a storage resource without these protections unless explicitly overridden by the user.
