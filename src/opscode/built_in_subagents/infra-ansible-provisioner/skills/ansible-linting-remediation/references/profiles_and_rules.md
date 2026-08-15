# Ansible Lint Profiles and Rules Reference

Guide to `ansible-lint` validation profiles, rule categories, and remediation strategies.

## 1. Validation Profiles

Profiles define progressive strictness levels for Ansible linting.

| Profile | Strictness Level | Focus Area / Enforcement |
|---------|------------------|--------------------------|
| `min` | Minimal | Syntax validity, core YAML structure, parser errors |
| `basic` | Low | Basic conventions, valid module names, deprecated features |
| `moderate` | Medium | FQCN module enforcement, missing name attributes |
| `safety` | High | Security risks, hardcoded credentials, unsafe shell commands |
| `shared` | High | Standards for shared roles/collections published on Galaxy |
| `production` | Maximum | Enterprise production readiness, strict formatting, idempotency |

---

## 2. Common Rule Categories & Remediation Matrix

### A. Auto-Fixable Rules (Phase 1: Automated Fix)
These rules are safely remediated automatically when invoking `ansible_lint` with `fix: true`.

- `yaml[truthy]`: Normalizes boolean values (`yes/no` -> `true/false`).
- `yaml[line-length]`: Formats long lines into multi-line YAML blocks.
- `jinja[spacing]`: Standardizes whitespace inside `{{ ... }}` Jinja tags.
- `key-order[task]`: Orders task keys standardly (`name` first, then action, then parameters).
- `name[casing]`: Capitalizes first letter of task names.

### B. Semantic Repair Rules (Phase 2: Intelligent Code Rewriting)
These rules require structural or semantic modifications that automated syntax formatters cannot perform.

#### `command-instead-of-module`
- **Violation**: Executing shell commands (`curl`, `mkdir`, `useradd`, `systemctl`) instead of declarative modules.
- **Remediation**:
  - `mkdir /dir` -> `ansible.builtin.file: state: directory path: /dir`
  - `chmod 0644 /file` -> `ansible.builtin.file: mode: '0644' path: /file`
  - `systemctl restart app` -> `ansible.builtin.systemd: name: app state: restarted`

#### `no-changed-when`
- **Violation**: `ansible.builtin.command` or `ansible.builtin.shell` task without explicit change tracking.
- **Remediation**:
  - Add explicit `changed_when: false` for read-only status commands (`changed_when: false`).
  - Add explicit `changed_when` expression or `creates`/`removes` parameters (`creates: /path/to/file`).

#### `fqcn[action]`
- **Violation**: Using short module names (e.g. `copy`, `template`, `file`).
- **Remediation**: Prepend namespace (e.g. `ansible.builtin.copy`, `ansible.builtin.template`, `ansible.builtin.file`).

#### `risky-file-permissions`
- **Violation**: `ansible.builtin.copy` or `ansible.builtin.file` without explicit `mode`.
- **Remediation**: Add explicit octal permissions string (e.g. `mode: '0644'` or `mode: '0755'`). Always quote octal modes.

#### `package-latest`
- **Violation**: Package tasks using `state: latest`.
- **Remediation**: Use `state: present` or pin a specific version.
