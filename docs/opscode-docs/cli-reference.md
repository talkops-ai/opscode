# CLI Reference

> Complete command-line flags, subcommands, and slash commands for OpsCode.

## Usage

```bash
opscode [OPTIONS] [PROMPT]
# or:
ops [OPTIONS] [PROMPT]
```

When run without arguments, OpsCode starts in interactive TUI mode. Pass a positional prompt or use `-n` for non-interactive headless mode.

## Command-line options

### Prompts and input

| Flag | Description |
|---|---|
| `PROMPT` | Non-interactive prompt (positional argument, alternative to `-n`) |
| `-n`, `--non-interactive TEXT` | Run a single task non-interactively and exit |
| `-m`, `--message TEXT` | Initial prompt to auto-submit when an interactive session starts |
| `-s`, `--skill NAME` | Invoke a skill when the interactive session starts |
| `--startup-cmd CMD` | Shell command executed at startup before the first prompt |
| `--stdin` | Read input from stdin explicitly |

### Thread management

| Flag | Description |
|---|---|
| `-r`, `--resume [ID]` | Resume a thread: `-r` for most recent, `-r <ID>` for specific thread ID |

### Agent selection

| Flag | Description |
|---|---|
| `-a`, `--agent NAME` | Agent / subagent to use (default: `opscode`) |

### Model and execution profile

| Flag | Description |
|---|---|
| `-M`, `--model MODEL` | Model specifier (e.g., `anthropic:claude-opus-4-7`, `openai:gpt-4.1`) |
| `--model-params JSON` | Extra kwargs to pass to the model constructor as a JSON string |
| `--max-retries N` | Override max retries for transient model errors |
| `--profile-override JSON` | Override model profile fields as a JSON string |
| `--default-model [MODEL]` | Set or show the current persistent default model |
| `--clear-default-model` | Clear the configured persistent default model |

### Non-interactive mode controls

These flags require `-n`, a positional prompt, or piped stdin:

| Flag | Description |
|---|---|
| `-q`, `--quiet` | Clean output for piping stdout (suppresses spinners/banners) |
| `--no-stream` | Buffer the full response before writing to stdout |
| `--max-turns N` | Maximum agentic turns before stopping |
| `--timeout SECONDS` | Hard wall-clock timeout in seconds |

### Goal and rubric evaluation

| Flag | Description |
|---|---|
| `--goal TEXT` | Goal objective to generate acceptance criteria (interactive only) |
| `--rubric TEXT\|@PATH` | Acceptance criteria text or `@path` for self-evaluation loop (requires non-interactive mode) |
| `--rubric-model MODEL` | Dedicated grader model for rubric self-evaluation |
| `--rubric-max-iterations N` | Max grader iterations per rubric attempt |
| `--recursion-limit N` | Override main agent recursion limit (default: 2000) |

### Approval modes

Mutually exclusive:

| Flag | Description |
|---|---|
| `-y`, `--auto-approve` | Enable classifier-backed Auto mode (auto-approves safe read-only actions) |
| `--yolo` | Run gated actions without review (after risk acknowledgement) |

### Shell and sandbox

| Flag | Description |
|---|---|
| `-S`, `--shell-allow-list LIST` | Comma-separated allowed shell commands (`recommended`, `all`, or list) |
| `--sandbox [TYPE]` | Remote sandbox for code execution (`agentcore`, `daytona`, `langsmith`, `modal`, `runloop`, `vercel`; default: `none`) |
| `--sandbox-id ID` | Existing remote sandbox ID to attach to |
| `--sandbox-snapshot-name NAME` | Snapshot or blueprint name to create or attach |
| `--sandbox-setup PATH` | Path to setup shell script to run after sandbox creation |

### Interpreter and filesystem tools

| Flag | Description |
|---|---|
| `--interpreter` / `--no-interpreter` | Toggle JavaScript QuickJS interpreter (`js_eval`) middleware |
| `--interpreter-tools VALUE` | Programmatic Tool Calling (PTC) allowlist: `safe`, `all`, or comma-separated list |
| `--allow-fs-tools LIST` | Allowlist of filesystem tools (`all` or comma-separated: `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`, `ls`) |

### MCP and security

| Flag | Description |
|---|---|
| `--mcp-config PATH` | Path to explicit MCP JSON configuration file |
| `--no-mcp` | Disable all MCP tool loading |
| `--trust-project-mcp` | Skip interactive approval for project-level MCP configs |
| `--trust-project-hooks` | Trust project-level `.opscode/hooks.json` command handlers |
| `--acp` | Run as an Agent Client Protocol (ACP) server over stdio instead of launching the TUI |

### Meta

| Flag | Description |
|---|---|
| `-v`, `--version` | Show OpsCode version and exit |
| `--verbose` | Enable verbose debug logging |

---

## Subcommands

### `opscode config`

Inspect resolved configuration without starting a session:

```bash
opscode config show          # Show all effective values and their sources
opscode config list          # List all available options with types and defaults
opscode config get <key>     # Show effective value and source for a single option
opscode config set <key> <v> # Set a configuration value
opscode config path          # Show config file locations and existence status
```

### `opscode auth`

Manage provider credentials from the shell:

```bash
opscode auth list            # List configured credentials and their sources
opscode auth set <provider>  # Set an API key or endpoint for a provider
opscode auth remove <provider> # Remove a stored credential
```

### `opscode plugin`

Manage plugins and marketplace sources from the shell:

```bash
opscode plugin list          # List installed and project plugins
opscode plugin install <id>  # Install a plugin from marketplace
opscode plugin uninstall <id># Uninstall an installed plugin
opscode plugin enable <id>   # Enable a plugin
opscode plugin disable <id>  # Disable a plugin
opscode plugin marketplace add <url>     # Add a remote or local marketplace source
opscode plugin marketplace remove <name> # Remove a marketplace source
opscode plugin marketplace list          # List active marketplace sources
```

### `opscode skills`

Inspect and manage skills:

```bash
opscode skills list          # List all discovered skills across the 7-tier hierarchy
opscode skills info <name>   # Display details, domain, and description for a skill
opscode skills find <query>  # Search skills by keyword
opscode skills create <name> # Scaffolds a new skill directory
```

### `opscode mcp`

Inspect and test MCP server definitions:

```bash
opscode mcp list             # List configured MCP servers
opscode mcp tools            # List available tools across all MCP servers
opscode mcp test <server>    # Test connection to a specific MCP server
```

### `opscode threads`

Manage conversation history and thread checkpoints:

```bash
opscode threads list         # List recent threads (options: --agent, -n/--limit, --branch, --cwd)
opscode threads delete <id>  # Delete a specific thread checkpoint
```

### `opscode agents`

Manage subagents:

```bash
opscode agents list          # List built-in, user, and project subagents
opscode agents reset --agent <name> # Reset an agent's prompt to default
```

### `opscode doctor`

Run comprehensive system diagnostics (checking authentication, network endpoints, core tools, and dependencies).

---

## Slash commands

Available inside an interactive session. Type `/help` to list all commands.

### Core commands

| Command | Aliases | Description |
|---|---|---|
| `/auth` | `/login` | Open interactive credential manager |
| `/logout` | — | Remove stored credentials |
| `/model` | — | Open model selector modal |
| `/effort` | — | Set reasoning effort (`low`, `medium`, `high`) |
| `/fast` | — | Quick switch to a faster / cheaper model |
| `/config` | — | View or modify runtime configuration |
| `/permissions` | `/perms` | Inspect and toggle tool permissions |
| `/skills` | — | Browse and inspect active skills |
| `/mcp` | — | Inspect MCP servers and available tools |
| `/plugins` | — | Manage plugins and marketplace sources |
| `/cost` | — | View session token consumption and USD cost |
| `/context` | — | View context window utilization gauge |
| `/compact` | — | Trigger manual conversation compaction |
| `/clear` | — | Clear conversation history |
| `/clear!` | — | Force clear history without confirmation prompt |
| `/resume` | — | Open thread selector modal to resume a past session |
| `/doctor` | — | Run system diagnostics (auth, tools, dependencies) |
| `/bug` | — | Open GitHub bug report template |
| `/help` | `/h` | List all available slash commands |
| `/exit` | `/quit` | Exit OpsCode session |

### Power commands

| Command | Description |
|---|---|
| `/agents` | Open subagent selector modal to hot-swap active agent |
| `/goal <text>` | Define high-level objective and generate acceptance criteria |
| `/rubric <text\|@file>`| Attach evaluation rubric to current session |
| `/tasks` | Open task management board |
| `/loop` | Enter autonomous execution loop |
| `/review` | Request agent self-review of recent workspace modifications |
| `/memory` | View, save, or delete persistent memory entries (`AGENTS.md`) |
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
| `/skill <name>` | Explicitly invoke a skill |
| `/skill-create`| Distill conversation into a new reusable skill |

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | General runtime error |
| `2` | Argument parsing / validation error |
| `130` | Interrupted by user (Ctrl+C / SIGINT) |
