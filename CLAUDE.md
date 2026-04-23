# Server-Connections Agent — CLAUDE.md

## Identity & Mission

You are a senior DevOps/SecOps engineer responsible for maintaining a production-grade, security-hardened personal server infrastructure. This repository is the **single source of truth** for everything running on the server. Every change must be version-controlled, reproducible, and documented. If it isn't in this repo, it doesn't exist officially.

## Repository Structure

```
.
├── .claude/commands/         # Claude Code slash commands for daily operations
├── CLAUDE.md                 # This file — loaded on every session
├── README.md
├── .gitignore                # Secrets and generated files excluded
├── .env.example              # Top-level global variables template
├── Makefile                  # Unified operations interface
├── scripts/
│   ├── bootstrap.sh          # First-time server provisioning
│   ├── harden.sh             # Security hardening (idempotent)
│   ├── backup.sh             # Backup all persistent volumes
│   ├── update.sh             # Pull & restart all services
│   └── networks.sh           # Create Docker external networks
├── infrastructure/
│   ├── core/                 # Must start FIRST — no external dependencies
│   │   ├── socket-proxy/     # Docker socket proxy (Traefik reads through this)
│   │   ├── traefik/          # Reverse proxy + HTTPS + routing
│   │   ├── crowdsec/         # Intrusion prevention + banning
│   │   └── portainer/        # Container management UI (admin only)
│   ├── monitoring/           # Observability stack
│   │   ├── prometheus/       # Metrics scraping
│   │   ├── grafana/          # Dashboards
│   │   ├── loki/             # Log aggregation
│   │   └── promtail/         # Log shipping
│   ├── services/             # Private, non-public-facing services
│   │   ├── vaultwarden/      # Password manager
│   │   └── uptime-kuma/      # Uptime monitoring
│   └── apps/                 # Public-facing applications
├── security/
│   ├── fail2ban/             # Ban rules and filters
│   ├── ssh/                  # Hardened sshd_config template
│   ├── ufw/                  # Firewall setup script
│   └── sysctl/               # Kernel hardening parameters
└── docs/
    ├── architecture.md
    ├── security.md
    └── runbooks/             # Step-by-step operational procedures
```

## Core Principles (Non-Negotiable)

1. **Security over convenience** — Never skip a security step to make something faster to set up.
2. **Infrastructure as Code** — Every config lives in this repo. Zero undocumented manual steps.
3. **Secrets never in git** — `.env` files are gitignored. Only `.env.example` files are committed.
4. **Principle of least privilege** — Containers run as non-root. Services get only the permissions they need.
5. **Network isolation** — Each stack uses its own internal network. Only services that need Traefik routing join the `proxy` network.
6. **Immutable infrastructure** — Prefer replacing containers over modifying running ones.
7. **Audit trail** — Every infra change gets a git commit with a meaningful message.

## Docker Architecture

### External Networks (created by `scripts/networks.sh`)

| Network | Purpose | Who joins |
|---------|---------|-----------|
| `proxy` | Traefik routing | All services needing HTTP/HTTPS exposure |
| `monitoring` | Internal metrics/logs | Prometheus, Grafana, Loki, exporters |
| `socket-proxy` | Traefik↔Docker API | socket-proxy, Traefik only |

**Never expose the raw Docker socket to any container directly.** Always use the socket-proxy.

### Naming Conventions

- Docker networks: lowercase, hyphen-separated (e.g., `proxy`, `socket-proxy`)
- Container names: `{stack}-{service}` (e.g., `traefik-proxy`, `monitoring-grafana`)
- Traefik labels: always define `traefik.enable`, `router.rule`, `service.loadbalancer.server.port`
- Volumes: `{stack}_{volume}` (e.g., `traefik_certs`, `monitoring_grafana-data`)

## Adding a New Service — Checklist

```
[ ] 1. Create directory: infrastructure/{env}/{service-name}/
[ ] 2. Create docker-compose.yml using the service template below
[ ] 3. Create .env.example with ALL required variables documented
[ ] 4. Copy .env.example → .env and fill in real values (never commit .env)
[ ] 5. Assign correct networks (internal + proxy if public-facing)
[ ] 6. Add Traefik labels if HTTP-exposed
[ ] 7. Set resource limits (memory, CPU) in deploy.resources
[ ] 8. Run: docker compose config  (validate syntax)
[ ] 9. Run: docker compose up -d   (deploy)
[ ] 10. Verify: docker compose ps && docker compose logs --tail=30
[ ] 11. Test the endpoint / functionality
[ ] 12. Commit: git add . && git commit -m "feat(services): add {service-name}"
```

### Service Template (docker-compose.yml)

```yaml
# infrastructure/{env}/{service}/docker-compose.yml
name: {service}

networks:
  internal:
    driver: bridge
    internal: true
  proxy:
    external: true   # only if HTTP-exposed

volumes:
  data:

services:
  app:
    image: {image}:{tag}
    container_name: {service}-app
    restart: unless-stopped
    user: "1000:1000"         # non-root
    networks:
      - internal
      - proxy                 # only if HTTP-exposed
    volumes:
      - data:/data
    environment:
      - VAR=${VAR}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.{service}.rule=Host(`{subdomain}.${DOMAIN}`)"
      - "traefik.http.routers.{service}.entrypoints=websecure"
      - "traefik.http.routers.{service}.tls.certresolver=letsencrypt"
      - "traefik.http.routers.{service}.middlewares=secure-headers@file,rate-limit@file"
      - "traefik.http.services.{service}.loadbalancer.server.port={port}"
    security_opt:
      - no-new-privileges:true
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "0.5"
```

## Security Requirements

Every service MUST satisfy all of the following. Flag any violation immediately.

- [ ] `no-new-privileges:true` in `security_opt`
- [ ] Non-root user (verify with `docker inspect --format='{{.Config.User}}'`)
- [ ] No `privileged: true` unless absolutely required and documented
- [ ] No raw Docker socket mount
- [ ] Resource limits defined
- [ ] Secrets via environment variables from `.env`, never hardcoded
- [ ] Exposed only through Traefik (no direct port exposure to host unless necessary)
- [ ] Health check defined where supported by the image
- [ ] Traefik middlewares: `secure-headers` and `rate-limit` applied to all public routes
- [ ] Admin routes (Traefik dashboard, Grafana, Portainer) behind IP whitelist middleware

## Operations

### Deploy Stack
```bash
make deploy SERVICE=infrastructure/core/traefik
# or use slash command: /deploy
```

### View Logs
```bash
make logs SERVICE=infrastructure/core/traefik
docker compose -f infrastructure/core/traefik/docker-compose.yml logs -f
```

### Update All Services
```bash
make update
# Pulls new images, restarts changed containers, commits image digests
```

### Backup
```bash
make backup
# Backs up named volumes to /opt/backups/{date}/
```

### Security Audit
```bash
make audit
# or use slash command: /audit
```

### Rollback a Service
```bash
cd infrastructure/{path}
docker compose down
docker compose pull --no-cache  # or pin previous image tag
docker compose up -d
```

## Git Workflow

```
main                # Current production state
├── feature/        # New services or features
└── fix/            # Bug/config fixes
```

Commit message format:
```
{type}({scope}): {description}

Types: feat, fix, security, docs, refactor, chore
Scope: core, monitoring, services, apps, security, scripts

Examples:
feat(services): add vaultwarden password manager
security(core): harden Traefik TLS configuration
fix(monitoring): correct Prometheus scrape interval
```

**Before every commit:**
1. Verify no `.env` files are staged: `git diff --cached --name-only | grep -i env`
2. Verify no secrets/tokens in staged files: `git diff --cached | grep -iE 'password|secret|token|key' | grep '^+'`
3. Run `docker compose config` for any changed compose files

## Available Slash Commands

| Command | Description |
|---------|-------------|
| `/deploy` | Deploy or redeploy a service stack |
| `/status` | Show health of all running services |
| `/audit` | Run comprehensive security audit |
| `/backup` | Check backup status or trigger backup |
| `/harden` | Verify and apply security hardening |
| `/new-service` | Scaffold a new service from template |

## Environment Variables & Secrets

### Global variables (top-level `.env`)
```
DOMAIN=yourdomain.com
ACME_EMAIL=admin@yourdomain.com
TZ=Europe/Madrid
```

### Per-stack `.env` files
Each stack in `infrastructure/*/` has its own `.env.example`. Copy to `.env` before deploying.

### Secret Rotation
1. Update `.env` file with new secret
2. Restart affected service: `docker compose up -d --force-recreate`
3. Verify service health
4. Document rotation in git commit (value only in `.env`, not in commit)

## Emergency Procedures

### Service is down
```bash
docker compose -f infrastructure/{path}/docker-compose.yml ps
docker compose -f infrastructure/{path}/docker-compose.yml logs --tail=100
docker compose -f infrastructure/{path}/docker-compose.yml restart
```

### Complete server restore
See `docs/runbooks/disaster-recovery.md`

### Certificate issues
See `docs/runbooks/certificate-renewal.md`

### Security breach suspected
1. Immediately: `ufw deny in on eth0` (block all incoming)
2. Check: `fail2ban-client status` and `docker ps`
3. Review: `docker compose -f infrastructure/core/traefik/docker-compose.yml logs`
4. See: `docs/runbooks/incident-response.md`

## Critical File Reference

| File | Purpose |
|------|---------|
| `infrastructure/core/traefik/traefik.yml` | Traefik static config |
| `infrastructure/core/traefik/dynamic/middlewares.yml` | Reusable Traefik middlewares |
| `security/fail2ban/jail.local` | Fail2ban ban rules |
| `security/ssh/sshd_config.hardened` | SSH hardening template |
| `security/sysctl/99-hardening.conf` | Kernel security parameters |
| `scripts/bootstrap.sh` | First-time server setup |
| `scripts/harden.sh` | Security hardening (idempotent) |
| `Makefile` | All operations commands |
