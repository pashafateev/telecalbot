"""Tests for persisted user profile preferences."""

from app.database import Database
from app.database.migrations import initialize_schema
from app.services.user_preferences import UserPreferenceService


def test_returns_none_when_user_has_no_preferences(temp_db_path):
    db = Database(temp_db_path)
    initialize_schema(db)
    service = UserPreferenceService(db)

    assert service.get_timezone(12345) is None


def test_saves_and_loads_timezone_preference(temp_db_path):
    db = Database(temp_db_path)
    initialize_schema(db)
    service = UserPreferenceService(db)

    service.set_timezone(12345, "Europe/Moscow")

    preference = service.get_timezone(12345)
    assert preference is not None
    assert preference.telegram_id == 12345
    assert preference.timezone == "Europe/Moscow"
    assert preference.updated_at.tzinfo is not None


def test_updates_existing_timezone_preference(temp_db_path):
    db = Database(temp_db_path)
    initialize_schema(db)
    service = UserPreferenceService(db)

    service.set_timezone(12345, "Europe/Moscow")
    service.set_timezone(12345, "Asia/Yekaterinburg")

    preference = service.get_timezone(12345)
    assert preference is not None
    assert preference.timezone == "Asia/Yekaterinburg"
