# Subagents

> Delegate specialized tasks to domain subagents with isolated memory and scoped tools

OpsCode can delegate tasks to specialized subagents. Each subagent runs with its own system prompt, isolated memory, scoped tool permissions, and domain-specific skills. When a subagent searches documentation or iterates on a broken plan, all that intermediate work stays inside the subagent — only the final result comes back to your main conversation.

## How subagents work

The main OpsCode agent acts as an orchestrator. It has 4 global skills (cloud-core, docker, kubernetes, remember) and delegates domain-specific work to subagents:

```
Main Agent (Global Context)
 ├── Global Skills: cloud-core, docker, kubernetes, remember
 └── Subagents (Delegated Execution)
      ├── aws-opentofu-provisioner (7 OpenTofu skills + AWS MCP)
      ├── aws-terraform-module-writer (7 Terraform skills + AWS MCP)
      ├── ci-jenkins-automater (4 Jenkins skills)
      ├── github-actions-writer (4 GitHub Actions skills)
      ├── infra-ansible-provisioner (7 Ansible skills + Ansible MCP)
      └── k8s-helm-provisioner (5 Helm skills)
```

Subagent skills are only loaded when that subagent is active — they don't eat into your token budget during general conversation.

## Define custom subagents

Each subagent lives in its own folder with an `AGENTS.md` file:

```
.opscode/agents/{subagent-name}/AGENTS.md   # Project-level (Git-tracked)
~/.opscode/{agent}/agents/{subagent-name}/AGENTS.md  # User-level
```

Project subagents override user subagents with the same name.

### File format

```markdown
---
name: terraform-reviewer
description: Review Terraform and OpenTofu modules for security and best practices
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

The markdown body below the frontmatter becomes the subagent's system prompt. See [Subagent frontmatter fields](#subagent-frontmatter-fields) for the full list of supported fields.

## Built-in subagents

OpsCode ships with 6 subagents covering common DevOps domains:

### `aws-opentofu-provisioner`
Provisions OpenTofu infrastructure on AWS — state encryption with KMS, S3/DynamoDB backends, cross-account IAM roles, and CI/CD workflows.
- **Skills (7):** `opentofu-data-security`, `opentofu-iam-security`, `opentofu-mcp-schema-lookup`, `opentofu-module-layout`, `opentofu-state-management`, `opentofu-testing-validation`, `opentofu-vpc-networking`
- **MCP:** AWS integration via embedded `.mcp.json`

### `aws-terraform-module-writer`
Authors AWS Terraform modules following HashiCorp best practices — multi-account architecture, remote state, and live AWS queries.
- **Skills (7):** `aws-data-security-enforcement`, `aws-iam-policy-engine`, `aws-vpc-network-patterns`, `terraform-iteration-patterns`, `terraform-mcp-schema-lookup`, `terraform-module-layout`, `terraform-repair-loop`
- **MCP:** AWS integration via embedded `.mcp.json`

### `ci-jenkins-automater`
Scaffolds Jenkins declarative pipelines, shared libraries, Job DSL, and Kubernetes-based agent pods.
- **Skills (4):** `jenkins-job-dsl-jcasc`, `jenkins-pipeline-generation`, `jenkins-pipeline-testing`, `jenkins-shared-libraries`

### `github-actions-writer`
Generates hardened GitHub Actions workflows with OIDC cloud authentication, concurrency controls, and matrix strategies.
- **Skills (4):** `github-actions-architecture`, `github-actions-performance`, `github-actions-security-hardening`, `github-actions-vulnerability-mitigation`

### `infra-ansible-provisioner`
Scaffolds Ansible playbooks, role structures, Vault encryption, Molecule testing, and dynamic inventory.
- **Skills (7):** `ansible-code-authoring`, `ansible-environment-setup`, `ansible-execution-environments`, `ansible-linting-remediation`, `ansible-mcp-schema-lookup`, `ansible-runner-execution`, `ansible-security-operations`
- **MCP:** Ansible integration via embedded `.mcp.json`

### `k8s-helm-provisioner`
Builds production Helm charts with values schemas, template helpers, dry-run debugging, and Pod Security Standard hardening.
- **Skills (5):** `helm-chart-authoring`, `helm-deployment-recovery`, `helm-schema-validation`, `helm-security-secrets`, `helm-testing`

## Plugin subagents

Plugins can also introduce subagents. When a plugin has an `agents/` directory, OpsCode treats it as an **agent plugin** — its skills, MCP servers, and commands bind exclusively to the plugin's subagent, not the main agent.

For example, a `terraform-linter` agent plugin defines a subagent with scoped tools and skills:

```markdown
---
name: terraform-linter
description: Lints and validates Terraform modules for formatting, syntax errors, and best-practice compliance.
tools: read_file, execute, glob, grep
skills:
  - tf-fmt-check
  - tf-validate
permission_tier: read-write
---

You are the **Terraform Linter** — a senior infrastructure engineer who specializes in Terraform code quality.
```

Key differences from custom subagents:

- Plugin subagents are discovered from `plugins/{plugin-name}/agents/` instead of `.opscode/agents/`.
- Their skills are loaded from the plugin's own `skills/` directory, not the global skill hierarchy.
- They can bundle their own MCP servers via the plugin's `.mcp.json`.
- They're enabled/disabled through the plugin manager (`/plugins`), not individually.

See [Plugins](./plugins.md) for the full plugin architecture.

### Subagent frontmatter fields

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Unique identifier for the subagent |
| `description` | Yes | What the subagent does — the main agent uses this to decide when to delegate |
| `model` | No | Model override in `provider:model-name` format. Omit to use the main agent's model |
| `skills` | No | List of skill names to load when this subagent is active |
| `tools` | No | Tool patterns this subagent is allowed to use (e.g. `read_file, execute, glob, grep`) |
| `permission_tier` | No | Permission level: `read-only` (default) or `read-write` |

## Dynamic subagents

OpsCode ships with the code interpreter enabled, so dynamic subagents work out of the box. Dynamic subagents are spawned at runtime — not predefined in `AGENTS.md` — by using the built-in `task()` function inside the interpreter.

To trigger dynamic subagents, ask for a "workflow". Instead of doing the work itself, the agent writes an orchestration script that calls `task()` and runs it in the code interpreter:

```
Run a workflow to review every Terraform module in modules/ for security issues
```

The agent generates something like:

```javascript
// Phase 1: Discover modules
const modules = await glob("modules/*/main.tf");

// Phase 2: Review each module in parallel
const results = await Promise.all(
  modules.map(mod => task(`Review ${mod} for IAM wildcards, open security groups, and unencrypted storage`))
);
```

As subagents spawn, OpsCode shows them live in the **dynamic subagents panel** in the TUI, grouped into phases by dispatch.

Dynamic subagents are useful for parallelizing repetitive tasks across many files, modules, or services — like reviewing 20 Terraform modules or validating 50 Kubernetes manifests.

## How isolation works

Each subagent runs with isolated memory. Intermediate reasoning, search results, and sub-steps stay inside the subagent and don't pollute your main conversation's context window. Only the final summary and output files return to you.

Subagents are also restricted to their declared toolset. A Terraform subagent can only use the tools listed in its definition — it can't access tools from other subagents.

Some subagents bundle their own MCP server configurations. These MCP sessions start when the subagent is invoked and stop when it finishes.

## Use subagents

Subagents are delegated to automatically when the main agent detects a matching request:

```
Create a hardened GitHub Actions workflow that deploys an EKS Helm chart
```

The agent delegates to `github-actions-writer` and `k8s-helm-provisioner` as needed.

### Launch with a specific subagent

```bash
ops -a aws-terraform-module-writer
```

### Switch subagents in a session

Use `/agents` inside an interactive session to browse and switch between available subagents.

### Cost-efficient subagents

Use a cheaper model for delegation tasks while keeping your main agent on a more capable model:

```markdown
---
name: general-purpose
description: General-purpose agent for research and multi-step tasks
model: anthropic:claude-haiku-4-5-20251001
---

You are a general-purpose assistant. Complete the task efficiently and return a concise summary.
```
