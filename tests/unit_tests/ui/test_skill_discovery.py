"""Phase 5 integration tests — skill discovery and server config validation."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


BUILT_IN_SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "src" / "opscode" / "built_in_skills"

EXPECTED_SKILLS = [
    "cloud-core",
    "docker",
    "kubernetes",
    "remember",
]


# ── Skill Discovery ─────────────────────────────────────


class TestBuiltInSkillsExist:
    """All expected built-in skill directories must contain SKILL.md."""

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_dir_exists(self, skill_name: str):
        skill_dir = BUILT_IN_SKILLS_DIR / skill_name
        assert skill_dir.is_dir(), f"Missing skill directory: {skill_dir}"

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_md_exists(self, skill_name: str):
        skill_md = BUILT_IN_SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_md.is_file(), f"Missing SKILL.md: {skill_md}"


class TestSkillFrontmatter:
    """Every SKILL.md must have valid YAML frontmatter with required fields."""

    _FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    _NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_frontmatter_parseable(self, skill_name: str):
        skill_md = BUILT_IN_SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        match = self._FRONTMATTER_RE.match(content)
        assert match is not None, f"{skill_name}: no YAML frontmatter block found"

        fm = yaml.safe_load(match.group(1))
        assert isinstance(fm, dict), f"{skill_name}: frontmatter is not a dict"

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_frontmatter_has_required_fields(self, skill_name: str):
        skill_md = BUILT_IN_SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        match = self._FRONTMATTER_RE.match(content)
        assert match is not None
        fm = yaml.safe_load(match.group(1))

        assert "name" in fm, f"{skill_name}: frontmatter missing 'name'"
        assert "description" in fm, f"{skill_name}: frontmatter missing 'description'"
        assert isinstance(fm["name"], str), f"{skill_name}: 'name' must be a string"
        assert isinstance(fm["description"], str), f"{skill_name}: 'description' must be a string"

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_name_matches_directory(self, skill_name: str):
        skill_md = BUILT_IN_SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        match = self._FRONTMATTER_RE.match(content)
        assert match is not None
        fm = yaml.safe_load(match.group(1))

        assert fm["name"] == skill_name, (
            f"Skill directory '{skill_name}' has frontmatter name '{fm['name']}' — they must match"
        )

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_name_valid_format(self, skill_name: str):
        assert self._NAME_RE.match(skill_name), (
            f"Skill name '{skill_name}' does not match the required pattern: "
            "lowercase alphanumeric + hyphens, max 64 chars"
        )
        assert len(skill_name) <= 64

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_has_body_content(self, skill_name: str):
        skill_md = BUILT_IN_SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        match = self._FRONTMATTER_RE.match(content)
        assert match is not None
        body = content[match.end():].strip()
        # Every skill should have at least 100 chars of instructions
        assert len(body) >= 100, (
            f"{skill_name}: SKILL.md body is too short ({len(body)} chars) — "
            "should contain comprehensive instructions"
        )


# ── Server Config ────────────────────────────────────────


class TestServerConfig:
    def test_generate_langgraph_json(self, tmp_path: Path):
        from opscode.server.server import generate_langgraph_json

        config_path = generate_langgraph_json(
            tmp_path,
            graph_ref="./server_graph.py:make_graph",
            checkpointer_path="./checkpointer.py:create_checkpointer",
        )
        assert config_path.is_file()

        import json
        config = json.loads(config_path.read_text())
        assert "graphs" in config
        assert config["graphs"]["agent"] == "./server_graph.py:make_graph"
        assert config["checkpointer"]["path"] == "./checkpointer.py:create_checkpointer"

    def test_server_env_prefix(self):
        from opscode.server import SERVER_ENV_PREFIX
        assert SERVER_ENV_PREFIX == "OPSCODE_SERVER_"


# ── Integrations Package ────────────────────────────────


class TestIntegrationsPackage:
    def test_imports(self):
        """Verify all public APIs are importable."""
        from opscode.integrations import (
            EventBus,
            ExternalEvent,
            dispatch_hook,
            dispatch_hook_fire_and_forget,
            drain_pending_hooks,
        )

    def test_hook_event_constants(self):
        from opscode.integrations.hooks import ALL_KNOWN_EVENTS, STANDARD_EVENTS, DEVOPS_EVENTS
        assert "session.start" in STANDARD_EVENTS
        assert "terraform.plan" in DEVOPS_EVENTS
        assert STANDARD_EVENTS | DEVOPS_EVENTS == ALL_KNOWN_EVENTS
