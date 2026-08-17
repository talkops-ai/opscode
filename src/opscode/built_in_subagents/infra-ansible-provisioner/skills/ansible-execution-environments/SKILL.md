---
name: ansible-execution-environments
description: >-
  Execution Environment (EE) engineering for containerised Ansible runtimes using
  Ansible Builder. Covers Version 3 schema compliance, dependency mapping
  (requirements.yml, requirements.txt, bindep.txt), base container image selection,
  and additional_build_steps for custom Containerfile/Dockerfile injection. Use when:
  (1) designing execution-environment.yml definition files, (2) validating EE
  definitions against schema://execution-environment and rules://execution-environment
  MCP resources, (3) building EE images via define_and_build_execution_env MCP tool,
  (4) mapping Galaxy collections, Python pip packages, and system packages into the
  dependencies block, or (5) injecting custom build steps (certificates, system users).
license: MIT
compatibility: designed for opscode
---

# Ansible Execution Environments

Engineer containerised Ansible execution environment (EE) images using Ansible Builder v3, ensuring schema compliance, structured dependency resolution, and multi-stage container build customizations.

---

## Workflow Decision Tree

```
1. Base Image Selection & Schema Initialization
   ├── Select base runtime & builder container images
   ├── Ensure 'version: 3' top-level schema compliance
   └── Refer to starter template in [assets/execution-environment.yml](assets/execution-environment.yml)
2. Dependency Mapping
   ├── Galaxy Collections: Map to requirements.yml (dependencies.galaxy)
   ├── Python Packages: Map to requirements.txt (dependencies.python)
   ├── System Packages: Map to bindep.txt with profile tags (dependencies.system)
   └── Consult [references/dependency_mapping.md](references/dependency_mapping.md) for syntax & profiles
3. Build Stage Customization
   ├── Inject custom steps via 'additional_build_steps'
   ├── Prepend/append base, galaxy, builder, or final stages
   └── Consult [references/schema_v3_reference.md](references/schema_v3_reference.md) for lifecycle hook details
4. MCP Schema Validation & Image Building
   ├── Validate definition against 'schema://execution-environment' & 'rules://execution-environment'
   ├── Trigger container build using 'define_and_build_execution_env' MCP tool
   └── Consult [references/mcp_integration.md](references/mcp_integration.md) for MCP integration
```

---

## 1. Schema Version 3 Definition Authoring

Every `execution-environment.yml` MUST conform to Ansible Builder v3 schema.

### Core Structure

```yaml
version: 3

images:
  base_image:
    name: quay.io/ansible/ansible-runner:latest
  builder_image:
    name: quay.io/ansible/ansible-builder:latest

dependencies:
  galaxy: requirements.yml
  python: requirements.txt
  system: bindep.txt

options:
  package_manager_path: /usr/bin/microdnf

additional_build_steps:
  append_final:
    - RUN useradd -u 1000 -g 0 runner
    - USER 1000
```

For full parameter options and schema rules, see [references/schema_v3_reference.md](references/schema_v3_reference.md).

---

## 2. Dependency Mapping

Structure dependencies into their designated definition files:

1. **Ansible Galaxy Collections (`requirements.yml`)**: Specify collection dependencies with version locking.
2. **Python Packages (`requirements.txt`)**: Specify pip packages required by Ansible modules/plugins.
3. **System Dependencies (`bindep.txt`)**: Specify RPM/DEB OS packages using `bindep` rules and `[compile]` build stage tags.

For complete dependency mapping examples and syntax guidelines, see [references/dependency_mapping.md](references/dependency_mapping.md).

---

## 3. Custom Build Steps (`additional_build_steps`)

Inject Containerfile/Dockerfile directives into specific build stages:

- `prepend_base` / `append_base`: Early stage configurations (proxies, corporate CA certificates).
- `prepend_galaxy` / `append_galaxy`: Collection download settings or custom server credentials.
- `prepend_builder` / `append_builder`: Compilation flags and C library setup.
- `prepend_final` / `append_final`: Final container runtime user creation and environment settings.

---

## 4. MCP Validation & Image Building

When MCP server capabilities are active:

1. **Validation**: Validate definitions using `schema://execution-environment` and `rules://execution-environment` resources.
2. **Build Execution**: Invoke the `define_and_build_execution_env` tool to generate container context files and compile the final container image.

For detailed MCP usage, see [references/mcp_integration.md](references/mcp_integration.md).
