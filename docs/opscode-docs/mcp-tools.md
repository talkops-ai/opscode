# Model Context Protocol (MCP) Tools

> Connect OpsCode to external tools and context providers using the Model Context Protocol.

OpsCode provides native support for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). MCP allows you to connect external tool providers — Kubernetes cluster inspectors, Terraform registries, AWS API proxies, GitHub APIs, and database query servers — directly into the agent's tool execution graph without custom coding.

---

## Configuration

MCP servers are configured in JSON manifests. OpsCode resolves configuration files in the following precedence order:

### 1. Explicit CLI flag (highest priority)

```bash
opscode --mcp-config path/to/mcp.json
```

### 2. Project-level manifests (Git-tracked or project-scoped)

Checked in order (first found wins):

```
.mcp.json
mcp.json
.opscode/.mcp.json
.opscode/mcp.json
```

### 3. Global user manifest

```
~/.opscode/.mcp.json
```

---

## Configuration schema

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

| Field | Type | Description |
|---|---|---|
| `command` | string | Executable binary to launch (`npx`, `python`, `uvx`, `docker`) |
| `args` | list[string] | Command-line arguments passed to the server |
| `env` | object | Environment variables injected into the server subprocess |

---

## Tool discovery & naming convention

On startup, OpsCode:

1. Discovers and parses configured MCP manifests.
2. Spawns each MCP server as an isolated subprocess over stdio.
3. Queries server capabilities and tool schemas via MCP handshake.
4. Registers tools dynamically into the agent's runtime tool registry.

### Naming convention

MCP tools are registered into OpsCode with standard namespacing:

```
mcp__{server}__{tool}
```

For example, a tool `get_pods` provided by server `kubernetes` is registered as:

```
mcp__kubernetes__get_pods
```

This namespace format is used throughout OpsCode for slash commands, tool approval modals, and [hooks](./hooks.md) event listeners.

Use `/mcp` inside an interactive session to inspect loaded servers, tools, and schemas.

---

## Security & trust model

### Global vs. Project trust

- **Global MCP Servers (`~/.opscode/.mcp.json`):** Always trusted because they are directly controlled by the local user.
- **Project MCP Servers (`.opscode/.mcp.json`, `.mcp.json`):** Require explicit user confirmation on first encounter since they can be checked into Git repositories by other contributors. Trust decisions are persisted in `~/.opscode/.state/mcp_trust.json`.

Override trust prompts for CI/CD or trusted workspaces:

```bash
# Trust project MCP definitions for this session
opscode --trust-project-mcp

# Disable all MCP tool loading entirely
opscode --no-mcp
```

### Headless MCP guard (`HeadlessMCPGuardMiddleware`)

When running in non-interactive mode (`-n`) or automated CI/CD pipelines, OpsCode protects environments with a 4-tier tool classification guardrail:

| Security Tier | Policy | Examples |
|---|---|---|
| `READ_ONLY` | Allowed automatically | `mcp__k8s__get_pods`, `mcp__aws__describe_instances` |
| `MUTATING_SAFE` | Gated in automated runs | `mcp__k8s__apply_manifest`, `mcp__aws__tag_resource` |
| `MUTATING_DESTRUCTIVE` | Blocked without explicit allowlist | `mcp__k8s__delete_namespace`, `mcp__aws__terminate_instances` |
| `PRIVILEGED` | Blocked in headless mode | Operations modifying cluster RBAC or IAM root permissions |

---

## Subagent-scoped MCP servers

In addition to global and project MCP servers, individual built-in subagents and plugin subagents (such as `aws-terraform-module-writer`, `aws-opentofu-provisioner`, and `infra-ansible-provisioner`) encapsulate their own `.mcp.json` definitions.

These MCP sessions are instantiated exclusively for the subagent when invoked and do not leak into the parent agent's tool namespace.
