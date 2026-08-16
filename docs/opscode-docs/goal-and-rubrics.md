# Goals and Rubrics

> Define measurable objectives with goals in interactive sessions, or enforce deterministic acceptance criteria with self-evaluation rubric loops in automated workflows.

OpsCode provides two complementary evaluation frameworks:
1. **Interactive Goals (`--goal` / `/goal`):** Deconstructs high-level objectives into structured acceptance criteria and tracks interactive progress.
2. **Self-Evaluating Rubrics (`--rubric`):** Employs an autonomous grading loop in non-interactive mode where a dedicated grader model inspects agent outputs against a rubric until all criteria pass.

---

## Interactive Goals

Goals are designed for **interactive exploratory sessions**. OpsCode generates a live checklist of acceptance criteria that are evaluated dynamically throughout the turn execution loop.

### Using goals

From the CLI at startup:

```bash
opscode --goal "Harden the production EKS cluster with Pod Security Standards and NetworkPolicies"
```

Or inside an active interactive session:

```
/goal Implement AWS KMS state encryption and cross-account IAM roles for OpenTofu
```

### Architecture & execution flow

1. **Criteria Generation (`GoalCriteriaMiddleware`):** A criteria agent analyzes the repository workspace and generates clear, verifiable acceptance criteria.
2. **Visual Progress Tracking (`GoalStateNoticeMiddleware` & `GoalReviewWidget`):** A dedicated TUI panel displays criteria status in real-time (`[pending]`, `[passed]`, `[failed]`).
3. **Goal State Tools:** The agent inspects and updates criteria progress via native tools (`get_goal`, `update_goal`).

---

## Self-Evaluating Rubrics

Rubrics provide autonomous quality assurance for **non-interactive (`-n`) and CI/CD automation**. OpsCode executes the task, invokes a grader model to verify criteria, and loops automatically to fix any deficiencies.

### Using rubrics

```bash
opscode -n "Author a Terraform module for an AWS RDS Aurora Postgres cluster" \
  --rubric "1. Multi-AZ deployment is enabled.
2. Storage is encrypted with AWS KMS customer managed key.
3. Automated backups are retained for 14 days.
4. Enhanced monitoring and Performance Insights are enabled.
5. Security group restricts database port 5432 to VPC CIDR only."
```

### Rubric from a file

For complex specifications, load criteria from a file using `@path`:

```bash
opscode -n "Refactor VPC networking" --rubric @specs/vpc-rubric.md
```

**`specs/vpc-rubric.md`:**
```markdown
# VPC Architecture Rubric

1. Primary CIDR block is 10.100.0.0/16 with 3 public and 3 private subnets across 3 AZs.
2. NAT Gateways are deployed across all 3 availability zones for high availability.
3. Flow logs are configured to publish to an encrypted CloudWatch Log Group.
4. Default security group denies all inbound and outbound traffic.
5. VPC endpoints are provisioned for S3 and DynamoDB.
```

### Rubric CLI options

| Flag | Description |
|---|---|
| `--rubric TEXT\|@PATH` | Acceptance criteria string or `@path` to a markdown file |
| `--rubric-model MODEL` | Dedicated grader model for evaluation (e.g. `--rubric-model openai:gpt-4.1`) |
| `--rubric-max-iterations N` | Maximum self-correction iteration loops before completing |

### Grader loop architecture (`ReliableRubricMiddleware`)

```
┌────────────────────────────────────────────────────────┐
│                   Rubric Evaluation Loop               │
├────────────────────────────────────────────────────────┤
│ 1. Worker Agent completes initial task execution       │
│ 2. Grader Model evaluates work tree against rubric     │
│ 3. If all criteria PASS ──> Return final success       │
│ 4. If any criteria FAIL ──> Grader feeds back specific │
│    deficiency report into Worker Agent context         │
│ 5. Worker iterates on fixes and re-submits to Grader   │
│ 6. Repeats until PASS or max iterations reached        │
└────────────────────────────────────────────────────────┘
```

Using a separate grader model (e.g., grading an Anthropic worker with OpenAI GPT-4.1 or vice versa) avoids self-evaluation bias and catches subtle edge cases.

---

## Goals vs. Rubrics Comparison

| Feature | Goals | Rubrics |
|---|---|---|
| **Primary Mode** | Interactive TUI | Non-interactive (`-n`) / CI/CD |
| **Criteria Source** | Auto-generated from objective | User-defined or specification file |
| **Iteration Loop** | Human-guided with real-time UI checklist | Fully autonomous self-correction loop |
| **Middleware** | `GoalCriteriaMiddleware`, `GoalStateNoticeMiddleware` | `ReliableRubricMiddleware` |
| **Grader Model** | Interactive model | Dedicated grader (`--rubric-model`) |
| **CLI Flag** | `--goal TEXT` | `--rubric TEXT\|@PATH` |

---

## DevOps CI/CD examples

### Automated Kubernetes manifest verification

```bash
opscode -n "Audit and fix deployment.yaml" \
  --rubric "1. Non-root security context is configured.
2. Read-only root filesystem is enabled.
3. Liveness and readiness probes have timeout and failure thresholds.
4. CPU/memory limits and requests are defined." \
  --rubric-max-iterations 3 \
  --quiet
```

### Automated GitHub Actions workflow generation

```bash
opscode -n "Create a release pipeline workflow" \
  --rubric @specs/gha-rubric.md \
  --rubric-model "anthropic:claude-opus-4-7" \
  --max-turns 15
```
