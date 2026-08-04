import asyncio
import os
import sys
from pathlib import Path
import pytest
from langgraph.pregel import Pregel
from dcoder.server._server_config import ServerConfig
from dcoder.server.server_graph import make_graph
from dcoder.cli.server_manager import server_session


def test_server_config_from_env():
    # Set mock environment variables
    prefix = "DCODER_SERVER_"
    os.environ[f"{prefix}ASSISTANT_ID"] = "test-assistant"
    os.environ[f"{prefix}MODEL"] = "openai:gpt-4o"
    os.environ[f"{prefix}AUTO_APPROVE"] = "true"
    os.environ[f"{prefix}INTERACTIVE"] = "false"

    try:
        config = ServerConfig.from_env()
        assert config.assistant_id == "test-assistant"
        assert config.model == "openai:gpt-4o"
        assert config.auto_approve is True
        assert config.interactive is False
    finally:
        # Clean up
        os.environ.pop(f"{prefix}ASSISTANT_ID", None)
        os.environ.pop(f"{prefix}MODEL", None)
        os.environ.pop(f"{prefix}AUTO_APPROVE", None)
        os.environ.pop(f"{prefix}INTERACTIVE", None)


@pytest.mark.asyncio
async def test_make_graph():
    # Set mock environment variables to build the graph
    prefix = "DCODER_SERVER_"
    os.environ[f"{prefix}ASSISTANT_ID"] = "test-assistant"
    os.environ[f"{prefix}MODEL"] = "openai:gpt-4o"
    os.environ[f"{prefix}AUTO_APPROVE"] = "true"
    os.environ[f"{prefix}INTERACTIVE"] = "false"

    os.environ["OPENAI_API_KEY"] = "mock-key"
    try:
        # Resolve make_graph
        graph = await make_graph()
        assert isinstance(graph, Pregel)
    finally:
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop(f"{prefix}ASSISTANT_ID", None)
        os.environ.pop(f"{prefix}MODEL", None)
        os.environ.pop(f"{prefix}AUTO_APPROVE", None)
        os.environ.pop(f"{prefix}INTERACTIVE", None)


@pytest.mark.asyncio
async def test_make_graph_blockbuster_resilience(monkeypatch):
    from dcoder.server.server_graph import _build_graph_factory
    import threading

    real_getcwd = os.getcwd

    def main_thread_guard_getcwd():
        if threading.current_thread() is threading.main_thread():
            raise RuntimeError("Blocking call to os.getcwd on MainThread")
        return real_getcwd()

    monkeypatch.setattr(os, "getcwd", main_thread_guard_getcwd)

    prefix = "DCODER_SERVER_"
    os.environ[f"{prefix}ASSISTANT_ID"] = "test-assistant-blockbuster"
    os.environ[f"{prefix}MODEL"] = "openai:gpt-4o"
    os.environ["OPENAI_API_KEY"] = "mock-key"

    try:
        fresh_make_graph = _build_graph_factory()
        graph = await fresh_make_graph()
        assert isinstance(graph, Pregel)
    finally:
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop(f"{prefix}ASSISTANT_ID", None)
        os.environ.pop(f"{prefix}MODEL", None)

