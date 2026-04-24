Deploy a service stack with full tracking (Grafana annotation + Loki deploy log).

**Usage:** `/deploy [service-path]`

The correct deploy flow is: **commit locally → push to GitHub → pull on server → deploy**.
Never deploy directly from local files — the server must pull from GitHub first.

## Steps:

1. **Identify stack**: Use `$ARGUMENTS` if provided (e.g., `infrastructure/core/traefik`). Otherwise run `find infrastructure -name "docker-compose.yml" | sort` and ask which one.

2. **Check local state**:
   - `git status` — ensure no uncommitted changes that should be deployed
   - `git log --oneline -3` — confirm latest commit is pushed: `git push origin main` if needed

3. **Pre-flight checks on server** (via `ssh -i ~/.ssh/server_key deploy@82.223.64.68`):
   - `.env` file exists in the stack dir (if not, show `.env.example` and ask user to create it on server)
   - `docker network ls | grep -E "proxy|monitoring|socket-proxy"` — networks exist

4. **Deploy via tracked script**:
   ```bash
   ssh -i ~/.ssh/server_key deploy@82.223.64.68 \
     "cd /opt/server && bash scripts/deploy-service.sh {stack}"
   ```
   This does: `git pull` → `docker compose pull` → `docker compose up -d` → writes to `/var/log/deploys.log` → posts Grafana annotation.

5. **Verify**:
   - `docker ps --filter name={service}` — container is Up
   - `docker logs {container} --tail=20` — no errors
   - `curl -sI https://{subdomain}.pserenlo.com` — HTTP 2xx or 3xx (not 000 or 403 for public services)

6. **Confirm in Grafana**: Check `https://grafana.pserenlo.com` → Deploy History dashboard — new entry should appear.

7. **If config files were changed** during this session, stage and commit them (never commit `.env`, `admin-access.yml`, `.htpasswd`).

Report: what was deployed, container status, any errors, and the Grafana annotation URL.
