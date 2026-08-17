# `.ansible-lint` Configuration Guide

Complete guide to configuring `.ansible-lint` control files for projects, roles, and repositories.

## Standard `.ansible-lint` Specification

```yaml
# .ansible-lint configuration file

# Select lint profile: min, basic, moderate, safety, shared, production
profile: production

# Offline mode prevents galaxy lookup checks during local execution
offline: false

# Enable auto-fixing where supported
write_list:
  - format
  - jinja
  - key-order
  - name
  - yaml

# Paths to exclude from linting
exclude_paths:
  - .cache/
  - .git/
  - tests/fixtures/
  - vendor/

# Skip specific rules project-wide if necessary (use sparingly)
skip_list:
  - skip_this_rule_id

# Convert errors to warnings for transitional migration
warn_list:
  - experimental
  - meta-no-info

# Custom roles/collections paths
role_name_check: 1
strict: false
```

---

## Profile Selection Guidance

- **New Enterprise Projects**: Set `profile: production`.
- **Legacy Codebases undergoing modernization**: Start with `profile: basic` or `profile: moderate`, fix existing violations, then elevate profile to `production`.
- **Shared Galaxy Collections**: Set `profile: shared`.
