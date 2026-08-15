"""Tests for compaction middleware."""

from unittest.mock import MagicMock
import pytest
from langchain_core.language_models import BaseChatModel
from deepagents.backends.filesystem import FilesystemBackend
from opscode.middleware.compaction import (
    CLICompactionMiddleware,
    _create_cli_compaction_middleware,
)


class TestCompactionMiddleware:
    def test_create_cli_compaction_middleware(self, tmp_path):
        """Verify _create_cli_compaction_middleware creates a valid CLICompactionMiddleware."""
        fake_model = MagicMock(spec=BaseChatModel)
        backend = FilesystemBackend(root_dir=str(tmp_path))

        middleware = _create_cli_compaction_middleware(fake_model, backend)

        assert isinstance(middleware, CLICompactionMiddleware)
        assert middleware.name == "SummarizationMiddleware"
        assert len(middleware.tools) == 1
        assert middleware.tools[0].name == "compact_conversation"

    def test_offload_rejection_unauthorized(self, tmp_path):
        """Unauthorized tool call when offload_tool_call_id is set is rejected."""
        fake_model = MagicMock(spec=BaseChatModel)
        backend = FilesystemBackend(root_dir=str(tmp_path))
        middleware = _create_cli_compaction_middleware(fake_model, backend)

        mock_request = MagicMock()
        mock_request.runtime.context = {"offload_tool_call_id": "authorized-123"}
        mock_request.tool_call = {"id": "unauthorized-456", "name": "read_file", "args": {}}
        mock_request.state = {"messages": []}

        rejection = middleware._offload_rejection(mock_request)
        assert rejection is not None
        assert "Not executed: /offload only authorizes" in rejection.content

