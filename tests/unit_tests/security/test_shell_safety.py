"""Unit tests for shell_safety module — dangerous patterns and allow-list matching."""

import pytest

from dcoder.security.shell_safety import (
    DANGEROUS_SHELL_PATTERNS,
    DEVOPS_DESTRUCTIVE_COMMANDS,
    DEVOPS_SAFE_COMMANDS,
    contains_dangerous_patterns,
    is_shell_command_allowed,
)


class TestContainsDangerousPatterns:
    """Tests for the contains_dangerous_patterns function."""

    @pytest.mark.parametrize(
        "command",
        [
            "echo $(whoami)",
            "echo `hostname`",
            "cat file > /etc/passwd",
            "cat file >> /tmp/log",
            "read -r line < /etc/shadow",
            "cat <<EOF\nmalicious\nEOF",
            "ls >(tee log)",
            "cat <(ls)",
            "echo ${HOME}",
            "echo $HOME",
            "sleep 10 &",
            "echo $'\\x41'",
            "echo <<<'input'",
            "echo hello\nrm -rf /",
        ],
    )
    def test_dangerous_patterns_detected(self, command):
        assert contains_dangerous_patterns(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            "ls -la",
            "cat README.md",
            "terraform validate -json",
            "helm lint ./chart",
            "kubectl get pods -n default",
            "git status",
            "grep -r TODO src/",
            "find . -name '*.py'",
            "echo hello && echo world",
        ],
    )
    def test_safe_commands_pass(self, command):
        assert contains_dangerous_patterns(command) is False

    def test_double_ampersand_not_flagged(self):
        """&& should NOT be flagged as a background process."""
        assert contains_dangerous_patterns("ls && cat file") is False

    def test_single_ampersand_is_flagged(self):
        """Single & (background) should be flagged."""
        assert contains_dangerous_patterns("sleep 60 &") is True


class TestIsShellCommandAllowed:
    """Tests for the is_shell_command_allowed function."""

    def test_empty_allow_list_rejects_all(self):
        assert is_shell_command_allowed("ls", []) is False
        assert is_shell_command_allowed("ls", None) is False

    def test_empty_command_rejected(self):
        assert is_shell_command_allowed("", ["ls"]) is False
        assert is_shell_command_allowed("   ", ["ls"]) is False

    def test_exact_prefix_match(self):
        allow_list = ["terraform validate", "terraform fmt"]
        assert is_shell_command_allowed("terraform validate -json", allow_list) is True
        assert is_shell_command_allowed("terraform fmt .", allow_list) is True
        assert is_shell_command_allowed("terraform apply", allow_list) is False

    def test_single_word_prefix(self):
        allow_list = ["git", "ls", "cat"]
        assert is_shell_command_allowed("git status", allow_list) is True
        assert is_shell_command_allowed("git commit -m 'msg'", allow_list) is True
        assert is_shell_command_allowed("ls -la /tmp", allow_list) is True
        assert is_shell_command_allowed("rm -rf /", allow_list) is False

    def test_compound_commands_all_must_match(self):
        allow_list = ["ls", "cat"]
        assert is_shell_command_allowed("ls -la && cat file.txt", allow_list) is True
        assert is_shell_command_allowed("ls -la && rm -rf /", allow_list) is False

    def test_pipe_commands_all_must_match(self):
        allow_list = ["cat", "grep", "sort"]
        assert is_shell_command_allowed("cat file | grep TODO | sort", allow_list) is True
        assert is_shell_command_allowed("cat file | rm -rf /", allow_list) is False

    def test_dangerous_patterns_rejected_even_if_prefix_matches(self):
        allow_list = ["ls"]
        assert is_shell_command_allowed("ls $(whoami)", allow_list) is False
        assert is_shell_command_allowed("ls `hostname`", allow_list) is False

    def test_devops_safe_commands_constant_not_empty(self):
        """Verify the DEVOPS_SAFE_COMMANDS list is populated."""
        assert len(DEVOPS_SAFE_COMMANDS) > 10
        assert "terraform validate" in DEVOPS_SAFE_COMMANDS
        assert "helm lint" in DEVOPS_SAFE_COMMANDS
        assert "kubectl get" in DEVOPS_SAFE_COMMANDS

    def test_devops_destructive_commands_constant_not_empty(self):
        """Verify the DEVOPS_DESTRUCTIVE_COMMANDS list is populated."""
        assert len(DEVOPS_DESTRUCTIVE_COMMANDS) > 5
        assert "terraform apply" in DEVOPS_DESTRUCTIVE_COMMANDS
        assert "kubectl delete" in DEVOPS_DESTRUCTIVE_COMMANDS
        assert "helm uninstall" in DEVOPS_DESTRUCTIVE_COMMANDS
