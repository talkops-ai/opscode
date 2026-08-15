# Private Data Directory (`private_data_dir`) Architecture Guide

Complete directory layout and configuration reference for Ansible Runner execution environments.

## Directory Layout Overview

Ansible Runner requires a structured input/output directory known as `private_data_dir`.

```
private_data_dir/
├── project/
│   ├── site.yml
│   ├── playbooks/
│   │   └── deploy.yml
│   └── roles/
├── inventory/
│   ├── hosts.yml
│   └── group_vars/
├── env/
│   ├── settings        # Runner configuration parameters (JSON or YAML)
│   ├── envvars         # Environment variables passed to execution (JSON or YAML)
│   ├── extravars       # Extra variables (-e / --extra-vars) (JSON or YAML)
│   ├── cmdline         # Additional ansible-playbook command line flags
│   └── passwords       # SSH / sudo / vault passwords
└── artifacts/          # Generated execution logs, events, and status files
    └── <job_id>/
        ├── status      # Execution state: 'successful', 'failed', 'timeout'
        ├── rc          # Ansible playbook return code
        ├── stdout      # Playbook execution console log
        └── job_events/ # Detailed JSON event log files
```

---

## Environment Configuration (`/env/`)

### `env/settings`
Configures runner execution mode, container runtime, and isolation.

```yaml
---
container_image: quay.io/ansible/ansible-runner:latest
process_isolation: true
process_isolation_executable: podman  # podman or docker
timeout: 3600
idle_timeout: 600
```

### `env/envvars`
Defines environment variables inside the execution context.

```yaml
---
ANSIBLE_HOST_KEY_CHECKING: "False"
ANSIBLE_STDOUT_CALLBACK: "yaml"
ANSIBLE_FORCE_COLOR: "True"
```

### `env/extravars`
Defines extra variables passed directly to `ansible-playbook`.

```yaml
---
target_env: production
app_version: "2.4.1"
deploy_user: automation
```
