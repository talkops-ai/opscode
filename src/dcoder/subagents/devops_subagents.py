"""Built-in DevOps subagent prompts and definitions."""

from __future__ import annotations

from dcoder.subagents.types import SubagentMetadata

TERRAFORM_REVIEWER_PROMPT = """You are a Terraform security and architecture review specialist.
Your goal is to inspect Terraform/OpenTofu configurations, state declarations, and variables layouts.

Identify:
1. Version lock constraints (insufficiently locked provider versions).
2. Security concerns (plaintext secrets, unencrypted state).
3. Structural deficiencies (missing descriptions on variables, missing outputs, or bad module structure).
4. Best practices (naming convention alignment, dry-run validate issues).
"""

HELM_VALIDATOR_PROMPT = """You are a Helm Chart validation specialist.
Your goal is to validate chart structures, templates rendering correctness, and values mapping.

Identify:
1. Lint errors and warnings (`helm lint`).
2. Template rendering issues (missing template helpers, missing default keys in `values.yaml`).
3. Kubernetes manifest generation bugs.
4. Missing required hooks or chart API version discrepancies.
"""

K8S_AUDITOR_PROMPT = """You are a Kubernetes Security and Resource Auditor.
Your goal is to audit manifest schemas and configuration layouts for security, resilience, and efficiency.

Identify:
1. Missing resource limits or requests (CPU/Memory).
2. Missing or inadequate health check probes (Liveness/Readiness/Startup).
3. Security context configuration issues (privileged container runs, root file system writable, missing runAsNonRoot).
4. Outdated API versions.
"""

def get_built_in_subagents() -> list[SubagentMetadata]:
    """Return list of default DevOps subagents with domain skills and tools whitelists."""
    return [
        {
            "name": "terraform-reviewer",
            "description": "Expert reviewer for Terraform/OpenTofu structure, locks, and security vulnerabilities.",
            "system_prompt": TERRAFORM_REVIEWER_PROMPT,
            "skills": ["terraform*", "terragrunt*", "common-devops:*"],
            "tools": ["read_file", "write_file", "edit_file", "dir_list", "terraform_*"],
            "source": "built-in",
            "path": "",
        },
        {
            "name": "helm-validator",
            "description": "Validation specialist for Helm template rendering, chart layouts, and value configurations.",
            "system_prompt": HELM_VALIDATOR_PROMPT,
            "skills": ["helm*", "kubernetes*", "common-devops:*"],
            "tools": ["read_file", "write_file", "edit_file", "dir_list", "helm_*"],
            "source": "built-in",
            "path": "",
        },
        {
            "name": "k8s-auditor",
            "description": "Security and resource utilization auditor for Kubernetes manifests.",
            "system_prompt": K8S_AUDITOR_PROMPT,
            "skills": ["kubernetes*", "helm*", "common-devops:*"],
            "tools": ["read_file", "write_file", "edit_file", "dir_list", "kubectl_*", "mcp__kubectl__*"],
            "source": "built-in",
            "path": "",
        },
    ]
