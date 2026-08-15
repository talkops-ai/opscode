# Kustomize Base & Overlay Management

## 1. Directory Layout

```
k8s/
├── base/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── kustomization.yaml
└── overlays/
    ├── dev/
    │   ├── kustomization.yaml
    │   └── replica_patch.yaml
    └── prod/
        ├── kustomization.yaml
        ├── hpa.yaml
        └── patch_resources.yaml
```

---

## 2. Base Configuration (`base/kustomization.yaml`)

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
  - service.yaml

commonLabels:
  app.kubernetes.io/part-of: e-commerce
```

---

## 3. Production Overlay (`overlays/prod/kustomization.yaml`)

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: production
namePrefix: prod-

resources:
  - ../../base
  - hpa.yaml

images:
  - name: myregistry.azurecr.io/api-service
    newTag: v1.5.0

configMapGenerator:
  - name: api-config
    literals:
      - LOG_LEVEL=info
      - FEATURE_FLAGS_ENABLED=true

patches:
  - path: patch_resources.yaml
    target:
      kind: Deployment
      name: api-service
```

### Strategic Merge Patch Example (`overlays/prod/patch_resources.yaml`)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 5
  template:
    spec:
      containers:
        - name: app
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: 2000m
              memory: 1Gi
```
