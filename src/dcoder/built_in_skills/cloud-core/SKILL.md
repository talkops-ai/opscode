---
name: cloud-core
description: "Baseline multi-cloud primitives across AWS, Azure, and GCP: IAM least-privilege policies, VPC/VNet networking, secure compute, and CLI execution guardrails. Use when designing, reviewing, or implementing multi-cloud infrastructure primitives for: (1) IAM least-privilege policies and role design across AWS/Azure/GCP, (2) VPC, VNet, and Cloud VPC network topologies, (3) Secure compute instances and security groups/firewalls, or (4) CLI execution guardrails and dry-run safety."
license: MIT
compatibility: designed for deepagents-code
---

# Cloud Core (Multi-Cloud Primitives & Guardrails)

Standard baseline patterns and safety guardrails across AWS, Azure, and GCP for identity, networking, compute, and execution safety.

## Quick Workflow

1. **Identify the Cloud Provider**: Determine whether the target task targets AWS, Azure, or GCP.
2. **Apply Identity Least-Privilege**: Design or review IAM roles/policies without wildcards (`*`) using scoped resources and condition keys.
3. **Establish Network Topology**: Implement multi-tier subnets (public/private/database) with explicit ingress/egress boundaries.
4. **Harden Compute Security**: Enforce workload identity / instance profiles, disable public IPs where possible, and use IMDSv2 / Shielded VMs.
5. **Run CLI Pre-flight Guardrails**: Validate target identity and run dry-run simulations before executing mutating commands.

---

## Provider Reference Manuals

Read the provider-specific guide corresponding to the target cloud platform:

- **AWS Primitives**: See [references/aws.md](references/aws.md) for IAM least-privilege policy templates, 3-AZ VPC topology, IMDSv2 compute hardening, and `aws` CLI dry-run flags.
- **Azure Primitives**: See [references/azure.md](references/azure.md) for custom RBAC roles, VNet/NSG subnet delegation, Managed Identities, and `az` CLI `--what-if` previews.
- **GCP Primitives**: See [references/gcp.md](references/gcp.md) for GCP IAM custom roles, Custom Mode VPC with Cloud NAT, Workload Identity, and `gcloud` CLI guardrails.
- **CLI Guardrails & Pre-Flight Checks**: See [references/guardrails.md](references/guardrails.md) for multi-cloud command safety matrices, identity verification, and execution checklists.

---

## Universal Multi-Cloud Guardrail Checklist

Execute these verification steps whenever performing infra modifications or executing cloud CLI commands:

- [ ] **Identity Alignment**: Verify current cloud credentials point to the intended target environment (account/subscription/project).
- [ ] **Least Privilege Scope**: Ensure IAM roles and policy statements do not contain unconstrained wildcard actions or resources.
- [ ] **Private Connectivity**: Confirm compute resources run in private subnets with egress via NAT gateways/Cloud NAT and ingress restricted by security groups or NSGs.
- [ ] **Dry-Run Validation**: Run `--dry-run`, `--what-if`, or plan previews prior to executing mutating or destructive operations.
