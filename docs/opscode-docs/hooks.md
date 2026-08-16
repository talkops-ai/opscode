# Hooks

> Subscribe external commands and webhooks to agent lifecycle events via `hooks.json`.

Hooks allow you to trigger external scripts, audit logs, and security guardrails in response to OpsCode tool invocations (shell commands, file modifications, MCP calls). Hooks are managed by `ServerHooksMiddleware` and can act both as asynchronous event broadcasters and synchronous pre-execution gates.

---

## Configuration files

Hooks are declared in JSON manifests across two scopes:

| Location | Scope | Trust Policy |
|---|---|---|
| `~/.opscode/hooks.json` | Global (all user sessions) | Always trusted |
| `.opscode/hooks.json` | Project-level | Requires `--trust-project-hooks` or interactive approval |

Both global and project hooks are loaded and executed simultaneously.

---

## Manifest format

```json
{
  "hooks": {
    "Bash": {
      "command": "echo 'Shell: ${input.command}' >> /tmp/opscode-audit.log"
    },
    "Write": {
      "command": "echo 'File created/overwritten: ${input.file_path}' >> /tmp/opscode-audit.log"
    },
    "Edit": {
      "command": "echo 'File edited: ${input.file_path}' >> /tmp/opscode-audit.log"
    }
  }
}
```

Each key corresponds to a **wire tool name**, and the `command` specifies the shell command executed when that tool is invoked.

---

## Tool name mapping

OpsCode maps internal tool identifiers to standardized wire names:

| Internal Name | Wire Name | Input Fields Available |
|---|---|---|
| `execute` | `Bash` | `command`, `timeout` |
| `write_file` | `Write` | `file_path`, `content` |
| `edit_file` | `Edit` | `file_path`, `old_string`, `new_string`, `replace_all` |
| `read_file` | `Read` | `file_path`, `offset`, `limit` |
| `glob` | `Glob` | `pattern`, `path` |
| `grep` | `Grep` | `pattern`, `path`, `glob`, `output_mode`, `head_limit` |
| `ls` | `LS` | `path` |

### MCP tool hooks

MCP tools use the standard `mcp__{server}__{tool}` wire identifier:

```json
{
  "hooks": {
    "mcp__kubernetes__get_pods": {
      "command": "echo 'Kubernetes cluster inspected' >> ~/.opscode/audit.log"
    }
  }
}
```

---

## Use cases & examples

### 1. Immutable audit logging

Record all terminal executions and file changes to a centralized log:

```json
{
  "hooks": {
    "Bash": {
      "command": "echo \"$(date -u +%Y-%m-%dT%H:%M:%SZ) EXEC: ${input.command}\" >> ~/.opscode/audit.log"
    },
    "Write": {
      "command": "echo \"$(date -u +%Y-%m-%dT%H:%M:%SZ) WRITE: ${input.file_path}\" >> ~/.opscode/audit.log"
    },
    "Edit": {
      "command": "echo \"$(date -u +%Y-%m-%dT%H:%M:%SZ) EDIT: ${input.file_path}\" >> ~/.opscode/audit.log"
    }
  }
}
```

### 2. Slack / ChatOps alerts for Terraform plans

Notify the team when infrastructure operations are planned:

```json
{
  "hooks": {
    "Bash": {
      "command": "if echo '${input.command}' | grep -qE '(terraform|tofu) plan'; then curl -s -X POST -H 'Content-type: application/json' --data '{\"text\":\"OpsCode running infrastructure plan\"}' $SLACK_WEBHOOK_URL; fi"
    }
  }
}
```

### 3. Automated linting & formatting on write

Automatically trigger formatters after the agent modifies code:

```json
{
  "hooks": {
    "Write": {
      "command": "if echo '${input.file_path}' | grep -qE '\\.(tf|tofu)$'; then tofu fmt '${input.file_path}' 2>/dev/null || terraform fmt '${input.file_path}' 2>/dev/null || true; fi"
    }
  }
}
```

---

## Trust and security

Project-level hooks (`.opscode/hooks.json`) can execute arbitrary shell commands and require explicit trust authorization:

```bash
# Trust project hooks for the current session
opscode --trust-project-hooks
```

Global hooks (`~/.opscode/hooks.json`) are always trusted as they reside in the user's home directory.
