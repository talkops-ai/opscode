from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, TypedDict, cast

from dcoder.config.paths import CONFIG_PATH as DEFAULT_CONFIG_PATH

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

logger = logging.getLogger("dcoder")


def _normalize_provider_configs(
    providers: dict[str, Any],
) -> dict[str, SandboxProviderConfig]:
    normalized: dict[str, SandboxProviderConfig] = {}
    for name, provider in providers.items():
        if not isinstance(provider, dict):
            logger.warning(
                "Sandbox provider '%s' is not a table (%s); ignoring it",
                name,
                type(provider).__name__,
            )
            continue
        normalized[name] = cast("SandboxProviderConfig", provider)
    return normalized


class SandboxProviderConfig(TypedDict, total=False):
    class_path: str
    working_dir: str
    package: str
    supports_sandbox_id: bool
    supports_snapshot_name: bool
    params: dict[str, Any]


@dataclass(frozen=True)
class SandboxConfig:
    default: str | None = None
    providers: Mapping[str, SandboxProviderConfig] = field(default_factory=dict)
    parse_error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.providers, MappingProxyType):
            object.__setattr__(self, "providers", MappingProxyType(self.providers))

    @classmethod
    def load(cls, config_path: Path | None = None) -> SandboxConfig:
        if config_path is None:
            config_path = DEFAULT_CONFIG_PATH

        if not config_path.exists():
            return cls()

        try:
            with config_path.open("rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            logger.warning(
                "Config file %s has invalid TOML syntax: %s. Ignoring sandbox config.",
                config_path,
                e,
            )
            return cls(parse_error=f"invalid TOML syntax: {e}")
        except (PermissionError, OSError) as e:
            logger.warning("Could not read config file %s: %s", config_path, e)
            return cls(parse_error=f"could not read config file: {e}")

        section = data.get("sandboxes", {})
        if not isinstance(section, dict):
            logger.warning("[sandboxes] is not a table; ignoring sandbox config")
            return cls(parse_error="[sandboxes] is not a table")

        providers = section.get("providers", {})
        if not isinstance(providers, dict):
            logger.warning(
                "[sandboxes.providers] is not a table; ignoring sandbox providers"
            )
            providers = {}

        config = cls(
            default=section.get("default"),
            providers=_normalize_provider_configs(providers),
        )
        config._validate()
        return config

    def _validate(self) -> None:
        for name, provider in self.providers.items():
            class_path = provider.get("class_path")
            if not class_path:
                logger.warning(
                    "Sandbox provider '%s' is missing required 'class_path'", name
                )
            elif ":" not in class_path:
                logger.warning(
                    "Sandbox provider '%s' has invalid class_path '%s': "
                    "must be in module.path:ClassName format",
                    name,
                    class_path,
                )
            params = provider.get("params")
            if params is not None and not isinstance(params, dict):
                logger.warning(
                    "Sandbox provider '%s' has non-table 'params' (%s); ignoring it",
                    name,
                    type(params).__name__,
                )

    def get_params(self, provider_name: str) -> dict[str, Any]:
        provider = self.providers.get(provider_name)
        if not provider:
            return {}
        params = provider.get("params", {})
        return dict(params) if isinstance(params, dict) else {}
