# Plugins & Marketplaces

> Extend OpsCode with modular plugins bundling domain skills, subagents, MCP servers, and custom commands.

OpsCode features a marketplace-backed plugin architecture. Plugins can bundle skills, specialized subagents, MCP server definitions, slash commands, custom renderers, and color themes.

---

## Agent Plugins vs. Non-Agent Plugins

When discovering plugins, OpsCode automatically **bifurcates** them based on their directory contents:

1. **Agent Plugins (Subagent Bundles):**
   - Identified by an `agents/` directory containing one or more `*.md` files.
   - Each agent definition becomes a registered subagent.
   - The plugin's bundled `skills/`, `.mcp.json` configs, and commands are bound **exclusively** to that subagent. They do not pollute the main deep agent.

2. **Non-Agent Plugins (Global Deep Agent Extensions):**
   - Plugins without an `agents/` directory.
   - Their skills (Tier 2 in hierarchy), MCP servers, and commands are bound directly to the **main** OpsCode deep agent.

---

## Plugin protocol

Python-based plugins implement the `OpsCodePlugin` protocol:

```python
from typing import Protocol, Any
from opscode.commands import SlashCommand

class OpsCodePlugin(Protocol):
    name: str

    def register_commands(self) -> list[SlashCommand]: ...
    def register_tools(self) -> list[Any]: ...
    def register_renderers(self) -> dict[str, Any]: ...
    def get_theme_overrides(self) -> dict[str, str] | None: ...
```

Plugins can be packaged as:
- **Filesystem plugins:** Directories containing a `plugin.json` manifest.
- **Python entrypoints:** Installed packages exposing the `opscode.plugins` entry point group in `pyproject.toml`.
- **Marketplace plugins:** Git repositories or archives installed from remote marketplaces.

---

## Plugin directory layout

```
my-devops-plugin/
├── plugin.json           # Required — plugin metadata and manifest
├── agents/               # Optional — subagent definitions (*.md)
│   └── sre-automater.md
├── skills/               # Optional — domain skills (SKILL.md)
│   └── incident-triage/
│       └── SKILL.md
├── mcp.json              # Optional — embedded MCP server configuration
└── resources/            # Optional — templates, scripts, and assets
```

### `plugin.json` manifest format

```json
{
  "name": "kubernetes-sre",
  "version": "1.0.0",
  "description": "Kubernetes SRE incident diagnostics, runbooks, and cluster health skills",
  "author": "Platform Team",
  "skills": [
    "skills/incident-triage"
  ]
}
```

---

## Plugin storage locations

### Project plugins (`.opscode/plugins/`)

Place plugins directly inside your repository for team-shared extensions:

```
.opscode/plugins/
├── aws-governance/
│   ├── plugin.json
│   ├── agents/
│   │   └── aws-auditor.md
│   ├── skills/
│   │   └── iam-least-privilege/
│   │       └── SKILL.md
│   └── mcp.json
```

Project plugins are automatically discovered and loaded on session startup.

### User plugins (`~/.opscode/plugins/`)

Marketplace-installed user plugins reside in `~/.opscode/plugins/`:

```
~/.opscode/plugins/
├── cache/              # Downloaded plugin tarballs and archives
├── data/               # Persistent per-plugin working state
└── marketplaces/       # Cloned remote marketplace repositories
```

### Enablement settings

Plugin activation is tracked across three standard settings scopes:

| File | Scope | Git Tracking |
|---|---|---|
| `~/.opscode/settings.json` | User-scope | Local only |
| `.opscode/settings.json` | Project-scope | Committed to Git (shared with team) |
| `.opscode/settings.local.json` | Local project override | Gitignored |

```json
{
  "enabledPlugins": {
    "kubernetes-sre@company-marketplace": true,
    "aws-governance@company-marketplace": true
  }
}
```

---

## Marketplace management

### CLI commands

Manage plugins from the shell using `opscode plugin`:

```bash
# List all installed and discovered plugins
opscode plugin list

# Install a plugin from a configured marketplace
opscode plugin install kubernetes-sre

# Uninstall a plugin
opscode plugin uninstall kubernetes-sre

# Enable or disable a plugin
opscode plugin enable kubernetes-sre
opscode plugin disable kubernetes-sre

# Manage marketplace sources
opscode plugin marketplace add https://github.com/my-org/opscode-marketplace
opscode plugin marketplace list
opscode plugin marketplace remove my-marketplace
```

Marketplace source registry is maintained in `~/.opscode/.state/plugin_marketplaces.json`.

Or use `/plugins` inside an interactive OpsCode session to manage plugins visually.
