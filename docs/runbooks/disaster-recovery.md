# Runbook: Disaster Recovery

## Scenario: Complete Server Loss

### 1. Provision new server

```bash
# On new Debian server (as root):
apt-get update && apt-get install -y git

# Clone the repo
git clone https://github.com/YOUR_USER/server-connections.git /opt/server
cd /opt/server

# Bootstrap
bash scripts/bootstrap.sh
```

### 2. Restore secrets

`.env` files are NOT in the repository (gitignored). You need them from:
- A secure backup (encrypted external drive, password manager notes, etc.)
- Manually recreate from `.env.example` files

```bash
# For each stack, copy .env.example and fill in values
for dir in infrastructure/{core,monitoring,services,apps}/*/; do
  if [ -f "$dir/.env.example" ] && [ ! -f "$dir/.env" ]; then
    echo "Missing .env for: $dir"
  fi
done
```

### 3. Restore volume data

```bash
BACKUP_DATE="2024-01-15_120000"  # Use your backup date
BACKUP_DIR="/opt/backups/${BACKUP_DATE}"

# Restore a specific volume
docker volume create vaultwarden_data
docker run --rm \
  -v vaultwarden_data:/data \
  -v "${BACKUP_DIR}:/backup:ro" \
  alpine \
  tar -xzf /backup/vaultwarden_data.tar.gz -C /data
```

### 4. Deploy services in order

```bash
make networks

make deploy SERVICE=infrastructure/core/socket-proxy
make deploy SERVICE=infrastructure/core/traefik
make deploy SERVICE=infrastructure/core/crowdsec
make deploy SERVICE=infrastructure/core/portainer
make deploy SERVICE=infrastructure/monitoring
make deploy SERVICE=infrastructure/services/vaultwarden
make deploy SERVICE=infrastructure/services/uptime-kuma
```

### 5. Verify

```bash
make status
curl -I https://traefik.yourdomain.com
curl -I https://grafana.yourdomain.com
```

---

## Scenario: Service Failure

```bash
# Check logs
make logs SERVICE=infrastructure/{path}

# Restart
make restart SERVICE=infrastructure/{path}

# Nuclear option — rebuild from scratch
make down SERVICE=infrastructure/{path}
make deploy SERVICE=infrastructure/{path}
```

---

## Scenario: Certificate Issues

```bash
# Check Traefik logs for ACME errors
docker logs traefik-proxy --tail=100 | grep -i acme

# Force certificate renewal
docker exec traefik-proxy traefik healthcheck

# If acme.json is corrupted:
docker exec traefik-proxy sh -c "cat /letsencrypt/acme.json | jq ."
# If empty/invalid, remove and restart (certs will be re-requested)
```
