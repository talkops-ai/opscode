from unittest.mock import MagicMock
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest
from opscode.middleware.registry import MiddlewareRegistry
from opscode.middleware.configurable_model import ConfigurableModelMiddleware

def test_middleware_registry():
    registry = MiddlewareRegistry()

    class MiddlewareA(AgentMiddleware):
        pass

    class MiddlewareB(AgentMiddleware):
        pass

    registry.register("middleware_b", MiddlewareB)
    registry.register("middleware_a", MiddlewareA)

    stack = registry.build_stack()
    assert len(stack) == 2
    assert isinstance(stack[0], MiddlewareB)
    assert isinstance(stack[1], MiddlewareA)


def test_configurable_model_middleware():
    mw = ConfigurableModelMiddleware(persist_model_state=False)  # type: ignore[reportCallIssue]
    
    mock_model = MagicMock()
    mock_model.name = "original-model"
    
    request = ModelRequest(
        model=mock_model,
        messages=[],
        model_settings={},
        system_prompt="system",
        runtime=MagicMock(),
    )
    
    # Test no overrides
    request.runtime.context = None
    resolved_req, resolved_spec, resolved_params = mw._apply_overrides(request)
    assert resolved_req.model == mock_model
    assert resolved_spec is None
    assert resolved_params is None
