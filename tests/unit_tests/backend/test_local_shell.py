"""Tests for local shell backend and environment building."""

from __future__ import annotations

import os
from unittest.mock import patch

from dcoder.backend.local import _build_shell_env


class TestBuildShellEnv:
    def test_build_shell_env_includes_safe_keys(self):
        """Standard safe keys like PATH, HOME, USER are included."""
        mock_env = {
            "PATH": "/usr/bin",
            "HOME": "/home/user",
            "USER": "user",
            "SECRET_KEY": "supersecret",
            "AWS_ACCESS_KEY_ID": "AKIA...",
        }
        with patch.dict(os.environ, mock_env, clear=True):
            env = _build_shell_env()
            
            assert "PATH" in env
            assert "HOME" in env
            assert "USER" in env
            assert "SECRET_KEY" not in env
            assert "AWS_ACCESS_KEY_ID" not in env

    def test_build_shell_env_prepends_local_bin(self):
        """/usr/local/bin and ~/.local/bin are prepended to PATH."""
        mock_env = {"PATH": "/usr/bin:/bin"}
        with patch.dict(os.environ, mock_env, clear=True):
            with patch("os.path.expanduser", lambda x: x.replace("~", "/home/user")):
                env = _build_shell_env()
                
                path_val = env["PATH"]
                assert path_val.startswith("/home/user/.local/bin:/usr/local/bin:/usr/bin:/bin")

    def test_build_shell_env_copies_tf_and_ansible_vars(self):
        """TF_VAR_* and ANSIBLE_* variables are explicitly preserved."""
        mock_env = {
            "PATH": "/usr/bin",
            "TF_VAR_region": "us-east-1",
            "ANSIBLE_CONFIG": "./ansible.cfg",
            "XDG_CONFIG_HOME": "/home/user/.config",
            "RANDOM_OTHER_VAR": "foo",
        }
        with patch.dict(os.environ, mock_env, clear=True):
            env = _build_shell_env()
            
            assert env["TF_VAR_region"] == "us-east-1"
            assert env["ANSIBLE_CONFIG"] == "./ansible.cfg"
            assert env["XDG_CONFIG_HOME"] == "/home/user/.config"
            assert "RANDOM_OTHER_VAR" not in env
