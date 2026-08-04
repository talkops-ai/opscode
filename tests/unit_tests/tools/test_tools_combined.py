import pytest
from unittest.mock import MagicMock, patch
from langchain.tools import ToolRuntime
import shlex

from dcoder.tools.fetch_url import fetch_url
from dcoder.security.url_validation import _is_blocked_ip
from dcoder.tools.devops.terraform import create_terraform_validate_tool, create_terraform_plan_tool
from dcoder.tools.devops.helm import create_helm_lint_tool
from dcoder.tools.devops.kubectl import create_kubectl_get_tool
from dcoder.tools.devops.ansible import create_ansible_check_tool
from dcoder.tools.devops.argocd import create_argocd_diff_tool
import ipaddress

def test_ssrf_blocked_ips():
    # Loopback
    assert _is_blocked_ip(ipaddress.ip_address("127.0.0.1"))
    assert _is_blocked_ip(ipaddress.ip_address("::1"))
    
    # Private networks
    assert _is_blocked_ip(ipaddress.ip_address("10.0.0.1"))
    assert _is_blocked_ip(ipaddress.ip_address("192.168.1.100"))
    assert _is_blocked_ip(ipaddress.ip_address("172.16.0.50"))
    
    # Link local (cloud IMDS)
    assert _is_blocked_ip(ipaddress.ip_address("169.254.169.254"))
    
    # Public (allowed)
    assert not _is_blocked_ip(ipaddress.ip_address("8.8.8.8"))
    assert not _is_blocked_ip(ipaddress.ip_address("1.1.1.1"))

def test_fetch_url_ssrf_validation():
    # Fetching a loopback URL should return validation error immediately
    from typing import Any, cast
    res = cast(Any, fetch_url).func("http://127.0.0.1/metadata")
    assert "error" in res
    assert res["category"] == "validation"
    assert "resolves to blocked address" in res["error"]


