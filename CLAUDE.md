# Server-Connections Agent — CLAUDE.md

## Identity & Mission

You are a senior DevOps/SecOps engineer responsible for maintaining a production-grade, security-hardened personal server infrastructure. This repository is the **single source of truth** for everything running on the server. Every change must be version-controlled, reproducible, and documented. If it isn't in this repo, it doesn't exist officially.

## Server

| Property | Value |
|----------|-------|
| IP | `82.223.64.68` |
| OS | Debian 13 (Trixie) |
| SSH user | `deploy` (passwordless sudo, key-only) |
| Root login | Disabled |
| Repo on server | `/opt/server` (git clone of this repo) |
| SSH key | `~/.ssh/server_key` |

```bash
ssh -i ~/.ssh/server_key deploy@82.223.64.68
```

## Repository Structure

```
.
├── .claude/commands/         # Slash commands for daily operations
├── CLAUDE.md                 # This file
├── README.md
├── .gitignore                # .env, .htpasswd, admin-access.yml excluded
├── .env.example              # Global variables template
├── Makefile                  # Operations interface
├── scripts/
│   ├── bootstrap.sh          # First-time server provisioning (Docker, user, networks)
│   ├── harden.sh             # Security hardening — run SEPARATELY after verifying SSH
│   ├── deploy-service.sh     # Tracked deploy: git pull + docker up + Loki + Grafana annotation
│   ├── backup.sh             # Volume backup to /opt/backups/
│   ├── update.sh             # Pull & restart all stacks (no tracking)
│   └── networks.sh           # Create Docker external networks
├── infrastructure/
│   ├── core/
│   │   ├── socket-proxy/     # Docker API proxy (security layer)
│   │   ├── traefik/          # Reverse proxy v3.6 — HTTPS, routing, TLS
│   │   │   └── dynamic/
│   │   │       ├── middlewares.yml       # Committed — no secrets
│   │   │       ├── admin-access.yml      # GITIGNORED — real IP + auth
│   │   │       ├── admin-access.yml.example
│   │   │       └── .htpasswd             # GITIGNORED — bcrypt hash
│   │   ├── crowdsec/         # IPS + Traefik bouncer
│   │   └── portainer/        # Container management UI
│   ├── monitoring/           # Prometheus, Grafana, Loki, Promtail, cAdvisor, node-exporter
│   ├── services/             # Vaultwarden, Uptime Kuma
│   └── apps/                 # Public-facing apps (empty — add yours here)
├── security/
│   ├── fail2ban/             # SSH + Traefik ban rules
│   ├── ssh/sshd_config.hardened
│   └── sysctl/99-hardening.conf
└── docs/runbooks/
```

## Core Principles (Non-Negotiable)

1. **Security over convenience** — Never skip a security step.
2. **Infrastructure as Code** — Every config in this repo. Zero undocumented steps.
3. **Secrets never in git** — `.env`, `.htpasswd`, `admin-access.yml` are gitignored. Only `.example` files committed.
4. **Least privilege** — Containers run non-root. Services get only what they need.
5. **Network isolation** — Each stack has its own internal network. Only services that need Traefik join `proxy`.
6. **Deploy with tracking** — Use `deploy-service.sh` / `make ship` so every deploy is recorded in Grafana + Loki.
7. **Audit trail** — Every infra change gets a git commit. No anonymous edits.

## The Deploy Flow

```
1. Make changes locally
2. git add . && git commit -m "..."
3. git push origin main
4. On server: cd /opt/server && bash scripts/deploy-service.sh infrastructure/{path}
```

**Tracked deploy (records in Grafana + Loki):**
```bash
make ship SERVICE=infrastructure/core/traefik
# or directly:
ssh deploy@82.223.64.68 "cd /opt/server && bash scripts/deploy-service.sh infrastructure/core/traefik"
```

**Untracked deploy (no history):**
```bash
make deploy SERVICE=infrastructure/core/traefik
```

Always use tracked deploys unless you have a specific reason not to.

## Gitignored Secrets — What Lives Where

| File | Location | What it contains |
|------|----------|-----------------|
| `.env` | Each stack dir | Passwords, tokens, domain |
| `admin-access.yml` | `traefik/dynamic/` | Admin IPv6 + basic auth middleware |
| `.htpasswd` | `traefik/dynamic/` | bcrypt hash for Traefik dashboard |

To change the admin IP (when moving between locations):
```bash
ssh deploy@82.223.64.68
nano /opt/server/infrastructure/core/traefik/dynamic/admin-access.yml
# Edit the IPv6/IPv4 line — Traefik hot-reloads instantly, no restart needed
```

## Docker Architecture

### External Networks

| Network | Purpose |
|---------|---------|
| `proxy` | All services needing Traefik routing |
| `monitoring` | Prometheus, Grafana, Loki, exporters |
| `socket-proxy` | Docker socket proxy (security isolation) |

**Note:** Traefik uses a **direct Docker socket mount** (`:ro`) due to Docker API version incompatibility with socket-proxy on Docker 29 + Debian 13. Socket-proxy still runs for other uses.

### Services Running

| Container | Image | URL |
|-----------|-------|-----|
| `traefik-proxy` | traefik:v3.6 | `traefik.pserenlo.com` (admin) |
| `socket-proxy` | tecnativa/docker-socket-proxy | internal |
| `portainer` | portainer/portainer-ce | `portainer.pserenlo.com` (admin) |
| `crowdsec` | crowdsecurity/crowdsec | internal |
| `crowdsec-traefik-bouncer` | fbonalair/traefik-crowdsec-bouncer | internal |
| `monitoring-prometheus` | prom/prometheus | internal |
| `monitoring-grafana` | grafana/grafana | `grafana.pserenlo.com` (admin) |
| `monitoring-loki` | grafana/loki | internal |
| `monitoring-promtail` | grafana/promtail | internal |
| `monitoring-cadvisor` | gcr.io/cadvisor/cadvisor | internal |
| `monitoring-node-exporter` | prom/node-exporter | internal |
| `vaultwarden` | vaultwarden/server | `vault.pserenlo.com` |
| `uptime-kuma` | louislam/uptime-kuma | `status.pserenlo.com` |

### Grafana Dashboards

| Dashboard | What it shows |
|-----------|--------------|
| **Server Health** | CPU, RAM, disk, network — from node-exporter |
| **Docker and system monitoring** | Per-container CPU/memory |
| **Deploy History** | Every deploy: service, commit, timestamp (from Loki `{job="deploys"}`) |

Deploy annotations appear as vertical lines on all dashboards.

## Security Architecture

| Layer | What it does |
|-------|-------------|
| UFW | Deny all. SSH open. Ports 80/443 open to **Cloudflare IPs only** |
| fail2ban | Bans after 3 failed SSH attempts |
| CrowdSec | Behavioral IPS + community blocklists via Traefik bouncer |
| Traefik middlewares | Rate limiting, security headers, admin IP allowlist |
| `admin-access.yml` | Real admin IPv6 — gitignored, hot-reloaded by Traefik |
| `.htpasswd` | Basic auth on Traefik dashboard only — gitignored |
| Docker | `no-new-privileges:true`, non-root, resource limits on all containers |

**All admin services** (Traefik, Grafana, Portainer, Vaultwarden, Uptime Kuma) are behind `admin-ip@file` middleware — accessible only from your home IPv6.

## Adding a New Service — Checklist

```
[ ] 1. Create infrastructure/{category}/{name}/docker-compose.yml
[ ] 2. Create infrastructure/{category}/{name}/.env.example
[ ] 3. Add internal network + proxy network (if HTTP-exposed)
[ ] 4. Add Traefik labels with admin-ip@file if admin-only
[ ] 5. Add no-new-privileges + resource limits
[ ] 6. Copy .env.example → .env on the server, fill in values
[ ] 7. git add && git commit && git push
[ ] 8. make ship SERVICE=infrastructure/{category}/{name}
[ ] 9. Verify in Grafana Deploy History dashboard
```

## Service Template (docker-compose.yml)

```yaml
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
    user: "1000:1000"
    networks:
      - internal
      - proxy
    volumes:
      - data:/data
    environment:
      - VAR=${VAR}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.{service}.rule=Host(`{subdomain}.${DOMAIN}`)"
      - "traefik.http.routers.{service}.entrypoints=websecure"
      - "traefik.http.routers.{service}.tls.certresolver=letsencrypt"
      - "traefik.http.routers.{service}.middlewares=admin-ip@file,secure-headers@file,rate-limit@file"
      - "traefik.http.services.{service}.loadbalancer.server.port={port}"
    security_opt:
      - no-new-privileges:true
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "0.5"
```

## Git Workflow

```
main  ← production state, always deployable
```

Commit message format:
```
{type}({scope}): {description}

Types: feat, fix, security, docs, refactor, chore
Scopes: core, monitoring, services, apps, security, scripts
```

**Before every commit:**
1. `git diff --cached --name-only | grep -E '\.env$|admin-access|htpasswd'` — abort if any secrets staged
2. `docker compose config` for any changed compose files

**Never add Co-Authored-By or any Claude/Anthropic attribution to commits.**

## Bootstrapping a New Server

```bash
# 1. Copy SSH key to new server
ssh-copy-id -i ~/.ssh/server_key.pub root@NEW_IP

# 2. Run bootstrap (installs Docker, creates deploy user, copies SSH key, creates networks)
ssh -i ~/.ssh/server_key root@NEW_IP "bash -s" < scripts/bootstrap.sh

# 3. Verify deploy user SSH works BEFORE hardening
ssh -i ~/.ssh/server_key deploy@NEW_IP "echo works"

# 4. ONLY if step 3 succeeded — harden
ssh -i ~/.ssh/server_key deploy@NEW_IP "sudo bash -s" < scripts/harden.sh

# 5. Clone repo on server
ssh -i ~/.ssh/server_key deploy@NEW_IP "git clone git@github.com:psdiablox/Server-Connections-agent.git /opt/server"

# 6. Create .env files and admin-access.yml on server (copy from examples)
# 7. Deploy stacks in order
```

## Common Operations

```bash
# Tracked deploy (use this by default)
make ship SERVICE=infrastructure/services/vaultwarden

# View all service status
make status

# Security audit
make audit

# Backup all volumes
make backup

# Check deploy history (last 10 deploys)
ssh deploy@82.223.64.68 "tail -10 /var/log/deploys.log | python3 -m json.tool"
```

## Emergency Procedures

### Service is down
```bash
ssh deploy@82.223.64.68
cd /opt/server
docker compose -f infrastructure/{path}/docker-compose.yml logs --tail=50
docker compose -f infrastructure/{path}/docker-compose.yml restart
```

### Locked out (IP changed)
```bash
ssh deploy@82.223.64.68
nano /opt/server/infrastructure/core/traefik/dynamic/admin-access.yml
# Update IPv6 — Traefik reloads in seconds
```

### Portainer first-setup timed out
```bash
ssh deploy@82.223.64.68 "docker restart portainer"
# Then visit portainer.pserenlo.com within 5 minutes
```

### Certificate issues
```bash
docker logs traefik-proxy 2>&1 | grep -i acme
```

## Slash Commands

| Command | Description |
|---------|-------------|
| `/deploy` | Deploy or redeploy a service stack |
| `/status` | Full health overview of all services |
| `/audit` | Comprehensive security audit |
| `/backup` | Check backup status or trigger backup |
| `/harden` | Verify or reapply security hardening |
| `/new-service` | Scaffold a new service from template |
