Show the full health and status of all running services on the server.

**Usage:** `/status`

Connect via `ssh -i ~/.ssh/server_key deploy@82.223.64.68` for all checks.

## Steps:

1. **Container health**:
   ```bash
   docker ps --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}" | sort
   ```
   Expected: 13 containers all Up. Flag any Restarting or Exited.

2. **Resource usage**:
   ```bash
   docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | sort
   ```
   Flag any container using >80% of its memory limit.

3. **Disk space**:
   ```bash
   df -h / && docker system df
   ```
   Flag if root partition >80%.

4. **Recent deploy history** (last 5 deploys):
   ```bash
   tail -5 /var/log/deploys.log | python3 -c "import sys,json; [print(json.loads(l)['time'], json.loads(l)['service'], json.loads(l)['commit']) for l in sys.stdin]"
   ```

5. **Traefik health** (certificate + routing):
   ```bash
   docker logs traefik-proxy --tail=20 2>&1 | grep -iE "error|cert|acme|expire"
   ```

6. **CrowdSec activity**:
   ```bash
   docker exec crowdsec cscli decisions list
   ```

7. **UFW status**:
   ```bash
   sudo ufw status | head -5
   ```
   Expected: active, SSH open, 80/443 Cloudflare-only.

8. **Repo sync check** — confirm server is up to date with GitHub:
   ```bash
   cd /opt/server && git fetch && git status
   ```
   Flag if server is behind `origin/main`.

Present as a clean summary. Use ✓ for healthy, ✗ for problems, ⚠ for warnings needing attention.
