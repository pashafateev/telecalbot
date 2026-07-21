"""Application configuration loaded from environment variables."""

from dataclasses import dataclass

from pydantic_settings import BaseSettings

from app.constants import SUPPORTED_BOOKING_DURATIONS


@dataclass(frozen=True)
class ResolvedEventType:
    """Cal.com event type and any duration override it requires."""

    event_type_id: int
    duration_minutes: int | None


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # Telegram Bot Configuration (Required)
    telegram_bot_token: str

    # Cal.com API Configuration (Required)
    calcom_api_key: str
    calcom_privacy_email: str | None = None

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
    booking_conversation_reminder_seconds_before_timeout: int = 120

    model_config = {"env_file": ".env", "extra": "ignore"}

    def resolve_event_type(self, duration_minutes: int) -> ResolvedEventType:
        """Resolve an event type and the duration override Cal.com expects.

        Raises:
            ValueError: If no event type ID is configured for the given duration.
        """
        if duration_minutes == 30:
            specific_event_type_id = self.calcom_event_type_id_30
        elif duration_minutes == 60:
            specific_event_type_id = self.calcom_event_type_id_60
        else:
            specific_event_type_id = None

        if specific_event_type_id is not None:
            return ResolvedEventType(
                event_type_id=specific_event_type_id,
                duration_minutes=None,
            )

        if self.calcom_event_type_id is None:
            raise ValueError(
                f"No event type ID configured for {duration_minutes}-minute duration. "
                "Set CALCOM_EVENT_TYPE_ID or duration-specific IDs in config."
            )
        return ResolvedEventType(
            event_type_id=self.calcom_event_type_id,
            duration_minutes=duration_minutes,
        )

    def get_event_type_id(self, duration_minutes: int) -> int:
        """Get the resolved event type ID for a given duration."""
        return self.resolve_event_type(duration_minutes).event_type_id

    def validate_event_type_configuration(self) -> None:
        """Fail startup unless every supported duration can be resolved."""
        for duration_minutes in SUPPORTED_BOOKING_DURATIONS:
            self.resolve_event_type(duration_minutes)


# Global settings instance
settings = Settings()
