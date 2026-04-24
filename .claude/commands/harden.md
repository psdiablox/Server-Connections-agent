Verify or reapply security hardening on the server.

**Usage:** `/harden [check|apply]`

- `check` (default): read-only audit of current hardening state
- `apply`: run `harden.sh` to reapply all settings (idempotent)

Connect via `ssh -i ~/.ssh/server_key deploy@82.223.64.68`.

## For `check`:

### SSH
```bash
sudo sshd -T | grep -E "port|permitrootlogin|passwordauthentication|pubkeyauthentication|maxauthtries|x11forwarding|allowtcpforwarding"
```
Expected: root=no, password=no, pubkey=yes, maxauthtries=3, x11=no, tcpforwarding=no

Also check no cloud-init override is re-enabling password auth:
```bash
ls /etc/ssh/sshd_config.d/
```
The file `50-cloud-init.conf` must NOT exist (harden.sh removes it).

### UFW
```bash
sudo ufw status verbose
```
Expected:
- Default: deny incoming
- Port 22: open to Anywhere
- Ports 80/443: open to **Cloudflare IP ranges only** (15 IPv4 + 7 IPv6 ranges), NOT 0.0.0.0/0

### fail2ban
```bash
sudo systemctl is-active fail2ban && sudo fail2ban-client status
```
Expected: active, sshd jail running.

### Kernel (sysctl)
```bash
sysctl kernel.randomize_va_space net.ipv4.tcp_syncookies kernel.dmesg_restrict fs.protected_symlinks kernel.yama.ptrace_scope
```
Expected: 2, 1, 1, 1, 1

### Docker Daemon
```bash
cat /etc/docker/daemon.json
```
Expected: `no-new-privileges: true`, `icc: false`, `live-restore: true`, log limits set.

### Unattended Upgrades
```bash
systemctl is-active unattended-upgrades && cat /etc/apt/apt.conf.d/20auto-upgrades
```

## For `apply`:

**WARNING**: Before running, confirm SSH key access works as `deploy` user. Hardening restarts SSH and disables password auth — if keys aren't in place you will be locked out.

```bash
# On server
cd /opt/server && sudo bash scripts/harden.sh
```

After applying, re-run `check` to confirm all settings are in effect.

Report pass/fail for each category.
