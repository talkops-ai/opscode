"""Unit tests for External Editor module (dcoder.editor)."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from dcoder.editor import (
    ExternalEditorError,
    _prepare_command,
    open_in_editor,
    resolve_editor,
)


def test_resolve_editor_visual():
    """Verify $VISUAL overrides $EDITOR."""
    with patch.dict(os.environ, {"VISUAL": "code --wait", "EDITOR": "vim"}):
        cmd = resolve_editor()
        assert cmd == ["code", "--wait"]


def test_resolve_editor_editor_fallback():
    """Verify $EDITOR is used when $VISUAL is absent."""
    with patch.dict(os.environ, {"VISUAL": "", "EDITOR": "nvim -u NONE"}):
        cmd = resolve_editor()
        assert cmd == ["nvim", "-u", "NONE"]


def test_resolve_editor_default():
    """Verify platform fallback when no env var set."""
    with patch.dict(os.environ, {}, clear=True):
        cmd = resolve_editor()
        if sys.platform == "win32":
            assert cmd == ["notepad"]
        else:
            assert cmd == ["vi"]


def test_prepare_command_gui():
    """Verify GUI editor wait flag auto-injection."""
    cmd = _prepare_command(["code"], "/tmp/test.md")
    assert cmd == ["code", "--wait", "/tmp/test.md"]


def test_prepare_command_vim():
    """Verify vim-family auto-injects `-i NONE`."""
    cmd = _prepare_command(["vim"], "/tmp/test.md")
    assert cmd == ["vim", "-i", "NONE", "/tmp/test.md"]


@patch("subprocess.run")
def test_open_in_editor_success(mock_run):
    """Verify successful external editor lifecycle."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_run.return_value = mock_proc

    with patch.dict(os.environ, {"EDITOR": "echo"}):
        with patch("pathlib.Path.read_text", return_value="Edited content\n"):
            res = open_in_editor("Initial content")
            assert res == "Edited content"


@patch("subprocess.run")
def test_open_in_editor_failure_raises(mock_run):
    """Verify ExternalEditorError raised when raise_on_error=True."""
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_run.return_value = mock_proc

    with patch.dict(os.environ, {"EDITOR": "false"}):
        with pytest.raises(ExternalEditorError):
            open_in_editor("Initial", raise_on_error=True)
