-- =============================================================
-- Schema: polymarket
-- Stores all data collected from Polymarket prediction markets
-- =============================================================

CREATE SCHEMA IF NOT EXISTS polymarket;

-- -------------------------------------------------------------
-- markets
-- One row per market instance (e.g. each BTC 5-min window)
-- -------------------------------------------------------------
CREATE TABLE polymarket.markets (
    id            SERIAL PRIMARY KEY,
    condition_id  TEXT        UNIQUE NOT NULL,
    yes_token_id  TEXT        NOT NULL,
    no_token_id   TEXT        NOT NULL,
    yes_outcome   TEXT        NOT NULL DEFAULT 'YES',  -- actual label e.g. 'Up', 'YES'
    no_outcome    TEXT        NOT NULL DEFAULT 'NO',   -- actual label e.g. 'Down', 'NO'
    question      TEXT        NOT NULL,
    start_ts      TIMESTAMPTZ NOT NULL,
    end_ts        TIMESTAMPTZ NOT NULL,
    resolved      BOOLEAN     NOT NULL DEFAULT FALSE,
    outcome       TEXT,                                -- filled on resolution
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ON polymarket.markets (yes_token_id);
CREATE INDEX ON polymarket.markets (no_token_id);
CREATE INDEX ON polymarket.markets (end_ts);

-- -------------------------------------------------------------
-- price_snapshots
-- REST-polled every 1 second. YES token only (NO = 1 - YES).
-- best_bid / best_ask kept in memory from WebSocket, snapshotted here.
-- -------------------------------------------------------------
CREATE TABLE polymarket.price_snapshots (
    ts        TIMESTAMPTZ  NOT NULL,
    market_id INTEGER      NOT NULL REFERENCES polymarket.markets(id),
    price     NUMERIC(6,4) NOT NULL,
    best_bid  NUMERIC(6,4),
    best_ask  NUMERIC(6,4),
    spread    NUMERIC(6,4),
    PRIMARY KEY (market_id, ts)
);

CREATE INDEX ON polymarket.price_snapshots (market_id, ts DESC);

-- -------------------------------------------------------------
-- trades
-- Every fill pushed by WebSocket last_trade_price event.
-- Both YES and NO tokens tracked (independent order books).
-- -------------------------------------------------------------
CREATE TABLE polymarket.trades (
    id        BIGSERIAL    PRIMARY KEY,
    ts        TIMESTAMPTZ  NOT NULL,
    market_id INTEGER      NOT NULL REFERENCES polymarket.markets(id),
    token_id  TEXT         NOT NULL,
    outcome   TEXT          NOT NULL,
    price     NUMERIC(6,4)  NOT NULL,
    size      NUMERIC(12,2) NOT NULL,
    side      TEXT          NOT NULL CHECK (side IN ('BUY', 'SELL'))
);

CREATE INDEX ON polymarket.trades (market_id, ts DESC);
CREATE INDEX ON polymarket.trades (token_id, ts DESC);

-- -------------------------------------------------------------
-- book_checkpoints
-- Full order book snapshot. Stored on subscribe + every ~1 min.
-- Used as reconstruction anchor points.
-- -------------------------------------------------------------
CREATE TABLE polymarket.book_checkpoints (
    id        BIGSERIAL    PRIMARY KEY,
    ts        TIMESTAMPTZ  NOT NULL,
    market_id INTEGER      NOT NULL REFERENCES polymarket.markets(id),
    token_id  TEXT         NOT NULL,
    bids      JSONB        NOT NULL,
    asks      JSONB        NOT NULL
);

CREATE INDEX ON polymarket.book_checkpoints (token_id, ts DESC);

-- -------------------------------------------------------------
-- book_deltas
-- Individual order book level changes from WebSocket price_change events.
-- size = 0 means the price level was removed from the book.
-- -------------------------------------------------------------
CREATE TABLE polymarket.book_deltas (
    id        BIGSERIAL     PRIMARY KEY,
    ts        TIMESTAMPTZ   NOT NULL,
    market_id INTEGER       NOT NULL REFERENCES polymarket.markets(id),
    token_id  TEXT          NOT NULL,
    side      TEXT          NOT NULL CHECK (side IN ('BUY', 'SELL')),
    price     NUMERIC(6,4)  NOT NULL,
    size      NUMERIC(12,2) NOT NULL
);

CREATE INDEX ON polymarket.book_deltas (token_id, ts);
