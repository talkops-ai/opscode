---
name: opentofu-state-management
description: >
  OpenTofu-native state management patterns covering client-side AES-256-GCM
  state encryption, native S3 state locking without DynamoDB, and KMS key
  rotation with fallback blocks. Use when: (1) configuring state encryption
  using the encryption block with aws_kms key_provider, (2) enabling enforced
  encryption to prevent accidental plaintext state writes, (3) implementing
  key rotation with fallback blocks for zero-downtime migration,
  (4) configuring native S3 locking via use_lockfile = true, or
  (5) eliminating legacy DynamoDB table requirements from backend config.
  Do NOT use for resource-level encryption (use opentofu-data-security) or
  IAM policies (use opentofu-iam-security).
license: MIT
compatibility: designed for deepagents-code
---

# OpenTofu State Management

Advanced, OpenTofu-native state management patterns that supersede legacy Terraform workarounds. The OpenTofu state file is the ultimate source of truth for infrastructure, containing plaintext secrets, passwords, and structural metadata — it must be protected with defence-in-depth.

---

## Core Principles

1. **Client-Side Encryption First**: Never rely solely on server-side encryption (SSE). Always encrypt state before it leaves the machine.
2. **Enforced Encryption**: Set `enforced = true` to mathematically prevent accidental plaintext state writes.
3. **No DynamoDB**: Use native S3 locking (`use_lockfile = true`) — the DynamoDB table requirement is deprecated.
4. **Safe Key Rotation**: Use fallback blocks to rotate encryption keys with zero downtime.

---

## Client-Side State Encryption (AES-256-GCM)

OpenTofu v1.7+ natively supports client-side state encryption. The state payload is encrypted **before** transmission to the remote backend, ensuring that even if someone gains read access to the S3 bucket, they cannot extract secrets.

### Configuration

Inject an `encryption` block within the top-level `terraform` configuration:

```hcl
terraform {
  required_version = ">= 1.8.0"

  encryption {
    key_provider "aws_kms" "state_key" {
      kms_key_id = "arn:aws:kms:us-east-1:123456789012:key/abcd-1234-efgh-5678"
      region     = "us-east-1"
    }

    method "aes_gcm" "state_encryption" {
      keys = key_provider.aws_kms.state_key
    }

    state {
      method   = method.aes_gcm.state_encryption
      enforced = true
    }

    plan {
      method   = method.aes_gcm.state_encryption
      enforced = true
    }
  }
}
```

### Key Points

- **`key_provider = aws_kms`**: Ties the encryption process to a customer-managed KMS key, leveraging AWS's key management lifecycle.
- **`method = aes_gcm`**: Uses AES-256-GCM authenticated encryption — the gold standard for symmetric encryption.
- **`enforced = true`**: The CI/CD pipeline will **critically fail** if state cannot be successfully encrypted. This prevents accidental plaintext state writes to the remote backend.
- Apply encryption to both `state` and `plan` blocks for full protection.

---

## KMS Key Rotation with Fallback Blocks

The AES-GCM cipher can degrade in security if a single key encrypts too much data over time (key saturation). When rotating KMS keys, do **not** blindly overwrite the existing `key_provider`.

Instead, use OpenTofu's **fallback block** architecture to perform a zero-downtime migration:

```hcl
terraform {
  encryption {
    # New key (write)
    key_provider "aws_kms" "new_key" {
      kms_key_id = "arn:aws:kms:us-east-1:123456789012:key/new-key-id"
      region     = "us-east-1"
    }

    # Old key (read-only fallback)
    key_provider "aws_kms" "old_key" {
      kms_key_id = "arn:aws:kms:us-east-1:123456789012:key/old-key-id"
      region     = "us-east-1"
    }

    method "aes_gcm" "new_encryption" {
      keys = key_provider.aws_kms.new_key
    }

    method "aes_gcm" "old_encryption" {
      keys = key_provider.aws_kms.old_key
    }

    state {
      method   = method.aes_gcm.new_encryption
      enforced = true

      fallback {
        method = method.aes_gcm.old_encryption
      }
    }

    plan {
      method   = method.aes_gcm.new_encryption
      enforced = true

      fallback {
        method = method.aes_gcm.old_encryption
      }
    }
  }
}
```

**How it works**: OpenTofu reads the existing state using the old (retiring) key via the `fallback` block, then encrypts the newly updated state with the new key. This ensures zero downtime and prevents permanent lockout during migration. After all state files have been re-encrypted, the `fallback` block can be safely removed.

---

## Native S3 State Locking (No DynamoDB)

Historically, state locking required a dedicated DynamoDB table to prevent concurrent `tofu apply` operations from corrupting the state file. OpenTofu eliminates this by implementing conditional writes directly against the S3 API using the `If-None-Match` header.

### Configuration

```hcl
terraform {
  backend "s3" {
    bucket       = "my-project-state"
    key          = "modules/my-module/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true    # Native S3 locking — no DynamoDB required
    # NOTE: Do NOT include dynamodb_table — it is deprecated
  }
}
```

### Benefits

- **Cost Reduction**: Eliminates the DynamoDB table and its associated read/write capacity costs.
- **Simplified Bootstrapping**: No need to provision locking infrastructure before managing state.
- **Reduced IAM Scope**: The orchestration pipeline no longer requires DynamoDB API permissions.
- **Race Condition Prevention**: Conditional writes guarantee that only one `tofu apply` can write state at a time.

---

## Complete Example: Production Backend

```hcl
terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket       = "myorg-tofu-state"
    key          = "prod/vpc/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }

  encryption {
    key_provider "aws_kms" "state_key" {
      kms_key_id = "arn:aws:kms:us-east-1:123456789012:key/state-encryption-key"
      region     = "us-east-1"
    }

    method "aes_gcm" "encrypt" {
      keys = key_provider.aws_kms.state_key
    }

    state {
      method   = method.aes_gcm.encrypt
      enforced = true
    }

    plan {
      method   = method.aes_gcm.encrypt
      enforced = true
    }
  }
}
```
