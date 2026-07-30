### Terraform / OpenTofu Conventions
- Formatting: Always apply standard formatting (2-space indent, align equals signs).
- Version Constraints: Always specify version constraints for required providers and require a minimum terraform version.
- Variables and Outputs: Use `locals` for intermediate computations, explicitly define types and descriptions for `variable` declarations, and document all `output` values.
- State: Never commit local terraform state files (`.tfstate` or `.tfstate.backup`) or `.terraform` directories.

### Helm Charts
- Structure: Adhere to standard Helm structure (Chart.yaml, values.yaml, templates/, charts/).
- Helpers: Utilize `_helpers.tpl` template helpers for consistent naming and label generation.
- Values Validation: Ensure all value references are documented in values.yaml. Run `helm lint` and `helm template` to check syntax.

### Kubernetes Resource Standards
- Security Context: Set non-root user permissions, read-only root filesystems, and drop capabilities where appropriate.
- Probes: Always configure `livenessProbe`, `readinessProbe`, and `startupProbe` for application workloads.
- Resources: Define resource requests and limits (CPU and memory) to prevent cluster starvation.

### ArgoCD Manifests
- Sync Policies: Define automated sync policies with `prune` and `selfHeal` set to true where safe.
- Applications and ApplicationSets: Organize multi-environment deployments using ApplicationSets.

### Ansible Playbooks and Roles
- Structure: Keep tasks modular by extracting them into roles. Use `main.yml` as the entrypoint.
- Safety: Ensure playbooks are idempotent. Use `ansible-playbook --check` to dry-run changes.

### CI/CD Pipelines
- Workflows: Use pin versions for Github Actions (e.g. `actions/checkout@v4`).
- Security: Never expose secrets in plaintext; load them from environment variables or secrets managers.

### Cloud CLIs
- CLI Safety: Prefer read-only or dry-run checks before running destructive CLI actions (e.g. `--dry-run` or `--confirm`).
