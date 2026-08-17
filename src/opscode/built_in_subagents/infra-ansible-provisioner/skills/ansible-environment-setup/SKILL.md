---
name: ansible-environment-setup
description: >-
  Environment discovery, automated configuration, and project scaffolding for
  Ansible workspaces. Use when: (1) assessing the host environment for installed
  Ansible Core, Python version, virtual environments, and available collections
  via ade_environment_info, (2) provisioning isolated Python environments and
  installing dependencies via ade_setup_environment, (3) scaffolding collection
  structures with galaxy.yml, plugins/, roles/, and playbooks/ via
  ansible_create_collection, (4) scaffolding playbook projects via
  ansible_create_playbook, or (5) enforcing official Ansible directory layouts
  and naming conventions. Do NOT use for writing playbook task logic (use
  ansible-code-authoring), linting (use ansible-linting-remediation), or
  execution (use ansible-runner-execution).
license: MIT
compatibility: designed for opscode
---

# Ansible Environment Setup

Assess host execution environments, provision isolated Python virtual environments, and scaffold enterprise Ansible playbook projects and Content Collections.

---

## Workflow Decision Tree

```
1. Host Environment Discovery
   ├── Query host system with 'ade_environment_info'
   ├── Check installed Ansible Core version (require >= 2.15.0)
   ├── Check active Python interpreter and virtualenv status
   └── List installed collections vs project requirements
2. Environment Provisioning
   ├── Create isolated Python venv via 'ade_setup_environment'
   ├── Install core Python dependencies (ansible-core, ansible-lint, molecule)
   └── Install collection dependencies (ansible-galaxy collection install)
3. Workspace & Project Scaffolding
   ├── For Playbook Projects: invoke 'ansible_create_playbook'
   │   └── Generates inventory/, playbooks/, roles/, group_vars/, ansible.cfg
   └── For Content Collections: invoke 'ansible_create_collection'
       └── Generates galaxy.yml, plugins/, roles/, playbooks/, docs/, tests/
4. Verification & Layout Enforcement
   ├── Validate official Ansible directory naming standards
   └── Consult [references/directory_layouts.md](references/directory_layouts.md) for layout guidelines
```

---

## 1. Environment Discovery (`ade_environment_info`)

Before scaffolding a workspace or running playbooks, assess host capabilities:

1. **Ansible Core Check**: Verify `ansible-core` is installed and version is `>= 2.15.0`.
2. **Python Runtime Check**: Confirm Python 3.10+ is available in the target environment.
3. **Virtualenv Status**: Check if running within an active virtual environment (`VIRTUAL_ENV`). If running in global system Python, recommend provisioning a virtual environment.
4. **Collection Discovery**: List installed collections via `ansible-galaxy collection list` to identify missing dependencies.

For detailed discovery fields and tools, see [references/environment_discovery.md](references/environment_discovery.md).

---

## 2. Environment Provisioning (`ade_setup_environment`)

Provision isolated, reproducible execution environments:

When invoking `ade_setup_environment`, pass these standard parameters for consistency:

- **`envName: "venv"`** — creates an isolated Python virtual environment, preventing systemic dependency conflicts.
- **`installRequirements: true`** — auto-installs from workspace `requirements.yml` / `requirements.txt` if detected.
- **`collections: [...]`** — array of Ansible Galaxy collections parsed from user requirements or repository state.

```bash
# Automated setup via ade_setup_environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
ansible-galaxy collection install -r collections/requirements.yml
```

---

## 3. Playbook Project Scaffolding (`ansible_create_playbook`)

Use `ansible_create_playbook` to scaffold new playbook projects adhering to official Ansible directory conventions:

- `ansible.cfg` with explicit callback plugins and paths.
- `inventory/` with `group_vars/` and `host_vars/`.
- `playbooks/` for component orchestration playbooks.
- `roles/` for reusable role definitions.

For complete structure diagrams and `ansible.cfg` examples, see [references/directory_layouts.md](references/directory_layouts.md).

---

## 4. Collection Scaffolding (`ansible_create_collection`)

Use `ansible_create_collection` to scaffold Ansible Content Collections:

- Valid `galaxy.yml` manifest with `namespace`, `name`, `version`, `readme`, `authors`, and `dependencies`.
- Standard directories: `plugins/modules/`, `plugins/filter/`, `roles/`, `playbooks/`, `docs/`, `tests/`.

---

## 5. Tool Reference

- **`ade_environment_info`**: Discovers system Ansible Core version, Python path, virtualenv status, and installed collections.
- **`ade_setup_environment`**: Provisions Python venv, installs `ansible-core`, `ansible-lint`, and collection dependencies. Key parameters: `envName` (venv name), `installRequirements` (auto-install from requirements files), `collections` (Galaxy collections array).
- **`ansible_create_playbook`**: Scaffolds standard Ansible playbook workspace structure.
- **`ansible_create_collection`**: Scaffolds standard Ansible Content Collection structure with `galaxy.yml`.
