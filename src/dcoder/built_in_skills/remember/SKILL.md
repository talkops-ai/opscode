---
name: remember
description: "Save learnings, conventions, and project-specific knowledge to AGENTS.md memory files"
domain: general
allowed_tools:
  - write_file
  - read_file
metadata:
  domain: general
  difficulty: beginner
---

# Remember Skill

You are a helpful assistant that saves project conventions, learnings, and preferences to memory files.

## How Memory Works

DCoder uses `AGENTS.md` files to persist knowledge across sessions. These files are automatically injected into the system prompt on every session start.

## Memory File Locations

| Location | Scope | When to Use |
|----------|-------|-------------|
| `~/.dcoder/AGENTS.md` | Global (all projects) | User preferences, coding style, tool preferences |
| `{project}/.agents/AGENTS.md` | Project-specific | Project conventions, architecture decisions, team rules |
| `{project}/.dcoder/AGENTS.md` | Project + DCoder specific | DevOps conventions, deployment procedures |

## When to Save

Save to memory when:
- The user explicitly asks to remember something.
- A project convention or pattern is established that should persist.
- A debugging insight is discovered that would help future sessions.
- The user corrects a mistake — remember the correction for next time.

## Format

Append to the appropriate `AGENTS.md` file using clear, concise entries:

```markdown
## Project Conventions

- Use Terraform workspaces for environment isolation (not directory-based).
- All Helm charts must pass `helm lint` before merge.
- Kubernetes namespaces follow `{team}-{env}` naming (e.g., `platform-prod`).

## Deployment Notes

- Production deploys require ArgoCD sync with manual approval.
- Staging auto-syncs from `main` branch via ArgoCD ApplicationSet.
```

## Rules

- **Never overwrite** existing AGENTS.md content — always **append**.
- Keep entries concise and actionable.
- Use markdown headers to group related entries.
- Ask the user which scope (global vs project) if unclear.
- Confirm what was saved after writing.
