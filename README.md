<div align="center">

# ⚡ OpsCode

**A terminal-native AI agent that safely writes, refactors, and validates Terraform, Kubernetes, and CI/CD pipelines. Built on LangGraph with strict human-in-the-loop guardrails.**

[![CI Pipeline](https://github.com/talkops-ai/opscode/actions/workflows/ci.yml/badge.svg)](https://github.com/talkops-ai/opscode/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-FF6F00.svg?style=flat-square&logo=langchain&logoColor=white)](https://langchain.com/)
[![Deep Agents SDK](https://img.shields.io/badge/framework-Deep%20Agents-10B981.svg?style=flat-square)](https://docs.langchain.com/)
[![MCP Ready](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-009688.svg?style=flat-square)](https://modelcontextprotocol.io/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square)](LICENSE)

[Quickstart](#-quickstart-30-seconds) • [Why OpsCode?](#-why-opscode-strategic-differentiators) • [Safety & Guardrails](#-safety--guardrails-engineering-trust-in-iac) • [Architecture](#-architecture--multi-agent-state-machines) • [Subagents](#-built-in-enterprise-devops-subagents) • [Documentation](#-documentation-index)

</div>

---

## 🖥️ Terminal Interface

```
┌─ OpsCode v0.1.0 ────────────────────────────────────────── [Auto: Shift+Tab] ──┐
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
│ ⚡ Action Required: [Approve (Enter)]  [Edit Diff (e)]  [Reject (Esc)]           │
└─────────────────────────────────────────────────────── Model: claude-3.7-sonnet ┘
```

---

## ⚡ Quickstart (30 Seconds)

### 1. Install

Install OpsCode directly into your environment:

```bash
curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/v0.1.0/scripts/install.sh | bash
```

> [!NOTE]
> **Windows Users:** Running inside **WSL (Windows Subsystem for Linux)** is strongly recommended for native shell execution and toolchain compatibility.

### 2. Configure Credentials

Launch the credential wizard to connect your model provider:

```bash
ops /auth
```

Or export your API key in your terminal profile (`~/.zshrc` / `~/.bashrc`):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# or: export OPENAI_API_KEY="sk-..."
# or: export GOOGLE_API_KEY="..."
```

### 3. Run Your First Task

```bash
# Interactive TUI mode:
ops -m "Generate a least-privilege AWS IAM policy for an S3 bucket"

# Or non-interactive CI/CD execution:
ops -n "Run tofu validate and fix any missing variable declarations"
```

---

## ⚖️ Why OpsCode? (Strategic Differentiators)

General-purpose AI coding assistants excel at application code, but lack the domain safety, state locking awareness, and toolchain integration required for cloud infrastructure. OpsCode is purpose-built for the infrastructure lifecycle.

### Comparison: AI Coding Agents

| Feature | Aider | OpenHands | Claude Code | OpsCode |
|---|:---:|:---:|:---:|:---:|
| **Primary Interface** | Terminal CLI | Web Canvas / CLI | Terminal CLI | **Terminal TUI & Headless CLI** |
| **Core Focus** | Git-native App Code | Full-stack Software | General Coding | **DevOps, SRE, & Platform IaC** |
| **Execution Guardrails** | Git Revert | Docker Sandbox | User Confirmation | **3-Tier Approval + Shell/Unicode Scanners** |
| **Multi-Agent Memory** | Shared Context | Multi-Agent Threads | Monolithic Context | **Isolated `BranchMemoryStore` Subagents** |
| **IaC State Protection** | — | — | — | **"Produce Diffs, Not Deployments"** |
| **CI/CD Self-Evaluation** | — | Test Suites | — | **Autonomous `--rubric` Grader Loops** |
| **MCP Integration** | — | Native | Native | **Native + 4-Tier Security Guard** |

### 1. Domain Expertise vs. Generalist
Generic coding agents pollute the main context window with hundreds of lines of raw Terraform schema lookups, Kubernetes manifests, and CLI errors, causing context overflow and hallucinated configurations. OpsCode uses **6 specialized subagents** that operate in isolated memory sandboxes (`BranchMemoryStore`). Intermediate reasoning tokens, documentation searches, and failed plan outputs are resolved inside the subagent, returning only the final, validated configuration to your workspace.

### 2. Safety vs. Unchecked Autonomy
Application code can be rolled back with `git revert`. Infrastructure failures (corrupted `.tfstate` files, dropped databases, public security groups) create catastrophic blast radiuses. OpsCode follows the **"Produce Diffs, Not Deployments"** principle:
- It generates plans, validates syntax, and inspects schemas.
- It presents visual, syntax-highlighted diffs for explicit human approval.
- It is architecturally restrained from performing un-sandboxed `terraform apply` or destructive deletions without human consent.

### 3. Dual-Mode: Interactive TUI & Headless CI/CD
OpsCode is equally comfortable in your local terminal and in your automated CI/CD pipelines:
- **Interactive TUI:** Rich Textual interface with real-time reasoning streams, `/model` hot-swapping, and `Shift+Tab` approval mode toggling.
- **Headless Mode (`-n`):** Pipe stdout/stdin in Jenkins, GitHub Actions, or GitLab CI (`cat pod.yaml | ops -n "..." --rubric @specs/k8s.md -y`).

---

## 🛡️ Safety & Guardrails: Engineering Trust in IaC

Deploying AI to infrastructure requires strict, deterministic controls. OpsCode implements multi-layer defense mechanisms at every stage of execution.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        OpsCode Security Architecture                   │
├────────────────────────────────────────────────────────────────────────┤
│  User Request ──> Unicode & Shell Scanner ──> Approval Mode Evaluator   │
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
│                           "Produce Diffs, Not Deployments" (IaC Gate) │
└────────────────────────────────────────────────────────────────────────┘
```

### 3-Tier Approval Safety Engine

Cycle instantly between approval modes during an active session using **`Shift+Tab`**:

1. **Manual Mode (Default):** Prompts an interactive modal for every shell execution and file modification (`[Approve]`, `[Reject]`, `[Edit Command]`, `[Always Allow]`).
2. **Auto Mode (`-y`, `--auto-approve`):** Powered by `AutoModeHITLMiddleware` and `security/shell_safety.py`. Automatically approves safe, read-only commands (`ls`, `grep`, `kubectl get`, `tofu plan`) while strictly halting before any mutating or destructive action.
3. **YOLO Mode (`--yolo`):** Executes all actions without prompting. Requires initial explicit acknowledgement of operational risk.

> [!TIP]
> Use `Shift+Tab` at any point during an interactive session to switch between **Manual** and **Auto** modes on the fly.

> [!CAUTION]
> Never run `--yolo` mode against production cloud accounts or live production cluster contexts.

### Multi-Layer Guardrails
- **Shell Safety Scanner (`security/shell_safety.py`):** Static analysis classifier that intercepts dangerous shell commands and enforces customizable execution allowlists (`-S recommended`, `-S all`, `-S "cmd1,cmd2"`).
- **Unicode Security Scanner (`security/unicode_security.py`):** Protects against Trojan Source attacks, bidirectional Unicode manipulation (Bidi overrides), and homoglyph spoofing.
- **SSRF & URL Guard (`security/url_validation.py`):** Blocks agent tool requests to cloud metadata endpoints (`169.254.169.254`), localhost, and private RFC-1918 networks.
- **Headless MCP Guard (`HeadlessMCPGuardMiddleware`):** Programmatically classifies external MCP tools into 4 security tiers (`READ_ONLY`, `MUTATING_SAFE`, `MUTATING_DESTRUCTIVE`, `PRIVILEGED`) for unattended execution.

---

## 🤖 Built-in Enterprise DevOps Subagents

OpsCode includes **6 specialized subagents**, each running with dedicated domain skills, isolated branch memory (`BranchMemoryStore`), and scoped tool bindings:

```
                  ┌───────────────────────────────┐
                  │    Root Orchestration Agent   │
                  │   (Global Context & Router)   │
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
                    │   (BranchMemoryStore)     │
                    └───────────────────────────┘
```

| Subagent | Specialization | Encapsulated Skills (34 Total) | Embedded MCP |
|---|---|---|:---:|
| **`aws-opentofu-provisioner`** | OpenTofu / AWS | `opentofu-data-security`, `opentofu-iam-security`, `opentofu-mcp-schema-lookup`, `opentofu-module-layout`, `opentofu-state-management`, `opentofu-testing-validation`, `opentofu-vpc-networking` | ✅ |
| **`aws-terraform-module-writer`** | Terraform / AWS | `aws-data-security-enforcement`, `aws-iam-policy-engine`, `aws-vpc-network-patterns`, `terraform-iteration-patterns`, `terraform-mcp-schema-lookup`, `terraform-module-layout`, `terraform-repair-loop` | ✅ |
| **`ci-jenkins-automater`** | Jenkins Pipelines | `jenkins-job-dsl-jcasc`, `jenkins-pipeline-generation`, `jenkins-pipeline-testing`, `jenkins-shared-libraries` | — |
| **`github-actions-writer`** | GitHub Workflows | `github-actions-architecture`, `github-actions-performance`, `github-actions-security-hardening`, `github-actions-vulnerability-mitigation` | — |
| **`infra-ansible-provisioner`** | Ansible Automation | `ansible-code-authoring`, `ansible-environment-setup`, `ansible-execution-environments`, `ansible-linting-remediation`, `ansible-mcp-schema-lookup`, `ansible-runner-execution`, `ansible-security-operations` | ✅ |
| **`k8s-helm-provisioner`** | Kubernetes & Helm | `helm-chart-authoring`, `helm-deployment-recovery`, `helm-schema-validation`, `helm-security-secrets`, `helm-testing` | — |

> [!IMPORTANT]
> **Context Engineering:** OpsCode implements progressive disclosure. Subagent domain skills are only loaded into context when relevant files or tasks are detected, preserving your model's token budget and reducing hallucinations.

---

## 🏗️ Architecture & Multi-Agent State Machines

OpsCode is engineered on top of the **Deep Agents SDK** and **LangGraph Pregel state machines**, executing turns through an 18-middleware processing pipeline:

```
┌────────────────────────────────────────────────────────────────────────┐
│                         OpsCode 18-Middleware Pipeline                 │
├────────────────────────────────────────────────────────────────────────┤
│ 1. UnifiedSystemMessageMiddleware  - Synthesizes persona & core skills │
│ 2. LocalContextMiddleware          - Injects Git state & DevOps markers│
│ 3. ResumeStateMiddleware           - Restores thread checkpoint state  │
│ 4. ConfigurableModelMiddleware     - Hot-swaps models at runtime       │
│ 5. CostTrackingMiddleware          - Token usage & live USD calculation│
│ 6. GlmTerminalStallRecoveryMW      - Deadlock prevention in non-TUI    │
│ 7. ShellAllowListMiddleware        - Evaluates auto-approved shell cmds│
│ 8. ServerHooksMiddleware           - Dispatches to hooks.json bus      │
│ 9. MCPContextMiddleware            - Manages MCP sessions and tools    │
│ 10. HeadlessMCPGuardMiddleware     - 4-tier security gating in CI/auto │
│ 11. ToolFilterMiddleware           - Frontmatter tool filtering proxy  │
│ 12. PluginSkillsMiddleware         - 7-tier skill discovery & injection│
│ 13. GoalStateNoticeMiddleware      - Acceptance criteria notifications │
│ 14. GoalCriteriaMiddleware         - Acceptance criteria evaluation    │
│ 15. CompactionMiddleware           - Automated context summarization   │
│ 16. ReliableRubricMiddleware       - Autonomous CI/CD grading loop     │
│ 17. CodeInterpreterMiddleware      - QuickJS REPL & PTC execution      │
│ 18. SubagentsMiddleware            - Multi-agent dispatch & monitoring │
└────────────────────────────────────────────────────────────────────────┘
```

### 7-Tier Skill Resolution Hierarchy

OpsCode discovers and loads skills (`SKILL.md`) following a deterministic 7-tier hierarchy:

```
[Tier 7] Claude Experimental Skills (~/.claude/skills/, .claude/skills/)
   ▲
[Tier 6] Project Agents Skills (.agents/skills/)
   ▲
[Tier 5] Project OpsCode Skills (.opscode/skills/)
   ▲
[Tier 4] User Agents Skills (~/.agents/skills/)
   ▲
[Tier 3] User OpsCode Skills (~/.opscode/skills/)
   ▲
[Tier 2] Active Plugin Skills (Non-agent marketplace plugins)
   ▲
[Tier 1] Built-in Skills (src/opscode/built_in_skills/)
```

### Supported Model Providers & Extended Thinking

OpsCode supports **20+ providers** with first-class streaming and extended reasoning tokens:

- **Extended Thinking Models:** Claude 3.7 Sonnet Thinking, OpenAI o1 / o3-mini, Gemini 2.0 Flash Thinking, DeepSeek R1.
- **Direct Providers:** Anthropic, OpenAI, Google GenAI, Vertex AI, Azure OpenAI, Groq, DeepSeek, Together AI, Fireworks AI, Mistral, NVIDIA NIM, Perplexity, Cohere, IBM watsonx, HuggingFace, LiteLLM, xAI, Baseten.
- **Local Offline Inference:** Ollama (`ops -M ollama:llama3.3`).

---

## 🎯 Autonomous CI/CD Rubric Evaluation Loops

In automated pipelines, OpsCode pairs a worker agent with a dedicated grader model to iteratively self-correct code against a strict specification:

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

## 🚫 Not For You If... (Anti-Marketing & Honesty)

To build long-term engineering trust, we are explicit about what OpsCode is **not** designed to do:

- ❌ **It is not a replacement for human code review:** All infrastructure modifications must be audited by qualified platform engineers before production deployment.
- ❌ **It is not an unmonitored deployment bot:** OpsCode produces audited plans and diffs. It does not run un-sandboxed `terraform apply -auto-approve` on live production environments.
- ❌ **It is not for users with zero IaC knowledge:** Safely reviewing and approving agent-generated diffs requires understanding core cloud and networking fundamentals.

---

## 📖 Documentation Index

Comprehensive technical documentation is maintained in [`docs/opscode-docs/`](docs/opscode-docs/):

| Guide | Topic |
|---|---|
| 📄 **[Overview](docs/opscode-docs/overview.md)** | Full platform capabilities, tools inventory, and data paths |
| 🚀 **[Quickstart](docs/opscode-docs/quickstart.md)** | Getting started, interactive TUI, piping, and LangSmith tracing |
| 💻 **[CLI Reference](docs/opscode-docs/cli-reference.md)** | Complete CLI flags, subcommands (`config`, `auth`, `plugin`, etc.), and slash commands |
| ⚙️ **[Configuration](docs/opscode-docs/Configuration.md)** | Environment variables, `.opscode` directories, and precedence order |
| 📝 **[config.toml Reference](docs/opscode-docs/config.toml.md)** | Complete configuration schema for models, UI, tools, and permissions |
| 🔑 **[Provider Credentials](docs/opscode-docs/credentials.md)** | Credential setup, `/auth` manager, and provider resolution order |
| 🛡️ **[Approval Modes & Security](docs/opscode-docs/approval-mode.md)** | Manual/Auto/YOLO modes, shell allowlists, and Unicode/SSRF guardrails |
| 🤖 **[Subagents](docs/opscode-docs/subagents.md)** | 6 built-in subagents, 34 domain skills, and `BranchMemoryStore` |
| 🧠 **[Memory and Skills](docs/opscode-docs/memory-and-skills.md)** | 7-tier resolution hierarchy, 4 root global skills, and `remember` workflow |
| 🔌 **[MCP Tools](docs/opscode-docs/mcp-tools.md)** | Model Context Protocol integration, schemas, and `HeadlessMCPGuard` |
| 📦 **[Plugins & Marketplaces](docs/opscode-docs/plugins.md)** | Plugin protocol, marketplace commands, and agent vs non-agent bifurcation |
| 🪝 **[Hooks](docs/opscode-docs/hooks.md)** | Event hooks via `hooks.json`, wire tool mapping, and audit logging |
| 🤖 **[Model Providers](docs/opscode-docs/model-providers.md)** | 20+ supported providers, extended thinking tokens, and Ollama |
| 🎯 **[Goals & Rubrics](docs/opscode-docs/goal-and-rubrics.md)** | Interactive acceptance goals vs autonomous CI/CD rubric grading loops |
| ☁️ **[Remote Sandboxes](docs/opscode-docs/remote-sandboxes.md)** | Ephemeral cloud sandboxes (AgentCore, Daytona, Modal, Runloop, Vercel) |

---

## 🛠️ CLI Cheat Sheet

```bash
# Basic Usage
opscode [OPTIONS] [PROMPT]
ops [OPTIONS] [PROMPT]

# Common Subcommands
ops auth list | set <provider> | remove <provider>
ops config show | list | get <key> | set <key> <value>
ops plugin list | install <id> | uninstall <id> | marketplace add <url>
ops skills list | info <name> | find <query> | create <name>
ops mcp list | tools | test <server>
ops threads list | delete <id>
ops agents list | reset --agent <name>
ops doctor

# Essential Flags
-n, --non-interactive TEXT       # Run single task headlessly
-r, --resume [ID]                # Resume previous thread
-M, --model MODEL                # Model specifier (provider:model)
-a, --agent NAME                 # Launch with specific subagent
-s, --skill NAME                 # Pre-load specific skill
-y, --auto-approve               # Classifier-backed Auto mode
--yolo                           # YOLO mode (all actions permitted)
-S, --shell-allow-list LIST      # Shell allowlist (recommended, all, CSV)
--goal TEXT                      # Interactive goal with criteria
--rubric TEXT|@PATH              # Autonomous rubric grading loop
--rubric-model MODEL             # Grader model for rubric evaluation
--sandbox [TYPE]                 # Ephemeral cloud sandbox provider
```

---

## 🤝 Contributing & Community

We welcome community contributions! Please review our [Contributing Guidelines](CONTRIBUTING.md) and [Security Policy](SECURITY.md) before submitting pull requests.

```bash
# Clone the repository
git clone https://github.com/talkops-ai/opscode.git
cd opscode

# Create a virtual environment and install dev dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,test-integration]"

# Run the test suite
uv run pytest tests/ -m unit -v
```

---

## 📄 License

OpsCode is open-source software licensed under the [Apache License 2.0](LICENSE).
