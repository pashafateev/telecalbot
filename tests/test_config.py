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

    assert settings.cal_api_version == "2024-06-14"
    assert settings.calcom_event_slug == "step"
    assert settings.database_path == "telecalbot.db"
    assert settings.log_level == "INFO"


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
