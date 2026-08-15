"""Reasoning effort support for `/effort` and model configuration.

Supported levels and defaults come from LangChain model profiles. Provider
integrations translate the standard `reasoning_effort` constructor parameter
into their native request shapes.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from opscode.model.config import ModelSpec, get_model_profile

logger = logging.getLogger(__name__)


def _model_profile(
    model_spec: str | None, *, cli_override: dict[str, Any] | None = None
) -> Mapping[str, Any] | None:
    """Return the reasoning-capable profile for `model_spec`."""
    if not model_spec:
        return None
    entry = get_model_profile(model_spec)
    profile = cli_override if entry is None else (entry.get("profile") if isinstance(entry, dict) else None)
    if profile is None:
        return None
    if not isinstance(profile, Mapping):
        return None
    reasoning_output = profile.get("reasoning_output")
    if reasoning_output is not True:
        return None
    return profile


def supported_efforts_for_model(
    model_spec: str | None, *, cli_override: dict[str, Any] | None = None
) -> tuple[str, ...]:
    """Return the ordered reasoning effort levels supported by `model_spec`."""
    profile = _model_profile(model_spec, cli_override=cli_override)
    if profile is None or "reasoning_effort_levels" not in profile:
        return ("high", "medium", "low")
    levels = profile["reasoning_effort_levels"]
    if not isinstance(levels, list):
        return ("high", "medium", "low")
    return tuple(str(lvl) for lvl in levels)


def default_effort_for_model(
    model_spec: str | None, *, cli_override: dict[str, Any] | None = None
) -> str | None:
    """Return the profile's reasoning effort default independently of its levels."""
    profile = _model_profile(model_spec, cli_override=cli_override)
    if profile is None:
        return None
    default = profile.get("reasoning_effort_default")
    if default is not None:
        return str(default)
    return "medium"


def is_effort_supported_for_model(
    model_spec: str, effort: str, *, cli_override: dict[str, Any] | None = None
) -> bool:
    """Return whether `effort` is a supported level for `model_spec`."""
    return effort in supported_efforts_for_model(model_spec, cli_override=cli_override)


def _str_or_none(value: object, *, key: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return None


def _effort_paths(provider: str) -> tuple[tuple[str, ...], ...]:
    if provider == "openai":
        return (("reasoning", "effort"), ("reasoning_effort",))
    if provider == "anthropic":
        return (
            ("effort",),
            ("reasoning_effort",),
            ("output_config", "effort"),
        )
    if provider == "google_genai":
        return (
            ("thinking_level",),
            ("reasoning_effort",),
            ("thinking_config", "thinking_level"),
        )
    return (("reasoning_effort",),)


def _path_is_present(model_params: Mapping[str, Any], path: tuple[str, ...]) -> bool:
    if len(path) == 1:
        return path[0] in model_params
    nested = model_params.get(path[0])
    return isinstance(nested, Mapping) and path[1] in nested


def has_explicit_effort_model_params(
    model_spec: str | None, model_params: dict[str, Any] | None
) -> bool:
    """Return whether canonical or native effort parameters are present."""
    if not model_spec or not model_params:
        return False
    parsed = ModelSpec.try_parse(model_spec)
    provider = parsed.provider if parsed is not None else ""
    return any(_path_is_present(model_params, path) for path in _effort_paths(provider))


def current_effort_from_model_params(
    model_spec: str | None, model_params: dict[str, Any] | None
) -> str | None:
    """Read canonical or native effort settings using integration precedence."""
    if not model_spec or not model_params:
        return None
    parsed = ModelSpec.try_parse(model_spec)
    provider = parsed.provider if parsed is not None else ""

    if provider == "openai":
        reasoning = model_params.get("reasoning")
        if isinstance(reasoning, Mapping) and "effort" in reasoning:
            return _str_or_none(reasoning["effort"], key="reasoning.effort")
    elif provider == "anthropic" and "effort" in model_params:
        effort = model_params["effort"]
        if effort is not None:
            return _str_or_none(effort, key="effort")
    elif provider == "google_genai" and "thinking_level" in model_params:
        effort = model_params["thinking_level"]
        if effort is not None:
            return _str_or_none(effort, key="thinking_level")

    return _str_or_none(model_params.get("reasoning_effort"), key="reasoning_effort")


def _remove_nested_key(params: dict[str, Any], container: str, key: str) -> None:
    nested = params.get(container)
    if not isinstance(nested, Mapping):
        return
    remaining = dict(nested)
    remaining.pop(key, None)
    if remaining:
        params[container] = remaining
    else:
        params.pop(container, None)


def without_effort_model_params(
    model_spec: str, existing: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Remove canonical and native effort settings without changing siblings."""
    if not existing:
        return None
    cleaned = dict(existing)
    cleaned.pop("reasoning_effort", None)

    parsed = ModelSpec.try_parse(model_spec)
    provider = parsed.provider if parsed is not None else ""
    if provider == "openai":
        _remove_nested_key(cleaned, "reasoning", "effort")
    elif provider == "anthropic":
        cleaned.pop("effort", None)
        _remove_nested_key(cleaned, "output_config", "effort")
    elif provider == "google_genai":
        cleaned.pop("thinking_level", None)
        _remove_nested_key(cleaned, "thinking_config", "thinking_level")
    return cleaned or None


def with_effort_model_params(
    model_spec: str, existing: dict[str, Any] | None, effort: str
) -> dict[str, Any]:
    """Replace existing effort settings with canonical and provider-native parameters."""
    updated = without_effort_model_params(model_spec, existing) or {}
    updated["reasoning_effort"] = effort

    parsed = ModelSpec.try_parse(model_spec)
    provider = parsed.provider if parsed is not None else ""
    eff_lower = effort.lower()

    if provider == "google_genai":
        updated["include_thoughts"] = True
        updated["thinking_level"] = eff_lower.upper()
        updated["thinking_budget"] = {
            "low": 1024,
            "medium": 2048,
            "high": 8192,
            "max": 16384,
        }.get(eff_lower, 4096)
    elif provider == "anthropic":
        budget = {
            "low": 1024,
            "medium": 4096,
            "high": 8192,
            "max": 16384,
        }.get(eff_lower, 4096)
        updated["thinking"] = {"type": "enabled", "budget_tokens": budget}
    elif provider == "openai":
        updated["reasoning"] = {"effort": eff_lower}

    return updated
