# Multi-Stage Dockerfile Patterns

## 1. Node.js (TypeScript) Multi-Stage Build

```dockerfile
# Syntax directive for BuildKit cache mounts
# syntax=docker/dockerfile:1

# Stage 1: Dependencies
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --only=production && cp -R node_modules prod_node_modules
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Stage 2: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# Stage 3: Runner
FROM gcr.io/distroless/nodejs20-debian12:nonroot AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=deps /app/prod_node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY package.json ./

USER nonroot
EXPOSE 3000
CMD ["dist/main.js"]
```

---

## 2. Python (uv / FastApi) Multi-Stage Build

```dockerfile
# syntax=docker/dockerfile:1

# Stage 1: Build virtual environment
FROM python:3.12-slim AS builder
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Stage 2: Minimal Runtime
FROM python:3.12-slim AS runner
WORKDIR /app

# Create non-root user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/false appuser

COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --chown=appuser:appgroup src/ ./src

ENV PATH="/app/.venv/bin:$PATH"
USER appuser
EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 3. Go Compiled Binary (Distroless Final)

```dockerfile
# syntax=docker/dockerfile:1

# Stage 1: Build Go Binary
FROM golang:1.22-alpine AS builder
WORKDIR /src

RUN apk add --no-cache git ca-certificates

COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /bin/server ./cmd/server

# Stage 2: Scratch or Distroless
FROM gcr.io/distroless/static-debian12:nonroot AS runner
COPY --from=builder /bin/server /server

USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/server"]
```

---

## 4. Layer Ordering & Optimization Best Practices

- **Copy order matter**: Copy dependency definition files (`package.json`, `go.mod`, `pyproject.toml`) first, install dependencies, and only then copy application source code.
- **Use `.dockerignore`**: Always include a `.dockerignore` file containing `.git`, `node_modules`, `.env`, `dist`, `build`, and local test logs.
- **Use BuildKit Cache Mounts**: Use `RUN --mount=type=cache,target=...` to preserve package manager caches across builds without expanding image size.
