# Helm values.schema.json Draft-07 Specification Guide

Comprehensive guide to writing `values.schema.json` using JSON Schema Draft-07 for Helm charts.

## 1. Top-Level Structure

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://example.com/values.schema.json",
  "title": "Helm Values Schema",
  "description": "Validation schema for chart configuration values",
  "type": "object",
  "required": [
    "replicaCount",
    "image",
    "service"
  ],
  "properties": {}
}
```

## 2. Type Definitions & Rules

| JSON Schema Type | Permitted YAML Values |
|---|---|
| `"type": "string"` | String text (`"nginx"`, `"8080"`) |
| `"type": "integer"` | Whole numbers (`1`, `80`, `443`) |
| `"type": "number"` | Floating point or integers (`1.5`, `2`) |
| `"type": "boolean"` | `true` or `false` |
| `"type": "array"` | Lists (`[ "a", "b" ]`) |
| `"type": "object"` | Nested maps/key-value pairs |

## 3. String Patterns & Constraints

### Common Regex Patterns for Kubernetes
- **SemVer Tag**: `"pattern": "^v?[0-9]+\\.[0-9]+\\.[0-9]+(-[a-zA-Z0-9.]+)?$"`
- **Kubernetes Memory Quantity**: `"pattern": "^[0-9]+(Mi|Gi|Ti|Ki|M|G|T|K)?$"`
- **Kubernetes CPU Quantity**: `"pattern": "^[0-9]+(m)?$"`
- **DNS Subdomain Label**: `"pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"`

## 4. Array Item Constraints

```json
{
  "ingress": {
    "type": "object",
    "properties": {
      "hosts": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["host", "paths"],
          "properties": {
            "host": {
              "type": "string",
              "format": "hostname"
            },
            "paths": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          }
        }
      }
    }
  }
}
```
