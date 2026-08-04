"""Unit tests for dcoder.state.session.SessionManager."""

import pytest
import sqlite3
import json
from pathlib import Path
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from dcoder.state.session import SessionManager


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    """Fixture providing a temporary SQLite database path."""
    db_path = tmp_path / "test_checkpoints.sqlite"
    return db_path


@pytest.fixture
def session_manager(test_db_path: Path) -> SessionManager:
    """Fixture providing a SessionManager instance."""
    return SessionManager(db_path=test_db_path)


@pytest.mark.asyncio
async def test_session_manager_initializes_checkpointer(session_manager: SessionManager):
    """Test get_checkpointer initializes and yields a valid AsyncSqliteSaver."""
    async with (await session_manager.get_checkpointer()) as saver:
        await saver.setup()
        # Check that it has an active aiosqlite connection
        assert getattr(saver, "conn", None) is not None
        # It should automatically create the necessary tables
        async with saver.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "checkpoints"


@pytest.mark.asyncio
async def test_session_manager_get_thread_messages_deserialization(session_manager: SessionManager):
    """
    Test critical functionality: get_thread_messages must accurately extract and deserialize
    LangChain Message objects from the raw 'writes' or 'checkpoints' tables using JsonPlusSerializer.
    """
    # 1. Setup the checkpointer and write dummy thread data to it
    thread_id = "test-thread-456"
    
    # We will manually seed the DB with serialized LangChain messages to simulate
    # how LangGraph writes to the `writes` table.
    serde = JsonPlusSerializer()
    
    # Simulating a human message and an AI message with a tool call
    messages_to_store = [
        HumanMessage(content="Hello world"),
        AIMessage(
            content="I am doing a tool call", 
            tool_calls=[{"name": "test_tool", "args": {"arg": "value"}, "id": "call_1"}]
        ),
        ToolMessage(content="Tool result", tool_call_id="call_1", name="test_tool")
    ]
    
    # LangGraph typically serializes them using the serializer
    type_str, blob = serde.dumps_typed(messages_to_store)
    
    async with (await session_manager.get_checkpointer()) as saver:
        await saver.setup()
        # Seed the DB directly to mimic what happens internally during agent execution
        await saver.conn.execute(
            """
            INSERT INTO writes (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (thread_id, "", "checkpoint-123", "task-123", 0, "messages", type_str, blob)
        )
        await saver.conn.commit()

    # 2. Test extraction and deserialization via the method used by the UI
    extracted_messages = await session_manager.get_thread_messages(thread_id)
    
    # 3. Assert correct mapping back to LangChain objects
    assert len(extracted_messages) == 3
    assert isinstance(extracted_messages[0], HumanMessage)
    assert extracted_messages[0].content == "Hello world"
    
    assert isinstance(extracted_messages[1], AIMessage)
    assert extracted_messages[1].tool_calls[0]["name"] == "test_tool"
    
    assert isinstance(extracted_messages[2], ToolMessage)
    assert extracted_messages[2].content == "Tool result"
    assert extracted_messages[2].tool_call_id == "call_1"


@pytest.mark.asyncio
async def test_session_manager_delete_thread(session_manager: SessionManager):
    """Test delete_thread removes all associated rows from the database."""
    thread_id = "thread-to-delete"
    
    async with (await session_manager.get_checkpointer()) as saver:
        await saver.setup()
        # Seed dummy checkpoint
        await saver.conn.execute(
            """
            INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata)
            VALUES (?, '', 'chk-1', '', 'json', ?, ?)
            """,
            (thread_id, b'{}', b'{}')
        )
        await saver.conn.commit()
        
    # Verify it exists
    threads = await session_manager.list_threads()
    assert any(t["thread_id"] == thread_id for t in threads)
    
    # Delete it
    success = await session_manager.delete_thread(thread_id)
    assert success is True
    
    # Verify it's gone
    threads = await session_manager.list_threads()
    assert not any(t["thread_id"] == thread_id for t in threads)
