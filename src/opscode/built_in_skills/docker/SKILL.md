---
name: docker
description: "Write optimised Dockerfiles with multi-stage builds, security hardening, and Compose orchestration. Use when authoring, reviewing, or optimizing container artifacts for: (1) Multi-stage Dockerfiles for Go, Node.js, Python, or Rust, (2) Container security hardening including non-root USER, minimal base images, and secret mounts, (3) Docker Compose orchestration definitions, healthchecks, and networking, or (4) Docker build performance and layer caching optimization."
license: MIT
compatibility: designed for opscode
---

# Docker (Multi-Stage Builds, Security Hardening & Compose)

Guidelines for building lightweight, secure, and production-ready Docker containers and multi-service Docker Compose stacks.

## Quick Workflow

1. **Multi-Stage Build Pipeline**: Separate build dependencies from runtime dependencies using multi-stage builds (`AS builder`, `AS runner`).
2. **Layer Caching Optimization**: Copy lockfiles/manifests first, run dependency downloads with BuildKit cache mounts (`--mount=type=cache`), then copy application source.
3. **Security Hardening**: Enforce non-root execution (`USER nonroot` or dedicated UID/GID), select minimal base images (Distroless or Alpine), and drop Linux capabilities.
4. **Secrets Protection**: Use BuildKit secret mounts (`--mount=type=secret`) during build and Docker Compose secrets for runtime. Never hardcode credentials in `ENV` or `ARG`.
5. **Orchestration with Compose v2**: Define multi-container services with healthchecks (`condition: service_healthy`), internal networks, and resource limits.

---

## Detailed References

- **Multi-Stage Dockerfile Templates**: See [references/dockerfile-patterns.md](references/dockerfile-patterns.md) for production multi-stage Dockerfiles for Node.js, Python, Go, and Rust.
- **Security Hardening**: See [references/security-hardening.md](references/security-hardening.md) for non-root setup, distroless images, read-only root filesystems, and capability drops.
- **Docker Compose Orchestration**: See [references/compose-orchestration.md](references/compose-orchestration.md) for Docker Compose v2 patterns, network segmentation, healthcheck dependencies, and secret mounting.

---

## Production Container Checklist

- [ ] **Multi-Stage Separation**: Build toolchains (compilers, dev dependencies) excluded from final runtime image.
- [ ] **Non-Root User**: Container runs as explicit non-root user (`USER appuser` or `USER nonroot`).
- [ ] **Minimal Base Image**: Base image uses Alpine, Distroless, or minimal slim distributions.
- [ ] **Build Caching**: Dependencies installed before copying application source; BuildKit cache mounts applied.
- [ ] **Secret Hygiene**: No credentials stored in `ENV`, `ARG`, or image layers.
- [ ] **Compose Healthchecks**: Services use `depends_on` with `condition: service_healthy` for startup dependencies.
