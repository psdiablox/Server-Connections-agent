Scaffold a new service from the standard template.

**Usage:** `/new-service`

If `$ARGUMENTS` is provided, parse it for service name and category (e.g., "services/myapp" or "apps/portfolio").

## Steps:

1. **Gather information** — ask the user:
   - Service name (e.g., `nextcloud`, `gitea`, `portfolio`)
   - Category: `core`, `services`, or `apps`
   - Docker image + tag (e.g., `nextcloud:28-apache`)
   - Internal port the container listens on
   - Should it be HTTP-exposed via Traefik? (y/n)
   - Should it be admin-only (IP-restricted)? (y/n)
   - Approximate memory limit (e.g., 512M, 1G)
   - Any required environment variables?

2. **Create directory structure**:
   ```
   infrastructure/{category}/{service-name}/
   ├── docker-compose.yml
   └── .env.example
   ```

3. **Generate `docker-compose.yml`** using the template from CLAUDE.md, filled in with the collected values. Include:
   - `internal` network (always)
   - `proxy` network (if HTTP-exposed)
   - Traefik labels (if HTTP-exposed)
   - `admin-ip@file` middleware (if admin-only)
   - `security_opt: [no-new-privileges:true]`
   - Resource limits
   - `restart: unless-stopped`

4. **Generate `.env.example`** listing all variables with inline comments explaining each.

5. **Show the generated files** to the user for review before writing.

6. **Write files** once user confirms.

7. **Next steps** — remind the user:
   - Copy `.env.example` → `.env` and fill in values
   - Add DNS record for `{subdomain}.domain.com` pointing to server IP
   - Deploy with: `make deploy SERVICE=infrastructure/{category}/{service-name}`
   - Commit: `git add infrastructure/{category}/{service-name}/ && git commit -m "feat({category}): add {service-name}"`
