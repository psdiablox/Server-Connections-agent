-- =============================================================================
-- Heartbeat table: every collector source emits a row roughly every 10s while
-- it's healthy. Gaps > GAP_THRESHOLD seconds during a market window are
-- reported as outages on the analysis chart.
-- =============================================================================

CREATE TABLE core.collection_health (
    source TEXT NOT NULL,
    ts     TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (source, ts)
);

SELECT create_hypertable('core.collection_health', 'ts', chunk_time_interval => INTERVAL '1 day');

CREATE INDEX collection_health_source_ts_idx
    ON core.collection_health (source, ts DESC);

SELECT add_retention_policy('core.collection_health', INTERVAL '180 days');

INSERT INTO core.schema_migrations (version) VALUES ('0004_collection_health')
ON CONFLICT DO NOTHING;
