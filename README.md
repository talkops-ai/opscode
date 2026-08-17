<div align="center">

<img src="assets/opscode_logo.jpeg" alt="OpsCode" width="120">

# OpsCode

**A terminal-native AI agent for DevOps, SRE, and Platform Engineering. Ships with built-in subagents, skills and a plugin system to extend it to any stack. Built on LangGraph with modes to manage human in the loop.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-FF6F00.svg?style=flat-square&logo=langchain&logoColor=white)](https://langchain.com/)
[![Deep Agents SDK](https://img.shields.io/badge/framework-Deep%20Agents%20SDK-10B981.svg?style=flat-square)](https://docs.langchain.com/)
[![MCP Ready](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-009688.svg?style=flat-square)](https://modelcontextprotocol.io/)
[![Textual TUI](https://img.shields.io/badge/TUI-Textual-7C3AED.svg?style=flat-square)](https://textual.textualize.io/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square)](LICENSE)

[Quickstart](#-quickstart-30-seconds) • [Why OpsCode?](#%EF%B8%8F-why-opscode) • [Safety & Guardrails](#%EF%B8%8F-safety--guardrails) • [Subagents & Plugins](#-subagents--plugins) • [Architecture](#%EF%B8%8F-architecture) • [Docs](#-documentation)

</div>

---

## 🖥️ See It in Action

<!-- TODO: Replace this ASCII mock with a VHS-generated terminal GIF/video once recorded -->

```
┌─ OpsCode v0.1.1 ────────────────────────────────────────── [Auto: Shift+Tab] ──┐
│                                                                                │
│ > User: Create an AWS S3 bucket with KMS customer-managed key encryption       │
│                                                                                │
│ 🤖 OpsCode [aws-terraform-module-writer]                                       │
│ 💭 Analyzing AWS KMS & S3 security baseline...                                 │
│ 🛠️ Tool: mcp__aws__get_kms_policy_schema                                      │
│ 📝 Generating main.tf, variables.tf, outputs.tf                                │
│                                                                                │
│ ┌─ Proposed Diff: main.tf ───────────────────────────────────────────────────┐ │
│ │ + resource "aws_kms_key" "s3_key" {                                        │ │
│ │ +   description             = "KMS CMK for S3 bucket storage encryption"   │ │
│ │ +   deletion_window_in_days = 30                                           │ │
│ │ +   enable_key_rotation     = true                                         │ │
│ │ + }                                                                        │ │
│ │ + resource "aws_s3_bucket" "secure_bucket" {                               │ │
│ │ +   bucket = var.bucket_name                                               │ │
│ │ + }                                                                        │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│ ⚡ Action Required: [Approve (Enter)]  [Edit Diff (e)]  [Reject (Esc)]         │
└─────────────────────────────────────────────────────────── Model: claude-3.7-sonnet ┘
```

---

## ⚡ Quickstart (30 Seconds)

### 1. Install

```bash
curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/v0.1.1/scripts/install.sh | bash
```

> [!NOTE]
> **Windows users:** We strongly recommend running inside **WSL (Windows Subsystem for Linux)** for proper shell and toolchain compatibility.

### 2. Launch the TUI & Configure Your LLM

Start OpsCode by running:

```bash
ops
```

This opens the interactive terminal UI. Once inside, type the `/auth` slash command to open the credential manager and configure your model provider (Anthropic, OpenAI, Google, etc.):

```
/auth
```

Alternatively, you can export your API key directly in `~/.zshrc` or `~/.bashrc`:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# or: export OPENAI_API_KEY="sk-..."
# or: export GOOGLE_API_KEY="..."
```

### 3. Start Working

Once credentials are set, just type your prompt in the TUI chat input:

```
Generate a least-privilege AWS IAM policy for an S3 bucket
```

OpsCode will pick the right subagent, show you a syntax-highlighted diff, and wait for your approval before touching anything.

That's it. You're up and running.

---

## ⚖️ Why OpsCode?

General-purpose coding agents are great at application code. But they weren't built for infrastructure. They don't understand state locking, blast radius, or why running `terraform apply` without review is a terrible idea.

OpsCode is purpose-built for the infrastructure lifecycle — and here's why it stands apart.

### How It Compares

| Feature | Aider | OpenHands | Claude Code | OpsCode |
|---|:---:|:---:|:---:|:---:|
| **Interface** | Terminal CLI | Web Canvas / CLI | Terminal CLI | **Terminal TUI & Headless CLI** |
| **Focus** | Git-native app code | Full-stack software | General coding | **DevOps, SRE, & Platform IaC** |
| **Guardrails** | Git revert | Docker sandbox | User confirmation | **3-Tier Approval + Shell/Unicode Scanners** |
| **Multi-Agent Memory** | Shared context | Multi-agent threads | Monolithic context | **Isolated `BranchMemoryStore` per subagent** |
| **IaC State Safety** | — | — | — | **"Produce Diffs, Not Deployments"** |
| **Extensibility** | Limited | Plugin API | Skills/MCP | **Plugins, Marketplace, Custom Subagents, MCP** |
| **CI/CD Self-Grading** | — | Test suites | — | **Autonomous `--rubric` grader loops** |
| **MCP Integration** | — | Native | Native | **Native + 4-Tier Security Guard** |

### 1. Domain Expertise With Isolated Subagents

Generic coding agents dump hundreds of lines of raw Terraform schemas, Kubernetes manifests, and CLI errors straight into the main context window. That leads to context overflow and hallucinated configs.

OpsCode takes a different approach. It ships with **6 specialized subagents** — each running in its own isolated memory sandbox (`BranchMemoryStore`). When a subagent searches AWS docs or iterates on a broken plan, all that messy intermediate work stays inside the subagent. Only the final, validated result comes back to your workspace.

### 2. Extend It to Any Stack

The built-in subagents cover Terraform, OpenTofu, Kubernetes, Ansible, Jenkins, and GitHub Actions. But OpsCode is designed to be extended:

- **Plugin system:** Install plugins from a marketplace or drop them into `.opscode/plugins/` — each can bundle new skills, subagents, MCP servers, and slash commands.
- **Custom subagents:** Create your own subagents in `.opscode/agents/` or `~/.opscode/agents/` — just an `AGENTS.md` file with YAML frontmatter.
- **7-tier skill hierarchy:** Add skills at any level — built-in, plugin, user, or project — with deterministic priority resolution.
- **Async remote subagents:** Connect to remote LangGraph deployments via `config.toml` for distributed workloads.

### 3. Safety First, Not Unchecked Autonomy

Application code gone wrong? `git revert` and move on. Infrastructure gone wrong? Corrupted `.tfstate` files, dropped databases, public security groups — those create real damage with real blast radius.

OpsCode follows the **"Produce Diffs, Not Deployments"** principle:
- It generates plans, validates syntax, and inspects schemas.
- It shows you syntax-highlighted diffs and waits for your explicit approval.
- It will **not** run `terraform apply` or perform destructive operations without your consent.

### 4. Works in Your Terminal and Your Pipelines

OpsCode isn't just an interactive tool — it runs equally well in CI/CD:
- **Interactive TUI:** Rich Textual interface with live reasoning streams, `/model` hot-swapping, and `Shift+Tab` to toggle approval modes on the fly.
- **Headless Mode (`-n`):** Pipe it into Jenkins, GitHub Actions, or GitLab CI. Example: `cat pod.yaml | ops -n "..." --rubric @specs/k8s.md -y`

---

## 🛡️ Safety & Guardrails

Handing AI the keys to your infrastructure requires real trust. So we built OpsCode with multiple layers of defense — not as an afterthought, but as a core design principle.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        OpsCode Security Architecture                   │
├────────────────────────────────────────────────────────────────────────┤
│  User Request ──> Unicode & Shell Scanner ──> Approval Mode Evaluator  │
│                                                │                       │
│    ┌───────────────────┬───────────────────────┴────────────────────┐  │
│    ▼                   ▼                                            ▼  │
│ [Manual Mode]     [Auto Mode]                                  [YOLO]  │
│ Prompt on every   Auto-approves safe read-only                 Unrestricted │
│ mutating action   (ls, grep, tofu plan); gates destructive     (Explicit ACK) │
│    │                   │                                            │  │
│    └───────────────────┴───────────────────────┬────────────────────┘  │
│                                                ▼                       │
│                           Headless MCP Guard (4 Security Tiers)        │
│                           [READ_ONLY | MUTATING_SAFE | PRIVILEGED]     │
│                                                │                       │
│                                                ▼                       │
│                           "Produce Diffs, Not Deployments" (IaC Gate)  │
└────────────────────────────────────────────────────────────────────────┘
```

### 3-Tier Approval Engine

Switch between approval modes mid-session with **`Shift+Tab`**:

1. **Manual Mode (default):** Every shell command and file edit gets an interactive prompt — `[Approve]`, `[Reject]`, `[Edit Command]`, or `[Always Allow]`. Nothing runs without your say-so.
2. **Auto Mode (`-y`):** A classifier decides which commands are safe. Read-only commands (`ls`, `grep`, `kubectl get`, `tofu plan`) run automatically. Anything mutating or destructive stops and asks.
3. **YOLO Mode (`--yolo`):** Everything runs without prompting. You'll need to explicitly acknowledge the risk before this kicks in.

> [!TIP]
> Hit `Shift+Tab` at any time during an interactive session to flip between **Manual** and **Auto** modes.

> [!CAUTION]
> Don't run `--yolo` mode against production cloud accounts or live cluster contexts. Seriously.

### Multi-Layer Defense

- **Shell Safety Scanner:** Every shell command is classified before execution. You can configure allowlists to control what runs automatically (`-S recommended`, `-S all`, or a custom CSV list).
- **Unicode Security Scanner:** Catches Trojan Source attacks, bidirectional text manipulation, and homoglyph spoofing before they reach your codebase.
- **SSRF & URL Guard:** Blocks requests to cloud metadata endpoints (`169.254.169.254`), localhost, and private RFC-1918 ranges.
- **Headless MCP Guard:** When running unattended, OpsCode classifies each MCP tool into security tiers (read-only, mutating, destructive, privileged) and blocks anything unsafe.

---

## 🤖 Subagents & Plugins

OpsCode ships with **6 specialized subagents** out of the box. Each one has its own domain skills, isolated memory, and scoped tool bindings. They don't pollute each other's context.

```
                  ┌───────────────────────────────┐
                  │    Root Orchestration Agent    │
                  │   (Global Context & Router)    │
                  └───────────────┬───────────────┘
                                  │
      ┌──────────────┬────────────┼────────────┬──────────────┐
      ▼              ▼            ▼            ▼              ▼
┌───────────┐  ┌───────────┐┌───────────┐┌───────────┐  ┌───────────┐
│ OpenTofu  │  │ Terraform ││  Jenkins  ││  GitHub   │  │  Ansible  │
│Provisioner│  │  Writer   ││ Automater ││  Actions  │  │Provisioner│
└─────┬─────┘  └─────┬─────┘└─────┬─────┘└─────┬─────┘  └─────┬─────┘
      │              │            │            │              │
      └──────────────┴────────────┼────────────┴──────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │     Isolated Memory       │
                    │    (Per-Subagent Store)    │
                    └───────────────────────────┘
```

### Built-in Subagents

| Subagent | What It Does | Skills (34 Total) | MCP |
|---|---|---|:---:|
| **`aws-opentofu-provisioner`** | OpenTofu on AWS | `opentofu-data-security`, `opentofu-iam-security`, `opentofu-mcp-schema-lookup`, `opentofu-module-layout`, `opentofu-state-management`, `opentofu-testing-validation`, `opentofu-vpc-networking` | ✅ |
| **`aws-terraform-module-writer`** | Terraform on AWS | `aws-data-security-enforcement`, `aws-iam-policy-engine`, `aws-vpc-network-patterns`, `terraform-iteration-patterns`, `terraform-mcp-schema-lookup`, `terraform-module-layout`, `terraform-repair-loop` | ✅ |
| **`ci-jenkins-automater`** | Jenkins pipelines | `jenkins-job-dsl-jcasc`, `jenkins-pipeline-generation`, `jenkins-pipeline-testing`, `jenkins-shared-libraries` | — |
| **`github-actions-writer`** | GitHub workflows | `github-actions-architecture`, `github-actions-performance`, `github-actions-security-hardening`, `github-actions-vulnerability-mitigation` | — |
| **`infra-ansible-provisioner`** | Ansible automation | `ansible-code-authoring`, `ansible-environment-setup`, `ansible-execution-environments`, `ansible-linting-remediation`, `ansible-mcp-schema-lookup`, `ansible-runner-execution`, `ansible-security-operations` | ✅ |
| **`k8s-helm-provisioner`** | Kubernetes & Helm | `helm-chart-authoring`, `helm-deployment-recovery`, `helm-schema-validation`, `helm-security-secrets`, `helm-testing` | — |

### Bring Your Own Subagents & Skills

The 6 built-in subagents are just the starting point. You can extend OpsCode to cover any domain:

**Custom subagents** — Drop an `AGENTS.md` file with YAML frontmatter into a directory and OpsCode picks it up:

```
.opscode/agents/
└── sre-incident-responder/
    └── AGENTS.md          # name, description, system prompt, skills, tools
```

**Marketplace plugins** — Install community or team plugins that bundle subagents, skills, MCP configs, and commands:

```bash
ops plugin install kubernetes-sre@company-marketplace
```

**Plugin types:** OpsCode automatically distinguishes between two kinds:
- **Agent plugins** (have an `agents/` dir) — skills and MCP configs bind to the plugin's subagent only.
- **Non-agent plugins** (no `agents/` dir) — skills and MCP configs bind to the main root agent.

> [!IMPORTANT]
> **How context stays lean:** OpsCode uses progressive disclosure — subagent skills are only loaded when relevant files or tasks show up in your workspace. If you're not working on Terraform, those skills don't eat your token budget. This keeps hallucinations low and responses fast.

---

## 🏗️ Architecture

OpsCode is built on the **Deep Agents SDK** and **LangGraph** state machines. Every agent turn passes through a modular middleware pipeline that handles:

- **Context injection** — Git state, DevOps environment markers, and skill discovery
- **Model management** — Hot-swap models mid-session, track token usage and costs in real-time
- **Safety gates** — Shell command classification, MCP tool security tiers, and approval mode enforcement
- **Plugin & skill loading** — Discovers skills from 7 sources (built-in → plugins → user → project) and injects them on demand
- **Session continuity** — SQLite-backed thread checkpointing, context compaction, and session resume
- **Autonomous grading** — Rubric evaluation loops and goal acceptance criteria checks
- **Subagent orchestration** — Dispatches tasks to specialized subagents with isolated memory

See the [Overview doc](docs/opscode-docs/overview.md) for the full middleware breakdown.

### Skill Resolution

Skills are loaded from multiple locations. Project-level skills take priority over user-level, which take priority over plugins and built-in defaults:

```
Project skills (.opscode/skills/, .agents/skills/)
   ▲ overrides
User skills (~/.opscode/skills/, ~/.agents/skills/)
   ▲ overrides
Plugin skills (marketplace plugins)
   ▲ overrides
Built-in skills (ships with OpsCode)
```

### Supported Models & Providers

OpsCode works with **20+ providers** out of the box, with first-class streaming and extended reasoning:

- **Extended Thinking:** Claude 3.7 Sonnet Thinking, OpenAI o1 / o3-mini, Gemini 2.0 Flash Thinking, DeepSeek R1
- **Direct Providers:** Anthropic, OpenAI, Google GenAI, Vertex AI, Azure OpenAI, Groq, DeepSeek, Together AI, Fireworks AI, Mistral, NVIDIA NIM, Perplexity, Cohere, IBM watsonx, HuggingFace, LiteLLM, xAI, Baseten
- **Local / Offline:** Ollama (`ops -M ollama:llama3.3`)

---

## 🎯 CI/CD Rubric Grading

When running in automated pipelines, OpsCode can pair a worker agent with a dedicated grader model. The grader checks the output against your spec and feeds back specific failures until everything passes (or you hit the iteration limit):

```bash
opscode -n "Author a production Kubernetes deployment for an API service" \
  --rubric "1. Non-root user securityContext is configured.
2. Read-only root filesystem is enforced.
3. Liveness and readiness probes have timeout thresholds.
4. Resource limits and requests are defined.
5. PDB (PodDisruptionBudget) manifest is included." \
  --rubric-model "openai:gpt-4.1" \
  --rubric-max-iterations 3 \
  -y
```

```
┌────────────────────────────────────────────────────────┐
│                   Rubric Evaluation Loop               │
├────────────────────────────────────────────────────────┤
│ 1. Worker Agent creates initial infrastructure files   │
│ 2. Grader Model evaluates work tree against rubric     │
│ 3. If PASS ──> Return 0 and output final manifest      │
│ 4. If FAIL ──> Grader feeds back specific deficiency   │
│    report into Worker Agent context                    │
│ 5. Worker iterates on fixes and re-submits to Grader   │
│ 6. Repeats until PASS or max iterations reached        │
└────────────────────────────────────────────────────────┘
```

---

## 🚫 Not For You If...

We'd rather be upfront about what OpsCode isn't:

- ❌ **Not a replacement for code review.** Every infrastructure change should still be reviewed by a qualified engineer before it hits production.
- ❌ **Not an unmonitored deploy bot.** OpsCode produces diffs and plans. It doesn't blindly run `terraform apply -auto-approve` on your live environment.
- ❌ **Not for zero-IaC-knowledge users.** You need to understand Terraform, Kubernetes, or Ansible basics to meaningfully review what the agent proposes. If you can't read the diff, you shouldn't approve it.

---

## 📖 Documentation

Full docs live in [`docs/opscode-docs/`](docs/opscode-docs/):

| Guide | Topic |
|---|---|
| 📄 **[Overview](docs/opscode-docs/overview.md)** | What OpsCode can do, core tools, and data paths |
| 🚀 **[Quickstart](docs/opscode-docs/quickstart.md)** | Install, launch the TUI, and run your first task |
| 💻 **[CLI Reference](docs/opscode-docs/cli-reference.md)** | All CLI flags, subcommands, and slash commands |
| ⚙️ **[Configuration](docs/opscode-docs/Configuration.md)** | Environment variables, `.opscode` directories, and settings |
| 📝 **[config.toml Reference](docs/opscode-docs/config.toml.md)** | Full config file schema — models, UI, tools, permissions |
| 🔑 **[Provider Credentials](docs/opscode-docs/credentials.md)** | Set up API keys using `/auth` or environment variables |
| 🛡️ **[Approval Modes & Security](docs/opscode-docs/approval-mode.md)** | Manual, Auto, and YOLO modes with shell allowlists |
| 🤖 **[Subagents](docs/opscode-docs/subagents.md)** | Built-in and custom subagents with isolated memory |
| 🧠 **[Memory & Skills](docs/opscode-docs/memory-and-skills.md)** | Persistent memory, reusable skills, and the `remember` command |
| 🔌 **[MCP Tools](docs/opscode-docs/mcp-tools.md)** | Add external tools via Model Context Protocol |
| 📦 **[Plugins & Marketplace](docs/opscode-docs/plugins.md)** | Install and create plugins, manage marketplaces |
| 🪝 **[Hooks](docs/opscode-docs/hooks.md)** | Run custom logic before or after tool execution |
| 🤖 **[Model Providers](docs/opscode-docs/model-providers.md)** | 20+ supported providers, extended thinking, and Ollama |
| 🎯 **[Goals & Rubrics](docs/opscode-docs/goal-and-rubrics.md)** | Set goals interactively or grade work in CI/CD |
| ☁️ **[Remote Sandboxes](docs/opscode-docs/remote-sandboxes.md)** | Run in ephemeral cloud sandboxes instead of locally |

---

## 🛠️ CLI Cheat Sheet

```bash
# Basic Usage
opscode [OPTIONS] [PROMPT]
ops [OPTIONS] [PROMPT]

# Subcommands
ops auth list | set <provider> | remove <provider>
ops config show | list | get <key> | set <key> <value>
ops plugin list | install <id> | uninstall <id> | marketplace add <url>
ops skills list | info <name> | find <query> | create <name>
ops mcp list | tools | test <server>
ops threads list | delete <id>
ops agents list | reset --agent <name>
ops doctor

# Key Flags
-n, --non-interactive TEXT       # Run a single task headlessly
-r, --resume [ID]                # Resume a previous thread
-M, --model MODEL                # Model specifier (provider:model)
-a, --agent NAME                 # Launch with a specific subagent
-s, --skill NAME                 # Pre-load a specific skill
-y, --auto-approve               # Auto mode (classifier-backed)
--yolo                           # YOLO mode (everything auto-approved)
-S, --shell-allow-list LIST      # Shell allowlist (recommended, all, CSV)
--goal TEXT                      # Interactive goal with acceptance criteria
--rubric TEXT|@PATH              # Autonomous rubric grading loop
--rubric-model MODEL             # Grader model for rubric evaluation
--sandbox [TYPE]                 # Ephemeral cloud sandbox provider
```

---

## 🤝 Contributing

We'd love your help. Check out our [Contributing Guidelines](CONTRIBUTING.md) and [Security Policy](SECURITY.md) before opening a PR.

```bash
git clone https://github.com/talkops-ai/opscode.git
cd opscode
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,test-integration]"
uv run pytest tests/ -m unit -v
```

---

## 📄 License

OpsCode is open-source under the [Apache License 2.0](LICENSE).
