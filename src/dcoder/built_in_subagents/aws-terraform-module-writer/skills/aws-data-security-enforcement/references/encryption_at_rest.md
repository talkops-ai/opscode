# AWS Data Protection: Encryption at Rest Standards

This document specifies HCL implementation patterns for enforcing Customer Managed Keys (CMK) or AWS-managed KMS server-side encryption across AWS storage and data plane resources in Terraform.

---

## 1. KMS Customer Master Key (CMK) Baseline

When enforcing encryption at rest across storage services, use dedicated Customer Managed Keys (`aws_kms_key`) with automatic key rotation enabled.

```hcl
resource "aws_kms_key" "data_encryption" {
  description             = "CMK for data plane and storage encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = data.aws_iam_policy_document.kms_key_policy.json

  tags = {
    SecurityClass = "Restricted"
  }
}

resource "aws_kms_alias" "data_encryption" {
  name          = "alias/app-data-encryption"
  target_key_id = aws_kms_key.data_encryption.key_id
}

data "aws_iam_policy_document" "kms_key_policy" {
  # Key Administration Statement
  statement {
    sid    = "EnableIAMUserPermissions"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }

  # Service Access for Cryptographic Operations
  statement {
    sid    = "AllowServiceUsage"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = [
        "s3.amazonaws.com",
        "rds.amazonaws.com",
        "sqs.amazonaws.com",
        "secretsmanager.amazonaws.com",
        "dynamodb.amazonaws.com"
      ]
    }
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey*",
      "kms:DescribeKey"
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}
```

---

## 2. Amazon S3 Encryption at Rest

Every S3 bucket must have server-side encryption enabled using KMS CMK or SSE-S3. Always set `bucket_key_enabled = true` to reduce KMS API costs by up to 99%.

```hcl
resource "aws_s3_bucket" "data_store" {
  bucket = "app-data-store-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data_store" {
  bucket = aws_s3_bucket.data_store.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.data_encryption.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}
```

---

## 3. Amazon RDS & Aurora Encryption at Rest

Database instances and Aurora clusters must have `storage_encrypted = true` and specify a valid KMS key.

### RDS DB Instance
```hcl
resource "aws_db_instance" "postgres" {
  identifier          = "app-postgres-db"
  engine              = "postgres"
  instance_class      = "db.t4g.medium"
  allocated_storage   = 50
  storage_type        = "gp3"
  
  storage_encrypted   = true
  kms_key_id          = aws_kms_key.data_encryption.arn

  skip_final_snapshot = false
  final_snapshot_identifier = "app-postgres-db-final"
}
```

### Aurora DB Cluster
```hcl
resource "aws_rds_cluster" "aurora" {
  cluster_identifier = "app-aurora-cluster"
  engine             = "aurora-postgresql"
  
  storage_encrypted  = true
  kms_key_id         = aws_kms_key.data_encryption.arn

  master_username    = "dbadmin"
  manage_master_user_password = true
  master_user_secret_kms_key_id = aws_kms_key.data_encryption.arn
}
```

---

## 4. Amazon EBS Volume Encryption at Rest

Enable region-level default encryption for all newly created EBS volumes in the AWS account, and explicitly specify `encrypted = true` on individual volume and launch template definitions.

### Account-Level Default EBS Encryption
```hcl
resource "aws_ebs_encryption_by_default" "enforce" {
  enabled = true
}

resource "aws_ebs_default_kms_key" "custom" {
  key_arn = aws_kms_key.data_encryption.arn
}
```

### Standalone EBS Volume & Launch Template
```hcl
resource "aws_ebs_volume" "data" {
  availability_zone = "us-east-1a"
  size              = 100
  type              = "gp3"
  
  encrypted  = true
  kms_key_id = aws_kms_key.data_encryption.arn
}

resource "aws_launch_template" "app_nodes" {
  name_prefix   = "app-node-"
  image_id      = "ami-0123456789abcdef0"
  instance_type = "t3.medium"

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = 30
      volume_type           = "gp3"
      encrypted             = true
      kms_key_id            = aws_kms_key.data_encryption.arn
      delete_on_termination = true
    }
  }
}
```

---

## 5. Amazon DynamoDB Encryption at Rest

DynamoDB tables must be configured with AWS KMS server-side encryption.

```hcl
resource "aws_dynamodb_table" "app_state" {
  name         = "app-state-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.data_encryption.arn
  }
}
```

---

## 6. Amazon SQS Queue Encryption at Rest

Queue messages must be encrypted using KMS CMK or SSE-SQS.

```hcl
resource "aws_sqs_queue" "task_queue" {
  name                              = "app-task-queue"
  kms_master_key_id                 = aws_kms_key.data_encryption.arn
  kms_data_key_reuse_period_seconds = 300
}
```

---

## 7. AWS Secrets Manager Encryption at Rest

Secrets in Secrets Manager must be encrypted with a customer-managed KMS key.

```hcl
resource "aws_secretsmanager_secret" "api_credential" {
  name                    = "app/production/api_key"
  kms_key_id              = aws_kms_key.data_encryption.arn
  recovery_window_in_days = 30
}
```
