# AWS Data Protection: In-Transit Encryption & SSL/TLS Enforcement

This document specifies HCL implementation patterns for enforcing SSL/TLS encryption in transit across storage and data plane resources in Terraform.

---

## 1. Amazon S3 In-Transit SSL Enforcement

S3 buckets must enforce TLS/SSL by attaching a resource policy that explicitly denies any request where `aws:SecureTransport` evaluates to `false`.

```hcl
resource "aws_s3_bucket_policy" "enforce_tls" {
  bucket = aws_s3_bucket.data_store.id
  policy = data.aws_iam_policy_document.s3_tls_policy.json
}

data "aws_iam_policy_document" "s3_tls_policy" {
  statement {
    sid    = "EnforceTLSRequestsOnly"
    effect = "Deny"
    
    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.data_store.arn,
      "${aws_s3_bucket.data_store.arn}/*"
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid    = "EnforceTLSVersion"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.data_store.arn,
      "${aws_s3_bucket.data_store.arn}/*"
    ]

    condition {
      test     = "NumericLessThan"
      variable = "s3:TlsVersion"
      values   = ["1.2"]
    }
  }
}
```

---

## 2. Amazon RDS & Aurora SSL/TLS Enforcement

Database engine configurations must enforce encrypted connections via Parameter Groups.

### PostgreSQL / Aurora PostgreSQL Parameter Group
```hcl
resource "aws_db_parameter_group" "postgres_tls" {
  name   = "pg-force-tls-param-group"
  family = "postgres15"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

resource "aws_db_instance" "postgres" {
  identifier           = "app-postgres-db"
  engine               = "postgres"
  instance_class       = "db.t4g.medium"
  parameter_group_name = aws_db_parameter_group.postgres_tls.name
  
  # ... other database configuration ...
}
```

### MySQL / MariaDB Parameter Group
```hcl
resource "aws_db_parameter_group" "mysql_tls" {
  name   = "mysql-force-tls-param-group"
  family = "mysql8.0"

  parameter {
    name  = "require_secure_transport"
    value = "ON"
  }
}
```

---

## 3. Amazon SQS In-Transit SSL Enforcement

SQS queues must enforce TLS for all API operations (`SendMessage`, `ReceiveMessage`, `DeleteMessage`) via queue policies.

```hcl
resource "aws_sqs_queue_policy" "enforce_tls" {
  queue_url = aws_sqs_queue.task_queue.id
  policy    = data.aws_iam_policy_document.sqs_tls_policy.json
}

data "aws_iam_policy_document" "sqs_tls_policy" {
  statement {
    sid    = "EnforceTLSRequestsOnly"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["sqs:*"]

    resources = [aws_sqs_queue.task_queue.arn]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}
```

---

## 4. AWS Secrets Manager In-Transit SSL Enforcement

Secrets Manager resource policies must deny unencrypted HTTP requests.

```hcl
resource "aws_secretsmanager_secret_policy" "enforce_tls" {
  secret_arn = aws_secretsmanager_secret.api_credential.arn
  policy     = data.aws_iam_policy_document.secretsmanager_tls_policy.json
}

data "aws_iam_policy_document" "secretsmanager_tls_policy" {
  statement {
    sid    = "EnforceTLSRequestsOnly"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["secretsmanager:*"]

    resources = ["*"]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}
```

---

## 5. Amazon DynamoDB & VPC Endpoint In-Transit Policy

Enforce SSL in transit for DynamoDB access via VPC Endpoint policy.

```hcl
data "aws_iam_policy_document" "dynamodb_endpoint_policy" {
  statement {
    sid    = "EnforceTLSOnEndpoint"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["dynamodb:*"]

    resources = ["*"]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid    = "AllowDynamoDBAccess"
    effect = "Allow"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["dynamodb:*"]
    resources = ["*"]
  }
}
```
