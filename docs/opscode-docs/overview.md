# OpsCode

> Terminal-native AI agent for DevOps, SRE, and Platform Engineering

OpsCode is an open-source coding agent built on the [Deep Agents SDK](https://docs.langchain.com/oss/python/deepagents/quickstart) and [LangGraph](https://docs.langchain.com/langgraph). It works with 20+ LLM providers (Anthropic, OpenAI, Google, and more), ships with 6 specialized DevOps subagents, and can be extended with custom skills, plugins, and MCP servers.

Unlike general-purpose coding agents, OpsCode understands infrastructure. It knows about state locking, blast radius, IAM policies, and why `terraform apply` without review is a terrible idea. It produces diffs and plans — not unreviewed deployments.

## Quick install

```bash
curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/v0.1.1/scripts/install.sh | bash

# Launch the interactive TUI
ops
```

See the [Quickstart](./quickstart.md) to configure provider credentials and run your first task.

## Capabilities

### Core tools

OpsCode comes with a set of built-in tools for filesystem operations, shell execution, web search, and more:

| Tool | What it does |
|---|---|
| `execute` | Run shell commands with stdout/stderr capture, timeouts, and safety checks |
| `read_file` / `write_file` / `edit_file` | Read, create, and edit files with precision replacements |
| `delete` | Remove files (gated behind approval) |
| `glob` / `grep` / `ls` | Search and browse the filesystem |
| `web_search` | Search the web for docs, CVEs, error codes, and release notes |
| `fetch_url` | Extract content from documentation URLs |
| `js_eval` | Evaluate JavaScript in an in-memory QuickJS interpreter |
| `get_goal` / `update_goal` | Inspect and update goal acceptance criteria |
| `get_rubric` | Retrieve rubric specifications for self-evaluation |

### Built-in skills

Four global skills are always available to the root agent:

| Skill | What it covers |
|---|---|
| `cloud-core` | Cloud infrastructure fundamentals — IAM, networking, tagging, cost governance |
| `docker` | Dockerfile best practices, multi-stage builds, rootless security, caching |
| `kubernetes` | K8s manifests, Pod Security Standards, RBAC, NetworkPolicies, probes |
| `remember` | Saves learnings and conventions to persistent memory or new reusable skills |

Skills are loaded from multiple locations with a clear priority order — project-level skills override user-level, which override plugin and built-in defaults. See [Memory and Skills](./memory-and-skills.md) for the full resolution order.

### Built-in subagents

OpsCode ships with 6 DevOps subagents, each with their own system prompts, domain skills, and isolated memory:

| Subagent | Domain | Skills |
|---|---|---|
| **`aws-opentofu-provisioner`** | OpenTofu on AWS | 7 skills covering IAM, VPC, state management, testing, and MCP schema lookup |
| **`aws-terraform-module-writer`** | Terraform on AWS | 7 skills for IAM policies, VPC patterns, module layout, and repair loops |
| **`ci-jenkins-automater`** | Jenkins CI | 4 skills for pipeline generation, Job DSL, shared libraries, and testing |
| **`github-actions-writer`** | GitHub Actions | 4 skills for workflow architecture, performance, and security hardening |
| **`infra-ansible-provisioner`** | Ansible | 7 skills for playbook authoring, linting, execution environments, and security |
| **`k8s-helm-provisioner`** | Kubernetes & Helm | 5 skills for chart authoring, schema validation, secrets, and deployment recovery |

Each subagent runs with isolated memory — intermediate work (AWS doc searches, plan iterations) stays inside the subagent and doesn't pollute your main context. See [Subagents](./subagents.md).

### Platform features

| Feature | What it does |
|---|---|
| **Persistent memory** | Project-scoped and user-scoped `AGENTS.md` files carry context across sessions |
| **Skill hierarchy** | Skills are discovered from built-in, plugin, user, and project directories with clear precedence |
| **MCP tools** | Connect external tools via Model Context Protocol — with automatic security classification in headless mode |
| **Plugins & marketplaces** | Install community or team plugins that bundle skills, subagents, MCP servers, and commands |
| **3 approval modes** | Manual, Auto, and YOLO — switch mid-session with `Shift+Tab` |
| **Goals & rubrics** | Set interactive goals with acceptance criteria, or grade work automatically in CI/CD |
| **Remote sandboxes** | Run in ephemeral cloud environments (AgentCore, Daytona, Modal, and more) |
| **Context compaction** | Automatically summarizes older messages when approaching context limits |
| **Cost tracking** | Real-time token usage and USD cost calculation across all providers |
| **Hooks** | Run custom logic before or after tool execution via `hooks.json` |

### DevOps environment awareness

OpsCode automatically detects and preserves your infrastructure environment:

- **Kubernetes**: `KUBECONFIG`, `KUBE_CONTEXT`
- **AWS**: `AWS_PROFILE`, `AWS_REGION`, `AWS_DEFAULT_REGION`
- **GCP**: `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT`
- **Azure**: `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`
- **Ansible**: `ANSIBLE_CONFIG`, `ANSIBLE_INVENTORY`
- **Helm**: `HELM_HOME`, `HELM_REPOSITORY_CONFIG`
- **ArgoCD**: `ARGOCD_SERVER`, `ARGOCD_AUTH_TOKEN`
- **Terraform / OpenTofu**: `TF_CLI_CONFIG_FILE`, `TERRAGRUNT_CONFIG`

It also recognizes DevOps project markers (`terragrunt.hcl`, `Chart.yaml`, `ansible.cfg`, `.opscode/`) alongside standard ones (`.git`, `pyproject.toml`, `package.json`).

## Architecture

OpsCode is built on:

- **[Deep Agents SDK](https://docs.langchain.com/oss/python/deepagents/quickstart)** — Agent framework with turn streaming, subagent orchestration, and middleware
- **[LangGraph](https://docs.langchain.com/langgraph)** — Stateful agent orchestration with SQLite checkpointing
- **[LangChain](https://docs.langchain.com/)** — LLM provider abstraction and tool interfaces
- **[Textual](https://textual.textualize.io/)** — Terminal UI framework for the interactive TUI
- **[MCP](https://modelcontextprotocol.io/)** — Model Context Protocol for external tool integration

Every agent turn passes through a modular middleware pipeline that handles context injection, model hot-swapping, safety classification, skill discovery, session checkpointing, rubric grading, and subagent dispatch.

### Data locations

| Path | What it stores |
|---|---|
| `~/.opscode/` | User data root |
| `~/.opscode/config.toml` | Main configuration |
| `~/.opscode/.env` | API keys and secrets |
| `~/.opscode/.mcp.json` | Global MCP server definitions |
| `~/.opscode/hooks.json` | Lifecycle hooks |
| `~/.opscode/memory/` | User-scoped memory entries |
| `~/.opscode/.state/` | Session database, auth state, trust stores |
| `.opscode/` | Project-level configuration |
| `.opscode/skills/` | Project skills |
| `.opscode/agents/` | Project subagents |
| `.opscode/plugins/` | Project plugins |
| `.opscode/memory/` | Project-scoped memory |

## Next steps

- **[Quickstart](./quickstart.md)** — Install OpsCode, launch the TUI, and run your first task.
- **[Configuration](./Configuration.md)** — Set up `config.toml`, environment variables, and data locations.
- **[CLI Reference](./cli-reference.md)** — Complete flag and subcommand reference.
