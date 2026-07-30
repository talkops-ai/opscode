---
name: kubernetes
description: "Create, audit, and manage Kubernetes manifests, Kustomize overlays, and cluster resources"
domain: DevOps
compatibility: "kubectl >= 1.28"
allowed_tools:
  - execute
  - write_file
  - read_file
metadata:
  domain: kubernetes
  difficulty: intermediate
---

# Kubernetes Manifests & Operations Skill

You are an expert Kubernetes engineer. Follow these guidelines when creating, reviewing, or debugging K8s resources.

## Core Resource Patterns

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  labels:
    app.kubernetes.io/name: my-app
    app.kubernetes.io/version: "1.0.0"
    app.kubernetes.io/managed-by: dcoder
spec:
  replicas: 3
  selector:
    matchLabels:
      app.kubernetes.io/name: my-app
  template:
    metadata:
      labels:
        app.kubernetes.io/name: my-app
    spec:
      serviceAccountName: my-app
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: my-app
          image: registry.example.com/my-app:1.0.0
          ports:
            - containerPort: 8080
              protocol: TCP
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 15
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
```

## Resource Requests & Limits

- **Always** set both `requests` and `limits` for CPU and memory.
- `requests` determine scheduling and QoS class.
- `limits` prevent runaway resource consumption.
- QoS classes: `Guaranteed` (requests == limits), `Burstable` (requests < limits), `BestEffort` (no requests/limits — avoid).

## Health Probes

- **Liveness**: Restarts container if unhealthy. Use for deadlock detection.
- **Readiness**: Removes pod from Service endpoints. Use for dependency checks.
- **Startup**: Delays liveness/readiness checks. Use for slow-starting apps.
- Set appropriate `initialDelaySeconds` and `periodSeconds`.
- Prefer `httpGet` over `exec` probes (lower overhead).

## Security Contexts

Required for every Pod:
- `runAsNonRoot: true` — never run containers as root.
- `readOnlyRootFilesystem: true` — mount tmpfs for writable paths.
- `allowPrivilegeEscalation: false` — block privilege escalation.
- `capabilities.drop: ["ALL"]` — drop all Linux capabilities.
- `seccompProfile.type: RuntimeDefault` — enable seccomp filtering.

## Kustomize Overlays

```
k8s/
├── base/
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── configmap.yaml
└── overlays/
    ├── dev/
    │   ├── kustomization.yaml
    │   └── patch-replicas.yaml
    ├── staging/
    │   └── kustomization.yaml
    └── prod/
        ├── kustomization.yaml
        └── patch-resources.yaml
```

Base `kustomization.yaml`:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
commonLabels:
  app.kubernetes.io/managed-by: kustomize
```

Overlay `kustomization.yaml`:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
namePrefix: prod-
patches:
  - path: patch-resources.yaml
    target:
      kind: Deployment
```

## Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: my-app-netpol
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: my-app
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: api-gateway
      ports:
        - port: 8080
  egress:
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: database
      ports:
        - port: 5432
```

Default deny all ingress/egress, then whitelist needed paths.

## Validation Workflow

1. `kubectl apply --dry-run=server -f manifest.yaml` — server-side validation.
2. `kubectl diff -f manifest.yaml` — preview changes against live cluster.
3. `kubeval manifest.yaml` or `kubeconform manifest.yaml` — offline schema validation.

Always run `--dry-run=server` before proposing kubectl apply.

## Best Practices

- Use the standard label set: `app.kubernetes.io/{name,version,component,part-of,managed-by}`.
- Pin image tags to specific versions — never use `:latest` in production.
- Use `imagePullPolicy: IfNotPresent` for tagged images, `Always` for digest-pinned.
- Set `terminationGracePeriodSeconds` to match your app's shutdown time.
- Use `PodDisruptionBudget` for critical workloads.
- Store configuration in ConfigMaps, secrets in Secrets (encrypted at rest).
