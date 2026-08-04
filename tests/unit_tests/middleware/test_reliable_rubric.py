"""Unit tests for ReliableRubricMiddleware — transport error detection and message filtering."""

import pytest
import httpx

from dcoder.middleware.reliable_rubric import (
    _exception_chain,
    _is_transient_grader_transport_error,
)


class TestExceptionChain:
    """Tests for _exception_chain traversal."""

    def test_single_exception(self):
        exc = ValueError("test")
        chain = list(_exception_chain(exc))
        assert len(chain) == 1
        assert chain[0] is exc

    def test_chained_exceptions(self):
        inner = ValueError("inner")
        outer = RuntimeError("outer")
        outer.__cause__ = inner
        chain = list(_exception_chain(outer))
        assert len(chain) == 2
        assert outer in chain
        assert inner in chain

    def test_context_exception(self):
        inner = ValueError("inner")
        outer = RuntimeError("outer")
        outer.__context__ = inner
        chain = list(_exception_chain(outer))
        assert len(chain) == 2

    def test_no_duplicate_visits(self):
        exc = ValueError("loop")
        exc.__context__ = exc  # Circular — should not infinite-loop
        chain = list(_exception_chain(exc))
        assert len(chain) == 1


class TestIsTransientGraderTransportError:
    """Tests for _is_transient_grader_transport_error."""

    def test_httpx_read_error(self):
        exc = httpx.ReadError("Connection reset")
        assert _is_transient_grader_transport_error(exc) is True

    def test_httpx_remote_protocol_error(self):
        exc = httpx.RemoteProtocolError("Invalid response")
        assert _is_transient_grader_transport_error(exc) is True

    def test_wrapped_read_error(self):
        inner = httpx.ReadError("Connection reset")
        outer = RuntimeError("Grader failed")
        outer.__cause__ = inner
        assert _is_transient_grader_transport_error(outer) is True

    def test_non_transport_error(self):
        exc = ValueError("Not a transport error")
        assert _is_transient_grader_transport_error(exc) is False

    def test_timeout_error_not_retryable(self):
        exc = httpx.TimeoutException("Connection timed out")
        assert _is_transient_grader_transport_error(exc) is False

    def test_connect_error_not_retryable(self):
        exc = httpx.ConnectError("Connection refused")
        assert _is_transient_grader_transport_error(exc) is False
