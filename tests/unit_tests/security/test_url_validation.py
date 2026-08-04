"""Unit tests for URL validation — SSRF protection, DNS pinning, blocked IPs."""

import ipaddress

import pytest

from dcoder.security.url_validation import (
    _UrlValidationError,
    _is_blocked_ip,
    _validate_url,
)


class TestIsBlockedIp:
    """Tests for _is_blocked_ip."""

    def test_loopback_ipv4_blocked(self):
        assert _is_blocked_ip(ipaddress.ip_address("127.0.0.1")) is True

    def test_loopback_ipv6_blocked(self):
        assert _is_blocked_ip(ipaddress.ip_address("::1")) is True

    def test_private_10_blocked(self):
        assert _is_blocked_ip(ipaddress.ip_address("10.0.0.1")) is True
        assert _is_blocked_ip(ipaddress.ip_address("10.255.255.255")) is True

    def test_private_192_168_blocked(self):
        assert _is_blocked_ip(ipaddress.ip_address("192.168.1.100")) is True

    def test_private_172_16_blocked(self):
        assert _is_blocked_ip(ipaddress.ip_address("172.16.0.50")) is True

    def test_link_local_cloud_imds_blocked(self):
        """AWS/GCP/Azure IMDS endpoint must be blocked."""
        assert _is_blocked_ip(ipaddress.ip_address("169.254.169.254")) is True

    def test_public_ips_allowed(self):
        assert _is_blocked_ip(ipaddress.ip_address("8.8.8.8")) is False
        assert _is_blocked_ip(ipaddress.ip_address("1.1.1.1")) is False
        assert _is_blocked_ip(ipaddress.ip_address("142.250.80.46")) is False


class TestValidateUrl:
    """Tests for _validate_url."""

    def test_valid_https_url(self):
        # Should not raise
        _validate_url("https://example.com/page")

    def test_valid_http_url(self):
        _validate_url("http://example.com/page")

    def test_rejects_blocked_schemes(self):
        with pytest.raises(_UrlValidationError):
            _validate_url("file:///etc/passwd")

    def test_rejects_no_hostname(self):
        with pytest.raises(_UrlValidationError):
            _validate_url("https://")

    def test_rejects_loopback(self):
        with pytest.raises(_UrlValidationError):
            _validate_url("http://127.0.0.1/metadata")

    def test_rejects_imds_endpoint(self):
        """SSRF protection: cloud metadata service must be blocked."""
        with pytest.raises(_UrlValidationError):
            _validate_url("http://169.254.169.254/latest/meta-data/")
