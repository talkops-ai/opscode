---
name: github-actions-architecture
description: >
  Guidelines for structuring modular GitHub Actions CI/CD pipelines using reusable
  workflows (workflow_call) and composite actions (runs.using: composite). Use when:
  (1) creating CI/CD pipelines with more than 3 stages, (2) refactoring monolithic
  workflow YAML into reusable components, (3) building reusable workflow templates
  with typed input schemas and secret inheritance, (4) authoring composite actions
  with shell specifications and github.action_path resolution, or (5) targeting
  ephemeral self-hosted runners via Actions Runner Controller (ARC). Do NOT use
  for security hardening (use github-actions-security-hardening), vulnerability
  defense (use github-actions-vulnerability-mitigation), or caching/artifacts
  (use github-actions-performance).
license: MIT
compatibility: designed for opscode
---

# GitHub Actions Architecture & Modularity

Structure complex CI/CD pipelines using GitHub's native modularity primitives — reusable workflows and composite actions — eliminating monolithic YAML anti-patterns.

---

## Core Principles

1. **Modular Over Monolithic**: Never create workflow files exceeding 200 lines. Decompose into reusable components.
2. **Right Primitive for the Job**: Reusable workflows replace entire jobs; composite actions bundle steps within a job.
3. **No Duplicated Logic**: Environment setup, caching, and common tasks must be encapsulated and shared.
4. **Ephemeral Runners for Enterprise**: Use Actions Runner Controller (ARC) for self-hosted environments.

---

## When to Use This Skill

- Creating a CI/CD pipeline with more than 3 distinct stages (lint, build, test, deploy)
- User requests a "template" or "reusable" workflow
- Refactoring a repetitive or legacy monolithic workflow
- Designing cross-repository pipeline sharing

---

## Reusable Workflows vs Composite Actions

| Feature | Reusable Workflows (`workflow_call`) | Composite Actions (`runs.using: composite`) |
|---|---|---|
| **Call Granularity** | Job-level — `jobs.<job_id>.uses` | Step-level — `steps[*].uses` within a job |
| **Input Schema** | Typed inputs (`type: boolean`, `type: string`) with native GitHub API validation | No type enforcement — all inputs evaluate as strings |
| **Execution Context** | Replaces an entire job; can run on separate runner instances | Bundles steps into a single logical step; inherits parent job runner |
| **Secret Access** | Direct `secrets: inherit` or explicit `secrets:` schema definition | **Cannot** access `secrets.*` directly — pass via `with:` inputs |
| **Path Resolution** | N/A — represents a complete workflow execution | Must use `${{ github.action_path }}` for internal scripts |

---

## Reusable Workflows (`workflow_call`)

Use to share entire job sequences across repositories or projects.

### Defining a Reusable Workflow

```yaml
# .github/workflows/reusable-build.yml
name: Reusable Build Pipeline

on:
  workflow_call:
    inputs:
      node-version:
        description: "Node.js version to use"
        required: true
        type: string
        default: "20"
      run-tests:
        description: "Whether to run test suite"
        required: false
        type: boolean
        default: true
    secrets:
      NPM_TOKEN:
        description: "NPM registry authentication token"
        required: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
        with:
          persist-credentials: false
      - uses: actions/setup-node@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v4.0.0
        with:
          node-version: ${{ inputs.node-version }}
          cache: 'npm'
      - run: npm ci
      - run: npm run build
      - if: ${{ inputs.run-tests }}
        run: npm test
```

### Calling a Reusable Workflow

```yaml
jobs:
  build:
    uses: myorg/shared-workflows/.github/workflows/reusable-build.yml@main
    with:
      node-version: "20"
      run-tests: true
    secrets: inherit    # Pass all org secrets automatically
```

---

## Composite Actions (`runs.using: composite`)

Use to bundle repetitive step sequences into a single logical step.

### Defining a Composite Action

```yaml
# .github/actions/setup-environment/action.yml
name: 'Setup Environment'
description: 'Bootstraps Node.js and caches dependencies securely'
inputs:
  node-version:
    description: 'Node.js version'
    required: true
    default: '20'

runs:
  using: "composite"
  steps:
    - uses: actions/setup-node@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v4.0.0
      with:
        node-version: ${{ inputs.node-version }}
        cache: 'npm'
    - run: npm ci
      shell: bash    # MANDATORY: shell must be explicit in composite actions
```

### Critical Rules for Composite Actions

- **Every `run` step MUST specify `shell:`** — it is NOT inferred in composite environments.
- **Use `${{ github.action_path }}`** when referencing internal scripts packaged with the action.
- **Secrets cannot be accessed directly** — pass sensitive data via `with:` inputs from the calling workflow.

---

## Ephemeral Self-Hosted Runners (ARC)

For enterprise compliance, networking, or specialised hardware requirements, use **Actions Runner Controller (ARC)** — a Kubernetes operator for autoscaling self-hosted runners.

### Key Concepts

- ARC deploys runners as **ephemeral, containerised pods** in runner scale sets.
- Pods scale dynamically based on webhook events from the GitHub API.
- Each job executes in a **completely clean environment** — no residual artifacts or state from prior runs.

### Usage

```yaml
jobs:
  build:
    runs-on: my-arc-scale-set    # Custom scale set name from Kubernetes cluster
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
        with:
          persist-credentials: false
      # ... build steps
```

> **Security mandate**: Always enforce ephemeral runners over persistent instances to prevent cross-job contamination.

---

## Anti-Patterns

- ❌ Monolithic workflow files exceeding 200 lines
- ❌ Duplicated environment setup across parallel jobs
- ❌ Using composite actions for job-level orchestration (use reusable workflows)
- ❌ Persistent self-hosted runners with residual state
