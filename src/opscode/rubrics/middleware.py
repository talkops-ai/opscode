"""Re-export RubricMiddleware from opscode middleware registry."""

from opscode.middleware.reliable_rubric import ReliableRubricMiddleware as RubricMiddleware

__all__ = ["RubricMiddleware"]
