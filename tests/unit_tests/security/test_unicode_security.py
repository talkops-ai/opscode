"""Unit tests for unicode_security module — detection, sanitization, and URL safety."""

import pytest

from opscode.security.unicode_security import (
    CONFUSABLES,
    UnicodeIssue,
    UrlSafetyResult,
    check_url_safety,
    detect_dangerous_unicode,
    format_warning_detail,
    iter_string_values,
    looks_like_url_key,
    render_with_unicode_markers,
    sanitize_control_chars,
    strip_dangerous_unicode,
    summarize_issues,
)


class TestDetectDangerousUnicode:
    """Tests for detect_dangerous_unicode."""

    def test_clean_text_returns_empty(self):
        assert detect_dangerous_unicode("Hello, world!") == []
        assert detect_dangerous_unicode("terraform apply -auto-approve") == []

    def test_detects_bidi_override(self):
        """RTL override (U+202E) should be detected."""
        text = "normal\u202eevil"
        issues = detect_dangerous_unicode(text)
        assert len(issues) >= 1
        assert any("U+202E" in i.codepoint for i in issues)

    def test_detects_zero_width_space(self):
        text = "hello\u200bworld"
        issues = detect_dangerous_unicode(text)
        assert len(issues) == 1
        assert issues[0].codepoint == "U+200B"

    def test_detects_zero_width_joiner(self):
        text = "file\u200dname"
        issues = detect_dangerous_unicode(text)
        assert len(issues) == 1
        assert issues[0].codepoint == "U+200D"

    def test_detects_bom(self):
        text = "\uFEFFHello"
        issues = detect_dangerous_unicode(text)
        assert len(issues) == 1
        assert issues[0].codepoint == "U+FEFF"

    def test_detects_soft_hyphen(self):
        text = "in\u00ADvisible"
        issues = detect_dangerous_unicode(text)
        assert len(issues) == 1
        assert issues[0].codepoint == "U+00AD"


class TestStripDangerousUnicode:
    def test_removes_dangerous_chars(self):
        result = strip_dangerous_unicode("hello\u200b\u202eworld")
        assert "\u200b" not in result
        assert "\u202e" not in result
        assert result == "helloworld"

    def test_preserves_normal_text(self):
        text = "Normal ASCII and émojis 🎉"
        assert strip_dangerous_unicode(text) == text


class TestSanitizeControlChars:
    def test_basic_sanitization(self):
        text = "hello\x00world"
        result = sanitize_control_chars(text)
        assert "\x00" not in result
        assert "hello" in result and "world" in result

    def test_keep_newlines(self):
        text = "line1\nline2"
        result = sanitize_control_chars(text, keep_newlines=True)
        assert "\n" in result

    def test_collapse_whitespace(self):
        text = "hello    world"
        result = sanitize_control_chars(text, collapse_whitespace=True)
        assert result == "hello world"

    def test_max_length(self):
        text = "a" * 200
        result = sanitize_control_chars(text, max_length=50)
        assert len(result) == 50
        assert result.endswith("…")


class TestRenderWithUnicodeMarkers:
    def test_normal_text_unchanged(self):
        text = "Hello, world!"
        assert render_with_unicode_markers(text) == text

    def test_dangerous_chars_annotated(self):
        text = "hello\u200bworld"
        result = render_with_unicode_markers(text)
        assert "U+200B" in result
        assert "ZERO WIDTH SPACE" in result


class TestSummarizeIssues:
    def test_few_issues(self):
        issues = [
            UnicodeIssue(position=0, character="\u200b", codepoint="U+200B", name="ZERO WIDTH SPACE"),
        ]
        result = summarize_issues(issues)
        assert "U+200B ZERO WIDTH SPACE" in result

    def test_many_issues_truncated(self):
        issues = [
            UnicodeIssue(position=i, character=chr(cp), codepoint=f"U+{cp:04X}",
                         name=f"CHAR_{i}")
            for i, cp in enumerate([0x200B, 0x200C, 0x200D, 0x200E, 0x200F])
        ]
        result = summarize_issues(issues, max_items=2)
        assert "+3 more" in result


class TestFormatWarningDetail:
    def test_few_warnings(self):
        warnings = ("Warning A", "Warning B")
        assert "Warning A" in format_warning_detail(warnings)
        assert "Warning B" in format_warning_detail(warnings)

    def test_many_warnings_truncated(self):
        warnings = ("A", "B", "C", "D")
        result = format_warning_detail(warnings, max_shown=2)
        assert "+2 more" in result


class TestCheckUrlSafety:
    def test_clean_url_is_safe(self):
        result = check_url_safety("https://example.com/page")
        assert result.safe is True
        assert len(result.warnings) == 0

    def test_url_with_bidi_is_unsafe(self):
        result = check_url_safety("https://example\u202e.com")
        assert result.safe is False
        assert len(result.issues) > 0

    def test_mixed_script_domain_flagged(self):
        # Cyrillic 'а' mixed with Latin in domain
        result = check_url_safety("https://exаmple.com")
        assert result.safe is False
        assert any("confusable" in w.lower() or "mixes scripts" in w.lower() for w in result.warnings)

    def test_localhost_treated_as_local(self):
        result = check_url_safety("http://localhost:8080/api")
        assert result.safe is True

    def test_ip_address_treated_as_local(self):
        result = check_url_safety("http://192.168.1.1:3000/")
        assert result.safe is True

    def test_no_hostname(self):
        result = check_url_safety("file:///etc/passwd")
        assert result.decoded_domain is None


class TestIterStringValues:
    def test_flat_dict(self):
        data = {"url": "https://example.com", "name": "test"}
        values = iter_string_values(data)
        assert ("url", "https://example.com") in values
        assert ("name", "test") in values

    def test_nested_dict(self):
        data = {"config": {"endpoint": "https://api.example.com"}}
        values = iter_string_values(data)
        assert ("config.endpoint", "https://api.example.com") in values

    def test_list_values(self):
        data = {"urls": ["https://a.com", "https://b.com"]}
        values = iter_string_values(data)
        assert ("urls[0]", "https://a.com") in values
        assert ("urls[1]", "https://b.com") in values


class TestLooksLikeUrlKey:
    def test_url_keys(self):
        assert looks_like_url_key("url") is True
        assert looks_like_url_key("uri") is True
        assert looks_like_url_key("href") is True
        assert looks_like_url_key("config.base_url") is True
        assert looks_like_url_key("endpoint") is True

    def test_non_url_keys(self):
        assert looks_like_url_key("name") is False
        assert looks_like_url_key("command") is False
        assert looks_like_url_key("output") is False
