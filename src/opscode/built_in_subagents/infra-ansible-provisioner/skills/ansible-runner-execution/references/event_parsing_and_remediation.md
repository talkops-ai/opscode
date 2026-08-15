# Event Parsing and Self-Healing Remediation Guide

Parsing Ansible Runner event artifacts from `/artifacts/<job_id>/job_events/` for event-driven feedback loops and self-healing pipelines.

## Artifact Directory Structure

After execution completes, Ansible Runner records outputs under `artifacts/<job_id>/`:

- `status`: String state (`successful`, `failed`, `unreachable`).
- `rc`: Exit code integer (`0` for success).
- `stdout`: Raw text console output.
- `job_events/*.json`: Sequential event JSON records.

---

## Core Event Types

Every task invocation generates structured JSON event records in `job_events/`:

| Event Identifier | Description | Key Result Fields |
|------------------|-------------|-------------------|
| `runner_on_ok` | Task completed cleanly or made a change (`changed: true/false`) | `event_data.res.changed`, `event_data.task` |
| `runner_on_failed` | Task failed execution | `event_data.res.msg`, `event_data.res.stdout`, `event_data.res.module_stderr`, `event_data.task` |
| `runner_on_unreachable` | Host connection failed (SSH/WinRM timeout/auth error) | `event_data.res.unreachable`, `event_data.host` |
| `playbook_on_stats` | Final playbook execution summary stats | `event_data.ok`, `event_data.failures`, `event_data.unreachable` |

---

## Event JSON Schema Example (`runner_on_failed`)

```json
{
  "event": "runner_on_failed",
  "uuid": "8c5e1234-5678-90ab-cdef-1234567890ab",
  "counter": 14,
  "created": "2025-02-23T12:00:00.123456",
  "event_data": {
    "playbook": "site.yml",
    "play": "Configure Web Servers",
    "task": "Ensure Nginx service is running",
    "role": "nginx",
    "host": "web01.prod.example.com",
    "remote_addr": "192.168.1.50",
    "res": {
      "msg": "Job for nginx.service failed because the control process exited with error code.",
      "rc": 1,
      "stdout": "",
      "stderr": "nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)",
      "changed": false
    }
  }
}
```

---

## Event-Driven Self-Healing Pipeline Workflow

1. Read `artifacts/<job_id>/status`. If `failed`:
2. Scan `job_events/*.json` for `event == "runner_on_failed"` or `event == "runner_on_unreachable"`.
3. Extract `event_data.host`, `event_data.task`, and `event_data.res.msg`.
4. Apply targeted remediation:
   - For `Address already in use`: Trigger service port cleanup / process kill playbook.
   - For `unreachable`: Check cloud instance status / reboot target node.
   - For `Permission denied`: Refresh SSH keys / credentials in `env/passwords`.
5. Trigger automated re-execution via Ansible Runner.
