-- =============================================================================
-- TRACE — initial schema
-- TimescaleDB-backed Postgres. Schemas: core (catalogue) + polymarket (raw).
-- Future networks add their own schema with the same table layout.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS polymarket;

-- =============================================================================
-- core — network-agnostic catalogue served to the frontend
-- =============================================================================

CREATE TABLE core.networks (
    id          SERIAL PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL,
    color       TEXT,
    tagline     TEXT,
    enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order  INT NOT NULL DEFAULT 0,
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE core.coins (
    id          SERIAL PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    symbol      TEXT NOT NULL,
    name        TEXT NOT NULL,
    color       TEXT,
    base_price  NUMERIC,
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE core.network_coins (
    network_id  INT NOT NULL REFERENCES core.networks(id) ON DELETE CASCADE,
    coin_id     INT NOT NULL REFERENCES core.coins(id) ON DELETE CASCADE,
    enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order  INT NOT NULL DEFAULT 0,
    PRIMARY KEY (network_id, coin_id)
);

CREATE TABLE core.markets (
    id              BIGSERIAL PRIMARY KEY,
    network_id      INT NOT NULL REFERENCES core.networks(id),
    coin_id         INT REFERENCES core.coins(id),
    external_id     TEXT NOT NULL,
    kind            TEXT NOT NULL,
    question        TEXT,
    period_seconds  INT,
    strike          NUMERIC,
    starts_at       TIMESTAMPTZ,
    ends_at         TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    status          TEXT NOT NULL,
    resolution      TEXT,
    total_volume    NUMERIC,
    traders         INT,
    last_yes        NUMERIC,
    last_no         NUMERIC,
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (network_id, external_id)
);

CREATE INDEX markets_lookup_idx
    ON core.markets (network_id, coin_id, period_seconds, starts_at DESC);
CREATE INDEX markets_status_idx
    ON core.markets (status);
CREATE INDEX markets_window_idx
    ON core.markets (starts_at, ends_at);

CREATE TABLE core.market_outcomes (
    id                BIGSERIAL PRIMARY KEY,
    market_id         BIGINT NOT NULL REFERENCES core.markets(id) ON DELETE CASCADE,
    label             TEXT NOT NULL,
    external_token_id TEXT,
    UNIQUE (market_id, label)
);

CREATE INDEX market_outcomes_token_idx
    ON core.market_outcomes (external_token_id);

-- =============================================================================
-- polymarket — raw timeseries (hypertables on ts)
-- Same shape will be reproduced under future per-network schemas.
-- =============================================================================

CREATE TABLE polymarket.trades (
    market_id      BIGINT NOT NULL,
    outcome_id     BIGINT NOT NULL,
    ts             TIMESTAMPTZ NOT NULL,
    price          NUMERIC NOT NULL,
    size           NUMERIC NOT NULL,
    side           TEXT NOT NULL,
    taker_address  TEXT,
    maker_address  TEXT,
    tx_hash        TEXT,
    external_id    TEXT
);

SELECT create_hypertable('polymarket.trades', 'ts', chunk_time_interval => INTERVAL '1 day');

CREATE INDEX trades_market_ts_idx
    ON polymarket.trades (market_id, ts DESC);
CREATE INDEX trades_outcome_ts_idx
    ON polymarket.trades (outcome_id, ts DESC);
CREATE UNIQUE INDEX trades_dedup_idx
    ON polymarket.trades (market_id, outcome_id, ts, COALESCE(external_id, ''));

CREATE TABLE polymarket.book_snapshots (
    market_id   BIGINT NOT NULL,
    outcome_id  BIGINT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    bids        JSONB NOT NULL,
    asks        JSONB NOT NULL,
    hash        TEXT
);

SELECT create_hypertable('polymarket.book_snapshots', 'ts', chunk_time_interval => INTERVAL '1 day');

CREATE INDEX book_snapshots_market_ts_idx
    ON polymarket.book_snapshots (market_id, outcome_id, ts DESC);

CREATE TABLE polymarket.book_events (
    market_id   BIGINT NOT NULL,
    outcome_id  BIGINT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    side        TEXT NOT NULL,
    price       NUMERIC NOT NULL,
    size        NUMERIC NOT NULL
);

SELECT create_hypertable('polymarket.book_events', 'ts', chunk_time_interval => INTERVAL '1 day');

CREATE INDEX book_events_market_ts_idx
    ON polymarket.book_events (market_id, outcome_id, ts DESC);

CREATE TABLE polymarket.price_snapshots (
    market_id   BIGINT NOT NULL,
    outcome_id  BIGINT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    best_bid    NUMERIC,
    best_ask    NUMERIC,
    mid         NUMERIC,
    last        NUMERIC
);

SELECT create_hypertable('polymarket.price_snapshots', 'ts', chunk_time_interval => INTERVAL '1 day');

CREATE INDEX price_snapshots_market_ts_idx
    ON polymarket.price_snapshots (market_id, outcome_id, ts DESC);

CREATE TABLE polymarket.coin_prices (
    coin_id  INT NOT NULL,
    ts       TIMESTAMPTZ NOT NULL,
    price    NUMERIC NOT NULL,
    source   TEXT NOT NULL
);

SELECT create_hypertable('polymarket.coin_prices', 'ts', chunk_time_interval => INTERVAL '1 day');

CREATE INDEX coin_prices_coin_ts_idx
    ON polymarket.coin_prices (coin_id, ts DESC);

-- =============================================================================
-- Retention — 180 days on every hypertable
-- =============================================================================

SELECT add_retention_policy('polymarket.trades',          INTERVAL '180 days');
SELECT add_retention_policy('polymarket.book_snapshots',  INTERVAL '180 days');
SELECT add_retention_policy('polymarket.book_events',     INTERVAL '180 days');
SELECT add_retention_policy('polymarket.price_snapshots', INTERVAL '180 days');
SELECT add_retention_policy('polymarket.coin_prices',     INTERVAL '180 days');

-- =============================================================================
-- Migration tracking
-- =============================================================================

CREATE TABLE IF NOT EXISTS core.schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO core.schema_migrations (version) VALUES ('0001_init');
