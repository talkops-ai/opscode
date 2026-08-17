# Container Security Hardening

## 1. Non-Root Execution

Never run container processes as `root` (UID 0).

- **Alpine**: `RUN addgroup -S appgroup && adduser -S appuser -G appgroup` -> `USER appuser`
- **Debian / Ubuntu**: `RUN groupadd -r appgroup && useradd -r -g appgroup appuser` -> `USER appuser`
- **Distroless**: Use `gcr.io/distroless/...:nonroot` which defaults to UID/GID 65532.

---

## 2. Minimal Base Images

Reduce attack surface and vulnerability scanner flags (CVEs) by selecting small, minimal base images:

| Base Image Type | Example Image | Use Case |
|---|---|---|
| **Distroless** | `gcr.io/distroless/static-debian12:nonroot` | Compiled binaries (Go, Rust) |
| **Distroless Node/Python** | `gcr.io/distroless/nodejs20-debian12` | Runtime environments without shell |
| **Alpine Linux** | `alpine:3.19` | Lightweight POSIX environment |
| **Slim Debian** | `python:3.12-slim` | Python applications requiring GLIBC |

---

## 3. Secret Handling Without Leaks

- **NEVER use `ENV` or `ARG` for secrets**: Values defined via `ENV` or `ARG` are permanently recorded in Docker image layers and inspectable via `docker history`.
- **Use BuildKit Secret Mounts**:
  ```dockerfile
  RUN --mount=type=secret,id=my_api_key \
      API_KEY=$(cat /run/secrets/my_api_key) && ./build_script.sh
  ```
  Invoke build with: `docker build --secret id=my_api_key,src=./api_key.txt .`

---

## 4. Runtime Security Standards

### Read-Only Root Filesystem
Ensure root filesystem cannot be modified at runtime.
```dockerfile
# Require writable paths to be mounted as temporary volumes
VOLUME ["/tmp", "/var/log"]
```
In Docker Compose or Kubernetes:
```yaml
security_opt:
  - no-new-privileges:true
read_only: true
tmpfs:
  - /tmp
  - /run
```

### Capabilities Drop
Drop default Linux kernel capabilities:
```yaml
cap_drop:
  - ALL
cap_add:
  - NET_BIND_SERVICE # Only if binding to ports < 1024
```
