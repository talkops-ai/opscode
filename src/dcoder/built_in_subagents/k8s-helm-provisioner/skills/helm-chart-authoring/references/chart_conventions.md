# Helm Chart Naming & Structure Conventions

Detailed reference rules for Helm chart naming, versioning, directory layout, and template naming.

## 1. Directory Layout Guidelines

A production-ready Helm chart directory must adhere to the following structure:

```
<chart-name>/
├── Chart.yaml              # Chart metadata (Required)
├── values.yaml             # Default configuration values (Required)
├── README.md               # User documentation (Recommended)
├── .helmignore             # Ignore patterns for packaging (Recommended)
├── charts/                 # Directory for subcharts (Optional)
├── crds/                   # Custom Resource Definitions (Optional)
└── templates/              # Manifest templates (Required)
    ├── _helpers.tpl        # Template helpers and partials
    ├── NOTES.txt           # Post-installation instructions
    ├── deployment.yaml     # Application deployment template
    ├── service.yaml        # Service definition template
    └── ingress.yaml        # Ingress route definition
```

### Notes on Special Directories:
- `crds/`: CRDs in this folder are installed before any template rendering. Helm does not manage or upgrade CRDs placed here on subsequent `helm upgrade` commands.
- `charts/`: Contains tarballs or unpacked directory forms of subchart dependencies.

## 2. Chart Naming Rules

- **Chart Name (`name` in Chart.yaml)**:
  - Must consist solely of lowercase ASCII letters, numbers, and hyphens (`[a-z0-9-]`).
  - Must start and end with an alphanumeric character.
  - Examples: `frontend-web`, `payment-gateway`, `auth-service`
  - Counter-examples (Invalid): `FrontendWeb`, `payment_gateway`, `auth-service-`

- **Resource Naming in Templates**:
  - All Kubernetes resource names rendered by the chart must be generated using `{{ include "<chart-name>.fullname" . }}`.
  - Names must be truncated to 63 characters to conform to Kubernetes DNS label rules.

## 3. SemVer 2.0.0 Versioning Rules

The `version` attribute in `Chart.yaml` tracks chart release iterations and MUST strictly follow SemVer 2.0.0 (`MAJOR.MINOR.PATCH`):

1. **MAJOR Version**: Increment when making incompatible values changes or breaking template schema modifications.
2. **MINOR Version**: Increment when adding functionality or supporting new Kubernetes resources in a backward-compatible manner.
3. **PATCH Version**: Increment when applying backward-compatible bug fixes or minor helper refinements.

Example `Chart.yaml`:
```yaml
apiVersion: v2
name: payment-service
description: High-throughput payment processing service
type: application
version: 2.1.4
appVersion: "1.9.0"
```
