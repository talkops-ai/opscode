---
name: kubernetes
description: "Create, audit, and manage Kubernetes manifests, Kustomize overlays, and cluster resources. Use when authoring, reviewing, or managing Kubernetes artifacts for: (1) Production-grade Deployment, Service, Ingress, and NetworkPolicy manifests, (2) Kustomize base and overlay configurations across environments (dev/staging/prod), (3) Pod Security Standards and manifest security auditing, or (4) Kubectl pre-flight dry-run and diff workflows."
license: MIT
compatibility: designed for opscode
---

# Kubernetes Manifests, Kustomize Overlays & Resource Management

Guidelines for authoring, auditing, and managing production Kubernetes manifests, Kustomize overlay structures, and cluster resources safely.

## Quick Workflow

1. **Manifest Authoring**: Structure workload manifests (Deployments, Services, Ingress, NetworkPolicies) using explicit API versions, resource requests/limits, health probes, and non-root security contexts.
2. **Environment Overlays via Kustomize**: Keep common resource definitions in `base/` and manage environment-specific variations (namespaces, replicas, resource patches, image tags) in `overlays/<env>/`.
3. **Security Auditing**: Enforce Pod Security Standards (Restricted profile) with `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, and `runAsNonRoot: true`.
4. **Pre-flight Dry-Run Guardrails**: Always run `kubectl diff` or `kubectl apply --dry-run=server` prior to applying changes to a cluster.

---

## Detailed References

- **Manifest Patterns**: See [references/manifest-patterns.md](references/manifest-patterns.md) for production Deployments, Services, TLS Ingress, and NetworkPolicies.
- **Kustomize Overlays**: See [references/kustomize-overlays.md](references/kustomize-overlays.md) for base/overlay directory layouts, Strategic Merge Patches, image overrides, and configMapGenerators.
- **Security Audit & Dry-Run**: See [references/security-audit.md](references/security-audit.md) for Pod Security Standards, RBAC auditing, and `kubectl` dry-run commands.

---

## Kubernetes Production Checklist

- [ ] **Resource Isolation**: Explicit `cpu` and `memory` requests and limits set on all containers.
- [ ] **Probes**: `livenessProbe` and `readinessProbe` configured with appropriate timeouts and initial delays.
- [ ] **Restricted Security Context**: `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, and `readOnlyRootFilesystem: true`.
- [ ] **Network Segmentation**: Default-deny NetworkPolicies configured to restrict pod ingress and egress.
- [ ] **Tag Immutability**: Container images use explicit version tags or digest SHAs (no `:latest`).
- [ ] **Server-Side Dry-Run**: Manifests tested against target cluster admission controllers using `kubectl apply --dry-run=server`.
