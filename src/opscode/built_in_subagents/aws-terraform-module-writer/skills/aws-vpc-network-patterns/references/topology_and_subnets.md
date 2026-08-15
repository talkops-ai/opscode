# VPC Topology and Subnet Architecture Patterns

This reference defines standard multi-tier infrastructure topologies, subnet layouts, CIDR allocation schemes, and tagging conventions for AWS network orchestration in Terraform.

---

## 1. Multi-Tier Subnet Topology

A robust AWS network architecture separates workloads into distinct isolation tiers across multiple Availability Zones (AZs):

| Tier Name | Internet Access | Default Route | Target Workloads |
|---|---|---|---|
| **Public** | Inbound & Outbound via IGW | Internet Gateway (`igw-xxxx`) | ALBs, NLBs, NAT Gateways, Bastion Hosts |
| **Private Application** | Outbound only via NAT GW | NAT Gateway (`nat-xxxx`) | ECS Tasks, EKS Worker Nodes, EC2 Application Servers |
| **Isolated Data / Database** | None (No Internet) | Local VPC Route Only | RDS Instances, ElastiCache Clusters, Redshift |
| **Transit / Edge** (Optional) | Internal / Hybrid | Transit Gateway (`tgw-xxxx`) | TGW ENIs, Firewall Appliances (GWLB) |

---

## 2. Dynamic CIDR Allocation with `cidrsubnet()`

Avoid hardcoding individual subnet CIDRs. Use Terraform's built-in `cidrsubnet(prefix, newbits, netnum)` function to dynamically partition the VPC primary CIDR block.

### CIDR Partitioning Calculation Example
For a `/16` VPC CIDR (e.g., `10.0.0.0/16`) and 3 AZs:
- **Public Subnets**: `newbits = 8` (`/24` per AZ -> `10.0.0.0/24`, `10.0.1.0/24`, `10.0.2.0/24`)
- **Private Subnets**: `newbits = 4` (`/20` per AZ -> `10.0.16.0/20`, `10.0.32.0/20`, `10.0.48.0/20`)
- **Database Subnets**: `newbits = 8` (`/24` per AZ -> `10.0.64.0/24`, `10.0.65.0/24`, `10.0.66.0/24`)

```hcl
locals {
  az_count = length(var.availability_zones)

  public_subnet_cidrs = [
    for idx in range(local.az_count) : cidrsubnet(var.vpc_cidr, 8, idx)
  ]

  private_subnet_cidrs = [
    for idx in range(local.az_count) : cidrsubnet(var.vpc_cidr, 4, idx + 1)
  ]

  database_subnet_cidrs = [
    for idx in range(local.az_count) : cidrsubnet(var.vpc_cidr, 8, idx + 64)
  ]
}
```

---

## 3. Subnet Resource Declarations

```hcl
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = local.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(
    var.tags,
    {
      Name                                = "${var.environment}-public-${var.availability_zones[count.index]}"
      Type                                = "Public"
      "kubernetes.io/role/elb"            = "1"
    }
  )
}

resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = local.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(
    var.tags,
    {
      Name                                = "${var.environment}-private-${var.availability_zones[count.index]}"
      Type                                = "Private"
      "kubernetes.io/role/internal-elb"   = "1"
    }
  )
}

resource "aws_subnet" "database" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = local.database_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-database-${var.availability_zones[count.index]}"
      Type = "Database"
    }
  )
}
```

---

## 4. Subnet Group Associations

For managed AWS services like RDS and ElastiCache, define dedicated subnet groups attached exclusively to the isolated database tier:

```hcl
resource "aws_db_subnet_group" "database" {
  name        = "${var.environment}-db-subnet-group"
  description = "Database subnet group for ${var.environment}"
  subnet_ids  = aws_subnet.database[*].id

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-db-subnet-group"
    }
  )
}
```

---

## 5. IPv6 Dual-Stack Support (Optional)

When IPv6 capability is required:
1. Enable `assign_generated_ipv6_cidr_block = true` on the `aws_vpc` resource.
2. Slice the `/56` assigned IPv6 block into `/64` subnets using `cidrsubnet(aws_vpc.main.ipv6_cidr_block, 8, count.index)`.
