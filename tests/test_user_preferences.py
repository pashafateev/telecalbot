"""Tests for explicitly consented booking profile preferences."""

import pytest

from app.database import Database
from app.database.migrations import initialize_schema
from app.services.user_preferences import UserPreferenceService


@pytest.fixture
def profile_service(temp_db_path):
    db = Database(temp_db_path)
    initialize_schema(db)
    return UserPreferenceService(db)


def test_returns_none_when_user_has_no_profile(profile_service):
    assert profile_service.get_profile(12345) is None


def test_saves_and_loads_granular_profile_fields(profile_service):
    profile_service.save_preferred_name(12345, "Alice")
    profile_service.save_timezone(12345, "Europe/Moscow")
    profile_service.save_email(12345, "alice@example.com")

    profile = profile_service.get_profile(12345)

    assert profile is not None
    assert profile.telegram_id == 12345
    assert profile.preferred_name == "Alice"
    assert profile.timezone == "Europe/Moscow"
    assert profile.email_mode == "saved"
    assert profile.email == "alice@example.com"
    assert profile.updated_at.tzinfo is not None


def test_profile_survives_service_restart(profile_service):
    profile_service.save_preferred_name(12345, "Alice")
    profile_service.save_timezone(12345, "Asia/Yekaterinburg")

    restarted_service = UserPreferenceService(profile_service.db)
    profile = restarted_service.get_profile(12345)

    assert profile is not None
    assert profile.preferred_name == "Alice"
    assert profile.timezone == "Asia/Yekaterinburg"


def test_rejects_unsupported_timezone_without_creating_profile(profile_service):
    with pytest.raises(ValueError, match="Unsupported timezone"):
        profile_service.save_timezone(12345, "Europe/Removed")

    assert profile_service.get_profile(12345) is None


def test_private_email_mode_discards_personal_email(profile_service):
    profile_service.save_email(12345, "alice@example.com")

    profile_service.save_private_email_mode(12345)

    profile = profile_service.get_profile(12345)
    assert profile is not None
    assert profile.email_mode == "private"
    assert profile.email is None


def test_clearing_email_returns_to_ask_mode(profile_service):
    profile_service.save_preferred_name(12345, "Alice")
    profile_service.save_email(12345, "alice@example.com")

    profile_service.clear_email(12345)

    profile = profile_service.get_profile(12345)
    assert profile is not None
    assert profile.preferred_name == "Alice"
    assert profile.email_mode == "ask"
    assert profile.email is None


def test_clear_operations_are_field_specific(profile_service):
    profile_service.save_preferred_name(12345, "Alice")
    profile_service.save_timezone(12345, "Europe/Moscow")
    profile_service.save_private_email_mode(12345)

    profile_service.clear_preferred_name(12345)
    profile_service.clear_timezone(12345)

    profile = profile_service.get_profile(12345)
    assert profile is not None
    assert profile.preferred_name is None
    assert profile.timezone is None
    assert profile.email_mode == "private"


def test_clear_profile_removes_every_remembered_field(profile_service):
    profile_service.save_preferred_name(12345, "Alice")
    profile_service.save_timezone(12345, "Europe/Moscow")
    profile_service.save_email(12345, "alice@example.com")

    profile_service.clear_profile(12345)

    assert profile_service.get_profile(12345) is None
