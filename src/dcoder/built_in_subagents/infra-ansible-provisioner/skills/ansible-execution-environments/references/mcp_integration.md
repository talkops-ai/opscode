# MCP Tool & Resource Integration Guide

How to validate execution environment definitions and trigger EE container image builds using available MCP resources and tools.

## 1. Validation Resources

Validate `execution-environment.yml` definitions against official schema and rule checks before building.

### `schema://execution-environment`
- Read this MCP resource to obtain the official JSON Schema specification for Ansible Builder v3 definitions.
- Verify structure, required fields (`version: 3`), field types, and allowed block names.

### `rules://execution-environment`
- Read this MCP resource to check linting and policy rules for Execution Environments.
- Common rules enforced:
  - Version 3 schema compliance (`version: 3`).
  - Base image specification validity.
  - Prohibition of legacy v1/v2 schema keys.
  - Proper formatting of `additional_build_steps` hooks.

---

## 2. EE Image Building Tool

### `define_and_build_execution_env`
Use this MCP tool to build the container image directly from an `execution-environment.yml` definition.

#### Typical Parameter Usage:
- `definition_file`: Path to the `execution-environment.yml` file.
- `output_directory`: Target build context directory for generated Containerfile and build context artifacts.
- `tag`: Name and tag for the resulting container image (e.g., `custom-ee:v1.0.0`).
- `verbosity`: Build log verbosity level (0 to 3).
