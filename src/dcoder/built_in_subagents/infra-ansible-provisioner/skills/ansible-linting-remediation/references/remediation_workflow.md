# Two-Phase Remediation Workflow Guide

Detailed operational procedure for autonomous code quality validation and two-phase remediation using `ansible-lint`.

## Overview

Remediation uses a structured two-phase process:
1. **Phase 1: Automated Fix Pass**: Automatically resolves mechanical formatting, Jinja spacing, YAML booleans, and key ordering.
2. **Phase 2: Semantic Repair Pass**: Inspects remaining structured violations and applies intelligent code refactoring for complex rules.

---

## Remediation Workflow Steps

```
[Target Playbook/Role]
         │
         ▼
1. Phase 1: Automated Fix Pass
   └── Execute ansible_lint with fix: true
         │
         ▼
2. Lint Validation & Structured Output Capture
   └── Execute ansible_lint (JSON/SARIF mode)
         │
         ▼
3. Violation Parsing
   └── Parse remaining violations by rule ID, file, line number, and message
         │
         ▼
4. Phase 2: Semantic Repair
   ├── Fix command-instead-of-module violations
   ├── Add changed_when / creates parameters to shell tasks
   ├── Enforce FQCN prefixes on legacy module names
   └── Add explicit quoted file mode permissions ('0644')
         │
         ▼
5. Final Verification Pass
   └── Re-run ansible_lint to confirm zero remaining violations
```

---

## Executing Phase 1: Automated Fix Pass

When using the `ansible_lint` MCP tool:

- Set `fix: true` on the target path.
- Review automatically modified files.

---

## Executing Phase 2: Semantic Repair Pass

1. Obtain structured lint violations (SARIF or JSON output).
2. Group violations by file and line number.
3. For each violation:
   - Identify the rule tag (`command-instead-of-module`, `no-changed-when`, `fqcn[action]`, `risky-file-permissions`).
   - Modify the exact task in the target file maintaining existing indentation and variable references.
4. Re-run `ansible_lint` to verify all issues are resolved cleanly.
