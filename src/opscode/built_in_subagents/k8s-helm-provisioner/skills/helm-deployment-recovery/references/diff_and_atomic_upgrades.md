# Defensive Upgrade & Pre-Deployment Diffing Guide

Comprehensive guide to pre-deployment verification with `helm-diff` and atomic upgrade flags.

## 1. Pre-Deployment Verification with `helm-diff`

The `helm-diff` plugin provides clear visual diffs between currently deployed manifests and pending chart changes.

### Installation
```bash
helm plugin install https://github.com/databus23/helm-diff || true
```

### Essential Diff Flags
- `--detailed-exitcode`: Returns exit code `2` when diffs exist. Essential for CI/CD automation pipelines.
- `--suppress-secrets`: Hides secret values in diff output to prevent leaking credentials in terminal or build logs.
- `--context N`: Limits diff context to N lines around changes.

### Environment Variables
- `HELM_DIFF_NORMALIZE_MANIFESTS=true`: Ignores trivial stylistic and formatting differences (e.g. label ordering, whitespace) — shows only semantic changes. **Always set this.**

```bash
export HELM_DIFF_NORMALIZE_MANIFESTS=true
helm diff upgrade my-release ./my-chart \
  --namespace my-namespace \
  --values values-prod.yaml \
  --detailed-exitcode \
  --suppress-secrets \
  --context 3
```

## 2. Atomic Upgrades & Failure Cleanup Flags

### Flag Breakdown

| Flag | Purpose |
|------|---------|
| `--atomic` | Automatically triggers a rollback if the upgrade fails or times out. Implies `--wait`. |
| `--cleanup-on-fail` | Purges any new resources created during a failed upgrade attempt. |
| `--wait` | Waits until all Pods, PVCs, Services, and Deployments are in `Ready` state before returning. |
| `--timeout <duration>` | Specifies maximum wait time before marking deployment failed (default: `5m0s`). |

### Standard Defensive Command
```bash
helm upgrade --install my-app ./my-chart \
  --namespace my-namespace \
  --values values.yaml \
  --atomic \
  --cleanup-on-fail \
  --wait \
  --timeout 5m0s
```
