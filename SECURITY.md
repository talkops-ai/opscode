# Security Policy

OpsCode is built for infrastructure and DevOps automation where security, credential safety, and execution boundaries are paramount.

---

## 🛡️ Supported Versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |
| < 0.1.0 | ❌ |

---

## 🔒 Security Principles in OpsCode

OpsCode incorporates multiple defense-in-depth mechanisms:

1. **"Produce Diffs, Not Deployments"**: OpsCode generates plans and diffs for interactive approval. It is architecturally restrained from running un-sandboxed `terraform apply` or destructive deletions without human consent.
2. **3-Tier Approval Safety Engine**:
   - **Manual Mode**: Requires confirmation for every mutating shell command or file write.
   - **Auto Mode**: Classifies shell commands with static safety analysis (`security/shell_safety.py`) and only allows safe read-only operations (`ls`, `grep`, `tofu plan`).
   - **YOLO Mode**: Unrestricted execution requiring explicit initial acknowledgement.
3. **Unicode Security Scanner**: Analyzes prompts and files to neutralize Trojan Source attacks, bidirectional overrides, and homoglyph substitution.
4. **SSRF & Cloud Metadata Protection**: Blocks access to `169.254.169.254`, localhost, and private RFC-1918 CIDRs in URL extraction tools.
5. **Headless MCP Guard**: Categorizes MCP tool invocations into 4 tiers (`READ_ONLY`, `MUTATING_SAFE`, `MUTATING_DESTRUCTIVE`, `PRIVILEGED`).

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
