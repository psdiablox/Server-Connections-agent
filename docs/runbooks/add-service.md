# Runbook: Adding a New Service

## 1. Determine the service category

| Category | Path | Exposed publicly? |
|----------|------|------------------|
| Core infrastructure | `infrastructure/core/{name}/` | Admin only |
| Private service | `infrastructure/services/{name}/` | Optional |
| Public app | `infrastructure/apps/{name}/` | Yes |

## 2. Create the directory and files

```bash
mkdir -p infrastructure/{category}/{service-name}
```

Create `docker-compose.yml` using the template from CLAUDE.md.
Create `.env.example` listing all required environment variables with descriptions.

## 3. Configure Traefik routing (if HTTP-exposed)

Add these labels to the service container:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.{name}.rule=Host(`{subdomain}.${DOMAIN}`)"
  - "traefik.http.routers.{name}.entrypoints=websecure"
  - "traefik.http.routers.{name}.tls.certresolver=letsencrypt"
  - "traefik.http.routers.{name}.middlewares=secure-headers@file,rate-limit@file"
  - "traefik.http.services.{name}.loadbalancer.server.port={port}"
```

For admin-only: add `admin-ip@file` to middlewares.

## 4. Add to the correct networks

```yaml
networks:
  internal:          # Always — for service isolation
    driver: bridge
    internal: true
  proxy:             # Only if HTTP-exposed via Traefik
    external: true
```

## 5. Set security options

Every service must include:

```yaml
security_opt:
  - no-new-privileges:true
deploy:
  resources:
    limits:
      memory: XXXm
      cpus: "0.X"
```

## 6. Deploy and verify

```bash
# Copy .env.example → .env and fill in values
cp infrastructure/{category}/{service}/.env.example infrastructure/{category}/{service}/.env
vim infrastructure/{category}/{service}/.env

# Validate compose file
docker compose -f infrastructure/{category}/{service}/docker-compose.yml config

# Deploy
make deploy SERVICE=infrastructure/{category}/{service}

# Verify
docker compose -f infrastructure/{category}/{service}/docker-compose.yml ps
docker compose -f infrastructure/{category}/{service}/docker-compose.yml logs --tail=30
curl -I https://{subdomain}.yourdomain.com
```

## 7. Commit

```bash
git add infrastructure/{category}/{service}/docker-compose.yml
git add infrastructure/{category}/{service}/.env.example
git commit -m "feat({category}): add {service-name}"
```

Never add `.env` to git. Verify with `git diff --cached --name-only | grep -i env`.
