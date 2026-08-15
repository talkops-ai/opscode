# Kubernetes Security Audit & Execution Safety

## 1. Pod Security Standards (Restricted Profile)

Ensure pod security contexts comply with the Kubernetes **Restricted** Pod Security Standard:

- `runAsNonRoot: true`: Prevent running as root user.
- `allowPrivilegeEscalation: false`: Prevent child processes from gaining elevated permissions.
- `readOnlyRootFilesystem: true`: Root filesystem mounted read-only; write temporary files to `/tmp` via `emptyDir`.
- `capabilities.drop: ["ALL"]`: Drop all default Linux capabilities.
- `seccompProfile.type: RuntimeDefault`: Enforce default seccomp profile.

---

## 2. Manifest Security Audit Checklist

When reviewing Kubernetes manifests for security and reliability:

1. **Resource Limits**: Ensure `resources.requests` and `resources.limits` are explicitly configured for all containers.
2. **Probes**: Confirm `livenessProbe` and `readinessProbe` are defined.
3. **RBAC Scope**: Verify `ClusterRoleBinding` is not used where `RoleBinding` within a namespace suffices.
4. **ServiceAccount Tokens**: Set `automountServiceAccountToken: false` unless the workload explicitly queries the Kubernetes API server.
5. **Image Tags**: Avoid `:latest` tag; require immutable tags or digest SHAs (`@sha256:...`).

---

## 3. Kubectl Pre-Flight & Dry-Run Guardrails

Always test manifest changes before applying to live clusters:

```bash
# 1. Client-side dry-run (Syntax and structure check)
kubectl apply -k k8s/overlays/prod --dry-run=client

# 2. Server-side dry-run (Admission control and schema validation)
kubectl apply -k k8s/overlays/prod --dry-run=server

# 3. Diff inspection against live cluster
kubectl diff -k k8s/overlays/prod
```
