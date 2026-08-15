# Ansible Navigator MCP Integration Guide

Executing playbooks and managing execution environments using the `ansible_navigator` MCP tool.

## Execution via `ansible_navigator` Tool

The `ansible_navigator` MCP tool enables containerized playbook execution using execution environments and structured output capture.

### Tool Parameters Overview

- `playbook`: Path to the playbook file (e.g., `project/site.yml`).
- `inventory`: Path to inventory file or inventory directory (e.g., `inventory/hosts.yml`).
- `execution_environment_image`: Container image tag for execution (e.g., `quay.io/ansible/ansible-runner:latest`).
- `mode`: Execution mode (`stdout` for non-interactive automated pipeline runs, `interactive` for TUI).
- `private_data_dir`: Root path of the runner private data directory.
- `extra_vars`: Key-value map or string of extra parameters (`-e`).

### Workflow Example

1. Prepare `private_data_dir` with `project/`, `inventory/`, and `env/` subdirectories.
2. Invoke `ansible_navigator` MCP tool pointing to `private_data_dir`.
3. Inspect generated `artifacts/` for status and event details.
