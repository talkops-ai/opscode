# Configuration

> Configure OpsCode with config.toml, environment variables, hooks, and CLI flags.

OpsCode stores configuration under `~/.opscode/` and in project-level dotfiles (`.opscode/`). For the full directory tree, session storage, and skill paths, see [Data locations](#data-locations).

The main configuration files are:

| File | Description |
|---|---|
| **[config.toml](./config.toml.md)** | Model defaults, provider settings, UI themes, tool allowlists, and permissions |
| **[Environment variables](#environment-variables)** | API keys and secrets in `~/.opscode/.env` or shell exports |
| **[hooks.json](./hooks.md)** | Lifecycle event subscriptions for audit logging and tool guards |
| **[.mcp.json](./mcp-tools.md)** | Global and project MCP server definitions |

## How settings resolve

OpsCode merges settings from several sources in a strictly defined precedence order.

**General options** (interpreter limits, update settings, themes, and `config.toml` keys) resolve in this order:

1. `OPSCODE_CODE_`-prefixed environment variable
2. Canonical environment variable (when applicable)
3. `~/.opscode/config.toml`
4. Built-in default

**Provider API keys** use a separate resolution order. See [Key resolution order](./credentials.md#key-resolution-order).

**Dotenv files** load at startup: the nearest project `.env` (walking up from the launch directory), then `~/.opscode/.env`. Shell exports always take priority over `.env` values. See [Loading order and precedence](#loading-order-and-precedence).

## Inspect configuration

The `opscode config` command group reports what configuration is in effect and where each value originates, without starting an interactive session.

| Command | Description |
|---|---|
| `opscode config show` | Resolve every option and print the effective value and source |
| `opscode config list` (alias `ls`) | List every available option with its type, default, and valid scopes |
| `opscode config get <key>` | Show the effective value and source for a single option |
| `opscode config set <key> <value>` | Set a configuration value in `~/.opscode/config.toml` |
| `opscode config path` | Show config file locations and whether each exists |

Or use `/config` inside an interactive session to view and modify settings.

## Environment variables

### Loading order and precedence

OpsCode loads `.env` files at startup in this order:

1. **Project `.env`** — walks up from the current directory to find the nearest `.env` file
2. **Global `~/.opscode/.env`** — user-level keys (provider credentials, Tavily, LangSmith)

Shell exports always override `.env` values. The `OPSCODE_` prefix takes priority over canonical variable names:

```
OPSCODE_OPENAI_API_KEY  >  OPENAI_API_KEY  >  ~/.opscode/.env  >  project .env
```

### Security

The following environment variables are **blocked** from being set via `.env` files to prevent environment hijacking:

`PATH`, `HOME`, `USER`, `LOGNAME`, `SHELL`, `TERM`, `DISPLAY`, `PYTHONPATH`, `PYTHONSTARTUP`, `PYTHONHOME`, `NODE_PATH`, `NODE_OPTIONS`, `LD_PRELOAD`, `LD_LIBRARY_PATH`, `DYLD_LIBRARY_PATH`, `DYLD_INSERT_LIBRARIES`, `HISTFILE`, `HISTSIZE`, `SSH_AUTH_SOCK`, `GPG_AGENT_INFO`, `TMPDIR`, `TEMP`, `TMP`.

### OPSCODE_CODE_* variables

OpsCode reads the following runtime environment variables:

| Variable | Description |
|---|---|
| `OPSCODE_CODE_DEBUG` | Enable verbose debug logging |
| `OPSCODE_CODE_DEBUG_FILE` | Path for the debug log file (default: `/tmp/opscode_debug.log`) |
| `OPSCODE_CODE_LOG_LEVEL` | Override runtime logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `OPSCODE_CODE_AUTO_UPDATE` | Toggle automatic package updates (default: `enabled`) |
| `OPSCODE_CODE_COLLAPSE_PASTES` | Collapse large chat-input pastes into placeholders (default: `enabled`) |

### DevOps environment preservation

OpsCode automatically isolates and preserves DevOps-specific environment variables across tool and subprocess executions:

| Category | Variables |
|---|---|
| **Kubernetes** | `KUBECONFIG`, `KUBE_CONTEXT` |
| **AWS** | `AWS_PROFILE`, `AWS_REGION`, `AWS_DEFAULT_REGION`, `AWS_SHARED_CREDENTIALS_FILE` |
| **GCP** | `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT`, `CLOUDSDK_CORE_PROJECT` |
| **Azure** | `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID` |
| **Ansible** | `ANSIBLE_CONFIG`, `ANSIBLE_INVENTORY` |
| **Helm** | `HELM_HOME`, `HELM_REPOSITORY_CONFIG` |
| **ArgoCD** | `ARGOCD_SERVER`, `ARGOCD_AUTH_TOKEN` |
| **Terraform / OpenTofu** | `TF_CLI_CONFIG_FILE`, `TERRAGRUNT_CONFIG` |

This ensures that when the agent runs `kubectl`, `terraform`, `tofu`, `helm`, or other DevOps CLIs, local credentials and clusters remain immediately accessible.

## Project detection

OpsCode auto-detects the project root by walking up from the current working directory looking for project markers:

| Marker | Type |
|---|---|
| `.opscode/` | OpsCode project configuration root |
| `.git/` | Git repository |
| `terragrunt.hcl` | Terragrunt project |
| `Chart.yaml` | Helm chart root |
| `ansible.cfg` | Ansible project |
| `pyproject.toml` | Python project |
| `package.json` | Node.js project |
| `Makefile` | Build system |

When a project root is detected, project-level configuration (`.opscode/`, `.env`, skills, subagents, memory) is discovered and merged with user-level settings.

## Data locations

### User-level (`~/.opscode/`)

| Path | Purpose |
|---|---|
| `~/.opscode/config.toml` | Main configuration file |
| `~/.opscode/.env` | Global API keys and secrets |
| `~/.opscode/hooks.json` | Lifecycle hooks |
| `~/.opscode/.mcp.json` | Global MCP server definitions |
| `~/.opscode/memory/` | User-scoped memory entries |
| `~/.opscode/settings.json` | User-scope settings (enabled plugins, etc.) |
| `~/.opscode/plugins/` | Plugin storage (cache, data, marketplaces) |

### Agent-specific (`~/.opscode/{agent}/`)

| Path | Purpose |
|---|---|
| `~/.opscode/{agent}/skills/` | User-level skills for this agent |
| `~/.opscode/{agent}/agents/` | User-level subagents for this agent |
| `~/.opscode/{agent}/AGENTS.md` | User-level agent instructions and memories |

### Managed state (`~/.opscode/.state/`)

These files are machine-managed. Do not edit them manually.

| Path | Purpose |
|---|---|
| `sessions.db` | Conversation checkpoints and threads |
| `auth.json` | Credential store (gateway/OpenRouter auth) |
| `history.jsonl` | Interactive command input history |
| `recent_models.json` | Recent `/model` selections (up to 10 entries) |
| `mcp_trust.json` | MCP project trust decisions |
| `skill_trust.json` | Skill trust decisions |
| `onboarding_complete` | First-run onboarding marker |
| `installed_plugins.json` | Installed plugin registry |
| `plugin_state.json` | Plugin runtime state |
| `plugin_marketplaces.json` | Marketplace sources registry |

### Project-level (`.opscode/`)

| Path | Purpose |
|---|---|
| `.opscode/skills/` | Project skills |
| `.opscode/agents/` | Project subagents |
| `.opscode/plugins/` | Project plugins |
| `.opscode/memory/` | Project-scoped memory |
| `.opscode/AGENTS.md` | Project-level agent instructions |
| `.opscode/settings.json` | Project-scope settings (committed to git) |
| `.opscode/settings.local.json` | Local-scope settings (gitignored personal overrides) |
| `.opscode/hooks.json` | Project-level hooks |
| `.opscode/.mcp.json` | Project-level MCP servers |

### Universal shared data (`~/.agents/`, `.agents/`)

| Path | Purpose |
|---|---|
| `~/.agents/skills/` | User-level tool-agnostic skills (shared across agents) |
| `.agents/skills/` | Project-level tool-agnostic skills (shared across agents) |

## Settings precedence summary

| Setting type | Resolution order (first wins) |
|---|---|
| **General options** | `OPSCODE_CODE_*` env → canonical env → `config.toml` → default |
| **Provider API keys** | `OPSCODE_{KEY}` env → canonical env → `~/.opscode/.env` → `/auth` stored |
| **Provider base URLs** | Stored base URL → env var → default endpoint |
| **Skills** | Built-in → Plugin → User → Project (project overrides all) |
| **Memory** | Project `.opscode/memory/` → User `~/.opscode/memory/` |
| **Subagents** | Project `.opscode/agents/` → User `~/.opscode/{agent}/agents/` → Built-in subagents |
| **MCP servers** | `--mcp-config` → Project `.mcp.json` / `.opscode/.mcp.json` → Global `~/.opscode/.mcp.json` |
| **Hooks** | Project `.opscode/hooks.json` + Global `~/.opscode/hooks.json` (merged) |
