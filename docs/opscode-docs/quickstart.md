# Quickstart

> Install OpsCode, run your first task, and explore interactive or non-interactive workflows.

OpsCode is a terminal coding and orchestration agent specialized for DevOps, Platform Engineering, and Infrastructure-as-Code. This guide covers installation, your first task, interactive TUI mode, non-interactive automation, and LangSmith tracing. For a complete feature overview, see the [Overview](./overview.md). For `config.toml` and provider settings, see [Configuration](./Configuration.md).

## Install and run your first task

### 1. Install and launch

```bash
# Using pip
pip install opscode

# Or using uv
uv pip install opscode
```

Launch an interactive session using the primary binary or short alias:

```bash
opscode
# or short alias:
ops
```

### 2. Add provider credentials

OpsCode works with 20+ tool-calling LLM providers. OpenAI, Anthropic, Google, DeepSeek, and Groq are available out of the box.

Use the `/auth` command inside an interactive session to configure a provider:

```
/auth
```

See [Credentials](./credentials.md) for the full provider list, environment variable formats, and resolution order.

:::tip
Web search uses [Tavily](https://tavily.com). Add an API key via `/auth` or set `export TAVILY_API_KEY="tvly-..."`.
:::

### 3. Give the agent a task

```
Create a Terraform module for an AWS S3 bucket with KMS encryption, versioning, and lifecycle rules
```

The agent interprets the request, uses its built-in cloud knowledge, and proposes changes with diffs for your approval before modifying files. It can execute `terraform validate` and `terraform plan` to verify the output.

### 4. Enable tracing (optional)

To log agent operations, tool calls, and decisions in LangSmith, run `/auth` and add your LangSmith API key. Tracing is enabled on the next launch.

For project naming and advanced tracing options, see [Trace with LangSmith](#trace-with-langsmith).

:::note
OpsCode is designed for macOS and Linux. Windows users can run it seamlessly under [WSL](https://learn.microsoft.com/en-us/windows/wsl/install).
:::

## Interactive mode

Type naturally as you would in a chat interface. The agent uses its built-in tools, skills, and memory to assist you.

### Slash commands

Use slash commands inside an OpsCode session:

| Command | Description |
|---|---|
| `/model` | Switch models or open the interactive model selector |
| `/effort` | Set reasoning effort (`low`, `medium`, `high`) for reasoning models |
| `/agents` | Hot-swap between pre-configured subagents |
| `/auth` | Manage provider credentials and endpoints |
| `/skills` | Browse and invoke loaded skills |
| `/memory` | View, save, or delete persistent memory entries |
| `/mcp` | View loaded MCP servers and tools |
| `/plugins` | Manage plugins (install, uninstall, enable, disable) |
| `/config` | View or modify runtime configuration |
| `/permissions` | Manage file and tool execution permissions |
| `/cost` | View token usage and USD cost for the current session |
| `/context` | Display context window utilization gauge |
| `/compact` | Manually trigger conversation compaction |
| `/goal` | Set a goal with auto-generated acceptance criteria |
| `/rubric` | Attach or view rubric criteria |
| `/tasks` | View and manage the agent's task list |
| `/review` | Request agent self-review of recent changes |
| `/loop` | Enter an autonomous execution loop |
| `/copy` | Copy the last assistant response to clipboard |
| `/clear` | Clear the conversation history |
| `/resume` | Browse and select from past conversation threads |
| `/trace` | View or toggle LangSmith tracing status |
| `/doctor` | Run diagnostics (providers, tools, dependencies) |
| `/bug` | Open GitHub bug report template |
| `/fast` | Quick switch to a faster / cost-effective model |
| `/btw` | Send an out-of-band note without triggering LLM turn execution |
| `/help` | List all available commands |
| `/exit` | Exit the session |
| `/version` | Show OpsCode version and environment metadata |

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Shift+Tab` | Cycle approval mode (Manual → Auto → YOLO) |
| `Escape` | Cancel the current agent response stream |
| `Ctrl+C` | Interrupt running tool or exit |

### Thread management

OpsCode tracks conversations as threads persisted in SQLite with zero-latency resumption (`idx_opscode_threads_list` index):

```bash
# Resume the most recent thread
opscode -r

# Resume a specific thread by ID
opscode -r <thread-id>
```

Or use the `/resume` command inside an interactive session to browse and preview past threads.

### Subagent switching

Hot-swap between specialized subagents without restarting:

```bash
# Launch with a specific built-in or custom subagent
opscode -a aws-terraform-module-writer
```

Or use `/agents` inside a session. Subagents are defined in `~/.opscode/{agent}/agents/` or `.opscode/agents/`. See [Subagents](./subagents.md) for details.

## Non-interactive mode

Run a single task without launching the TUI and exit when finished:

```bash
opscode -n "Validate all Terraform modules in this repo"
```

### Piped input

Pipe input from another command directly into OpsCode:

```bash
echo "Explain this Kubernetes deployment" | opscode
cat pod-spec.yaml | opscode -n "Review this pod spec for security issues"
```

### Output control

| Flag | Description |
|---|---|
| `-q`, `--quiet` | Clean output for piping stdout |
| `--no-stream` | Buffer the full response before writing |
| `--max-turns N` | Limit the number of agentic turns |
| `--timeout SECONDS` | Hard wall-clock timeout in seconds |

### Self-evaluation with rubrics

Attach acceptance criteria so the agent evaluates its own work with a grader model:

```bash
opscode -n "Add health checks to the deployment" \
  --rubric "livenessProbe and readinessProbe are configured on all containers"
```

For detailed rubric options, see [Goals and Rubrics](./goal-and-rubrics.md).

### Examples

```bash
# Quick validation task
opscode -n "Run terraform validate on modules/"

# Quiet mode for CI pipelines
opscode -n "Check all Helm charts for linting errors" --quiet

# With a max turn limit
opscode -n "Refactor the network module" --max-turns 10

# Auto-approve all safe tool executions
opscode -n "Format all Terraform files" -y

# With rubric self-evaluation
opscode -n "Create a Kubernetes NetworkPolicy for the API service" \
  --rubric "Policy denies all ingress by default and allows only port 8080 from the gateway"
```

## Trace with LangSmith

OpsCode integrates with [LangSmith](https://smith.langchain.com) for end-to-end tracing of agent execution, subagents, and tool calls.

### Setup

1. Run `/auth` and add your LangSmith API key
2. Restart OpsCode — tracing is automatically enabled

### Configuration

Set the project name via environment variable (defaults to `opscode`):

```bash
export LANGSMITH_PROJECT="my-infra-project"
opscode
```

Or use `/trace` inside a session to inspect tracing status.

### CI / headless setup

For non-interactive CI/CD pipelines:

```bash
export LANGSMITH_API_KEY="ls-..."
export LANGSMITH_PROJECT="ci-opscode"
opscode -n "Run infrastructure tests" --quiet
```

## What's next

- **[Configuration](./Configuration.md)** — `config.toml`, environment variables, and data locations
- **[CLI Reference](./cli-reference.md)** — Complete flag and subcommand reference
- **[Credentials](./credentials.md)** — Provider key management and resolution order
- **[Memory and Skills](./memory-and-skills.md)** — Persistent memory and custom skills
- **[Subagents](./subagents.md)** — Delegating tasks to specialized DevOps subagents
