# AWS Routing, Gateways, and Egress Architecture

This reference covers routing design, Internet Gateways (IGW), NAT Gateway strategies, Egress-Only Internet Gateways (EOIGW), Route Table management, and Transit Gateway (TGW) attachments in Terraform.

---

## 1. Gateway Patterns and Trade-Offs

### Internet Gateway (IGW)
- Attaches directly to the VPC.
- Provides target for public subnet route tables (`0.0.0.0/0 -> igw-xxxx`).
- Required for public-facing resources and NAT Gateways.

### NAT Gateway Strategies
Select the appropriate deployment model based on cost and availability requirements:

| Model | Count | Availability | Use Case | Cost Impact |
|---|---|---|---|---|
| **Single NAT Gateway** | 1 | Single AZ failure risk | Non-Production / Staging | Low ($32/mo + data transfer) |
| **NAT per AZ** | 1 per AZ (e.g., 3) | High Availability / Fault Isolation | Production Workloads | Medium-High ($96+/mo) |
| **No NAT Gateway** | 0 | Air-gapped / VPC Endpoint only | High-Security Isolated VPCs | Minimal (VPC Endpoints only) |

---

## 2. Route Table Architecture in Terraform

To maintain clean route boundaries, create separate route tables for each tier and AZ.

### Public Route Table (Shared across Public Subnets)

```hcl
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-igw"
    }
  )
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-public-rt"
    }
  )
}

resource "aws_route" "public_internet_access" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
```

---

### Private Route Tables (Per-AZ NAT Gateway Integration)

For production environments, allocate one Elastic IP (EIP) and NAT Gateway per AZ to ensure cross-AZ fault isolation:

```hcl
resource "aws_eip" "nat" {
  count  = var.single_nat_gateway ? 1 : length(var.availability_zones)
  domain = "vpc"

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-nat-eip-${count.index}"
    }
  )

  depends_on = [aws_internet_gateway.main]
}

resource "aws_nat_gateway" "main" {
  count         = var.single_nat_gateway ? 1 : length(var.availability_zones)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-nat-gw-${count.index}"
    }
  )

  depends_on = [aws_internet_gateway.main]
}

resource "aws_route_table" "private" {
  count  = length(var.availability_zones)
  vpc_id = aws_vpc.main.id

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-private-rt-${var.availability_zones[count.index]}"
    }
  )
}

resource "aws_route" "private_nat_gateway" {
  count                  = length(var.availability_zones)
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main[var.single_nat_gateway ? 0 : count.index].id
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}
```

---

### Isolated Database Route Tables (Local Only)

The database tier must not have default routes to IGW or NAT Gateway:

```hcl
resource "aws_route_table" "database" {
  vpc_id = aws_vpc.main.id

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-database-rt"
    }
  )
}

resource "aws_route_table_association" "database" {
  count          = length(aws_subnet.database)
  subnet_id      = aws_subnet.database[count.index].id
  route_table_id = aws_route_table.database.id
}
```

---

## 3. Transit Gateway (TGW) Integration Pattern

When connecting the VPC to a hub-and-spoke enterprise topology via Transit Gateway:

```hcl
resource "aws_ec2_transit_gateway_vpc_attachment" "this" {
  count              = var.enable_transit_gateway ? 1 : 0
  transit_gateway_id = var.transit_gateway_id
  vpc_id             = aws_vpc.main.id
  subnet_ids         = aws_subnet.private[*].id

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-tgw-attachment"
    }
  )
}

resource "aws_route" "corporate_network" {
  count                  = var.enable_transit_gateway ? length(aws_route_table.private) : 0
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = var.corporate_network_cidr # e.g., "10.0.0.0/8"
  transit_gateway_id     = var.transit_gateway_id
}
```
