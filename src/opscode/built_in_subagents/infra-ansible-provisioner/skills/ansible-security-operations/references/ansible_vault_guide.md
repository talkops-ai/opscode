# Ansible Vault & Secrets Encryption Guide

Encrypting variables, files, and injecting vault passwords into Ansible Runner executions.

## 1. Encrypting Variables (`ansible-vault encrypt_string`)

Prefer inline encrypted strings over whole-file encryption when only specific keys contain secrets.

### Command Example

```bash
ansible-vault encrypt_string 'my-super-secret-password' --name 'db_password'
```

### Inlined Encrypted String Output in `vars/main.yml`

```yaml
---
db_user: app_user
db_password: !vault |
          $ANSIBLE_VAULT;1.1;AES256
          36626539303131663030386237303061613038656163353434653531393863333333393931653835
          32633038316133333161303032333034373934336136616200313531393635393138376537333536
          37003032383830386265326532663937303534353463323062333634363233363338363737333837
```

---

## 2. Masking Output with `no_log`

Always set `no_log: true` on tasks handling sensitive credentials to prevent secrets leaking into console stdout or callback output artifacts.

```yaml
- name: Authenticate against internal API
  ansible.builtin.uri:
    url: https://api.internal.example.com/v1/auth
    method: POST
    body_format: json
    body:
      username: "{{ api_user }}"
      password: "{{ db_password }}"
  register: auth_response
  no_log: true
```

---

## 3. Injecting Vault Passwords into Ansible Runner

When executing via Ansible Runner or Ansible Navigator, inject vault passwords through `private_data_dir/env/passwords`:

```yaml
# env/passwords file
^Vault: "secret_vault_password_here"
```
