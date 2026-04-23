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
  passwd -l "${DEPLOY_USER}"  # Lock password — SSH key only
  info "User '${DEPLOY_USER}' created (password locked, SSH key required)"
else
  warn "User '${DEPLOY_USER}' already exists — skipping creation"
fi

# Ensure deploy user is in docker group
usermod -aG docker "${DEPLOY_USER}"

# ─── SSH Key Setup (deploy user) ─────────────────────────────────────────────
SSH_DIR="/home/${DEPLOY_USER}/.ssh"
mkdir -p "${SSH_DIR}"
chmod 700 "${SSH_DIR}"
touch "${SSH_DIR}/authorized_keys"
chmod 600 "${SSH_DIR}/authorized_keys"
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${SSH_DIR}"
info "SSH dir ready at ${SSH_DIR}/authorized_keys — add your public key manually"

# ─── Repository Directory ────────────────────────────────────────────────────
info "Setting up repo directory at ${REPO_DIR}..."
mkdir -p "${REPO_DIR}"
chown "${DEPLOY_USER}:${DEPLOY_USER}" "${REPO_DIR}"

# ─── Docker Networks ─────────────────────────────────────────────────────────
info "Creating Docker networks..."
bash "$(dirname "$0")/networks.sh"

# ─── Apply Security Hardening ────────────────────────────────────────────────
info "Applying security hardening..."
bash "$(dirname "$0")/harden.sh"

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
echo "  Next steps:"
echo "  1. Add SSH public key to /home/${DEPLOY_USER}/.ssh/authorized_keys"
echo "  2. Copy .env.example files to .env and fill in values"
echo "  3. Deploy core stack: make deploy SERVICE=infrastructure/core/traefik"
echo "  4. Deploy monitoring: make deploy SERVICE=infrastructure/monitoring"
echo ""
warn "Reboot recommended before deploying services."
