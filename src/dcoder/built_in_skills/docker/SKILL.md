---
name: docker
description: "Write optimised Dockerfiles with multi-stage builds, security hardening, and Compose orchestration"
domain: DevOps
compatibility: "docker >= 24, docker-compose >= 2.20"
allowed_tools:
  - write_file
  - read_file
  - execute
metadata:
  domain: docker
  difficulty: intermediate
---

# Docker & Container Skill

You are an expert container engineer. Follow these guidelines for Dockerfiles, images, and Compose configurations.

## Dockerfile Best Practices

### Multi-Stage Builds

```dockerfile
# Build stage
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY src/ src/

# Runtime stage
FROM python:3.12-slim AS runtime
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8080
ENTRYPOINT ["python", "-m", "myapp"]
```

### Layer Caching

- Copy dependency files (`requirements.txt`, `package.json`, `go.mod`) BEFORE source code.
- Use `--mount=type=cache` for package manager caches:
  ```dockerfile
  RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
  ```
- Combine `RUN` commands to reduce layers: `RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*`.

### Security

- Use minimal base images: `*-slim`, `distroless`, or `scratch`.
- Run as non-root: `USER app` (create user with `groupadd`/`useradd`).
- Don't store secrets in images — use build args with `--secret` mount.
- Pin base image digests for reproducibility: `FROM python:3.12-slim@sha256:...`.
- Use `.dockerignore` to exclude `.git`, `.venv`, `node_modules`, `*.pyc`.

### .dockerignore

```
.git
.venv
node_modules
__pycache__
*.pyc
.env
.env.*
*.md
tests/
```

## Docker Compose

```yaml
services:
  app:
    build:
      context: .
      target: runtime
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgresql://db:5432/mydb
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/healthz"]
      interval: 10s
      timeout: 5s
      retries: 3

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: mydb
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5
    secrets:
      - db_password

volumes:
  pgdata:

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

## Validation

1. `docker build --target runtime -t myapp:test .` — build and tag.
2. `docker scan myapp:test` or `trivy image myapp:test` — vulnerability scan.
3. `docker compose config` — validate Compose file.
4. `hadolint Dockerfile` — Dockerfile linting.

## Best Practices Summary

- One process per container.
- Use `ENTRYPOINT` for the main process, `CMD` for default arguments.
- Set `HEALTHCHECK` in Dockerfile or Compose.
- Use named volumes for persistent data — never bind-mount in production.
- Use `depends_on` with `condition: service_healthy` for startup ordering.
- Tag images with Git SHA or SemVer — never use `:latest` in production.
