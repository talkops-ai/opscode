---
name: ansible-security-operations
description: >-
  Security operations for Ansible automation covering privilege escalation
  management (become, sudoers.d), Ansible Vault secrets encryption, credential
  handling for Runner/Navigator, and observability data privacy. Use when:
  (1) configuring privilege escalation with become directives and passwordless
  sudo, (2) writing sudoers.d drop-in configurations with visudo validation,
  (3) encrypting sensitive variables with ansible-vault encrypt_string,
  (4) injecting vault passwords into Ansible Runner env/passwords, (5) handling
  API keys, certificates, and database credentials securely, or (6) ensuring
  observability telemetry does not leak decrypted secrets.
license: MIT
compatibility: designed for opscode
---

# Ansible Security Operations

Security governance for Ansible automation covering privilege escalation (`become`, `/etc/sudoers.d/`), secrets encryption (`ansible-vault`), Runner credential injection, and observability data privacy (`no_log`).

---

## Workflow Decision Tree

```
1. Privilege Escalation Governance
   ├── Restrict 'become: true' to tasks strictly requiring elevated privilege
   ├── Write drop-in policy files under '/etc/sudoers.d/'
   ├── Enforce 'validate: "/usr/sbin/visudo -cf %s"' on template tasks
   └── Refer to [references/privilege_escalation.md](references/privilege_escalation.md) for sudoers configuration
2. Secrets Encryption & Management
   ├── Encrypt sensitive values using 'ansible-vault encrypt_string'
   ├── Set 'no_log: true' on tasks processing secrets or tokens
   └── Consult [references/ansible_vault_guide.md](references/ansible_vault_guide.md) for inline vault encryption
3. Credential Injection in Execution Runtimes
   ├── Inject vault passwords into Runner 'private_data_dir/env/passwords'
   └── Keep plain-text passwords out of playbook files and inventory variables
4. Observability Privacy
   ├── Scrub task output and prevent secret leakage in telemetry/logs
   └── Refer to [references/observability_privacy.md](references/observability_privacy.md) for privacy patterns
```

---

## 1. Privilege Escalation & Sudoers

- Apply `become: true` at task level rather than play level.
- Deploy sudo policies via `/etc/sudoers.d/` with `validate: '/usr/sbin/visudo -cf %s'`.

See [references/privilege_escalation.md](references/privilege_escalation.md) for details and templates in [assets/sudoers_dropin.j2](assets/sudoers_dropin.j2).

---

## 2. Secrets Encryption (`ansible-vault`)

- Use `ansible-vault encrypt_string` to inline-encrypt passwords, API keys, and certificates.
- Set `no_log: true` on tasks handling sensitive responses to prevent output leakage.

See [references/ansible_vault_guide.md](references/ansible_vault_guide.md) for vault usage.

---

## 3. Observability Privacy

- Mask secrets in execution logs, callbacks, and telemetry collectors.

See [references/observability_privacy.md](references/observability_privacy.md) for guidelines.
