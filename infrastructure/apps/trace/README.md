# TRACE — Trading Analytics Terminal

Historical analysis terminal for prediction-market data. v1 ingests Polymarket BTC 5-minute up/down windows + Binance BTC/USDT spot price.

Hosted at **`data.${DOMAIN}`** (e.g. `data.pserenlo.com`), behind two layers of access control:

1. **`admin-ip@file`** Traefik middleware — your IPv6 (in `infrastructure/core/traefik/dynamic/admin-access.yml`) is the only IP the proxy will speak to. Anyone else gets `403` before a container ever sees the request.
2. **App-level login** — single admin user, bcrypt password hash, 24h JWT in an httpOnly cookie. Every `/api/*` call validates the cookie.

## Architecture

```
┌──────────────┐  http  ┌─────────────────────────────┐
│ data.${DOMAIN}│──────▶│ Traefik (admin-ip middleware)│
└──────────────┘        └──────────────┬──────────────┘
                                       │
                       ┌───────────────┼───────────────┐
                       │               │               │
                  ┌────▼────┐     ┌────▼────┐    ┌─────▼─────┐
                  │ trace-  │     │ trace-  │    │  trace-   │
                  │  web    │     │  api    │    │ collector │
                  │ (nginx) │     │(FastAPI)│    │ (asyncio) │
                  └─────────┘     └────┬────┘    └─────┬─────┘
                                       │               │
                                  ┌────▼───────────────▼────┐
                                  │   trace-db (Timescale)  │
                                  └─────────────────────────┘
```

- **`trace-web`** — Vite + React + TS SPA. Static, served by nginx.
- **`trace-api`** — FastAPI. Read-only endpoints for the SPA. Runs DB migrations on startup.
- **`trace-collector`** — Polls Polymarket gamma every 60s for the next BTC 5-min market, subscribes to Polymarket CLOB websocket for trades + book snapshots + book diffs, subscribes to Binance `btcusdt@trade` for the underlying spot.
- **`trace-db`** — Postgres 16 + TimescaleDB. Schemas: `core` (catalogue) and `polymarket` (raw timeseries, hypertables, 180-day retention).

## First deploy

### 1. Set secrets on the server

```bash
ssh deploy@${SERVER_IP}
cp /opt/server/infrastructure/apps/trace/.env.example /opt/server/infrastructure/apps/trace/.env
nano /opt/server/infrastructure/apps/trace/.env
```

Generate values:

```bash
# POSTGRES_PASSWORD
openssl rand -hex 24

# TRACE_JWT_SECRET
openssl rand -hex 48

# TRACE_PASSWORD_HASH (interactive prompt — paste the output back into .env)
docker run --rm -it python:3.12-slim bash -c \
  "pip install -q bcrypt && python -c \"import bcrypt,getpass; print(bcrypt.hashpw(getpass.getpass().encode(),bcrypt.gensalt(rounds=12)).decode())\""
```

Set `TRACE_USER` to whatever username you want.

### 2. Confirm admin-IP is current

```bash
cat /opt/server/infrastructure/core/traefik/dynamic/admin-access.yml
```

If your IP has changed, edit it — Traefik hot-reloads.

### 3. Tracked deploy

```bash
make ship SERVICE=infrastructure/apps/trace
```

This will:
- `git pull` on the server
- `docker compose up -d --build` the stack
- annotate Grafana
- log the deploy to Loki (`{job="deploys"}`)

First boot takes a few minutes — Vite + Node build for the web container, plus initial migrations.

### 4. Verify

```bash
# all four containers up
ssh deploy@${SERVER_IP} "docker compose -f /opt/server/infrastructure/apps/trace/docker-compose.yml ps"

# api healthy
curl -s https://data.${DOMAIN}/api/health
# {"ok":true}

# discovery has begun
ssh deploy@${SERVER_IP} "docker logs trace-collector --tail 30"
```

Open `https://data.${DOMAIN}` in your browser. Log in. The Networks screen will list 7 cards — only Polymarket is enabled. Click it → BTC is the only active coin → click it → windows table fills as the collector observes them.

## Operating

### Tail collector

```bash
ssh deploy@${SERVER_IP} "docker logs trace-collector -f"
```

Look for `discovered market <id> @ <timestamp>` and `clob ws connecting (N tokens)` messages.

### Tail API

```bash
ssh deploy@${SERVER_IP} "docker logs trace-api -f"
```

### Inspect DB

```bash
ssh deploy@${SERVER_IP}
docker exec -it trace-db psql -U trace -d trace
\dn                                       -- list schemas (core, polymarket)
SELECT count(*) FROM core.markets;
SELECT count(*), max(ts) FROM polymarket.trades;
SELECT count(*), max(ts) FROM polymarket.book_snapshots;
```

### Reset just this stack

```bash
ssh deploy@${SERVER_IP}
cd /opt/server/infrastructure/apps/trace
docker compose down
docker volume rm trace_db-data    # destroys all collected data
docker compose up -d --build
```

## Adding a new network later

Each "network" gets its own Postgres schema. To add e.g. Kalshi:

1. New migration `db/migrations/0003_kalshi_init.sql` creating `CREATE SCHEMA kalshi` plus the same five hypertables (`trades`, `book_snapshots`, `book_events`, `price_snapshots`, `coin_prices`) under that schema.
2. New collector module `collector/kalshi.py` — same shape as `polymarket.py`, writing to `kalshi.*`.
3. Toggle `core.networks.enabled = TRUE` for `slug='kalshi'` (insert the row in the same migration).
4. The API's market endpoints already key off `network_slug`; they'll pick up the new schema once the table exists. For *now* the API queries `polymarket.*` directly — extending to a per-network schema dispatcher is a 30-line refactor.

## Files

```
api/                    FastAPI service
  app/main.py           ↳ entrypoint, lifespan
  app/auth.py           ↳ JWT cookie, bcrypt
  app/db.py             ↳ asyncpg pool + jsonb codec
  app/migrate.py        ↳ runs db/migrations on startup
  app/routers/          ↳ auth, networks, markets

collector/              Async Polymarket + Binance ingestion
  collector/main.py     ↳ orchestrator
  collector/discovery.py ↳ schedule-aware gamma polling
  collector/clob.py     ↳ Polymarket CLOB websocket
  collector/binance.py  ↳ btcusdt@trade websocket (1s buckets)
  collector/status.py   ↳ rolls up totals + status flips

web/                    Vite + React + TS frontend
  src/App.tsx           ↳ router (login → networks → polyCoins → polyWindows → polyAnalysis)
  src/api.ts            ↳ typed fetch wrappers
  src/screens/          ↳ one component per screen
  src/components/       ↳ AnalysisChart / TradesTable / OrderStatsRail
  src/styles.css        ↳ verbatim from the design

db/migrations/
  0001_init.sql         ↳ core + polymarket schemas, hypertables, retention
  0002_seed_catalogue.sql ↳ networks + coins
```

## Known follow-ups (not yet built)

- **Order-accumulation heatmap richness** — the v1 chart paints book snapshots into a coloured grid; the prototype's localized "blob" rendering with persistence + intensity gradients can be added once the DB has real data to look at.
- **Trade-bubble overlay on chart** — buy/sell markers per outcome are surfaced in the trades table and order-stats rail, but not as bubbles on the price chart.
- **Other networks / coins** — every non-Polymarket card and every non-BTC coin lands on a structured `// no data yet` empty state. Adding ingest for Ethereum, Solana, etc. is a per-network schema + collector module.
