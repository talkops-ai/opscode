# Memory and Skills

> Persistent memory across sessions and extensible skills for deep DevOps and Platform Engineering expertise.

OpsCode provides two complementary knowledge systems: **Persistent Memory** (`AGENTS.md`) for user preferences, project conventions, and past architectural decisions; and **Skills** (`SKILL.md`) for structured, multi-step engineering procedures.

---

## Memory

Memory allows OpsCode to maintain context across sessions — coding conventions, cluster topology rules, security policies, and team preferences. Memories are Markdown files injected into the system prompt at turn initialization.

### Storage locations and precedence

Memories follow a scoped hierarchy:

| Scope | Path | Purpose |
|---|---|---|
| **Project** (highest priority) | `.opscode/memory/` | Project-specific conventions and decisions |
| **User** (fallback) | `~/.opscode/memory/` | Global developer preferences across all workspaces |

When both scopes contain a memory with the same key, the project entry takes precedence.

### Memory limits

- Maximum **200 lines** injected into context per session
- Maximum **25 KB** total memory bytes per session

These caps ensure memory never starves the model's context window.

### Managing memory

Use `/memory` inside an interactive session:

```
/memory                    # List all loaded memories
/memory save <key>         # Save a memory entry
/memory delete <key>       # Delete a memory entry
```

Or instruct the agent naturally:

```
Remember that we use AWS KMS customer-managed keys for all S3 buckets in this repository
```

This triggers the built-in `remember` skill, which captures the learning into the appropriate memory file or `AGENTS.md`.

### AGENTS.md

In addition to granular memory files, OpsCode loads `AGENTS.md` files as persistent system instructions:

| Path | Scope |
|---|---|
| `.opscode/AGENTS.md` | Project-level instructions (committed to Git) |
| `AGENTS.md` | Repository root instructions (alternative location) |
| `~/.opscode/{agent}/AGENTS.md` | User-level agent instructions |

All discovered project files are combined, providing unified project guidelines.

---

## Skills

Skills are modular, executable instruction sets extending OpsCode with deep domain workflows. Each skill is a self-contained directory with a `SKILL.md` file featuring YAML frontmatter and structured Markdown procedures.

### Deep Agent Skills vs. Subagent Skills

- **Deep Agent Skills (Global):** Discovered across the 7-tier resolution hierarchy and loaded directly into the root agent's turn prompt (e.g. `cloud-core`, `docker`, `kubernetes`, `remember`).
- **Subagent Skills (Encapsulated):** Bundled exclusively inside individual subagent packages (such as OpenTofu, Terraform, Helm, Ansible, Jenkins, and GitHub Actions subagents). These skills are activated only when delegating to that specific subagent.

### Skill directory structure

```
skill-name/
├── SKILL.md          # Required — main instructions with YAML frontmatter
├── scripts/          # Optional — executable helper scripts
├── references/       # Optional — domain documentation and cheat sheets
└── assets/           # Optional — templates, boilerplate, and schema examples
```

### SKILL.md format

```markdown
---
name: kubernetes
description: "Author, audit, and troubleshoot Kubernetes manifests following Pod Security Standards"
domain: DevOps
compatibility: "kubectl >= 1.28"
allowed_tools:
  - execute
  - write_file
  - read_file
metadata:
  domain: kubernetes
  difficulty: intermediate
---

# Kubernetes Engineering Skill

You are an expert Kubernetes platform engineer. When authoring or debugging manifests:

1. Always define explicit CPU and memory `requests` and `limits`.
2. Configure `readinessProbe` and `livenessProbe` on all long-running workloads.
3. Enforce non-root `securityContext` (`runAsNonRoot: true`, `readOnlyRootFilesystem: true`).
4. Include standard labels: `app.kubernetes.io/name`, `app.kubernetes.io/instance`, `app.kubernetes.io/version`.
```

---

## The 7-Tier Skill Resolution Hierarchy

OpsCode resolves skills using a strict 7-tier precedence hierarchy (Tier 1 is base; Tier 7 is highest override):

| Tier | Name | Location | Scope |
|---|---|---|---|
| **Tier 1** | Built-in Skills | `src/opscode/built_in_skills/` | Shipped with OpsCode core |
| **Tier 2** | Plugin Skills | Active Plugin `skills/` directories | Installed/Project Plugins (Namespaced) |
| **Tier 3** | User OpsCode Skills | `~/.opscode/skills/` | User Global OpsCode |
| **Tier 4** | User Agents Skills | `~/.agents/skills/` | Universal User Tool-Agnostic |
| **Tier 5** | Project OpsCode Skills | `.opscode/skills/` | Project Specific (Git tracked) |
| **Tier 6** | Project Agents Skills | `.agents/skills/` | Universal Project Tool-Agnostic |
| **Tier 7** | Claude Experimental Skills | `~/.claude/skills/`, `.claude/skills/` | Ecosystem Compatibility |

---

## Built-in Global Skills

OpsCode core bundles 4 root skills loaded into the main agent:

| Skill | Description |
|---|---|
| **`cloud-core`** | Cloud infrastructure fundamentals, IAM principles, networking topologies (VPC/VNet), resource tagging, and cost governance |
| **`docker`** | Dockerfile multi-stage builds, rootless container security, minimal base images (Distroless/Alpine), layer caching optimization |
| **`kubernetes`** | Manifest authoring, Pod Security Standards (Baseline/Restricted), resource quotas, affinity rules, probes, and NetworkPolicies |
| **`remember`** | Conversation analysis to extract architectural decisions, team patterns, and save them into persistent memory or scaffold new skills |

---

## Using skills

### Automatic activation
Skills activate dynamically based on their `description` and domain metadata when the agent interprets a matching user turn.

### Manual invocation
Browse and invoke skills explicitly:

```
/skills                    # Open interactive skills browser
/skill kubernetes          # Explicitly invoke a skill
```

From the CLI at launch:

```bash
opscode -s kubernetes      # Pre-load skill on startup
```

### Creating custom skills

Scaffold a new skill directory in your project or global user path:

```bash
opscode skills create my-custom-skill
```

Or write `SKILL.md` directly into `.opscode/skills/my-custom-skill/`:

```markdown
---
name: my-custom-skill
description: "Internal release engineering workflow for staging and production deployments"
---

# Release Engineering Procedure

1. Run pre-flight linting and integration test suites.
2. Verify image digest signatures using Cosign.
3. Update Helm values in the GitOps deployment repository.
4. Trigger ArgoCD synchronization and monitor rollout health.
```

### The `remember` skill & `/skill-create`

The `remember` skill can automatically distill the current pair-programming session into a reusable skill:

- Run `/skill-create` inside an interactive session.
- OpsCode analyzes the conversation trajectory, extracts best practices and commands executed, and writes a complete `SKILL.md` file ready for future reuse.

### Skill trust

To safeguard against unauthorized repository skills, OpsCode records skill validation decisions in `~/.opscode/.state/skill_trust.json`.
