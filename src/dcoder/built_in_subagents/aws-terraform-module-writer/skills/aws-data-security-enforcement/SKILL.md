---
name: aws-data-security-enforcement
description: "Comprehensive guidance and HCL standards for enforcing security across AWS storage and data plane resources (S3, RDS, EBS, DynamoDB, SQS, Secrets Manager) in Terraform. Use when generating, auditing, or refactoring Terraform code for: (1) Enforcing server-side encryption at rest using KMS CMK or SSE, (2) Implementing public access blocking and private network/policy isolation, or (3) Enforcing TLS/SSL in-transit encryption using resource policies (aws:SecureTransport) and DB parameter groups."
license: MIT
compatibility: designed for deepagents-code
---

# AWS Data Security Enforcement

This skill provides architectural guardrails, security baselines, and native HCL patterns for enforcing data protection across AWS storage and data plane services in Terraform.

---

## Core Security Pillars

1. **Encryption at Rest (KMS CMK & SSE)**: Enforce KMS Customer Managed Keys or default SSE across S3, RDS, EBS, DynamoDB, SQS, and Secrets Manager with automated key rotation and S3 Bucket Key optimization.
2. **Public Access Prevention**: Eliminate public network and policy exposure at the account, resource, and subnet level using S3 account/bucket blocks, EBS snapshot public access blocks, non-public RDS instances, and Private VPC Endpoints.
3. **In-Transit TLS/SSL Enforcement**: Mandate TLS 1.2+ encrypted connections across all API data operations using IAM policy `aws:SecureTransport: false` Deny statements and database parameter group settings (`rds.force_ssl`, `require_secure_transport`).

---

## Execution Workflow

When authoring or auditing Terraform modules for AWS storage and data plane services, follow this 3-step security workflow:

### Step 1: Enforce Encryption at Rest

Define KMS Customer Managed Keys (`aws_kms_key`) with automated rotation, and configure service-level encryption blocks:
- **S3**: `aws_s3_bucket_server_side_encryption_configuration` with `bucket_key_enabled = true`.
- **RDS / Aurora**: `storage_encrypted = true` and `kms_key_id`.
- **EBS**: Account-level `aws_ebs_encryption_by_default` plus volume-level `encrypted = true`.
- **DynamoDB**: `server_side_encryption` block with KMS key ARN.
- **SQS**: `kms_master_key_id` or SSE-SQS enabled.
- **Secrets Manager**: `kms_key_id` assigned on secret creation.

For full HCL configurations and KMS key policy templates, see [references/encryption_at_rest.md](references/encryption_at_rest.md).

---

### Step 2: Implement Public Access Block Mechanisms

Apply multi-layered isolation to prevent public exposure:
- **Account Controls**: Deploy `aws_s3_account_public_access_block` and `aws_ebs_snapshot_block_public_access`.
- **Resource Block**: Attach `aws_s3_bucket_public_access_block` with all four block settings set to `true`.
- **Network Isolation**: Deploy RDS databases in private subnets with `publicly_accessible = false` and security groups restricted to application tier SGs.
- **Endpoint Protection**: Use Gateway and Interface VPC Endpoints (`com.amazonaws.<region>.<service>`) to keep traffic off the public internet.

For complete public access blocking patterns, see [references/public_access_blocking.md](references/public_access_blocking.md).

---

### Step 3: Enforce TLS/SSL Encryption in Transit

Attach explicit policies and parameter group settings that deny unencrypted traffic:
- **Resource Policies**: Attach bucket, queue, and secret policies that explicitly `Deny` requests where `aws:SecureTransport` is `false`.
- **TLS Version**: Enforce `s3:TlsVersion` >= 1.2 in S3 bucket policy conditions.
- **Database Engine**: Set `rds.force_ssl = 1` (PostgreSQL) or `require_secure_transport = ON` (MySQL) in `aws_db_parameter_group`.

For in-transit policy syntax and parameter group templates, see [references/in_transit_enforcement.md](references/in_transit_enforcement.md).

---

## Quick Reference Map

| Security Domain | Reference Document | Covered Services & Controls |
|---|---|---|
| **Encryption at Rest** | [encryption_at_rest.md](references/encryption_at_rest.md) | KMS CMK, S3 SSE/Bucket Key, RDS/Aurora, EBS default encryption, DynamoDB, SQS, Secrets Manager |
| **Public Access Blocking** | [public_access_blocking.md](references/public_access_blocking.md) | Account S3/EBS blocks, S3 Public Access Block, RDS private isolation, VPC Endpoints, Resource policies |
| **In-Transit Protection** | [in_transit_enforcement.md](references/in_transit_enforcement.md) | `aws:SecureTransport` Deny rules, TLS 1.2+ enforcement, RDS parameter groups (`force_ssl`, `require_secure_transport`) |
