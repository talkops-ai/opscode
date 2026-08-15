---
name: github-actions-performance
description: >
  Performance optimization, state management, and v4 artifact compliance for
  GitHub Actions workflows. Covers deterministic dependency caching with
  actions/cache@v4, built-in setup action caching, v4 artifact immutability
  constraints (unique naming, hidden files, 500 artifact limit), and concurrency
  control for queue management. Use when: (1) optimising slow builds with
  dependency caching, (2) uploading or downloading build artifacts between jobs,
  (3) configuring concurrency groups to cancel redundant runs, (4) passing state
  data between workflow jobs, or (5) encountering v4 artifact collision errors.
  Do NOT use for security hardening (use github-actions-security-hardening) or
  vulnerability defense (use github-actions-vulnerability-mitigation).
license: MIT
compatibility: designed for opscode
---

# GitHub Actions Performance & Artifact Management

Aggressive performance optimisation, deterministic caching, v4-compliant artifact management, and concurrency control for GitHub Actions workflows.

---

## Core Principles

1. **Cache Everything**: Dependency installation is the largest pipeline time sink — eliminate it.
2. **Deterministic Keys**: Cache keys must uniquely identify the dependency tree via lockfile hashes.
3. **v4 Immutability**: Artifacts are immutable — unique names per job, explicit hidden file inclusion.
4. **Cancel Redundant Runs**: Use concurrency groups to prevent wasted compute on superseded commits.

---

## When to Use This Skill

- Workflow installs extensive dependencies (npm, pip, cargo, maven, go)
- Workflow uploads or downloads build artifacts
- User requests execution time optimisation
- Encountering concurrency race conditions or duplicate runs

---

## Directive 1: Dependency Caching

### Built-in Setup Action Caching (Preferred)

For supported ecosystems, use the built-in `cache` parameter — simpler and less verbose:

```yaml
- uses: actions/setup-node@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v4.0.0
  with:
    node-version: '20'
    cache: 'npm'    # Built-in caching — no separate cache step needed
```

**Supported actions with built-in caching:**
- `actions/setup-node` → `cache: 'npm'` / `cache: 'yarn'` / `cache: 'pnpm'`
- `actions/setup-python` → `cache: 'pip'` / `cache: 'pipenv'` / `cache: 'poetry'`
- `actions/setup-java` → `cache: 'maven'` / `cache: 'gradle'`

### Manual Cache with `actions/cache@v4`

For ecosystems without built-in support, or when fine-grained control is needed:

```yaml
- uses: actions/cache@v4
  with:
    path: |
      ~/.cache/pip
      ~/.local/lib/python*/site-packages
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

### Cache Key Construction Rules

1. **Concatenate OS + language + lockfile hash**: `${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}`
2. **Always provide `restore-keys`**: Enables partial cache hits when exact hashes miss due to minor dependency bumps
3. **Hash the lockfile, not the manifest**: Use `package-lock.json` not `package.json`

### Common Cache Paths

| Ecosystem | Cache Path | Lockfile |
|---|---|---|
| npm | `~/.npm` | `**/package-lock.json` |
| Yarn | `~/.cache/yarn` | `**/yarn.lock` |
| pip | `~/.cache/pip` | `**/requirements.txt` |
| Cargo | `~/.cargo/registry`, `~/.cargo/git`, `target/` | `**/Cargo.lock` |
| Maven | `~/.m2/repository` | `**/pom.xml` |
| Go | `~/go/pkg/mod` | `**/go.sum` |

---

## Directive 2: v4 Artifact Management

You **MUST** use `actions/upload-artifact@v4` and `actions/download-artifact@v4`. Legacy versions are deprecated.

### v4 Breaking Changes

| Constraint | Impact | Mitigation |
|---|---|---|
| **Strict Immutability** | Cannot upload multiple times to the same artifact name across jobs | Use unique names per job: `name: build-output-${{ github.sha }}` |
| **Hidden Files Excluded** | Files prefixed with `.` (e.g., `.env`, `.vscodeignore`) silently dropped | Set `include-hidden-files: true` |
| **500 Artifact Limit** | Maximum 500 individual artifacts per job | Consolidate outputs into fewer, larger archives |

### Compliant Upload

```yaml
- uses: actions/upload-artifact@65462800fd760344b1a7b4382951275a0abb4808 # v4.3.3
  with:
    name: build-output-${{ github.sha }}    # Unique name per run
    path: dist/
    include-hidden-files: true              # Capture .env, .config files
    retention-days: 7
```

### Cross-Job Download

```yaml
- uses: actions/download-artifact@v4
  with:
    name: build-output-${{ github.sha }}
    path: ./dist
```

---

## Directive 3: Concurrency Control

Cancel redundant in-progress runs when new commits arrive on the same branch:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

**Where to place**: At the top level of the workflow, before `jobs:`.

**When to use**: Feature branch CI where only the latest commit matters. **Do not** use `cancel-in-progress: true` on `main`/`release` branches where every commit must complete.

---

## Complete Example: Optimised Build Pipeline

```yaml
name: Build & Test

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
        with:
          persist-credentials: false

      - uses: actions/setup-node@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v4.0.0
        with:
          node-version: '20'
          cache: 'npm'

      - run: npm ci
      - run: npm run build
      - run: npm test

      - uses: actions/upload-artifact@65462800fd760344b1a7b4382951275a0abb4808 # v4.3.3
        with:
          name: build-output-${{ github.sha }}
          path: dist/
          include-hidden-files: true
```
