---
name: argocd
description: "Manage ArgoCD Application and ApplicationSet manifests for GitOps deployments"
domain: DevOps
compatibility: "argocd >= 2.8"
allowed_tools:
  - execute
  - write_file
  - read_file
metadata:
  domain: argocd
  difficulty: advanced
---

# ArgoCD GitOps Skill

You are an expert in ArgoCD-driven GitOps workflows. Follow these guidelines when creating, reviewing, or debugging ArgoCD configurations.

## Application Manifest

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/org/repo.git
    targetRevision: main
    path: manifests/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: my-app
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

## Sync Policies

- **Automated sync**: Set `automated.prune: true` and `automated.selfHeal: true` for production apps that should auto-converge.
- **Manual sync**: Omit `automated` block for apps requiring human approval before deployment.
- Use `syncOptions: [CreateNamespace=true]` to auto-create target namespaces.
- Set `retry` with exponential backoff for transient failures.

## Sync Waves & Hooks

Control deployment ordering with sync-wave annotations:

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-1"  # Deployed before wave 0
```

- **Wave -2**: Namespaces, CRDs
- **Wave -1**: ConfigMaps, Secrets, ServiceAccounts
- **Wave 0**: Core resources (Deployments, Services)
- **Wave 1**: Ingresses, NetworkPolicies
- **Wave 2**: Post-deploy jobs, tests

Hook types: `PreSync`, `Sync`, `PostSync`, `SyncFail`, `Skip`.

## ApplicationSet

Use ApplicationSet generators for multi-cluster/multi-env deployments:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: my-app-set
  namespace: argocd
spec:
  generators:
    - git:
        repoURL: https://github.com/org/repo.git
        revision: main
        directories:
          - path: manifests/overlays/*
  template:
    metadata:
      name: "my-app-{{path.basename}}"
    spec:
      project: default
      source:
        repoURL: https://github.com/org/repo.git
        targetRevision: main
        path: "{{path}}"
      destination:
        server: https://kubernetes.default.svc
        namespace: "{{path.basename}}"
```

Generator types: `git` (directory/file), `cluster`, `list`, `matrix`, `merge`, `pullRequest`.

## Health Checks

- ArgoCD auto-detects health for standard K8s resources.
- Add custom health checks in `argocd-cm` ConfigMap for CRDs.
- Check `Degraded` status for failing health checks — review resource events.
- Use `argocd app diff APPNAME` to compare live vs desired state.

## Project RBAC

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-platform
  namespace: argocd
spec:
  sourceRepos:
    - "https://github.com/org/*"
  destinations:
    - namespace: "team-*"
      server: https://kubernetes.default.svc
  clusterResourceWhitelist:
    - group: ""
      kind: Namespace
```

Restrict projects to specific repos, namespaces, and cluster resource types.

## Best Practices

- Always pin `targetRevision` to a branch, tag, or commit — never leave empty.
- Use `resources-finalizer.argocd.argoproj.io` to clean up resources on app deletion.
- Separate app-of-apps pattern for managing multiple Applications declaratively.
- Use `ignoreDifferences` for fields managed by controllers (e.g., HPA replicas).
- Monitor sync status and health via ArgoCD notifications or webhooks.
