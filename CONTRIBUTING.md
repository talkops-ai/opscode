# Contributing to OpsCode

Thank you for your interest in contributing to OpsCode! Whether you're fixing a bug, adding a new subagent, building a plugin, or improving documentation — we appreciate every contribution.

---

## 🛠️ Development Setup

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (fast package manager)
- Git

### 1. Clone & install

```bash
git clone https://github.com/talkops-ai/opscode.git
cd opscode

# Create a virtual environment and install
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev,test-integration]"
```

### 2. Run tests

```bash
# Unit tests (fast, no API keys required)
uv run pytest tests/ -m unit -v

# With coverage
uv run pytest tests/ -m unit --cov=opscode --cov-report=term-missing
```

### 3. Validate scripts

```bash
bash -n scripts/install.sh
```

---

## 🧩 Adding Skills

### Built-in skills

Built-in skills live in `src/opscode/built_in_skills/`. OpsCode ships with 4: `cloud-core`, `docker`, `kubernetes`, and `remember`.

1. Create a directory: `src/opscode/built_in_skills/<skill-name>/`
2. Add a `SKILL.md` with YAML frontmatter:
   ```markdown
   ---
   name: my-skill
   description: What this skill does and when the agent should activate it
   ---
   # Instructions
   When this skill is activated, perform the following steps:
   1. ...
   ```
3. Add reference docs under `references/` or templates under `assets/` if needed.
4. Verify discovery: `uv run pytest tests/unit_tests/skills/`

### User and project skills

Users can also create skills without modifying the codebase:

```
~/.opscode/{agent}/skills/<skill-name>/SKILL.md   # User-level
.opscode/skills/<skill-name>/SKILL.md             # Project-level
```

See [Memory and Skills](docs/opscode-docs/memory-and-skills.md) for the full resolution order.

---

## 🤖 Adding Subagents

### Built-in subagents

Built-in subagents live in `src/opscode/built_in_subagents/`. Each has its own skills directory and an agent definition:

```
src/opscode/built_in_subagents/<subagent-name>/
├── agents/
│   └── <subagent-name>.md    # System prompt with YAML frontmatter
├── skills/                    # Domain-specific skills
│   ├── skill-one/
│   │   └── SKILL.md
│   └── skill-two/
│       └── SKILL.md
└── .mcp.json                  # Optional — embedded MCP server config
```

Steps:
1. Create the directory structure above under `src/opscode/built_in_subagents/`.
2. Write the agent definition with frontmatter (`name`, `description`, `tools`, `skills`, `permission_tier`).
3. Add domain skills under `skills/`.
4. Add `.mcp.json` if the subagent needs an external tool server.
5. Verify: `uv run pytest tests/unit_tests/subagents/`

### Custom subagents (no code changes)

Users can add subagents without touching the codebase:

```
~/.opscode/{agent}/agents/<name>/AGENTS.md         # User-level
.opscode/agents/<name>/AGENTS.md                   # Project-level
```

See [Subagents](docs/opscode-docs/subagents.md) for the full frontmatter reference.

---

## 🔌 Adding Plugins

Plugins bundle skills, subagents, MCP servers, slash commands, and hooks into a shareable package. There are three plugin types:

### Agent plugin (bundles a subagent)

```
my-agent-plugin/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   └── my-agent.md
└── skills/
    └── my-skill/
        └── SKILL.md
```

### Vertical plugin (extends the main agent)

```
my-vertical-plugin/
├── .claude-plugin/
│   └── plugin.json
├── commands/                # Custom slash commands
│   └── my-command.md
├── hooks/
│   └── hooks.json
└── skills/
    └── my-skill/
        └── SKILL.md
```

### Partner-built plugin (third-party integration)

```
my-partner-plugin/
├── .claude-plugin/
│   └── plugin.json
├── .mcp.json                # MCP server (supports ${VAR} substitution)
├── CONNECTORS.md            # External service setup guide
└── skills/
    └── my-skill/
        └── SKILL.md
```

### plugin.json

```json
{
  "name": "my-plugin",
  "version": "0.1.0",
  "description": "What this plugin does",
  "author": {
    "name": "Your Name"
  }
}
```

Place plugins in `.opscode/plugins/` for project-level distribution or publish to a marketplace. Run plugin tests with:

```bash
uv run pytest tests/unit_tests/plugins/
```

See [Plugins](docs/opscode-docs/plugins.md) for the full architecture.

---

## 📖 Documentation

Documentation lives in two places:

| Location | What it covers |
|---|---|
| `README.md` | Project overview — keep it high-level and non-technical |
| `docs/opscode-docs/` | Detailed feature docs — one file per topic |

### Style guidelines

- **Human-readable**: Write for users, not developers. Avoid internal class names, module paths, and middleware references.
- **Task-oriented**: Lead with what the user can do, not how it's built internally.
- **Balanced**: Follow the tone of `docs/dcode-docs/` — conversational but precise.
- **No implementation jargon**: Say "OpsCode classifies the command" not "the `AutoModeHITLMiddleware` invokes the `ShellSafetyScanner`".

---

## 📝 Pull Request Guidelines

1. **Branch from main:** `git checkout -b feature/my-enhancement`
2. **Conventional commits:** Use `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`.
3. **Tests pass:** `uv run pytest tests/ -m unit`
4. **Lint clean:** Ensure no regressions in existing tests.
5. **Open a PR** against `main` with a clear description of what changed and why.

---

## 📄 License

By contributing to OpsCode, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
