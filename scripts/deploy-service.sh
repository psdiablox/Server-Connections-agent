#!/usr/bin/env bash
# Deploy a service stack and record the deployment in Loki + Grafana annotations.
# Usage: deploy-service.sh infrastructure/core/traefik
#        deploy-service.sh --all   (pull + redeploy all stacks)
set -euo pipefail

REPO_DIR="/opt/server"
DEPLOY_LOG="/var/log/deploys.log"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*"; }

SERVICE="${1:-}"
[[ -z "$SERVICE" ]] && { echo "Usage: $0 infrastructure/{path} | --all"; exit 1; }

# ─── Pull latest from GitHub ─────────────────────────────────────────────────
info "Pulling latest from GitHub..."
cd "$REPO_DIR"
git pull --ff-only

COMMIT_FULL=$(git log -1 --format="%H")
COMMIT_SHORT=$(git log -1 --format="%h")
COMMIT_MSG=$(git log -1 --format="%s")
DEPLOYER=$(whoami)

# ─── Record deploy (must be defined before deploy_stack calls it) ─────────────
_record_deploy() {
  local svc="$1"
  local svc_name="${svc##*/}"
  local ts
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  local entry
  entry=$(python3 -c "import json; print(json.dumps({
    'time': '${ts}',
    'level': 'info',
    'event': 'deploy',
    'service': '${svc_name}',
    'stack': '${svc}',
    'commit': '${COMMIT_SHORT}',
    'commit_full': '${COMMIT_FULL}',
    'commit_msg': '${COMMIT_MSG}',
    'deployer': '${DEPLOYER}'
  }))")
  echo "$entry" | sudo tee -a "$DEPLOY_LOG" > /dev/null

  local grafana_pass
  grafana_pass=$(grep GRAFANA_ADMIN_PASSWORD "${REPO_DIR}/infrastructure/monitoring/.env" | cut -d= -f2)
  docker run --rm --network monitoring alpine/curl -sf -X POST \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"Deploy: ${svc_name} @ ${COMMIT_SHORT} — ${COMMIT_MSG}\",\"tags\":[\"deploy\",\"${svc_name}\"]}" \
    "http://admin:${grafana_pass}@monitoring-grafana:3000/api/annotations" > /dev/null \
    && info "Grafana annotation created" \
    || warn "Grafana annotation failed (non-fatal)"
}

# ─── Deploy ──────────────────────────────────────────────────────────────────
deploy_stack() {
  local svc="$1"
  local compose="${REPO_DIR}/${svc}/docker-compose.yml"
  [[ ! -f "$compose" ]] && { error "No docker-compose.yml at $svc"; return 1; }

  info "Deploying: $svc @ $COMMIT_SHORT"
  docker compose -f "$compose" pull --quiet
  docker compose -f "$compose" up -d --remove-orphans
  info "Done: $svc"

  _record_deploy "$svc"
}

if [[ "$SERVICE" == "--all" ]]; then
  while IFS= read -r compose_file; do
    svc="${compose_file#$REPO_DIR/}"
    svc="${svc%/docker-compose.yml}"
    [[ -f "${REPO_DIR}/${svc}/.env" ]] && deploy_stack "$svc" || warn "Skipping $svc (no .env)"
  done < <(find "${REPO_DIR}/infrastructure" -name "docker-compose.yml" | sort)
else
  deploy_stack "$SERVICE"
fi

info "Deployment complete. View history at https://grafana.pserenlo.com"
