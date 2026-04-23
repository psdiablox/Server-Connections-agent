Run a comprehensive security audit of the server infrastructure.

**Usage:** `/audit`

Perform all checks systematically and report findings grouped by severity: CRITICAL, HIGH, MEDIUM, LOW, INFO.

## Checks to perform:

### Network & Firewall
- Run `ss -tlnp` or `netstat -tlnp` — list all listening ports. Flag any unexpected open ports.
- Run `ufw status verbose` — verify only 22, 80, 443 (+ custom SSH port) are allowed.
- Check for containers with `ports:` that expose to host directly (bypassing Traefik).

### Docker Security
- For each running container, check:
  - `docker inspect --format='{{.Name}} privileged={{.HostConfig.Privileged}}' {id}` — flag any `true`
  - `docker inspect --format='{{.Name}} user={{.Config.User}}' {id}` — flag empty user (root)
  - `docker inspect --format='{{.Name}} network={{.HostConfig.NetworkMode}}' {id}` — flag `host`
  - Check for raw Docker socket mounts: `docker inspect --format='{{.Name}} {{.HostConfig.Binds}}' {id} | grep docker.sock`
- Run `docker ps --format '{{.Names}}\t{{.Ports}}'` — flag any direct port bindings on 0.0.0.0

### Access Control
- Check fail2ban: `fail2ban-client status` — list active jails and banned IPs
- Review recent SSH login attempts: `journalctl -u ssh --since "24 hours ago" | grep -i "failed\|invalid"` (last 20 lines)
- Check CrowdSec decisions: `docker exec crowdsec cscli decisions list` (if running)

### Secrets & Config
- `git diff --cached --name-only | grep -iE '\.env$'` — flag if any .env staged
- `find . -name "*.env" -not -name "*.example"` — list any .env files in repo (should only be .env.example)
- Check traefik acme.json permissions: `stat infrastructure/core/traefik/letsencrypt/acme.json 2>/dev/null`

### System
- Check unattended-upgrades: `systemctl is-active unattended-upgrades`
- Pending security updates: `apt-get -s upgrade 2>/dev/null | grep -i security | wc -l`
- Check disk space: `df -h` — flag >80% usage

### Traefik Config
- Review `infrastructure/core/traefik/dynamic/middlewares.yml` — confirm `secure-headers`, `rate-limit`, and `admin-ip` are defined
- Verify all public routes use at minimum `secure-headers@file` and `rate-limit@file` middleware

## Report format:

```
## Security Audit Report — {date}

### CRITICAL
- [issue] — [remediation]

### HIGH
- [issue] — [remediation]

### MEDIUM / LOW / INFO
- ...

### Summary
X issues found: Y critical, Z high, ...
```

If all checks pass, say so explicitly.
