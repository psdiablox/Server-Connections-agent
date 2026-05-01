import os

DB_URL           = os.environ["DATABASE_URL"]
GAMMA_API        = "https://gamma-api.polymarket.com"
CLOB_API         = "https://clob.polymarket.com"
CLOB_WS          = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

MARKET_KEYWORDS  = [k.strip() for k in os.getenv("MARKET_KEYWORDS", "BTC").split(",")]
PRICE_POLL_SEC   = float(os.getenv("PRICE_POLL_INTERVAL", "1.0"))
DISCOVERY_SEC    = float(os.getenv("DISCOVERY_INTERVAL", "30.0"))
CHECKPOINT_SEC   = float(os.getenv("CHECKPOINT_INTERVAL", "60.0"))
