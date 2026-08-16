# Remote Sandboxes

> Execute OpsCode tools and commands in isolated, ephemeral remote cloud environments.

Remote sandboxes provide isolated execution environments where OpsCode executes tools (shell commands, file operations, script evaluations) without modifying your local developer workstation. This is ideal for:

- **Security & Blast Radius Isolation:** Safely execute infrastructure commands and automated tests without risking local environments.
- **Reproducibility:** Run in consistent, standardized Linux container environments.
- **Credential Protection:** Prevent unintended access to local environment variables, SSH keys, or personal files.
- **CI/CD Ephemeral Execution:** Spin up lightweight cloud sandboxes for automated pull request checks.

---

## Configuration & CLI flags

| Flag | Description |
|---|---|
| `--sandbox [TYPE]` | Enable a remote sandbox provider (`agentcore`, `daytona`, `langsmith`, `modal`, `runloop`, `vercel`) |
| `--sandbox-id ID` | Attach to an existing, already running sandbox by ID |
| `--sandbox-snapshot-name NAME` | Launch from a pre-baked cloud container snapshot or blueprint |
| `--sandbox-setup PATH` | Path to a local shell script executed inside the sandbox immediately after provisioning |

### Launch examples

```bash
# Launch with default remote sandbox provider
opscode --sandbox

# Attach to an existing sandbox instance
opscode --sandbox-id sb-prod-cluster-98234

# Provision with a custom snapshot and setup script
opscode --sandbox daytona \
  --sandbox-snapshot-name terraform-k8s-base \
  --sandbox-setup ./scripts/sandbox-init.sh
```

---

## Supported sandbox providers

OpsCode integrates with 6 remote cloud sandbox providers out of the box (extensible via the `opscode.sandbox_providers` entry point group):

| Provider | ID | Working Directory | Features | Backend Module |
|---|---|---|---|---|
| **AgentCore** | `agentcore` | `/tmp` | Managed AWS execution | `langchain_agentcore_codeinterpreter` |
| **Daytona** | `daytona` | `/home/daytona` | Self-hosted & cloud dev environments | `langchain_daytona` |
| **LangSmith** | `langsmith` | `/root` | Ephemeral evaluation sandboxes | Built-in |
| **Modal** | `modal` | `/workspace` | Serverless GPU/CPU containers | `langchain_modal` |
| **Runloop** | `runloop` | `/home/user` | Snapshots and fast container boot | `langchain_runloop` |
| **Vercel** | `vercel` | `/vercel/sandbox` | Ephemeral Vercel code sandboxes | `langchain_vercel_sandbox` |

---

## Workspace synchronization

When a sandbox session starts, OpsCode automatically mirrors your local project workspace to the remote environment:

1. Detects project boundaries using [Project Root Detection](./Configuration.md#project-detection).
2. Traverses the repository tree.
3. Uploads files directly into the sandbox working directory.
4. Automatically skips ignored directories and files:
   - `.opscode/`
   - `.git/`
   - `.venv/`, `venv/`, `env/`
   - `node_modules/`
   - `__pycache__/`, `.pytest_cache/`
   - `*.pyc`, `*.lock` (optional exclusions)

---

## Setup scripts

Use `--sandbox-setup` to execute initialization tasks immediately after container boot:

```bash
opscode --sandbox modal --sandbox-setup ./scripts/ci-setup.sh
```

**`./scripts/ci-setup.sh`:**
```bash
#!/usr/bin/env bash
set -euo pipefail

# Install required DevOps CLIs
apt-get update && apt-get install -y opentofu kubectl helm awscli

# Verify toolchain versions
tofu version
kubectl version --client=true
helm version
```

---

## Architecture & Execution Routing

When a remote sandbox is active, OpsCode uses a `CompositeBackend` to route operations intelligently:

```
┌────────────────────────────────────────────────────────┐
│                   OpsCode Tool Execution               │
├────────────────────────────────────────────────────────┤
│ Shell Execution (`execute`)     ───> Remote Sandbox    │
│ Filesystem Reads (`read_file`)  ───> Remote Sandbox    │
│ Filesystem Writes (`write_file`)───> Remote Sandbox    │
│ Grep / Glob / LS                ───> Remote Sandbox    │
│ Web Search (`web_search`)       ───> Local Host        │
│ URL Extraction (`fetch_url`)    ───> Local Host        │
└────────────────────────────────────────────────────────┘
```

All remote sandboxes are registered with `atexit` lifecycle handlers to guarantee clean remote container termination when your session ends.

---

## Non-interactive CI/CD execution

Sandboxes can be combined with `-n`, `-y`, and `--rubric` for zero-trust automation in GitHub Actions or GitLab CI:

```bash
opscode -n "Run OpenTofu plan and check for security violations" \
  --sandbox runloop \
  --sandbox-setup ./scripts/ci-init.sh \
  --rubric "tofu plan succeeds with zero syntax errors and no open security group ingress" \
  --quiet \
  -y
```
