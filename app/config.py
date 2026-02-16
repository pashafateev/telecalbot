"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # Telegram Bot Configuration (Required)
    telegram_bot_token: str

    # Cal.com API Configuration (Required)
    calcom_api_key: str
    cal_api_version: str = "2024-08-13"

    # Admin Configuration (Required)
    admin_telegram_id: int

    # Cal.com Event Configuration
    calcom_event_slug: str = "step"
    calcom_event_type_id: int | None = None

    # Database Configuration
    database_path: str = "telecalbot.db"

    # Application Settings
    log_level: str = "INFO"
    booking_conversation_timeout_seconds: int = 900

    model_config = {"env_file": ".env", "extra": "ignore"}


# Global settings instance
settings = Settings()
