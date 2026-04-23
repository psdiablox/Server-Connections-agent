Show the health and status of all running services.

**Usage:** `/status`

## Steps:

1. **Container overview**: Run `docker ps --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}\t{{.Ports}}" | sort`

2. **Stack-by-stack health**: For each `docker-compose.yml` found in `infrastructure/`, run `docker compose -f {path} ps` and show which containers are Up/Down/Restarting.

3. **Resource usage**: Run `docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"` — flag any container >80% memory limit.

4. **Disk space**: Run `df -h /` and `docker system df` — flag if disk >80%.

5. **Certificate status**: Check Traefik logs for certificate expiry warnings: `docker logs traefik-proxy --tail=50 2>&1 | grep -i "cert\|acme\|expire"`

6. **Recent errors**: For each stack, check if any container restarted recently: `docker ps -a --format "{{.Names}}\t{{.Status}}" | grep -v "Up "`

7. **Network status**: Run `docker network ls | grep -E "proxy|monitoring|socket-proxy"` — verify external networks exist.

Present results as a clean summary table. Use ✓ for healthy, ✗ for issues, and ⚠ for warnings. Highlight any containers that are not running or have restarted unexpectedly.
