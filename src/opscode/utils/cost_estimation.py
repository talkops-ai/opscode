"""Estimate model cost using ``genai-prices``.

Provides token-level and session-level pricing calculations for supported
model providers (Anthropic, OpenAI, Google, Bedrock, Azure, Mistral, xAI).

The primary entry point is ``estimate_cost``, which delegates to ``TokenCostEstimator``.
The import of ``genai-prices`` is lazy so CLI startup remains fast.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

SESSION_COST_EVENT_TYPE = "session_cost"
"""Custom-stream event type carrying the thread's absolute cumulative cost.

Emitted by the durable writer so the status bar can track spend live without
re-pricing anything.
"""

_PROVIDER_ALIASES: dict[str, str] = {
    "azure_openai": "azure",
    "bedrock": "aws",
    "google_genai": "google",
    "google_vertexai": "google",
    "mistralai": "mistral",
    "xai": "x-ai",
}
"""Map LangChain provider names to the identifiers used by ``genai-prices``."""

_UNPRICEABLE_PROVIDERS: frozenset[str] = frozenset({"openai_codex"})
"""Providers whose access model is not equivalent to per-token API billing."""


class TokenCostEstimator:
    """Calculates granular pricing estimates for model completions."""

    _pricing_unavailable: bool = False
    _pricing_contract_broken: bool = False
    _audio_cache_overlap_reported: bool = False

    @classmethod
    def is_available(cls) -> bool:
        """Report whether pricing engine is currently functional."""
        return not (cls._pricing_unavailable or cls._pricing_contract_broken)

    @classmethod
    def _load_pricing_backend(cls) -> tuple[Any, Any] | None:
        """Lazily load genai-prices calculation backend."""
        try:
            from genai_prices import Usage, calc_price
        except Exception:
            if not cls._pricing_unavailable:
                logger.warning(
                    "Could not load genai-prices; cost estimates are unavailable "
                    "for this session.",
                    exc_info=True,
                )
            cls._pricing_unavailable = True
            return None
        cls._pricing_unavailable = False
        return Usage, calc_price

    @staticmethod
    def _token_count(value: object) -> int:
        """Return non-negative integer token count."""
        return (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value > 0
            else 0
        )

    @classmethod
    def _cache_write_counts(cls, details: Mapping[str, Any]) -> tuple[int, int, int]:
        """Extract generic, 5m, and 1h cache-write token counts."""
        five_minute = cls._token_count(details.get("ephemeral_5m_input_tokens"))
        one_hour = cls._token_count(details.get("ephemeral_1h_input_tokens"))
        if five_minute or one_hour:
            return 0, five_minute, one_hour
        generic = cls._token_count(details.get("cache_creation")) or cls._token_count(
            details.get("cache_write")
        )
        return generic, 0, 0

    @classmethod
    def _clamp_cache_counts(
        cls,
        input_tokens: int,
        cache_read: int,
        cache_writes: tuple[int, int, int],
    ) -> tuple[int, tuple[int, int, int]]:
        """Clamp cache buckets to the inclusive input-token total."""
        clamped_read = min(cache_read, input_tokens)
        remaining = input_tokens - clamped_read
        clamped_writes: list[int] = []
        for count in cache_writes:
            clamped = min(count, remaining)
            clamped_writes.append(clamped)
            remaining -= clamped
        return clamped_read, (
            clamped_writes[0],
            clamped_writes[1],
            clamped_writes[2],
        )

    @classmethod
    def _clamped_detail(
        cls,
        value: object,
        total: int,
        *,
        field: str,
        model_ref: str,
        provider: str,
    ) -> int:
        """Return a detail token count clamped to the containing total."""
        count = cls._token_count(value)
        if count <= total:
            return count
        logger.warning(
            "Detail token count exceeds the total containing it; clamping for "
            "pricing. model=%r provider=%r field=%s reported=%d clamped=%d",
            model_ref,
            provider,
            field,
            count,
            total,
        )
        return total

    @classmethod
    def estimate(
        cls,
        usage_metadata: Mapping[str, Any] | None,
        model_name: str,
        provider: str = "",
    ) -> float | None:
        """Estimate token cost in USD for a single model completion."""
        model_ref = model_name.strip()
        provider_key = provider.strip().lower()
        if not usage_metadata or not model_ref:
            return None
        if provider_key in _UNPRICEABLE_PROVIDERS:
            logger.debug(
                "Cost estimate unavailable for non-API provider=%r model=%r",
                provider,
                model_ref,
            )
            return None

        input_tokens = cls._token_count(usage_metadata.get("input_tokens"))
        output_tokens = cls._token_count(usage_metadata.get("output_tokens"))
        if not input_tokens and not output_tokens:
            logger.debug(
                "Usage reports only a combined token total, which cannot be priced: "
                "model=%r provider=%r",
                model_ref,
                provider,
            )
            return None

        # ── Input detail decomposition ────────────────────────────────
        input_details = usage_metadata.get("input_token_details")
        if isinstance(input_details, Mapping):
            cache_read_tokens = cls._token_count(input_details.get("cache_read"))
            cache_writes = cls._cache_write_counts(input_details)
            input_audio_tokens = cls._clamped_detail(
                input_details.get("audio"),
                input_tokens,
                field="input audio",
                model_ref=model_ref,
                provider=provider,
            )
        else:
            cache_read_tokens = 0
            cache_writes = (0, 0, 0)
            input_audio_tokens = 0

        # ── Output detail decomposition ───────────────────────────────
        output_details = usage_metadata.get("output_token_details")
        if isinstance(output_details, Mapping):
            output_reasoning_tokens = cls._token_count(output_details.get("reasoning"))
            if provider_key == "perplexity":
                output_tokens += output_reasoning_tokens
            output_audio_tokens = cls._clamped_detail(
                output_details.get("audio"),
                output_tokens,
                field="output audio",
                model_ref=model_ref,
                provider=provider,
            )
            output_reasoning_tokens = cls._clamped_detail(
                output_reasoning_tokens,
                output_tokens,
                field="output reasoning",
                model_ref=model_ref,
                provider=provider,
            )
        else:
            output_audio_tokens = 0
            output_reasoning_tokens = 0

        # ── Cache clamping ────────────────────────────────────────────
        original_cache_read = cache_read_tokens
        original_cache_writes = cache_writes
        cache_read_tokens, cache_writes = cls._clamp_cache_counts(
            input_tokens, cache_read_tokens, cache_writes
        )
        if (
            cache_read_tokens != original_cache_read
            or cache_writes != original_cache_writes
        ):
            logger.warning(
                "Cache token counts exceed inclusive input total; clamping for "
                "pricing. model=%r provider=%r input=%d cache_read=%d->%d",
                model_ref,
                provider,
                input_tokens,
                original_cache_read,
                cache_read_tokens,
            )
        generic_cache_write_tokens, cache_write_5m_tokens, cache_write_1h_tokens = (
            cache_writes
        )
        cache_write_tokens = generic_cache_write_tokens or (
            cache_write_5m_tokens + cache_write_1h_tokens
        )

        # ── Audio / cache intersection guard ──────────────────────────
        if input_audio_tokens and (cache_read_tokens or any(cache_writes)):
            if not cls._audio_cache_overlap_reported:
                cls._audio_cache_overlap_reported = True
                logger.warning(
                    "Pricing audio input at base input rate due to unpartitioned "
                    "audio/cache reporting. model=%r provider=%r audio=%d",
                    model_ref,
                    provider,
                    input_audio_tokens,
                )
            input_audio_tokens = 0

        # ── Backend pricing computation ───────────────────────────────
        pricing = cls._load_pricing_backend()
        if pricing is None:
            return None
        usage_type, calc_price = pricing

        provider_id = _PROVIDER_ALIASES.get(provider_key, provider_key) or None
        try:
            usage = usage_type(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read_tokens or None,
                cache_write_tokens=cache_write_tokens or None,
                cache_write_5m_tokens=cache_write_5m_tokens or None,
                cache_write_1h_tokens=cache_write_1h_tokens or None,
                input_audio_tokens=input_audio_tokens or None,
                output_audio_tokens=output_audio_tokens or None,
                output_reasoning_tokens=output_reasoning_tokens or None,
            )
        except Exception:
            if not cls._pricing_contract_broken:
                logger.warning(
                    "genai-prices rejected the usage schema, so no request can be "
                    "priced; cost estimates are unavailable for this session. "
                    "model=%r provider=%r",
                    model_ref,
                    provider,
                    exc_info=True,
                )
            cls._pricing_contract_broken = True
            return None
        cls._pricing_contract_broken = False

        try:
            price = calc_price(
                usage,
                model_ref=model_ref,
                provider_id=provider_id,
            )
            cost_usd = float(price.total_price)
        except LookupError:
            logger.debug(
                "Cost estimate unavailable for model=%r provider=%r",
                model_ref,
                provider,
                exc_info=True,
            )
            return None
        except Exception:
            logger.debug(
                "Cost estimate unavailable for model=%r provider=%r",
                model_ref,
                provider,
                exc_info=True,
            )
            return None

        return cost_usd if math.isfinite(cost_usd) and cost_usd >= 0 else None


def _resolve_pricing_provider(
    provider: object,
    fallback_provider: str,
    *,
    prefer_fallback_provider: bool = True,
) -> str:
    """Resolve response metadata without losing a configured provider alias."""
    explicit_provider = provider if isinstance(provider, str) and provider else ""
    resolved_provider = explicit_provider or fallback_provider
    if explicit_provider and not prefer_fallback_provider:
        return explicit_provider
    fallback_provider_key = fallback_provider.strip().lower()
    if fallback_provider_key in _PROVIDER_ALIASES or (
        fallback_provider_key in _UNPRICEABLE_PROVIDERS
    ):
        return fallback_provider
    return resolved_provider


def pricing_data_available() -> bool:
    """Report whether pricing calculations are currently available."""
    return TokenCostEstimator.is_available()


def estimate_cost(
    usage_metadata: Mapping[str, Any] | None,
    model_name: str,
    provider: str = "",
) -> float | None:
    """Estimate one model request's cost in USD from LangChain usage metadata."""
    return TokenCostEstimator.estimate(usage_metadata, model_name, provider)


def resolve_message_model(
    message: object,
    *,
    fallback_model: str = "",
    fallback_provider: str = "",
    prefer_fallback_provider: bool = True,
) -> tuple[str, str]:
    """Resolve the model and provider attached to a streamed model message."""
    metadata = getattr(message, "response_metadata", None)
    if not isinstance(metadata, Mapping):
        metadata = {}
    model_name = metadata.get("model_name") or metadata.get("model") or fallback_model
    resolved_model = model_name if isinstance(model_name, str) else fallback_model
    resp_provider = metadata.get("model_provider") or metadata.get("provider")
    resolved_provider = _resolve_pricing_provider(
        resp_provider,
        fallback_provider,
        prefer_fallback_provider=prefer_fallback_provider,
    )
    return resolved_model, resolved_provider
