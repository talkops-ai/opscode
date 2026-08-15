import pytest
from unittest.mock import AsyncMock, MagicMock
from dcoder.ui.app import DCoderApp
from dcoder.ui.widgets.messages import SystemMessage

@pytest.mark.asyncio
async def test_finalize_connection_with_resume_thread():
    app = DCoderApp(resume_thread="test-thread-id")
    app._mount_message = AsyncMock()
    app._load_thread_history = AsyncMock()
    app.query_one = MagicMock()

    await app._finalize_connection(client=MagicMock())

    assert app._agent_thread_id == "test-thread-id"
    
    # Verify SystemMessage was mounted
    app._mount_message.assert_called_once()
    mounted_message = app._mount_message.call_args[0][0]
    assert isinstance(mounted_message, SystemMessage)
    assert "🔄 Resumed thread" in mounted_message._raw_content
    assert "test-thread-id" in mounted_message._raw_content

    # Verify history was loaded
    app._load_thread_history.assert_called_once_with("test-thread-id")

@pytest.mark.asyncio
async def test_finalize_connection_without_resume_thread():
    app = DCoderApp()
    app._mount_message = AsyncMock()
    app._load_thread_history = AsyncMock()
    app.query_one = MagicMock()

    await app._finalize_connection(client=MagicMock())

    assert app._agent_thread_id is not None
    assert app._agent_thread_id != "test-thread-id"
    app._mount_message.assert_not_called()
    app._load_thread_history.assert_not_called()
