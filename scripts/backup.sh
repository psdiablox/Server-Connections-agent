#!/usr/bin/env bash
# Backup all named Docker volumes to /opt/backups/{date}/.
# Keeps last 7 daily backups. Idempotent.
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/opt/backups}"
DATE="$(date +%Y-%m-%d_%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/${DATE}"
KEEP_DAYS="${KEEP_DAYS:-7}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[*]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }

mkdir -p "${BACKUP_DIR}"

# ─── Backup named volumes ─────────────────────────────────────────────────────
info "Starting volume backup to ${BACKUP_DIR}..."

# Get all named volumes (skip anonymous ones)
VOLUMES=$(docker volume ls --format '{{.Name}}' | grep -v '^[a-f0-9]\{64\}$' || true)

if [ -z "${VOLUMES}" ]; then
  warn "No named volumes found."
else
  for vol in ${VOLUMES}; do
    info "  Backing up volume: ${vol}"
    docker run --rm \
      -v "${vol}:/data:ro" \
      -v "${BACKUP_DIR}:/backup" \
      alpine:latest \
      tar -czf "/backup/${vol}.tar.gz" -C /data . \
      && echo "  [ok] ${vol}.tar.gz"
  done
fi

# ─── Backup compose files & configs ──────────────────────────────────────────
info "Backing up infrastructure configs..."
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
tar -czf "${BACKUP_DIR}/infrastructure-configs.tar.gz" \
  -C "${SCRIPT_DIR}" \
  --exclude='.git' \
  --exclude='*.env' \
  --exclude='acme.json' \
  . && echo "  [ok] infrastructure-configs.tar.gz"

# ─── Cleanup old backups ──────────────────────────────────────────────────────
info "Cleaning backups older than ${KEEP_DAYS} days..."
find "${BACKUP_ROOT}" -maxdepth 1 -type d -mtime "+${KEEP_DAYS}" -exec rm -rf {} + 2>/dev/null || true

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
info "Backup complete: ${BACKUP_DIR}"
du -sh "${BACKUP_DIR}"
echo ""
info "Available backups:"
ls -lh "${BACKUP_ROOT}" | tail -n +2
