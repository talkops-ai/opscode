# Ansible Environment Discovery & Tool Reference

This reference details the tools and discovery workflows used to assess host systems and scaffold Ansible environments.

## Table of Contents

- [Environment Discovery Tools](#environment-discovery-tools)
- [Environment Provisioning Tools](#environment-provisioning-tools)
- [Scaffolding Tools](#scaffolding-tools)

---

## Environment Discovery Tools

### `ade_environment_info`

Gathers environment telemetry from the execution host:

- Installed `ansible-core` or `ansible` package versions
- Active Python interpreter path and version (`python3 --version`)
- Virtual environment state (`VIRTUAL_ENV` environment variable)
- Installed Ansible collections (`ansible-galaxy collection list`)
- Configured collection and role paths (`ansible-config dump`)

Usage Workflow:
1. Run discovery prior to project creation or dependency installation.
2. Verify if `ansible-core` meets minimum requirements (`>= 2.15.0`).
3. Check missing collections against project `requirements.yml`.

---

## Environment Provisioning Tools

### `ade_setup_environment`

Automates isolation and dependency installation for Ansible control nodes:

- Creates a Python virtual environment (`python3 -m venv .venv`).
- Upgrades `pip`, `setuptools`, and `wheel`.
- Installs specified requirements (`requirements.txt` or `pyproject.toml`).
- Installs collection dependencies via `ansible-galaxy collection install -r collections/requirements.yml`.

---

## Scaffolding Tools

### `ansible_create_collection`

Scaffolds standard Ansible Content Collection file structure:

- Creates `galaxy.yml` with namespace, collection name, version, and dependencies.
- Generates standard directory layout: `plugins/modules/`, `plugins/filter/`, `roles/`, `playbooks/`, `docs/`, `tests/`.
- Enforces strict collection naming conventions (lowercase `namespace.collection_name`).

### `ansible_create_playbook`

Scaffolds a standard Ansible Playbook project workspace:

- Creates root directory layout: `playbooks/`, `inventory/`, `roles/`, `group_vars/`, `host_vars/`.
- Generates a production-ready `ansible.cfg` with recommended callback settings.
- Creates sample inventory (`staging.ini`, `production.ini`) and initial `site.yml`.
