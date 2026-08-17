---
name: helm-testing
description: >
  Multi-layered automated testing for Helm charts covering template unit testing
  (helm-unittest), integration testing (chart-testing / ct), and native Helm test
  hooks. Use when: (1) authoring YAML unit tests with helm-unittest assertions
  (isKind, equal, matchRegex, hasDocuments), (2) generating ct.yaml configuration
  for chart-testing (ct lint, ct install), (3) writing Helm test hook pods with
  helm.sh/hook: test annotations, (4) configuring hook-delete-policy for post-test
  cleanup, or (5) validating template rendering logic and conditionals without a
  live cluster. Do NOT use for chart structure (use helm-chart-authoring), security
  (use helm-security-secrets), or deployment operations (use helm-deployment-recovery).
license: MIT
compatibility: designed for opscode
---

# Helm Multi-Layered Testing

Validate Helm charts across three testing tiers — unit tests (helm-unittest), integration tests (chart-testing), and native Helm test hooks — before any cluster deployment.

---

## Core Principles

1. **Test Before Deploy**: Never deploy a chart that hasn't passed all three testing layers.
2. **Unit Tests First**: Validate template rendering logic without a cluster.
3. **Integration Tests Second**: Validate full lifecycle (install, upgrade, delete) in a sandbox.
4. **Hooks for Runtime**: Validate post-deployment health in the live cluster.

---

## Layer 1: Template Unit Testing (helm-unittest)

Pure YAML test suites that validate template rendering logic and conditionals **without requiring a live cluster**.

### Test File Location

```
my-chart/
└── tests/
    ├── deployment_test.yaml
    ├── service_test.yaml
    └── ingress_test.yaml
```

### Test Structure

```yaml
# tests/deployment_test.yaml
suite: Deployment Tests
templates:
  - templates/deployment.yaml
tests:
  - it: should render a Deployment
    asserts:
      - isKind:
          of: Deployment

  - it: should set the correct image
    set:
      image.repository: myrepo/myapp
      image.tag: "2.0.0"
    asserts:
      - equal:
          path: spec.template.spec.containers[0].image
          value: "myrepo/myapp:2.0.0"

  - it: should set replica count from values
    set:
      replicaCount: 5
    asserts:
      - equal:
          path: spec.replicas
          value: 5

  - it: should apply resource limits
    set:
      resources.limits.cpu: "500m"
      resources.limits.memory: "256Mi"
    asserts:
      - equal:
          path: spec.template.spec.containers[0].resources.limits.cpu
          value: "500m"
      - equal:
          path: spec.template.spec.containers[0].resources.limits.memory
          value: "256Mi"

  - it: should not render ingress when disabled
    templates:
      - templates/ingress.yaml
    set:
      ingress.enabled: false
    asserts:
      - hasDocuments:
          count: 0
```

### Available Assertions

| Assertion | Purpose |
|---|---|
| `isKind` | Verify resource kind (Deployment, Service, etc.) |
| `equal` | Exact value match at a YAML path |
| `matchRegex` | Regex match at a YAML path |
| `hasDocuments` | Verify number of rendered documents |
| `isNotEmpty` | Verify a path exists and has a value |
| `isNull` | Verify a path is null or absent |
| `contains` | Verify array/map contains an element |
| `failedTemplate` | Verify template rendering fails with a specific error |

### Execution

```bash
helm unittest ./my-chart
```

---

## Layer 2: Integration Testing (chart-testing / ct)

Full deployment lifecycle tests using the `ct` CLI — validates schema conformance, structural integrity, and install/upgrade functionality.

### Configuration: `ct.yaml`

```yaml
# ct.yaml (chart root or repo root)
target-branch: main
chart-dirs:
  - charts/
validate-chart-schema: true
validate-maintainers: false
check-version-increment: true
helm-extra-args: "--timeout 5m"
```

### Execution

```bash
# Lint — validates structure, schema, and metadata
ct lint --config ct.yaml

# Install — full lifecycle test (install → test → delete)
ct install --config ct.yaml
```

**`ct lint` checks:**
- Chart.yaml metadata completeness
- values.schema.json conformance
- Template rendering correctness
- Version increment validation

**`ct install` checks:**
- Full installation lifecycle in the target cluster
- Helm test hook execution
- Clean uninstallation without orphaned resources

---

## Layer 3: Helm Test Hooks (Runtime Validation)

Native Kubernetes Pod definitions that execute post-deployment to validate the release is functional.

### Test Hook Location

```
my-chart/
└── templates/
    └── tests/
        └── test-connection.yaml
```

### Test Hook Template

```yaml
# templates/tests/test-connection.yaml
apiVersion: v1
kind: Pod
metadata:
  name: "{{ include "my-chart.fullname" . }}-test-connection"
  labels:
    {{- include "my-chart.labels" . | nindent 4 }}
  annotations:
    "helm.sh/hook": test
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
spec:
  restartPolicy: Never
  containers:
    - name: wget
      image: busybox:1.36
      command: ['wget']
      args: ['{{ include "my-chart.fullname" . }}:{{ .Values.service.port }}']
```

### Critical Annotations

| Annotation | Value | Purpose |
|---|---|---|
| `helm.sh/hook` | `test` | Marks the pod as a Helm test hook |
| `helm.sh/hook-delete-policy` | `before-hook-creation,hook-succeeded` | Cleans up test pods to prevent resource leakage |

**Rules:**
- Always set `restartPolicy: Never` — test pods should not restart on failure.
- Always set `hook-delete-policy` — prevents stale test pods from accumulating.
- Test pods run via `helm test <release>` after deployment.

### Execution

```bash
helm test my-release --namespace production
```
