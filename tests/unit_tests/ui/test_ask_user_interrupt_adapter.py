import asyncio
from unittest.mock import MagicMock, patch
import pytest
from opscode.ui.app import OpsCodeApp
from opscode.ui.widgets.ask_user import AskUserMenu
from opscode.ui.widgets._ask_user_types import Question


@pytest.mark.asyncio
async def test_app_request_ask_user_mounting_and_cleanup():
    """Verify that OpsCodeApp._request_ask_user instantiates and mounts AskUserMenu."""
    app = OpsCodeApp()
    mock_messages = MagicMock()
    mock_chat_input = MagicMock()

    questions = [
        {"question": "Select region", "type": "multiple_choice", "choices": [{"value": "us-east-1"}]},
    ]

    with patch.object(app, "query_one") as mock_query_one:
        def query_side_effect(selector, *args, **kwargs):
            if selector == "#messages":
                return mock_messages
            if selector == "#input-area":
                return mock_chat_input
            return MagicMock()

        mock_query_one.side_effect = query_side_effect
        app._chat_input = mock_chat_input

        # Call _request_ask_user
        future = await app._request_ask_user(questions)
        assert isinstance(future, asyncio.Future)
        assert app._pending_ask_user_widget is not None
        assert isinstance(app._pending_ask_user_widget, AskUserMenu)

        # Simulate user answering via widget future
        app._pending_ask_user_widget._completion.resolve({
            "type": "answered",
            "answers": ["us-east-1"],
        })

        result = await future
        assert result["type"] == "answered"
        assert result["answers"] == ["us-east-1"]

        # Call finish cleanup
        await app._finish_ask_user_prompt(context="answered")
        assert app._pending_ask_user_widget is None


@pytest.mark.asyncio
async def test_app_cancel_pending_ask_user():
    """Verify that _cancel_pending_ask_user gracefully cancels any active widget."""
    app = OpsCodeApp()
    mock_messages = MagicMock()
    mock_chat_input = MagicMock()

    questions = [{"question": "Proceed?", "type": "text"}]

    with patch.object(app, "query_one") as mock_query_one:
        def query_side_effect(selector, *args, **kwargs):
            if selector == "#messages":
                return mock_messages
            if selector == "#input-area":
                return mock_chat_input
            return MagicMock()

        mock_query_one.side_effect = query_side_effect
        app._chat_input = mock_chat_input

        future = await app._request_ask_user(questions)
        widget = app._pending_ask_user_widget
        assert widget is not None

        await app._cancel_pending_ask_user()
        assert app._pending_ask_user_widget is None
        assert future.done()
        result = future.result()
        assert result["type"] == "cancelled"
