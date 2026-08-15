---
name: opentofu-mcp-schema-lookup
description: >
  Workflow for querying the OpenTofu MCP server to inspect AWS provider resource
  schemas, data source schemas, module inputs/outputs, and provider initialization
  requirements before writing or editing HCL code. Use when: (1) writing any new
  AWS resource block and need to confirm exact argument names and types via
  get-resource-docs, (2) looking up data source schemas via get-datasource-docs,
  (3) discovering providers or modules via search-opentofu-registry, (4) inspecting
  provider configuration requirements via get-provider-details, (5) analysing
  third-party module interfaces via get-module-details, or (6) pinning provider
  versions. Do NOT use for non-AWS providers, state operations, or CI/CD pipeline
  configuration.
license: MIT
compatibility: designed for deepagents-code
---

# OpenTofu MCP Schema Lookup

Query the **OpenTofu MCP Server** for real-time registry data before writing or editing any AWS HCL resource. This ensures generated configurations strictly adhere to the exact provider schema, eliminating hallucinated attributes, deprecated syntax, and type mismatches.

---

## Core Principles

1. **Zero Schema Hallucination**: Never guess resource names, argument types, or parameter constraints. Always retrieve the live schema first.
2. **Pre-Synthesis Verification**: Every resource block, data source, or module call must be preceded by an MCP lookup.
3. **Deprecation Awareness**: The MCP server returns current documentation — use it to detect and avoid deprecated arguments and inline blocks.
4. **Deterministic Compilation**: The agent transitions from a generic code predictor to a deterministic infrastructure compiler by grounding every HCL statement in registry data.

---

## Available MCP Tools

| MCP Tool | Purpose | When to Use |
|---|---|---|
| `search-opentofu-registry` | Discover latest providers and community modules | Initial planning phase — confirm namespace, exact naming conventions for AWS provider or verified modules |
| `get-provider-details` | Retrieve provider initialisation requirements | Understand required configuration blocks for `provider "aws"` — region specs, assumed role integrations, `default_tags` block structure |
| `get-resource-docs` | Deep inspection of resource arguments and attributes | **Most critical tool for authoring.** Retrieve exact argument references for specific AWS resources (e.g., `aws_iam_role`, `aws_s3_bucket`), ensuring no deprecated fields are used |
| `get-datasource-docs` | Lookup data source schemas for dynamic infrastructure querying | Understand how to fetch existing cloud state — e.g., `aws_iam_policy_document` for policy generation, `aws_vpc_endpoint_service` for network routing, `aws_caller_identity` for account ID |
| `get-module-details` | Analyse third-party or enterprise module inputs/outputs | When wrapping an existing public or private module — ensure all required variables are correctly mapped and outputs are consumed properly |

---

## Execution Workflow

### Step 1: Identify Required Resources

List all AWS resources, data sources, and module references needed for the configuration. For example:
- Resources: `aws_s3_bucket`, `aws_kms_key`, `aws_iam_role`
- Data sources: `aws_caller_identity`, `aws_iam_policy_document`
- Modules: Public registry modules or OCI-sourced enterprise modules

### Step 2: Discover Provider and Module Details

1. Call `search-opentofu-registry` to confirm the AWS provider namespace and discover available community modules.
2. Call `get-provider-details` to inspect the `provider "aws"` configuration block — region, assumed roles, `default_tags`, and required provider version.

### Step 3: Retrieve Resource and Data Source Schemas

For each resource and data source:

1. Call `get-resource-docs` with the exact resource name (e.g., `aws_s3_bucket`) to retrieve:
   - Required arguments (mandatory fields)
   - Optional arguments (with defaults)
   - Nested block structures
   - Data types (`list(string)`, `map(string)`, `bool`, `object(...)`)
   - Exported attributes (`.arn`, `.id`, `.endpoint`)
   - Deprecation warnings

2. Call `get-datasource-docs` with the data source name (e.g., `aws_iam_policy_document`) to understand:
   - Query arguments
   - Returned attributes
   - Usage patterns

### Step 4: Analyse Module Interfaces (if applicable)

Call `get-module-details` for any registry or OCI module being referenced to ensure:
- All required input variables are mapped
- Output attribute names are correct
- Version constraints are appropriate

### Step 5: Draft & Validate HCL

Write OpenTofu code adhering to the verified schemas, then run `tofu validate` to confirm correctness.

---

## Critical Mandate

> **The agent MUST halt and execute `get-resource-docs` before emitting HCL for any unfamiliar or complex resource.** This programmatic constraint is the foundational pillar of the autonomous agent's reliability. Never emit resource blocks based on memorised or cached schema knowledge.
