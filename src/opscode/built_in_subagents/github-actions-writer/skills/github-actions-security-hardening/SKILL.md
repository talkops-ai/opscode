---
name: github-actions-security-hardening
description: >
  Enforces security best practices for GitHub Actions: least-privilege token scoping,
  SHA-pinned dependency immutability, credential persistence prevention (zizmor
  artipacked rule), OIDC cloud authentication, and static analysis integration
  (zizmor, actionlint, OpenSSF Scorecard). Use whenever: (1) generating any new
  workflow file, (2) performing a security review or audit of an existing pipeline,
  (3) configuring cloud provider access (AWS, Azure, GCP) via OIDC, (4) setting
  up zizmor or actionlint scanning jobs, or (5) uploading SARIF results to GitHub
  Code Scanning. Do NOT use for threat vector defense (use
  github-actions-vulnerability-mitigation) or caching/artifacts (use
  github-actions-performance).
license: MIT
compatibility: designed for opscode
---

# GitHub Actions Security Hardening

Non-negotiable security protocols for every generated GitHub Actions workflow — token scoping, dependency pinning, credential protection, OIDC authentication, and static analysis.

---

## Core Principles

1. **Security by Default**: Every security directive applies to ALL generated workflows, not just those explicitly flagged as security-sensitive.
2. **Least Privilege**: Default permissions to `{}` (none) or `contents: read`. Escalate only per-job.
3. **Immutable Dependencies**: Pin all third-party actions to full 40-character SHA hashes.
4. **No Static Credentials**: Use OIDC for cloud authentication. Never store long-lived keys in secrets.

---

## When to Use This Skill

- Generating any entirely new workflow file
- Performing security review or audit of an existing pipeline
- Configuring cloud provider access (AWS, Azure, GCP)
- Setting up CI/CD security scanning

---

## Directive 1: Principle of Least Privilege (Token Scoping)

Every workflow MUST define a top-level `permissions:` block to override GitHub's default broad access:

```yaml
# Top-level — restrict globally
permissions:
  contents: read    # Minimum required for checkout

jobs:
  deploy:
    permissions:
      contents: read
      id-token: write    # Escalate ONLY where needed, ONLY at job level
    runs-on: ubuntu-latest
    steps:
      # ...
```

**Rules:**
- Default to `permissions: {}` (no permissions) or `contents: read`
- Escalate permissions **only** at the individual job level
- Only grant the **specific scopes** required by that job's steps

---

## Directive 2: Dependency Pinning & Immutability

**Never** use mutable tags (`@v2`, `@master`, `@main`) for third-party actions. Supply chain attacks like the [tj-actions/changed-files breach](https://research.sot.tl/tj-actions-changed-files-supply-chain-attack/) prove that tags can be retroactively mutated to point to malicious commits.

```yaml
# ❌ WRONG — mutable tag, vulnerable to supply chain attacks
- uses: actions/checkout@v4

# ✅ CORRECT — full SHA hash with version comment
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
```

**All `uses:` directives for third-party actions MUST:**
1. Be pinned to a full **40-character SHA-1 hash**
2. Include a trailing comment with the human-readable version tag

---

## Directive 3: Credential Persistence Prevention (Zizmor `artipacked` Rule)

By default, `actions/checkout` leaves the `GITHUB_TOKEN` embedded in `.git/config`, exposing it to every subsequent step, dependency, or third-party action in the same job.

```yaml
# ✅ MANDATORY on all checkout steps
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
  with:
    persist-credentials: false    # Prevents token theft via .git/config
```

**Exception**: Only omit `persist-credentials: false` when the job has an explicit, documented requirement to perform `git push` operations.

---

## Directive 4: Cloud Authentication via OIDC

**Never** use static, long-lived cloud credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) stored as GitHub Secrets.

Use **OpenID Connect (OIDC)** for federated trust:

```yaml
jobs:
  deploy:
    permissions:
      id-token: write    # Required to generate the OIDC JWT
      contents: read
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
        with:
          persist-credentials: false

      - name: Configure AWS credentials via OIDC
        uses: aws-actions/configure-aws-credentials@e3dd6a429d7300a6a4c196c26e071d42e0343502 # v4.0.2
        with:
          role-to-assume: arn:aws:iam::123456789012:role/my-github-actions-role
          aws-region: us-east-1
```

**Requirements:**
- Job-level `permissions.id-token: write` — allows GitHub to generate a short-lived JWT
- `role-to-assume` — points to a pre-configured IAM role with OIDC trust policy
- No static secrets needed — AWS validates the JWT cryptographically

---

## Directive 5: Static Analysis Integration

Every repository's CI pipeline should include a dedicated security scanning job:

### Zizmor (GitHub Actions Security Scanner)

```yaml
  security-scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write    # Required for SARIF upload
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
        with:
          persist-credentials: false

      - name: Run zizmor security analysis
        uses: zizmorcore/zizmor-action@v1
        with:
          persona: pedantic    # Maximum sensitivity
          format: sarif

      - name: Upload SARIF to GitHub Code Scanning
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif
```

### Actionlint (Semantic Syntax Checker)

```yaml
      - name: Run actionlint
        uses: rhysd/actionlint@v1
```

### OpenSSF Scorecard (Supply Chain Posture)

```yaml
      - name: Run OpenSSF Scorecard
        uses: ossf/scorecard-action@v2
        with:
          results_file: scorecard-results.sarif
          publish_results: true
```

**Zizmor detects:**
- Excessive permission scopes
- Template injections (`${{ }}` in inline scripts)
- Confusable Git references
- `artipacked` credential persistence
- Unpinned dependencies
