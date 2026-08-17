# Remote sandboxes

> Run OpsCode in isolated cloud environments instead of on your local machine

Remote sandboxes let OpsCode execute tools (shell commands, file operations, scripts) in an isolated cloud container instead of on your workstation. This is useful for:

- **Blast radius isolation** — Safely run infrastructure commands without risking your local environment.
- **Reproducibility** — Consistent Linux container environments every time.
- **Credential safety** — Prevent access to local SSH keys, env vars, or personal files.
- **CI/CD** — Spin up ephemeral sandboxes for automated checks in pull requests.

## Launch a sandbox

```bash
# Use the default sandbox provider
ops --sandbox

# Use a specific provider
ops --sandbox daytona

# Attach to an existing sandbox
ops --sandbox-id sb-prod-cluster-98234

# Use a pre-baked snapshot with a setup script
ops --sandbox modal \
  --sandbox-snapshot-name terraform-k8s-base \
  --sandbox-setup ./scripts/sandbox-init.sh
```

### CLI flags

| Flag | What it does |
|---|---|
| `--sandbox [TYPE]` | Enable a sandbox provider (`agentcore`, `daytona`, `langsmith`, `modal`, `runloop`, `vercel`) |
| `--sandbox-id ID` | Attach to an already-running sandbox |
| `--sandbox-snapshot-name NAME` | Launch from a pre-baked container snapshot |
| `--sandbox-setup PATH` | Shell script to run inside the sandbox after it starts |

## Supported providers

| Provider | ID | Working directory | What it offers |
|---|---|---|---|
| **AgentCore** | `agentcore` | `/tmp` | Managed AWS execution |
| **Daytona** | `daytona` | `/home/daytona` | Self-hosted & cloud dev environments |
| **LangSmith** | `langsmith` | `/root` | Ephemeral evaluation sandboxes |
| **Modal** | `modal` | `/workspace` | Serverless GPU/CPU containers |
| **Runloop** | `runloop` | `/home/user` | Snapshots and fast container boot |
| **Vercel** | `vercel` | `/vercel/sandbox` | Ephemeral Vercel code sandboxes |

## Workspace sync

When a sandbox starts, OpsCode automatically uploads your project files to the remote environment. It detects project boundaries, traverses the repository tree, and skips common ignored directories (`.git/`, `node_modules/`, `.venv/`, `__pycache__/`).

## Setup scripts

Run initialization tasks inside the sandbox immediately after it starts:

```bash
ops --sandbox modal --sandbox-setup ./scripts/ci-setup.sh
```

**`./scripts/ci-setup.sh`:**
```bash
#!/usr/bin/env bash
set -euo pipefail

# Install DevOps tools
apt-get update && apt-get install -y opentofu kubectl helm awscli

# Verify
tofu version
kubectl version --client=true
helm version
```

## How routing works

When a sandbox is active, OpsCode routes tool calls intelligently:

- **Shell commands, file reads/writes, grep, glob** → Remote sandbox
- **Web search, URL fetching** → Local host (no need to proxy these)

Sandboxes are automatically cleaned up when your session ends.

## CI/CD example

Combine sandboxes with headless mode and rubrics for zero-trust automation:

```bash
ops -n "Run OpenTofu plan and check for security violations" \
  --sandbox runloop \
  --sandbox-setup ./scripts/ci-init.sh \
  --rubric "tofu plan succeeds with zero syntax errors and no open security group ingress" \
  --quiet \
  -y
```
