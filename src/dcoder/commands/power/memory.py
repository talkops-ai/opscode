"""``/memory`` (``/remember``) — Conversation learning extraction and memory management.

Reference: deepagents_code/app.py L12002 — ``/remember`` is an alias for
``/skill:remember`` which extracts learnings from conversation history.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from dcoder.commands._base import BaseCommandHandler, CommandContext, CommandResult
from dcoder.commands._types import BypassTier, CommandCategory, SafetyLevel

if TYPE_CHECKING:
    from dcoder.memory.store import MemoryStore

logger = logging.getLogger(__name__)


class MemoryHandler(BaseCommandHandler):
    """Manage conversation learnings and persisted memories.

    Subcommands:
      ``/memory``            — usage help
      ``/memory show``       — list all persisted memories
      ``/memory get <key>``  — show a specific memory
      ``/memory save <key> <content>`` — save a memory directly
      ``/memory delete <key>`` — delete a memory
      ``/memory clear``      — delete all project-scoped memories
      ``/remember``          — invoke skill:remember to extract learnings
      ``/remember <text>``   — save text as a memory directly
    """

    @property
    def name(self) -> str:
        return "/memory"

    @property
    def aliases(self) -> tuple[str, ...]:
        return ("/remember",)

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.POWER

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.LOW_RISK

    @property
    def bypass_tier(self) -> BypassTier:
        return BypassTier.QUEUED

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from dcoder.memory.store import MemoryStore

        cmd_name = ctx.raw_command.strip().split()[0].lower()
        args = ctx.args.strip()

        # Project root detection
        project_root = _detect_project_root()
        store = MemoryStore(project_root=project_root)

        # ── /remember (skill alias) ──────────────────────
        if cmd_name == "/remember":
            return await self._handle_remember(ctx, store, args)

        # ── /memory subcommands ──────────────────────────
        if not args:
            return self._usage()

        sub, _, remainder = args.partition(" ")
        sub = sub.lower()
        remainder = remainder.strip()

        if sub in {"show", "list"}:
            return self._show_memories(store)

        if sub == "get":
            if not remainder:
                return CommandResult(success=False, message="Usage: /memory get <key>")
            return self._get_memory(store, remainder)

        if sub == "save":
            key, _, content = remainder.partition(" ")
            if not key or not content:
                return CommandResult(success=False, message="Usage: /memory save <key> <content>")
            path = store.save(key.strip(), content.strip())
            return CommandResult(
                success=True,
                message=f"✅ Memory saved: `{key.strip()}` → `{path}`",
            )

        if sub in {"delete", "rm", "remove"}:
            if not remainder:
                return CommandResult(success=False, message="Usage: /memory delete <key>")
            if store.delete(remainder):
                return CommandResult(success=True, message=f"Deleted memory: `{remainder}`")
            return CommandResult(success=False, message=f"Memory `{remainder}` not found.")

        if sub == "clear":
            entries = store.list_all()
            count = 0
            for entry in entries:
                if store.delete(entry.key):
                    count += 1
            return CommandResult(
                success=True,
                message=f"Cleared {count} memory entries." if count else "No memories to clear.",
            )

        return self._usage()

    async def _handle_remember(
        self,
        ctx: CommandContext,
        store: "MemoryStore",
        args: str,
    ) -> CommandResult:
        """Handle ``/remember`` — extract learnings or save directly.

        Reference: deepagents_code/app.py L12002-L12016.
        ``/remember`` with no args invokes ``/skill:remember``.
        ``/remember <text>`` saves text directly as a memory.
        """
        from dcoder.memory.store import MemoryStore

        if args:
            # Direct save: /remember prefer terraform fmt over tofu
            import re
            import time

            # Generate a key from the first few words
            words = re.sub(r"[^\w\s-]", "", args).split()[:5]
            key = "-".join(words).lower()
            path = store.save(key, args)
            return CommandResult(
                success=True,
                message=f"✅ Memory saved: `{key}` → `{path}`",
            )

        # No args: invoke skill:remember for conversation extraction
        app = ctx.app
        if app is not None and hasattr(app, "_handle_skill_command"):
            try:
                # Check if there are conversation messages first
                has_messages = True
                if hasattr(app, "_has_conversation_messages"):
                    has_messages = await app._has_conversation_messages()

                if not has_messages:
                    return CommandResult(
                        success=True,
                        message="Nothing to remember yet. Start a conversation first, "
                        "then use `/remember` to capture learnings.",
                    )

                await app._handle_skill_command("/skill:remember")
                return CommandResult(
                    success=True,
                    message=None,
                    mount_as_app_message=False,
                )
            except Exception as exc:
                logger.warning("Failed to invoke skill:remember: %s", exc)

        return CommandResult(
            success=True,
            message="The `remember` skill is not available. "
            "Use `/memory save <key> <content>` to save memories directly.",
        )

    def _show_memories(self, store: "MemoryStore") -> CommandResult:
        entries = store.list_all()
        if not entries:
            return CommandResult(
                success=True,
                message="No memories stored yet.\n"
                "Use `/remember <text>` or `/memory save <key> <content>` to create one.",
            )

        lines = ["**Persisted Memories:**", ""]
        for entry in entries:
            preview = entry.content.strip().splitlines()[0][:80] if entry.content.strip() else ""
            tag = f" ({entry.source})" if entry.source else ""
            lines.append(f"  • **{entry.key}**{tag} — {preview}")
        lines.append("")
        lines.append(f"_{len(entries)} total memories_")

        return CommandResult(success=True, message="\n".join(lines))

    def _get_memory(self, store: "MemoryStore", key: str) -> CommandResult:
        entry = store.get(key)
        if entry is None:
            return CommandResult(success=False, message=f"Memory `{key}` not found.")
        return CommandResult(
            success=True,
            message=f"**Memory: {entry.key}** ({entry.source})\n\n{entry.content}",
        )

    def _usage(self) -> CommandResult:
        return CommandResult(
            success=True,
            message=(
                "**Usage:**\n"
                "  `/memory show`           — list all memories\n"
                "  `/memory get <key>`      — view a specific memory\n"
                "  `/memory save <key> <text>` — save a memory\n"
                "  `/memory delete <key>`   — delete a memory\n"
                "  `/memory clear`          — delete all memories\n"
                "  `/remember`              — extract learnings from conversation\n"
                "  `/remember <text>`       — save text as a memory"
            ),
        )


def _detect_project_root() -> Path | None:
    """Walk up from cwd to find a project root (has .git or .dcoder)."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists() or (parent / ".dcoder").exists():
            return parent
    return None
