from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RIDAX Platform"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    secret_key: str = "change-this-secret-key"
    access_token_expire_minutes: int = 60
    password_reset_ttl_minutes: int = 15
    frontend_url: str = "http://localhost:3000"

    database_url: str = "postgresql+psycopg2://ridax:ridax@db:5432/ridax"
    cors_origins: str = "http://localhost:3000"

    telegram_bot_token: str = ""
    telegram_default_chat_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""

    default_language: str = "es"
    default_currency: str = "USD"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
