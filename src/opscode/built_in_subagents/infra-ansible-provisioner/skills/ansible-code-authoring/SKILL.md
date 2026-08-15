---
name: ansible-code-authoring
description: >-
  Idiomatic Ansible code authoring patterns covering declarative YAML conventions,
  strict idempotency enforcement, Fully Qualified Collection Names (FQCN), module
  selection over shell commands, and MCP knowledge base grounding. Use when:
  (1) writing playbook tasks, roles, or handlers, (2) enforcing idempotency via
  changed_when, creates, and removes parameters, (3) selecting specialised modules
  over shell/command, (4) querying zen_of_ansible or ansible_content_best_practices
  MCP endpoints, (5) converting legacy short module names to FQCN, or (6) authoring
  handlers, variables, defaults, and templates. Do NOT use for linting or
  remediation (use ansible-linting-remediation), execution (use
  ansible-runner-execution), or security/vault (use ansible-security-operations).
license: MIT
compatibility: designed for opscode
---

# Ansible Code Authoring

Author production-grade, enterprise Ansible playbooks, roles, tasks, handlers, and templates adhering to declarative YAML conventions, strict idempotency guardrails, and Fully Qualified Collection Names (FQCN).

---

## Workflow Decision Tree

```
1. Knowledge Base Grounding & Best Practices Check
   ├── Query MCP endpoint 'zen_of_ansible' for design philosophy
   └── Query MCP endpoint 'ansible_content_best_practices' for task & role standards
2. Module Selection & FQCN Mapping
   ├── Prefer declarative modules over shell/command
   ├── Map legacy short module names to FQCN (ansible.builtin, community.general, etc.)
   └── Consult [references/fqcn_mapping.md](references/fqcn_mapping.md) for full mapping table
3. Idempotency Guardrail Enforcement
   ├── Ensure native modules express desired state (state: present, state: started, etc.)
   ├── For command/shell: require creates, removes, or explicit changed_when
   ├── Mark read-only discovery tasks with changed_when: false
   └── Consult [references/idempotency_patterns.md](references/idempotency_patterns.md) for advanced patterns
4. Structure & Syntax Authoring
   ├── Task Naming: Descriptive, sentence-case name starting with action verb
   ├── Parameter Syntax: Map/dictionary format (avoid key=value strings)
   ├── File Permissions: Always specify octal string permissions (e.g., mode: '0644')
   ├── Variable Naming: Lowercase snake_case with role/domain prefixing
   └── Templates & Handlers: Jinja2 header tags, explicit defaults, and notify triggers
```

---

## 1. MCP Knowledge Base Grounding

When MCP server capabilities are active:

1. Query `zen_of_ansible` to verify general Ansible automation design principles.
2. Query `ansible_content_best_practices` to retrieve recommended conventions for:
   - Playbook task ordering and structure
   - Variable precedence and role layout (`defaults/main.yml`, `vars/main.yml`, `tasks/main.yml`, `handlers/main.yml`)
   - Jinja2 templating syntax and filter choices
3. Access `guidelines://ansible-content-best-practices` resource URI for deep-dive project structure standards during complex refactoring.

---

## 2. Declarative Module Selection & FQCN

Always use Fully Qualified Collection Names (FQCN) for every task action. Never use legacy short module names (e.g., `copy`, `yum`, `service`, `git`).

### Rules for FQCN Usage

1. Core built-in modules must be prefixed with `ansible.builtin.`
   - Example: `ansible.builtin.copy`, `ansible.builtin.template`, `ansible.builtin.service`, `ansible.builtin.file`, `ansible.builtin.user`
2. POSIX system modules must use `ansible.posix.`
   - Example: `ansible.posix.sysctl`, `ansible.posix.authorized_key`, `ansible.posix.firewalld`
3. Community collection modules must use their respective collection namespace.
   - Example: `community.general.ini_file`, `amazon.aws.ec2_instance`

For a complete lookup table of legacy short names to FQCNs, see [references/fqcn_mapping.md](references/fqcn_mapping.md).

### Module Selection Over Shell Commands

Do NOT use `ansible.builtin.shell` or `ansible.builtin.command` when a specialized module exists:

| Instead of Shell/Command | Use Specialized Declarative Module |
|--------------------------|------------------------------------|
| `mkdir -p /path` | `ansible.builtin.file` with `state: directory` |
| `chmod 644 /path` | `ansible.builtin.file` with `mode: '0644'` |
| `curl -o /dest http://...` | `ansible.builtin.get_url` |
| `systemctl restart app` | `ansible.builtin.systemd` or `ansible.builtin.service` |
| `useradd -m john` | `ansible.builtin.user` |
| `git clone repo` | `ansible.builtin.git` |
| `sed -i 's/.../.../' file` | `ansible.builtin.lineinfile` or `ansible.builtin.replace` |

---

## 3. Idempotency Enforcement

Every task MUST be idempotent. Re-running the task without system changes must report `ok` (`changed: false`).

### Native Declarative Modules
Use explicit `state` parameters:
- Files & Directories: `state: present`, `state: absent`, `state: directory`, `state: link`
- Services: `state: started`, `state: stopped`, `state: reloaded`
- Packages: `state: present`, `state: latest`, `state: absent`

### Mandatory Guardrails for Command & Shell

If `ansible.builtin.command` or `ansible.builtin.shell` is unavoidable, you MUST apply at least one of the following idempotency parameters:

1. **`creates`**: Skip execution if target file or directory exists.
2. **`removes`**: Execute only if target file or directory exists.
3. **`changed_when`**: Define exact boolean expression or condition string that signals a state change.
4. **`changed_when: false`**: Mark read-only or inspection commands so they never report changes.

```yaml
# Correct: Using 'creates' parameter
- name: Extract runtime binaries
  ansible.builtin.command:
    cmd: tar -xzf /tmp/runtime.tar.gz -C /opt/runtime
    creates: /opt/runtime/bin/server

# Correct: Explicit changed_when condition
- name: Apply database migrations
  ansible.builtin.command:
    cmd: /opt/app/bin/migrate.sh
  register: migration_out
  changed_when: "'Migrations applied' in migration_out.stdout"

# Correct: Read-only check setting changed_when: false
- name: Inspect existing cluster version
  ansible.builtin.command:
    cmd: /usr/local/bin/cluster-cli status
  register: cluster_status
  changed_when: false
```

For complete idempotency patterns and conditional stat checks, see [references/idempotency_patterns.md](references/idempotency_patterns.md).

---

## 4. Playbook, Role, and Handler Formatting Guidelines

### Task Authoring Standards

1. **Name**: Start with a capital letter, describing the exact desired state in plain language.
2. **YAML Syntax**: Use dictionary map key-value formatting for parameters, never key=value inline strings.
3. **Mode Permissions**: Always specify file permissions as quoted 4-digit octal strings (e.g., `mode: '0644'`, `mode: '0755'`).

```yaml
# Correct
- name: Deploy application configuration file
  ansible.builtin.template:
    src: app.conf.j2
    dest: /etc/app/app.conf
    owner: appuser
    group: appgroup
    mode: '0644'
  notify: Restart application service

# Incorrect: Inline key=value syntax and missing FQCN
- name: deploy config
  template: src=app.conf.j2 dest=/etc/app/app.conf mode=644
```

### Handlers & Notifications

Define service reloads/restarts as handlers in `handlers/main.yml` and trigger them using `notify`:

```yaml
# tasks/main.yml
- name: Update Nginx server block configuration
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
    mode: '0644'
  notify: Reload Nginx service

# handlers/main.yml
- name: Reload Nginx service
  ansible.builtin.service:
    name: nginx
    state: reloaded
```

### Jinja2 Templates & Variables

- **Variables**: Name all variables using lowercase `snake_case`. Prefix role variables with the role name (`myapp_port`, `myapp_install_dir`).
- **Templates**: Include the `# {{ ansible_managed }}` header comment at the top of all Jinja2 template files (`.j2`).
- **Default Filters**: Supply fallbacks for optional variables using `{{ myapp_setting | default('standard') }}`.
