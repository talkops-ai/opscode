"""Model configuration structures and TOML loader for LLM providers."""

from __future__ import annotations

import json
import logging
import os
import tomllib
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, TypedDict, cast

from dcoder.config.settings import resolve_env_var
from dcoder.config.paths import CONFIG_PATH as DEFAULT_CONFIG_PATH
from dcoder.exceptions import ModelConfigError

logger = logging.getLogger("dcoder")

PROVIDER_API_KEY_ENV: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "azure_openai": "AZURE_OPENAI_API_KEY",
    "baseten": "BASETEN_API_KEY",
    "cohere": "COHERE_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
    "google_vertexai": "GOOGLE_CLOUD_PROJECT",
    "groq": "GROQ_API_KEY",
    "huggingface": "HUGGINGFACEHUB_API_TOKEN",
    "ibm": "WATSONX_APIKEY",
    "litellm": "LITELLM_API_KEY",
    "mistralai": "MISTRAL_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "perplexity": "PPLX_API_KEY",
    "together": "TOGETHER_API_KEY",
    "xai": "XAI_API_KEY",
}

PROVIDER_BASE_URL_ENV: dict[str, tuple[str, ...]] = {
    "anthropic": ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_URL"),
    "azure_openai": ("AZURE_OPENAI_ENDPOINT",),
    "baseten": ("BASETEN_BASE_URL", "BASETEN_API_BASE"),
    "cohere": ("CO_API_URL",),
    "deepseek": ("DEEPSEEK_API_BASE",),
    "fireworks": ("FIREWORKS_BASE_URL", "FIREWORKS_API_BASE"),
    "google_genai": ("GOOGLE_GEMINI_BASE_URL",),
    "groq": ("GROQ_BASE_URL", "GROQ_API_BASE"),
    "huggingface": ("HF_INFERENCE_ENDPOINT",),
    "ibm": ("WATSONX_URL",),
    "meta": ("MODEL_API_BASE",),
    "mistralai": ("MISTRAL_BASE_URL",),
    "nvidia": ("NVIDIA_BASE_URL",),
    "openai": ("OPENAI_BASE_URL", "OPENAI_API_BASE"),
    "openrouter": ("OPENROUTER_API_BASE",),
    "perplexity": ("PERPLEXITY_BASE_URL",),
    "together": ("TOGETHER_API_BASE",),
    "xai": ("XAI_API_BASE",),
}

PROVIDER_CUSTOM_HEADERS_ENV: dict[str, str] = {
    "anthropic": "ANTHROPIC_CUSTOM_HEADERS",
}

IMPLICIT_AUTH_PROVIDERS: set[str] = {"google_vertexai"}
NO_AUTH_REQUIRED_PROVIDERS: set[str] = {"ollama"}
OPTIONAL_AUTH_ENV: dict[str, str] = {"ollama": "OLLAMA_API_KEY"}


class ProviderAuthState(StrEnum):
    CONFIGURED = "configured"
    MISSING = "missing"
    IMPLICIT = "implicit"
    NOT_REQUIRED = "not_required"
    MANAGED = "managed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderAuthStatus:
    state: str
    provider: str
    env_var: str | None = None
    detail: str = ""

    def as_legacy_bool(self) -> bool | None:
        """True=configured, False=missing, None=unknown."""
        if self.state in (
            ProviderAuthState.CONFIGURED,
            ProviderAuthState.IMPLICIT,
            ProviderAuthState.NOT_REQUIRED,
            ProviderAuthState.MANAGED,
        ):
            return True
        if self.state == ProviderAuthState.MISSING:
            return False
_SUPPRESSED_WARNINGS: set[str] = set()


def is_warning_suppressed(key: str) -> bool:
    """Check if a warning key is suppressed."""
    return key in _SUPPRESSED_WARNINGS


def suppress_warning(key: str) -> bool:
    """Suppress a warning key."""
    _SUPPRESSED_WARNINGS.add(key)
    return True


def unsuppress_warning(key: str) -> bool:
    """Unsuppress a warning key."""
    _SUPPRESSED_WARNINGS.discard(key)
    return True


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model: str

    def __post_init__(self):
        if not self.provider:
            raise ValueError("Provider cannot be empty")
        if not self.model:
            raise ValueError("Model cannot be empty")

    @classmethod
    def parse(cls, spec: str) -> "ModelSpec":
        if ":" not in spec:
            raise ValueError(f"Invalid spec '{spec}': must be provider:model format")
        provider, model = spec.split(":", 1)
        return cls(provider=provider.strip(), model=model.strip())

    @classmethod
    def try_parse(cls, spec: str) -> "ModelSpec | None":
        try:
            return cls.parse(spec)
        except ValueError:
            return None

    def __str__(self) -> str:
        return f"{self.provider}:{self.model}"


class ModelProfile(TypedDict, total=False):
    name: str
    max_input_tokens: int
    max_output_tokens: int
    text_inputs: bool
    image_inputs: bool
    audio_inputs: bool
    pdf_inputs: bool
    video_inputs: bool
    reasoning_output: bool
    tool_calling: bool
    structured_output: bool
    status: str | None


class ModelProfileEntry(TypedDict):
    profile: ModelProfile
    overridden_keys: set[str]


class ProviderConfig(TypedDict, total=False):
    enabled: bool
    models: list[str]
    api_key_env: str
    base_url: str
    base_url_env: str
    class_path: str
    params: dict[str, Any]
    profile: dict[str, Any]
    display_name: str


_default_config_cache: ModelConfig | None = None


@dataclass(frozen=True)
class ModelConfig:
    default_model: str | None = None
    recent_model: str | None = None
    providers: Mapping[str, ProviderConfig] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.providers, MappingProxyType):
            object.__setattr__(self, "providers", MappingProxyType(dict(self.providers)))

    @classmethod
    def load(cls, config_path: Path | None = None) -> "ModelConfig":
        """Load and cache model config from TOML."""
        global _default_config_cache
        is_default = config_path is None
        if is_default and _default_config_cache is not None:
            return _default_config_cache

        target_path = config_path or DEFAULT_CONFIG_PATH
        if not target_path.exists():
            fallback = cls()
            if is_default:
                _default_config_cache = fallback
            return fallback

        try:
            with target_path.open("rb") as f:
                data = tomllib.load(f)
        except Exception as e:
            logger.warning("Invalid TOML in %s: %s. Ignoring config.", target_path, e)
            fallback = cls()
            if is_default:
                _default_config_cache = fallback
            return fallback

        models_section = data.get("models", {})
        config = cls(
            default_model=models_section.get("default"),
            recent_model=models_section.get("recent"),
            providers=models_section.get("providers", {}),
        )
        if is_default:
            _default_config_cache = config
        return config

    @classmethod
    def _clear_cache(cls):
        global _default_config_cache
        _default_config_cache = None

    def is_provider_enabled(self, provider: str) -> bool:
        provider_config = self.providers.get(provider)
        if provider_config is None:
            return True
        return provider_config.get("enabled", True)

    def get_kwargs(self, provider: str, *, model_name: str | None = None) -> dict[str, Any]:
        provider_config = self.providers.get(provider)
        if not provider_config:
            return {}
        params = dict(provider_config.get("params", {}))

        if model_name and isinstance(params.get(model_name), dict):
            model_params = params.pop(model_name)
            params = {k: v for k, v in params.items() if not isinstance(v, dict)}
            params.update(model_params)
        else:
            params = {k: v for k, v in params.items() if not isinstance(v, dict)}

        return params

    def get_base_url(self, provider: str) -> str | None:
        provider_config = self.providers.get(provider)
        if not provider_config:
            return None
        base_url_env = provider_config.get("base_url_env")
        if base_url_env:
            val = resolve_env_var(base_url_env)
            if val:
                return val
        return provider_config.get("base_url")

    def get_base_url_env(self, provider: str) -> str | None:
        provider_config = self.providers.get(provider)
        if not provider_config:
            return None
        return provider_config.get("base_url_env")

    def get_api_key_env(self, provider: str) -> str | None:
        provider_config = self.providers.get(provider)
        if not provider_config:
            return None
        return provider_config.get("api_key_env")

    def get_class_path(self, provider: str) -> str | None:
        provider_config = self.providers.get(provider)
        if not provider_config:
            return None
        return provider_config.get("class_path")

    def get_profile_overrides(self, provider: str, *, model_name: str | None = None) -> dict[str, Any]:
        provider_config = self.providers.get(provider)
        if not provider_config:
            return {}
        profile = dict(provider_config.get("profile", {}))
        if model_name and isinstance(profile.get(model_name), dict):
            model_profile = profile.pop(model_name)
            profile = {k: v for k, v in profile.items() if not isinstance(v, dict)}
            profile.update(model_profile)
        else:
            profile = {k: v for k, v in profile.items() if not isinstance(v, dict)}
        return profile


_PROVIDER_DEPENDENCIES: dict[str, tuple[str, str]] = {
    "anthropic": ("langchain_anthropic", "anthropic"),
    "azure_openai": ("langchain_openai", "openai"),
    "baseten": ("langchain_baseten", "baseten"),
    "bedrock": ("langchain_aws", "bedrock"),
    "cohere": ("langchain_cohere", "cohere"),
    "deepseek": ("langchain_deepseek", "deepseek"),
    "fireworks": ("langchain_fireworks", "fireworks"),
    "google_genai": ("langchain_google_genai", "google-genai"),
    "google_vertexai": ("langchain_google_vertexai", "vertex"),
    "groq": ("langchain_groq", "groq"),
    "huggingface": ("langchain_huggingface", "huggingface"),
    "ibm": ("langchain_ibm", "ibm"),
    "litellm": ("langchain_litellm", "litellm"),
    "meta": ("langchain_meta", "meta"),
    "mistralai": ("langchain_mistralai", "mistralai"),
    "nvidia": ("langchain_nvidia_ai_endpoints", "nvidia"),
    "ollama": ("langchain_ollama", "ollama"),
    "openai": ("langchain_openai", "openai"),
    "openrouter": ("langchain_openrouter", "openrouter"),
    "perplexity": ("langchain_perplexity", "perplexity"),
    "together": ("langchain_together", "together"),
    "xai": ("langchain_xai", "xai"),
}


def provider_install_extra(provider: str) -> str | None:
    """Return the extra package name required for provider."""
    dep = _PROVIDER_DEPENDENCIES.get(provider)
    return dep[1] if dep else None


def is_provider_package_installed(provider: str) -> bool:
    """Check if the provider's Python integration package is installed."""
    import importlib.util

    dep = _PROVIDER_DEPENDENCIES.get(provider)
    if dep is None:
        return True
    try:
        return importlib.util.find_spec(dep[0]) is not None
    except Exception:
        return False


def get_credential_env_var(provider: str) -> str | None:
    config = ModelConfig.load()
    custom_env = config.get_api_key_env(provider)
    if custom_env:
        return custom_env
    return PROVIDER_API_KEY_ENV.get(provider)


def get_base_url_env_vars(provider: str) -> tuple[str, ...]:
    """Return all base-URL env var names for a provider (config-declared or built-in)."""
    config = ModelConfig.load()
    config_env = config.get_base_url_env(provider)
    if config_env:
        return (config_env,)
    return PROVIDER_BASE_URL_ENV.get(provider, ())


def get_base_url_env_var(provider: str) -> str | None:
    """Return the canonical base-URL env var name for a provider."""
    env_vars = get_base_url_env_vars(provider)
    return env_vars[0] if env_vars else None


def _apply_stored_base_url(provider: str, base_url: str | None) -> None:
    """Reconcile a provider's base-URL env vars with stored/resolved endpoint."""
    canonical = get_base_url_env_var(provider)
    names = set(PROVIDER_BASE_URL_ENV.get(provider, ()))
    if canonical:
        names.add(canonical)
    if not names:
        return
    for name in names:
        if base_url and name == canonical:
            os.environ[name] = base_url
        else:
            os.environ.pop(name, None)

    custom_headers_env = PROVIDER_CUSTOM_HEADERS_ENV.get(provider)
    if custom_headers_env and not base_url:
        os.environ.pop(custom_headers_env, None)


def get_provider_auth_status(provider: str) -> ProviderAuthStatus:
    config = ModelConfig.load()
    if not config.is_provider_enabled(provider):
        return ProviderAuthStatus(state=ProviderAuthState.MISSING, provider=provider, detail="Provider disabled in config")

    if provider in NO_AUTH_REQUIRED_PROVIDERS:
        return ProviderAuthStatus(state=ProviderAuthState.NOT_REQUIRED, provider=provider, detail="local provider")

    if provider in IMPLICIT_AUTH_PROVIDERS:
        return ProviderAuthStatus(state=ProviderAuthState.IMPLICIT, provider=provider, detail="implicit auth")

    class_path = config.get_class_path(provider)
    if class_path and not config.get_api_key_env(provider):
        return ProviderAuthStatus(state=ProviderAuthState.MANAGED, provider=provider, detail="custom auth")

    env_var = get_credential_env_var(provider)
    if env_var:
        val = resolve_env_var(env_var)
        if val:
            return ProviderAuthStatus(state=ProviderAuthState.CONFIGURED, provider=provider, env_var=env_var)

    if provider == "google_genai":
        if resolve_env_var("GEMINI_API_KEY"):
            return ProviderAuthStatus(state=ProviderAuthState.CONFIGURED, provider=provider, env_var="GEMINI_API_KEY")
        if resolve_env_var("GOOGLE_CLOUD_PROJECT"):
            return ProviderAuthStatus(state=ProviderAuthState.CONFIGURED, provider=provider, env_var="GOOGLE_CLOUD_PROJECT")
        use_vertex = resolve_env_var("GOOGLE_GENAI_USE_VERTEXAI")
        if use_vertex and use_vertex.lower() in ("true", "1"):
            return ProviderAuthStatus(state=ProviderAuthState.CONFIGURED, provider=provider, env_var="GOOGLE_GENAI_USE_VERTEXAI")

    optional_env = OPTIONAL_AUTH_ENV.get(provider)
    if optional_env and resolve_env_var(optional_env):
        return ProviderAuthStatus(state=ProviderAuthState.CONFIGURED, provider=provider, env_var=optional_env)

    if not env_var:
        return ProviderAuthStatus(state=ProviderAuthState.UNKNOWN, provider=provider, detail="credentials unknown")

    return ProviderAuthStatus(state=ProviderAuthState.MISSING, provider=provider, env_var=env_var, detail=f"{env_var} is not set")


def has_provider_credentials(provider: str) -> bool | None:
    return get_provider_auth_status(provider).as_legacy_bool()


def apply_stored_credentials(provider: str) -> bool:
    """Export stored provider API key and env vars from ~/.dcoder/.env to os.environ.

    LangChain model factories read credentials from process env vars.
    Returns True if credentials were set/found in environment, False otherwise.
    """
    from dcoder.config.settings import _load_dotenv, resolve_env_var

    _load_dotenv(refresh_loaded=True)

    config = ModelConfig.load()
    applied = False

    # 1. Export provider API key onto canonical env var name
    env_var = get_credential_env_var(provider)
    if env_var:
        key_val = resolve_env_var(env_var)
        if not key_val and provider == "google_genai":
            key_val = resolve_env_var("GEMINI_API_KEY")
        if key_val:
            os.environ[env_var] = key_val
            applied = True

    # 2. Reconcile base URL env vars
    base_url = config.get_base_url(provider)
    _apply_stored_base_url(provider, base_url)
    if base_url:
        applied = True

    # 3. Export provider-specific environment settings if present in environment
    if provider == "google_genai":
        use_vertex = resolve_env_var("GOOGLE_GENAI_USE_VERTEXAI")
        if use_vertex is not None:
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = use_vertex
        project = resolve_env_var("GOOGLE_CLOUD_PROJECT")
        if project is not None:
            os.environ["GOOGLE_CLOUD_PROJECT"] = project

    return applied


PROVIDER_ENV_MAPPINGS: dict[str, list[str]] = {
    "openai": ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_ORGANIZATION"],
    "anthropic": ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"],
    "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_CLOUD_PROJECT"],
    "google_genai": ["GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_CLOUD_PROJECT"],
    "groq": ["GROQ_API_KEY", "GROQ_BASE_URL"],
    "deepseek": ["DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL"],
    "tavily": ["TAVILY_API_KEY"],
    "mistralai": ["MISTRAL_API_KEY"],
    "fireworks": ["FIREWORKS_API_KEY"],
    "together": ["TOGETHER_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "xai": ["XAI_API_KEY"],
}

PROVIDER_SETTINGS_FIELDS: dict[str, str] = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "google": "google_api_key",
    "google_genai": "google_api_key",
    "groq": "groq_api_key",
    "deepseek": "deepseek_api_key",
    "tavily": "tavily_api_key",
}


def revoke_provider_credentials(provider: str | None = None, settings: Any | None = None) -> list[str]:
    """Revoke stored credentials for a specified provider, or all providers if provider is None or 'all'.

    Clears process environment variables, settings instance fields, and removes
    credential lines from ~/.dcoder/.env file.

    Returns a list of provider names whose credentials were revoked.
    """
    from dcoder.config.paths import DATA_DIR, GLOBAL_ENV_PATH

    target_providers: list[str] = []
    if provider and provider.lower() not in ("all", "*", ""):
        prov = provider.lower()
        if prov in PROVIDER_ENV_MAPPINGS:
            target_providers.append(prov)
        else:
            for p_key in PROVIDER_ENV_MAPPINGS:
                if prov in p_key or p_key in prov:
                    target_providers.append(p_key)
            if not target_providers:
                target_providers.append(prov)
    else:
        target_providers = list(PROVIDER_ENV_MAPPINGS.keys())

    keys_to_remove: set[str] = set()
    revoked_providers: set[str] = set()

    for prov in target_providers:
        env_vars = PROVIDER_ENV_MAPPINGS.get(prov, [f"{prov.upper()}_API_KEY"])
        found_active = False
        for ev in env_vars:
            keys_to_remove.add(ev)
            if os.environ.get(ev):
                found_active = True
                os.environ.pop(ev, None)

        field = PROVIDER_SETTINGS_FIELDS.get(prov)
        if settings and field and hasattr(settings, field):
            if getattr(settings, field, None) is not None:
                found_active = True
                setattr(settings, field, None)

        if found_active:
            revoked_providers.add(prov)

    # Clean disk env files
    cred_files = [
        GLOBAL_ENV_PATH,
    ]
    for cfile in cred_files:
        if cfile.is_file():
            try:
                content = cfile.read_text(encoding="utf-8")
                lines = content.splitlines()
                new_lines = []
                file_changed = False
                for line in lines:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        new_lines.append(line)
                        continue
                    key_part = stripped.removeprefix("export ").split("=", 1)[0].strip()
                    if key_part in keys_to_remove:
                        file_changed = True
                        for prov_name, ev_list in PROVIDER_ENV_MAPPINGS.items():
                            if key_part in ev_list:
                                revoked_providers.add(prov_name)
                        continue
                    new_lines.append(line)
                if file_changed:
                    non_empty = [l for l in new_lines if l.strip() and not l.strip().startswith("#")]
                    if non_empty:
                        cfile.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                    else:
                        cfile.unlink(missing_ok=True)
            except Exception as exc:
                logger.debug("Failed stripping credentials from %s: %s", cfile, exc)

    return sorted(list(revoked_providers))


# ── Detailed Model Catalog & Profiles ────────────────────

MODEL_PROFILES: dict[str, ModelProfile] = {
    # OpenRouter Models
    "openrouter:moonshotai/kimi-k3": {
        "name": "Kimi K3",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 1_000_000,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openrouter:moonshotai/kimi-k2.7-code": {
        "name": "Kimi K2.7 Code",
        "max_input_tokens": 200_000,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": False,
        "audio_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openrouter:minimax/minimax-m3": {
        "name": "MiniMax-M3",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openrouter:qwen/qwen3.7-plus": {
        "name": "Qwen 3.7 Plus",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openrouter:deepseek/deepseek-v4-pro": {
        "name": "DeepSeek V4 Pro",
        "max_input_tokens": 128_000,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": False,
        "audio_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openrouter:deepseek/deepseek-v4-flash": {
        "name": "DeepSeek V4 Flash",
        "max_input_tokens": 128_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": False,
        "audio_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openrouter:anthropic/claude-sonnet-5": {
        "name": "Claude Sonnet 5",
        "max_input_tokens": 200_000,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openrouter:anthropic/claude-opus-4.7": {
        "name": "Claude Opus 4.7",
        "max_input_tokens": 200_000,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openrouter:google/gemini-3.6-flash": {
        "name": "Gemini 3.6 Flash",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    # OpenAI Models
    "openai:gpt-5.4": {
        "name": "GPT-5.4",
        "max_input_tokens": 400_000,
        "max_output_tokens": 128_000,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openai:gpt-5.4-mini": {
        "name": "GPT-5.4 mini",
        "max_input_tokens": 400_000,
        "max_output_tokens": 128_000,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openai:gpt-5.4-pro": {
        "name": "GPT-5.4 Pro",
        "max_input_tokens": 400_000,
        "max_output_tokens": 128_000,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openai:gpt-5.5": {
        "name": "GPT-5.5",
        "max_input_tokens": 400_000,
        "max_output_tokens": 128_000,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openai:gpt-5.5-pro": {
        "name": "GPT-5.5 Pro",
        "max_input_tokens": 400_000,
        "max_output_tokens": 128_000,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openai:gpt-5.6-luna": {
        "name": "GPT-5.6 Luna",
        "max_input_tokens": 400_000,
        "max_output_tokens": 128_000,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openai:gpt-4o": {
        "name": "GPT-4o",
        "max_input_tokens": 128_000,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openai:gpt-4o-mini": {
        "name": "GPT-4o Mini",
        "max_input_tokens": 128_000,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "pdf_inputs": False,
        "video_inputs": False,
        "reasoning_output": False,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openai:o1": {
        "name": "o1",
        "max_input_tokens": 200_000,
        "max_output_tokens": 100_000,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "pdf_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "openai:o3-mini": {
        "name": "o3 Mini",
        "max_input_tokens": 200_000,
        "max_output_tokens": 100_000,
        "text_inputs": True,
        "image_inputs": False,
        "audio_inputs": False,
        "pdf_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    # Anthropic Direct
    "anthropic:claude-opus-4-7": {
        "name": "Claude Opus 4.7",
        "max_input_tokens": 200_000,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "pdf_inputs": True,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "anthropic:claude-opus-4-8": {
        "name": "Claude Opus 4.8",
        "max_input_tokens": 200_000,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "pdf_inputs": True,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "anthropic:claude-sonnet-5": {
        "name": "Claude Sonnet 5",
        "max_input_tokens": 200_000,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "pdf_inputs": True,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    # Google GenAI Direct
    "google_genai:gemini-3.1-pro-preview": {
        "name": "Gemini 3.1 Pro Preview",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "google_genai:gemini-3.6-flash": {
        "name": "Gemini 3.6 Flash",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "google_genai:gemini-3.5-flash": {
        "name": "Gemini 3.5 Flash",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "google_genai:gemini-3.5-flash-lite": {
        "name": "Gemini 3.5 Flash Lite",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "google_genai:gemini-3.1-pro-preview": {
        "name": "Gemini 3.1 Pro Preview",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "google_genai:gemini-3.1-flash-lite": {
        "name": "Gemini 3.1 Flash Lite",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "google_genai:gemini-3.1-flash-lite-preview": {
        "name": "Gemini 3.1 Flash Lite Preview",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "google_genai:gemini-3-flash-preview": {
        "name": "Gemini 3 Flash Preview",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "google_genai:gemini-3-pro-preview": {
        "name": "Gemini 3 Pro Preview",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "pdf_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    # Anthropic Direct
    "anthropic:claude-3-5-sonnet-20241022": {
        "name": "Claude 3.5 Sonnet",
        "max_input_tokens": 200_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "anthropic:claude-sonnet-4-20250514": {
        "name": "Claude Sonnet 4",
        "max_input_tokens": 200_000,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    # Google GenAI Direct
    "google_genai:gemini-2.0-flash": {
        "name": "Gemini 2.0 Flash",
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": True,
        "video_inputs": True,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    # Ollama Local
    "ollama:deepseek-v4-flash:cloud": {
        "name": "DeepSeek V4 Flash",
        "max_input_tokens": 128_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": False,
        "audio_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    "ollama:llama3.1": {
        "name": "Llama 3.1",
        "max_input_tokens": 128_000,
        "max_output_tokens": 4_096,
        "text_inputs": True,
        "image_inputs": False,
        "audio_inputs": False,
        "video_inputs": False,
        "reasoning_output": False,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    # xAI
    "xai:grok-4.5": {
        "name": "Grok 4.5",
        "max_input_tokens": 131_072,
        "max_output_tokens": 16_384,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
    # Meta
    "meta:muse-spark-1.1": {
        "name": "Muse Spark 1.1",
        "max_input_tokens": 128_000,
        "max_output_tokens": 8_192,
        "text_inputs": True,
        "image_inputs": True,
        "audio_inputs": False,
        "video_inputs": False,
        "reasoning_output": True,
        "tool_calling": True,
        "structured_output": True,
        "status": None,
    },
}

AVAILABLE_MODELS: dict[str, list[tuple[str, str]]] = {
    "openrouter": [
        ("google/gemini-3.5-flash", "Gemini 3.5 Flash"),
        ("google/gemini-3.5-flash-lite", "Gemini 3.5 Flash Lite"),
        ("anthropic/claude-opus-4.6", "Claude Opus 4.6"),
        ("anthropic/claude-opus-4.7", "Claude Opus 4.7"),
        ("anthropic/claude-opus-4.7-fast", "Claude Opus 4.7 (Fast)"),
        ("anthropic/claude-opus-4.8", "Claude Opus 4.8"),
        ("anthropic/claude-sonnet-5", "Claude Sonnet 5"),
        ("deepseek/deepseek-v4-flash", "DeepSeek V4 Flash"),
        ("deepseek/deepseek-v4-pro", "DeepSeek V4 Pro"),
        ("moonshotai/kimi-k3", "Kimi K3"),
        ("moonshotai/kimi-k2.7-code", "Kimi K2.7 Code"),
        ("minimax/minimax-m3", "MiniMax-M3"),
        ("qwen/qwen3.7-plus", "Qwen 3.7 Plus"),
        ("nvidia/nemotron-3-ultra-550b-a55b", "Nemotron 3 Ultra"),
        ("openai/gpt-5.4", "GPT-5.4"),
        ("openai/gpt-5.4-mini", "GPT-5.4 mini"),
        ("openai/gpt-5.4-pro", "GPT-5.4 Pro"),
        ("openai/gpt-5.5", "GPT-5.5"),
        ("openrouter/fusion", "OpenRouter Fusion"),
        ("z-ai/glm-5.2", "GLM 5.2"),
    ],
    "openai_codex": [
        ("gpt-5.2", "GPT-5.2"),
        ("gpt-5.3-codex", "GPT-5.3 Codex"),
        ("gpt-5.4", "GPT-5.4"),
        ("gpt-5.4-mini", "GPT-5.4 mini"),
        ("gpt-5.5", "GPT-5.5"),
        ("gpt-5.6-luna", "GPT-5.6 Luna"),
        ("gpt-5.6-sol", "GPT-5.6 Sol"),
        ("gpt-5.6-terra", "GPT-5.6 Terra"),
    ],
    "openai": [
        ("gpt-5.4", "GPT-5.4"),
        ("gpt-5.4-mini", "GPT-5.4 mini"),
        ("gpt-5.4-pro", "GPT-5.4 Pro"),
        ("gpt-5.5", "GPT-5.5"),
        ("gpt-5.5-pro", "GPT-5.5 Pro"),
        ("gpt-5.6-luna", "GPT-5.6 Luna"),
        ("gpt-4o", "GPT-4o"),
        ("gpt-4o-mini", "GPT-4o Mini"),
        ("o1", "o1"),
        ("o3-mini", "o3 Mini"),
    ],
    "anthropic": [
        ("claude-opus-4-7", "Claude Opus 4.7"),
        ("claude-opus-4-8", "Claude Opus 4.8"),
        ("claude-sonnet-5", "Claude Sonnet 5"),
        ("claude-sonnet-4-20250514", "Claude Sonnet 4"),
        ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet"),
    ],
    "google_genai": [
        ("gemini-3.6-flash", "Gemini 3.6 Flash"),
        ("gemini-3.5-flash", "Gemini 3.5 Flash"),
        ("gemini-3.5-flash-lite", "Gemini 3.5 Flash Lite"),
        ("gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview"),
        ("gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite"),
        ("gemini-3.1-flash-lite-preview", "Gemini 3.1 Flash Lite Preview"),
        ("gemini-3-flash-preview", "Gemini 3 Flash Preview"),
        ("gemini-3-pro-preview", "Gemini 3 Pro Preview"),
        ("gemini-2.0-flash", "Gemini 2.0 Flash"),
        ("gemini-1.5-pro", "Gemini 1.5 Pro"),
    ],
    "baseten": [
        ("deepseek-ai/DeepSeek-V4-Pro", "DeepSeek V4 Pro"),
        ("moonshotai/Kimi-K2.7-Code", "Kimi K2.7 Code"),
        ("nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B", "Nemotron 3 Ultra"),
        ("zai-org/GLM-5.2", "GLM 5.2"),
    ],
    "fireworks": [
        ("accounts/fireworks/models/deepseek-v4-pro", "DeepSeek V4 Pro"),
        ("accounts/fireworks/models/glm-5p2", "GLM 5.2"),
        ("accounts/fireworks/models/kimi-k2p7-code", "Kimi K2.7 Code"),
        ("accounts/fireworks/models/minimax-m3", "MiniMax-M3"),
        ("accounts/fireworks/models/qwen3p7-plus", "Qwen 3.7 Plus"),
    ],
    "ollama": [
        ("deepseek-v4-flash:cloud", "DeepSeek V4 Flash"),
        ("deepseek-v4-pro:cloud", "DeepSeek V4 Pro"),
        ("glm-5.2:cloud", "GLM 5.2"),
        ("kimi-k2.7-code:cloud", "Kimi K2.7 Code"),
        ("minimax-m3:cloud", "MiniMax-M3"),
        ("llama3.1", "Llama 3.1"),
    ],
    "meta": [
        ("muse-spark-1.1", "Muse Spark 1.1"),
    ],
    "xai": [
        ("grok-4.5", "Grok 4.5"),
    ],
}

RECOMMENDED_SPECS: frozenset[str] = frozenset({
    "openrouter:google/gemini-3.5-flash",
    "openrouter:google/gemini-3.5-flash-lite",
    "openrouter:anthropic/claude-opus-4.6",
    "openrouter:anthropic/claude-opus-4.7",
    "openrouter:anthropic/claude-opus-4.7-fast",
    "openrouter:anthropic/claude-opus-4.8",
    "openrouter:anthropic/claude-sonnet-5",
    "openrouter:deepseek/deepseek-v4-flash",
    "openrouter:deepseek/deepseek-v4-pro",
    "openrouter:moonshotai/kimi-k3",
    "openrouter:moonshotai/kimi-k2.7-code",
    "openrouter:minimax/minimax-m3",
    "openrouter:qwen/qwen3.7-plus",
    "openrouter:openai/gpt-5.4",
    "openai_codex:gpt-5.4",
    "openai:gpt-5.4",
    "openai:gpt-5.4-mini",
    "openai:gpt-5.4-pro",
    "openai:gpt-5.5",
    "openai:gpt-5.5-pro",
    "openai:gpt-5.6-luna",
    "openai:gpt-4o",
    "anthropic:claude-opus-4-7",
    "anthropic:claude-opus-4-8",
    "anthropic:claude-sonnet-5",
    "google_genai:gemini-3.6-flash",
    "google_genai:gemini-3.5-flash",
    "google_genai:gemini-3.5-flash-lite",
    "google_genai:gemini-3.1-pro-preview",
    "google_genai:gemini-3.1-flash-lite",
    "google_genai:gemini-3.1-flash-lite-preview",
    "google_genai:gemini-3-flash-preview",
    "google_genai:gemini-3-pro-preview",
    "ollama:deepseek-v4-flash:cloud",
    "meta:muse-spark-1.1",
    "xai:grok-4.5",
})

PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "openrouter": "OpenRouter",
    "openai_codex": "OpenAI Codex",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google_genai": "Google GenAI",
    "baseten": "Baseten",
    "fireworks": "Fireworks",
    "ollama": "Ollama",
    "meta": "Meta",
    "xai": "xAI",
    "azure_openai": "Azure OpenAI",
    "deepseek": "DeepSeek",
    "mistralai": "Mistral",
}


def get_provider_display_name(provider: str) -> str:
    """Return human-readable display name for provider."""
    return PROVIDER_DISPLAY_NAMES.get(provider, provider.title())


def get_model_profile(spec: str) -> ModelProfileEntry | None:
    """Return model profile entry for specified provider:model string."""
    config = ModelConfig.load()
    if ":" in spec:
        provider, model_id = spec.split(":", 1)
    else:
        provider, model_id = "openai", spec

    base_profile: dict[str, Any] = dict(MODEL_PROFILES.get(spec, {}))
    overrides = config.get_profile_overrides(provider, model_name=model_id)

    overridden_keys: set[str] = set()
    for k, v in overrides.items():
        if k in base_profile and base_profile[k] != v:
            overridden_keys.add(k)
        base_profile[k] = v

    if not base_profile:
        base_profile = {
            "name": model_id,
            "max_input_tokens": 128_000,
            "max_output_tokens": 16_384,
            "text_inputs": True,
            "image_inputs": False,
            "audio_inputs": False,
            "video_inputs": False,
            "reasoning_output": False,
            "tool_calling": True,
            "structured_output": True,
            "status": None,
        }

    prof_dict: ModelProfile = cast(ModelProfile, base_profile)
    return {"profile": prof_dict, "overridden_keys": overridden_keys}


def get_available_models_list() -> list[tuple[str, str, str]]:
    """Return flat list of (spec, display_name, provider) tuples."""
    result: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    for provider, models in AVAILABLE_MODELS.items():
        for model_id, display_name in models:
            spec = f"{provider}:{model_id}"
            if spec not in seen:
                result.append((spec, display_name, provider))
                seen.add(spec)

    config = ModelConfig.load()
    for provider, pconfig in config.providers.items():
        if not config.is_provider_enabled(provider):
            continue
        models = pconfig.get("models", [])
        for model_id in models:
            spec = f"{provider}:{model_id}"
            if spec not in seen:
                result.append((spec, model_id, provider))
                seen.add(spec)

    return result


# ── Recent / Default model persistence ───────────────────

from dcoder.config.paths import STATE_DIR as _STATE_DIR, RECENT_MODELS_PATH as _RECENT_MODELS_FILE
_DEFAULT_MODEL_FILE = _STATE_DIR / "default_model.json"
_MAX_RECENT = 10


from dcoder.config.toml_config import (
    clear_default_model as clear_default_model,
    load_default_model as _toml_load_default_model,
    load_recent_model as _toml_load_recent_model,
    save_default_model as save_default_model,
    save_recent_model as save_recent_model,
)


def load_recent_models() -> list[str]:
    """Load the most-recently-used model specs (most recent first)."""
    try:
        if _RECENT_MODELS_FILE.exists():
            data = json.loads(_RECENT_MODELS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(s) for s in data[:_MAX_RECENT]]
            elif isinstance(data, dict) and isinstance(data.get("models"), list):
                return [str(s) for s in data["models"][:_MAX_RECENT]]
    except Exception:
        logger.debug("Failed to load recent models", exc_info=True)
    return []


def load_default_model() -> str | None:
    """Load the user's saved default model spec from config.toml or recent/state fallbacks."""
    default_spec = _toml_load_default_model()
    if default_spec:
        return default_spec
    recent_spec = _toml_load_recent_model()
    if recent_spec:
        return recent_spec
    try:
        if _DEFAULT_MODEL_FILE.exists():
            data = json.loads(_DEFAULT_MODEL_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "spec" in data:
                return str(data["spec"])
    except Exception:
        logger.debug("Failed to load default model fallback", exc_info=True)
    return None


def resolve_model_spec(spec: str | None) -> tuple[str, str]:
    """Resolve a model spec into (provider, model_id) tuple."""
    if not spec:
        spec = load_default_model() or "openrouter:moonshotai/kimi-k3"
    if ":" in spec:
        provider, model_id = spec.split(":", 1)
        return provider.lower(), model_id
    return "openai", spec



def format_token_count(count: int) -> str:
    """Format token count integer to human-readable string (e.g. 1.0M, 200k)."""
    if count >= 1_000_000:
        val = count / 1_000_000
        return f"{val:.1f}M" if val % 1 != 0 else f"{int(val)}M"
    if count >= 1_000:
        val = count / 1_000
        return f"{val:.1f}k" if val % 1 != 0 else f"{int(val)}k"
    return str(count)
