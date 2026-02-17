"""Tests for configuration loading."""

import os

import pytest


def test_config_loads_from_env():
    """Test that configuration loads from environment variables."""
    # Set up environment (conftest.py sets these)
    from app.config import Settings

    settings = Settings()

    assert settings.telegram_bot_token == "test_token"
    assert settings.calcom_api_key == "test_api_key"
    assert settings.admin_telegram_id == 123456789


def test_config_defaults():
    """Test that default values are set correctly."""
    from app.config import Settings

    settings = Settings()

    assert settings.cal_api_version == "2024-08-13"
    assert settings.calcom_event_slug == "step"
    assert settings.database_path == "telecalbot.db"
    assert settings.log_level == "INFO"
    assert settings.booking_conversation_timeout_seconds == 900


def test_get_event_type_id_with_duration_specific():
    """Test get_event_type_id returns duration-specific IDs."""
    from app.config import Settings

    settings = Settings(
        calcom_event_type_id=1,
        calcom_event_type_id_30=30,
        calcom_event_type_id_60=60,
    )
    assert settings.get_event_type_id(30) == 30
    assert settings.get_event_type_id(60) == 60


def test_get_event_type_id_fallback():
    """Test get_event_type_id falls back to calcom_event_type_id."""
    from app.config import Settings

    settings = Settings(calcom_event_type_id=99)
    assert settings.get_event_type_id(30) == 99
    assert settings.get_event_type_id(60) == 99


def test_get_event_type_id_unknown_duration():
    """Test get_event_type_id with unknown duration falls back."""
    from app.config import Settings

    settings = Settings(calcom_event_type_id=42)
    assert settings.get_event_type_id(15) == 42


def test_get_event_type_id_raises_when_none():
    """Test get_event_type_id raises ValueError when no ID configured."""
    from app.config import Settings

    settings = Settings()
    with pytest.raises(ValueError, match="No event type ID configured"):
        settings.get_event_type_id(30)


def test_config_required_fields():
    """Test that missing required fields raise validation error."""
    # Temporarily unset required environment variables
    old_token = os.environ.pop("TELEGRAM_BOT_TOKEN", None)

    try:
        from pydantic import ValidationError

        from app.config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None)  # Don't load from .env file
    finally:
        # Restore environment
        if old_token:
            os.environ["TELEGRAM_BOT_TOKEN"] = old_token
