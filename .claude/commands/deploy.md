Deploy a service stack from the infrastructure directory.

**Usage:** `/deploy [service-path]`

If `$ARGUMENTS` is provided, use it as the stack path (e.g., `infrastructure/core/traefik`). Otherwise, list available stacks and ask which one to deploy.

## Steps to follow:

1. **Identify stack**: Use `$ARGUMENTS` if provided. Otherwise run `find infrastructure -name "docker-compose.yml" | sort` and ask the user to choose.

2. **Pre-flight checks**:
   - Verify `.env` file exists alongside `docker-compose.yml`. If missing, show the `.env.example` contents and prompt the user to create it before proceeding.
   - Run `docker compose -f {stack}/docker-compose.yml config` to validate syntax. Show any errors.
   - Check that required external networks exist: `docker network ls | grep -E "proxy|monitoring|socket-proxy"`

3. **Pull images**: Run `docker compose -f {stack}/docker-compose.yml pull`

4. **Deploy**: Run `docker compose -f {stack}/docker-compose.yml up -d --remove-orphans`

5. **Verify**:
   - `docker compose -f {stack}/docker-compose.yml ps` — check all containers are Up
   - `docker compose -f {stack}/docker-compose.yml logs --tail=30` — check for errors
   - If service is HTTP-exposed, attempt `curl -sI https://{subdomain}.{DOMAIN}` to verify Traefik routing

6. **Security check**: Confirm all containers in the stack have `no-new-privileges` set and no raw Docker socket mounted.

7. **Commit**: If any config files were modified during this process, commit them with `git add` (excluding .env) and create a meaningful commit.

Report what was deployed, the container statuses, and any issues found.
