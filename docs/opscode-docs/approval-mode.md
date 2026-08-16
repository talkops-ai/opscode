# Approval Modes & Security Controls

> Control how OpsCode handles tool-execution approvals: Manual, Auto, and YOLO modes, alongside multi-layer security guardrails.

OpsCode provides three operational approval modes that govern whether the agent can execute tools (shell commands, file writes, infrastructure modifications) without human review.

## Approval Modes

| Mode | Description | CLI Flag |
|---|---|---|
| **Manual** | Every mutating tool call requires explicit interactive approval | *(default)* |
| **Auto** | Classifier-backed approval for safe operations; mutating or risky actions prompt for review | `-y`, `--auto-approve` |
| **YOLO** | All gated actions execute without review (after acknowledging risk) | `--yolo` |

### Manual mode (default)

Every mutating tool execution pauses turn streaming and presents an interactive modal:

```
[Approve]  [Reject]  [Edit Command]  [Always Allow]
```

You inspect the exact shell command or file diff before it touches your environment. This is the recommended mode for production infrastructure where unintended commands (`terraform destroy`, `kubectl delete`) carry severe consequences.

### Auto mode

Powered by `AutoModeHITLMiddleware` and command safety classification (`security/shell_safety.py`), Auto mode auto-approves safe, read-only operations (such as `ls`, `grep`, `cat`, `kubectl get`, `terraform validate`, file reads) while interrupting for mutating actions (`terraform apply`, `rm`, `kubectl delete`, file edits).

Enable at launch:

```bash
opscode -y
# or:
ops -y
```

### YOLO mode

All gated actions execute without interruption. On first activation, OpsCode presents a safety acknowledgement prompt explaining the risks.

```bash
opscode --yolo
```

:::warning
YOLO mode is not recommended for production environments. The agent could execute destructive commands without manual verification.
:::

## Switching modes at runtime

Press **Shift+Tab** in an interactive session to cycle through available modes:

```
Manual ───────────────> Auto ───────────────> YOLO ───────────────> Manual
```

The cycle respects your session configuration:
- Auto is skipped if the classifier is not eligible for the current environment.
- YOLO is skipped if the YOLO switcher is disabled in config (`[startup].yolo_switcher = false`).

## Per-thread persistence

Approval mode is persisted per conversation thread in SQLite (`~/.opscode/.state/sessions.db`). When you resume a thread with `opscode -r`, it automatically restores the exact approval mode that was active when the thread was last saved.

## Shell safety & command allowlisting

OpsCode includes a dedicated shell safety classifier in `security/shell_safety.py` that analyzes commands regardless of approval mode:

- **Safe**: Read-only inspection commands (`ls`, `cat`, `grep`, `git status`, `kubectl get`, `terraform validate`, `tofu plan`)
- **Unsafe**: Mutating or privileged commands (`rm`, `chmod`, `terraform apply`, `kubectl delete`, `tofu apply`)

### Shell allow lists

Pre-approve specific commands so they bypass interactive prompts:

```bash
# Via CLI flag with specific commands
opscode -S "terraform,tofu,kubectl,helm"

# Use the curated recommended set
opscode -S recommended

# Allow all shell commands without approval
opscode -S all
```

Via `~/.opscode/config.toml`:

```toml
[tools]
shell_allow_list = ["tofu", "terraform", "kubectl", "helm", "ansible-playbook"]
```

## Security subsystems & guardrails

OpsCode layers multiple automated security defenses:

### 1. Fine-grained permission toggles

Permission flags in `~/.opscode/config.toml` complement approval modes:

| Permission | Default | Description |
|---|---|---|
| `shell_read` | `true` | Non-mutating shell commands (e.g., `kubectl get`) |
| `shell_write` | `false` | Mutating shell commands (e.g., `kubectl apply`) |
| `file_read` | `true` | File read operations (`read_file`, `grep`, `glob`, `ls`) |
| `file_write` | `false` | File write/edit/delete operations |
| `infra_plan` | `false` | Infrastructure dry-run operations (`terraform plan`, `tofu plan`) |
| `infra_apply` | `false` | Infrastructure mutating operations (`terraform apply`, `tofu apply`) |

Inspect and toggle permissions interactively with `/permissions`.

### 2. Headless MCP guard (`HeadlessMCPGuardMiddleware`)

For unattended, CI/CD, or automated executions, MCP tools are classified into 4 security tiers:
- `READ_ONLY` — Safe to run unattended
- `MUTATING_SAFE` — Gated in headless mode
- `MUTATING_DESTRUCTIVE` — Blocked in unattended mode
- `PRIVILEGED` — Blocked in unattended mode

### 3. Tool filtering proxy (`ToolFilterMiddleware`)

Restricts subagents to their explicitly declared toolsets (`tools: ["execute", "mcp__*"]`) in frontmatter, preventing privilege escalation.

### 4. Unicode security scanner (`security/unicode_security.py`)

Scans all tool arguments and model inputs for:
- Invisible zero-width characters
- Homoglyph attacks (look-alike Unicode characters)
- Bidirectional text overrides (Trojan Source attacks)

### 5. URL validation & SSRF guard (`security/url_validation.py`)

All web requests (`fetch_url`) are validated before execution:
- Enforces permitted protocols (`http`, `https`)
- Blocks loopback addresses (`127.0.0.1`, `localhost`, `::1`)
- Blocks private IPv4/IPv6 networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
- Blocks cloud provider metadata endpoints (`169.254.169.254`, `metadata.google.internal`)
