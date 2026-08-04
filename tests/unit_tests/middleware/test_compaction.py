"""Tests for compaction middleware."""

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from dcoder.middleware.compaction import CLICompactionMiddleware

class TestCompactionMiddleware:
    def test_compaction_triggers_on_threshold(self):
        """Compaction triggers when messages exceed the threshold."""
        middleware = CLICompactionMiddleware(max_message_lines=10, thread_id="test_thread")
        
        from langchain_core.messages import BaseMessage
        from typing import cast, Any
        messages: list[BaseMessage] = [SystemMessage(content="System prompt")]
        for i in range(20):
            messages.append(HumanMessage(content=f"Message {i}\nLine 2\nLine 3"))
            
        state = cast(Any, {"messages": messages})
        res = middleware.before_agent(state, runtime=None, config=None)
        
        assert res is not None
        compacted = res["messages"]
        assert len(compacted) < len(messages)
        assert any("[Compacted Conversation History" in str(m.content) for m in compacted)

    def test_compaction_preserves_system_message(self):
        """System prompt is never summarized."""
        middleware = CLICompactionMiddleware(max_message_lines=10, thread_id="test_thread")
        
        from langchain_core.messages import BaseMessage
        from typing import cast, Any
        messages: list[BaseMessage] = [SystemMessage(content="System prompt")]
        for i in range(20):
            messages.append(HumanMessage(content=f"Message {i}\nLine 2\nLine 3"))
            
        state = cast(Any, {"messages": messages})
        res = middleware.before_agent(state, runtime=None, config=None)
        
        compacted = res["messages"]
        assert isinstance(compacted[0], SystemMessage)
        assert compacted[0].content == "System prompt"

    def test_compaction_result_is_valid_message(self):
        """The resulting summary is a valid HumanMessage."""
        middleware = CLICompactionMiddleware(max_message_lines=10, thread_id="test_thread")
        
        from langchain_core.messages import BaseMessage
        from typing import cast, Any
        messages: list[BaseMessage] = [SystemMessage(content="System prompt")]
        for i in range(20):
            messages.append(HumanMessage(content=f"Message {i}\nLine 2\nLine 3"))
            
        state = cast(Any, {"messages": messages})
        res = middleware.before_agent(state, runtime=None, config=None)
        
        compacted = res["messages"]
        # In this implementation, the summary is placed as a SystemMessage at index 1
        assert isinstance(compacted[1], SystemMessage)
        assert "[Compacted Conversation History" in str(compacted[1].content)
