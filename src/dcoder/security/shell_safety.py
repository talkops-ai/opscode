import re
import shlex

DANGEROUS_SHELL_PATTERNS = (
    "$(",  # Command substitution
    "`",  # Backtick command substitution
    "$'",  # ANSI-C quoting
    "\n",  # Newline
    "\r",  # Carriage return
    "\t",  # Tab
    "<(",  # Process substitution (input)
    ">(",  # Process substitution (output)
    "<<<",  # Here-string
    "<<",  # Here-doc
    ">>",  # Append redirect
    ">",  # Output redirect
    "<",  # Input redirect
    "${",  # Variable expansion with braces
)

DEVOPS_SAFE_COMMANDS = [
    # Terraform read-only
    "terraform validate", "terraform fmt", "terraform plan",
    "terraform show", "terraform state list", "terraform state show",
    "terraform version", "terraform providers",
    
    # Helm read-only
    "helm lint", "helm template", "helm list", "helm status",
    "helm get", "helm search", "helm version",
    
    # Kubectl read-only
    "kubectl get", "kubectl describe", "kubectl logs",
    "kubectl explain", "kubectl api-resources",
    "kubectl config view", "kubectl config current-context",
    
    # Ansible read-only
    "ansible --version", "ansible-playbook --check",
    "ansible-lint", "ansible-inventory --list",
    
    # ArgoCD read-only
    "argocd app list", "argocd app get", "argocd app diff",
    
    # General safe
    "git", "cat", "ls", "find", "grep", "head", "tail",
    "wc", "sort", "uniq", "diff", "jq", "yq",
]

DEVOPS_DESTRUCTIVE_COMMANDS = [
    # These ALWAYS require HITL approval
    "terraform apply", "terraform destroy", "terraform import",
    "helm install", "helm upgrade", "helm uninstall", "helm rollback",
    "kubectl apply", "kubectl delete", "kubectl patch", "kubectl edit",
    "kubectl scale", "kubectl rollout",
    "ansible-playbook",  # without --check
    "argocd app sync", "argocd app delete",
]

def contains_dangerous_patterns(command: str) -> bool:
    if any(pattern in command for pattern in DANGEROUS_SHELL_PATTERNS):
        return True

    # Bare variable expansion
    if re.search(r"\$[A-Za-z_]", command):
        return True

    # Standalone & (background execution)
    return bool(re.search(r"(?<![&])&(?![&])", command))

def is_shell_command_allowed(command: str, allow_list: list[str] | None) -> bool:
    """Validate prefix match on whitespace-separated command tokens."""
    if not allow_list or not command or not command.strip():
        return False

    if contains_dangerous_patterns(command):
        return False

    allow_entries = [entry.strip() for entry in allow_list if entry.strip()]
    if not allow_entries:
        return False

    # Split compound commands
    segments = re.split(r"&&|\|\||[|;]", command)
    found_command = False

    for raw_segment in segments:
        segment = raw_segment.strip()
        if not segment:
            continue

        try:
            tokens = shlex.split(segment)
            if not tokens:
                continue
            found_command = True
            
            matched = False
            for entry in allow_entries:
                entry_tokens = shlex.split(entry)
                if not entry_tokens:
                    continue
                if len(tokens) >= len(entry_tokens) and tokens[:len(entry_tokens)] == entry_tokens:
                    matched = True
                    break
            
            if not matched:
                return False
        except ValueError:
            return False

    return found_command
