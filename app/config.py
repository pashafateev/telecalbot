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
    calcom_event_type_id_30: int | None = None
    calcom_event_type_id_60: int | None = None

    # Database Configuration
    database_path: str = "telecalbot.db"

    # Application Settings
    log_level: str = "INFO"
    booking_conversation_timeout_seconds: int = 900

    model_config = {"env_file": ".env", "extra": "ignore"}

    def get_event_type_id(self, duration_minutes: int) -> int:
        """Get the event type ID for a given duration, with fallback.

        Raises:
            ValueError: If no event type ID is configured for the given duration.
        """
        if duration_minutes == 30:
            result = self.calcom_event_type_id_30 or self.calcom_event_type_id
        elif duration_minutes == 60:
            result = self.calcom_event_type_id_60 or self.calcom_event_type_id
        else:
            result = self.calcom_event_type_id

        if result is None:
            raise ValueError(
                f"No event type ID configured for {duration_minutes}-minute duration. "
                "Set CALCOM_EVENT_TYPE_ID or duration-specific IDs in config."
            )
        return result


# Global settings instance
settings = Settings()
