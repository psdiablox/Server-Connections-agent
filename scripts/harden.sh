#!/usr/bin/env bash
# Security hardening script — idempotent, safe to re-run.
# Applies SSH, UFW, fail2ban, and kernel hardening.
set -euo pipefail

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'
info() { echo -e "${GREEN}[*]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
die()  { echo -e "${RED}[ERR]${NC} $*"; exit 1; }

[[ $EUID -eq 0 ]] || die "Must run as root"

SSH_PORT="${SSH_PORT:-22}"

# ─── SSH Hardening ───────────────────────────────────────────────────────────
info "Hardening SSH configuration..."
SSHD="/etc/ssh/sshd_config"
cp "${SSHD}" "${SSHD}.bak.$(date +%s)"

apply_sshd() {
  local key="$1" val="$2"
  if grep -qE "^#?${key}" "${SSHD}"; then
    sed -i "s|^#\?${key}.*|${key} ${val}|" "${SSHD}"
  else
    echo "${key} ${val}" >> "${SSHD}"
  fi
}

apply_sshd "Port"                        "${SSH_PORT}"
apply_sshd "PermitRootLogin"             "no"
apply_sshd "PasswordAuthentication"      "no"
apply_sshd "PubkeyAuthentication"        "yes"
apply_sshd "AuthorizedKeysFile"          ".ssh/authorized_keys"
apply_sshd "PermitEmptyPasswords"        "no"
apply_sshd "ChallengeResponseAuthentication" "no"
apply_sshd "X11Forwarding"              "no"
apply_sshd "PrintMotd"                  "no"
apply_sshd "AcceptEnv"                  "LANG LC_*"
apply_sshd "MaxAuthTries"               "3"
apply_sshd "LoginGraceTime"             "20"
apply_sshd "ClientAliveInterval"        "300"
apply_sshd "ClientAliveCountMax"        "2"
apply_sshd "AllowAgentForwarding"       "no"
apply_sshd "AllowTcpForwarding"         "no"
apply_sshd "Protocol"                   "2"

# Remove cloud-init override that re-enables password auth on VPS providers
rm -f /etc/ssh/sshd_config.d/50-cloud-init.conf

sshd -t && systemctl restart ssh && info "SSH hardened and restarted"

# ─── UFW Firewall ────────────────────────────────────────────────────────────
info "Configuring UFW firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow "${SSH_PORT}/tcp" comment "SSH"

# Ports 80/443 restricted to Cloudflare IPs only — prevents bypassing the proxy
for ip in \
  173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 \
  141.101.64.0/18 108.162.192.0/18 190.93.240.0/20 188.114.96.0/20 \
  197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13 \
  104.24.0.0/14 172.64.0.0/13 131.0.72.0/22 \
  2400:cb00::/32 2606:4700::/32 2803:f800::/32 2405:b500::/32 \
  2405:8100::/32 2a06:98c0::/29 2c0f:f248::/32; do
  ufw allow from "${ip}" to any port 80,443 proto tcp comment "Cloudflare"
done

ufw --force enable
ufw status

# ─── fail2ban ────────────────────────────────────────────────────────────────
info "Configuring fail2ban..."
FAIL2BAN_DIR="$(dirname "$0")/../security/fail2ban"
if [ -f "${FAIL2BAN_DIR}/jail.local" ]; then
  cp "${FAIL2BAN_DIR}/jail.local" /etc/fail2ban/jail.local
  if [ -d "${FAIL2BAN_DIR}/filter.d" ]; then
    cp "${FAIL2BAN_DIR}/filter.d/"* /etc/fail2ban/filter.d/ 2>/dev/null || true
  fi
fi
systemctl enable --now fail2ban
systemctl restart fail2ban
fail2ban-client status

# ─── Kernel Hardening (sysctl) ───────────────────────────────────────────────
info "Applying kernel hardening parameters..."
SYSCTL_CONF="$(dirname "$0")/../security/sysctl/99-hardening.conf"
if [ -f "${SYSCTL_CONF}" ]; then
  cp "${SYSCTL_CONF}" /etc/sysctl.d/99-hardening.conf
  sysctl --system
else
  warn "No sysctl config found at ${SYSCTL_CONF}"
fi

# ─── Disable unused services ──────────────────────────────────────────────────
info "Disabling unnecessary services..."
for svc in avahi-daemon cups bluetooth; do
  if systemctl is-enabled "$svc" &>/dev/null; then
    systemctl disable --now "$svc" 2>/dev/null && info "  Disabled: $svc"
  fi
done

# ─── Docker daemon hardening ─────────────────────────────────────────────────
info "Configuring Docker daemon security options..."
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "no-new-privileges": true,
  "userland-proxy": false,
  "live-restore": true,
  "icc": false
}
EOF
systemctl restart docker

info "Hardening complete!"
