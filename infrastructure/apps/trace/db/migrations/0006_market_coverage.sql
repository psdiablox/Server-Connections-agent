-- =============================================================================
-- Per-market data-coverage percentage. Computed by the status loop as
-- (distinct seconds in [starts_at, ends_at) with a price_snapshot row) /
-- period_seconds * 100. 100 % = continuous data; lower = gaps.
-- =============================================================================

ALTER TABLE core.markets ADD COLUMN IF NOT EXISTS data_coverage_pct NUMERIC;

INSERT INTO core.schema_migrations (version) VALUES ('0006_market_coverage')
ON CONFLICT DO NOTHING;
