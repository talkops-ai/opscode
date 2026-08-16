# Subagents

> Delegate specialized DevOps workflows to custom or built-in domain subagents with isolated execution graphs.

OpsCode subagents allow the main agent to delegate specialized, multi-step tasks to dedicated subagent graphs. Each subagent runs with its own focused system prompt, isolated branch memory (`BranchMemoryStore`), scoped tool permissions, and domain-specific skills.

## Deep Agent Skills vs. Subagent Skills

It is important to understand the structural difference between skills:

- **Deep Agent Skills (Global):** Loaded directly into the main root agent prompt (e.g. `cloud-core`, `docker`, `kubernetes`, `remember`). These skills guide the root agent across all general turns.
- **Subagent Skills (Domain-Scoped):** Encapsulated exclusively within a specific subagent directory (`skills/`). These skills are only loaded when that particular subagent is invoked and do not pollute the main agent's context.

```
Main Deep Agent (Global Context)
 ├── Global Skills: cloud-core, docker, kubernetes, remember
 └── Subagent Registry (Delegated Execution)
      ├── aws-opentofu-provisioner (Isolated Branch Memory + 7 OpenTofu Skills + AWS MCP)
      ├── aws-terraform-module-writer (Isolated Branch Memory + 7 Terraform Skills + AWS MCP)
      ├── ci-jenkins-automater (Isolated Branch Memory + 4 Jenkins Skills)
      ├── github-actions-writer (Isolated Branch Memory + 4 GHA Skills)
      ├── infra-ansible-provisioner (Isolated Branch Memory + 7 Ansible Skills + Ansible MCP)
      └── k8s-helm-provisioner (Isolated Branch Memory + 5 Helm Skills)
```

---

## Defining custom subagents

Each custom subagent is defined as a Markdown file with YAML frontmatter:

```
.opscode/agents/{subagent-name}/AGENTS.md   # Project-level (Git-tracked)
~/.opscode/{agent}/agents/{subagent-name}/AGENTS.md  # User-level
```

Project subagents override user subagents with the same name.

### File format

```markdown
---
name: terraform-reviewer
description: Review Terraform and OpenTofu modules for security, least-privilege IAM, and state locking
model: anthropic:claude-opus-4-7
tools:
  - execute
  - read_file
  - grep
skills:
  - opentofu-iam-security
  - aws-iam-policy-engine
---

You are a specialized Terraform and OpenTofu security auditor.

## Audit Criteria:
1. Ensure S3 remote state uses AWS KMS encryption and DynamoDB state locking.
2. Verify all IAM policies follow least-privilege principle (no wildcard actions).
3. Validate that security groups avoid open 0.0.0.0/0 ingress on sensitive ports.
4. Ensure resource tags conform to corporate standards.
```

### Frontmatter fields

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Unique identifier for the subagent |
| `description` | Yes | Functional description used by the main agent for delegation matching |
| `model` | No | Model override in `provider:model-name` format. Omit to inherit the main agent's active model |
| `skills` | No | List of skill names to explicitly load into this subagent's execution context |
| `tools` | No | Tool filtering proxy patterns allowed for this subagent (e.g. `["execute", "read_file", "mcp__*"]`) |

The Markdown body below the frontmatter becomes the subagent's specialized `system_prompt`.

---

## Built-in Enterprise DevOps Subagents

OpsCode ships with **6 built-in enterprise subagents** in `src/opscode/built_in_subagents/`:

### 1. `aws-opentofu-provisioner`
Provisions OpenTofu infrastructure, implements OpenTofu 1.6+ native state encryption with AWS KMS, provisions S3/DynamoDB state backends, configures cross-account IAM roles, and sets up OpenTofu CI/CD workflows.
- **System Prompt:** `agents/opentofu-writer.md`
- **Embedded MCP:** `.mcp.json`
- **Encapsulated Skills (7):**
  - `opentofu-data-security`
  - `opentofu-iam-security`
  - `opentofu-mcp-schema-lookup`
  - `opentofu-module-layout`
  - `opentofu-state-management`
  - `opentofu-testing-validation`
  - `opentofu-vpc-networking`

### 2. `aws-terraform-module-writer`
Authoring AWS Terraform modules adhering to HashiCorp best practices, multi-account policy architecture, remote state locking, S3/DynamoDB backends, and live AWS MCP queries.
- **System Prompt:** `agents/aws-terraform-writer.md`
- **Embedded MCP:** `.mcp.json`
- **Encapsulated Skills (7):**
  - `aws-data-security-enforcement`
  - `aws-iam-policy-engine`
  - `aws-vpc-network-patterns`
  - `terraform-iteration-patterns`
  - `terraform-mcp-schema-lookup`
  - `terraform-module-layout`
  - `terraform-repair-loop`

### 3. `ci-jenkins-automater`
Scaffolds declarative pipelines (`Jenkinsfile`), creates shared libraries (`vars/`, `src/`), manages Kubernetes and Docker dynamic agent pods, and debugs pipeline execution.
- **System Prompt:** `agents/ci-jenkins-automater.md`
- **Encapsulated Skills (4):**
  - `jenkins-job-dsl-jcasc`
  - `jenkins-pipeline-generation`
  - `jenkins-pipeline-testing`
  - `jenkins-shared-libraries`

### 4. `github-actions-writer`
Generates hardened GitHub Actions workflows, reusable composite actions, OpenID Connect (OIDC) cloud authentication, concurrency controls, secret masking, and matrix testing strategies.
- **System Prompt:** `agents/github-actions-writer.md`
- **Encapsulated Skills (4):**
  - `github-actions-architecture`
  - `github-actions-performance`
  - `github-actions-security-hardening`
  - `github-actions-vulnerability-mitigation`

### 5. `infra-ansible-provisioner`
Scaffolds Ansible playbooks and standard role structures (`tasks/`, `handlers/`, `vars/`, `defaults/`, `meta/`), dynamic inventory management, Ansible Vault encryption, Molecule testing, and idempotency checks.
- **System Prompt:** `agents/infra-provisioner.md`
- **Embedded MCP:** `.mcp.json`
- **Encapsulated Skills (7):**
  - `ansible-code-authoring`
  - `ansible-environment-setup`
  - `ansible-execution-environments`
  - `ansible-linting-remediation`
  - `ansible-mcp-schema-lookup`
  - `ansible-runner-execution`
  - `ansible-security-operations`

### 6. `k8s-helm-provisioner`
Builds production Helm charts, values schemas (`values.schema.json`), template helpers (`_helpers.tpl`), dry-run template debuggers, and Pod Security Standard hardening.
- **System Prompt:** `agents/k8s-helm-provisioner.md`
- **Encapsulated Skills (5):**
  - `helm-chart-authoring`
  - `helm-deployment-recovery`
  - `helm-schema-validation`
  - `helm-security-secrets`
  - `helm-testing`

---

## Subagent Architecture Features

### 1. Isolated Branch Memory (`BranchMemoryStore`)
Subagents execute within an isolated branch memory file. Intermediate reasoning, transient search dumps, and sub-steps remain inside the subagent graph without polluting the parent agent's context window. Only final summaries and outcomes return to the parent.

### 2. Tool Filtering Proxy (`ToolFilterMiddleware`)
When a subagent specifies `tools: ["pattern"]`, OpsCode wraps the toolset in a filtering proxy. Any tool call outside the pattern is rejected before execution.

### 3. Subagent Embedded MCP Servers
Subagents can bundle their own `.mcp.json` manifests. These MCP server sessions are instantiated exclusively for that subagent's graph and closed upon task completion.

---

## Using subagents

Subagents are delegated to automatically when the main agent detects a matching domain request:

```
Create a hardened GitHub Actions workflow that authenticates to AWS via OIDC and deploys an EKS Helm chart
```

The agent compiles and delegates execution to `github-actions-writer` and `k8s-helm-provisioner`.

### Switching agents at launch or runtime

Start a session directly with a subagent:

```bash
opscode -a aws-terraform-module-writer
```

Or press `/agents` inside an interactive session to open the subagent switcher modal.
