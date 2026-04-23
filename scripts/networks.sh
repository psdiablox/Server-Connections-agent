#!/usr/bin/env bash
# Creates all required external Docker networks.
# Idempotent — safe to run multiple times.
set -euo pipefail

create_network() {
  local name="$1"
  local opts="${2:-}"
  if docker network inspect "$name" &>/dev/null; then
    echo "  [skip] Network '$name' already exists"
  else
    # shellcheck disable=SC2086
    docker network create $opts "$name"
    echo "  [ok]   Network '$name' created"
  fi
}

echo "[*] Creating Docker networks..."
create_network "proxy"
create_network "monitoring"
create_network "socket-proxy" "--internal"
echo "[done] Networks ready."
