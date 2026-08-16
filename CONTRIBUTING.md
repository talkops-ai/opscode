# Contributing to OpsCode

Thank you for your interest in contributing to OpsCode! OpsCode is an autonomous AI agent purpose-built for DevOps, Site Reliability Engineering, and Infrastructure-as-Code.

---

## 🛠️ Development Setup

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended fast package manager)
- Git

### 1. Clone & Set Up Environment

```bash
# Clone the repository
git clone https://github.com/talkops-ai/opscode.git
cd opscode

# Create a virtual environment
uv venv --python 3.12
source .venv/bin/activate

# Install all dev and test dependencies in editable mode
uv pip install -e ".[dev,test-integration]"
```

### 2. Running Tests

```bash
# Run unit tests (fast, no API keys required)
uv run pytest tests/ -m unit -v

# Run with coverage report
uv run pytest tests/ -m unit --cov=opscode --cov-report=term-missing
```

### 3. Shell Syntax Validation

```bash
# Validate installer scripts
bash -n scripts/install.sh
```

---

## 🧩 Adding a Custom Subagent or Skill

### Adding a Built-in Skill
1. Create a new directory under `src/opscode/built_in_skills/<skill-name>/`.
2. Add a `SKILL.md` file with YAML frontmatter:
   ```yaml
   ---
   name: my-skill
   description: Explains what this skill does and when the agent should trigger it
   ---
   # Skill Instructions
   ...
   ```
3. Add any reference documents under `references/` or templates under `assets/`.
4. Run `uv run pytest tests/unit_tests/skills/` to verify discovery.

### Adding an Enterprise Subagent
1. Create a directory under `src/opscode/built_in_subagents/<subagent-name>/`.
2. Add the agent markdown definition under `agents/<subagent-name>.md`.
3. Add domain-specific skills under `skills/` and optional `.mcp.json`.
4. Register the subagent in `src/opscode/agent/factory.py`.
5. Run `uv run pytest tests/unit_tests/subagents/` to verify isolated branch memory.

---

## 📝 Pull Request Guidelines

1. **Create a topic branch:** `git checkout -b feature/my-enhancement`
2. **Commit conventions:** Use conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).
3. **Ensure tests pass:** Run `uv run pytest tests/ -m unit`.
4. **Submit PR:** Open a Pull Request on GitHub against `main`.

---

## 📄 License

By contributing to OpsCode, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
