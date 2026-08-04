"""Estimate model cost using ``genai-prices``.

Replicates the pricing logic from ``deepagents_code.cost_tracking`` (lines
1-626) so dcoder's status bar displays the same dollar figures as the reference
dcode implementation. The middleware half (``_SessionCostRecorder``,
``CostTrackingMiddleware``) is intentionally not replicated because dcoder's
adapter-based streaming architecture handles cost differently.

Every caller uses ``estimate_cost``, the only function that imports or calls
``genai-prices``. The import is lazy so the package and its bundled pricing data
stay off the CLI startup path. Unsupported models and malformed usage return
``None``; pricing must never interrupt a model turn.
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
re-pricing anything. The payload is ``{"type": ..., "total": <usd>, "thread_id":
<id>, "pricing_ok": <bool>}``; ``total`` is the full thread lifetime estimate,
never a delta, so a client that misses an event still converges on the next one.
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


def _resolve_pricing_provider(
    provider: object,
    fallback_provider: str,
    *,
    prefer_fallback_provider: bool = True,
) -> str:
    """Resolve response metadata without losing a configured provider alias.

    Args:
        provider: Provider named by the response, if any.
        fallback_provider: Provider configured for the completed request.
        prefer_fallback_provider: Whether a configured alias or non-API provider
            should replace response metadata. Disable this when the fallback
            belongs to a parent request rather than this specific model call.

    Returns:
        The provider identifier to use for pricing.
    """
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


def _token_count(value: object) -> int:
    """Return a non-negative integer token count for a metadata value."""
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else 0
    )


def _cache_write_counts(details: Mapping[str, Any]) -> tuple[int, int, int]:
    """Return generic-only, five-minute, and one-hour cache-write counts.

    LangChain Anthropic zeroes the generic ``cache_creation`` field when the
    response includes a TTL breakdown, so preserve that breakdown. Only the
    one-hour bucket earns anything by being split out: ``genai-prices`` publishes a
    premium one-hour rate, while five-minute writes have no rate of their own and
    fall back to the generic cache-write rate.

    Returns:
        The generic-only, five-minute, and one-hour counts. A TTL breakdown wins
            outright, so the generic slot is mutually exclusive with the other
            two.
    """
    five_minute = _token_count(details.get("ephemeral_5m_input_tokens"))
    one_hour = _token_count(details.get("ephemeral_1h_input_tokens"))
    if five_minute or one_hour:
        return 0, five_minute, one_hour
    generic = _token_count(details.get("cache_creation")) or _token_count(
        details.get("cache_write")
    )
    return generic, 0, 0


def _clamp_cache_counts(
    input_tokens: int,
    cache_read: int,
    cache_writes: tuple[int, int, int],
) -> tuple[int, tuple[int, int, int]]:
    """Clamp disjoint cache buckets to the inclusive input-token total.

    Args:
        input_tokens: Inclusive input-token count, covering reads and writes.
        cache_read: Cache-read token count.
        cache_writes: Generic-only, five-minute, and one-hour write counts.

    Returns:
        The clamped read count and write-count tuple.
    """
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


def _clamped_detail(
    value: object,
    total: int,
    *,
    field: str,
    model_ref: str,
    provider: str,
) -> int:
    """Return a detail token count clamped to the total that contains it.

    Args:
        value: Raw metadata value for the detail bucket.
        total: Inclusive total the bucket has to fit inside.
        field: Detail name, for the log message only.
        model_ref: Model being priced, for the log message only.
        provider: Provider being priced, for the log message only.

    Returns:
        The clamped count.
    """
    count = _token_count(value)
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


_PRICING_UNAVAILABLE = False
"""Whether importing ``genai-prices`` failed on the most recent attempt."""

_PRICING_CONTRACT_BROKEN = False
"""Whether ``Usage`` rejected the normalized fields supplied by this package."""

_AUDIO_CACHE_OVERLAP_REPORTED = False
"""Whether the audio/cache overlap understatement has been reported."""


def pricing_data_available() -> bool:
    """Report whether ``genai-prices`` is currently able to price a request.

    Returns:
        ``False`` when the most recent import failed, or when the most recent
            construction of ``Usage`` rejected this package's normalized field
            schema.
    """
    return not (_PRICING_UNAVAILABLE or _PRICING_CONTRACT_BROKEN)


def _load_pricing() -> tuple[Any, Any] | None:
    """Import ``genai-prices`` lazily, tracking whether it is currently loadable.

    Returns:
        The ``(Usage, calc_price)`` pair, or ``None`` when the package is
            unavailable.
    """
    global _PRICING_UNAVAILABLE  # noqa: PLW0603
    try:
        from genai_prices import Usage, calc_price
    except Exception:
        if not _PRICING_UNAVAILABLE:
            logger.warning(
                "Could not load genai-prices; cost estimates are unavailable "
                "for this session.",
                exc_info=True,
            )
        _PRICING_UNAVAILABLE = True
        return None
    _PRICING_UNAVAILABLE = False
    return Usage, calc_price


def estimate_cost(
    usage_metadata: Mapping[str, Any] | None,
    model_name: str,
    provider: str = "",
) -> float | None:
    """Estimate one model request's cost in USD from LangChain usage metadata.

    LangChain's ``input_tokens`` is the full input count, including cache reads
    and writes. ``genai-prices`` receives that inclusive total plus the cache,
    modality, and reasoning details; it subtracts each detail bucket from the
    total that contains it before applying rates, so tokens are not
    double-counted.

    Args:
        usage_metadata: The request's LangChain ``usage_metadata`` mapping.
        model_name: Model identifier used for the request.
        provider: LangChain provider identifier. An empty value lets
            ``genai-prices`` infer the provider from ``model_name``.

    Returns:
        Estimated cost in USD, or ``None`` when usage or pricing is unavailable.
    """
    global _AUDIO_CACHE_OVERLAP_REPORTED, _PRICING_CONTRACT_BROKEN  # noqa: PLW0603
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

    input_tokens = _token_count(usage_metadata.get("input_tokens"))
    output_tokens = _token_count(usage_metadata.get("output_tokens"))
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
        cache_read_tokens = _token_count(input_details.get("cache_read"))
        cache_writes = _cache_write_counts(input_details)
        input_audio_tokens = _clamped_detail(
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
        output_reasoning_tokens = _token_count(output_details.get("reasoning"))
        # langchain-perplexity reports completion tokens as the output total and
        # exposes reasoning as an extra bucket. genai-prices expects the total to
        # include every detailed bucket.
        if provider_key == "perplexity":
            output_tokens += output_reasoning_tokens
        output_audio_tokens = _clamped_detail(
            output_details.get("audio"),
            output_tokens,
            field="output audio",
            model_ref=model_ref,
            provider=provider,
        )
        output_reasoning_tokens = _clamped_detail(
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
    cache_read_tokens, cache_writes = _clamp_cache_counts(
        input_tokens, cache_read_tokens, cache_writes
    )
    if (
        cache_read_tokens != original_cache_read
        or cache_writes != original_cache_writes
    ):
        logger.warning(
            "Cache token counts exceed the inclusive input total; clamping for "
            "pricing. model=%r provider=%r input=%d cache_read=%d->%d "
            "cache_write generic=%d->%d 5m=%d->%d 1h=%d->%d",
            model_ref,
            provider,
            input_tokens,
            original_cache_read,
            cache_read_tokens,
            *(
                count
                for pair in zip(original_cache_writes, cache_writes, strict=True)
                for count in pair
            ),
        )
    generic_cache_write_tokens, cache_write_5m_tokens, cache_write_1h_tokens = (
        cache_writes
    )
    cache_write_tokens = generic_cache_write_tokens or (
        cache_write_5m_tokens + cache_write_1h_tokens
    )

    # ── Audio/cache overlap ───────────────────────────────────────
    if input_audio_tokens and (cache_read_tokens or any(cache_writes)):
        if not _AUDIO_CACHE_OVERLAP_REPORTED:
            _AUDIO_CACHE_OVERLAP_REPORTED = True
            logger.warning(
                "Pricing audio input at the ordinary input rate because the "
                "catalog wants an audio/cache intersection, which "
                "LangChain does not report. This understates requests that mix "
                "audio with prompt caching. model=%r provider=%r audio=%d",
                model_ref,
                provider,
                input_audio_tokens,
            )
        input_audio_tokens = 0

    # ── Price via genai-prices ────────────────────────────────────
    pricing = _load_pricing()
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
        if not _PRICING_CONTRACT_BROKEN:
            logger.warning(
                "genai-prices rejected the usage schema, so no request can be "
                "priced; cost estimates are unavailable for this session. "
                "model=%r provider=%r",
                model_ref,
                provider,
                exc_info=True,
            )
        _PRICING_CONTRACT_BROKEN = True
        return None
    _PRICING_CONTRACT_BROKEN = False

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


def resolve_message_model(
    message: object,
    *,
    fallback_model: str = "",
    fallback_provider: str = "",
    prefer_fallback_provider: bool = True,
) -> tuple[str, str]:
    """Resolve the model and provider attached to a streamed model message.

    Args:
        message: An AI message or chunk with optional ``response_metadata``.
        fallback_model: Model to use when message metadata does not name one.
        fallback_provider: Provider to use when message metadata does not name
            one. Known provider aliases and non-API providers override generic
            response metadata.
        prefer_fallback_provider: Whether those configured providers should
            replace response metadata. Disable this when the fallback describes
            a parent request rather than the message itself.

    Returns:
        The ``(model_name, provider)`` pair used for pricing.
    """
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
