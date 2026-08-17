"""Atomic TOML configuration persistence for OpsCode."""

from __future__ import annotations

import contextlib
import logging
import os
import tempfile
import threading
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from opscode.config.paths import CONFIG_PATH, STATE_DIR

logger = logging.getLogger(__name__)

_config_write_lock = threading.Lock()
_RECENT_MODELS_FILE = STATE_DIR / "recent_models.json"
_MAX_RECENT = 10


def read_config_toml(config_path: Path | None = None) -> dict[str, Any]:
    """Read config.toml and return parsed dict, or empty dict on missing/error."""
    target_path = config_path or CONFIG_PATH
    if not target_path.exists():
        return {}
    try:
        with target_path.open("rb") as f:
            return tomllib.load(f)
    except Exception as exc:
        logger.warning("Could not read config TOML from %s: %s", target_path, exc)
        return {}


def _save_toml_field(
    section: str,
    field: str,
    value: Any,
    config_path: Path | None = None,
) -> bool:
    """Read-modify-write a key under a section in config.toml atomically."""
    target_path = config_path or CONFIG_PATH
    try:
        with _config_write_lock:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if target_path.exists():
                with target_path.open("rb") as f:
                    data = tomllib.load(f)
            else:
                data = {}

            if section not in data or not isinstance(data[section], dict):
                data[section] = {}
            data[section][field] = value

            fd, tmp_path = tempfile.mkstemp(dir=target_path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    tomli_w.dump(data, f)
                Path(tmp_path).replace(target_path)
            except BaseException:
                with contextlib.suppress(OSError):
                    Path(tmp_path).unlink()
                raise
    except (OSError, tomllib.TOMLDecodeError, TypeError, ValueError):
        logger.exception("Could not save %s.%s preference to %s", section, field, target_path)
        return False
    return True


def save_recent_model(model_spec: str, config_path: Path | None = None) -> bool:
    """Persist recent model selection to [models].recent in config.toml and MRU cache."""
    if not isinstance(model_spec, str) or not model_spec:
        return False
    ok = _save_toml_field("models", "recent", model_spec, config_path)
    touch_recent_model(model_spec)
    return ok


def load_recent_model(config_path: Path | None = None) -> str | None:
    """Load [models].recent from config.toml."""
    data = read_config_toml(config_path)
    val = data.get("models", {}).get("recent")
    return str(val).strip() if isinstance(val, str) and val.strip() else None


def save_default_model(model_spec: str, config_path: Path | None = None) -> bool:
    """Persist default model selection to [models].default in config.toml."""
    if not isinstance(model_spec, str) or not model_spec:
        return False
    return _save_toml_field("models", "default", model_spec, config_path)


def clear_default_model(config_path: Path | None = None) -> bool:
    """Remove default model entry from [models].default in config.toml."""
    target_path = config_path or CONFIG_PATH
    if not target_path.exists():
        return True
    try:
        with _config_write_lock:
            with target_path.open("rb") as f:
                data = tomllib.load(f)
            models_sec = data.get("models")
            if not isinstance(models_sec, dict) or "default" not in models_sec:
                return True
            del models_sec["default"]

            fd, tmp_path = tempfile.mkstemp(dir=target_path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    tomli_w.dump(data, f)
                Path(tmp_path).replace(target_path)
            except BaseException:
                with contextlib.suppress(OSError):
                    Path(tmp_path).unlink()
                raise
    except (OSError, tomllib.TOMLDecodeError, TypeError, ValueError):
        logger.exception("Could not clear default model preference")
        return False
    return True


def load_default_model(config_path: Path | None = None) -> str | None:
    """Load [models].default from config.toml, falling back to [models].recent."""
    data = read_config_toml(config_path)
    models_sec = data.get("models", {})
    val = models_sec.get("default")
    if isinstance(val, str) and val.strip():
        return val.strip()
    recent = models_sec.get("recent")
    if isinstance(recent, str) and recent.strip():
        return recent.strip()
    return None


def touch_recent_model(model_spec: str) -> bool:
    """Promote model_spec to the front of recent_models.json."""
    if not isinstance(model_spec, str) or not model_spec:
        return False
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        recent: list[str] = []
        if _RECENT_MODELS_FILE.exists():
            try:
                import json
                raw = json.loads(_RECENT_MODELS_FILE.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    recent = [str(item) for item in raw]
                elif isinstance(raw, dict) and isinstance(raw.get("models"), list):
                    recent = [str(item) for item in raw["models"]]
            except Exception:
                recent = []
        recent = [s for s in recent if s != model_spec]
        recent.insert(0, model_spec)
        recent = recent[:_MAX_RECENT]
        import json
        _RECENT_MODELS_FILE.write_text(json.dumps({"models": recent}, indent=2), encoding="utf-8")
        return True
    except Exception as exc:
        logger.warning("Could not update recent models file: %s", exc)
        return False


def save_effort_for_model(
    model_spec: str,
    effort: str | None,
    config_path: Path | None = None,
) -> bool:
    """Read-modify-write an entry under [effort.by_model] in config.toml."""
    if not isinstance(model_spec, str) or not model_spec:
        return False
    target_path = config_path or CONFIG_PATH

    try:
        with _config_write_lock:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if target_path.exists():
                with target_path.open("rb") as f:
                    data = tomllib.load(f)
            else:
                data = {}

            effort_sec = data.setdefault("effort", {})
            if not isinstance(effort_sec, dict):
                effort_sec = {}
                data["effort"] = effort_sec
            by_mod = effort_sec.setdefault("by_model", {})
            if not isinstance(by_mod, dict):
                by_mod = {}
                effort_sec["by_model"] = by_mod

            if effort is None:
                by_mod.pop(model_spec, None)
                if not by_mod:
                    effort_sec.pop("by_model", None)
                if not effort_sec:
                    data.pop("effort", None)
            else:
                by_mod[model_spec] = effort

            fd, tmp_path = tempfile.mkstemp(dir=target_path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    tomli_w.dump(data, f)
                Path(tmp_path).replace(target_path)
            except BaseException:
                with contextlib.suppress(OSError):
                    Path(tmp_path).unlink()
                raise
    except (OSError, tomllib.TOMLDecodeError, TypeError, ValueError):
        logger.exception("Could not save reasoning effort preference for %s", model_spec)
        return False
    return True


def clear_effort_for_model(model_spec: str, config_path: Path | None = None) -> bool:
    """Remove reasoning effort entry for model_spec from [effort.by_model] in config.toml."""
    return save_effort_for_model(model_spec, None, config_path=config_path)


def load_effort_for_model(model_spec: str, config_path: Path | None = None) -> str | None:
    """Load persisted reasoning effort for a model from [effort.by_model] in config.toml."""
    data = read_config_toml(config_path)
    by_mod = data.get("effort", {}).get("by_model", {})
    if isinstance(by_mod, dict):
        val = by_mod.get(model_spec)
        return str(val).strip() if isinstance(val, str) and val.strip() else None
    return None


def save_recent_agent(agent_name: str, config_path: Path | None = None) -> bool:
    """Persist recent agent selection to [agents].recent in config.toml."""
    return _save_toml_field("agents", "recent", agent_name, config_path)


def load_recent_agent(config_path: Path | None = None) -> str | None:
    """Load [agents].recent from config.toml."""
    data = read_config_toml(config_path)
    val = data.get("agents", {}).get("recent")
    return str(val).strip() if isinstance(val, str) and val.strip() else None


def save_default_agent(agent_name: str, config_path: Path | None = None) -> bool:
    """Persist default agent selection to [agents].default in config.toml."""
    return _save_toml_field("agents", "default", agent_name, config_path)


def clear_default_agent(config_path: Path | None = None) -> bool:
    """Remove default agent entry from [agents].default in config.toml."""
    target_path = config_path or CONFIG_PATH
    if not target_path.exists():
        return True
    try:
        with _config_write_lock:
            with target_path.open("rb") as f:
                data = tomllib.load(f)
            agents_sec = data.get("agents")
            if not isinstance(agents_sec, dict) or "default" not in agents_sec:
                return True
            del agents_sec["default"]

            fd, tmp_path = tempfile.mkstemp(dir=target_path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    tomli_w.dump(data, f)
                Path(tmp_path).replace(target_path)
            except BaseException:
                with contextlib.suppress(OSError):
                    Path(tmp_path).unlink()
                raise
    except (OSError, tomllib.TOMLDecodeError, TypeError, ValueError):
        logger.exception("Could not clear default agent preference")
        return False
    return True


def load_default_agent(config_path: Path | None = None) -> str | None:
    """Load [agents].default from config.toml, falling back to [agents].recent."""
    data = read_config_toml(config_path)
    agents_sec = data.get("agents", {})
    val = agents_sec.get("default")
    if isinstance(val, str) and val.strip():
        return val.strip()
    recent = agents_sec.get("recent")
    if isinstance(recent, str) and recent.strip():
        return recent.strip()
    return None



def save_theme_preference(theme: str, config_path: Path | None = None) -> bool:
    """Persist theme preference to [ui].theme in config.toml."""
    return _save_toml_field("ui", "theme", theme, config_path)


def load_theme_preference(config_path: Path | None = None) -> str:
    """Load theme preference from [ui].theme in config.toml, defaulting to 'opscode-dark'."""
    data = read_config_toml(config_path)
    val = data.get("ui", {}).get("theme")
    if isinstance(val, str) and val.strip():
        return val.strip()
    return "opscode-dark"

