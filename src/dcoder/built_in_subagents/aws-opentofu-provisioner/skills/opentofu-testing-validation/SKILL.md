---
name: opentofu-testing-validation
description: >
  Testing, validation, and policy enforcement patterns for OpenTofu modules
  covering lifecycle preconditions and postconditions, the native .tftest.hcl
  testing framework, and Open Policy Agent (OPA) / Conftest integration. Use when:
  (1) embedding precondition checks to validate assumptions before resource creation,
  (2) embedding postcondition checks to verify guarantees after resource creation,
  (3) authoring .tftest.hcl test files with run blocks and assert blocks,
  (4) writing negative tests with expect_failures to prove defensive posture,
  (5) exporting tofu plan to JSON for policy-as-code validation, or
  (6) integrating Conftest with Rego policies for corporate governance.
  Do NOT use for state encryption (use opentofu-state-management) or IAM policies
  (use opentofu-iam-security).
license: MIT
compatibility: designed for deepagents-code
---

# OpenTofu Testing & Validation

Autonomous testing, self-validation, and policy enforcement patterns for OpenTofu modules. The agent must be capable of verifying its own output — without a robust testing loop, it risks pushing hallucinated or flawed configurations to the apply phase.

---

## Core Principles

1. **Self-Validating Code**: Embed preconditions and postconditions directly in resource HCL before relying on external frameworks.
2. **Test-Driven Infrastructure**: Author `.tftest.hcl` files alongside module generation — adopt a TDD posture.
3. **Negative Testing**: Use `expect_failures` to prove that security constraints and validation blocks work as intended.
4. **Policy-as-Code**: Integrate OPA/Conftest to enforce corporate governance guardrails autonomously.

---

## Step 1: Embed Preconditions & Postconditions

### Preconditions (Before Resource Creation)

Evaluated by the OpenTofu engine **before** a resource is created. Use to validate assumptions about data sources and input variables:

```hcl
data "aws_ami" "app" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_instance" "app" {
  ami           = data.aws_ami.app.id
  instance_type = var.instance_type

  lifecycle {
    precondition {
      condition     = data.aws_ami.app.architecture == "x86_64"
      error_message = "AMI architecture must be x86_64, got: ${data.aws_ami.app.architecture}"
    }
  }
}
```

### Postconditions (After Resource Creation)

Evaluated **after** the resource is created or updated, using the `self` object reference. Use to verify infrastructure guarantees:

```hcl
resource "aws_instance" "web" {
  ami                         = data.aws_ami.app.id
  instance_type               = var.instance_type
  associate_public_ip_address = true

  lifecycle {
    postcondition {
      condition     = self.public_ip != ""
      error_message = "EC2 instance failed to acquire a public IP address."
    }
  }
}

resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name

  lifecycle {
    postcondition {
      condition     = self.arn != ""
      error_message = "S3 bucket was created but ARN is empty."
    }
  }
}
```

If a postcondition fails, OpenTofu immediately halts the apply process and returns an error, preventing downstream dependent resources from cascading the failure.

---

## Step 2: Author `.tftest.hcl` Test Files

OpenTofu features a powerful, built-in testing framework invoked via `tofu test`. Author test files alongside module code:

```
module-root/
├── main.tf
├── variables.tf
├── outputs.tf
└── tests/
    ├── basic.tftest.hcl
    ├── security.tftest.hcl
    └── validation.tftest.hcl
```

### Basic Test Structure

Test files consist of `run` blocks that simulate `tofu plan` or `tofu apply` in isolated, ephemeral environments:

```hcl
# tests/basic.tftest.hcl

variables {
  environment   = "dev"
  project_name  = "test-project"
  bucket_name   = "test-bucket-dev"
}

run "creates_s3_bucket" {
  command = plan

  assert {
    condition     = aws_s3_bucket.this.bucket == "test-bucket-dev"
    error_message = "S3 bucket name does not match expected value."
  }

  assert {
    condition     = aws_s3_bucket.this.tags["Environment"] == "dev"
    error_message = "S3 bucket is missing the Environment tag."
  }
}

run "enables_encryption" {
  command = plan

  assert {
    condition     = aws_s3_bucket_server_side_encryption_configuration.this.rule[0].apply_server_side_encryption_by_default[0].sse_algorithm == "aws:kms"
    error_message = "S3 bucket must use KMS encryption."
  }
}
```

### Negative Testing with `expect_failures`

Validate that security constraints and validation blocks actually reject invalid input:

```hcl
# tests/security.tftest.hcl

run "rejects_invalid_environment" {
  command = plan

  variables {
    environment = "production"   # Invalid — not in allowed list
  }

  expect_failures = [
    var.environment,   # Expects the validation block on this variable to fail
  ]
}

run "rejects_public_bucket" {
  command = plan

  variables {
    enable_public_access = true
  }

  expect_failures = [
    aws_s3_bucket_public_access_block.this,
  ]
}
```

By passing intentionally invalid inputs and expecting the plan to fail, the agent mathematically proves the module's defensive posture.

---

## Step 3: Integrate OPA/Conftest Policy Checks

For enterprise-wide governance, integrate Open Policy Agent (OPA) via the **Conftest** utility:

### Workflow

```bash
# 1. Generate the execution plan in JSON format
tofu plan -out=tfplan
tofu show -json tfplan > plan.json

# 2. Run Conftest against corporate policies
conftest test plan.json --policy policies/
```

### Example Rego Policies

```
policies/
├── tags.rego           # Enforce mandatory tags
├── security.rego       # Block 0.0.0.0/0 ingress
└── encryption.rego     # Require KMS encryption
```

**Mandatory Tags Policy** (`policies/tags.rego`):

```rego
package main

deny[msg] {
  resource := input.resource_changes[_]
  resource.change.after.tags == null
  msg := sprintf("Resource %s is missing tags", [resource.address])
}

deny[msg] {
  resource := input.resource_changes[_]
  not resource.change.after.tags.CostCenter
  msg := sprintf("Resource %s is missing required CostCenter tag", [resource.address])
}
```

**Security Group Policy** (`policies/security.rego`):

```rego
package main

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_security_group_rule"
  resource.change.after.cidr_blocks[_] == "0.0.0.0/0"
  resource.change.after.type == "ingress"
  msg := sprintf("Security group %s allows 0.0.0.0/0 ingress", [resource.address])
}
```

### Autonomous Iteration

The agent can iterate on its HCL generation based on Conftest failure outputs until it passes all predefined corporate guardrails, ensuring that only fully compliant modules are finalised.

---

## Validation Command Reference

| Command | Purpose |
|---|---|
| `tofu validate` | Check HCL syntax, block structures, missing arguments, type mismatches |
| `tofu fmt -check` | Verify formatting compliance without modifying files |
| `tofu test` | Execute `.tftest.hcl` test suites in isolated environments |
| `tofu plan` | Generate execution plan, catch deep provider evaluation issues |
| `conftest test plan.json --policy policies/` | Run OPA Rego policies against the plan |
