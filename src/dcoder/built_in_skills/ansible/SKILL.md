---
name: ansible
description: "Write, validate, and dry-run Ansible playbooks, roles, and inventory"
domain: DevOps
compatibility: "ansible-core >= 2.15"
allowed_tools:
  - execute
  - write_file
  - read_file
metadata:
  domain: ansible
  difficulty: intermediate
---

# Ansible Automation Skill

You are an expert Ansible automation engineer. Follow these guidelines when writing, reviewing, or debugging Ansible configurations.

## Playbook Structure

```yaml
---
- name: Configure web servers
  hosts: webservers
  become: true
  vars:
    http_port: 80
  pre_tasks:
    - name: Update apt cache
      ansible.builtin.apt:
        update_cache: true
      when: ansible_os_family == "Debian"
  roles:
    - common
    - nginx
  tasks:
    - name: Ensure nginx is running
      ansible.builtin.service:
        name: nginx
        state: started
        enabled: true
  handlers:
    - name: Restart nginx
      ansible.builtin.service:
        name: nginx
        state: restarted
```

## Role Layout

```
roles/nginx/
├── tasks/
│   └── main.yml          # Task entry point
├── handlers/
│   └── main.yml          # Handler definitions
├── templates/
│   └── nginx.conf.j2     # Jinja2 templates
├── files/                # Static files to copy
├── vars/
│   └── main.yml          # Role-specific variables (high precedence)
├── defaults/
│   └── main.yml          # Default variables (low precedence, user-overridable)
├── meta/
│   └── main.yml          # Role dependencies and metadata
└── README.md
```

## Task Best Practices

- Always use **fully qualified collection names** (FQCN): `ansible.builtin.copy`, not `copy`.
- Every task MUST have a descriptive `name`.
- Use `when` conditions for OS-specific or conditional tasks.
- Use `notify` + `handlers` for service restarts — don't restart inline.
- Prefer `ansible.builtin.template` over `ansible.builtin.copy` for dynamic config files.
- Use `block/rescue/always` for error handling:

```yaml
- block:
    - name: Deploy application
      ansible.builtin.command: deploy.sh
  rescue:
    - name: Rollback on failure
      ansible.builtin.command: rollback.sh
  always:
    - name: Notify team
      ansible.builtin.uri:
        url: "{{ webhook_url }}"
```

## Inventory Patterns

**Static inventory** (`inventory/hosts.yml`):
```yaml
all:
  children:
    webservers:
      hosts:
        web1:
          ansible_host: 10.0.1.10
        web2:
          ansible_host: 10.0.1.11
    databases:
      hosts:
        db1:
          ansible_host: 10.0.2.10
  vars:
    ansible_user: deploy
```

- Use `group_vars/` and `host_vars/` directories for variable organization.
- Use dynamic inventory scripts for cloud environments (AWS, GCP, Azure).

## Vault & Secrets

- Encrypt sensitive files: `ansible-vault encrypt secrets.yml`.
- Use `ansible-vault encrypt_string` for inline encrypted values.
- Never commit plaintext secrets — always vault-encrypt.
- Reference vault files via `vars_files` or `include_vars`.

## Validation Workflow

1. `ansible-lint playbook.yml` — best-practice linting.
2. `ansible-playbook --check --diff playbook.yml` — dry-run with change preview.
3. `ansible-playbook playbook.yml --limit staging` — deploy to subset first.

Always run `ansible-playbook --check --diff` before proposing real execution.

## Collections

- Declare dependencies in `requirements.yml`:
```yaml
collections:
  - name: community.general
    version: ">=7.0.0"
  - name: amazon.aws
    version: ">=6.0.0"
```
- Install with `ansible-galaxy collection install -r requirements.yml`.

## Security

- Set `become: true` only when needed — prefer least privilege.
- Use `no_log: true` on tasks that handle secrets.
- Validate input with `assert` tasks before destructive operations.
- Avoid `ansible.builtin.shell` when a dedicated module exists.
