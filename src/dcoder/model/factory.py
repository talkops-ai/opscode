"""LLM Model construction factory and provider detection."""

import importlib
import logging
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel

from dcoder.config.settings import resolve_env_var, _get_settings
from dcoder.exceptions import (
    ModelConfigError,
    MissingCredentialsError,
    MissingProviderPackageError,
    NoCredentialsConfiguredError,
)
from dcoder.model.config import (
    ModelConfig,
    ModelSpec,
    get_credential_env_var,
    has_provider_credentials,
    IMPLICIT_AUTH_PROVIDERS,
)

logger = logging.getLogger("dcoder")

@dataclass(frozen=True)
class ModelResult:
    model: BaseChatModel
    model_name: str
    provider: str
    context_limit: int | None = None
    unsupported_modalities: frozenset[str] = frozenset()

    def apply_to_settings(self) -> None:
        """Commit this result's metadata to the global settings singleton."""
        s = _get_settings()
        s.model_name = self.model_name
        s.model_provider = self.provider
        s.model_context_limit = self.context_limit
        s.model_unsupported_modalities = self.unsupported_modalities


def detect_provider(model_name: str) -> str | None:
    """Infer provider from model name prefixes."""
    name_lower = model_name.lower()
    if name_lower.startswith(("claude-", "claude3")):
        return "anthropic"
    if name_lower.startswith(("gpt-", "o1-", "o3-", "chatgpt-")):
        return "openai"
    if name_lower.startswith("gemini"):
        return "google_genai"
    if name_lower.startswith("deepseek"):
        return "deepseek"
    if name_lower.startswith("groq"):
        return "groq"
    return None


def _get_default_model_spec() -> str:
    """Resolve the default model spec to use."""
    config = ModelConfig.load()

    def _has_creds(spec: str) -> bool:
        provider = spec.split(":", 1)[0] if ":" in spec else detect_provider(spec)
        return bool(provider and has_provider_credentials(provider))

    if config.default_model and _has_creds(config.default_model):
        return config.default_model
    if config.recent_model and _has_creds(config.recent_model):
        return config.recent_model

    # Auto-detect from credentials
    if has_provider_credentials("google_genai") is True:
        return "google_genai:gemini-3.5-flash-lite"
    if has_provider_credentials("anthropic") is True:
        return "anthropic:claude-3-5-sonnet-latest"
    if has_provider_credentials("openai") is True:
        return "openai:gpt-4o"
    if has_provider_credentials("groq") is True:
        return "groq:llama-3.3-70b-versatile"
    if has_provider_credentials("deepseek") is True:
        return "deepseek:deepseek-chat"

    raise NoCredentialsConfiguredError(
        "No credentials configured for any provider. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or run /login."
    )


def _get_provider_kwargs(provider: str, *, model_name: str | None = None) -> dict[str, Any]:
    """Retrieve all configuration arguments for the provider/model."""
    config = ModelConfig.load()
    result = config.get_kwargs(provider, model_name=model_name)

    base_url = config.get_base_url(provider)
    if base_url:
        result["base_url"] = base_url

    env_var = get_credential_env_var(provider)
    if env_var:
        api_key = resolve_env_var(env_var)
        if not api_key and provider == "google_genai":
            api_key = resolve_env_var("GEMINI_API_KEY")
        if api_key:
            result["api_key"] = api_key
            if provider == "google_genai":
                result["google_api_key"] = api_key

    # Special handling for google_genai Vertex AI & Google Cloud parameters
    if provider == "google_genai":
        use_vertex_env = resolve_env_var("GOOGLE_GENAI_USE_VERTEXAI")
        if use_vertex_env is not None:
            result["vertexai"] = use_vertex_env.lower() in ("true", "1")
        project_env = resolve_env_var("GOOGLE_CLOUD_PROJECT")
        if project_env:
            result["project"] = project_env
        location_env = resolve_env_var("GOOGLE_CLOUD_LOCATION")
        if location_env:
            result["location"] = location_env

    # ── Reasoning Effort Configuration (Generic / Configurable) ──
    from dcoder.model.reasoning import with_effort_model_params
    settings = _get_settings()
    effort = getattr(settings, "reasoning_effort", None)
    if effort:
        spec = f"{provider}:{model_name}" if model_name else provider
        result = with_effort_model_params(spec, result, effort)

    return result


def _create_model_from_class(
    class_path: str,
    model_name: str,
    provider: str,
    kwargs: dict[str, Any],
) -> BaseChatModel:
    """Instantiate a chat model dynamically via class reflection."""
    if ":" not in class_path:
        raise ModelConfigError(f"Invalid class_path '{class_path}': must be module:Class format")

    module_path, class_name = class_path.rsplit(":", 1)
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ModelConfigError(f"Module '{module_path}' not found for class_path '{class_path}': {e}") from e

    cls = getattr(module, class_name, None)
    if cls is None:
        raise ModelConfigError(f"Class '{class_name}' not found in module '{module_path}'")

    if not (isinstance(cls, type) and issubclass(cls, BaseChatModel)):
        raise ModelConfigError(f"'{class_path}' is not a BaseChatModel subclass")

    # Cast to Any to prevent Pyright reportCallIssue for dynamic instantiation
    from typing import Any, cast
    cls_any = cast(Any, cls)
    try:
        return cls_any(model=model_name, **kwargs)
    except TypeError:
        # Fallback for models that might use model_name
        return cls_any(model_name=model_name, **kwargs)


def _create_model_via_init(
    model_name: str,
    provider: str,
    kwargs: dict[str, Any],
) -> BaseChatModel:
    """Delegate to langchain's dynamic init_chat_model function."""
    from langchain.chat_models import init_chat_model

    try:
        if provider:
            return init_chat_model(model_name, model_provider=provider, **kwargs)
        return init_chat_model(model_name, **kwargs)
    except ImportError as e:
        package_map = {
            "anthropic": "langchain-anthropic",
            "openai": "langchain-openai",
            "google_genai": "langchain-google-genai",
        }
        package = package_map.get(provider, f"langchain-{provider}")
        raise MissingProviderPackageError(
            f"Missing package for '{provider}'. Install: pip install {package}",
            provider=provider,
            package=package,
        ) from e
    except (ValueError, TypeError) as e:
        raise ModelConfigError(f"Invalid configuration for '{provider}:{model_name}': {e}") from e


def create_model(
    model_spec: str | None = None,
    *,
    extra_kwargs: dict[str, Any] | None = None,
    profile_overrides: dict[str, Any] | None = None,
) -> ModelResult:
    """Factory function to build a BaseChatModel and return ModelResult metadata."""
    if not model_spec:
        model_spec = _get_default_model_spec()

    parsed = ModelSpec.try_parse(model_spec)
    if parsed:
        provider = parsed.provider
        model_name = parsed.model
    else:
        model_name = model_spec
        provider = detect_provider(model_spec) or ""

    if provider:
        from dcoder.model.config import apply_stored_credentials
        apply_stored_credentials(provider)

    if provider and provider not in IMPLICIT_AUTH_PROVIDERS:
        cred_status = has_provider_credentials(provider)
        if cred_status is False:
            env_var = get_credential_env_var(provider)
            raise MissingCredentialsError(
                f"No credentials configured for provider '{provider}'. Set environment variable {env_var}.",
                provider=provider,
                env_var=env_var,
            )

    kwargs = _get_provider_kwargs(provider, model_name=model_name)
    if extra_kwargs:
        kwargs.update(extra_kwargs)
        eff = extra_kwargs.get("reasoning_effort")
        if eff:
            from dcoder.model.reasoning import with_effort_model_params
            spec = f"{provider}:{model_name}" if model_name else (model_name or "")
            kwargs = with_effort_model_params(spec, kwargs, eff)

    config = ModelConfig.load()
    class_path = config.get_class_path(provider) if provider else None

    if class_path:
        model = _create_model_from_class(class_path, model_name, provider, kwargs)
    else:
        model = _create_model_via_init(model_name, provider, kwargs)

    # Apply profile overrides
    # If the model has profile overrides in config.toml, merge them
    if provider:
        profile = config.get_profile_overrides(provider, model_name=model_name)
        if profile_overrides:
            profile.update(profile_overrides)
    else:
        profile = profile_overrides or {}

    context_limit = profile.get("max_input_tokens")
    unsupported_modalities = frozenset(profile.get("unsupported_modalities", []))

    # Try to extract context limit from model class metadata if not explicitly in profile
    if context_limit is None:
        model_profile = getattr(model, "profile", None)
        if isinstance(model_profile, dict) and isinstance(model_profile.get("max_input_tokens"), int):
            context_limit = model_profile["max_input_tokens"]

    return ModelResult(
        model=model,
        model_name=model_name,
        provider=provider or getattr(model, "_model_provider", ""),
        context_limit=context_limit,
        unsupported_modalities=unsupported_modalities,
    )
