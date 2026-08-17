---
name: aws-vpc-network-patterns
description: "Architectural standards and Terraform HCL implementation patterns for AWS VPC networking, subnet tiering, routing, VPC endpoints, and security groups. Use when designing, building, or auditing AWS network infrastructure in Terraform, including: (1) Designing multi-tier VPC topologies (public, private app, isolated database), (2) Calculating dynamic subnet CIDRs using cidrsubnet(), (3) Configuring NAT Gateways, Internet Gateways, and Route Tables, (4) Setting up Gateway and Interface VPC Endpoints (PrivateLink), or (5) Authoring least-privilege security group rules and NACLs without inline rule blocks."
license: MIT
compatibility: designed for opscode
---

# AWS VPC Networking & Infrastructure Architecture

This skill provides production-grade architectural standards, network boundary definitions, and Terraform HCL implementation patterns for authoring AWS network infrastructure.

---

## Core Architectural Guardrails

1. **Strict 3-Tier Subnet Isolation**: Separate workloads into **Public**, **Private Application**, and **Isolated Database/Data** subnet tiers across at least 2 or 3 Availability Zones.
2. **Dynamic CIDR Math**: Never hardcode individual subnet CIDRs. Derive subnet ranges dynamically using Terraform's `cidrsubnet(prefix, newbits, netnum)` function.
3. **Dedicated Route Tables per AZ & Tier**: Allocate individual private route tables per AZ to support cross-AZ NAT Gateway fault isolation. Database subnets must never have routes to IGW or NAT Gateways.
4. **Standalone Security Group Rules**: Never use inline `ingress {}` or `egress {}` blocks inside `aws_security_group`. Always write standalone `aws_vpc_security_group_ingress_rule` and `aws_vpc_security_group_egress_rule` resources to prevent state drift and cycle errors.
5. **Private Connectivity First**: Prioritize Gateway Endpoints (S3, DynamoDB) and Interface Endpoints (ECR, KMS, SSM) over NAT Gateway egress for internal AWS service access.

---

## Execution Workflow

When authoring or refactoring an AWS network module in Terraform, follow these sequential steps:

### Step 1: Define Network Topology and Calculate Subnet CIDRs
- Establish primary VPC CIDR (e.g., `10.0.0.0/16`).
- Partition subnets across Availability Zones using `cidrsubnet()`.
- Tag public subnets with `kubernetes.io/role/elb = "1"` and private subnets with `kubernetes.io/role/internal-elb = "1"`.

For topology layouts, multi-AZ CIDR math, and subnet groups, see [references/topology_and_subnets.md](references/topology_and_subnets.md).

---

### Step 2: Configure Internet & NAT Gateways and Route Tables
- Create an Internet Gateway (`aws_internet_gateway`) attached to the VPC.
- Determine NAT Gateway strategy: single NAT GW for non-prod vs. per-AZ NAT GWs for high-availability production.
- Associate route tables explicitly to each subnet tier (`aws_route_table_association`).

For routing patterns, NAT strategies, and Transit Gateway attachments, see [references/routing_and_gateways.md](references/routing_and_gateways.md).

---

### Step 3: Integrate VPC Endpoints (PrivateLink)
- Enable VPC DNS options: `enable_dns_hostnames = true` and `enable_dns_support = true`.
- Attach free Gateway Endpoints for S3 and DynamoDB to all relevant route tables.
- Deploy Interface Endpoints (ECR, KMS, Secrets Manager) attached to private subnets with a dedicated endpoint Security Group.

For endpoint types, security policies, and PrivateLink setup, see [references/vpc_endpoints.md](references/vpc_endpoints.md).

---

### Step 4: Implement Security Groups & Network Boundaries
- Define tier-specific security groups: ALB SG -> Application SG -> Database SG.
- Scope rules using `referenced_security_group_id` rather than CIDR blocks wherever possible.
- Use standalone `aws_vpc_security_group_ingress_rule` and `aws_vpc_security_group_egress_rule` resources.

For tier isolation, self-referencing rules, and NACL boundaries, see [references/security_groups_and_nacls.md](references/security_groups_and_nacls.md).

---

## Quick Reference Map

| Domain / Topic | Reference Document | Key Concepts |
|---|---|---|
| **Topology & Subnets** | [topology_and_subnets.md](references/topology_and_subnets.md) | 3-Tier topology, `cidrsubnet()` math, Subnet groups, K8s tags |
| **Routing & Gateways** | [routing_and_gateways.md](references/routing_and_gateways.md) | IGW, NAT GW per AZ, Route tables, Transit Gateway (TGW) |
| **VPC Endpoints** | [vpc_endpoints.md](references/vpc_endpoints.md) | S3/DynamoDB Gateway endpoints, Interface PrivateLink, Endpoint policies |
| **Security Groups & NACLs** | [security_groups_and_nacls.md](references/security_groups_and_nacls.md) | Standalone rule resources, Referenced SGs, Tier isolation, NACLs |
