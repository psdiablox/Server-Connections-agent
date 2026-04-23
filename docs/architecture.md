# Architecture

## Stack Overview

```
Internet
    │
    ▼
 Cloudflare (optional CDN/proxy)
    │
    ▼
 UFW (80, 443, SSH only)
    │
    ▼
 CrowdSec (IPS — bans malicious IPs)
    │
    ▼
 Traefik v3 (reverse proxy, TLS termination, routing)
    │  reads Docker labels via socket-proxy
    ▼
 ┌─────────────────────────────────┐
 │  Docker Networks                │
 │                                 │
 │  proxy (external)               │
 │  ├── traefik-proxy              │
 │  ├── monitoring-grafana         │
 │  ├── portainer                  │
 │  ├── vaultwarden                │
 │  └── uptime-kuma                │
 │                                 │
 │  monitoring (external)          │
 │  ├── prometheus                 │
 │  ├── grafana                    │
 │  ├── loki                       │
 │  └── promtail                   │
 │                                 │
 │  socket-proxy (internal)        │
 │  ├── socket-proxy               │
 │  └── traefik-proxy              │
 └─────────────────────────────────┘
```

## Deployment Order

Services must be deployed in this order (dependencies first):

1. `infrastructure/core/socket-proxy` — Docker API proxy
2. `infrastructure/core/traefik` — Reverse proxy (depends on socket-proxy)
3. `infrastructure/core/crowdsec` — IPS (integrates with Traefik)
4. `infrastructure/core/portainer` — Container UI (depends on proxy network)
5. `infrastructure/monitoring` — Observability (depends on monitoring network)
6. `infrastructure/services/*` — Any order, each uses proxy network
7. `infrastructure/apps/*` — Any order, each uses proxy network

## Security Layers

| Layer | Technology | Purpose |
|-------|-----------|---------|
| 1 | UFW | Port-level firewall. Only 22/80/443 |
| 2 | fail2ban | Rate-based SSH and web banning |
| 3 | CrowdSec | Behavioral IPS with community blocklists |
| 4 | Traefik middlewares | Rate limiting, security headers, IP allowlists |
| 5 | Docker socket proxy | Limit Traefik's Docker API access |
| 6 | Container security | no-new-privileges, non-root, resource limits |
| 7 | Network isolation | Each stack in isolated internal network |

## Certificate Management

Certificates are managed by Traefik via Let's Encrypt ACME.

- **HTTP-01 challenge** (default): Works with any registrar. Requires port 80 accessible.
- **DNS-01 challenge** (for wildcards): Requires Cloudflare API token. Supports `*.domain.com`.

Certs are stored in `traefik_certs` Docker volume at `/letsencrypt/acme.json` (mode 600).

## Data Persistence

All persistent data lives in named Docker volumes. Never use bind-mounts for service data — they couple the service to a specific host path and complicate backups.

Backup strategy: `scripts/backup.sh` dumps all named volumes to `/opt/backups/{date}/`.
