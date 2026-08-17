# Memory and skills

> Persistent memory across sessions and reusable skills for domain expertise

There are two ways to customize how OpsCode works:

* **Memory**: `AGENTS.md` files and saved memories that persist across sessions. Use memory for coding style, project conventions, and learned patterns.
* **Skills**: Reusable, on-demand capabilities that OpsCode discovers and reads when relevant. Use skills for task-specific workflows, best practices, and reference docs.

In practice, skills and memory sit on a spectrum. Use `/remember` to prompt the agent to update its memory and skills from the current conversation.

## Memory

### Automatic memory

As you work with OpsCode, it can automatically store information for future sessions. When you teach it conventions:

```
> Our Terraform modules always use snake_case and include lifecycle blocks
```

It remembers for next time — no need to repeat yourself.

### Where memories are stored

| Scope | Path | When it loads |
|---|---|---|
| **Project** (higher priority) | `.opscode/memory/` | When running inside that project |
| **User** (fallback) | `~/.opscode/memory/` | Every session |

When both contain a memory with the same key, the project version wins.

### Memory limits

- Maximum **200 lines** injected per session
- Maximum **25 KB** total memory per session

These limits prevent memory from crowding out your actual conversation.

### Managing memory

Use `/memory` inside an interactive session:

```
/memory                    # List all loaded memories
/memory save <key>         # Save a memory entry
/memory delete <key>       # Delete a memory entry
```

Or just tell the agent naturally:

```
Remember that we use AWS KMS customer-managed keys for all S3 buckets
```

### AGENTS.md files

`AGENTS.md` files provide persistent instructions that are always loaded at session start:

| Path | Scope |
|---|---|
| `.opscode/AGENTS.md` | Project-level (committed to Git, shared with team) |
| `AGENTS.md` | Repository root (alternative location) |
| `~/.opscode/{agent}/AGENTS.md` | User-level (personal preferences) |

Both project and user files are loaded, with project taking priority when there's overlap.

## Skills

Skills are modular instruction sets that extend OpsCode with deep domain knowledge. Each skill is a directory with a `SKILL.md` file.

### Two kinds of skills

- **Global skills:** Discovered from your user or project directories and loaded into the main agent. These include the 4 built-in skills (`cloud-core`, `docker`, `kubernetes`, `remember`).
- **Subagent skills:** Bundled inside specific subagent packages (Terraform, Helm, Ansible, etc.). These only load when that subagent is active — they don't use tokens during general conversation.

### Skill directory structure

```
skill-name/
├── SKILL.md          # Required — instructions with YAML frontmatter
├── scripts/          # Optional — helper scripts
├── references/       # Optional — domain documentation
└── assets/           # Optional — templates and examples
```

### SKILL.md format

```markdown
---
name: kubernetes
description: "Author, audit, and troubleshoot Kubernetes manifests following Pod Security Standards"
---

# Kubernetes Engineering Skill

When authoring or debugging manifests:

1. Always define explicit CPU and memory requests and limits.
2. Configure readinessProbe and livenessProbe on all long-running workloads.
3. Enforce non-root securityContext (runAsNonRoot: true).
4. Include standard labels: app.kubernetes.io/name, instance, version.
```

### Skill resolution order

Skills are loaded from multiple locations. When two skills have the same name, the higher-priority source wins:

| Priority | Source | Path |
|---|---|---|
| Highest | Project agents skills | `.agents/skills/` |
| ↑ | Project OpsCode skills | `.opscode/skills/` |
| ↑ | User agents skills | `~/.agents/skills/` |
| ↑ | User OpsCode skills | `~/.opscode/skills/` |
| ↑ | Plugin skills | Installed marketplace plugins |
| Lowest | Built-in skills | Ships with OpsCode |

### Use skills

**Automatic activation:** Skills activate automatically based on their description when the agent detects a matching task.

**Manual invocation:**

```
/skills                    # Browse loaded skills
/skill kubernetes          # Invoke a specific skill
```

**At launch:**

```bash
ops -s kubernetes          # Pre-load a skill on startup
```

### Create custom skills

Scaffold a new skill:

```bash
ops skills create my-custom-skill
```

Or write `SKILL.md` directly into `.opscode/skills/my-custom-skill/`:

```markdown
---
name: my-custom-skill
description: "Internal release engineering workflow for staging and production"
---

# Release Engineering

1. Run pre-flight linting and integration test suites.
2. Verify image digest signatures using Cosign.
3. Update Helm values in the GitOps repository.
4. Trigger ArgoCD sync and monitor rollout health.
```

### Create skills from conversation

The `remember` skill can distill your current conversation into a reusable skill:

- Run `/skill-create` inside a session.
- OpsCode analyzes the conversation, extracts best practices and commands, and writes a complete `SKILL.md` file for future reuse.

### Skill trust

To prevent unauthorized skills from running, OpsCode records trust decisions for new project skills. You'll be asked to approve a skill the first time it's discovered from a repository you haven't used before.
