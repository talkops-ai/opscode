"""Unit tests for DevOps tools with backend and subprocess execution fallbacks."""

from unittest.mock import MagicMock
from dcoder.tools.devops.terraform import (
    create_terraform_validate_tool,
    create_terraform_plan_tool,
    create_terraform_fmt_tool,
)
from dcoder.tools.devops.helm import create_helm_lint_tool, create_helm_template_tool
from dcoder.tools.devops.kubectl import create_kubectl_get_tool
from dcoder.tools.devops.ansible import create_ansible_check_tool
from dcoder.tools.devops.argocd import create_argocd_diff_tool


def test_devops_tools_with_mock_backend():
    """Verify that DevOps tools invoke backend.execute when backend is supplied."""
    backend = MagicMock()
    backend.execute.return_value = MagicMock(output="success", exit_code=0)

    t1 = create_terraform_validate_tool(backend)
    res = t1.invoke({"directory": "."})
    assert res["output"] == "success"
    assert backend.execute.called

    backend.reset_mock()
    t2 = create_helm_lint_tool(backend)
    res = t2.invoke({"directory": "."})
    assert res["output"] == "success"
    assert backend.execute.called


def test_devops_tools_with_none_backend_fallback(tmp_path):
    """Verify that DevOps tools fall back to subprocess when backend is None."""
    t1 = create_terraform_validate_tool(None)
    res = t1.invoke({"directory": str(tmp_path)})
    assert "output" in res
    assert "exit_code" in res
