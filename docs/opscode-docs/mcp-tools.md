# MCP tools

> Connect OpsCode to external tools using the Model Context Protocol

OpsCode supports the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). MCP lets you connect external tool providers — Kubernetes cluster inspectors, Terraform registries, AWS APIs, database servers — directly into the agent without writing custom code.

## Add an MCP server

MCP servers are configured in JSON files. Create an `.mcp.json` in your project root or in `~/.opscode/`:

```json
{
  "mcpServers": {
    "kubernetes": {
      "command": "npx",
      "args": ["-y", "@kubernetes/mcp-server"],
      "env": {
        "KUBECONFIG": "/Users/user/.kube/config"
      }
    },
    "aws": {
      "command": "npx",
      "args": ["-y", "@aws/mcp-server"],
      "env": {
        "AWS_PROFILE": "production",
        "AWS_REGION": "us-west-2"
      }
    }
  }
}
```

Each server entry defines:

| Field | Type | What it does |
|---|---|---|
| `command` | string | Executable to launch (`npx`, `python`, `uvx`, `docker`) |
| `args` | list | Arguments passed to the server |
| `env` | object | Environment variables for the server process |

## Where to put the config

OpsCode checks for MCP configs in this order (first found wins):

1. **CLI flag** (highest priority): `ops --mcp-config path/to/mcp.json`
2. **Project-level**: `.mcp.json`, `mcp.json`, `.opscode/.mcp.json`, or `.opscode/mcp.json`
3. **User-level**: `~/.opscode/.mcp.json`

## How tools are named

When OpsCode starts, it launches each configured MCP server, discovers its tools, and registers them with a namespaced name:

```
mcp__{server}__{tool}
```

For example, a tool `get_pods` from server `kubernetes` becomes `mcp__kubernetes__get_pods`.

Use `/mcp` inside a session to inspect loaded servers, tools, and their schemas.

## Trust and security

### Global vs. project trust

- **Global servers** (`~/.opscode/.mcp.json`) are always trusted — you control them.
- **Project servers** (`.opscode/.mcp.json`, `.mcp.json`) require confirmation on first use since they can be committed to Git by other contributors. OpsCode remembers your trust decisions.

Override trust for CI/CD:

```bash
# Trust project MCP servers for this session
ops --trust-project-mcp

# Disable all MCP tools
ops --no-mcp
```

### Headless safety

When running unattended (headless mode or CI/CD), OpsCode automatically classifies each MCP tool into security tiers:

| Tier | What happens | Examples |
|---|---|---|
| **Read-only** | Runs automatically | `mcp__k8s__get_pods`, `mcp__aws__describe_instances` |
| **Mutating-safe** | Gated in headless mode | `mcp__k8s__apply_manifest`, `mcp__aws__tag_resource` |
| **Mutating-destructive** | Blocked without explicit allowlist | `mcp__k8s__delete_namespace`, `mcp__aws__terminate_instances` |
| **Privileged** | Blocked in headless mode | Operations modifying cluster RBAC or IAM root permissions |

## Subagent MCP servers

Some built-in subagents (like `aws-terraform-module-writer` and `infra-ansible-provisioner`) bundle their own MCP server configs. These servers start when the subagent is invoked and stop when it finishes — they don't affect the main agent's tools.
