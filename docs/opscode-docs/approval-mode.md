# Approval modes

> Choose how OpsCode reviews tool calls with Manual, Auto, and YOLO modes

By default, OpsCode asks for your approval before running anything that could change your environment. These are called **gated actions** and include:

* Editing or deleting files
* Running shell commands
* Making web requests
* Delegating work to subagents

Read-only tools like `ls`, `read_file`, `glob`, and `grep` always run without prompting. Approval modes let you choose how much oversight each session requires for everything else.

## Choose a mode

| Mode | What it does | CLI flag |
|---|---|---|
| **Manual** (default) | Asks for approval before every gated action | *(none)* |
| **Auto** | Auto-approves safe, read-only operations; asks for anything mutating or uncertain | `-y`, `--auto-approve` |
| **YOLO** | Runs everything without review | `--yolo` |

Toggle between Manual and Auto at any time during a session with `Shift+Tab`. YOLO cannot be entered through the keyboard toggle.

:::warning
Auto is a safety heuristic for a local coding agent. It is **not** sandbox containment or an operating-system boundary.
:::

## Manual mode

Every mutating tool call pauses the conversation and shows an interactive prompt:

```
[Approve]  [Reject]  [Edit Command]  [Always Allow]
```

You inspect the exact shell command or file diff before it touches your environment. This is the recommended mode for production infrastructure where unintended commands carry severe consequences.

## Auto mode

Auto mode uses a classifier to decide which commands are safe. Read-only operations like `ls`, `grep`, `cat`, `kubectl get`, `terraform validate`, and file reads run automatically. Mutating actions like `terraform apply`, `rm`, `kubectl delete`, and file edits stop and ask.

Launch with Auto mode:

```bash
ops -y
```

Or set it as your default in `~/.opscode/config.toml`:

```toml
[startup]
mode = "auto"
```

## YOLO mode

All gated actions run without interruption. On first activation, OpsCode presents a safety acknowledgement explaining the risks.

```bash
ops --yolo
```

:::warning
YOLO mode is not recommended for production environments. The agent can execute destructive commands without manual verification.
:::

## Switch modes at runtime

Press **Shift+Tab** in an interactive session to cycle through available modes:

```
Manual → Auto → YOLO → Manual
```

The cycle respects your session configuration:
- Auto is skipped if the classifier is not eligible for the current environment.
- YOLO is skipped if you've disabled the YOLO switcher in config (`[startup].yolo_switcher = false`).

## Per-thread persistence

Your approval mode is saved per conversation thread. When you resume a thread with `ops -r`, OpsCode restores the exact approval mode that was active when the thread was last used.

## Shell allowlists

You can pre-approve specific commands so they bypass interactive prompts regardless of approval mode:

```bash
# Allow specific commands
ops -S "terraform,tofu,kubectl,helm"

# Use the curated recommended set
ops -S recommended

# Allow all shell commands
ops -S all
```

Or set them in `~/.opscode/config.toml`:

```toml
[tools]
shell_allow_list = ["tofu", "terraform", "kubectl", "helm", "ansible-playbook"]
```

## Permission controls

Fine-grained permission flags in `~/.opscode/config.toml` complement approval modes:

| Permission | Default | What it controls |
|---|---|---|
| `shell_read` | `true` | Non-mutating shell commands (e.g., `kubectl get`) |
| `shell_write` | `false` | Mutating shell commands (e.g., `kubectl apply`) |
| `file_read` | `true` | File reads (`read_file`, `grep`, `glob`, `ls`) |
| `file_write` | `false` | File writes, edits, and deletes |
| `infra_plan` | `false` | Infrastructure dry-runs (`terraform plan`, `tofu plan`) |
| `infra_apply` | `false` | Infrastructure mutations (`terraform apply`, `tofu apply`) |

Use `/permissions` inside a session to inspect and toggle these interactively.

## Security layers

OpsCode includes several automated security checks that run regardless of approval mode:

### Shell safety classification

Every shell command is analyzed before execution and classified as safe (read-only) or unsafe (mutating/privileged). This classification drives Auto mode decisions and allowlist matching.

### MCP tool security

When running unattended (headless or CI/CD), OpsCode automatically classifies each MCP tool into security tiers — read-only, mutating-safe, mutating-destructive, and privileged — and blocks anything unsafe from running without review.

### Subagent tool restrictions

Subagents are restricted to their declared toolsets. A Terraform subagent can only use the tools listed in its definition — it can't access tools belonging to other subagents or escalate its own permissions.

### Unicode security

All tool arguments and model inputs are scanned for invisible zero-width characters, homoglyph attacks (look-alike Unicode), and bidirectional text overrides (Trojan Source attacks).

### URL validation

All web requests are validated before execution. OpsCode blocks requests to loopback addresses, private networks, and cloud metadata endpoints (`169.254.169.254`, `metadata.google.internal`).
