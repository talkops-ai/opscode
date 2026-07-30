"""``/reload``, ``/restart``, ``/update`` — Runtime management commands.

``/install`` is intentionally omitted (deprecated — packages are installed
via the ``/model`` command or plugin system).
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from dcoder.commands._base import BaseCommandHandler, CommandContext, CommandResult
from dcoder.commands._types import BypassTier, CommandCategory, SafetyLevel

logger = logging.getLogger(__name__)


# ── /reload ──────────────────────────────────────────────


class ReloadHandler(BaseCommandHandler):
    """Hot-reload configuration, skills, themes, and ``.env`` without restart.

    This clears cached settings, re-discovers skills and plugins, and
    re-reads environment variables.  The LangGraph server subprocess is
    NOT restarted — use ``/restart`` for that.
    """

    @property
    def name(self) -> str:
        return "/reload"

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.POWER

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.LOW_RISK

    @property
    def bypass_tier(self) -> BypassTier:
        return BypassTier.IMMEDIATE

    async def execute(self, ctx: CommandContext) -> CommandResult:
        report_parts: list[str] = []

        # 1. Reload .env / environment
        _reload_dotenv()
        report_parts.append("✓ Environment variables reloaded")

        # 2. Clear settings cache
        try:
            from dcoder.config.settings import settings as _settings

            _settings.reload_from_environment()
            report_parts.append("✓ Settings cache cleared")
        except Exception as exc:
            report_parts.append(f"⚠ Settings cache: {exc}")

        # 3. Re-discover skills
        try:
            app = ctx.app
            if app is not None and hasattr(app, "_discover_skills"):
                app._discover_skills()
                report_parts.append("✓ Skills re-discovered")
            else:
                report_parts.append("⚠ Skills: app._discover_skills not available")
        except Exception as exc:
            report_parts.append(f"⚠ Skills: {exc}")

        # 4. Re-discover plugins
        try:
            app = ctx.app
            if app is not None and hasattr(app, "_discover_plugins"):
                app._discover_plugins()
                report_parts.append("✓ Plugins re-discovered")
        except Exception as exc:
            report_parts.append(f"⚠ Plugins: {exc}")

        # 5. Re-load themes
        try:
            app = ctx.app
            if app is not None and hasattr(app, "reload_css"):
                app.reload_css()
                report_parts.append("✓ Themes reloaded")
        except Exception as exc:
            report_parts.append(f"⚠ Themes: {exc}")

        return CommandResult(
            success=True,
            message="**Configuration Reloaded:**\n" + "\n".join(report_parts),
        )


# ── /restart ─────────────────────────────────────────────


class RestartHandler(BaseCommandHandler):
    """Full restart: ``/reload`` + respawn the LangGraph server subprocess.

    Cancels any in-flight agent work and drops the queued message
    backlog before respawning.  Reference: deepagents_code/app.py L20234.
    """

    @property
    def name(self) -> str:
        return "/restart"

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.POWER

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.HIGH_RISK

    @property
    def bypass_tier(self) -> BypassTier:
        # Must always run, even when agent is wedged.
        return BypassTier.IMMEDIATE

    async def execute(self, ctx: CommandContext) -> CommandResult:
        app = ctx.app
        report_parts: list[str] = []

        # 1. Reload configuration first (same as /reload)
        _reload_dotenv()
        try:
            from dcoder.config.settings import settings as _settings

            _settings.reload_from_environment()
        except Exception:
            pass
        report_parts.append("✓ Configuration reloaded")

        # 2. Cancel in-flight agent work
        if app is not None and hasattr(app, "_cancel_active_work"):
            try:
                app._cancel_active_work()
                report_parts.append("✓ Active work cancelled")
            except Exception as exc:
                report_parts.append(f"⚠ Cancel work: {exc}")

        # 3. Respawn server
        if app is not None and hasattr(app, "_server_proc") and app._server_proc is not None:
            try:
                app._server_proc.stop()
                report_parts.append("✓ Server process stopped")
            except Exception as exc:
                report_parts.append(f"⚠ Stop server: {exc}")

            if hasattr(app, "_start_server"):
                try:
                    await app._start_server()
                    report_parts.append("✓ Server process restarted")
                except Exception as exc:
                    report_parts.append(f"⚠ Restart server: {exc}")
        else:
            report_parts.append("ℹ No owned server subprocess — configuration reloaded only")

        # 4. Re-discover skills and plugins
        if app is not None:
            if hasattr(app, "_discover_skills"):
                try:
                    app._discover_skills()
                    report_parts.append("✓ Skills re-discovered")
                except Exception:
                    pass
            if hasattr(app, "_discover_plugins"):
                try:
                    app._discover_plugins()
                    report_parts.append("✓ Plugins re-discovered")
                except Exception:
                    pass

        return CommandResult(
            success=True,
            message="**Server Restarted:**\n" + "\n".join(report_parts),
        )


# ── /update ──────────────────────────────────────────────


class UpdateHandler(BaseCommandHandler):
    """Check for and install DCoder updates.

    Reference: deepagents_code/app.py L5428.

    Usage:
      ``/update``              — check and upgrade to latest stable
      ``/update --prerelease`` — include pre-release versions
      ``/update --deps``       — refresh dependency versions
    """

    @property
    def name(self) -> str:
        return "/update"

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.POWER

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.HIGH_RISK

    @property
    def bypass_tier(self) -> BypassTier:
        return BypassTier.IMMEDIATE

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()
        parts = args.split() if args else []

        # Validate flags
        allowed = {"--prerelease", "--deps"}
        unknown = [p for p in parts if p.startswith("-") and p not in allowed]
        if unknown:
            return CommandResult(
                success=False,
                message=f"Unknown option(s): {' '.join(unknown)}.\nUsage: /update [--deps] [--prerelease]",
            )

        prerelease = "--prerelease" in parts

        # Check current version
        try:
            from dcoder import __version__ as current_version
        except ImportError:
            current_version = "unknown"

        # Check PyPI for latest
        latest = await asyncio.to_thread(_check_pypi_version, prerelease=prerelease)
        if latest is None:
            return CommandResult(
                success=True,
                message=f"Could not determine latest version. Currently on v{current_version}.\n"
                "Check your network connection and try again.",
            )

        if latest == current_version:
            return CommandResult(
                success=True,
                message=f"Already on the latest version (v{current_version}).",
            )

        # Perform upgrade
        success, output = await asyncio.to_thread(
            _perform_upgrade, target_version=latest, prerelease=prerelease
        )
        if success:
            return CommandResult(
                success=True,
                message=f"✅ Updated from v{current_version} → v{latest}.\n"
                "Restart DCoder to use the new version (`/restart`).",
            )

        return CommandResult(
            success=False,
            message=f"Update failed:\n```\n{output}\n```",
        )


# ── Helpers ──────────────────────────────────────────────


def _reload_dotenv() -> None:
    """Re-read .env files into os.environ."""
    try:
        from dotenv import load_dotenv

        load_dotenv(override=True)
        # Also try project-level .env
        project_env = Path.cwd() / ".env"
        if project_env.is_file():
            load_dotenv(project_env, override=True)
    except ImportError:
        pass


def _check_pypi_version(*, prerelease: bool = False) -> str | None:
    """Query PyPI for the latest dcoder version."""
    try:
        import json
        import urllib.request

        url = "https://pypi.org/pypi/dcoder/json"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())

        if prerelease:
            # Get all versions and pick the latest
            versions = list(data.get("releases", {}).keys())
            if versions:
                return versions[-1]

        return data.get("info", {}).get("version")
    except Exception:
        return None


def _perform_upgrade(*, target_version: str, prerelease: bool = False) -> tuple[bool, str]:
    """Run pip install to upgrade dcoder."""
    cmd = ["pip", "install", "--upgrade", f"dcoder=={target_version}"]
    if prerelease:
        cmd.append("--pre")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as exc:
        return False, str(exc)
