# Terraform Variable Conventions & Type Standards

Detailed guidelines and standards for defining input variables in Terraform modules.

## Table of Contents
1. [Core Principles](#core-principles)
2. [Explicit Typing Rules](#explicit-typing-rules)
3. [Mandatory Descriptions](#mandatory-descriptions)
4. [Default Value Handling](#default-value-handling)
5. [Validation Rules](#validation-rules)
6. [Complex Object Types](#complex-object-types)
7. [Sensitivity & Security](#sensitivity--security)

---

## Core Principles

- Every input variable must be explicitly defined in `variables.tf`.
- Variables represent the module's public API contract—clarity, safety, and strict validation are paramount.
- Omit `default` for required variables; provide explicit defaults for optional variables.

---

## Explicit Typing Rules

Never use raw `any` types unless accepting unstructured dynamic data is genuinely required. Always specify explicit types.

### Primitive Types
- `string`: Text values, names, IDs, ARNs, CIDR blocks.
- `number`: Numeric values, port numbers, retention periods, capacities.
- `bool`: Feature flags, enabling/disabling module features (`true` / `false`).

### Collection Types
- `list(string)` or `set(string)`: Ordered or distinct collections of strings (e.g., subnet IDs, security group IDs).
- `map(string)`: Key-value string pairs (e.g., resource tags, environment variables).

```hcl
variable "subnet_ids" {
  type        = list(string)
  description = "List of VPC subnet IDs where resources will be deployed."
}

variable "custom_environment_variables" {
  type        = map(string)
  description = "Key-value map of environment variables passed to the container."
  default     = {}
}
```

---

## Mandatory Descriptions

Every variable definition MUST include a `description` string.

Good description criteria:
- State what the variable controls.
- Specify expected format or unit (e.g., "in GB", "in days", "CIDR notation e.g., 10.0.0.0/16").
- Indicate valid option choices if applicable.

---

## Default Value Handling

- **Required Variables**: Do NOT specify a `default` attribute. This forces the caller to provide a value.
- **Optional Variables**: Always supply a `default` attribute matching the explicit type.
- **Null Defaults**: Use `default = null` for optional attributes when Terraform or AWS provider defaults should take effect if unsupplied.

```hcl
# Optional string with null default
variable "kms_key_arn" {
  type        = string
  description = "ARN of the customer managed KMS key for encryption. Omit for default AWS key."
  default     = null
}
```

---

## Validation Rules

Use `validation` blocks to enforce constraints early during `terraform plan` rather than failing during resource deployment.

```hcl
variable "instance_type" {
  type        = string
  description = "EC2 instance class."
  default     = "t3.micro"

  validation {
    condition     = can(regex("^[trm][3-6][a-z]?\\.", var.instance_type))
    error_message = "Instance type must be a valid general purpose, compute, or memory optimized instance (e.g. t3.micro, m5.large)."
  }
}
```

---

## Complex Object Types

When a variable expects structured configuration, use explicit `object({...})` types instead of untyped maps or objects.

```hcl
variable "scaling_config" {
  type = object({
    min_capacity = number
    max_capacity = number
    desired_capacity = optional(number, 2)
  })
  description = "Auto-scaling capacity constraints."
  default = {
    min_capacity = 1
    max_capacity = 5
    desired_capacity = 2
  }
}
```

---

## Sensitivity & Security

Set `sensitive = true` for variables holding passwords, tokens, private keys, or credentials to prevent them from printing in CLI outputs and logs.

```hcl
variable "db_password" {
  type        = string
  description = "Master password for the database cluster."
  sensitive   = true
}
```
