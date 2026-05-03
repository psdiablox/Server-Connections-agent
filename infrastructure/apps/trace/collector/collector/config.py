from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, case_sensitive=False)

    database_url: str

    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"
    polymarket_clob_ws: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    # Binance public spot trade websocket — used for the BTC underlying spot price.
    binance_ws: str = "wss://stream.binance.com:9443/ws/btcusdt@trade"
    binance_symbol: str = "BTCUSDT"

    # Schedule: 5-min BTC up/down on Polymarket, every 5 minutes from :00 UTC.
    btc_window_seconds: int = 300

    discovery_interval_seconds: int = 60
    status_interval_seconds: int = 30

    log_level: str = "info"


settings = Settings()
