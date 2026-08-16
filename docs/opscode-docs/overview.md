# OpsCode — AI DevOps & Coding Agent

> Terminal-first autonomous coding and orchestration agent purpose-built for DevOps, SRE, Platform Engineering, and Infrastructure-as-Code.

OpsCode is an enterprise-ready CLI agent built on the [Deep Agents SDK](https://docs.langchain.com/oss/python/deepagents/quickstart) and [LangGraph](https://docs.langchain.com/langgraph) state machines. It works with 20+ tool-calling LLM providers (Anthropic, OpenAI, Google, and more). An 18-middleware execution pipeline, persistent SQLite session checkpointing, a 7-tier skill resolution hierarchy, 6 specialized DevOps subagents, and a classifier-backed human-in-the-loop approval engine ensure safe and deterministic infrastructure orchestration.

Unlike general-purpose coding agents, OpsCode ships with first-class support for Terraform, OpenTofu, Kubernetes, Helm, Ansible, GitHub Actions, Jenkins, and cloud platforms (AWS, Azure, GCP) — including native execution tools, domain-specific subagents, isolated branch memory, and embedded MCP integrations.

## Quick install

```bash
# Standalone installation
curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/v0.1.0/scripts/install.sh | bash

# Launch OpsCode interactive TUI (or use short alias 'ops')
opscode
# or: ops
```

See the [Quickstart](./quickstart.md) to configure provider credentials, run your first task, and explore interactive mode.

## Capabilities

### Native Core Tools & Execution Engine

OpsCode executes operations through native core tools, shell execution with safety controls, and dynamic MCP servers:

| Tool | Category | Description |
|---|---|---|
| `execute` | Terminal / Subprocess | Shell command execution with stdout/stderr capture, timeouts, and allowlist checking |
| `read_file` | Filesystem | Chunked file reading with offset and limit |
| `write_file` | Filesystem | Full file creation and overwrite |
| `edit_file` | Filesystem | Precision string and regex replacement |
| `delete` | Filesystem | Destructive file removal (strictly gated) |
| `glob` | Filesystem | Pattern-based file search |
| `grep` | Filesystem / Ripgrep | High-speed content search with regex and glob filtering |
| `ls` | Filesystem | Directory structure listing |
| `web_search` | Tavily API | Real-time web search for docs, CVEs, error codes, and release notes |
| `fetch_url` | HTTP Client | Markdown extraction from documentation URLs with SSRF protection |
| `get_current_thread_id` | State | Thread identifier inspection |
| `get_goal` / `update_goal` | Goal System | Acceptance criteria inspection and state transitions |
| `get_rubric` | Rubric System | Rubric specification retrieval |
| `js_eval` | QuickJS REPL | In-memory JavaScript code evaluation (PTC interpreter) |

### Built-in Global Deep Agent Skills

OpsCode includes 4 core deep agent skills loaded into the root agent prompt:

| Skill | Domain | Description |
|---|---|---|
| `cloud-core` | Cloud Infrastructure | Cloud infrastructure fundamentals, IAM principles, networking topologies, resource tagging, and cost governance |
| `docker` | Containers | Dockerfile best practices, multi-stage builds, rootless security, minimal base images (Distroless/Alpine), caching optimization |
| `kubernetes` | Orchestration | K8s manifests, Pod Security Standards, resource quotas, affinity/anti-affinity, probes, RBAC, NetworkPolicies |
| `remember` | Memory & Knowledge | Active conversation review to extract learnings and persist them directly into `AGENTS.md` memory or generate new reusable skills |

Skills are resolved across a **7-Tier Resolution Hierarchy** (Built-in → Plugin → User OpsCode → User Agents → Project OpsCode → Project Agents → Claude Experimental). See [Memory and Skills](./memory-and-skills.md) for details.

### Built-in Enterprise DevOps Subagents

OpsCode ships with **6 production-ready DevOps subagents**, each bundling specialized system prompts, references, boilerplate templates, and dedicated domain skills:

| Subagent | Domain | Skills Bundled |
|---|---|---|
| **`aws-opentofu-provisioner`** | OpenTofu / AWS | 7 skills (`opentofu-data-security`, `opentofu-iam-security`, `opentofu-mcp-schema-lookup`, `opentofu-module-layout`, `opentofu-state-management`, `opentofu-testing-validation`, `opentofu-vpc-networking`) |
| **`aws-terraform-module-writer`** | Terraform / AWS | 7 skills (`aws-data-security-enforcement`, `aws-iam-policy-engine`, `aws-vpc-network-patterns`, `terraform-iteration-patterns`, `terraform-mcp-schema-lookup`, `terraform-module-layout`, `terraform-repair-loop`) |
| **`ci-jenkins-automater`** | Jenkins / CI | 4 skills (`jenkins-job-dsl-jcasc`, `jenkins-pipeline-generation`, `jenkins-pipeline-testing`, `jenkins-shared-libraries`) |
| **`github-actions-writer`** | GitHub Actions / CI | 4 skills (`github-actions-architecture`, `github-actions-performance`, `github-actions-security-hardening`, `github-actions-vulnerability-mitigation`) |
| **`infra-ansible-provisioner`** | Ansible / Automation | 7 skills (`ansible-code-authoring`, `ansible-environment-setup`, `ansible-execution-environments`, `ansible-linting-remediation`, `ansible-mcp-schema-lookup`, `ansible-runner-execution`, `ansible-security-operations`) |
| **`k8s-helm-provisioner`** | Kubernetes / Helm | 5 skills (`helm-chart-authoring`, `helm-deployment-recovery`, `helm-schema-validation`, `helm-security-secrets`, `helm-testing`) |

Subagents run with **isolated branch memory** (`BranchMemoryStore`), tool filtering proxies (`tools:`), skill whitelisting (`skills:`), and optional embedded MCP configurations (`.mcp.json`). See [Subagents](./subagents.md).

### Platform Features

| Feature | Description |
|---|---|
| **18-Middleware Turn Pipeline** | Modular execution stack handling context injection, model hot-swapping, cost tracking, hooks, MCP, compaction, and rubric grading |
| **Memory (`AGENTS.md`)** | Project-scoped and user-scoped persistent memory across sessions |
| **7-Tier Skill Hierarchy** | Strict precedence hierarchy from built-in skills to project overrides |
| **MCP Tools & Headless Guard** | Dynamic Model Context Protocol client with 4-tier security classification (`READ_ONLY`, `MUTATING_SAFE`, `MUTATING_DESTRUCTIVE`, `PRIVILEGED`) |
| **Plugins & Marketplaces** | Marketplace plugin discovery, bifurcating agent plugins (scoped to subagents) and non-agent plugins (scoped to main agent) |
| **3 Approval Modes** | Manual, Auto (classifier-backed via `AutoModeHITLMiddleware`), and YOLO modes with `Shift+Tab` runtime cycling |
| **Goals & Rubrics** | Interactive acceptance criteria generation and non-interactive self-evaluation grading loops |
| **Remote Sandboxes** | Isolated execution in remote sandbox environments (AgentCore, Daytona, LangSmith, Modal, Runloop, Vercel) |
| **Context Compaction** | Automated token summarization preserving critical decisions when context limits approach |
| **Cost & Token Tracking** | Real-time token consumption and USD cost calculation across 20+ model providers via `genai-prices` |
| **Server Hooks Bus** | Pre/post tool execution event dispatch to `hooks.json` handlers |

### DevOps Environment Awareness

OpsCode automatically detects and preserves DevOps environment variables:

- **Kubernetes**: `KUBECONFIG`, `KUBE_CONTEXT`
- **AWS**: `AWS_PROFILE`, `AWS_REGION`, `AWS_DEFAULT_REGION`, `AWS_SHARED_CREDENTIALS_FILE`
- **GCP**: `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT`, `CLOUDSDK_CORE_PROJECT`
- **Azure**: `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`
- **Ansible**: `ANSIBLE_CONFIG`, `ANSIBLE_INVENTORY`
- **Helm**: `HELM_HOME`, `HELM_REPOSITORY_CONFIG`
- **ArgoCD**: `ARGOCD_SERVER`, `ARGOCD_AUTH_TOKEN`
- **Terraform / OpenTofu**: `TF_CLI_CONFIG_FILE`, `TERRAGRUNT_CONFIG`

OpsCode recognizes DevOps-specific project root markers (`terragrunt.hcl`, `Chart.yaml`, `ansible.cfg`, `.opscode/`) alongside standard repository markers (`.git`, `pyproject.toml`, `package.json`, `Makefile`).

## Architecture

OpsCode is built on:

- **[Deep Agents SDK](https://docs.langchain.com/oss/python/deepagents/quickstart)** — Agent framework with turn streaming, subagent compilation, and middleware
- **[LangGraph](https://docs.langchain.com/langgraph)** — Stateful agent orchestration with SQLite checkpointing (`idx_opscode_threads_list`)
- **[LangChain](https://docs.langchain.com/)** — LLM provider abstraction and tool interfaces
- **[Textual](https://textual.textualize.io/)** — Terminal UI framework with modular widgets for diff rendering, status monitoring, and approval modals
- **[MCP](https://modelcontextprotocol.io/)** — Model Context Protocol for external tool integration

### Data locations

| Path | Purpose |
|---|---|
| `~/.opscode/` | User data root |
| `~/.opscode/config.toml` | Main configuration file |
| `~/.opscode/.env` | API keys and secrets |
| `~/.opscode/.mcp.json` | Global MCP server definitions |
| `~/.opscode/hooks.json` | Lifecycle hooks |
| `~/.opscode/memory/` | User-scoped memory entries |
| `~/.opscode/.state/` | Managed state (`sessions.db`, `auth.json`, trust stores) |
| `.opscode/` | Project-level configuration root |
| `.opscode/skills/` | Project skills |
| `.opscode/agents/` | Project subagents |
| `.opscode/plugins/` | Project plugins |
| `.opscode/memory/` | Project-scoped memory |

## Next steps

- **[Quickstart](./quickstart.md)** — Install OpsCode, run your first task, and explore interactive and non-interactive workflows.
- **[Configuration](./Configuration.md)** — Set up credentials, `config.toml`, environment variables, hooks, and CLI flags.
- **[CLI Reference](./cli-reference.md)** — Complete command-line flags and slash commands.
