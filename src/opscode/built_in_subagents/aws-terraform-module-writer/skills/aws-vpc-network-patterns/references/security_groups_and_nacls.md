# Security Group and Network ACL Guardrails

This reference provides Terraform best practices for Security Group rule modularity, tier-based traffic scoping, self-referencing cluster rules, and Network ACL (NACL) configurations.

---

## 1. Security Group Rule Resource Modularity

### CRITICAL: Avoid Inline Ingress / Egress Blocks
Never write `ingress {}` or `egress {}` blocks directly inside the `aws_security_group` resource.
Inline rules cause state drift, prevent rule modularity, and create cyclic dependencies when security groups reference each other.

**Always use standalone rule resources:**
- `aws_vpc_security_group_ingress_rule`
- `aws_vpc_security_group_egress_rule`

---

## 2. Tier-to-Tier Security Group Isolation Architecture

Implement strict least-privilege flow across network tiers:

```
[ Internet ]
     | (Port 80/443)
     v
[ Public ALB SG ]
     | (Port 8080/8000 referenced SG)
     v
[ App Server / Container SG ]
     | (Port 5432/3306 referenced SG)
     v
[ Isolated Database SG ]
```

---

## 3. Terraform HCL Security Group Tier Implementation

### Public Load Balancer Security Group

```hcl
resource "aws_security_group" "alb" {
  name_prefix = "${var.environment}-alb-sg-"
  description = "Public ALB Security Group"
  vpc_id      = aws_vpc.main.id

  tags = merge(var.tags, { Name = "${var.environment}-alb-sg" })

  lifecycle { create_before_destroy = true }
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  description       = "Allow inbound HTTPS from Internet"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  ip_protocol       = "tcp"
  to_port           = 443
}

resource "aws_vpc_security_group_egress_rule" "alb_to_app" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Allow egress from ALB to Application workloads"
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 8080
  ip_protocol                  = "tcp"
  to_port                      = 8080
}
```

---

### Application Workload Security Group

```hcl
resource "aws_security_group" "app" {
  name_prefix = "${var.environment}-app-sg-"
  description = "Application Workload Security Group"
  vpc_id      = aws_vpc.main.id

  tags = merge(var.tags, { Name = "${var.environment}-app-sg" })

  lifecycle { create_before_destroy = true }
}

resource "aws_vpc_security_group_ingress_rule" "app_from_alb" {
  security_group_id            = aws_security_group.app.id
  description                  = "Allow traffic only from Public ALB SG"
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 8080
  ip_protocol                  = "tcp"
  to_port                      = 8080
}

# Self-referencing rule for container-to-container / mesh service discovery
resource "aws_vpc_security_group_ingress_rule" "app_self" {
  security_group_id            = aws_security_group.app.id
  description                  = "Allow intra-tier communication within application SG"
  referenced_security_group_id = aws_security_group.app.id
  ip_protocol                  = "-1"
}

resource "aws_vpc_security_group_egress_rule" "app_to_db" {
  security_group_id            = aws_security_group.app.id
  description                  = "Allow traffic from App to Database SG"
  referenced_security_group_id = aws_security_group.database.id
  from_port                    = 5432
  ip_protocol                  = "tcp"
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "app_https_out" {
  security_group_id = aws_security_group.app.id
  description       = "Allow outbound HTTPS for API and VPC Endpoint communication"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  ip_protocol       = "tcp"
  to_port           = 443
}
```

---

### Database / Storage Security Group

```hcl
resource "aws_security_group" "database" {
  name_prefix = "${var.environment}-db-sg-"
  description = "Isolated Database Security Group"
  vpc_id      = aws_vpc.main.id

  tags = merge(var.tags, { Name = "${var.environment}-db-sg" })

  lifecycle { create_before_destroy = true }
}

resource "aws_vpc_security_group_ingress_rule" "db_from_app" {
  security_group_id            = aws_security_group.database.id
  description                  = "Allow PostgreSQL access strictly from App SG"
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 5432
  ip_protocol                  = "tcp"
  to_port                      = 5432
}

# Explicitly no egress rule required for database tier (or restrict to local VPC)
```

---

## 4. Network Access Control Lists (NACLs) vs Security Groups

| Metric | Security Groups | Network ACLs (NACLs) |
|---|---|---|
| **Operates At** | Instance / ENI Level | Subnet Boundary Level |
| **Statefulness** | Stateful (Return traffic automatically allowed) | Stateless (Inbound & Outbound rules required explicitly) |
| **Evaluation Order** | Evaluates all rules before deciding | Processed in strict rule number order (100, 200, 300...) |
| **Rule Types** | Allow rules only | Allow and Deny rules |

---

## 5. Explicit Deny NACL Pattern for Isolated Subnets

```hcl
resource "aws_network_acl" "database" {
  vpc_id     = aws_vpc.main.id
  subnet_ids = aws_subnet.database[*].id

  # Rule 100: Allow inbound PostgreSQL from App subnets
  ingress {
    action     = "allow"
    cidr_block = aws_vpc.main.cidr_block
    from_port  = 5432
    protocol   = "tcp"
    rule_no    = 100
    to_port    = 5432
  }

  # Rule 100: Allow ephemeral return ports to App subnets
  egress {
    action     = "allow"
    cidr_block = aws_vpc.main.cidr_block
    from_port  = 1024
    protocol   = "tcp"
    rule_no    = 100
    to_port    = 65535
  }

  tags = merge(var.tags, { Name = "${var.environment}-database-nacl" })
}
```
