"""Cost / token usage command handler for DCoder."""

from __future__ import annotations

from dcoder.commands._base import BaseCommandHandler, CommandContext, CommandResult
from dcoder.commands._types import BypassTier, CommandCategory, SafetyLevel


class CostHandler(BaseCommandHandler):
    """Handler for /cost and /tokens commands displaying session token consumption and estimated cost."""

    @property
    def name(self) -> str:
        return "/cost"

    @property
    def aliases(self) -> tuple[str, ...]:
        return ("/tokens",)

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.CORE

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.READ_ONLY

    @property
    def bypass_tier(self) -> BypassTier:
        return BypassTier.QUEUED

    async def execute(self, ctx: CommandContext) -> CommandResult:
        total_tokens = 0
        conv_tokens: int | None = None

        if ctx.app is not None:
            # 1. Read total context tokens from app._context_tokens or adapter stats
            if hasattr(ctx.app, "_context_tokens") and isinstance(ctx.app._context_tokens, int) and ctx.app._context_tokens > 0:
                total_tokens = ctx.app._context_tokens
            elif hasattr(ctx.app, "_adapter") and ctx.app._adapter:
                stats = getattr(ctx.app._adapter, "stats", None)
                if stats:
                    inp = getattr(stats, "input_tokens", 0)
                    out = getattr(stats, "output_tokens", 0)
                    total_tokens = inp + out

            # 2. Retrieve approximate conversation token count matching reference dcode
            if hasattr(ctx.app, "_get_conversation_token_count"):
                try:
                    res = await ctx.app._get_conversation_token_count()
                    if res is not None:
                        conv_tokens = res
                except Exception:
                    pass

            if conv_tokens is None and hasattr(ctx.app, "query"):
                try:
                    from dcoder.ui.widgets.messages import AssistantMessage, UserMessage, ToolCallMessage
                    acc = 0
                    for u in ctx.app.query(UserMessage):
                        txt = getattr(u, "_raw_content", "") or ""
                        if txt:
                            acc += max(1, len(txt) // 4)
                    for a in ctx.app.query(AssistantMessage):
                        txt = getattr(a, "content_text", None) or "".join(getattr(a, "_fragments", []))
                        if txt:
                            acc += max(1, len(txt) // 4)
                    for t in ctx.app.query(ToolCallMessage):
                        txt = str(getattr(t, "_result", "")) or str(getattr(t, "_args", ""))
                        if txt:
                            acc += max(1, len(txt) // 4)
                    if acc > 0:
                        conv_tokens = acc
                except Exception:
                    pass

            if total_tokens == 0 and conv_tokens is not None and conv_tokens > 0:
                total_tokens = conv_tokens

        model_name = (
            getattr(ctx.settings, "model_name", None)
            or ctx.model_spec
            or (getattr(ctx.app, "_model", None) if ctx.app else None)
            or "default"
        )
        context_limit = getattr(ctx.settings, "model_context_limit", None)

        if total_tokens <= 0:
            parts = ["No token usage yet"]
            if context_limit:
                parts.append(f"{self._format(context_limit)} token context window")
            if model_name:
                parts.append(model_name)
            return CommandResult(success=True, message=" · ".join(parts))

        formatted_total = self._format(total_tokens)

        if context_limit is not None:
            limit_str = self._format(context_limit)
            pct = (total_tokens / context_limit) * 100
            usage_str = f"{formatted_total} / {limit_str} tokens ({pct:.0f}%)"
        else:
            usage_str = f"{formatted_total} tokens used"

        msg = f"{usage_str} · {model_name}" if model_name else usage_str

        if conv_tokens is not None:
            overhead = max(0, total_tokens - conv_tokens)
            overhead_str = self._format(overhead)
            conv_str = self._format(conv_tokens)

            overhead_unit = " tokens" if overhead < 1000 else ""
            conv_unit = " tokens" if conv_tokens < 1000 else ""

            msg += (
                f"\n├ System prompt + tools: ~{overhead_str}{overhead_unit} (fixed)"
                f"\n└ Conversation: ~{conv_str}{conv_unit}"
            )

        return CommandResult(success=True, message=msg)

    @staticmethod
    def _format(count: int) -> str:
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        if count >= 1_000:
            return f"{count / 1_000:.1f}k"
        return str(count)


__all__ = ["CostHandler"]
