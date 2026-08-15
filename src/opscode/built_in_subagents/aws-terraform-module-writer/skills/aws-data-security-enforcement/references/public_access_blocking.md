# AWS Data Protection: Public Access Blocking & Isolation Mechanisms

This document specifies HCL standards for preventing public access to AWS storage and data plane resources across account, resource, network, and policy dimensions.

---

## 1. Account-Level Public Access Guardrails

Enforce global account-level blocks to prevent accidental public exposure of storage assets and snapshots across all AWS regions.

### S3 Account-Level Public Access Block
```hcl
resource "aws_s3_account_public_access_block" "account_guardrail" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

### EBS Snapshot Account-Level Public Access Block
```hcl
resource "aws_ebs_snapshot_block_public_access" "account_guardrail" {
  state = "block-all"
}
```

---

## 2. Amazon S3 Bucket Public Access Block

Every S3 bucket must explicitly declare an `aws_s3_bucket_public_access_block` resource with all four controls enabled.

```hcl
resource "aws_s3_bucket" "private_store" {
  bucket = "app-private-store-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "private_store_block" {
  bucket = aws_s3_bucket.private_store.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

---

## 3. RDS & Database Network Isolation

Database instances and clusters must never be directly accessible from the public internet.

```hcl
# Private Subnet Group
resource "aws_db_subnet_group" "isolated" {
  name       = "app-isolated-db-subnet-group"
  subnet_ids = var.isolated_subnet_ids

  tags = {
    Name = "DB Private Isolation Subnet Group"
  }
}

# Strictly Isolated Security Group
resource "aws_security_group" "db_sg" {
  name        = "app-db-security-group"
  description = "Strict ingress for internal app instances only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL access from App Tier SG"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.app_security_group_id]
  }

  egress {
    description = "No outbound internet access"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = []
  }
}

# Database Instance configured as Non-Public
resource "aws_db_instance" "secure_db" {
  identifier             = "app-secure-db"
  engine                 = "postgres"
  instance_class         = "db.t4g.medium"
  allocated_storage      = 50
  
  publicly_accessible    = false
  db_subnet_group_name   = aws_db_subnet_group.isolated.name
  vpc_security_group_ids = [aws_security_group.db_sg.id]
}
```

---

## 4. DynamoDB, SQS & Secrets Manager Policy & Endpoint Isolation

Data plane services like DynamoDB, SQS, and Secrets Manager must restrict access using IAM resource policies and Private VPC Endpoints (AWS PrivateLink).

### Private VPC Endpoints
```hcl
# S3 Gateway Endpoint
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.private_route_table_ids
}

# Interface Endpoints for Secrets Manager & SQS
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [var.vpc_endpoint_security_group_id]
  private_dns_enabled = true
}

resource "aws_vpc_endpoint" "sqs" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.sqs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [var.vpc_endpoint_security_group_id]
  private_dns_enabled = true
}
```

### Secrets Manager Resource Policy Restricting to VPC Endpoint or Org
```hcl
resource "aws_secretsmanager_secret_policy" "restrict_access" {
  secret_arn = aws_secretsmanager_secret.api_credential.arn
  policy     = data.aws_iam_policy_document.secrets_manager_policy.json
}

data "aws_iam_policy_document" "secrets_manager_policy" {
  statement {
    sid    = "RestrictToVpcEndpoint"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["*"]
    condition {
      test     = "StringNotEquals"
      variable = "aws:sourceVpce"
      values   = [aws_vpc_endpoint.secretsmanager.id]
    }
  }
}
```

### SQS Policy Preventing Unauthenticated or Global Access
```hcl
resource "aws_sqs_queue_policy" "secure_access" {
  queue_url = aws_sqs_queue.task_queue.id
  policy    = data.aws_iam_policy_document.sqs_policy.json
}

data "aws_iam_policy_document" "sqs_policy" {
  statement {
    sid    = "DenyNonAccountAccess"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions   = ["sqs:*"]
    resources = [aws_sqs_queue.task_queue.arn]
    condition {
      test     = "StringNotEquals"
      variable = "aws:PrincipalAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}
```
