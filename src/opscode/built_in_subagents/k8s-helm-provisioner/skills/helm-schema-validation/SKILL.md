---
name: helm-schema-validation
description: "JSON Schema enforcement for Helm charts via values.schema.json. Covers JSON Schema draft-07 construction, type definitions, required arrays, pattern regex validation, enum restrictions, and automatic Helm validation during install/upgrade. Use when: (1) creating values.schema.json for a new chart, (2) defining mandatory parameters with required arrays, (3) enforcing string format constraints with pattern regex, (4) restricting allowed values with enum, (5) validating user-supplied value overrides before template rendering, or (6) debugging schema validation failures during helm install/upgrade. Do NOT use for chart structure (use helm-chart-authoring), security (use helm-security-secrets), or testing (use helm-testing)."
license: MIT
compatibility: designed for opscode
---

# Helm Values Schema Validation

Constructing and enforcing `values.schema.json` using JSON Schema Draft-07 for Helm charts.

## Core Concepts & Rules

### 1. File Location & Draft-07 Schema Declaration

Helm automatically loads and validates `values.schema.json` located at the root of the chart directory during `helm install`, `helm upgrade`, `helm template`, and `helm lint`.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://example.com/values.schema.json",
  "title": "Values Schema for My App Chart",
  "type": "object",
  "required": ["replicaCount", "image", "service"],
  "properties": {
    "replicaCount": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100,
      "description": "Number of deployment replicas"
    }
  }
}
```

A starter template is available in `assets/values.schema.json`.

### 2. Defining Mandatory Parameters (`required` arrays)

Specify mandatory fields at every object level using the `required` array.

```json
{
  "type": "object",
  "required": ["repository", "tag"],
  "properties": {
    "repository": {
      "type": "string",
      "minLength": 1
    },
    "tag": {
      "type": "string"
    }
  }
}
```

### 3. String Format & Pattern Regex Validation (`pattern`, `format`)

Enforce string formatting (e.g. semver tags, domain names, memory/CPU quantities) using `pattern` regular expressions or built-in `format` constraints.

```json
{
  "image": {
    "type": "object",
    "properties": {
      "tag": {
        "type": "string",
        "pattern": "^v?[0-9]+\\.[0-9]+\\.[0-9]+$",
        "description": "Must be a valid SemVer tag (e.g., v1.2.3)"
      }
    }
  },
  "service": {
    "type": "object",
    "properties": {
      "port": {
        "type": "integer",
        "minimum": 1,
        "maximum": 65535
      }
    }
  }
}
```

### 4. Restricting Allowed Values (`enum`)

Restrict parameter choices to a closed set of permitted options using `enum`.

```json
{
  "service": {
    "type": "object",
    "properties": {
      "type": {
        "type": "string",
        "enum": ["ClusterIP", "NodePort", "LoadBalancer"],
        "description": "Kubernetes Service type"
      }
    }
  },
  "image": {
    "type": "object",
    "properties": {
      "pullPolicy": {
        "type": "string",
        "enum": ["Always", "IfNotPresent", "Never"]
      }
    }
  }
}
```

For comprehensive JSON Schema Draft-07 patterns, see [references/schema_draft07_guide.md](references/schema_draft07_guide.md).

### 5. Validating Overrides & Debugging Schema Failures

Test schema validation explicitly before deployment:

```bash
# Validate chart and values against values.schema.json
helm lint <chart-path> --values <override-values.yaml>

# Render dry-run to trigger schema validation
helm template <release-name> <chart-path> --values <override-values.yaml>
```

#### Common Schema Error Interpretation:
- `values.schema.json: values.replicaCount must be greater than or equal to 1`: Provided value violates `minimum` numeric constraint.
- `values.schema.json: values.service.type must be one of "ClusterIP", "NodePort", "LoadBalancer"`: Provided value violates `enum` constraint.
- `values.schema.json: values.image must have required property 'repository'`: Missing key declared in `required` array.

## Out-of-Scope Domains

Do NOT use this skill for:
- **Chart Structure & Directory Layout**: Use `helm-chart-authoring`.
- **Security & Secret Management**: Use `helm-security-secrets`.
- **Testing & Assertions**: Use `helm-testing`.
