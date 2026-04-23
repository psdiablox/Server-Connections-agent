# Server Infrastructure

Production-grade, security-hardened personal server infrastructure defined as code.

## Quick Start

```bash
# 1. Provision a fresh Debian server (as root)
bash scripts/bootstrap.sh

# 2. Copy and fill .env files for each stack you want to deploy
cp infrastructure/core/traefik/.env.example infrastructure/core/traefik/.env
# edit .env...

# 3. Create Docker networks
make networks

# 4. Deploy core stack (required first)
make deploy SERVICE=infrastructure/core/socket-proxy
make deploy SERVICE=infrastructure/core/traefik

# 5. Deploy other stacks
make deploy SERVICE=infrastructure/monitoring
make deploy SERVICE=infrastructure/services/vaultwarden
```

## Stack Layout

| Stack | Path | URL |
|-------|------|-----|
| Reverse Proxy | `infrastructure/core/traefik` | `traefik.yourdomain.com` (admin) |
| Container UI | `infrastructure/core/portainer` | `portainer.yourdomain.com` (admin) |
| IPS | `infrastructure/core/crowdsec` | internal |
| Metrics | `infrastructure/monitoring` | `grafana.yourdomain.com` (admin) |
| Password Manager | `infrastructure/services/vaultwarden` | `vault.yourdomain.com` |
| Uptime Monitor | `infrastructure/services/uptime-kuma` | `status.yourdomain.com` |

## Common Operations

```bash
make status                                    # Health of all services
make logs SERVICE=infrastructure/core/traefik  # Tail logs
make update                                    # Pull & restart all stacks
make backup                                    # Backup all volumes
make audit                                     # Security audit
```

## Claude Code Slash Commands

| Command | Description |
|---------|-------------|
| `/deploy` | Deploy or redeploy a stack |
| `/status` | Service health overview |
| `/audit` | Security audit |
| `/backup` | Backup status or trigger |
| `/harden` | Verify/apply hardening |
| `/new-service` | Scaffold a new service |

## Security

- All traffic enters via Traefik (HTTPS only, TLS 1.2+)
- Docker API access via socket proxy (read-only, scoped)
- Fail2ban + CrowdSec for intrusion prevention
- SSH: key-only, no root login
- UFW: deny all, allow 22/80/443 only
- Containers: non-root, no-new-privileges, resource-limited

Secrets are never committed. See `.env.example` files for required variables.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full stack diagram and security layers.
