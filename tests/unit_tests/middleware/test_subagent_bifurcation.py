from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

from dcoder.middleware.subagents import SubagentsMiddleware
from dcoder.middleware.unified_system_message import UnifiedSystemMessageMiddleware
from dcoder.subagents.types import SubagentMetadata


def test_subagent_prompt_dynamic_bifurcation() -> None:
    """Verify system prompt block dynamically categorizes built-in vs plugin subagents."""
    built_in_meta: SubagentMetadata = {
        "name": "aws-terraform-writer",
        "description": "Generates AWS Terraform modules",
        "system_prompt": "Built-in prompt",
        "source": "built-in",
        "path": "/built_in/aws-terraform-writer/AGENTS.md",
        "skills": ["aws-terraform-module-writer"],
    }
    plugin_meta: SubagentMetadata = {
        "name": "terraform-linter@devops-terraform-toolkit",
        "description": "Lints and validates Terraform configurations",
        "system_prompt": "Plugin prompt",
        "source": "plugin:terraform-linter@devops-terraform-toolkit",
        "path": "/plugin/terraform-linter/AGENTS.md",
        "skills": ["terraform-linter:*"],
    }

    middleware = SubagentsMiddleware(subagent_metas=[built_in_meta, plugin_meta])
    prompt_block = middleware._build_prompt_block()

    # Check main header
    assert "## Subagent Delegation & Orchestration Architecture" in prompt_block

    # Check Built-in section
    assert "### 1. Built-in Subagents (Direct `task` Tool)" in prompt_block
    assert "- **`aws-terraform-writer`**: Generates AWS Terraform modules" in prompt_block
    assert 'task(description="...", subagent_type="<subagent_name>")' in prompt_block

    # Check Plugin section
    assert "### 2. Plugin & Extension Subagents (Code Interpreter `js_eval`)" in prompt_block
    assert "- **`terraform-linter@devops-terraform-toolkit`**: Lints and validates Terraform configurations" in prompt_block
    assert "Source: `plugin:terraform-linter@devops-terraform-toolkit`" in prompt_block
    assert "Skills: `terraform-linter:*`" in prompt_block
    assert 'subagentType: "<subagent_name@plugin_id>"' in prompt_block

    # Check Automatic Routing Rules
    assert "### Automatic Routing Rules (Zero User Intervention)" in prompt_block
    assert "Built-in Subagents" in prompt_block
    assert "Plugin & Extension Subagents" in prompt_block
    assert "Promise.all" in prompt_block


def test_subagent_prompt_builtin_only() -> None:
    """Verify system prompt block when only built-in subagents exist."""
    built_in_meta: SubagentMetadata = {
        "name": "k8s-auditor",
        "description": "Audits Kubernetes manifests",
        "system_prompt": "K8s prompt",
        "source": "built-in",
        "path": "/built_in/k8s-auditor/AGENTS.md",
    }

    middleware = SubagentsMiddleware(subagent_metas=[built_in_meta])
    prompt_block = middleware._build_prompt_block()

    assert "### 1. Built-in Subagents (Direct `task` Tool)" in prompt_block
    assert "k8s-auditor" in prompt_block
    assert "### 2. Plugin & Extension Subagents" not in prompt_block


def test_subagent_prompt_plugin_only() -> None:
    """Verify system prompt block when only plugin subagents exist."""
    plugin_meta: SubagentMetadata = {
        "name": "sec-scanner@security-plugin",
        "description": "Scans containers for vulnerabilities",
        "system_prompt": "Sec prompt",
        "source": "plugin:security-plugin",
        "path": "/plugin/sec-scanner/AGENTS.md",
    }

    middleware = SubagentsMiddleware(subagent_metas=[plugin_meta])
    prompt_block = middleware._build_prompt_block()

    assert "### 1. Built-in Subagents" not in prompt_block
    assert "### 2. Plugin & Extension Subagents (Code Interpreter `js_eval`)" in prompt_block
    assert "sec-scanner@security-plugin" in prompt_block


def test_subagents_middleware_wrap_model_call() -> None:
    """Verify wrap_model_call appends system prompt block to ModelRequest."""
    built_in_meta: SubagentMetadata = {
        "name": "helm-validator",
        "description": "Validates Helm charts",
        "system_prompt": "Helm prompt",
        "source": "built-in",
        "path": "/built_in/helm-validator/AGENTS.md",
    }
    middleware = SubagentsMiddleware(subagent_metas=[built_in_meta])

    base_system_message = SystemMessage(content="You are a helpful assistant.")
    request = ModelRequest(
        messages=[],
        system_message=base_system_message,
        model=cast(Any, "test-model"),
    )

    def dummy_handler(req: ModelRequest[Any]) -> ModelResponse[Any]:
        return ModelResponse(result=cast(Any, []))

    # Sync wrap_model_call
    middleware.wrap_model_call(request, dummy_handler)
    assert request.system_message is not None

    # Retrieve modified system message from handler invocation
    last_req: ModelRequest[Any] | None = None

    def capturing_handler(req: ModelRequest[Any]) -> ModelResponse[Any]:
        nonlocal last_req
        last_req = req
        return ModelResponse(result=cast(Any, []))

    middleware.wrap_model_call(request, capturing_handler)
    assert last_req is not None
    assert last_req.system_message is not None
    assert "You are a helpful assistant." in str(last_req.system_message.content)
    assert "## Subagent Delegation & Orchestration Architecture" in str(last_req.system_message.content)
    assert "helm-validator" in str(last_req.system_message.content)


@pytest.mark.asyncio
async def test_subagents_middleware_awrap_model_call() -> None:
    """Verify awrap_model_call appends system prompt block asynchronously."""
    plugin_meta: SubagentMetadata = {
        "name": "tf-linter@tf-plugin",
        "description": "Lints terraform files",
        "system_prompt": "TF prompt",
        "source": "plugin:tf-plugin",
        "path": "/plugin/tf-linter/AGENTS.md",
    }
    middleware = SubagentsMiddleware(subagent_metas=[plugin_meta])

    base_system_message = SystemMessage(content="Async base prompt")
    request = ModelRequest(
        messages=[],
        system_message=base_system_message,
        model=cast(Any, "test-model"),
    )

    last_req: ModelRequest[Any] | None = None

    async def capturing_handler(req: ModelRequest[Any]) -> ModelResponse[Any]:
        nonlocal last_req
        last_req = req
        return ModelResponse(result=cast(Any, []))

    await middleware.awrap_model_call(request, capturing_handler)
    assert last_req is not None
    assert last_req.system_message is not None
    assert "Async base prompt" in str(last_req.system_message.content)
    assert "## Subagent Delegation & Orchestration Architecture" in str(last_req.system_message.content)
    assert "tf-linter@tf-plugin" in str(last_req.system_message.content)


def test_unified_system_message_preserves_bifurcation() -> None:
    """Verify UnifiedSystemMessageMiddleware collapses bifurcated system message into a single string."""
    builtin_meta: SubagentMetadata = {
        "name": "builtin-sub",
        "description": "built-in",
        "system_prompt": "Prompt",
        "source": "built-in",
        "path": "/builtin/path",
    }
    plugin_meta: SubagentMetadata = {
        "name": "plugin-sub@plugin",
        "description": "plugin",
        "system_prompt": "Prompt",
        "source": "plugin:plugin",
        "path": "/plugin/path",
    }
    subagents_mw = SubagentsMiddleware(subagent_metas=[builtin_meta, plugin_meta])
    unified_mw = UnifiedSystemMessageMiddleware()

    req = ModelRequest(
        messages=[],
        system_message=SystemMessage(content="Initial system prompt."),
        model=cast(Any, "test-model"),
    )

    final_request: ModelRequest[Any] | None = None

    def final_handler(r: ModelRequest[Any]) -> ModelResponse[Any]:
        nonlocal final_request
        final_request = r
        return ModelResponse(result=cast(Any, []))

    # Pipeline wrapper simulating request flow through SubagentsMiddleware -> UnifiedSystemMessageMiddleware
    def middleware_pipeline(r: ModelRequest[Any]) -> ModelResponse[Any]:
        res = subagents_mw.wrap_model_call(
            r,
            lambda r2: cast(
                ModelResponse[Any],
                unified_mw.wrap_model_call(r2, final_handler),
            ),
        )
        return cast(ModelResponse[Any], res)

    middleware_pipeline(req)

    assert final_request is not None
    system_msg = final_request.system_message
    assert system_msg is not None
    assert isinstance(system_msg.content, str)
    assert "Initial system prompt." in system_msg.content
    assert "## Subagent Delegation & Orchestration Architecture" in system_msg.content
    assert "1. Built-in Subagents (Direct `task` Tool)" in system_msg.content
    assert "builtin-sub" in system_msg.content
    assert "2. Plugin & Extension Subagents (Code Interpreter `js_eval`)" in system_msg.content
    assert "plugin-sub@plugin" in system_msg.content


def test_subagent_state_injection_with_is_plugin() -> None:
    """Verify state update from before_agent includes is_plugin classification flag."""
    builtin_meta: SubagentMetadata = {
        "name": "built-in-agent",
        "description": "built-in",
        "system_prompt": "Prompt",
        "source": "built-in",
        "path": "/builtin/path",
    }
    plugin_meta: SubagentMetadata = {
        "name": "plugin-agent@ext",
        "description": "plugin",
        "system_prompt": "Prompt",
        "source": "plugin:ext",
        "path": "/plugin/path",
    }
    mw = SubagentsMiddleware(subagent_metas=[builtin_meta, plugin_meta])

    state_update = mw.before_agent(state=cast(Any, {}), runtime=MagicMock())
    assert state_update is not None
    registry = state_update.get("_subagent_registry", {})

    assert registry["built-in-agent"]["is_plugin"] is False
    assert registry["plugin-agent@ext"]["is_plugin"] is True
