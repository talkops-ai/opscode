import uuid
import logging
from pathlib import Path
from typing import Any, NamedTuple, Optional
from datetime import datetime, timezone
import contextlib
import asyncio

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger("dcoder")

_aiosqlite_patched = False

def _patch_aiosqlite() -> None:
    """Patch aiosqlite.Connection with is_alive() if missing.
    Required by langgraph-checkpoint >= 2.1.0.
    """
    global _aiosqlite_patched
    if _aiosqlite_patched:
        return
    import aiosqlite
    if not hasattr(aiosqlite.Connection, "is_alive"):
        def _is_alive(self):
            return bool(self._running and self._connection is not None)
        setattr(aiosqlite.Connection, "is_alive", _is_alive)
    _aiosqlite_patched = True


async def _drain_aiosqlite_worker(conn) -> None:
    """Join the aiosqlite worker thread after close."""
    worker = getattr(conn, "_thread", None)
    if worker is None or not worker.is_alive():
        return
    with contextlib.suppress(RuntimeError):
        await asyncio.to_thread(worker.join, 5.0)


class ThreadInfo(NamedTuple):
    thread_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    initial_prompt: Optional[str]


class SessionManager:
    """Manage conversation threads and checkpoint persistence."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._message_count_cache: dict[str, tuple[str | None, int]] = {}
        self._initial_prompt_cache: dict[str, tuple[str | None, str | None]] = {}

    def generate_thread_id(self) -> str:
        """Generate new UUID thread ID."""
        return str(uuid.uuid4())

    async def get_checkpointer(self) -> contextlib.AbstractAsyncContextManager[AsyncSqliteSaver]:
        """Create or connect to checkpoint database."""
        _patch_aiosqlite()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        return AsyncSqliteSaver.from_conn_string(str(self._db_path))

    async def list_threads(self, limit: int = 20) -> list[ThreadInfo]:
        """List recent threads, newest first."""
        import aiosqlite
        _patch_aiosqlite()
        if not self._db_path.exists():
            return []

        threads = []
        try:
            async with aiosqlite.connect(self._db_path) as conn:
                async with conn.execute(
                    """
                    SELECT thread_id, MIN(checkpoint_id), MAX(checkpoint_id)
                    FROM checkpoints
                    GROUP BY thread_id
                    ORDER BY MAX(checkpoint_id) DESC
                    LIMIT ?
                    """,
                    (limit,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    
                for row in rows:
                    thread_id, min_cp, max_cp = row
                    created_at = datetime.now(timezone.utc)
                    updated_at = datetime.now(timezone.utc)
                    
                    msg_count = await self.get_message_count(thread_id, freshness=max_cp, conn=conn)
                    init_prompt = await self.get_initial_prompt(thread_id, freshness=max_cp, conn=conn)
                    
                    threads.append(
                        ThreadInfo(
                            thread_id=thread_id,
                            created_at=created_at,
                            updated_at=updated_at,
                            message_count=msg_count,
                            initial_prompt=init_prompt,
                        )
                    )
        except Exception as e:
            logger.warning("Failed to list threads from database: %s", e)
        return threads

    async def resume_thread(self, thread_id: str) -> Any:
        """Load thread state for resumption."""
        async with (await self.get_checkpointer()) as saver:
            config = RunnableConfig(configurable={"thread_id": thread_id})
            return await saver.aget_tuple(config)

    async def get_message_count(self, thread_id: str, freshness: str | None = None, conn: Any = None) -> int:
        """Count messages (cached)."""
        if thread_id in self._message_count_cache:
            cached_freshness, count = self._message_count_cache[thread_id]
            if freshness is None or cached_freshness == freshness:
                return count

        count = 0
        try:
            from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
            serde = JsonPlusSerializer()

            async def _query(connection):
                c = 0
                async with connection.execute(
                    "SELECT type, value FROM writes WHERE thread_id = ? AND channel = 'messages'",
                    (thread_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                for type_str, blob in rows:
                    if type_str and blob:
                        try:
                            msgs = serde.loads_typed((type_str, blob))
                            if isinstance(msgs, list):
                                c += len(msgs)
                        except Exception:
                            pass
                return c

            if conn is not None:
                count = await _query(conn)
            else:
                import aiosqlite
                _patch_aiosqlite()
                if self._db_path.exists():
                    async with aiosqlite.connect(self._db_path) as db_conn:
                        count = await _query(db_conn)
        except Exception as e:
            logger.warning("Failed to count messages for %s: %s", thread_id, e)

        self._message_count_cache[thread_id] = (freshness, count)
        return count

    async def get_initial_prompt(self, thread_id: str, freshness: str | None = None, conn: Any = None) -> Optional[str]:
        """First user message for display."""
        if thread_id in self._initial_prompt_cache:
            cached_freshness, prompt = self._initial_prompt_cache[thread_id]
            if freshness is None or cached_freshness == freshness:
                return prompt

        prompt = None
        try:
            from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
            serde = JsonPlusSerializer()

            async def _query(connection):
                p = None
                async with connection.execute(
                    "SELECT type, value FROM writes WHERE thread_id = ? AND channel = 'messages' ORDER BY checkpoint_id ASC",
                    (thread_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                for type_str, blob in rows:
                    if type_str and blob:
                        try:
                            msgs = serde.loads_typed((type_str, blob))
                            if isinstance(msgs, list):
                                for m in msgs:
                                    content = getattr(m, "content", None) or str(m)
                                    if content and not str(content).startswith("System Prompt"):
                                        p = str(content)
                                        break
                                if p:
                                    break
                        except Exception:
                            pass
                return p

            if conn is not None:
                prompt = await _query(conn)
            else:
                import aiosqlite
                _patch_aiosqlite()
                if self._db_path.exists():
                    async with aiosqlite.connect(self._db_path) as db_conn:
                        prompt = await _query(db_conn)
        except Exception as e:
            logger.warning("Failed to get initial prompt for %s: %s", thread_id, e)

        self._initial_prompt_cache[thread_id] = (freshness, prompt)
        return prompt

    async def get_thread_messages(self, thread_id: str) -> list[Any]:
        """Fetch and deserialize all stored messages for a thread from writes/checkpoints."""
        import aiosqlite
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

        _patch_aiosqlite()
        if not self._db_path.exists():
            return []

        serde = JsonPlusSerializer()
        messages: list[Any] = []

        try:
            async with aiosqlite.connect(self._db_path) as conn:
                async with conn.execute(
                    """
                    SELECT type, value FROM writes
                    WHERE thread_id = ? AND channel = 'messages'
                    ORDER BY checkpoint_id ASC
                    """,
                    (thread_id,)
                ) as cursor:
                    rows = await cursor.fetchall()

                for type_str, blob in rows:
                    if type_str and blob:
                        try:
                            msgs = serde.loads_typed((type_str, blob))
                            if isinstance(msgs, list):
                                messages.extend(msgs)
                            elif msgs:
                                messages.append(msgs)
                        except Exception as exc:
                            logger.debug("Failed deserializing write entry for thread %s: %s", thread_id, exc)

                if not messages:
                    async with conn.execute(
                        """
                        SELECT type, checkpoint FROM checkpoints
                        WHERE thread_id = ?
                        ORDER BY checkpoint_id DESC LIMIT 1
                        """,
                        (thread_id,)
                    ) as cursor:
                        row = await cursor.fetchone()
                    if row and row[0] and row[1]:
                        try:
                            cp_data = serde.loads_typed((row[0], row[1]))
                            if isinstance(cp_data, dict):
                                channel_vals = cp_data.get("channel_values", {})
                                raw_msgs = channel_vals.get("messages", [])
                                if isinstance(raw_msgs, list):
                                    messages.extend(raw_msgs)
                        except Exception as exc:
                            logger.debug("Failed deserializing checkpoint for thread %s: %s", thread_id, exc)
        except Exception as exc:
            logger.warning("Failed fetching thread history for %s: %s", thread_id, exc)

        return messages



    async def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread and its checkpoints."""
        import aiosqlite
        _patch_aiosqlite()
        if not self._db_path.exists():
            return False

        try:
            async with aiosqlite.connect(self._db_path) as conn:
                await conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
                await conn.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
                await conn.commit()
            self._message_count_cache.pop(thread_id, None)
            self._initial_prompt_cache.pop(thread_id, None)
            return True
        except Exception as e:
            logger.warning("Failed to delete thread %s: %s", thread_id, e)
            return False
