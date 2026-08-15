# GCP Baseline Primitives & Guardrails

## 1. IAM Least-Privilege Policies

### Guiding Principles
- Prefer GCP Custom Roles over predefined primitive roles (`roles/owner`, `roles/editor`, `roles/viewer`).
- Bind permissions to Service Accounts attached directly to GCP workloads.
- Enforce Workload Identity Federation for external CI/CD pipelines instead of downloading long-lived Service Account JSON keys.

### Example Custom Role Definition (GCP YAML)
```yaml
title: "Scoped Application Reader & PubSub Publisher"
description: "Minimal role for microservice app tier"
stage: "GA"
includedPermissions:
  - storage.objects.get
  - storage.objects.list
  - pubsub.topics.publish
  - logging.logEntries.create
```

---

## 2. VPC Network Topology

### Custom Mode VPC Architecture
- Create VPCs in **Custom Mode** (disable automatic subnet creation).
- **Subnet Segmentation**: Separate subnets per region (e.g., `10.2.0.0/20` in `us-central1` for primary compute).
- **Secondary Range Allocation**: Dedicated secondary CIDR ranges for GKE Pods and Services.
- **Private Google Access**: Enable Private Google Access on all internal subnets so instances without public IPs can reach Google APIs safely.
- **Cloud NAT**: Provision Cloud NAT for outbound internet connectivity from private compute instances.

### Firewall Rules
- Ingress: Deny all ingress rules with lower priority (higher priority number e.g. 65534). Explicit allow rules targeted by Network Tags or Service Account principal bindings.
- Egress: Restrict egress where compliance mandates it.

---

## 3. Secure Compute

### Service Accounts & Instance Security
- Attach dedicated Service Accounts with minimal IAM roles to Compute Engine instances or GKE ServiceAccounts (via Workload Identity).
- Disable External IP addresses (`natIP` omitted) on Compute instances; access via IAP (Identity-Aware Proxy) tunnel for SSH.
- Enforce Shielded VMs (`enableSecureBoot: true`, `enableVtpm: true`).

---

## 4. gcloud CLI Guardrails

### Dry-Run & Simulation Flags
- Use `--dry-run` or preview mode on supported gcloud commands (e.g. `gcloud compute instances create ... --dry-run`).
- Use `gcloud asset analyze-iam-policy` to inspect permission trees and simulate access.

### High-Risk Command Interceptions
- **Destructive Deletions**: Prompt and confirm before executing `gcloud projects delete`, `gcloud compute instances delete`, `gcloud container clusters delete`, `gcloud sql instances delete`.
- **Identity Check**: Verify current active account and project via `gcloud config get-value project` and `gcloud auth list`.
