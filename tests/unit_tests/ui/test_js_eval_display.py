"""Unit tests for JS Interpreter (_js_eval_display) output parser."""

from opscode.ui.widgets._js_eval_display import (
    JsEvalError,
    JsEvalResult,
    JsEvalStdout,
    parse_js_eval_blocks,
    unescape_js_eval_text,
)


def test_unescape_js_eval_text():
    """Verify XML escaping reversal for JS eval text."""
    escaped = "&lt;div&gt;&amp;hello&lt;/div&gt;"
    assert unescape_js_eval_text(escaped) == "<div>&hello</div>"


def test_parse_js_eval_blocks_plain_result():
    """Verify parsing a plain result block without stdout."""
    raw_output = '<result kind="handle">42</result>'
    blocks = parse_js_eval_blocks(raw_output)
    assert blocks is not None
    assert len(blocks) == 1
    res = blocks[0]
    assert isinstance(res, JsEvalResult)
    assert res.kind == "handle"
    assert res.body == "42"


def test_parse_js_eval_blocks_stdout_and_result():
    """Verify parsing stdout block followed by result block."""
    raw_output = "<stdout>\nHello World\n</stdout>\n<result kind=\"\">true</result>"
    blocks = parse_js_eval_blocks(raw_output)
    assert blocks is not None
    assert len(blocks) == 2

    stdout = blocks[0]
    assert isinstance(stdout, JsEvalStdout)
    assert stdout.body == "Hello World"

    res = blocks[1]
    assert isinstance(res, JsEvalResult)
    assert res.body == "true"


def test_parse_js_eval_blocks_error():
    """Verify parsing an error block with error_type."""
    raw_output = '<error type="ReferenceError">foo is not defined\n    at &lt;anonymous&gt;:1:1</error>'
    blocks = parse_js_eval_blocks(raw_output)
    assert blocks is not None
    assert len(blocks) == 1

    err = blocks[0]
    assert isinstance(err, JsEvalError)
    assert err.error_type == "ReferenceError"
    assert "foo is not defined" in err.body
    assert "<anonymous>" in err.body


def test_parse_js_eval_blocks_invalid_format():
    """Verify invalid format returns None."""
    assert parse_js_eval_blocks("plain unformatted string") is None
    assert parse_js_eval_blocks("<stdout>unclosed stdout") is None
