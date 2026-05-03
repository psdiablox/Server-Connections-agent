from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, case_sensitive=False)

    database_url: str
    migrations_dir: str = "/migrations"

    trace_user: str
    trace_password_hash: str
    trace_jwt_secret: str
    trace_cookie_domain: str = ""
    trace_cookie_secure: bool = True
    trace_session_hours: int = 24

    log_level: str = "info"


settings = Settings()
