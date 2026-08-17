# Goals and rubrics

> Set goals interactively or grade work automatically in CI/CD

OpsCode gives you two ways to set expectations for the agent's work:

- **Goals** — For interactive sessions. OpsCode generates a checklist of acceptance criteria and tracks progress in the TUI as you work together.
- **Rubrics** — For automated CI/CD. A dedicated grader model evaluates the agent's output against your criteria and feeds back failures until everything passes.

## Goals

Goals work best in **interactive sessions** where you're working alongside the agent. OpsCode breaks your objective into acceptance criteria and tracks each one in real-time.

### Set a goal

At launch:

```bash
ops --goal "Harden the production EKS cluster with Pod Security Standards and NetworkPolicies"
```

Or inside a session:

```
/goal Implement AWS KMS state encryption and cross-account IAM roles for OpenTofu
```

### How it works

1. OpsCode analyzes your workspace and generates verifiable acceptance criteria.
2. A panel in the TUI shows criteria status in real-time: `[pending]`, `[passed]`, `[failed]`.
3. The agent uses built-in tools (`get_goal`, `update_goal`) to inspect and update progress.

## Rubrics

Rubrics provide autonomous quality assurance for **non-interactive and CI/CD** workflows. The agent does the work, a grader model checks the results, and if anything fails, the agent iterates on fixes automatically.

### Set a rubric

```bash
ops -n "Author a Terraform module for an AWS RDS Aurora Postgres cluster" \
  --rubric "1. Multi-AZ deployment is enabled.
2. Storage is encrypted with AWS KMS customer managed key.
3. Automated backups are retained for 14 days.
4. Enhanced monitoring and Performance Insights are enabled.
5. Security group restricts port 5432 to VPC CIDR only."
```

### Load from a file

For complex specs, load criteria from a file using `@path`:

```bash
ops -n "Refactor VPC networking" --rubric @specs/vpc-rubric.md
```

**`specs/vpc-rubric.md`:**
```markdown
# VPC Architecture Rubric

1. Primary CIDR block is 10.100.0.0/16 with 3 public and 3 private subnets across 3 AZs.
2. NAT Gateways are deployed across all 3 availability zones.
3. Flow logs publish to an encrypted CloudWatch Log Group.
4. Default security group denies all inbound and outbound traffic.
5. VPC endpoints are provisioned for S3 and DynamoDB.
```

### Rubric options

| Flag | What it does |
|---|---|
| `--rubric TEXT\|@PATH` | Acceptance criteria (inline text or `@path` to a file) |
| `--rubric-model MODEL` | Dedicated grader model (e.g. `--rubric-model openai:gpt-4.1`) |
| `--rubric-max-iterations N` | Maximum fix-and-recheck cycles |

### How the grading loop works

1. The worker agent completes the initial task.
2. The grader model evaluates the work against the rubric.
3. If all criteria pass → done.
4. If anything fails → the grader sends a specific deficiency report back to the worker.
5. The worker fixes the issues and resubmits.
6. This repeats until everything passes or the iteration limit is reached.

Using a separate grader model (e.g., grading an Anthropic worker with OpenAI GPT-4.1) avoids self-evaluation bias and catches edge cases.

## Goals vs. rubrics

| | Goals | Rubrics |
|---|---|---|
| **Best for** | Interactive sessions | CI/CD and automation |
| **Criteria** | Auto-generated from your objective | You define them |
| **Iteration** | You guide the agent with real-time feedback | Fully autonomous fix-and-recheck loop |
| **Grader** | Same model | Dedicated model (optional) |
| **CLI flag** | `--goal TEXT` | `--rubric TEXT\|@PATH` |

## CI/CD examples

### Kubernetes manifest verification

```bash
ops -n "Audit and fix deployment.yaml" \
  --rubric "1. Non-root security context is configured.
2. Read-only root filesystem is enabled.
3. Liveness and readiness probes have timeout thresholds.
4. CPU/memory limits and requests are defined." \
  --rubric-max-iterations 3 \
  --quiet
```

### GitHub Actions workflow generation

```bash
ops -n "Create a release pipeline workflow" \
  --rubric @specs/gha-rubric.md \
  --rubric-model "anthropic:claude-opus-4-7" \
  --max-turns 15
```
