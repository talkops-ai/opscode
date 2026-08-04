"""Unit tests for goal_state_notice — message classification and introspection."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from dcoder.middleware.goal_state_notice import (
    GOAL_CONTROL_MESSAGE_SOURCE,
    GOAL_STATE_MESSAGE_SOURCE,
    is_conversation_control_message,
    is_goal_internal_message,
    is_goal_state_message,
    is_human_message,
    is_internal_message,
    message_source,
    message_text,
)


class TestIsHumanMessage:
    """Tests for is_human_message classifier."""

    def test_langchain_human_message(self):
        msg = HumanMessage(content="hello")
        assert is_human_message(msg) is True

    def test_langchain_ai_message(self):
        msg = AIMessage(content="response")
        assert is_human_message(msg) is False

    def test_dict_with_role_user(self):
        msg = {"role": "user", "content": "hello"}
        assert is_human_message(msg) is True

    def test_dict_with_type_human(self):
        msg = {"type": "human", "content": "hello"}
        assert is_human_message(msg) is True

    def test_dict_with_role_assistant(self):
        msg = {"role": "assistant", "content": "hi"}
        assert is_human_message(msg) is False


class TestMessageText:
    """Tests for message_text extraction."""

    def test_string_content(self):
        msg = HumanMessage(content="hello world")
        assert message_text(msg) == "hello world"

    def test_dict_content(self):
        msg = {"content": "hello from dict"}
        assert message_text(msg) == "hello from dict"

    def test_list_content_with_text_blocks(self):
        msg = {"content": [{"type": "text", "text": "block1"}, {"type": "text", "text": "block2"}]}
        assert message_text(msg) == "block1block2"

    def test_list_content_with_strings(self):
        msg = {"content": ["part1", "part2"]}
        assert message_text(msg) == "part1part2"

    def test_no_content_returns_empty(self):
        msg = {}
        assert message_text(msg) == ""


class TestMessageSource:
    """Tests for message_source."""

    def test_goal_control_source(self):
        msg = HumanMessage(
            content="Continue with goal",
            additional_kwargs={"lc_source": GOAL_CONTROL_MESSAGE_SOURCE},
        )
        assert message_source(msg) == GOAL_CONTROL_MESSAGE_SOURCE

    def test_goal_state_source(self):
        msg = HumanMessage(
            content="State update",
            additional_kwargs={"lc_source": GOAL_STATE_MESSAGE_SOURCE},
        )
        assert message_source(msg) == GOAL_STATE_MESSAGE_SOURCE

    def test_no_source(self):
        msg = HumanMessage(content="plain message")
        assert message_source(msg) is None

    def test_dict_message_with_source(self):
        msg = {
            "type": "human",
            "content": "test",
            "additional_kwargs": {"lc_source": "goal_state"},
        }
        assert message_source(msg) == "goal_state"


class TestIsGoalInternalMessage:
    """Tests for is_goal_internal_message."""

    def test_goal_control_message(self):
        msg = HumanMessage(
            content="Continue",
            additional_kwargs={"lc_source": GOAL_CONTROL_MESSAGE_SOURCE},
        )
        assert is_goal_internal_message(msg) is True

    def test_goal_state_message(self):
        msg = HumanMessage(
            content="State changed",
            additional_kwargs={"lc_source": GOAL_STATE_MESSAGE_SOURCE},
        )
        assert is_goal_internal_message(msg) is True

    def test_plain_message_not_internal(self):
        msg = HumanMessage(content="Hello there")
        assert is_goal_internal_message(msg) is False

    def test_ai_message_not_internal(self):
        msg = AIMessage(content="Response")
        assert is_goal_internal_message(msg) is False


class TestIsGoalStateMessage:
    """Tests for is_goal_state_message."""

    def test_modern_source_tag(self):
        msg = HumanMessage(
            content="State update",
            additional_kwargs={"lc_source": GOAL_STATE_MESSAGE_SOURCE},
        )
        assert is_goal_state_message(msg) is True

    def test_legacy_prefix(self):
        from dcoder._constants import SYSTEM_MESSAGE_PREFIX

        msg = HumanMessage(
            content=f"{SYSTEM_MESSAGE_PREFIX} Goal/rubric state changed. Status: active"
        )
        assert is_goal_state_message(msg) is True

    def test_plain_user_message_not_goal_state(self):
        msg = HumanMessage(content="Deploy a VPC")
        assert is_goal_state_message(msg) is False


class TestIsConversationControlMessage:
    """Tests for is_conversation_control_message."""

    def test_goal_control(self):
        msg = HumanMessage(
            content="Continue",
            additional_kwargs={"lc_source": GOAL_CONTROL_MESSAGE_SOURCE},
        )
        assert is_conversation_control_message(msg) is True

    def test_rubric_grader(self):
        msg = HumanMessage(
            content="Grading result",
            additional_kwargs={"lc_source": "rubric_grader"},
        )
        assert is_conversation_control_message(msg) is True

    def test_user_message_not_control(self):
        msg = HumanMessage(content="Tell me about VPCs")
        assert is_conversation_control_message(msg) is False


class TestIsInternalMessage:
    """Tests for is_internal_message."""

    def test_summarization_message(self):
        msg = HumanMessage(
            content="Summary...",
            additional_kwargs={"lc_source": "summarization"},
        )
        assert is_internal_message(msg) is True

    def test_system_prefix_message(self):
        from dcoder._constants import SYSTEM_MESSAGE_PREFIX

        msg = HumanMessage(content=f"{SYSTEM_MESSAGE_PREFIX} Internal notice.")
        assert is_internal_message(msg) is True

    def test_user_message_not_internal(self):
        msg = HumanMessage(content="Hello!")
        assert is_internal_message(msg) is False
