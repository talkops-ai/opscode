---
name: helm-security-secrets
description: >
  Kubernetes security enforcement and cryptographic secrets management for Helm
  charts. Covers Pod Security Admission (PSA) restricted profiles, hardened
  securityContext (runAsNonRoot, readOnlyRootFilesystem, allowPrivilegeEscalation),
  NetworkPolicies with default-deny posture, and SOPS/helm-secrets/age encryption
  for cryptographic materials. Use when: (1) writing pod securityContext blocks,
  (2) enforcing PSA restricted profiles, (3) configuring default-deny NetworkPolicies,
  (4) integrating SOPS with helm-secrets and age key pairs, (5) structuring .sops.yaml
  creation rules, (6) encrypting secrets.yaml with sops --encrypt, or (7) deploying
  with helm secrets upgrade --install. Do NOT use for chart structure (use
  helm-chart-authoring), schema validation (use helm-schema-validation), or
  testing (use helm-testing).
license: MIT
compatibility: designed for deepagents-code
---

# Helm Security & Secrets Management

Enforce Kubernetes security standards (PSA restricted profiles, NetworkPolicies) and manage cryptographic secrets via SOPS/helm-secrets/age encryption.

---

## Core Principles

1. **Never Hardcode Secrets**: Plaintext credentials must never appear in Helm charts, values files, or version control.
2. **PSA Restricted by Default**: All pod templates must pass the Kubernetes Pod Security Admission `restricted` profile.
3. **Default-Deny Networking**: NetworkPolicies must deny all traffic by default, whitelisting only required paths.
4. **SOPS + age**: Use Mozilla SOPS with age encryption for at-rest secret protection.

---

## Pod Security Context (PSA Restricted Profile)

Every pod template MUST include a hardened `securityContext` aligned with the Kubernetes `restricted` PSA profile:

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "my-chart.fullname" . }}
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          # If the application needs writable directories, use emptyDir volumes:
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
```

### Security Context Checklist

| Setting | Value | Purpose |
|---|---|---|
| `runAsNonRoot` | `true` | Prevents container processes from running as root |
| `runAsUser` | `1000` (or non-zero) | Explicit non-root user ID |
| `runAsGroup` | `1000` (or non-zero) | Explicit group ID |
| `readOnlyRootFilesystem` | `true` | Prevents filesystem tampering inside the container |
| `allowPrivilegeEscalation` | `false` | Blocks sudo and setuid binaries |
| `capabilities.drop` | `["ALL"]` | Drops all Linux capabilities |
| `seccompProfile.type` | `RuntimeDefault` | Applies default seccomp filtering |

---

## NetworkPolicies (Default-Deny)

Implement a default-deny posture and whitelist only required communication paths:

```yaml
# templates/networkpolicy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "my-chart.fullname" . }}-deny-all
spec:
  podSelector:
    matchLabels:
      {{- include "my-chart.selectorLabels" . | nindent 6 }}
  policyTypes:
    - Ingress
    - Egress
  # Default: deny all ingress and egress
  ingress: []
  egress: []

---
# Allow only required ingress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "my-chart.fullname" . }}-allow-ingress
spec:
  podSelector:
    matchLabels:
      {{- include "my-chart.selectorLabels" . | nindent 6 }}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - protocol: TCP
          port: {{ .Values.service.port }}
```

---

## SOPS / helm-secrets / age Encryption

### End-to-End Cryptographic Workflow

**Step 1: Generate age Key Pair**

```bash
age-keygen -o key.txt
# Output: public key age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Step 2: Create `.sops.yaml` Configuration**

Place in chart root — defines which files to encrypt and with which key:

```yaml
# .sops.yaml
creation_rules:
  - path_regex: secrets\.yaml$
    age: "age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  - path_regex: secrets/.*\.yaml$
    age: "age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

**Step 3: Create Plaintext Secrets File**

```yaml
# secrets.yaml (BEFORE encryption)
dbPassword: "SuperSecretPassword123!"
apiKey: "sk-live-abc123def456"
tlsCert: |
  -----BEGIN CERTIFICATE-----
  MIIDXTCCAkWgAwIBAgI...
  -----END CERTIFICATE-----
```

**Step 4: Encrypt with SOPS**

```bash
sops --encrypt --in-place secrets.yaml
```

The file is now encrypted at rest — safe for version control.

**Step 5: Deploy with helm-secrets**

```bash
helm secrets upgrade --install my-release ./my-chart \
  -f secrets.yaml \
  --namespace production
```

`helm-secrets` decrypts on-the-fly during deployment, never writing plaintext to disk.

### Referencing Encrypted Values in Templates

```yaml
# templates/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "my-chart.fullname" . }}
type: Opaque
data:
  db-password: {{ .Values.dbPassword | b64enc | quote }}
  api-key: {{ .Values.apiKey | b64enc | quote }}
```

### Critical Rules

- **Never commit `key.txt`** (the age private key) to version control
- **Always commit `.sops.yaml`** — it defines encryption rules, not keys
- **Encrypted `secrets.yaml` is safe** for Git — the data is AES-256-GCM encrypted
- **Use `helm secrets` wrapper** for install/upgrade — not plain `helm install`
