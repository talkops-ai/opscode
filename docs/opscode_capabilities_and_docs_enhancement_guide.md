# OpsCode Capabilities Specification & Documentation Enhancement Guide

> **Target Audience:** Engineering, Documentation, and Platform Teams  
> **Status:** Authoritative Blueprint for OpsCode Capabilities & Documentation Update  
> **Date:** August 2026  
> **Repository Root:** `/Users/structbinary/Documents/work/talkops/dcoder`  
> **Target Docs Directory:** `docs/opscode-docs/`

---

## 1. Executive Summary & Migration Context

OpsCode (formerly *DCoder* / *dcode*) has transitioned into an enterprise-ready, CLI-first autonomous AI coding and orchestration agent purpose-built for DevOps, SRE, Platform Engineering, and Infrastructure-as-Code (IaC). 

As part of this transition:
1. **Zero Backward Compatibility:** OpsCode is a pre-release greenfield deployment. All legacy `dcoder` / `dcode` naming, `DCODER_*` environment variables, and `~/.dcoder/` paths have been removed across the codebase and replaced with `opscode`, `ops`, `OPSCODE_*`, and `~/.opscode/`.
2. **Deep Architecture Expansion:** The implementation in `src/opscode/` includes an 18-middleware execution pipeline, 6 built-in enterprise subagents with 34 domain skills, a 7-tier skill resolution hierarchy, an embedded QuickJS code interpreter REPL, SQLite session checkpointing with covering indices, a 3-mode approval HITL engine, remote sandbox execution, and a modular Textual TUI widget architecture.
3. **Documentation Alignment:** The documentation in `docs/opscode-docs/` currently contains outdated naming, obsolete tool listings, and missing architecture modules. This document provides the complete, authoritative capability specification and a file-by-file action plan for updating the entire documentation suite.

---

## 2. Nomenclature, Paths & Environment Reference

| Component | Legacy (DCoder) | OpsCode Current (Authoritative) |
|---|---|---|
| **Package Name** | `dcoder` | `opscode` |
| **CLI Binaries** | `dcoder`, `dcode` | `opscode` (primary), `ops` (short alias) |
| **User Data Root** | `~/.dcoder/` | `~/.opscode/` |
| **Project Data Root** | `.dcoder/` | `.opscode/` |
| **Global Config File** | `~/.dcoder/config.toml` | `~/.opscode/config.toml` |
| **Global Secrets / Env** | `~/.dcoder/.env` | `~/.opscode/.env` |
| **Global MCP Manifest** | `~/.dcoder/.mcp.json` | `~/.opscode/.mcp.json` |
| **Global Hooks Manifest** | `~/.dcoder/hooks.json` | `~/.opscode/hooks.json` |
| **Managed State Root** | `~/.dcoder/.state/` | `~/.opscode/.state/` |
| **SQLite Session DB** | `~/.dcoder/.state/sessions.db` | `~/.opscode/.state/sessions.db` |
| **SQLite Covering Index** | `idx_dcoder_threads_list` | `idx_opscode_threads_list` |
| **Environment Prefix** | `DCODER_` / `DCODER_CODE_` | `OPSCODE_` / `OPSCODE_CODE_` |
| **Approval Mode Namespace**| `("dcoder", "approval_mode")` | `("opscode", "approval_mode")` |
| **Plugin Group Entry Point**| `dcoder.plugins` | `opscode.plugins` |
| **Subagent Skills Directory**| `~/.dcoder/{agent}/skills/` | `~/.opscode/{agent}/skills/` |
| **Subagent Agents Directory**| `~/.dcoder/{agent}/agents/` | `~/.opscode/{agent}/agents/` |
| **Telemetry Agent Name** | `dcoder` | `opscode` |
| **Notification Schema** | `DCoderNotification` | `OpscodeNotification` |

---

## 3. Comprehensive OpsCode Capabilities Inventory

### 3.1 Core Architecture & Agent Framework
- **Deep Agents SDK & LangGraph Pregel Engine:** Built on top of LangChain, LangGraph Pregel state machines, and the Deep Agents SDK. Supports synchronous turn streaming, interrupt-driven human-in-the-loop approvals, and subagent graph bifurcation.
- **Fast SQLite Session Checkpointing (`src/opscode/state/session.py`):**
  - Thread state persisted using SQLite checkpointing.
  - Dedicated covering index `idx_opscode_threads_list` (`(thread_id, checkpoint_ns, checkpoint_id DESC)`) ensures sub-millisecond thread listing and zero-latency session resumption (`opscode -r`).
- **DevOps-Aware Project Root Detection (`src/opscode/project_utils.py`):**
  - Walks parent directories to detect project boundaries using standard markers (`.git`, `pyproject.toml`, `package.json`, `Makefile`) and DevOps markers (`terragrunt.hcl`, `Chart.yaml`, `ansible.cfg`, `.opscode/`).
- **DevOps Environment Preservation:**
  - Automatically isolates and preserves DevOps environment variables across subprocesses: `KUBECONFIG`, `KUBE_CONTEXT`, `AWS_PROFILE`, `AWS_REGION`, `AWS_DEFAULT_REGION`, `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT`, `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`, `ANSIBLE_CONFIG`, `ANSIBLE_INVENTORY`, `HELM_HOME`, `HELM_REPOSITORY_CONFIG`, `ARGOCD_SERVER`, `ARGOCD_AUTH_TOKEN`, `TF_CLI_CONFIG_FILE`, `TERRAGRUNT_CONFIG`.

---

### 3.2 The 18-Middleware Execution Pipeline (`src/opscode/middleware/`)

OpsCode executes every turn through a modular, high-integrity middleware pipeline:

```
┌────────────────────────────────────────────────────────────────────────┐
│                         OpsCode Turn Execution Pipeline                │
├────────────────────────────────────────────────────────────────────────┤
│ 1. UnifiedSystemMessageMiddleware  - Combines persona, DevOps context, │
│                                      memory, skills, model profiles    │
│ 2. LocalContextMiddleware          - Injects directory state & markers │
│ 3. ResumeStateMiddleware           - Restores thread & approval state  │
│ 4. ConfigurableModelMiddleware     - Hot-swaps models without restart  │
│ 5. CostTrackingMiddleware          - Token and cost calculation        │
│ 6. GlmTerminalStallRecoveryMW      - Deadlock prevention for non-TUI   │
│ 7. ShellAllowListMiddleware        - Evaluates auto-approved shell cmds│
│ 8. ServerHooksMiddleware           - Dispatches to hooks.json bus      │
│ 9. MCPContextMiddleware            - MCP server sessions & tools       │
│ 10. HeadlessMCPGuardMiddleware     - 4-tier security gating in CI/auto │
│ 11. ToolFilterMiddleware           - Frontmatter tool filtering proxy  │
│ 12. PluginSkillsMiddleware         - 7-tier skill discovery & injection│
│ 13. GoalStateNoticeMiddleware      - Acceptance criteria notifications │
│ 14. GoalCriteriaMiddleware         - Acceptance criteria evaluation    │
│ 15. CompactionMiddleware           - Automated context summarization   │
│ 16. ReliableRubricMiddleware       - Non-interactive grading loop      │
│ 17. CodeInterpreterMiddleware      - QuickJS REPL & PTC execution      │
│ 18. SubagentsMiddleware            - Multi-agent dispatch & monitoring │
└────────────────────────────────────────────────────────────────────────┘
```

#### Middleware Specifications:
1. **`UnifiedSystemMessageMiddleware`:** Dynamically synthesizes the system prompt with persona, DevOps context, active skills, loaded memories, and supported model modalities (text, vision, thinking, tool calling).
2. **`LocalContextMiddleware`:** Injects real-time workspace context, Git branches, working tree status, and DevOps config files into the prompt.
3. **`ResumeStateMiddleware`:** Recovers conversation state, active approval mode, and UI configuration when resuming threads (`-r`).
4. **`ConfigurableModelMiddleware`:** Enables runtime model hot-swapping (`/model`) without losing memory or execution state.
5. **`CostTrackingMiddleware`:** Calculates prompt/completion tokens and estimated USD costs in real-time across 20+ model providers via `genai-prices`.
6. **`GlmTerminalStallRecoveryMiddleware`:** Detects and recovers from token streaming stalls or unresponsive LLM outputs in non-interactive mode.
7. **`ShellAllowListMiddleware`:** Evaluates shell commands against allowlists (`recommended`, `all`, or user-specified) to bypass interactive approval prompts safely.
8. **`ServerHooksMiddleware`:** Intercepts pre/post tool executions and broadcasts events to global and project `hooks.json` handlers.
9. **`MCPContextMiddleware`:** Manages live MCP client connections, tool registration, and lifecycle restarts.
10. **`HeadlessMCPGuardMiddleware`:** Implements 4-tier tool classification (`READ_ONLY`, `MUTATING_SAFE`, `MUTATING_DESTRUCTIVE`, `PRIVILEGED`) to guard unattended MCP executions.
11. **`ToolFilterMiddleware`:** Restricts subagents to their frontmatter-declared toolsets (`tools: ["execute", "mcp__*"]`).
12. **`PluginSkillsMiddleware`:** Discovers, ranks, and loads skills across the full 7-tier resolution hierarchy.
13. **`GoalStateNoticeMiddleware`:** Injects persistent visual reminders of active goal criteria into the agent's turn loop.
14. **`GoalCriteriaMiddleware`:** Evaluates objective progress and enforces search/tool budgets during goal execution.
15. **`CompactionMiddleware`:** Automatically summarizes older conversation turns when token consumption exceeds context limits, preserving vital decisions.
16. **`ReliableRubricMiddleware`:** Runs an autonomous self-evaluation loop in non-interactive mode (`-n`) using a grader model and rubric grader tools.
17. **`CodeInterpreterMiddleware`:** Embedded QuickJS runtime supporting programmatic tool calling (PTC) and JavaScript REPL execution (`js_eval`).
18. **`SubagentsMiddleware`:** Handles delegation to compiled subagents, background async tasks, and subagent state isolation.

---

### 3.3 Built-in Enterprise DevOps Subagents (`src/opscode/built_in_subagents/`)

OpsCode ships with **6 production-ready DevOps subagents**, each bundling specialized system prompts, references, boilerplate templates, and dedicated skills:

```
src/opscode/built_in_subagents/
├── aws-opentofu-provisioner/
│   ├── agents/opentofu-writer.md
│   └── skills/
│       ├── opentofu-module-boilerplate
│       ├── opentofu-backend-s3-dynamo
│       ├── opentofu-state-encryption
│       ├── opentofu-cross-account-iam
│       ├── opentofu-ci-cd-pipelines
│       ├── opentofu-drift-detection
│       └── opentofu-migration-patterns
├── aws-terraform-module-writer/
│   ├── .mcp.json
│   ├── agents/aws-terraform-writer.md
│   └── skills/
│       ├── terraform-module-boilerplate
│       ├── terraform-backend-s3-dynamo
│       ├── terraform-state-encryption
│       ├── terraform-cross-account-iam
│       ├── terraform-ci-cd-pipelines
│       ├── terraform-drift-detection
│       └── terraform-migration-patterns
├── ci-jenkins-automater/
│   ├── agents/ci-jenkins-automater.md
│   └── skills/
│       ├── jenkins-declarative-pipeline-writer
│       ├── jenkins-shared-library-scaffolder
│       ├── jenkins-docker-kubernetes-agents
│       ├── jenkins-security-vault-integration
│       └── jenkinsfile-linter-debugger
├── github-actions-writer/
│   ├── agents/github-actions-writer.md
│   └── skills/
│       ├── gha-workflow-scaffolder
│       ├── gha-security-hardening
│       ├── gha-composite-action-writer
│       └── gha-matrix-concurrency-optimizer
├── infra-ansible-provisioner/
│   ├── agents/infra-provisioner.md
│   └── skills/
│       ├── ansible-playbook-scaffolder
│       ├── ansible-role-scaffolder
│       ├── ansible-inventory-manager
│       ├── ansible-vault-encryptor
│       ├── ansible-lint-debugger
│       ├── ansible-molecule-tester
│       └── ansible-idempotency-validator
└── k8s-helm-provisioner/
    ├── agents/k8s-helm-provisioner.md
    └── skills/
        ├── helm-chart-scaffolder
        ├── helm-values-schema-validator
        ├── helm-template-debugger
        └── helm-security-hardening
```

#### Subagent Capabilities Summary:
1. **`aws-opentofu-provisioner`:** Generates OpenTofu infrastructure, implements OpenTofu 1.6+ native state encryption with AWS KMS, provisions S3/DynamoDB state backends, configures cross-account IAM roles, and sets up OpenTofu CI/CD workflows.
2. **`aws-terraform-module-writer`:** Complete AWS Terraform module authoring adhering to HashiCorp best practices, multi-account policy architecture, remote state locking, S3/DynamoDB backends, and embedded AWS MCP query tools.
3. **`ci-jenkins-automater`:** Scaffolds Jenkins declarative pipelines (`Jenkinsfile`), creates shared libraries (`vars/`, `src/`), manages Kubernetes and Docker dynamic agent pods, integrates HashiCorp Vault secrets, and runs pipeline validation.
4. **`github-actions-writer`:** Generates hardened GitHub Actions workflows, reusable composite actions, OpenID Connect (OIDC) cloud authentication, concurrency controls, secret masking, and matrix testing strategies.
5. **`infra-ansible-provisioner`:** Scaffolds Ansible playbooks and standard role structures (`tasks/`, `handlers/`, `vars/`, `defaults/`, `meta/`), dynamic inventory management, Ansible Vault encryption, Molecule testing, and idempotency checks.
6. **`k8s-helm-provisioner`:** Builds production Helm charts, values schemas (`values.schema.json`), template helpers (`_helpers.tpl`), dry-run template debuggers, and Pod Security Standard hardening.

#### Subagent Architecture Features:
- **Tool Filtering Proxy:** Declared via `tools: ["pattern1", "pattern2"]` in subagent frontmatter.
- **Skill Whitelisting:** Declared via `skills: ["skill-name"]` in subagent frontmatter.
- **Branch Memory Store (`BranchMemoryStore`):** Subagents execute with an isolated branch memory file to prevent prompt pollution while preserving working context.
- **Subagent MCP Scoping:** Subagents can bundle their own `.mcp.json` configs loaded exclusively into the subagent's execution graph.

---

### 3.4 The 7-Tier Skill Resolution Precedence (`src/opscode/skills/registry.py`)

OpsCode resolves skills using a strict 7-tier precedence hierarchy (Tier 1 is base, Tier 7 is highest override):

| Tier | Name | Location | Scope |
|---|---|---|---|
| **Tier 1** | Built-in Skills | `src/opscode/built_in_skills/` | Shipped with OpsCode |
| **Tier 2** | Plugin Skills | Active Plugin `skills/` directories | Installed/Project Plugins (Namespaced) |
| **Tier 3** | User OpsCode Skills | `~/.opscode/skills/` or `~/.opscode/{agent}/skills/` | User Global |
| **Tier 4** | User Agents Skills | `~/.agents/skills/` | Universal User Tool-Agnostic |
| **Tier 5** | Project OpsCode Skills | `.opscode/skills/` | Project Specific (Git tracked) |
| **Tier 6** | Project Agents Skills | `.agents/skills/` | Universal Project Tool-Agnostic |
| **Tier 7** | Claude Experimental Skills | `~/.claude/skills/`, `.claude/skills/` | Ecosystem Compatibility |

#### Built-in Global Skills:
- **`cloud-core`:** Cloud infrastructure fundamentals, IAM principles, networking topologies, resource tagging, cost governance.
- **`docker`:** Multi-stage builds, rootless container security, minimal base images (Distroless/Alpine), caching optimization.
- **`kubernetes`:** Pod security standards, resource quotas, affinity/anti-affinity, probes, RBAC, NetworkPolicies.
- **`remember`:** Active conversation analysis to extract decisions and save them directly into `AGENTS.md` memory or generate new reusable skills.

---

### 3.5 Native Tools & Execution Engine (`src/opscode/tools/`)

OpsCode provides native core tools combined with shell capabilities and dynamic MCP integration:

| Tool | Implementation | Description |
|---|---|---|
| `execute` | Terminal / Subprocess | Shell command execution with stdout/stderr capture and timeout controls |
| `read_file` | Filesystem | Chunked file reading with offset and limit |
| `write_file` | Filesystem | Full file creation and overwrite |
| `edit_file` | Filesystem | Precision string and regex replacement |
| `delete` | Filesystem | Destructive file removal (strictly gated) |
| `glob` | Filesystem | Pattern-based file search |
| `grep` | Filesystem / Ripgrep | High-speed content search with regex and glob filtering |
| `ls` | Filesystem | Directory structure listing |
| `web_search` | Tavily API | Real-time web search for docs, CVEs, error codes |
| `fetch_url` | HTTP Client | Markdown extraction from documentation URLs with SSRF protection |
| `get_current_thread_id` | State | Thread identifier inspection |
| `get_goal` / `update_goal` | Goal System | Acceptance criteria inspection and state transitions |
| `get_rubric` | Rubric System | Rubric specification retrieval |
| `js_eval` | QuickJS REPL | In-memory JavaScript code evaluation (PTC interpreter) |

---

### 3.6 Approval Modes & Security Subsystem (`src/opscode/security/`)

OpsCode provides three operational approval modes:

```
┌──────────────┐     Shift+Tab     ┌──────────────┐     Shift+Tab     ┌──────────────┐
│    Manual    │ ───────────────>  │     Auto     │ ───────────────>  │     YOLO     │
│  (Default)   │ <───────────────  │ (Classifier) │ <───────────────  │ (All Actions)│
└──────────────┘     Shift+Tab     └──────────────┘     Shift+Tab     └──────────────┘
```

1. **Manual Mode (Default):** Every mutating shell command, file write, or external tool execution triggers an interactive approval modal.
2. **Auto Mode (`-y`, `--auto-approve`):** Powered by the `AutoModeHITLMiddleware`. Employs command classification to auto-approve safe, read-only operations while interrupting for dangerous actions.
3. **YOLO Mode (`--yolo`):** Executes all gated actions without interruption (requires initial risk acknowledgement).
4. **Shell Safety & Command Allowlisting (`src/opscode/security/shell_safety.py`):**
   - Classifies commands into Safe vs. Unsafe.
   - Supports `--shell-allow-list` (`recommended`, `all`, or CSV list).
5. **Unicode Security Scanner (`src/opscode/security/unicode_security.py`):**
   - Intercepts homoglyph substitutions, invisible zero-width spaces, and bidirectional text exploits (Trojan Source attacks).
6. **URL Validation & SSRF Guard (`src/opscode/security/url_validation.py`):**
   - Enforces permitted protocols (`http`, `https`), blocks loopback addresses (`127.0.0.1`, `localhost`), and blocks internal private IP ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, AWS metadata `169.254.169.254`).
7. **Role-Based Access Control (`src/opscode/security/rbac.py`):**
   - Granular tool execution permission enforcement across subagents and MCP servers.

---

### 3.7 Interactive TUI & Modular Widgets (`src/opscode/ui/`)

OpsCode features a rich Textual terminal interface:

- **Core Application (`src/opscode/ui/app.py`):** Responsive TUI with asynchronous stream handling, multi-line editor, history scrolling, and keyboard navigation.
- **Dedicated Widgets Package (`src/opscode/ui/widgets/`):**
  - `chat_input.py`: Multi-line prompt input, past-command history, slash-command autocompletion, paste collapsing.
  - `messages.py`: Styled message renderers with diff highlighting, syntax coloring, and markdown tables.
  - `status_bar.py`: Real-time display for model, reasoning effort, approval mode, active git branch, token count, USD cost.
  - `thinking_stream.py`: Collapsible real-time thinking block for reasoning models (Claude 3.7 Thinking, o1/o3-mini, Gemini 2.0 Flash Thinking).
  - `subagent_panel.py`: Live monitor for active child subagents, task execution status, and progress trees.
  - `goal_review_widget.py`: Interactive acceptance criteria checklist with live status indicators (`[pending]`, `[passed]`, `[failed]`).
  - `approval_widget.py`: Tool approval modal (`[Approve]`, `[Reject]`, `[Edit Command]`, `[Always Allow]`).
  - `thread_selector.py`: Thread resumption modal with fuzzy search and preview.
  - `tool_grouping_history.py`: Collapsible accordion for consecutive tool executions.
  - `js_eval_display.py`: Visualizer for QuickJS code execution blocks.
  - `devops_widgets.py`: Specialized renderers for Terraform plans, Helm diffs, Kubernetes YAMLs, Ansible runs.
  - `auto_mode_notice.py`: Non-intrusive toast notifications and warning banners.

---

### 3.8 Command Surface Reference

#### CLI Subcommands & Flags (`src/opscode/cli/main.py`)
```bash
opscode [OPTIONS] [PROMPT]
ops [OPTIONS] [PROMPT]

# Subcommands
opscode config show | list | get <key> | path
opscode auth list | set <provider> | remove <provider>
opscode plugin list | install <id> | uninstall <id> | enable <id> | disable <id> | marketplace add <url>

# Core Flags
-n, --non-interactive TEXT      # Run single task and exit
-m, --message TEXT              # Auto-submit prompt on interactive launch
-s, --skill NAME                # Start with pre-loaded skill
-a, --agent NAME                # Start with specific subagent
-r, --resume [THREAD_ID]        # Resume latest or specific thread
-M, --model MODEL               # Model specifier (provider:model-name)
--default-model [MODEL]         # Get or set persistent default model
-y, --auto-approve              # Enable classifier-backed Auto mode
--yolo                          # Enable YOLO mode
-S, --shell-allow-list LIST     # Shell command allowlist (recommended, all, or CSV)
--goal TEXT                     # Set interactive goal with acceptance criteria
--rubric TEXT|@PATH             # Non-interactive self-evaluation rubric
--rubric-model MODEL            # Dedicated grader model for rubric evaluations
--rubric-max-iterations N       # Maximum grading iteration loops
--sandbox [TYPE]                # Remote sandbox provider (agentcore, daytona, modal, runloop, vercel)
--interpreter / --no-interpreter# Toggle QuickJS code interpreter
--acp                           # Launch as Agent Client Protocol server over stdio
```

#### Slash Commands (Interactive TUI)
| Core Commands | Aliases | Description |
|---|---|---|
| `/auth` | `/login` | Open interactive credential manager |
| `/logout` | — | Remove stored credentials |
| `/model` | — | Open model selector modal |
| `/effort` | — | Set reasoning effort (`low`, `medium`, `high`) |
| `/fast` | — | Switch to fast/cost-effective model |
| `/config` | — | Inspect or modify runtime configuration |
| `/permissions` | `/perms` | Inspect and toggle tool permissions |
| `/skills` | — | Browse and inspect active skills |
| `/skill <name>` | — | Explicitly invoke a skill |
| `/skill-create`| — | Distill conversation into a new reusable skill |
| `/mcp` | — | Inspect MCP servers and available tools |
| `/plugins` | — | Manage plugins and marketplace sources |
| `/cost` | — | View session token consumption and USD cost |
| `/context` | — | View context window utilization gauge |
| `/compact` | — | Trigger manual conversation compaction |
| `/clear`, `/clear!`| — | Clear conversation history |
| `/resume` | — | Open thread selector modal |
| `/doctor` | — | Run system diagnostics (auth, tools, dependencies) |
| `/bug` | — | Open GitHub bug report template |
| `/help` | `/h` | List all slash commands |
| `/exit` | `/quit` | Exit OpsCode session |

| Power Commands | Description |
|---|---|
| `/agents` | Open subagent selector modal to hot-swap active agent |
| `/goal <text>` | Define high-level objective and generate acceptance criteria |
| `/rubric <text\|@file>`| Attach evaluation rubric to current session |
| `/tasks` | Open task management board |
| `/loop` | Enter autonomous execution loop |
| `/review` | Request agent self-review of recent workspace modifications |
| `/memory` | View, save, or delete persistent memory entries |
| `/btw <note>` | Send out-of-band note without triggering LLM turn execution |
| `/copy` | Copy last assistant response to system clipboard |
| `/trace` | View or toggle LangSmith tracing status |
| `/version` | Display OpsCode version and environment metadata |
| `/reload` | Hot-reload configuration and skill definitions |
| `/restart` | Restart current agent session |
| `/update` | Check for newer OpsCode package releases |
| `/auto-update` | Toggle automatic background updates |
| `/install` | Install missing package dependencies |
| `/notifications`| Toggle desktop notification toasts |
| `/scrollbar` | Toggle chat window vertical scrollbars |
| `/timestamps` | Toggle timestamp display on messages |

---

## 4. File-by-File Documentation Audit & Gap Analysis

Below is the exhaustive audit of all 15 markdown documents located in `docs/opscode-docs/` detailing all legacy naming, missing capabilities, and required modifications.

### 4.1 `docs/opscode-docs/overview.md`
- **Current Issues:**
  - Header and text refer to "DCoder".
  - Install snippet uses `pip install dcoder` and `dcoder`.
  - "DevOps-Native Tools" lists non-existent standalone tools (`kubectl_get`, `terraform_validate`, `helm_lint`, `argocd_diff`).
  - "Built-in Skills" lists 12 flat legacy skills instead of the 4 root skills + 34 subagent skills.
  - "Built-in Subagents" lists 3 subagents instead of all 6 enterprise subagents (`aws-opentofu-provisioner`, `aws-terraform-module-writer`, `ci-jenkins-automater`, `github-actions-writer`, `infra-ansible-provisioner`, `k8s-helm-provisioner`).
  - Data locations table uses `~/.dcoder/` and `.dcoder/`.
- **Required Updates:**
  - Rebrand title and all text to **OpsCode**.
  - Update install command to `pip install opscode` and entry point `opscode` / `ops`.
  - Replace hypothetical DevOps tools table with the actual Architecture: Native core tools (`execute`, filesystem, `web_search`, `fetch_url`, QuickJS REPL) + Subagents + MCP tools.
  - Update Built-in Subagents section to list all 6 subagents with their domains.
  - Update Built-in Skills section to reflect `cloud-core`, `docker`, `kubernetes`, `remember`, and note the 7-tier skill hierarchy.
  - Update Data locations table to `~/.opscode/` and `.opscode/`.

---

### 4.2 `docs/opscode-docs/quickstart.md`
- **Current Issues:**
  - Mentions `pip install dcoder` and CLI command `dcoder`.
  - Thread resumption uses `dcoder -r`.
  - Data directories point to `~/.dcoder/`.
  - Missing alias `ops`.
  - LangSmith default project name listed as `dcoder` instead of `opscode`.
- **Required Updates:**
  - Update all commands to `opscode` and note the `ops` alias.
  - Update package installation to `pip install opscode` / `uv pip install opscode`.
  - Update paths to `~/.opscode/` and `.opscode/`.
  - Update LangSmith default project to `opscode`.
  - Add quick tips on `Shift+Tab` approval mode switching and `/agents` hot-swapping.

---

### 4.3 `docs/opscode-docs/cli-reference.md`
- **Current Issues:**
  - Usage syntax shows `dcoder [OPTIONS] [PROMPT]`.
  - Subcommands show `dcoder config`, `dcoder auth`, `dcoder plugin`.
  - Default agent listed as `dcoder` instead of `opscode`.
  - Trust flags reference `.dcoder/hooks.json`.
- **Required Updates:**
  - Change usage to `opscode [OPTIONS] [PROMPT]` and `ops [OPTIONS] [PROMPT]`.
  - Update all subcommands to `opscode config ...`, `opscode auth ...`, `opscode plugin ...`.
  - Update default agent parameter to `opscode`.
  - Update hook trust flag description to `.opscode/hooks.json`.
  - Document all current flags (`--goal`, `--rubric`, `--rubric-model`, `--rubric-max-iterations`, `--sandbox`, `--interpreter`, `--acp`, `-S`).

---

### 4.4 `docs/opscode-docs/Configuration.md`
- **Current Issues:**
  - References `~/.dcoder/` throughout.
  - Setting resolution order lists `DCODER_CODE_*` and `DCODER_*`.
  - Debug log default listed as `/tmp/dcoder_debug.log`.
  - Managed state paths list `~/.dcoder/.state/`.
- **Required Updates:**
  - Replace all paths with `~/.opscode/` and `.opscode/`.
  - Update environment variable precedence to `OPSCODE_CODE_*` and `OPSCODE_*`.
  - Update debug log path to `/tmp/opscode_debug.log`.
  - Update managed state files table to reflect `~/.opscode/.state/` (`sessions.db`, `credentials.env`, `mcp_trust.json`, `skill_trust.json`, `plugin_marketplaces.json`).

---

### 4.5 `docs/opscode-docs/config.toml.md`
- **Current Issues:**
  - Path listed as `~/.dcoder/config.toml`.
  - Env vars list `DCODER_THEME`, `DCODER_VERBOSE`.
  - CLI flag examples use `dcoder`.
- **Required Updates:**
  - Update path to `~/.opscode/config.toml`.
  - Update environment variables to `OPSCODE_THEME`, `OPSCODE_VERBOSE`.
  - Update CLI examples to `opscode`.
  - Ensure all tables (`[model]`, `[providers]`, `[ui]`, `[tools]`, `[interpreter]`, `[permissions]`, `[startup]`, `[warnings]`) match current settings schemas in `src/opscode/config/settings.py`.

---

### 4.6 `docs/opscode-docs/credentials.md`
- **Current Issues:**
  - References `~/.dcoder/.env`.
  - Resolution order lists `DCODER_{KEY}`.
  - Subcommands list `dcoder auth`.
  - LangSmith default project listed as `dcoder`.
- **Required Updates:**
  - Update path to `~/.opscode/.env`.
  - Update resolution order to `OPSCODE_{KEY}` -> Canonical Env -> `~/.opscode/.env` -> `/auth` stored.
  - Update CLI examples to `opscode auth ...`.
  - Update LangSmith default project to `opscode`.

---

### 4.7 `docs/opscode-docs/approval-mode.md`
- **Current Issues:**
  - Mentions `dcoder -y` and `dcoder --yolo`.
  - Code references point to legacy structure.
- **Required Updates:**
  - Update CLI commands to `opscode -y`, `opscode --yolo`.
  - Document the classifier-backed Auto mode powered by `AutoModeHITLMiddleware`.
  - Document `Shift+Tab` cycling behavior (Manual -> Auto -> YOLO).
  - Document shell safety scanner and command allowlists (`-S recommended`, `-S all`, `-S "cmd1,cmd2"`).
  - Document permission toggles (`shell_read`, `shell_write`, `file_read`, `file_write`, `infra_plan`, `infra_apply`).

---

### 4.8 `docs/opscode-docs/subagents.md`
- **Current Issues:**
  - Lists only 3 subagents (`aws-terraform-module-writer`, `helm-validator`, `k8s-auditor`).
  - Storage paths use `.dcoder/agents/` and `~/.dcoder/{agent}/agents/`.
  - CLI flag uses `dcoder -a`.
  - Missing details on tool filtering proxies, branch memory, and embedded MCP servers.
- **Required Updates:**
  - Update paths to `.opscode/agents/` and `~/.opscode/{agent}/agents/`.
  - Document all 6 built-in subagents (`aws-opentofu-provisioner`, `aws-terraform-module-writer`, `ci-jenkins-automater`, `github-actions-writer`, `infra-ansible-provisioner`, `k8s-helm-provisioner`) and their skill directories.
  - Add frontmatter specification for `tools:` (tool filtering proxy) and `skills:` (whitelisting).
  - Explain `BranchMemoryStore` and how subagent working context is isolated from main agent memory.
  - Explain subagent-scoped `.mcp.json` definitions.

---

### 4.9 `docs/opscode-docs/memory-and-skills.md`
- **Current Issues:**
  - Storage paths use `.dcoder/memory/`, `~/.dcoder/memory/`, `.dcoder/skills/`, `~/.dcoder/{agent}/skills/`.
  - Skill priority lists only 3 tiers instead of the 7-tier hierarchy.
  - Built-in skills list 12 flat legacy skills instead of the 4 root skills + 34 subagent skills.
  - Trust file points to `~/.dcoder/.state/skill_trust.json`.
- **Required Updates:**
  - Update all paths to `.opscode/` and `~/.opscode/`.
  - Document the full **7-Tier Skill Resolution Hierarchy** (Built-in -> Plugin -> User OpsCode -> User Agents -> Project OpsCode -> Project Agents -> Claude Experimental).
  - Document the 4 built-in global skills (`cloud-core`, `docker`, `kubernetes`, `remember`) and reference the 34 subagent skills.
  - Detail the `remember` skill workflow (extracting learnings -> saving to `AGENTS.md` / generating new skills).

---

### 4.10 `docs/opscode-docs/mcp-tools.md`
- **Current Issues:**
  - Paths use `~/.dcoder/.mcp.json` and `.dcoder/.mcp.json`.
  - CLI flags use `dcoder --mcp-config`, `dcoder --no-mcp`, `dcoder --trust-project-mcp`.
  - Trust decisions point to `~/.dcoder/.state/mcp_trust.json`.
- **Required Updates:**
  - Update paths to `~/.opscode/.mcp.json` and `.opscode/.mcp.json`.
  - Update CLI command examples to `opscode`.
  - Document the 4-tier `HeadlessMCPGuardMiddleware` for unattended/CI execution.
  - Document MCP RBAC scope mapping support.

---

### 4.11 `docs/opscode-docs/plugins.md`
- **Current Issues:**
  - Protocol class named `DCoderPlugin`.
  - Paths use `.dcoder/plugins/`, `~/.dcoder/plugins/`, `.dcoder/settings.json`.
  - Marketplace state points to `~/.dcoder/.state/plugin_marketplaces.json`.
  - CLI subcommands use `dcoder plugin ...`.
  - Python entry point group listed as `dcoder.plugins`.
- **Required Updates:**
  - Update plugin protocol name to `OpsCodePlugin`.
  - Update paths to `.opscode/plugins/`, `~/.opscode/plugins/`, `.opscode/settings.json`.
  - Update entry point group to `opscode.plugins`.
  - Update CLI commands to `opscode plugin ...`.
  - Document automatic discovery of project-local marketplace plugins.

---

### 4.12 `docs/opscode-docs/hooks.md`
- **Current Issues:**
  - Paths use `~/.dcoder/hooks.json` and `.dcoder/hooks.json`.
  - Audit log examples write to `~/.dcoder/audit.log` or `/tmp/dcoder-audit.log`.
  - Trust flag uses `dcoder --trust-project-hooks`.
- **Required Updates:**
  - Update paths to `~/.opscode/hooks.json` and `.opscode/hooks.json`.
  - Update log examples to `~/.opscode/audit.log` and `/tmp/opscode-audit.log`.
  - Update trust flag to `opscode --trust-project-hooks`.
  - Document `ServerHooksMiddleware` lifecycle integration with wire tool mapping (`execute` -> `Bash`, `write_file` -> `Write`, `read_file` -> `Read`, `edit_file` -> `Edit`, `grep` -> `Grep`, `glob` -> `Glob`, `ls` -> `LS`).

---

### 4.13 `docs/opscode-docs/model-providers.md`
- **Current Issues:**
  - References `dcoder -M`, `dcoder --default-model`.
  - State file listed as `~/.dcoder/.state/recent_models.json`.
- **Required Updates:**
  - Update CLI examples to `opscode -M ...` and `opscode --default-model ...`.
  - Update state file path to `~/.opscode/.state/recent_models.json`.
  - Verify all 20 provider configurations (Anthropic, OpenAI, Google GenAI, Vertex AI, Azure OpenAI, Groq, DeepSeek, Together, Fireworks, OpenRouter, Mistral, NVIDIA, Perplexity, Cohere, IBM watsonx, HuggingFace, LiteLLM, xAI, Baseten, Ollama).
  - Document extended thinking support for reasoning models.

---

### 4.14 `docs/opscode-docs/goal-and-rubrics.md`
- **Current Issues:**
  - CLI examples use `dcoder --goal`, `dcoder -n ... --rubric`.
- **Required Updates:**
  - Update CLI examples to `opscode --goal ...` and `opscode -n ... --rubric ...`.
  - Document `GoalCriteriaMiddleware` and `GoalStateNoticeMiddleware` in interactive mode.
  - Document `ReliableRubricMiddleware` and rubric grader tools in non-interactive mode.

---

### 4.15 `docs/opscode-docs/remote-sandboxes.md`
- **Current Issues:**
  - CLI examples use `dcoder --sandbox`.
  - Ignore list mentions `.dcoder`.
- **Required Updates:**
  - Update CLI examples to `opscode --sandbox ...`.
  - Update ignore list to `.opscode`.
  - Document supported remote sandbox providers (AgentCore, Daytona, Modal, Runloop, Vercel) and workspace syncing mechanics.

---

## 5. Documentation Update Execution Plan

To execute the documentation update across `docs/opscode-docs/`, the team should follow this systematic 4-step workflow:

### Step 1: Global Terminology & Branding Refactoring
Perform an exact global replacement across `docs/opscode-docs/*.md`:
- `DCoder` → `OpsCode`
- `dcoder` → `opscode`
- `dcode` → `ops` (or `opscode`)
- `~/.dcoder` → `~/.opscode`
- `.dcoder` → `.opscode`
- `DCODER_` → `OPSCODE_`
- `dcoder.plugins` → `opscode.plugins`

### Step 2: Architecture & Capabilities Sync
- Update `overview.md` with the 6 enterprise subagents, 4 root skills + 34 subagent skills, and real native tool architecture.
- Update `subagents.md` with complete details on `aws-opentofu-provisioner`, `aws-terraform-module-writer`, `ci-jenkins-automater`, `github-actions-writer`, `infra-ansible-provisioner`, `k8s-helm-provisioner`, tool filtering proxies, and branch memory.
- Update `memory-and-skills.md` with the 7-tier precedence table and `remember` workflow.
- Update `cli-reference.md` and `quickstart.md` with both `opscode` and `ops` command aliases, and all current flags.

### Step 3: Verification & Review
- Verify all code blocks, Markdown links, and CLI examples.
- Ensure that no legacy `dcoder` references remain in `docs/opscode-docs/`.

---

## 6. Summary Checklist for Documentation Team

- [ ] `docs/opscode-docs/overview.md` updated with OpsCode branding, 6 subagents, 4 root skills, and real tools.
- [ ] `docs/opscode-docs/quickstart.md` updated with `opscode` / `ops` commands and `~/.opscode` paths.
- [ ] `docs/opscode-docs/cli-reference.md` updated with all CLI flags, subcommands, and slash commands.
- [ ] `docs/opscode-docs/Configuration.md` updated with `OPSCODE_*` env vars and `~/.opscode/` paths.
- [ ] `docs/opscode-docs/config.toml.md` updated with accurate TOML schemas and `~/.opscode/config.toml`.
- [ ] `docs/opscode-docs/credentials.md` updated with `OPSCODE_{KEY}` resolution and `~/.opscode/.env`.
- [ ] `docs/opscode-docs/approval-mode.md` updated with `Shift+Tab`, Auto mode classifier, and shell safety.
- [ ] `docs/opscode-docs/subagents.md` updated with all 6 subagents, tool filtering, and branch memory.
- [ ] `docs/opscode-docs/memory-and-skills.md` updated with 7-tier precedence and 4 root skills.
- [ ] `docs/opscode-docs/mcp-tools.md` updated with paths, headless MCP guardrails, and RBAC.
- [ ] `docs/opscode-docs/plugins.md` updated with `OpsCodePlugin`, entry points, and project-local discovery.
- [ ] `docs/opscode-docs/hooks.md` updated with paths, wire tool mappings, and lifecycle events.
- [ ] `docs/opscode-docs/model-providers.md` updated with 20 providers, reasoning thinking, and `opscode` commands.
- [ ] `docs/opscode-docs/goal-and-rubrics.md` updated with `opscode` commands and middleware details.
- [ ] `docs/opscode-docs/remote-sandboxes.md` updated with providers, workspace sync, and ignore lists.
