.PHONY: help bootstrap harden networks deploy up down logs update status audit backup clean

SHELL := /bin/bash
BASE  := $(shell pwd)

# Default target
help:
	@echo ""
	@echo "  Server Infrastructure — Make Targets"
	@echo "  ─────────────────────────────────────"
	@echo "  Setup:"
	@echo "    make bootstrap          First-time server provisioning"
	@echo "    make harden             Apply security hardening (idempotent)"
	@echo "    make networks           Create required Docker external networks"
	@echo ""
	@echo "  Service Operations:"
	@echo "    make deploy  SERVICE=path/to/stack    Deploy a stack"
	@echo "    make up      SERVICE=path/to/stack    Start a stack"
	@echo "    make down    SERVICE=path/to/stack    Stop a stack"
	@echo "    make restart SERVICE=path/to/stack    Restart a stack"
	@echo "    make logs    SERVICE=path/to/stack    Tail logs for a stack"
	@echo "    make pull    SERVICE=path/to/stack    Pull latest images"
	@echo ""
	@echo "  Bulk Operations:"
	@echo "    make update             Pull & restart all stacks with changes"
	@echo "    make status             Show health of all services"
	@echo ""
	@echo "  Security & Maintenance:"
	@echo "    make audit              Run security audit"
	@echo "    make backup             Backup all persistent volumes"
	@echo "    make clean-images       Remove unused Docker images"
	@echo ""
	@echo "  Examples:"
	@echo "    make deploy SERVICE=infrastructure/core/traefik"
	@echo "    make logs   SERVICE=infrastructure/monitoring"
	@echo ""

# ─── Setup ──────────────────────────────────────────────────────────────────

bootstrap:
	@echo "[*] Bootstrapping server..."
	@bash scripts/bootstrap.sh

harden:
	@echo "[*] Applying security hardening..."
	@bash scripts/harden.sh

networks:
	@echo "[*] Creating Docker networks..."
	@bash scripts/networks.sh

# ─── Service Operations ──────────────────────────────────────────────────────

deploy: _require-service
	@echo "[*] Deploying $(SERVICE)..."
	@$(MAKE) _env-check SERVICE=$(SERVICE)
	@docker compose -f $(SERVICE)/docker-compose.yml config --quiet
	@docker compose -f $(SERVICE)/docker-compose.yml pull
	@docker compose -f $(SERVICE)/docker-compose.yml up -d --remove-orphans
	@docker compose -f $(SERVICE)/docker-compose.yml ps

up: _require-service
	@docker compose -f $(SERVICE)/docker-compose.yml up -d --remove-orphans

down: _require-service
	@docker compose -f $(SERVICE)/docker-compose.yml down

restart: _require-service
	@docker compose -f $(SERVICE)/docker-compose.yml restart

logs: _require-service
	@docker compose -f $(SERVICE)/docker-compose.yml logs -f --tail=100

pull: _require-service
	@docker compose -f $(SERVICE)/docker-compose.yml pull

# ─── Bulk Operations ─────────────────────────────────────────────────────────

update:
	@echo "[*] Updating all service stacks..."
	@bash scripts/update.sh

status:
	@echo ""
	@echo "  Docker Container Status"
	@echo "  ─────────────────────────────────────"
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | sort
	@echo ""

# ─── Security & Maintenance ──────────────────────────────────────────────────

audit:
	@echo "[*] Running security audit..."
	@echo ""
	@echo "  [1] Open Ports"
	@ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null
	@echo ""
	@echo "  [2] UFW Status"
	@ufw status verbose 2>/dev/null || echo "  UFW not available"
	@echo ""
	@echo "  [3] Fail2ban Status"
	@fail2ban-client status 2>/dev/null || echo "  Fail2ban not available"
	@echo ""
	@echo "  [4] Privileged Containers"
	@docker ps -q | xargs -I{} docker inspect --format='{{.Name}}: privileged={{.HostConfig.Privileged}}' {} | grep "true" || echo "  None found (good)"
	@echo ""
	@echo "  [5] Containers Running as Root"
	@docker ps -q | xargs -I{} docker inspect --format='{{.Name}}: user={{.Config.User}}' {} | grep 'user=$$' || echo "  All containers declare a user (verify manually)"
	@echo ""
	@echo "  [6] Containers with Host Network"
	@docker ps -q | xargs -I{} docker inspect --format='{{.Name}}: network={{.HostConfig.NetworkMode}}' {} | grep "host" || echo "  None found (good)"
	@echo ""
	@echo "  [7] Exposed .env Files Check"
	@git diff --cached --name-only 2>/dev/null | grep -E '\.env$$' && echo "  WARNING: .env file staged!" || echo "  No .env staged (good)"
	@echo ""

backup:
	@echo "[*] Running backup..."
	@bash scripts/backup.sh

clean-images:
	@echo "[*] Pruning unused Docker images..."
	@docker image prune -f
	@docker system df

# ─── Internal Helpers ────────────────────────────────────────────────────────

_require-service:
ifndef SERVICE
	$(error SERVICE is required. Usage: make $(MAKECMDGOALS) SERVICE=path/to/stack)
endif

_env-check:
	@if [ ! -f "$(SERVICE)/.env" ]; then \
		echo ""; \
		echo "  ERROR: $(SERVICE)/.env not found."; \
		echo "  Copy $(SERVICE)/.env.example to $(SERVICE)/.env and fill in values."; \
		echo ""; \
		exit 1; \
	fi
