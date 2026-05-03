-- =============================================================================
-- Per-market trade statistics, denormalised onto core.markets so the windows
-- table can render them without a join-aggregate per row.
-- =============================================================================

ALTER TABLE core.markets ADD COLUMN IF NOT EXISTS trade_count   INT;
ALTER TABLE core.markets ADD COLUMN IF NOT EXISTS largest_trade NUMERIC;
ALTER TABLE core.markets ADD COLUMN IF NOT EXISTS avg_trade     NUMERIC;
ALTER TABLE core.markets ADD COLUMN IF NOT EXISTS close_btc     NUMERIC;

INSERT INTO core.schema_migrations (version) VALUES ('0005_market_trade_stats')
ON CONFLICT DO NOTHING;
