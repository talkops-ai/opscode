import pytest
from unittest.mock import MagicMock, AsyncMock, Mock
from dcoder.ui.textual_adapter import TextualAdapter
from langgraph.types import Command

@pytest.mark.asyncio
async def test_textual_adapter_interrupt_handling():
    """Verify that an __interrupt__ updates chunk triggers approval flow and resumes correctly."""
    adapter = TextualAdapter(
        app=MagicMock(),
        client=MagicMock(),
        assistant_id="mock_id",
        status_bar=MagicMock()
    )
    
    # Mock the await approval to return True (approved)
    adapter._await_approval = AsyncMock(return_value=True)
    
    # We will track the resume payload passed to astream
    captured_resume = None
    
    async def mock_astream(stream_input, *args, **kwargs):
        nonlocal captured_resume
        if isinstance(stream_input, Command) and stream_input.resume:
            captured_resume = stream_input.resume
            # Yield nothing on resume to end the stream loop
            return
            
        # First call, yield the interrupt chunk
        interrupt_obj = Mock()
        interrupt_obj.id = "int_123"
        interrupt_obj.value = {
            "action_requests": [{"name": "write_file", "args": {"file_path": "test.txt"}}],
            "review_configs": []
        }
        
        yield ((), "updates", {"__interrupt__": [interrupt_obj]})

    adapter._client.astream = mock_astream
    
    await adapter.stream_turn(prompt="Test", thread_id="t1")
    
    # Verify we awaited the approval
    adapter._await_approval.assert_called_once_with("int_123_0")
    
    # Verify we resumed with the correct payload
    assert captured_resume == {
        "int_123": {
            "decisions": [{"type": "approve"}]
        }
    }

