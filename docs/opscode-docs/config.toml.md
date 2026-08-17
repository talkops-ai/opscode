# config.toml Reference

> Complete reference for `~/.opscode/config.toml` — model defaults, display settings, tool permissions, and interpreter configuration.

OpsCode reads its main configuration from `~/.opscode/config.toml`. Use `/config` in an interactive session to view and modify settings, or `opscode config show` from the shell. See [Configuration](./Configuration.md) for how settings resolve across environment variables, `config.toml`, and defaults.

## File location

```
~/.opscode/config.toml
```

Create this file manually or let OpsCode create it automatically when you first change a setting via `/config` or `/model`.

## Models

```toml
[model]
default = "anthropic:claude-opus-4-7"     # Default model (provider:model-name format)
reasoning_effort = "medium"               # low, medium, or high
```

| Key | Type | Default | Description |
|---|---|---|---|
| `default` | string | *(none)* | Default model specifier in `provider:model-name` format |
| `reasoning_effort` | choice | `"medium"` | Reasoning effort level for supported models: `low`, `medium`, `high` |

Set the default model from the CLI:

```bash
opscode --default-model anthropic:claude-opus-4-7
```

Or use `/model` inside an interactive session to switch models on the fly.

## Providers

Configure provider-specific settings and endpoints:

```toml
[providers.openai]
enabled = true
base_url = "https://api.openai.com/v1"
models = ["gpt-4.1", "gpt-4.1-mini", "o3-mini"]

[providers.anthropic]
enabled = true

[providers.ollama]
enabled = true
base_url = "http://localhost:11434"
models = ["llama3.3", "qwen2.5-coder"]
```

| Key | Type | Description |
|---|---|---|
| `enabled` | bool | Whether this provider is active |
| `models` | list[string] | Model identifiers available from this provider |
| `base_url` | string | Override the default API endpoint |
| `base_url_env` | string | Env var name for the base URL override |
| `api_key_env` | string | Env var name for the API key |
| `class_path` | string | Custom LangChain model class path |
| `params` | table | Extra kwargs passed to the model constructor |
| `display_name` | string | Human-readable provider name |

### Endpoints, keys, and gateways

If you use an API gateway, proxy, or private VPC endpoint, configure `base_url`:

```toml
[providers.openai]
base_url = "https://my-gateway.corp.internal/openai/v1"
```

Or use `/auth` inside a session to configure keys and base URLs interactively.

## Display / UI

```toml
[ui]
theme = "dark"                    # Color theme
show_scrollbar = false            # Vertical scrollbar in chat area
show_timestamps = true            # Timestamps on messages
auto_scroll = true                # Auto-scroll to newest messages
notifications = true              # Desktop notifications
show_turn_duration = true         # Agent turn execution duration
verbose = false                   # Verbose debug output
auto_compact = false              # Auto-compact conversation history
```

| Key | Type | Default | Env Var | Description |
|---|---|---|---|---|
| `theme` | string | `"dark"` | `OPSCODE_THEME` | Active color theme |
| `show_scrollbar` | bool | `false` | — | Show vertical scrollbar in chat pane |
| `show_timestamps` | bool | `true` | — | Show timestamps on messages |
| `auto_scroll` | bool | `true` | — | Auto-scroll to newest streaming tokens |
| `notifications` | bool | `true` | — | Enable desktop notifications |
| `show_turn_duration` | bool | `true` | — | Show agent turn duration timer |
| `verbose` | bool | `false` | `OPSCODE_VERBOSE` | Enable verbose debugging mode |
| `auto_compact` | bool | `false` | — | Automatically compact conversation history |

## Tools

```toml
[tools]
shell_allow_list = ["terraform", "tofu", "kubectl", "helm", "ansible-playbook"]
```

| Key | Type | Env Var | Description |
|---|---|---|---|
| `shell_allow_list` | list[string] | `SHELL_ALLOW_LIST` | Shell commands allowed without approval |

### Shell allow list values

The `--shell-allow-list` CLI flag (or `shell_allow_list` config) accepts:

- `"recommended"` — Curated set of safe, read-only commands (`ls`, `cat`, `grep`, `kubectl get`, `terraform validate`, etc.)
- `"all"` — Allow all shell commands without approval prompt
- Comma-separated list — Specific command binaries (e.g., `"terraform,tofu,kubectl,helm"`)

## Interpreter

```toml
[interpreter]
enable_interpreter = false
ptc = "safe"
ptc_acknowledge_unsafe = false
```

| Key | Type | Default | Description |
|---|---|---|---|
| `enable_interpreter` | bool | `false` | Enable QuickJS JavaScript code interpreter (`js_eval`) |
| `ptc` | string | *(none)* | Programmatic Tool Calling (PTC) mode: `"safe"`, `"all"`, or comma-separated tools |
| `ptc_acknowledge_unsafe` | bool | `false` | Explicitly acknowledge unsafe PTC exposure |

## Permissions

Default permission settings for tool operations:

```toml
[permissions]
shell_read = true       # Allow non-mutating shell commands
shell_write = false     # Allow mutating shell commands
file_read = true        # Allow file read operations
file_write = false      # Allow file write / edit operations
infra_plan = false      # Allow infrastructure plan operations (terraform plan, etc.)
infra_apply = false     # Allow infrastructure apply operations (terraform apply, etc.)
```

| Key | Type | Default | Description |
|---|---|---|---|
| `shell_read` | bool | `true` | Non-mutating shell commands (e.g., `kubectl get`, `cat`) |
| `shell_write` | bool | `false` | Mutating shell commands (e.g., `kubectl apply`, `rm`) |
| `file_read` | bool | `true` | File read operations (`read_file`, `grep`, `glob`, `ls`) |
| `file_write` | bool | `false` | File write/edit/delete operations |
| `infra_plan` | bool | `false` | Infrastructure dry-run operations (e.g., `terraform plan`) |
| `infra_apply` | bool | `false` | Infrastructure mutating operations (e.g., `terraform apply`) |

:::tip
Use `/permissions` inside an interactive session to inspect and toggle these permissions dynamically.
:::

## Startup

```toml
[startup]
yolo_switcher = false     # Allow YOLO mode switching via Shift+Tab
```

## Warnings

Suppress recurring informational banners:

```toml
[warnings]
suppress = ["yolo"]       # Suppress "YOLO is active" toast
```

## Complete example

```toml
[model]
default = "anthropic:claude-opus-4-7"
reasoning_effort = "high"

[providers.openai]
enabled = true

[providers.anthropic]
enabled = true

[providers.ollama]
enabled = true
base_url = "http://localhost:11434"
models = ["llama3.3", "qwen2.5-coder"]

[ui]
theme = "dark"
show_timestamps = true
auto_compact = false

[interpreter]
enable_interpreter = false

[tools]
shell_allow_list = ["tofu", "terraform", "kubectl", "helm"]

[permissions]
shell_read = true
shell_write = false
file_read = true
file_write = false
infra_plan = false
infra_apply = false
```
