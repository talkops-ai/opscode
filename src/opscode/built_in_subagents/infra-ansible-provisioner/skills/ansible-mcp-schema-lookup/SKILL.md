---
name: ansible-mcp-schema-lookup
description: >-
  Workflow for querying the Ansible MCP server to discover available tools,
  inspect resource schemas, access documentation endpoints, and validate
  definitions before code generation. Use when: (1) discovering available MCP
  tools and their parameter signatures via list_available_tools, (2) querying
  zen_of_ansible or ansible_content_best_practices for philosophy and conventions,
  (3) reading guidelines://ansible-content-best-practices resource URI for deep
  project structure standards, (4) validating execution-environment.yml against
  schema://execution-environment and rules://execution-environment MCP resources,
  (5) inspecting ade_environment_info response fields before environment setup,
  (6) checking ade_setup_environment parameter schemas (envName, installRequirements,
  collections), or (7) resolving MCP tool invocation errors. Do NOT use for writing
  playbook code (use ansible-code-authoring), linting (use ansible-linting-remediation),
  or deployment execution (use ansible-runner-execution).
license: MIT
compatibility: designed for opscode
---

# Ansible MCP Schema Lookup

Query the Ansible Development Tools MCP server to discover tools, inspect parameter schemas, access documentation endpoints, and validate definitions before writing or modifying Ansible configurations.

---

## Core Principles

1. **Schema-First**: Never invoke an MCP tool without first understanding its parameter schema. Guessing parameters leads to tool invocation failures.
2. **Ground Before Generate**: Always query documentation endpoints (`zen_of_ansible`, `ansible_content_best_practices`) before authoring complex playbooks.
3. **Validate Against Schema**: Before building Execution Environments, validate definitions against the MCP schema and rules resources.
4. **Resource URIs Are Read-Only**: MCP resources (`guidelines://`, `schema://`, `rules://`) are read-only references — they cannot be modified.

---

## MCP Server Connection

The Ansible MCP server connects via `stdio` transport:

```json
{
  "mcpServers": {
    "ansible": {
      "command": "npx",
      "args": ["-y", "@ansible/ansible-mcp-server", "--stdio"],
      "env": {
        "WORKSPACE_ROOT": "."
      }
    }
  }
}
```

`WORKSPACE_ROOT` scopes all file operations to the designated workspace directory.

---

## Available Tools

### Environment & Scaffolding

| MCP Tool | Purpose | Key Parameters |
|---|---|---|
| `ade_environment_info` | Discover host system state — Python version, Ansible Core version, virtualenv status, installed collections | None required |
| `ade_setup_environment` | Provision isolated Python venv, install core tooling and collection dependencies | `envName: "venv"`, `installRequirements: true`, `collections: ["community.general"]` |
| `ansible_create_collection` | Scaffold collection structure with galaxy.yml, plugins/, roles/ | `namespace`, `name`, `path` |
| `ansible_create_playbook` | Scaffold playbook project with inventory/, playbooks/, roles/ | `name`, `path` |

### Knowledge Base & Documentation

| MCP Tool / Resource | Type | Purpose |
|---|---|---|
| `zen_of_ansible` | Tool endpoint | Core philosophical tenets — "Playbooks are not for programming", declarative state > imperative logic |
| `ansible_content_best_practices` | Tool endpoint | Naming conventions, structural organisation, modularity standards |
| `guidelines://ansible-content-best-practices` | Resource URI (read-only) | Deep-dive project structure standards, testing strategies, naming patterns |

### Validation & Execution

| MCP Tool / Resource | Type | Purpose |
|---|---|---|
| `ansible_lint` | Tool endpoint | Static analysis with profiles (min → production), auto-fix (`fix: true`), SARIF/JSON output |
| `ansible_navigator` | Tool endpoint | Production playbook execution inside Execution Environments |
| `define_and_build_execution_env` | Tool endpoint | Build containerised EE images via Ansible Builder v3 |
| `schema://execution-environment` | Resource URI (read-only) | JSON Schema for validating `execution-environment.yml` definitions |
| `rules://execution-environment` | Resource URI (read-only) | Validation rules and constraints for EE definitions |

---

## Execution Workflow

### Step 1: Discover Available Tools

Before any operation, verify tool availability:

1. List all available MCP tools via the server
2. Inspect parameter schemas for each tool you intend to use
3. Confirm required vs optional parameters

### Step 2: Query Documentation Endpoints

Before authoring playbooks or collections:

1. **`zen_of_ansible`** — Ingest core Ansible philosophy
2. **`ansible_content_best_practices`** — Retrieve naming, structure, modularity standards
3. **`guidelines://ansible-content-best-practices`** — Deep-dive resource URI for complex refactoring

### Step 3: Inspect Environment Discovery Fields

Before scaffolding or executing:

1. Call `ade_environment_info` to inspect the workspace
2. Check response fields: Python version, Ansible Core version, virtualenv status, installed collections
3. If tooling is missing, call `ade_setup_environment` with:
   - `envName: "venv"` — creates an isolated Python venv
   - `installRequirements: true` — installs from workspace `requirements.yml` / `requirements.txt`
   - `collections: [...]` — array of collections to install

### Step 4: Validate EE Definitions Against Schema

Before building Execution Environments:

1. Read `schema://execution-environment` to understand the Version 3 schema structure
2. Read `rules://execution-environment` to understand validation constraints
3. Validate the authored `execution-environment.yml` against both resources
4. Invoke `define_and_build_execution_env` only after validation passes

### Step 5: Inspect Lint Tool Parameters

Before running linting:

1. Confirm `ansible_lint` supports the target profile (`min`, `basic`, `moderate`, `safety`, `shared`, `production`)
2. Confirm `fix: true` parameter is available for auto-remediation
3. Check output format options (SARIF, JSON) for structured violation parsing

---

## Quick Reference Map

| Workflow Step | What to Check | MCP Query |
|---|---|---|
| **Tool Discovery** | Available tools and parameter schemas | List available tools from MCP server |
| **Philosophy Grounding** | Ansible design tenets | `zen_of_ansible` |
| **Best Practices** | Naming, structure, modularity | `ansible_content_best_practices` or `guidelines://ansible-content-best-practices` |
| **Environment State** | Python, Ansible Core, collections | `ade_environment_info` |
| **Environment Setup** | Provision venv, install deps | `ade_setup_environment` (envName, installRequirements, collections) |
| **Scaffolding** | Collection or playbook project | `ansible_create_collection` / `ansible_create_playbook` |
| **EE Schema Validation** | execution-environment.yml structure | `schema://execution-environment` + `rules://execution-environment` |
| **EE Build** | Container image construction | `define_and_build_execution_env` |
| **Lint Validation** | Static analysis, auto-fix | `ansible_lint` (profile, fix) |
| **Playbook Execution** | Production deployment | `ansible_navigator` |
