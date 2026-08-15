---
name: aws-iam-policy-engine
description: "Comprehensive guidance and HCL standards for constructing secure, composable, service-level AWS resource policies (S3, KMS, SNS, SQS, ECR, Secrets Manager) in Terraform. Use when generating, auditing, or refactoring AWS service-level IAM resource policies for: (1) Same-account, cross-account, or AWS Organization access control, (2) Converting raw JSON/heredoc policies to native aws_iam_policy_document HCL data sources, (3) Implementing least privilege rules, SSL enforcement (aws:SecureTransport), and ABAC tag conditions, (4) Protecting against Confused Deputy attacks using aws:SourceArn and aws:SourceAccount, or (5) Designing dynamic policy statements using HCL dynamic statement blocks."
license: MIT
compatibility: designed for deepagents-code
---

# AWS IAM Policy Engine

This skill provides architectural standards, guardrails, and HCL execution patterns for authoring AWS service-level resource policies in Terraform using `aws_iam_policy_document`.

---

## Core Principles

1. **Native HCL Data Sources over Raw JSON**: Never write raw JSON strings, `jsonencode()`, or heredoc template files for IAM policies. Always use `aws_iam_policy_document` for compile-time validation, type safety, and composability.
2. **Explicit Deny Guardrails**: Enforce mandatory security baselines (such as SSL/TLS enforcement via `aws:SecureTransport: false`) using explicit Deny statements.
3. **Confused Deputy Protection**: When granting access to AWS service principals (`type = "Service"`), always enforce `aws:SourceArn` and/or `aws:SourceAccount` conditions.
4. **Organization-Wide Boundary Scoping**: Restrict cross-account or public access using `aws:PrincipalOrgID` or `aws:PrincipalOrgPaths` rather than open `*` principals.
5. **Action Minimization**: Avoid wildcards (`*`) in actions. Restrict permissions strictly to required API operations.

---

## Execution Workflow

When constructing or refactoring an AWS resource policy in Terraform, follow these steps:

### Step 1: Identify Access Scoping Tier
Determine the required accessibility scope:
- **Same Account**: Scope principal to exact IAM role ARNs or account root.
- **Cross-Account**: Specify trusted account root or foreign role ARNs.
- **AWS Organization**: Use `identifiers = ["*"]` combined with `aws:PrincipalOrgID` condition.
- **Service Principal**: Use `type = "Service"` combined with `aws:SourceArn` / `aws:SourceAccount`.

For detailed access scoping rules and AWS Organization guardrails, see [references/access_scoping_and_orgs.md](references/access_scoping_and_orgs.md).

---

### Step 2: Enforce Mandatory Security Baselines
Inject explicit Deny statements to ensure security baselines cannot be bypassed by Allow statements:
- **SSL Enforcement**: Deny any request where `aws:SecureTransport` is `false`.
- **Server-Side Encryption**: Deny unencrypted uploads for storage resources (S3).

For guardrail patterns, explicit Deny rules, and ABAC tagging conditions, see [references/least_privilege_and_abac.md](references/least_privilege_and_abac.md).

---

### Step 3: Author Policy using `aws_iam_policy_document`
Construct the policy using HCL data sources:
- Use `source_policy_documents` to merge reusable base security policies.
- Use `override_policy_documents` to customize or override specific statement SIDs.
- Use `dynamic "statement"` blocks for conditional policy statements driven by module variables.

For HCL data source patterns, policy merging, and dynamic statement syntax, see [references/hcl_policy_documents.md](references/hcl_policy_documents.md).

---

### Step 4: Apply Service-Specific Policy Patterns
Refer to production-tested service policy templates:
- **S3 Bucket Policies**: Public access block integration, SSL enforcement, Org restrictions.
- **KMS Key Policies**: Account root delegation (`kms:*`), KMS admin vs user separation.
- **SNS & SQS Policies**: Service notifications, S3/EventBridge event conditions.
- **ECR Repository Policies**: Cross-account image pull/push policies.

For service-specific policy templates, see [references/service_policy_patterns.md](references/service_policy_patterns.md).

---

## Quick Reference Map

| Resource / Topic | Reference Document | Key Concepts |
|---|---|---|
| **Access Scoping & Orgs** | [access_scoping_and_orgs.md](references/access_scoping_and_orgs.md) | Same-account, Cross-account, `aws:PrincipalOrgID`, Confused Deputy |
| **HCL Policy Documents** | [hcl_policy_documents.md](references/hcl_policy_documents.md) | `aws_iam_policy_document`, `override_policy_documents`, `dynamic "statement"` |
| **Least Privilege & ABAC** | [least_privilege_and_abac.md](references/least_privilege_and_abac.md) | `aws:SecureTransport`, `aws:ResourceTag`, `aws:PrincipalTag`, Explicit Deny |
| **Service Policy Patterns** | [service_policy_patterns.md](references/service_policy_patterns.md) | S3, KMS Key Policies, SNS, SQS, ECR Repository Policies |
