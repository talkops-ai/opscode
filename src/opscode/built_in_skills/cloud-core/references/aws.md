# AWS Baseline Primitives & Guardrails

## 1. IAM Least-Privilege Policies

### Guiding Principles
- Avoid wildcard permissions (`"Action": "*"`, `"Resource": "*"`) in policy statements.
- Scope actions to specific ARN patterns and enforce boundary conditions via condition keys (`aws:PrincipalOrgID`, `aws:SourceVpc`, `aws:ViaAWSService`).
- Use Role Assumptions (`sts:AssumeRole`) with explicit External ID or Session Tags for cross-account or sub-system access.

### Example Least-Privilege IAM Policy (Application Worker)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3ObjectReadWriteScoped",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::app-data-bucket-prod-12345",
        "arn:aws:s3:::app-data-bucket-prod-12345/*"
      ]
    },
    {
      "Sid": "KMSKeyDecryptScoped",
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
    }
  ]
}
```

---

## 2. VPC Networking Topology

### Standard Multi-AZ Architecture
- **CIDR Block**: `/16` overall (e.g., `10.0.0.0/16`) split across 3 Availability Zones.
- **Public Subnets**: High-level ingress only (ALB, Bastion/NAT Gateway). `/24` per AZ.
- **Private Subnets (App)**: Application workloads and compute instances. Egress via NAT Gateway. `/20` per AZ.
- **Database Subnets (Isolated)**: Databases and storage services. No internet ingress/egress. `/24` per AZ.

### Security Group Defaults
- **Ingress**: Deny all by default. Open required ports specifically scoped to peer Security Groups or VPC CIDR.
- **Egress**: Restrict egress to required service endpoints or private subnet ranges where applicable.

---

## 3. Secure Compute

### Instance Profile Security
- EC2 instances and EKS nodes must run with IAM Instance Profiles tied to scoped roles.
- Never hardcode IAM access keys or credentials inside compute instances or user-data scripts.
- Enforce IMDSv2 (Instance Metadata Service v2) with `HttpTokens=required` and `HttpPutResponseHopLimit=1`.

### Security Group Ingress Rule Example
```hcl
# Example Terraform snippet for secure security group ingress
resource "aws_security_group_rule" "ingress_app_from_alb" {
  type                     = "ingress"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  security_group_id        = aws_security_group.app.id
  source_security_group_id = aws_security_group.alb.id
  description              = "Allow traffic from ALB to App tier only"
}
```

---

## 4. AWS CLI Guardrails

### Dry-Run & Simulation Flags
- Always pass `--dry-run` to EC2 CLI commands before executing mutations (e.g., `aws ec2 run-instances --dry-run ...`, `aws ec2 authorize-security-group-ingress --dry-run ...`).
- Use `aws iam simulate-principal-policy` to verify policy permissions before attaching to roles.

### High-Risk Command Interceptions
- **Destructive Deletions**: Prompt and require explicit confirmation for `aws s3 rb --force`, `aws ec2 terminate-instances`, `aws rds delete-db-instance`, `aws dynamodb delete-table`.
- **Credential Hygiene**: Verify active AWS identity via `aws sts get-caller-identity` before executing commands to ensure target account alignment.
