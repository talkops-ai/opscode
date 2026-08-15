---
name: terraform-repair-loop
description: "Iterative self-healing repair loop workflow for Terraform modules. Evaluates compilation and linter outputs from terraform validate, terraform plan, and tflint, diagnoses error root causes, and applies surgical HCL code edits during automated remediation turns. Use when fixing build/validation failures, resolving HCL syntax or reference errors, addressing tflint warnings/errors, or executing automated self-healing code edits."
license: MIT
compatibility: designed for opscode
---

# Terraform Self-Healing Repair Loop

Automated, deterministic self-healing workflow for evaluating, diagnosing, and remediating HCL errors and linter rule violations in Terraform modules.

---

## Repair Loop Workflow

Execute the repair loop iteratively through four distinct phases:

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  1. OBSERVE │ ──> │ 2. DIAGNOSE │ ──> │ 3. REMEDIATE │ ──> │  4. VERIFY   │
└─────────────┘     └─────────────┘     └──────────────┘     └──────────────┘
```

### Phase 1: Observe (Execute Checks & Parse Logs)
Run validation and linter tools in order of precedence:
1. `terraform validate` - Catches core HCL syntax, block structures, missing arguments, and type mismatches.
2. `tflint` - Catches provider-specific schema deprecations, invalid resource configurations, and naming conventions.
3. `terraform plan` - Catches deep state/provider evaluation issues and dynamic value constraints.

Extract structured diagnostics from tool output:
- **Location**: Target file path (`file_path`) and line number (`line_number`).
- **Severity**: Critical Error vs Warning.
- **Rule/Code**: e.g., `Reference to undeclared resource` or `aws_s3_bucket_deprecated_acl`.

### Phase 2: Diagnose (Root Cause Analysis)
Classify failure into one of the core categories:
- **Syntax & HCL Parsing**: Unclosed braces, missing quotes, invalid block headers.
- **Undeclared References**: Typos in resource/variable identifiers, missing `variable` declarations.
- **Type/Attribute Mismatches**: Plural vs singular attributes, String vs List/Set data structure wrappers.
- **Missing Required Arguments**: Unspecified mandatory resource inputs per provider schema.
- **Linter Rule Violations**: Deprecated attributes, unused declarations, invalid instance types/ARNs.

Consult [references/error-catalog.md](references/error-catalog.md) for matching error patterns and diagnostic logic.

### Phase 3: Remediate (Surgical Code Edits)
Apply targeted, localized edits to resolve the primary error:
1. **Target Precision**: Modify only lines directly involved in the failure. Never re-write whole files or untouched resource blocks.
2. **Preserve Context**: Maintain HCL formatting, indentation (2 spaces), and comments.
3. **Atomic Changes**: Fix compiler blocking errors (`terraform validate`) first before addressing linter warnings (`tflint`).

Consult [references/surgical-editing-patterns.md](references/surgical-editing-patterns.md) for exact HCL editing patterns and anti-patterns.

### Phase 4: Verify (Re-Validation)
Re-run `terraform validate` and `tflint` after every remediation turn:
- If errors are resolved, proceed to next step or complete the repair loop.
- If new errors are introduced, roll back or apply targeted correction on the new location.
- Limit remediation loops to a maximum of 3 turns per error category before flagging for review.

---

## Detailed Reference Guides

- **Error Patterns & Diagnostic Catalog**: See [references/error-catalog.md](references/error-catalog.md) for detailed error message mappings and root cause explanations.
- **Surgical Editing Patterns**: See [references/surgical-editing-patterns.md](references/surgical-editing-patterns.md) for HCL editing rules, anti-patterns, and example diffs.
