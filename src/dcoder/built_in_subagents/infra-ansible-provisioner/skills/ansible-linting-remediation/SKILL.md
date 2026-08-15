---
name: ansible-linting-remediation
description: >-
  Code quality validation and autonomous remediation using ansible-lint via the
  ansible_lint MCP tool. Covers profile-driven validation (min through production),
  two-phase remediation (automated fix + semantic repair), and SARIF/JSON output
  parsing. Use when: (1) validating playbook or role code quality via ansible_lint,
  (2) selecting and configuring lint profiles (min, basic, moderate, safety, shared,
  production), (3) auto-fixing formatting issues with fix:true, (4) parsing
  structured lint output to identify line-level violations, (5) performing semantic
  remediation of unfixable rules (command-instead-of-module, no-changed-when),
  or (6) configuring .ansible-lint for a project.
license: MIT
compatibility: designed for deepagents-code
---

# Ansible Linting & Remediation

Validate Ansible code quality and perform two-phase autonomous remediation using `ansible-lint` and the `ansible_lint` MCP tool across progressive validation profiles (`min` through `production`).

---

## Workflow Decision Tree

```
1. Configuration & Profile Selection
   ├── Check or create project '.ansible-lint' config file
   ├── Select profile: 'min', 'basic', 'moderate', 'safety', 'shared', 'production'
   └── Consult [references/configuration_guide.md](references/configuration_guide.md) for configuration settings
2. Phase 1: Automated Fix Pass
   ├── Execute 'ansible_lint' MCP tool with 'fix: true'
   ├── Automatically resolve formatting, Jinja spacing, truthy booleans, key ordering
   └── Refer to [references/remediation_workflow.md](references/remediation_workflow.md) for workflow details
3. Lint Violation Inspection & Parsing
   ├── Execute 'ansible_lint' MCP tool to capture remaining violations
   ├── Parse structured output (SARIF / JSON) by rule ID, file, and line number
   └── Consult [references/profiles_and_rules.md](references/profiles_and_rules.md) for rule taxonomy
4. Phase 2: Semantic Repair
   ├── Replace shell commands with declarative modules ('command-instead-of-module')
   ├── Add explicit 'changed_when' / 'creates' tracking to command tasks ('no-changed-when')
   ├── Enforce FQCN prefixes ('fqcn[action]') and explicit quoted permissions ('mode: "0644"')
   └── Re-run 'ansible_lint' to confirm zero remaining violations
```

---

## 1. Profile-Driven Validation

Set the linting profile according to code maturity and standards:

- `min`: Basic YAML and syntax validation.
- `basic` / `moderate`: FQCN usage and basic structural conventions.
- `safety` / `production`: Enterprise readiness, explicit file permissions, idempotency tracking (`changed_when`), and zero shell command anti-patterns.

For details on profiles and rule definitions, see [references/profiles_and_rules.md](references/profiles_and_rules.md).

---

## 2. Two-Phase Autonomous Remediation

Remediate issues in two ordered steps:

1. **Phase 1 (Automated Fix)**: Pass `fix: true` to the `ansible_lint` MCP tool. Safe mechanical transformations (key order, Jinja spacing, YAML boolean literals) are applied automatically.
2. **Phase 2 (Semantic Repair)**: Parse remaining unfixable rules and rewrite code semantically:
   - Convert `command`/`shell` invocations to declarative modules (`ansible.builtin.file`, `ansible.builtin.systemd`, `ansible.builtin.user`).
   - Add explicit `changed_when: false` or `changed_when: ...` conditions to command tasks.
   - Add explicit octal modes (`mode: '0644'`) to file/copy tasks.

For detailed step-by-step procedures, see [references/remediation_workflow.md](references/remediation_workflow.md).

---

## 3. Project Configuration (`.ansible-lint`)

Place a `.ansible-lint` configuration file at the repository root to standardize linting behavior across environments.

Refer to the starter asset in [assets/ansible-lint.yml](assets/ansible-lint.yml) or the [references/configuration_guide.md](references/configuration_guide.md).
