-- =============================================================================
-- Polymarket BTC up/down markets ship outcomes as "Up"/"Down". The collector
-- now normalizes to YES/NO at ingest. Re-label any existing rows so the
-- already-discovered markets line up with the API's YES/NO assumption.
-- =============================================================================

UPDATE core.market_outcomes SET label = 'YES' WHERE label = 'UP';
UPDATE core.market_outcomes SET label = 'NO'  WHERE label = 'DOWN';

INSERT INTO core.schema_migrations (version) VALUES ('0003_normalize_outcome_labels')
ON CONFLICT DO NOTHING;
