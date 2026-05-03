-- =============================================================================
-- TRACE — seed catalogue
-- Networks and coins shown in the UI. Only Polymarket + BTC are enabled for v1;
-- the rest render as cards with "no data yet" empty states.
-- =============================================================================

INSERT INTO core.networks (slug, name, kind, color, tagline, enabled, sort_order, meta) VALUES
  ('polymarket','Polymarket','prediction','#2d9cdb','Prediction · Binary YES/NO Markets',TRUE, 0,'{"symbol":"PM","tps":"—","blockTime":"event","tvl":1420000000}'),
  ('btc','Bitcoin','spot','#f7931a','Layer-1 Proof-of-Work',FALSE,1,'{"symbol":"BTC","tps":"7","blockTime":"10m","mcap":1284600000000}'),
  ('eth','Ethereum','spot','#627eea','Layer-1 Smart Contracts',FALSE,2,'{"symbol":"ETH","tps":"15","blockTime":"12s","tvl":84200000000,"mcap":412100000000}'),
  ('polygon','Polygon','spot','#8247e5','EVM Layer-2 Scaling',FALSE,3,'{"symbol":"POL","tps":"7000","blockTime":"2.1s","tvl":1060000000,"mcap":4870000000}'),
  ('sol','Solana','spot','#14f195','High-throughput Layer-1',FALSE,4,'{"symbol":"SOL","tps":"65000","blockTime":"0.4s","tvl":8900000000,"mcap":92300000000}'),
  ('arb','Arbitrum','spot','#28a0f0','Optimistic Rollup L2',FALSE,5,'{"symbol":"ARB","tps":"40000","blockTime":"0.25s","tvl":18400000000,"mcap":5200000000}'),
  ('base','Base','spot','#0052ff','Coinbase L2 Rollup',FALSE,6,'{"symbol":"BASE","tps":"350","blockTime":"2s","tvl":11700000000}')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO core.coins (slug, symbol, name, color, base_price, meta) VALUES
  ('btc','BTC','Bitcoin','#f7931a',64238,'{"vol24":28400000000,"marketCap":1284600000000}'),
  ('eth','ETH','Ethereum','#627eea',3428,'{"vol24":12400000000,"marketCap":412800000000}'),
  ('sol','SOL','Solana','#14f195',184.21,'{"vol24":3400000000,"marketCap":84600000000}'),
  ('xrp','XRP','Ripple','#00aae4',0.642,'{"vol24":1800000000,"marketCap":36200000000}'),
  ('doge','DOGE','Dogecoin','#c2a633',0.142,'{"vol24":920000000,"marketCap":20800000000}'),
  ('ada','ADA','Cardano','#0033ad',0.481,'{"vol24":420000000,"marketCap":17200000000}')
ON CONFLICT (slug) DO NOTHING;

-- Polymarket coverage: BTC enabled (v1), others rendered but disabled.
INSERT INTO core.network_coins (network_id, coin_id, enabled, sort_order)
SELECT n.id, c.id, c.slug='btc', sort_order
FROM core.networks n
CROSS JOIN (
  VALUES
    ('btc',  0),
    ('eth',  1),
    ('sol',  2),
    ('xrp',  3),
    ('doge', 4),
    ('ada',  5)
) AS x(coin_slug, sort_order)
JOIN core.coins c ON c.slug = x.coin_slug
WHERE n.slug = 'polymarket'
ON CONFLICT (network_id, coin_id) DO UPDATE
  SET enabled = EXCLUDED.enabled, sort_order = EXCLUDED.sort_order;

INSERT INTO core.schema_migrations (version) VALUES ('0002_seed_catalogue')
ON CONFLICT DO NOTHING;
