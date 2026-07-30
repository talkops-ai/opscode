---
name: ci-cd
description: "Design and maintain CI/CD pipelines for GitHub Actions, GitLab CI, and Argo Workflows"
domain: DevOps
compatibility: "github-actions, gitlab-ci, argo-workflows"
allowed_tools:
  - write_file
  - read_file
metadata:
  domain: ci-cd
  difficulty: intermediate
---

# CI/CD Pipeline Skill

You are an expert CI/CD pipeline engineer. Follow these guidelines when creating, reviewing, or debugging pipelines.

## GitHub Actions

### Workflow Structure

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff && ruff check .

  test:
    needs: lint
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]" && pytest

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - run: echo "Deploy to production"
```

### Best Practices

- Pin action versions to SHA or major version: `actions/checkout@v4`.
- Use `permissions` to set minimum required OIDC/token scopes.
- Use `needs` for job dependencies — parallel by default.
- Use `environment` with protection rules for production deploys.
- Cache dependencies: `actions/cache@v4` or built-in `setup-*` caching.
- Use `concurrency` to cancel redundant runs.
- Store secrets in GitHub Secrets — never hardcode.

### Reusable Workflows

```yaml
# .github/workflows/reusable-deploy.yml
on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
    secrets:
      deploy_key:
        required: true
```

## GitLab CI

```yaml
stages:
  - lint
  - test
  - deploy

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"

lint:
  stage: lint
  image: python:3.12-slim
  script:
    - pip install ruff
    - ruff check .
  cache:
    paths: [.cache/pip]

test:
  stage: test
  image: python:3.12-slim
  script:
    - pip install -e ".[dev]"
    - pytest --junitxml=report.xml
  artifacts:
    reports:
      junit: report.xml

deploy:
  stage: deploy
  environment: production
  only: [main]
  script:
    - echo "Deploy to production"
```

## Argo Workflows

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  name: ci-pipeline
spec:
  entrypoint: main
  templates:
    - name: main
      dag:
        tasks:
          - name: lint
            template: lint
          - name: test
            template: test
            dependencies: [lint]
    - name: lint
      container:
        image: python:3.12-slim
        command: [sh, -c]
        args: ["pip install ruff && ruff check ."]
    - name: test
      container:
        image: python:3.12-slim
        command: [sh, -c]
        args: ["pip install pytest && pytest"]
```

## General CI/CD Principles

- **Fail fast**: Run linting and static analysis before expensive tests.
- **Parallelise**: Use matrix builds and DAG-based job graphs.
- **Artifact passing**: Use built-in artifact systems, not shared volumes.
- **Secrets management**: Inject secrets via CI variables — never in code.
- **Idempotency**: Every pipeline step should be safely re-runnable.
- **Notifications**: Alert on failure (Slack, email, webhook).
- **Branch protection**: Require CI pass before merge to main.
