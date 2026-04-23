#!/usr/bin/env bash
# First-time server provisioning script.
# Run as root on a fresh Debian server.
# Idempotent where possible.
set -euo pipefail

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'
info()    { echo -e "${GREEN}[*]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
die()     { echo -e "${RED}[ERR]${NC} $*"; exit 1; }

[[ $EUID -eq 0 ]] || die "Must run as root"

DEPLOY_USER="${DEPLOY_USER:-deploy}"
REPO_DIR="${REPO_DIR:-/opt/server}"

# ─── System Update ───────────────────────────────────────────────────────────
info "Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
  curl wget git vim htop tree \
  ufw fail2ban unattended-upgrades apt-listchanges \
  ca-certificates gnupg lsb-release \
  jq net-tools \
  logrotate

# ─── Automatic Security Updates ─────────────────────────────────────────────
info "Configuring unattended security upgrades..."
dpkg-reconfigure -plow unattended-upgrades
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

# ─── Docker Installation ─────────────────────────────────────────────────────
info "Installing Docker..."
if ! command -v docker &>/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  info "Docker already installed — skipping"
fi

# ─── Deploy User ─────────────────────────────────────────────────────────────
info "Creating deploy user '${DEPLOY_USER}'..."
if ! id "${DEPLOY_USER}" &>/dev/null; then
  useradd -m -s /bin/bash -G docker,sudo "${DEPLOY_USER}"
  usermod -p '*' "${DEPLOY_USER}"  # Disable password (not locked) — PAM allows SSH key auth
  info "User '${DEPLOY_USER}' created (password disabled, SSH key only)"
else
  warn "User '${DEPLOY_USER}' already exists — skipping creation"
fi

# Ensure deploy user is in docker group
usermod -aG docker "${DEPLOY_USER}"

# ─── SSH Key Setup (deploy user) ─────────────────────────────────────────────
# Copy root's authorized_keys to deploy user BEFORE hardening disables root login.
SSH_DIR="/home/${DEPLOY_USER}/.ssh"
mkdir -p "${SSH_DIR}"
chmod 700 "${SSH_DIR}"
if [ -s /root/.ssh/authorized_keys ]; then
  cp /root/.ssh/authorized_keys "${SSH_DIR}/authorized_keys"
  info "Copied root SSH keys to ${DEPLOY_USER}"
else
  touch "${SSH_DIR}/authorized_keys"
  warn "No root authorized_keys found — add your public key to ${SSH_DIR}/authorized_keys manually before hardening disables root login"
fi
chmod 600 "${SSH_DIR}/authorized_keys"
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${SSH_DIR}"

# ─── Repository Directory ────────────────────────────────────────────────────
info "Setting up repo directory at ${REPO_DIR}..."
mkdir -p "${REPO_DIR}"
chown "${DEPLOY_USER}:${DEPLOY_USER}" "${REPO_DIR}"

# ─── Docker Networks ─────────────────────────────────────────────────────────
info "Creating Docker networks..."
bash "$(dirname "$0")/networks.sh"

# ─── Logrotate for Docker ────────────────────────────────────────────────────
cat > /etc/logrotate.d/docker-containers <<'EOF'
/var/lib/docker/containers/*/*.log {
  rotate 7
  daily
  compress
  missingok
  delaycompress
  copytruncate
}
EOF

info "Bootstrap complete!"
echo ""
echo "  ✓ Docker installed"
echo "  ✓ User '${DEPLOY_USER}' created with your SSH key"
echo "  ✓ Docker networks created"
echo ""
echo "  NEXT — verify deploy user access BEFORE hardening:"
echo "    ssh -i ~/.ssh/server_key ${DEPLOY_USER}@<server-ip>"
echo ""
echo "  Once confirmed working, run hardening:"
echo "    bash scripts/harden.sh"
echo ""
warn "Do NOT run harden.sh until you have confirmed SSH access as '${DEPLOY_USER}'."
