# Ansible Directory Layouts & Scaffolding Standards

This reference details official Ansible workspace layouts for both standalone Playbook Projects and Ansible Content Collections.

## Table of Contents

- [Playbook Project Layout](#playbook-project-layout)
- [Ansible Collection Layout (`galaxy.yml`)](#ansible-collection-layout-galaxyyml)
- [Python Virtual Environment Requirements](#python-virtual-environment-requirements)

---

## Playbook Project Layout

Standard production-grade Ansible playbook repository structure:

```
ansible-project/
├── ansible.cfg              # Workspace configuration overrides
├── inventory/
│   ├── group_vars/
│   │   ├── all.yml          # Global group variables
│   │   └── webservers.yml   # Group-specific variables
│   ├── host_vars/
│   │   └── db01.example.com.yml
│   ├── production.ini       # Production inventory
│   └── staging.ini          # Staging inventory
├── playbooks/
│   ├── site.yml             # Main orchestration playbook
│   ├── webservers.yml       # Component playbook
│   └── dbservers.yml        # Component playbook
├── roles/
│   └── common/              # Standalone or embedded role
│       ├── defaults/main.yml
│       ├── vars/main.yml
│       ├── tasks/main.yml
│       ├── handlers/main.yml
│       ├── templates/
│       └── meta/main.yml
├── collections/
│   └── requirements.yml     # Collection dependencies
├── requirements.yml         # Role dependencies (ansible-galaxy)
└── pyproject.toml / requirements.txt # Python dependencies
```

### `ansible.cfg` Example

```ini
[defaults]
inventory = inventory/staging.ini
roles_path = roles:~/.ansible/roles
collections_path = collections:~/.ansible/collections
host_key_checking = False
stdout_callback = yaml
callbacks_enabled = timer, profile_tasks

[privilege_escalation]
become = False
become_method = sudo
become_user = root
```

---

## Ansible Collection Layout (`galaxy.yml`)

Standard structure for authoring reusable Ansible Content Collections:

```
my_namespace/my_collection/
├── galaxy.yml               # Collection metadata manifest
├── README.md                # Collection documentation
├── docs/                    # Detailed collection documentation
├── plugins/
│   ├── modules/             # Custom Ansible modules (.py)
│   ├── filter/              # Custom Jinja2 filter plugins
│   ├── lookup/              # Custom lookup plugins
│   └── action/              # Custom action plugins
├── roles/                   # Bundled collection roles
│   └── my_role/
│       ├── tasks/main.yml
│       └── defaults/main.yml
├── playbooks/               # Bundled sample playbooks
└── tests/                   # Integration and unit tests (molecule, sanity)
```

### `galaxy.yml` Skeleton

```yaml
namespace: my_namespace
name: my_collection
version: 1.0.0
readme: README.md
authors:
  - Enterprise Automation Team <devops@example.com>
description: Ansible collection for enterprise infrastructure management
license:
  - Apache-2.0
tags:
  - infrastructure
  - cloud
  - linux
repository: https://github.com/my_namespace/my_collection
documentation: https://github.com/my_namespace/my_collection/docs
dependencies:
  "ansible.posix": ">=1.5.0"
  "community.general": ">=8.0.0"
```

---

## Python Virtual Environment Requirements

To maintain reproducible Ansible control nodes, isolate execution environments in dedicated Python virtual environments (`venv`):

Recommended `requirements.txt`:
```
ansible-core>=2.15.0,<2.18.0
ansible-lint>=24.2.0
molecule>=24.2.0
jmespath>=1.0.1
netaddr>=0.10.0
pyyaml>=6.0.1
```
