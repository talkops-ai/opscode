---
name: helm-chart-authoring
description: "Production-grade Helm chart structuring, naming conventions, values management, and template patterns. Use when: (1) creating new Helm charts with proper directory layouts, (2) enforcing chart naming (lowercase-hyphenated) and variable naming (camelCase) conventions, (3) structuring values.yaml with flat-over-deep patterns and type coercion rules, (4) managing subchart variable overrides in umbrella charts, (5) scoping global values via .Values.global, or (6) applying SemVer 2.0.0 versioning to Chart.yaml. Do NOT use for schema validation (use helm-schema-validation), security contexts (use helm-security-secrets), testing (use helm-testing), or deployment operations (use helm-deployment-recovery)"
license: MIT
compatibility: designed for deepagents-code
---

# Helm Chart Authoring

Production-grade rules, directory layouts, and template patterns for authoring Helm v3 charts.

## Core Rules & Workflow

### 1. Directory Layout & Chart Structure

Structure Helm charts according to the standard Helm v3 layout:

```
my-chart/
├── Chart.yaml           # Chart metadata (apiVersion: v2, name, version)
├── values.yaml          # Default configuration values
├── README.md            # Chart documentation
├── .helmignore          # Patterns to exclude from chart packaging
├── charts/              # Subcharts directory
├── crds/                # Custom Resource Definitions
└── templates/           # Kubernetes manifest templates
    ├── _helpers.tpl     # Named template helpers
    ├── NOTES.txt        # Post-install usage notes
    ├── deployment.yaml  # Deployment manifest
    └── service.yaml     # Service manifest
```

Starter templates are available in `assets/chart-template/`.

### 2. Naming Conventions

- **Chart Name**: Use lowercase alphanumeric characters and hyphens (`lowercase-hyphenated`).
  - Example: `my-microservice`, `auth-api-service`
  - Avoid: `MyMicroservice`, `my_microservice`, `authAPI`
- **Variable Names (`values.yaml`)**: Use `camelCase` for all keys.
  - Example: `replicaCount`, `imagePullSecrets`, `serviceAccount.create`
  - Avoid: `replica_count`, `ReplicaCount`, `service-account`
- **Named Templates (`_helpers.tpl`)**: Prefix helper names with the chart name (`chartname.fullname`, `chartname.labels`).

For detailed convention details, see [references/chart_conventions.md](references/chart_conventions.md).

### 3. Versioning (`Chart.yaml`)

- Enforce **SemVer 2.0.0** (`MAJOR.MINOR.PATCH`) for the `version` field in `Chart.yaml`.
  - Increment `MAJOR` for breaking chart/values changes.
  - Increment `MINOR` for backward-compatible features or additions.
  - Increment `PATCH` for backward-compatible bug fixes.
- Set `apiVersion: v2` for Helm 3 charts.
- Keep `appVersion` aligned with application version string.

```yaml
apiVersion: v2
name: my-app
description: Production-grade microservice Helm chart
type: application
version: 1.2.0
appVersion: "2.4.1"
```

### 4. Structuring `values.yaml`

#### Flat-Over-Deep Principle
Keep values hierarchy flat. Avoid nesting deeper than 2-3 levels.

```yaml
# Good (Flat)
replicaCount: 2

image:
  repository: nginx
  pullPolicy: IfNotPresent
  tag: "1.25.0"

service:
  type: ClusterIP
  port: 80
```

#### Type Coercion & Quoting Rules
- Quote string values that resemble booleans (`"true"`, `"false"`) or numbers (`"8080"`, `"1.0"`).
- Use raw unquoted booleans (`true`/`false`) and integers (`80`) only when boolean/numeric types are strictly expected by Kubernetes schemas.

For full values structuring patterns and type coercion guidelines, see [references/values_patterns.md](references/values_patterns.md).

### 5. Subchart Overrides & Umbrella Charts

- **Subchart Overrides**: Reference the subchart name as a top-level key in the umbrella chart `values.yaml`.
- **Global Values (`.Values.global`)**: Define shared parameters under `global:` to expose them across subcharts via `.Values.global`.

```yaml
# Umbrella values.yaml
global:
  environment: production
  imagePullSecrets:
    - name: regcred

redis:
  architecture: standalone
```

### 6. Standard Helper Templates (`templates/_helpers.tpl`)

Define standard helpers for labels and naming in `templates/_helpers.tpl`:

```gotemplate
{{/*
Expand the name of the chart.
*/}}
{{- define "my-chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "my-chart.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "my-chart.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "my-chart.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "my-chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "my-chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

## Out-of-Scope Domains

Do NOT handle the following tasks in this skill; refer to the specialized skills instead:
- **Schema Validation**: Use `helm-schema-validation` for `values.schema.json`.
- **Security Contexts & Secrets**: Use `helm-security-secrets` for security contexts, RBAC, or secrets encryption.
- **Testing**: Use `helm-testing` for `helm test`, unittest plugins, or dry-run assertions.
- **Deployment Operations**: Use `helm-deployment-recovery` for `helm upgrade`, rollback, or release recovery.
