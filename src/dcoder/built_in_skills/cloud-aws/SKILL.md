---
name: cloud-aws
description: "AWS CLI operations, IAM policies, and CloudFormation/CDK patterns"
domain: DevOps
compatibility: "aws-cli >= 2.15"
allowed_tools:
  - execute
  - write_file
  - read_file
metadata:
  domain: cloud-aws
  difficulty: intermediate
---

# AWS Cloud Skill

You are an expert AWS cloud engineer. Follow these guidelines for AWS CLI, IAM, and infrastructure patterns.

## IAM Policies

Always follow **least privilege**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::my-bucket/prefix/*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    }
  ]
}
```

- Use `Condition` blocks to restrict by region, IP, MFA, etc.
- Prefer managed policies over inline policies.
- Use `aws:PrincipalTag` conditions for ABAC (attribute-based access control).
- Never use `*` for both Action and Resource.

## Common CLI Patterns

```bash
# List resources with JMESPath filtering
aws ec2 describe-instances --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name,Type:InstanceType}' --output table

# Assume a role
eval $(aws sts assume-role --role-arn arn:aws:iam::123456789012:role/MyRole --role-session-name MySession --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' --output text | awk '{printf "export AWS_ACCESS_KEY_ID=%s AWS_SECRET_ACCESS_KEY=%s AWS_SESSION_TOKEN=%s", $1, $2, $3}')

# S3 sync with delete
aws s3 sync ./build/ s3://my-bucket/static/ --delete --exclude "*.tmp"
```

## Key Services

| Service | Use Case |
|---------|----------|
| EC2 | Compute instances, auto-scaling groups |
| ECS/Fargate | Container orchestration |
| Lambda | Serverless functions |
| S3 | Object storage, static hosting |
| RDS/Aurora | Managed relational databases |
| DynamoDB | NoSQL key-value/document store |
| CloudFront | CDN and edge caching |
| Route 53 | DNS management |
| VPC | Network isolation and security groups |
| EKS | Managed Kubernetes |

## Security Best Practices

- Enable CloudTrail for audit logging.
- Use AWS Organizations and SCPs for account guardrails.
- Enable GuardDuty for threat detection.
- Rotate credentials regularly — prefer IAM Roles over static keys.
- Use AWS Secrets Manager or SSM Parameter Store for secrets.
- Enable default encryption on S3 buckets, EBS volumes, and RDS.
- Use VPC endpoints for private AWS service access.

## CloudFormation Tips

- Use `!Ref`, `!Sub`, and `!GetAtt` for dynamic references.
- Enable `DeletionPolicy: Retain` on stateful resources.
- Use `AWS::CloudFormation::StackSet` for multi-account/region deployments.
- Validate templates: `aws cloudformation validate-template --template-body file://template.yaml`.
