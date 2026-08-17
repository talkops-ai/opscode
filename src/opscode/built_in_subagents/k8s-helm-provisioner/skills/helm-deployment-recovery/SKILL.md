---
name: helm-deployment-recovery
description: "Defensive Helm deployment operations and operational recovery for stuck releases. Covers atomic upgrades with --cleanup-on-fail, pre-deployment diffs via helm-diff, and deadlock resolution for pending-upgrade/pending-install/pending-rollback states via helm rollback and Kubernetes secret ledger manipulation. Use when: (1) executing helm upgrade --install with atomic and cleanup-on-fail flags, (2) previewing deployment changes via helm diff upgrade with --detailed-exitcode, (3) diagnosing releases stuck in pending-upgrade, pending-install, or pending-rollback states, or (4) performing helm rollback to recover stalled releases."
license: MIT
compatibility: designed for opscode
---

# Helm Deployment Operations & Recovery

Defensive execution patterns, pre-deployment diffing, and operational recovery for stalled or deadlocked Helm releases.

## Core Workflows & Procedures

### 1. Pre-Deployment Inspection (`helm diff`)

Always preview manifest changes before applying upgrades to prevent unintended resource mutation or secret exposure.

```bash
# Generate colorized diff with detailed exit code
export HELM_DIFF_NORMALIZE_MANIFESTS=true    # Ignore trivial formatting differences
helm diff upgrade <release-name> <chart-path> \
  --namespace <namespace> \
  --values <values-file> \
  --detailed-exitcode \
  --suppress-secrets
```

**Exit Codes:**
- `0`: No changes detected.
- `1`: Error executing diff command.
- `2`: Changes detected in target manifests.

### 2. Defensive Atomic Deployment Commands

Deploy using defensive flags (`--atomic`, `--cleanup-on-fail`, `--wait`, `--timeout`) to guarantee that failed upgrades purge orphaned resources and automatically roll back to the last deployed release.

```bash
# Execute defensive upgrade/install
helm upgrade --install <release-name> <chart-path> \
  --namespace <namespace> \
  --values <values-file> \
  --atomic \
  --cleanup-on-fail \
  --wait \
  --timeout 5m0s
```

For safe upgrade patterns, see [references/diff_and_atomic_upgrades.md](references/diff_and_atomic_upgrades.md).

### 3. Diagnosing Stuck Release States

When a release is interrupted (e.g. CI/CD pipeline termination or timeout), Helm locks the release in a `pending-*` state:
- `pending-install`: Initial installation interrupted before completion.
- `pending-upgrade`: Upgrade process interrupted during resource application.
- `pending-rollback`: Rollback operation stalled before completion.

#### Step 1: Inspect Release History & Secrets
```bash
# List release status and revision numbers
helm history <release-name> -n <namespace>

# Query release secrets in Kubernetes secret ledger
kubectl get secret -n <namespace> -l "owner=helm,name=<release-name>"
```

For step-by-step deadlock resolution and manual secret ledger recovery, see [references/deadlock_resolution.md](references/deadlock_resolution.md).

### 4. Rollback & Deadlock Resolution

#### Method A: Helm Rollback (Preferred)
Roll back to the previous successful revision:
```bash
# Roll back to specified revision (or previous revision if omitted)
helm rollback <release-name> <revision-number> \
  --namespace <namespace> \
  --wait \
  --timeout 5m0s
```

#### Method B: Unlocking Deadlocked Releases via Secret Ledger Manipulation
If `helm rollback` or `helm upgrade` fails with `another operation is in progress`:

1. Identify the secret corresponding to the stuck revision:
   ```bash
   kubectl get secret -n <namespace> -l "owner=helm,name=<release-name>,status=pending-upgrade"
   ```
2. Mark the stuck release secret as `failed` or remove the orphaned pending secret:
   ```bash
   # Option 1: Patch status from pending-upgrade to failed
   kubectl patch secret <secret-name> -n <namespace> \
     --type=json -p='[{"op": "replace", "path": "/metadata/labels/status", "value": "failed"}]'
   
   # Option 2: Delete orphaned pending secret if revision never deployed
   kubectl delete secret <secret-name> -n <namespace>
   ```
3. Re-run `helm rollback` or `helm upgrade --install`.

## Out-of-Scope Domains

Do NOT use this skill for:
- **Chart Template Authoring**: Use `helm-chart-authoring` for `Chart.yaml`, `values.yaml`, and `_helpers.tpl` structure.
- **Values Schema Validation**: Use `helm-schema-validation` for `values.schema.json`.
- **Security & Secret Encryption**: Use `helm-security-secrets` for SOPS, Vault, or security contexts.
- **Unit Testing**: Use `helm-testing` for `helm test` and unittest plugins.
