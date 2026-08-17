# Plugins and marketplaces

> Extend OpsCode with plugins that bundle skills, subagents, MCP servers, slash commands, and hooks

Plugins extend OpsCode with reusable skills, subagents, MCP servers, custom slash commands, and hooks. There are three types of plugins depending on what they contain and who builds them:

| Type | What it adds | How it binds |
|---|---|---|
| **Agent plugins** | A dedicated subagent with its own skills, MCP servers, and tool scope | Skills and tools bind to the subagent only — not the main agent |
| **Vertical plugins** | Skills, slash commands, and hooks — no subagent | Skills and commands bind to the main agent directly |
| **Partner-built plugins** | Skills and MCP servers from third-party tool vendors | Skills and MCP tools bind to the main agent, often with external API connectors |

OpsCode detects the type automatically: if the plugin has an `agents/` directory, it's treated as an agent plugin; otherwise, its skills, MCP servers, and commands bind directly to the main agent.

:::warning
Install plugins and marketplaces only from sources you trust. An enabled plugin can add instructions, start MCP server processes, and register slash commands with your user permissions.
:::

## Manage plugins interactively

To browse marketplaces and manage plugins inside an OpsCode session:

1. Run `/plugins` to open the plugin manager.
2. Add a marketplace from the **Marketplaces** tab. Supported sources:
   * A GitHub repository in `owner/repo` format, optionally followed by `@branch-or-tag`.
   * An HTTPS Git URL, optionally followed by `#branch-or-tag`.
   * An HTTPS URL serving a marketplace JSON file.
   * A local directory or JSON file.
3. Install a plugin from the marketplace.
4. Run `/reload` to activate newly installed skills and MCP servers without restarting.

The plugin manager also lets you enable, disable, and uninstall installed plugins. Disabling a plugin keeps it installed but excludes its skills and MCP servers after `/reload`.

## Manage plugins from the command line

Use `ops plugin` for scripts and terminal-based administration. Plugin IDs use the `plugin-name@marketplace-name` format.

```bash
# Add and inspect a marketplace
ops plugin marketplace add acme/plugins
ops plugin marketplace list

# Browse and install plugins
ops plugin list
ops plugin install terraform-linter@devops-terraform-toolkit

# Change plugin state
ops plugin disable terraform-linter@devops-terraform-toolkit
ops plugin enable terraform-linter@devops-terraform-toolkit

# Remove a plugin or marketplace
ops plugin uninstall terraform-linter@devops-terraform-toolkit
ops plugin marketplace remove devops-terraform-toolkit
```

`plugin list` and `plugin marketplace list` accept `--json`. After installing, run `/reload` in an active session or start a new one.

---

## Plugin types in detail

### Agent plugins

An agent plugin bundles a **dedicated subagent** with its own skills and tool scope. The subagent runs in isolation — its skills and MCP servers don't affect the main agent.

**Example:** A Terraform linter agent plugin

```
terraform-linter/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   └── terraform-linter.md    # Subagent definition (AGENTS.md format)
└── skills/
    ├── tf-fmt-check/
    │   └── SKILL.md
    └── tf-validate/
        └── SKILL.md
```

**`agents/terraform-linter.md`:**
```markdown
---
name: terraform-linter
description: Lints and validates Terraform modules for formatting, syntax errors, and best-practice compliance.
tools: read_file, execute, glob, grep
skills:
  - tf-fmt-check
  - tf-validate
permission_tier: read-write
---

You are the **Terraform Linter** — a senior infrastructure engineer who specializes in Terraform code quality.

## Workflow
1. Discover `.tf` files with `glob`.
2. Check formatting with the `tf-fmt-check` skill.
3. Validate syntax with the `tf-validate` skill.
4. Combine findings into a structured report.

## Guardrails
- Read-only analysis. Never modify source files.
- Cite every finding with specific file and line number.
```

The subagent gets its skills (`tf-fmt-check`, `tf-validate`) loaded only when it's invoked. It's restricted to the tools declared in its frontmatter (`read_file`, `execute`, `glob`, `grep`).

### Vertical plugins

A vertical plugin adds skills, slash commands, and hooks directly to the **main agent** — no subagent involved. Use vertical plugins for cross-cutting capabilities like code review, security scanning, or compliance checks.

**Example:** A module reviewer vertical plugin

```
module-reviewer/
├── .claude-plugin/
│   └── plugin.json
├── commands/                    # Custom slash commands
│   ├── review-module.md
│   └── scan-security.md
├── hooks/
│   └── hooks.json
└── skills/
    ├── module-best-practices/
    │   └── SKILL.md
    └── security-scan/
        └── SKILL.md
```

#### Custom slash commands

Plugins can register their own slash commands by placing markdown files in a `commands/` directory. Each command file uses YAML frontmatter:

**`commands/review-module.md`:**
```markdown
---
name: review-module
description: Run a comprehensive code review on a Terraform module directory.
---

## Usage

```
/review-module <module-path>
```

## What it does

Runs a full code review on the specified Terraform module:
1. **Structure Check** — Verifies standard file layout.
2. **Naming Conventions** — Checks snake_case and descriptive names.
3. **Documentation** — Verifies all variables/outputs have descriptions.
4. **Best Practices** — Detects hardcoded values, missing types, resources without tags.
5. **Report** — Generates a structured report with severity levels.
```

Once installed, users can type `/review-module modules/s3` or `/scan-security modules/s3` directly inside an OpsCode session.

#### Plugin hooks

Plugins can bundle their own `hooks/hooks.json` to trigger scripts when specific tools are invoked. These hooks merge with the global and project hooks at load time.

### Partner-built plugins

Partner-built plugins come from third-party tool vendors who want to integrate their services into OpsCode. They typically bundle **skills and an MCP server** that connects to an external API.

**Example:** An AWS cost estimator built by a pricing data partner

```
aws-cost-estimator/
├── .claude-plugin/
│   └── plugin.json
├── .mcp.json                   # MCP server for Infracost API
├── CONNECTORS.md               # Setup guide for the external service
└── skills/
    └── cost-estimate/
        └── SKILL.md
```

**`.mcp.json` with variable substitution:**
```json
{
  "mcpServers": {
    "infracost": {
      "command": "echo",
      "args": ["${PLUGIN_ROOT}/scripts/mock-infracost-server"],
      "env": {
        "INFRACOST_API_KEY": "${INFRACOST_API_KEY}",
        "PROJECT_DIR": "${PROJECT_DIR}"
      }
    }
  }
}
```

MCP configs in plugins support **variable substitution** — OpsCode resolves `${PLUGIN_ROOT}`, `${PROJECT_DIR}`, and any `${ENV_VAR}` at startup time.

**`CONNECTORS.md`** is a setup guide for the external service (prerequisites, API keys, supported resources). It helps users understand what they need to configure before using the plugin.

---

## Plugin directory structure

The full set of components a plugin can contain:

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json          # Required — metadata and version
├── agents/                  # Optional — subagent definitions (makes it an agent plugin)
│   └── my-agent/
│       └── AGENTS.md        # Subagent system prompt with YAML frontmatter
├── skills/                  # Optional — domain skills
│   └── my-skill/
│       └── SKILL.md
├── commands/                # Optional — custom slash commands
│   └── my-command.md
├── hooks/                   # Optional — lifecycle hooks
│   └── hooks.json
├── .mcp.json                # Optional — embedded MCP server configuration
├── CONNECTORS.md            # Optional — external service setup guide
└── resources/               # Optional — templates, scripts, and assets
```

### plugin.json

```json
{
  "name": "terraform-linter",
  "version": "0.1.0",
  "description": "Lints and validates Terraform modules for formatting, syntax, and best practices.",
  "author": {
    "name": "TalkOps Engineering"
  }
}
```

Plugins can also be packaged as Python entrypoints exposing the `opscode.plugins` entry point group.

---

## Where plugins live

### Project plugins

Place plugins in `.opscode/plugins/` for team-shared extensions. Organize them by type:

```
.opscode/plugins/
├── agent-plugins/
│   └── terraform-linter/
├── partner-built/
│   └── aws-cost-estimator/
└── vertical-plugins/
    └── module-reviewer/
```

Project plugins are automatically discovered and loaded on session startup.

### Local project marketplace

You can also bundle a local marketplace inside your project so plugins are self-contained:

```
.opscode/.opscode-plugin/marketplace.json
```

```json
{
  "name": "devops-terraform-toolkit",
  "owner": {
    "name": "TalkOps Engineering"
  },
  "plugins": [
    {
      "name": "terraform-linter",
      "displayName": "Terraform Linter",
      "source": "./plugins/agent-plugins/terraform-linter",
      "description": "Agent plugin that lints Terraform modules with a dedicated subagent."
    },
    {
      "name": "aws-cost-estimator",
      "displayName": "AWS Cost Estimator",
      "source": "./plugins/partner-built/aws-cost-estimator",
      "description": "Partner-built plugin for AWS cost estimation via Infracost MCP."
    },
    {
      "name": "module-reviewer",
      "displayName": "Module Reviewer",
      "source": "./plugins/vertical-plugins/module-reviewer",
      "description": "Vertical plugin for Terraform module code review with security scanning."
    }
  ]
}
```

This makes the entire plugin ecosystem Git-trackable and team-shareable.

### User plugins

Marketplace-installed plugins live in `~/.opscode/plugins/`:

```
~/.opscode/plugins/
├── cache/              # Downloaded plugin archives
├── data/               # Persistent per-plugin data
└── marketplaces/       # Cloned marketplace repositories
```

### Enablement settings

Plugin activation is tracked across three scopes:

| File | Scope | Git tracked? |
|---|---|---|
| `~/.opscode/settings.json` | User | No |
| `.opscode/settings.json` | Project | Yes (shared with team) |
| `.opscode/settings.local.json` | Local project override | No (gitignored) |

```json
{
  "enabledPlugins": {
    "terraform-linter@devops-terraform-toolkit": true,
    "investment-banking@claude-for-financial-services": true
  }
}
```

---

## Create a marketplace

A marketplace is a directory or Git repository containing a `marketplace.json` catalog:

```json
{
  "name": "company-marketplace",
  "description": "Internal DevOps plugins",
  "plugins": [
    {
      "name": "kubernetes-sre",
      "displayName": "Kubernetes SRE",
      "description": "SRE incident diagnostics and runbooks",
      "source": "./plugins/kubernetes-sre"
    }
  ]
}
```

Share it with your team by hosting the repository and running:

```bash
ops plugin marketplace add https://github.com/my-org/opscode-marketplace
```
