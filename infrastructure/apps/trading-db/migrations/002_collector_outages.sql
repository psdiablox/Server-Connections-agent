-- =============================================================
-- collector_outages — explicit log of every period the collector
-- was not recording data. Each row has end_ts = NULL while ongoing
-- and a finite end_ts once recovered. Reasons:
--   process_restart  collector process was down (gap detected at startup)
--   ws_zombie        WebSocket data stream went silent (watchdog fired)
--   ws_disconnect    WebSocket dropped the connection
-- =============================================================

CREATE TABLE polymarket.collector_outages (
    id          SERIAL      PRIMARY KEY,
    start_ts    TIMESTAMPTZ NOT NULL,
    end_ts      TIMESTAMPTZ,
    reason      TEXT        NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ON polymarket.collector_outages (start_ts);
CREATE INDEX ON polymarket.collector_outages (end_ts) WHERE end_ts IS NULL;
