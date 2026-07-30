import pytest
from unittest.mock import MagicMock, patch
from langchain.tools import ToolRuntime
import shlex

from dcoder.tools.fetch_url import fetch_url
from dcoder.security.url_validation import _is_blocked_ip
from dcoder.tools.devops.terraform import terraform_validate, terraform_plan
from dcoder.tools.devops.helm import helm_lint
from dcoder.tools.devops.kubectl import kubectl_get
from dcoder.tools.devops.ansible import ansible_check
from dcoder.tools.devops.argocd import argocd_diff
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
    res = fetch_url.func("http://127.0.0.1/metadata")
    assert "error" in res
    assert res["category"] == "validation"
    assert "resolves to blocked address" in res["error"]

def test_terraform_validate_tool():
    mock_backend = MagicMock()
    mock_res = MagicMock()
    mock_res.output = '{"valid": true}'
    mock_res.exit_code = 0
    mock_backend.execute.return_value = mock_res
    
    runtime = MagicMock(spec=ToolRuntime)
    runtime.backend = mock_backend
    
    res = terraform_validate.func(directory="/path/to/tf", runtime=runtime)
    
    assert res["exit_code"] == 0
    assert res["output"] == '{"valid": true}'
    mock_backend.execute.assert_called_once_with("cd /path/to/tf && terraform validate -json")

def test_kubectl_get_tool():
    mock_backend = MagicMock()
    mock_res = MagicMock()
    mock_res.output = "running pods"
    mock_res.exit_code = 0
    mock_backend.execute.return_value = mock_res
    
    runtime = MagicMock(spec=ToolRuntime)
    runtime.backend = mock_backend
    
    res = kubectl_get.func(resource="pods", namespace="default", runtime=runtime)
    
    assert res["exit_code"] == 0
    mock_backend.execute.assert_called_once_with("kubectl get pods -n default")

def test_kubectl_logs_with_container():
    from dcoder.tools.devops.kubectl import kubectl_logs
    mock_backend = MagicMock()
    mock_res = MagicMock()
    mock_res.output = "logs output"
    mock_res.exit_code = 0
    mock_backend.execute.return_value = mock_res
    
    runtime = MagicMock(spec=ToolRuntime)
    runtime.backend = mock_backend
    
    res = kubectl_logs.func(pod_name="my-pod", namespace="my-ns", container="my-container", runtime=runtime)
    assert res["exit_code"] == 0
    mock_backend.execute.assert_called_once_with("kubectl logs my-pod -n my-ns -c my-container")

def test_ansible_check_inventory_fallback(tmp_path):
    from dcoder.tools.devops.ansible import ansible_check
    
    playbook_file = tmp_path / "playbook.yml"
    playbook_file.write_text("---")
    
    # Create a default hosts file in the playbook's directory
    hosts_file = tmp_path / "hosts"
    hosts_file.write_text("[all]")
    
    mock_backend = MagicMock()
    mock_res = MagicMock()
    mock_res.output = "ansible-check output"
    mock_res.exit_code = 0
    mock_backend.execute.return_value = mock_res
    
    runtime = MagicMock(spec=ToolRuntime)
    runtime.backend = mock_backend
    
    res = ansible_check.func(playbook=str(playbook_file), runtime=runtime)
    assert res["exit_code"] == 0
    
    # Verify that it automatically detected the hosts file in the same directory
    expected_cmd = f"ansible-playbook {shlex.quote(str(playbook_file))} -i {shlex.quote(str(hosts_file))} --check"
    mock_backend.execute.assert_called_once_with(expected_cmd)
