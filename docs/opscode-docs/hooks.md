# Hooks

> Run custom logic before or after tool execution via `hooks.json`

Hooks let you trigger external scripts, audit logs, or security checks whenever OpsCode runs a tool. You can use hooks to log every shell command, send Slack alerts for infrastructure operations, or auto-format files after the agent modifies them.

## Configuration

Hooks are declared in JSON files at two scopes:

| Location | Scope | Trust |
|---|---|---|
| `~/.opscode/hooks.json` | Global (all sessions) | Always trusted |
| `.opscode/hooks.json` | Project-level | Requires `--trust-project-hooks` or interactive approval |

Both global and project hooks run simultaneously.

## Format

```json
{
  "hooks": {
    "Bash": {
      "command": "echo 'Shell: ${input.command}' >> /tmp/opscode-audit.log"
    },
    "Write": {
      "command": "echo 'File created: ${input.file_path}' >> /tmp/opscode-audit.log"
    },
    "Edit": {
      "command": "echo 'File edited: ${input.file_path}' >> /tmp/opscode-audit.log"
    }
  }
}
```

Each key is a **tool name**, and `command` is the shell command that runs when that tool is invoked. You can use `${input.field}` to reference the tool's input values.

## Tool names

OpsCode maps its internal tools to these names for hooks:

| Tool name | Triggered by | Available input fields |
|---|---|---|
| `Bash` | Shell commands | `command`, `timeout` |
| `Write` | File creation/overwrite | `file_path`, `content` |
| `Edit` | File edits | `file_path`, `old_string`, `new_string`, `replace_all` |
| `Read` | File reads | `file_path`, `offset`, `limit` |
| `Glob` | Pattern searches | `pattern`, `path` |
| `Grep` | Content searches | `pattern`, `path`, `glob`, `output_mode` |
| `LS` | Directory listing | `path` |

MCP tools use their standard `mcp__{server}__{tool}` name:

```json
{
  "hooks": {
    "mcp__kubernetes__get_pods": {
      "command": "echo 'Kubernetes cluster inspected' >> ~/.opscode/audit.log"
    }
  }
}
```

## Examples

### Audit logging

Log all shell commands and file changes:

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

### Slack alerts for infrastructure plans

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

### Auto-format on save

Automatically format Terraform files after the agent creates or edits them:

```json
{
  "hooks": {
    "Write": {
      "command": "if echo '${input.file_path}' | grep -qE '\\.(tf|tofu)$'; then tofu fmt '${input.file_path}' 2>/dev/null || terraform fmt '${input.file_path}' 2>/dev/null || true; fi"
    }
  }
}
```

## Trust and security

Project-level hooks (`.opscode/hooks.json`) can run arbitrary shell commands and require explicit trust:

```bash
ops --trust-project-hooks
```

Global hooks (`~/.opscode/hooks.json`) are always trusted since they're in your home directory.
