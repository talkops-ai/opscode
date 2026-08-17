# Security Policy

OpsCode runs shell commands, modifies files, and interacts with cloud infrastructure on your behalf. Security is a first-class concern across every layer of the agent.

---

## 🛡️ Supported Versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |
| < 0.1.0 | ❌ |

---

## 🔒 How OpsCode protects your environment

### Approval modes

Every mutating action (shell commands, file writes, infrastructure operations) goes through an approval gate before execution:

- **Manual mode** (default) — You approve every action individually.
- **Auto mode** (`-y`) — A safety classifier analyzes each command and auto-approves safe read-only operations (`ls`, `grep`, `terraform validate`). Mutating commands still require your approval.
- **YOLO mode** — Unrestricted execution after explicit risk acknowledgement. Designed for trusted sandbox environments.

Use `Shift+Tab` to cycle between modes in a session, or see [Approval Modes](docs/opscode-docs/approval-mode.md).

### Shell command safety

OpsCode statically analyzes every shell command before execution:

- **Dangerous patterns blocked** — Commands containing `rm -rf /`, pipe to `sh`, `curl | bash`, `dd if=`, and other destructive patterns are flagged and require explicit approval.
- **DevOps-aware classification** — Infrastructure commands are categorized as safe (`kubectl get`, `terraform plan`, `helm lint`) or destructive (`kubectl delete`, `terraform destroy`, `helm uninstall`) with appropriate gating.

### MCP tool security

When running unattended (headless mode or CI/CD), MCP tool calls are classified into security tiers:

| Tier | Policy |
|---|---|
| **Read-only** | Runs automatically |
| **Mutating-safe** | Gated in headless mode |
| **Mutating-destructive** | Blocked without explicit allowlist |
| **Privileged** | Blocked in headless mode |

### Unicode and prompt injection defense

OpsCode scans prompts, file contents, and tool inputs for:

- **Trojan Source attacks** — Bidirectional Unicode overrides that make code appear different from what's executed.
- **Homoglyph substitution** — Characters that look identical but have different Unicode codepoints.
- **Invisible control characters** — Zero-width joiners, right-to-left marks, and other invisible characters that can alter execution flow.

Detected issues are surfaced with detailed warnings before any action proceeds.

### SSRF and cloud metadata protection

URL extraction and web fetch tools validate all targets:

- Blocks access to cloud metadata endpoints (`169.254.169.254`).
- Blocks localhost, loopback, and private RFC-1918 addresses.
- Only allows `http` and `https` schemes.
- Resolves DNS before connecting and validates the resolved IP is public and globally routable.

### Credential safety

- **`.env` file isolation** — System-critical environment variables (`PATH`, `HOME`, `PYTHONPATH`, `LD_PRELOAD`, `SSH_AUTH_SOCK`, etc.) are blocked from being set via `.env` files to prevent environment hijacking.
- **API key masking** — API keys are never logged or displayed in output. The `/auth` manager stores credentials in `~/.opscode/.env` with restricted file permissions.
- **DevOps environment preservation** — Cloud credentials (`KUBECONFIG`, `AWS_PROFILE`, `GOOGLE_APPLICATION_CREDENTIALS`) are isolated and preserved across tool executions.

### Plugin and skill trust

- **Project MCP servers** — Require explicit approval on first use since they can be committed to Git by other contributors. Trust decisions are persisted so you're only asked once.
- **Project skills** — New skills from untrusted repositories require approval before activation.
- **Project hooks** — Require `--trust-project-hooks` or interactive approval since they execute arbitrary shell commands.
- **Global configs** — Configs in `~/.opscode/` are always trusted since they're in your home directory.

### Subagent isolation

Each subagent runs with:

- **Scoped tools** — Only the tools declared in its definition are available. A Terraform subagent can't access Ansible tools.
- **Isolated memory** — Intermediate reasoning stays inside the subagent and doesn't leak to other subagents or the main conversation.
- **Scoped MCP** — Subagent MCP sessions start when the subagent is invoked and stop when it finishes.

### Remote sandboxes

For maximum isolation, run OpsCode inside a [remote sandbox](docs/opscode-docs/remote-sandboxes.md) — all shell commands and file operations execute in an ephemeral cloud container instead of on your workstation.

---

## 🚨 Reporting a Vulnerability

If you discover a potential security vulnerability in OpsCode:

1. **Do NOT file a public GitHub issue.**
2. Send a detailed report to the security team at:
   - **Email:** `security@talkops.ai`
3. Please include:
   - Description of the vulnerability
   - Proof-of-concept steps to reproduce
   - Potential impact and affected versions

We commit to acknowledging your report within 48 hours and providing regular updates throughout the remediation process.
