---
name: opentofu-vpc-networking
description: >
  VPC networking patterns for OpenTofu AWS modules covering VPC endpoint
  provisioning strategies, private connectivity prioritisation, Gateway endpoints
  (S3, DynamoDB), Interface endpoints (PrivateLink), and cost-aware routing
  decisions. Use when: (1) deploying aws_vpc_endpoint resources for AWS services,
  (2) distinguishing between Gateway and Interface endpoint implementations,
  (3) configuring route table associations for Gateway endpoints,
  (4) placing Interface endpoints in private subnets with security groups,
  (5) enabling private_dns_enabled for transparent SDK routing, or
  (6) optimising NAT Gateway costs via private endpoint routing.
  Do NOT use for IAM policies (use opentofu-iam-security) or encryption
  enforcement (use opentofu-data-security).
license: MIT
compatibility: designed for opscode
---

# OpenTofu VPC Networking & Endpoint Architecture

Production-grade patterns for AWS VPC networking and private service connectivity in OpenTofu, prioritising internal routing over public internet access.

---

## Core Architectural Guardrails

1. **Private Connectivity First**: Prioritise VPC endpoints over NAT Gateway egress for all internal AWS service access. NAT Gateway traffic incurs heavy data processing charges and exposes data to interception risks.
2. **Gateway Before Interface**: Always deploy free Gateway endpoints for S3 and DynamoDB before considering Interface endpoints for other services.
3. **Strict Security Groups**: VPC endpoints must have dedicated security groups. Security groups must have explicit rule descriptions and must **NEVER** open `0.0.0.0/0` ingress unless explicitly requested by the user.

---

## VPC Endpoint Types

The agent must discern between two completely distinct endpoint implementations:

### Gateway Endpoints (S3 & DynamoDB)

**How they work**: Inject managed prefix lists into route tables, directing traffic to the AWS service backbone. They do **not** use Elastic Network Interfaces and do **not** incur hourly charges.

**Configuration**: Associate the endpoint with route tables via `aws_vpc_endpoint_route_table_association`:

```hcl
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.this.id
  service_name = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
}

resource "aws_vpc_endpoint_route_table_association" "s3_private" {
  route_table_id  = aws_route_table.private.id
  vpc_endpoint_id = aws_vpc_endpoint.s3.id
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id       = aws_vpc.this.id
  service_name = "com.amazonaws.${var.region}.dynamodb"
  vpc_endpoint_type = "Gateway"
}

resource "aws_vpc_endpoint_route_table_association" "dynamodb_private" {
  route_table_id  = aws_route_table.private.id
  vpc_endpoint_id = aws_vpc_endpoint.dynamodb.id
}
```

---

### Interface Endpoints (AWS PrivateLink)

**How they work**: Create Elastic Network Interfaces (ENIs) in specified private subnets, routing traffic through the VPC's internal network fabric. They do incur hourly and data processing charges.

**Applicable services**: EC2 APIs, KMS, SNS, SQS, Secrets Manager, ECR, SSM, CloudWatch, and most other AWS services.

**Configuration**: Place in private subnets with security groups and enable private DNS:

```hcl
resource "aws_vpc_endpoint" "kms" {
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${var.region}.kms"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}

resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.project_name}-vpce-"
  vpc_id      = aws_vpc.this.id
  description = "Security group for VPC Interface endpoints"

  ingress {
    description     = "Allow HTTPS from application subnets"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    cidr_blocks     = var.private_subnet_cidrs
  }
}
```

> **Critical**: Always set `private_dns_enabled = true` on Interface endpoints. This modifies the VPC's internal DNS resolver, allowing applications to use default AWS SDK domain names while transparently routing all traffic privately through the ENIs — rather than out to the public internet.

---

## Common Interface Endpoints

Deploy these for most production workloads:

```hcl
locals {
  interface_endpoints = toset([
    "com.amazonaws.${var.region}.ec2",
    "com.amazonaws.${var.region}.ecr.api",
    "com.amazonaws.${var.region}.ecr.dkr",
    "com.amazonaws.${var.region}.kms",
    "com.amazonaws.${var.region}.secretsmanager",
    "com.amazonaws.${var.region}.ssm",
    "com.amazonaws.${var.region}.sns",
    "com.amazonaws.${var.region}.sqs",
    "com.amazonaws.${var.region}.logs",
    "com.amazonaws.${var.region}.monitoring",
  ])
}

resource "aws_vpc_endpoint" "interface" {
  for_each            = local.interface_endpoints
  vpc_id              = aws_vpc.this.id
  service_name        = each.value
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}
```

---

## Cost-Aware Routing Decision Tree

```
Need to access an AWS service from within VPC?
├── Is it S3 or DynamoDB?
│   └── YES → Deploy Gateway Endpoint (free, route table based)
├── Is it a supported Interface service?
│   └── YES → Deploy Interface Endpoint (hourly + data charges, but saves NAT costs)
└── Not supported?
    └── Route via NAT Gateway (last resort)
```
