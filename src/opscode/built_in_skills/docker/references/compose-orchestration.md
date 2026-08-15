# Docker Compose Orchestration (v2 Specification)

## 1. Production-Ready Docker Compose Pattern

```yaml
name: my-app-stack

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: runner
    ports:
      - "8080:8080"
    environment:
      - NODE_ENV=production
      - DB_HOST=db
      - DB_PORT=5432
    secrets:
      - db_password
    networks:
      - frontend-net
      - backend-net
    depends_on:
      db:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "1.5"
          memory: 512M
        reservations:
          cpus: "0.25"
          memory: 128M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 15s

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: appdb
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - backend-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U appuser -d appdb"]
      interval: 5s
      timeout: 3s
      retries: 5

networks:
  frontend-net:
    driver: bridge
  backend-net:
    driver: bridge
    internal: true # No external internet access for DB network

volumes:
  pgdata:
    driver: local

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

---

## 2. Key Docker Compose Features

### Healthchecks & Service Dependencies
Use `depends_on` with `condition: service_healthy` so dependant services do not launch until database/upstream services report ready.

### Network Segmentation
Isolate internal components (databases, cache layers) on networks with `internal: true` so they cannot route to or from the public internet directly.

### Secrets Management
Use `secrets:` to mount file-based secrets into `/run/secrets/<secret_name>` instead of passing raw passwords in environment variables.
