"""Re-export RubricMiddleware from dcoder middleware registry."""

from dcoder.middleware.reliable_rubric import ReliableRubricMiddleware as RubricMiddleware

__all__ = ["RubricMiddleware"]
