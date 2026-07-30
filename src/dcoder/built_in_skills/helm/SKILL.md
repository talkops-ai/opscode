---
name: helm
description: "Develop, validate, and manage Helm charts following best practices"
domain: DevOps
compatibility: "helm >= 3.12"
allowed_tools:
  - execute
  - write_file
  - read_file
metadata:
  domain: helm
  difficulty: intermediate
---

# Helm Chart Development Skill

You are an expert Helm chart developer. Follow these guidelines when creating, reviewing, or debugging Helm charts.

## Chart Structure

```
mychart/
├── Chart.yaml          # Chart metadata (name, version, appVersion)
├── values.yaml         # Default configuration values
├── values.schema.json  # JSON Schema for values validation (optional)
├── templates/
│   ├── _helpers.tpl    # Named templates and shared logic
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── serviceaccount.yaml
│   ├── hpa.yaml
│   └── NOTES.txt       # Post-install usage notes
├── charts/             # Subcharts / dependencies
└── tests/
    └── test-connection.yaml
```

## Chart.yaml

```yaml
apiVersion: v2
name: mychart
description: A Helm chart for my application
type: application
version: 0.1.0        # Chart version (SemVer)
appVersion: "1.0.0"   # Application version
dependencies:
  - name: postgresql
    version: "~12.0"
    repository: "https://charts.bitnami.com/bitnami"
    condition: postgresql.enabled
```

## Template Best Practices

- Use `{{ include "mychart.fullname" . }}` (not `{{ template }}`) so output can be piped.
- Define reusable templates in `_helpers.tpl`:

```yaml
{{- define "mychart.labels" -}}
app.kubernetes.io/name: {{ include "mychart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
```

- Use `{{ toYaml .Values.resources | nindent 12 }}` for nested YAML injection.
- Guard optional blocks with `{{- if .Values.ingress.enabled }}`.
- Use `{{- with .Values.nodeSelector }}` for conditional map blocks.
- Quote strings: `{{ .Values.image.tag | quote }}`.

## Values Best Practices

- Provide sensible defaults in `values.yaml` — chart should install with zero overrides.
- Nest related values logically: `image.repository`, `image.tag`, `image.pullPolicy`.
- Use `values.schema.json` to validate required fields and types.
- Document every value with inline comments.
- Use `null` for optional fields that should be omitted when unset.

## Hooks

```yaml
annotations:
  "helm.sh/hook": pre-install,pre-upgrade
  "helm.sh/hook-weight": "-5"
  "helm.sh/hook-delete-policy": before-hook-creation
```

Hook types: `pre-install`, `post-install`, `pre-upgrade`, `post-upgrade`, `pre-delete`, `post-delete`, `pre-rollback`, `post-rollback`, `test`.

## Validation Workflow

1. `helm lint ./mychart` — static analysis and best-practice checks.
2. `helm template ./mychart` — render templates locally without deploying.
3. `helm template ./mychart | kubectl apply --dry-run=server -f -` — server-side validation.
4. `helm test RELEASE` — run in-cluster test pods.

Always run `helm lint` and `helm template` before proposing chart changes.

## Subcharts & Dependencies

- Declare dependencies in `Chart.yaml`, not by copying charts.
- Use `condition` fields to make dependencies optional.
- Run `helm dependency update` after changing dependencies.
- Override subchart values via parent's `values.yaml` under the dependency name key.

## Security

- Never hardcode secrets in `values.yaml` — use external secret managers.
- Set `automountServiceAccountToken: false` unless needed.
- Define `securityContext` with `runAsNonRoot: true` and `readOnlyRootFilesystem: true`.
- Use `NetworkPolicy` templates to restrict pod-to-pod traffic.
