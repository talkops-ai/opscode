"""Unit tests for Phase 4 DevOps Visualization Widgets:
- diff.py & devops_renderers.py
- infra_panel.py
- status.py
- tool_renderers.py
- subagent_panel.py
- operation_card.py
"""

from dcoder.ui.devops_renderers import (
    AnsiblePlaybookRenderer,
    HelmDiffRenderer,
    KubectlRenderer,
    TerraformPlanRenderer,
)
from dcoder.ui.diff import compose_diff_lines
from dcoder.ui.infra_panel import InfraStatePanel
from dcoder.ui.operation_card import OperationCard
from dcoder.ui.status import StatusBar
from dcoder.ui.subagent_panel import SubagentPanel
from dcoder.ui.tool_renderers import render_tool_approval


def test_compose_diff_lines():
    diff_input = "--- a/main.tf\n+++ b/main.tf\n@@ -1,3 +1,3 @@\n- old\n+ new"
    widgets = list(compose_diff_lines(diff_input))
    texts = [str(getattr(w, "renderable", getattr(w, "_content", ""))) for w in widgets]
    combined = " ".join(texts)
    assert "old" in combined or any("diff-line-removed" in getattr(w, "classes", set()) for w in widgets)
    assert "new" in combined or any("diff-line-added" in getattr(w, "classes", set()) for w in widgets)


def test_devops_renderers():
    tf_ren = TerraformPlanRenderer()
    tf_out = tf_ren.render("Plan: 1 to add, 0 to change, 0 to destroy.")
    assert "Plan:" in tf_out.plain

    k8s_ren = KubectlRenderer()
    k8s_out = k8s_ren.render("pod/nginx Running 1/1")
    assert "Running" in k8s_out.plain

    ansible_ren = AnsiblePlaybookRenderer()
    ansible_out = ansible_ren.render("TASK [Install terraform] ***")
    assert "TASK" in ansible_out.plain


def test_render_tool_approval():
    res = render_tool_approval("terraform_plan", {"dir": "."})
    assert "Terraform PLAN" in res.title


def test_infra_panel_detection():
    panel = InfraStatePanel()
    ctx = panel._detect_context()
    assert "aws_profile" in ctx
    assert "k8s_context" in ctx


def test_operation_card():
    op = OperationCard("op1", "Terraform Apply")
    assert op.op_name == "Terraform Apply"
    op.append_log("Applying...")
    assert len(op._logs) == 1
