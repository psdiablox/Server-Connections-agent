# Server Infrastructure

This repository contains everything needed to run and manage a personal server at `pserenlo.com`. All services run in Docker containers behind a secure reverse proxy with automatic HTTPS.

---

## What's Running

| Service | Address | What it's for |
|---------|---------|---------------|
| **Vaultwarden** | vault.pserenlo.com | Password manager (self-hosted Bitwarden) |
| **Uptime Kuma** | status.pserenlo.com | Monitors that services are online |
| **Grafana** | grafana.pserenlo.com | Server dashboards — CPU, memory, disk, deploy history |
| **Portainer** | portainer.pserenlo.com | Visual interface to manage Docker containers |
| **Traefik** | traefik.pserenlo.com | The reverse proxy — routes traffic and manages HTTPS certs |

> All services except Vaultwarden are only accessible from your home IP address.

---

## How Deploys Work

Every change to the server goes through this flow:

```
1. Edit files on your computer
       ↓
2. Save to GitHub  (git push)
       ↓
3. Server pulls from GitHub  (git pull)
       ↓
4. Server restarts the affected service
       ↓
5. Deploy is recorded in Grafana with timestamp + commit
```

This means **GitHub is always the source of truth**. The server never has changes that aren't in this repo.

---

## Making a Change and Deploying It

### Step 1 — Save your changes to GitHub

```bash
git add .
git commit -m "describe what you changed"
git push origin main
```

### Step 2 — Deploy on the server

```bash
make ship SERVICE=infrastructure/services/vaultwarden
```

Replace `infrastructure/services/vaultwarden` with the path of whatever you changed. This command:
- Connects to the server
- Downloads your latest changes from GitHub
- Restarts the affected service
- Records the deploy in Grafana (timestamp, what changed, which commit)

### Deploying everything at once

```bash
make ship SERVICE=--all
```

---

## Viewing Deploy History

Open **Grafana** → `grafana.pserenlo.com` → **Deploy History** dashboard.

You'll see a table of every deploy ever made: when it happened, which service, and which code change triggered it. You'll also see vertical lines on the Server Health dashboard showing exactly when each deploy happened relative to CPU and memory usage.

---

## Adding a New Service

Use the built-in assistant:

```bash
/new-service
```

It will ask you a few questions (what is it, which port does it use, should it be private?) and generate all the necessary files automatically.

---

## Common Commands

```bash
make status          # See all running services and their health
make audit           # Security check — firewall, SSH, containers
make backup          # Back up all data to /opt/backups/ on the server
make logs SERVICE=infrastructure/services/vaultwarden   # View service logs
```

---

## SSH Access

```bash
ssh -i ~/.ssh/server_key deploy@82.223.64.68
```

---

## Security Overview

- All traffic goes through Cloudflare before reaching the server
- Ports 80 and 443 only accept connections from Cloudflare — direct server access is blocked at the firewall
- Admin panels are only accessible from your home IP address
- SSH only accepts key-based login — passwords are disabled
- Every container runs with the minimum permissions needed
- Automated security updates are enabled on the server

---

## Repository Layout

```
infrastructure/
├── core/           # The foundation: reverse proxy, security, container management
├── monitoring/     # Dashboards, metrics, logs
├── services/       # Private services (Vaultwarden, Uptime Kuma)
└── apps/           # Public-facing apps — add yours here

scripts/
├── bootstrap.sh    # Sets up a brand new server from scratch
├── harden.sh       # Applies security hardening
├── deploy-service.sh  # The deploy script used by `make ship`
└── backup.sh       # Backs up all data
```

---

## Secrets

Passwords and API keys are **never stored in this repository**. They live only on the server in files that git ignores (`.env`, `admin-access.yml`). The repository only contains templates (`.env.example`) showing which variables are needed.
