Scaffold a new service from the standard template and deploy it with tracking.

**Usage:** `/new-service [category/name]`

If `$ARGUMENTS` is provided (e.g., `services/nextcloud` or `apps/portfolio`), use it. Otherwise ask.

## Steps:

### 1. Gather information
Ask the user:
- Service name (e.g., `nextcloud`, `gitea`, `portfolio`)
- Category: `services` (private) or `apps` (public-facing) or `core`
- Docker image + tag
- Port the container listens on internally
- Should it be HTTP-exposed via Traefik? (y/n)
- Should it be admin-only (IP-restricted to your IPv6)? (y/n — default yes for safety)
- Memory limit (e.g., `512M`, `1G`)
- Required environment variables?

### 2. Generate files

**`infrastructure/{category}/{name}/docker-compose.yml`** using the template from CLAUDE.md.
Key requirements:
- `internal` network always
- `proxy` network if HTTP-exposed
- `admin-ip@file` middleware if admin-only (this is the default — only remove for truly public services)
- `secure-headers@file` and `rate-limit@file` on all routes
- `no-new-privileges:true` in `security_opt`
- Resource limits (`memory`, `cpus`)
- `restart: unless-stopped`

**`infrastructure/{category}/{name}/.env.example`** listing every variable with inline comment.

### 3. Show generated files for review

Show both files to the user before writing. Ask for confirmation.

### 4. Write files locally and commit

```bash
git add infrastructure/{category}/{name}/
git commit -m "feat({category}): add {name}"
git push origin main
```

### 5. Set up on server

```bash
# On server — create .env from example
ssh -i ~/.ssh/server_key deploy@82.223.64.68 \
  "cp /opt/server/infrastructure/{category}/{name}/.env.example \
      /opt/server/infrastructure/{category}/{name}/.env"
```

Then tell the user: **edit `.env` on the server** with real values before deploying:
```bash
ssh -i ~/.ssh/server_key deploy@82.223.64.68 \
  "nano /opt/server/infrastructure/{category}/{name}/.env"
```

### 6. Deploy with tracking

```bash
ssh -i ~/.ssh/server_key deploy@82.223.64.68 \
  "cd /opt/server && bash scripts/deploy-service.sh infrastructure/{category}/{name}"
```

### 7. Verify

- Container is Up: `docker ps --filter name={name}`
- Logs clean: `docker logs {name} --tail=20`
- URL responds: `curl -sI https://{subdomain}.pserenlo.com`
- Deploy History in Grafana shows the new entry

### 8. DNS reminder

If needed, remind the user to add a DNS A record in Cloudflare:
- Type: A
- Name: `{subdomain}`
- Content: `82.223.64.68`
- Proxy: orange (proxied)
