# Privilege Escalation & Sudoers Security Guide

Best practices for managing privilege escalation (`become`) and system sudoers configuration.

## 1. `become` Directives in Playbooks

Always restrict privilege escalation to tasks that strictly require elevated access.

### Task-Level Privilege Escalation (Recommended)

```yaml
---
- name: Configure Web Application
  hosts: webservers
  become: false  # Default to non-privileged execution

  tasks:
    - name: Fetch application configuration
      ansible.builtin.get_url:
        url: https://internal.example.com/config.json
        dest: /tmp/config.json
      # Runs as unprivileged remote user

    - name: Install Nginx system package
      ansible.builtin.package:
        name: nginx
        state: present
      become: true
      become_user: root
      become_method: sudo
```

---

## 2. Managing `/etc/sudoers.d/` Configurations

When configuring passwordless or restricted sudo access, always use drop-in files under `/etc/sudoers.d/` rather than modifying `/etc/sudoers` directly.

### Strict File Validation Requirement

Every file written to `/etc/sudoers.d/` MUST be validated with `visudo` during task execution to prevent lockout from broken syntax:

```yaml
- name: Deploy restricted sudoers policy for automation user
  ansible.builtin.template:
    src: sudoers_automation.j2
    dest: /etc/sudoers.d/automation
    mode: '0440'
    owner: root
    group: root
    validate: '/usr/sbin/visudo -cf %s'
  become: true
```

### Least-Privilege Sudoers Directive Example

```text
# /etc/sudoers.d/automation
automation ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart nginx, /usr/bin/systemctl reload nginx
```
