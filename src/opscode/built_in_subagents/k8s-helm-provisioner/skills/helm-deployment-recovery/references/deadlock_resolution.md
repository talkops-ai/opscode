# Helm Deadlock Resolution & Secret Ledger Recovery

Detailed guide for resolving `pending-install`, `pending-upgrade`, and `pending-rollback` states.

## 1. How Helm Stores Release State

Helm v3 stores release metadata in Kubernetes Secrets in the release namespace.
Secret name pattern: `sh.helm.release.v1.<release-name>.v<revision>`
Secret labels:
- `owner`: `helm`
- `name`: `<release-name>`
- `status`: `deployed` | `failed` | `pending-install` | `pending-upgrade` | `pending-rollback` | `superseded`

When an operation begins, Helm creates a secret with status `pending-*`. If the command crashes or is aborted before completion, the lock secret remains in `pending-*` state, blocking future operations with the error:
`Error: another operation is in progress`

## 2. Step-by-Step Recovery Procedure

### Step 1: Identify Stuck Secret
```bash
kubectl get secret -n <namespace> -l "owner=helm,name=<release-name>" --sort-by='.metadata.creationTimestamp'
```

Look for secrets where `STATUS` column shows `pending-upgrade`, `pending-install`, or `pending-rollback`.

### Step 2: Choose Recovery Strategy

#### Strategy A: Mark Pending Secret as Failed (Safest)
Patching the label changes the release status from pending to failed, allowing Helm to run rollbacks or upgrades again.

```bash
STUCK_SECRET=$(kubectl get secret -n <namespace> -l "owner=helm,name=<release-name>,status=pending-upgrade" -o jsonpath='{.items[0].metadata.name}')

kubectl patch secret $STUCK_SECRET -n <namespace> \
  --type=json -p='[{"op": "replace", "path": "/metadata/labels/status", "value": "failed"}]'
```

#### Strategy B: Delete Interrupted Secret (For Clean Uninstalls / Retries)
If an initial `helm install` stuck in `pending-install` and left partial resources:

```bash
# Delete pending secret
kubectl delete secret <stuck-secret-name> -n <namespace>

# Clean up remaining orphaned resources if necessary
kubectl delete deployment,service,ingress -l "app.kubernetes.io/managed-by=Helm,app.kubernetes.io/instance=<release-name>" -n <namespace>
```

### Step 3: Trigger Rollback or Safe Re-install
Once the pending lock is cleared:

```bash
# Rollback to last known deployed revision
helm rollback <release-name> <last-good-revision> -n <namespace> --wait --timeout 5m0s
```
