# Helm values.yaml Structuring & Pattern Guide

Best practices for flat values hierarchies, type coercion, subchart overrides, and global variable scoping.

## 1. Flat-Over-Deep Structuring

Avoid deeply nested values hierarchies. Shallow structures make chart overrides easier from `--set` and custom values files.

### Recommended Hierarchy Depth (Maximum 2-3 Levels)

```yaml
# Recommended Flat Hierarchy
replicaCount: 3

image:
  repository: myrepo/app
  pullPolicy: IfNotPresent
  tag: "v1.2.0"

service:
  type: ClusterIP
  port: 8080
  targetPort: 8080

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 100m
    memory: 128Mi
```

### Anti-Pattern: Deep Nesting (>3 Levels)

```yaml
# Anti-Pattern: Avoid deep nesting
app:
  components:
    server:
      scaling:
        replicas: 3
```
*Why avoid:* Overriding this value via command-line requires `--set app.components.server.scaling.replicas=3`, which is verbose and prone to typo errors.

## 2. Type Coercion & Quoting Principles

Go template evaluation inside Helm can implicitly coerce unquoted values into wrong types (e.g., numeric strings converted to float/int, boolean strings converted to bools).

### Quoting Rules

1. **Port Numbers & String Configs**:
   - Wrap port numbers or environment strings in explicit double quotes if they must be rendered as string types in ConfigMaps or Environment variables.
   ```yaml
   env:
     HTTP_PORT: "8080"
     ENABLE_METRICS: "true"
   ```

2. **Kubernetes API Version or Tags**:
   - Always quote semver-like strings or numbers in tags to prevent YAML parsers from converting them to scientific notation or floats.
   ```yaml
   image:
     tag: "1.0"   # Prevents parsing as float 1
   ```

3. **Strict Booleans and Integers**:
   - Use raw boolean/integer literals when rendering directly into native Kubernetes spec fields that require boolean or integer types:
   ```yaml
   replicaCount: 2
   podSecurityContext:
     runAsNonRoot: true
   ```

## 3. Subchart Variable Overrides & Umbrella Charts

In umbrella charts that incorporate subcharts (e.g., via `charts/` or `Chart.yaml` dependencies):

### Subchart Override Syntax
To override a subchart's value from the parent umbrella chart, use the exact subchart name as a top-level key in the umbrella chart's `values.yaml`.

```yaml
# Umbrella values.yaml
# Overriding values for subchart 'postgresql'
postgresql:
  auth:
    database: my_app_db
    username: my_user
  primary:
    persistence:
      enabled: true
      size: 10Gi
```

### Global Values Scoping (`.Values.global`)
Global values allow values to be shared across umbrella charts and all dependent subcharts.

1. **Umbrella `values.yaml`**:
   ```yaml
   global:
     imageRegistry: docker.io/myorg
     environment: production
     imagePullSecrets:
       - name: my-registry-key
   ```

2. **Subchart Template Access**:
   ```yaml
   {{- if .Values.global.imagePullSecrets }}
   imagePullSecrets:
   {{- toYaml .Values.global.imagePullSecrets | nindent 2 }}
   {{- end }}
   ```
