Run a comprehensive security audit of the server infrastructure.

**Usage:** `/audit`

Connect via `ssh -i ~/.ssh/server_key deploy@82.223.64.68`. Report findings grouped by severity: CRITICAL, HIGH, MEDIUM, LOW, INFO.

## Checks:

### 1. Firewall (UFW)
```bash
sudo ufw status verbose
```
Expected:
- Default: deny incoming, allow outgoing
- Port 22: open to Anywhere (SSH)
- Ports 80/443: open to **Cloudflare IP ranges ONLY** (not 0.0.0.0/0)
- Flag any other open ports

### 2. SSH Hardening
```bash
sudo sshd -T | grep -E "permitrootlogin|passwordauthentication|pubkeyauthentication|maxauthtries"
```
Expected: `permitrootlogin no`, `passwordauthentication no`, `maxauthtries 3`

### 3. fail2ban
```bash
sudo fail2ban-client status && sudo fail2ban-client status sshd
```
Expected: sshd jail active. Show currently banned IPs.

### 4. CrowdSec
```bash
docker exec crowdsec cscli decisions list
docker exec crowdsec cscli bouncers list
```
Expected: bouncer `traefik-bouncer` connected.

### 5. Docker Container Security
For each running container:
```bash
# Privileged (should only be cadvisor)
docker ps -q | xargs docker inspect --format '{{.Name}}: privileged={{.HostConfig.Privileged}}' | grep true

# Host network (should be none)
docker ps -q | xargs docker inspect --format '{{.Name}}: {{.HostConfig.NetworkMode}}' | grep host

# Docker socket mounts (only traefik-proxy and portainer allowed — both :ro)
docker ps -q | xargs docker inspect --format '{{.Name}}: {{.HostConfig.Binds}}' | grep docker.sock

# no-new-privileges check
docker ps -q | xargs docker inspect --format '{{.Name}}: {{.HostConfig.SecurityOpt}}'
```

### 6. Traefik Middleware on All Routes
Verify `admin-ip@file` is applied to every service:
```bash
for c in traefik-proxy portainer monitoring-grafana vaultwarden uptime-kuma; do
  docker inspect $c --format "{{.Name}}: {{index .Config.Labels \"traefik.http.routers.$(docker inspect $c --format '{{range $k,$v := .Config.Labels}}{{if contains $k \"middlewares\"}}{{$k}}{{end}}{{end}}').middlewares\"}}"
done
```
Every admin service must have `admin-ip@file`.

### 7. Secrets Hygiene
```bash
# No .env files in git
cd /opt/server && git ls-files | grep -E '\.env$|htpasswd|admin-access\.yml$'

# No secrets in staged files
git diff --cached --name-only | grep -iE '\.env$|htpasswd|admin-access'

# admin-access.yml exists (gitignored but required)
ls /opt/server/infrastructure/core/traefik/dynamic/admin-access.yml
```

### 8. Exposed Ports (host level)
```bash
sudo ss -tlnp | grep -v 127.0.0.1
```
Expected: only 22 (ssh), 80 (docker/traefik), 443 (docker/traefik).

### 9. System Security
```bash
sysctl kernel.randomize_va_space    # expect 2
sysctl net.ipv4.tcp_syncookies      # expect 1
sysctl kernel.dmesg_restrict        # expect 1
systemctl is-active unattended-upgrades
```

## Report format:
```
## Security Audit — {date}

### CRITICAL / HIGH / MEDIUM / LOW / INFO
- [finding] — [remediation]

### Summary
X issues: Y critical, Z high, ...
```
