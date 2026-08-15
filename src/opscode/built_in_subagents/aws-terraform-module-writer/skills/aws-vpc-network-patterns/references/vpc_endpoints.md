# VPC Endpoints and PrivateLink Integration

This reference provides architecture patterns and HCL implementations for AWS Gateway Endpoints, Interface Endpoints (PrivateLink), endpoint security policies, and DNS configuration.

---

## 1. Gateway Endpoints vs Interface Endpoints

| Feature | Gateway Endpoints | Interface Endpoints (PrivateLink) |
|---|---|---|
| **Supported Services** | Amazon S3, DynamoDB | S3, ECR, EC2, KMS, SSM, Secrets Manager, etc. |
| **Cost** | Free (No hourly fee or data fee) | Hourly fee per ENI + Data processed fee |
| **Underlying Component** | VPC Route Table entry | Elastic Network Interface (ENI) with IP in subnet |
| **Security Control** | Route Table Association + Policy | Security Group + Subnet Attachment + Policy |
| **DNS Resolution** | Standard public endpoints | Private DNS (`enable_dns_hostnames = true`) |

---

## 2. Mandatory VPC DNS Settings

Interface Endpoints rely on AWS Private Route 53 DNS resolution. Ensure the VPC has DNS flags enabled:

```hcl
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-vpc"
    }
  )
}
```

---

## 3. Gateway Endpoint Implementation (S3 & DynamoDB)

Gateway endpoints modify route tables directly and bypass NAT Gateways for zero cost:

```hcl
resource "aws_vpc_endpoint" "s3_gateway" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"

  route_table_ids = concat(
    [aws_route_table.public.id],
    aws_route_table.private[*].id,
    [aws_route_table.database.id]
  )

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-vpce-s3-gateway"
    }
  )
}

resource "aws_vpc_endpoint" "dynamodb_gateway" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"

  route_table_ids = aws_route_table.private[*].id

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-vpce-dynamodb-gateway"
    }
  )
}
```

---

## 4. Interface Endpoint Security Group Pattern

Interface endpoints require a dedicated Security Group allowing inbound HTTPS (port 443) from internal VPC CIDRs:

```hcl
resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.environment}-vpce-sg-"
  description = "Security group for VPC Interface Endpoints"
  vpc_id      = aws_vpc.main.id

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-vpce-sg"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "vpce_https" {
  security_group_id = aws_security_group.vpc_endpoints.id
  description       = "Allow inbound HTTPS from VPC workloads"
  cidr_ipv4         = aws_vpc.main.cidr_block
  from_port         = 443
  ip_protocol       = "tcp"
  to_port           = 443
}
```

---

## 5. Interface Endpoint Declarations (e.g., ECR, KMS, Secrets Manager)

```hcl
locals {
  interface_services = {
    ecr_api = "com.amazonaws.${var.aws_region}.ecr.api"
    ecr_dkr = "com.amazonaws.${var.aws_region}.ecr.dkr"
    kms     = "com.amazonaws.${var.aws_region}.kms"
    secrets = "com.amazonaws.${var.aws_region}.secretsmanager"
    logs    = "com.amazonaws.${var.aws_region}.logs"
  }
}

resource "aws_vpc_endpoint" "interface" {
  for_each          = local.interface_services
  vpc_id            = aws_vpc.main.id
  service_name      = each.value
  vpc_endpoint_type = "Interface"

  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-vpce-${each.key}"
    }
  )
}
```

---

## 6. VPC Endpoint Policies

Restrict endpoint access using IAM resource policy documents attached to the endpoint:

```hcl
data "aws_iam_policy_document" "s3_endpoint_policy" {
  statement {
    sid    = "AllowOrgS3AccessOnly"
    effect = "Allow"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.environment}-*/*", "arn:aws:s3:::${var.environment}-*"]

    condition {
      test     = "StringEquals"
      variable = "aws:PrincipalOrgID"
      values   = [var.organization_id]
    }
  }
}

resource "aws_vpc_endpoint_policy" "s3_policy_assoc" {
  vpc_endpoint_id = aws_vpc_endpoint.s3_gateway.id
  policy          = data.aws_iam_policy_document.s3_endpoint_policy.json
}
```
