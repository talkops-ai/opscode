---
name: ansible-runner-execution
description: >-
  Production playbook execution via Ansible Runner and Ansible Navigator, covering
  private_data_dir structure, inventory mapping, environment configuration,
  artifact consumption, and event-driven remediation. Use when: (1) structuring
  the private_data_dir for Ansible Runner (/project, /inventory, /env/settings,
  /env/envvars, /env/extravars), (2) executing playbooks via ansible_navigator
  MCP tool, (3) parsing execution artifacts from /artifacts for task-level
  success/failure events, (4) consuming runner_on_ok, runner_on_failed, and
  runner_on_unreachable events, or (5) implementing self-healing deployment
  pipelines based on failure event data. Do NOT use for writing playbook logic
  (use ansible-code-authoring) or linting (use ansible-linting-remediation).
license: MIT
compatibility: designed for opscode
---

# Ansible Runner & Navigator Execution

Manage containerised Ansible playbook execution, directory structure (`private_data_dir`), environment configuration, and event-driven self-healing pipeline integration using Ansible Runner and Ansible Navigator.

---

## Workflow Decision Tree

```
1. Directory Structure Setup (private_data_dir)
   ├── Create /project (playbooks, roles, collections)
   ├── Create /inventory (hosts, group_vars)
   ├── Configure /env (settings, envvars, extravars, passwords)
   └── Refer to [references/private_data_dir_structure.md](references/private_data_dir_structure.md) for specifications
2. Playbook Execution via MCP Tool
   ├── Invoke 'ansible_navigator' MCP tool
   ├── Specify Execution Environment container image and inventory path
   └── Refer to [references/mcp_navigator_integration.md](references/mcp_navigator_integration.md) for parameters
3. Artifact & Event Consumption
   ├── Inspect /artifacts/<job_id>/status and stdout
   ├── Parse granular JSON events in /artifacts/<job_id>/job_events/
   ├── Filter by event types ('runner_on_failed', 'runner_on_unreachable')
   └── Refer to [references/event_parsing_and_remediation.md](references/event_parsing_and_remediation.md) for event schemas
4. Event-Driven Self-Healing Pipeline
   ├── Extract failing module, task name, and stderr error message
   ├── Trigger automated corrective playbooks or credential refreshes
   └── Re-run Ansible Runner execution to verify resolution
```

---

## 1. Private Data Directory Structuring

Ansible Runner requires a clean `private_data_dir` tree:

- `/project`: Playbooks and roles.
- `/inventory`: Inventory host definitions.
- `/env`: Configuration parameters (`settings`), environment variables (`envvars`), extra vars (`extravars`).
- `/artifacts`: Execution logs and event stream JSON output.

See [references/private_data_dir_structure.md](references/private_data_dir_structure.md) for complete details.

---

## 2. Playbook Execution (`ansible_navigator`)

When executing playbooks:

1. Target the prepared `private_data_dir`.
2. Select appropriate Execution Environment container image.
3. Pass inventory and extra variables via the `ansible_navigator` tool.

See [references/mcp_navigator_integration.md](references/mcp_navigator_integration.md) for usage patterns.

---

## 3. Artifact Consumption & Self-Healing Pipelines

Inspect task-level event streams recorded under `/artifacts/<job_id>/job_events/`:

- `runner_on_ok`: Successful task completion.
- `runner_on_failed`: Task execution failure. Extract `res.msg` and `res.stderr` for automated repair.
- `runner_on_unreachable`: Node connection failure. Initiate automated network or credential recovery.

See [references/event_parsing_and_remediation.md](references/event_parsing_and_remediation.md) for parsing schemas and event handling strategies.
