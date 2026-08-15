# Ansible Idempotency Enforcement Patterns

Idempotency ensures that executing a playbook multiple times produces the exact same state without unintended side effects or false change reports.

## Table of Contents

- [Core Principles](#core-principles)
- [Command & Shell Modules](#command--shell-modules)
- [Stat & Conditional Execution](#stat--conditional-execution)
- [Changed When Override](#changed-when-override)
- [Handlers & Changed Notifications](#handlers--notification-patterns)

---

## Core Principles

1. **Avoid shell/command when declarative modules exist**: Modules like `ansible.builtin.copy`, `ansible.builtin.template`, `ansible.builtin.service`, `ansible.builtin.package`, and `ansible.builtin.file` are inherently idempotent.
2. **Explicit change tracking**: When `ansible.builtin.command` or `ansible.builtin.shell` MUST be used, always specify `creates`, `removes`, or `changed_when`.
3. **Check Mode Safety**: Ensure tasks support `--check` mode gracefully or explicitly set `check_mode: false` when safe discovery is required.

---

## Command & Shell Modules

### Pattern 1: `creates` Parameter

Skips task execution if the specified file or directory already exists.

```yaml
- name: Extract application archive
  ansible.builtin.command:
    cmd: tar -xzf /tmp/app-v1.0.tar.gz -C /opt/app
    creates: /opt/app/bin/app_binary
```

### Pattern 2: `removes` Parameter

Executes task ONLY if the specified file or directory exists.

```yaml
- name: Remove legacy configuration cache
  ansible.builtin.command:
    cmd: /opt/app/bin/clear_cache.sh
    removes: /var/cache/app/legacy.cache
```

### Pattern 3: Explicit `changed_when`

Explicitly define what constitutes a state change.

```yaml
- name: Rebuild application configuration index
  ansible.builtin.command:
    cmd: /usr/local/bin/app-cli reindex
  register: reindex_result
  changed_when: "'Index updated' in reindex_result.stdout"
```

### Pattern 4: Read-Only Discovery (`changed_when: false`)

Commands used purely for inspection or data gathering must never report changed status.

```yaml
- name: Query installed custom plugin version
  ansible.builtin.command:
    cmd: /usr/local/bin/plugin --version
  register: plugin_version_raw
  changed_when: false
  check_mode: false
```

---

## Stat & Conditional Execution

When a command needs to run based on remote system state, inspect state first with `ansible.builtin.stat` or specialized module facts, then guard the command with `when:`.

```yaml
- name: Check if database initialization is complete
  ansible.builtin.stat:
    path: /var/lib/app/db_initialized
  register: db_init_marker

- name: Initialize application database schema
  ansible.builtin.command:
    cmd: /opt/app/bin/init_db.sh
  when: not db_init_marker.stat.exists
  notify: Create database initialization marker

# In handlers/main.yml:
# - name: Create database initialization marker
#   ansible.builtin.file:
#     path: /var/lib/app/db_initialized
#     state: touch
```

---

## Handlers & Notification Patterns

Handlers execute at the end of a play ONLY when notified by a task that resulted in a state change (`changed: true`).

```yaml
- name: Update Nginx virtual host configuration
  ansible.builtin.template:
    src: vhost.conf.j2
    dest: /etc/nginx/sites-available/app.conf
    owner: root
    group: root
    mode: '0644'
  notify: Reload Nginx service

# In handlers/main.yml:
- name: Reload Nginx service
  ansible.builtin.service:
    name: nginx
    state: reloaded
```
