#!/usr/bin/env bash
# Pull latest images and restart stacks with changes.
# Iterates over all docker-compose.yml files in infrastructure/.
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[*]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[ERR]${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FAILED=()

info "Searching for service stacks..."
while IFS= read -r compose_file; do
  stack_dir="$(dirname "${compose_file}")"
  stack_name="$(basename "${stack_dir}")"

  # Skip if no .env file (can't deploy without it)
  if [ ! -f "${stack_dir}/.env" ]; then
    warn "  Skipping ${stack_name} — no .env file found"
    continue
  fi

  info "  Updating: ${stack_name}"
  if docker compose -f "${compose_file}" pull --quiet 2>&1; then
    docker compose -f "${compose_file}" up -d --remove-orphans --quiet-pull 2>&1 \
      && info "  [ok] ${stack_name}" \
      || { error "  [fail] ${stack_name}"; FAILED+=("${stack_name}"); }
  else
    error "  [fail] Pull failed for ${stack_name}"
    FAILED+=("${stack_name}")
  fi
done < <(find "${SCRIPT_DIR}/infrastructure" -name "docker-compose.yml" | sort)

echo ""
if [ ${#FAILED[@]} -eq 0 ]; then
  info "All stacks updated successfully."
else
  error "Failed stacks: ${FAILED[*]}"
  exit 1
fi

info "Cleaning up unused images..."
docker image prune -f --filter "until=24h"
