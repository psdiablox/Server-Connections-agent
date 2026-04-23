Verify and optionally reapply security hardening to the server.

**Usage:** `/harden [check|apply]`

- `check` (default): audit hardening state without making changes.
- `apply`: run the hardening script to apply/reapply all settings.

## For `check` — verify each hardening layer:

### SSH
- `sshd -T | grep -E "permitrootlogin|passwordauthentication|pubkeyauthentication|maxauthtries|x11forwarding"`
- Flag any values that deviate from the hardened template in `security/ssh/sshd_config.hardened`

### UFW
- `ufw status verbose`
- Expected: default deny in, allow 22(or custom)/80/443 only.

### fail2ban
- `fail2ban-client status`
- Verify `sshd` jail is active. Check `traefik-auth` jail if Traefik is running.

### Kernel (sysctl)
- Compare current values against `security/sysctl/99-hardening.conf`:
  ```
  sysctl kernel.randomize_va_space    # expect: 2
  sysctl net.ipv4.tcp_syncookies      # expect: 1
  sysctl kernel.dmesg_restrict        # expect: 1
  sysctl fs.protected_symlinks        # expect: 1
  ```

### Docker daemon
- `cat /etc/docker/daemon.json`
- Verify: `no-new-privileges: true`, `icc: false`, `live-restore: true`

### Unattended upgrades
- `systemctl is-active unattended-upgrades`
- `cat /etc/apt/apt.conf.d/20auto-upgrades`

## For `apply`:
Run `bash scripts/harden.sh` (requires root). Show output and confirm each section succeeded.
Warn the user: SSH restart will drop current connections if key auth is not set up — confirm before proceeding.

Report a pass/fail for each hardening category.
