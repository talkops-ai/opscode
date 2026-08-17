# Quickstart

> Install OpsCode, launch the TUI, and run your first task

OpsCode is a terminal agent for DevOps, Platform Engineering, and Infrastructure-as-Code. This guide covers installation, your first task, interactive mode, headless automation, and tracing. For a full feature overview, see the [Overview](./overview.md).

## Install and run your first task

### 1. Install

```bash
curl -LsSf https://raw.githubusercontent.com/talkops-ai/opscode/v0.1.0/scripts/install.sh | bash
```

### 2. Launch the TUI

```bash
ops
```

### 3. Add credentials

Inside the TUI, run:

```
/auth
```

Select a provider and enter your API key. See [Credentials](./credentials.md) for the full provider list and alternative setup methods.

:::tip
Web search uses [Tavily](https://tavily.com). Add a key via `/auth` or set `export TAVILY_API_KEY="tvly-..."`.
:::

### 4. Give it a task

Type a prompt directly in the chat input:

```
Create a Terraform module for an AWS S3 bucket with KMS encryption, versioning, and lifecycle rules
```

OpsCode interprets the request, uses its built-in cloud knowledge, and proposes changes with diffs for your approval. It can run `terraform validate` and `terraform plan` to verify the output.

### 5. Enable tracing (optional)

Run `/auth` and add your LangSmith API key. Tracing starts on the next launch. See [Trace with LangSmith](#trace-with-langsmith) for details.

:::note
OpsCode is designed for macOS and Linux. Windows users should run it under [WSL](https://learn.microsoft.com/en-us/windows/wsl/install).
:::

## Interactive mode

Type naturally as you would in a chat. The agent uses its built-in tools, skills, and memory to assist you.

### Slash commands

| Command | What it does |
|---|---|
| `/model` | Switch models or open the model picker |
| `/effort` | Set reasoning effort (`low`, `medium`, `high`) |
| `/agents` | Switch between subagents |
| `/auth` | Manage provider credentials |
| `/skills` | Browse and invoke skills |
| `/memory` | View, save, or delete persistent memory |
| `/mcp` | View loaded MCP servers and tools |
| `/plugins` | Manage plugins |
| `/config` | View or modify runtime configuration |
| `/permissions` | Manage file and tool permissions |
| `/cost` | View token usage and cost for the session |
| `/context` | Show context window utilization |
| `/compact` | Manually trigger conversation compaction |
| `/goal` | Set a goal with acceptance criteria |
| `/rubric` | Attach or view rubric criteria |
| `/tasks` | View and manage the agent's task list |
| `/review` | Request self-review of recent changes |
| `/loop` | Enter an autonomous execution loop |
| `/copy` | Copy the last response to clipboard |
| `/clear` | Clear conversation history |
| `/resume` | Browse and resume past threads |
| `/trace` | View or toggle LangSmith tracing |
| `/doctor` | Run diagnostics |
| `/bug` | Open a GitHub bug report |
| `/fast` | Switch to a faster model |
| `/btw` | Send a note without triggering a new turn |
| `/help` | List all commands |
| `/exit` | Exit the session |
| `/version` | Show version info |

### Keyboard shortcuts

| Shortcut | What it does |
|---|---|
| `Shift+Tab` | Cycle approval mode (Manual → Auto → YOLO) |
| `Escape` | Cancel the current response stream |
| `Ctrl+C` | Interrupt running tool or exit |

### Resume a conversation

OpsCode saves conversations as threads. Pick up where you left off:

```bash
ops -r              # Resume the most recent thread
ops -r <thread-id>  # Resume a specific thread
```

Or use `/resume` inside a session to browse past threads.

### Switch subagents

Start a session with a specific subagent:

```bash
ops -a aws-terraform-module-writer
```

Or use `/agents` inside a session to switch. See [Subagents](./subagents.md) for details.

## Non-interactive mode

Run a single task without the TUI:

```bash
ops -n "Validate all Terraform modules in this repo"
```

### Pipe input

```bash
echo "Explain this Kubernetes deployment" | ops
cat pod-spec.yaml | ops -n "Review this pod spec for security issues"
```

### Output control

| Flag | What it does |
|---|---|
| `-q`, `--quiet` | Clean output for piping |
| `--no-stream` | Buffer the full response before printing |
| `--max-turns N` | Limit agentic turns |
| `--timeout SECONDS` | Hard wall-clock timeout |

### Self-evaluation with rubrics

Attach acceptance criteria so the agent checks its own work:

```bash
ops -n "Add health checks to the deployment" \
  --rubric "livenessProbe and readinessProbe are configured on all containers"
```

See [Goals and Rubrics](./goal-and-rubrics.md) for more options.

### Examples

```bash
# Quick validation
ops -n "Run terraform validate on modules/"

# Quiet mode for CI
ops -n "Check all Helm charts for linting errors" --quiet

# With a turn limit
ops -n "Refactor the network module" --max-turns 10

# Auto-approve safe operations
ops -n "Format all Terraform files" -y

# With rubric grading
ops -n "Create a Kubernetes NetworkPolicy for the API service" \
  --rubric "Policy denies all ingress by default and allows only port 8080 from the gateway"
```

## Trace with LangSmith

OpsCode integrates with [LangSmith](https://smith.langchain.com) for tracing agent execution, subagent delegation, and tool calls.

### Setup

1. Run `/auth` and add your LangSmith API key.
2. Restart OpsCode — tracing starts automatically.

### Project name

Set a custom project name:

```bash
export LANGSMITH_PROJECT="my-infra-project"
ops
```

Or use `/trace` inside a session to check tracing status.

### CI/CD tracing

```bash
export LANGSMITH_API_KEY="ls-..."
export LANGSMITH_PROJECT="ci-opscode"
ops -n "Run infrastructure tests" --quiet
```

## What's next

- **[Configuration](./Configuration.md)** — `config.toml`, environment variables, and data locations
- **[CLI Reference](./cli-reference.md)** — Complete flag and subcommand reference
- **[Credentials](./credentials.md)** — Provider key management
- **[Memory and Skills](./memory-and-skills.md)** — Persistent memory and custom skills
- **[Subagents](./subagents.md)** — Delegating tasks to specialized subagents
