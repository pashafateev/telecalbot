"""Tests for database functionality."""

import sqlite3

import pytest

from app.database import Database
from app.database.migrations import initialize_schema, run_migrations


def test_database_creates_file(temp_db_path):
    """Test that database file is created."""
    db = Database(temp_db_path)
    # Execute a simple query to ensure connection works
    db.execute("SELECT 1")


def test_schema_initialization(temp_db_path):
    """Test that schema is initialized correctly."""
    db = Database(temp_db_path)
    initialize_schema(db)

    # Check that tables exist
    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    table_names = [row["name"] for row in tables]

    assert "whitelist" in table_names
    assert "access_requests" in table_names
    assert "user_preferences" in table_names
    assert "bookings" in table_names

    booking_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(bookings)")
    }
    assert "internal_ref" in booking_columns


def test_user_profile_schema_has_nullable_consent_fields(temp_db_path):
    db = Database(temp_db_path)
    initialize_schema(db)

    columns = {
        row["name"]: row for row in db.execute("PRAGMA table_info(user_preferences)")
    }

    assert set(columns) == {
        "telegram_id",
        "preferred_name",
        "timezone",
        "email_mode",
        "email",
        "updated_at",
    }
    assert columns["preferred_name"]["notnull"] == 0
    assert columns["timezone"]["notnull"] == 0
    assert columns["email"]["notnull"] == 0
    assert columns["email_mode"]["dflt_value"] == "'ask'"


@pytest.mark.parametrize("email_mode", ["unknown", "", "SAVED"])
def test_user_profile_schema_rejects_invalid_email_modes(temp_db_path, email_mode):
    db = Database(temp_db_path)
    initialize_schema(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute_write(
            """
            INSERT INTO user_preferences (telegram_id, email_mode, updated_at)
            VALUES (?, ?, ?)
            """,
            (123, email_mode, "2026-07-21T00:00:00+00:00"),
        )


def test_user_profile_schema_requires_email_only_for_saved_mode(temp_db_path):
    db = Database(temp_db_path)
    initialize_schema(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute_write(
            """
            INSERT INTO user_preferences (telegram_id, email_mode, email, updated_at)
            VALUES (?, 'saved', NULL, ?)
            """,
            (123, "2026-07-21T00:00:00+00:00"),
        )

    with pytest.raises(sqlite3.IntegrityError):
        db.execute_write(
            """
            INSERT INTO user_preferences (telegram_id, email_mode, email, updated_at)
            VALUES (?, 'private', ?, ?)
            """,
            (456, "private-value@example.com", "2026-07-21T00:00:00+00:00"),
        )

    db.execute_write(
        """
        INSERT INTO user_preferences (telegram_id, email_mode, email, updated_at)
        VALUES (?, 'saved', ?, ?)
        """,
        (789, "saved@example.com", "2026-07-21T00:00:00+00:00"),
    )


def test_whitelist_insert_and_query(temp_db_path):
    """Test inserting and querying whitelist entries."""
    db = Database(temp_db_path)
    initialize_schema(db)

    # Insert a whitelist entry
    db.execute_write(
        """
        INSERT INTO whitelist (telegram_id, display_name, username, approved_at, approved_by)
        VALUES (?, ?, ?, ?, ?)
        """,
        (123456, "Test User", "testuser", "2025-01-01T00:00:00", 789),
    )

    # Query it back
    result = db.execute_one("SELECT * FROM whitelist WHERE telegram_id = ?", (123456,))

    assert result is not None
    assert result["telegram_id"] == 123456
    assert result["display_name"] == "Test User"
    assert result["username"] == "testuser"
    assert result["approved_by"] == 789


def test_access_request_status_constraint(temp_db_path):
    """Test that access_requests status has valid constraint."""
    import sqlite3

    db = Database(temp_db_path)
    initialize_schema(db)

    # Valid status should work
    db.execute_write(
        """
        INSERT INTO access_requests (telegram_id, display_name, requested_at, status)
        VALUES (?, ?, ?, ?)
        """,
        (123, "Test", "2025-01-01T00:00:00", "pending"),
    )

    # Invalid status should fail
    try:
        db.execute_write(
            """
            INSERT INTO access_requests (telegram_id, display_name, requested_at, status)
            VALUES (?, ?, ?, ?)
            """,
            (456, "Test2", "2025-01-01T00:00:00", "invalid_status"),
        )
        assert False, "Should have raised an error for invalid status"
    except sqlite3.IntegrityError:
        pass  # Expected


def test_migrates_bookings_start_end_columns(temp_db_path):
    """Legacy bookings schema is migrated to start_at/end_at."""
    db = Database(temp_db_path)

    db.execute_write(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            calcom_booking_id INTEGER NOT NULL,
            calcom_booking_uid TEXT NOT NULL,
            title TEXT NOT NULL,
            start TEXT NOT NULL,
            "end" TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            cancelled_at TEXT,
            UNIQUE(telegram_id, calcom_booking_id)
        )
        """
    )
    db.execute_write(
        """
        INSERT INTO bookings (
            telegram_id, calcom_booking_id, calcom_booking_uid, title, start, "end", status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            123,
            456,
            "uid-456",
            "Meeting",
            "2026-01-01T10:00:00Z",
            "2026-01-01T11:00:00Z",
            "active",
            "2026-01-01T00:00:00Z",
        ),
    )

    run_migrations(db)

    columns = {row["name"] for row in db.execute("PRAGMA table_info(bookings)")}
    assert "start_at" in columns
    assert "end_at" in columns

    row = db.execute_one("SELECT start_at, end_at FROM bookings WHERE telegram_id = ?", (123,))
    assert row["start_at"] == "2026-01-01T10:00:00Z"
    assert row["end_at"] == "2026-01-01T11:00:00Z"
    assert "internal_ref" in columns


def test_migration_resets_legacy_automatically_saved_timezones(temp_db_path):
    db = Database(temp_db_path)
    db.execute_write(
        """
        CREATE TABLE user_preferences (
            telegram_id INTEGER PRIMARY KEY,
            timezone TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute_write(
        """
        INSERT INTO user_preferences (telegram_id, timezone, updated_at)
        VALUES (?, ?, ?)
        """,
        (123, "Europe/Moscow", "2026-07-20T00:00:00+00:00"),
    )

    run_migrations(db)

    assert db.execute_one(
        "SELECT * FROM user_preferences WHERE telegram_id = ?", (123,)
    ) is None
    columns = {
        row["name"] for row in db.execute("PRAGMA table_info(user_preferences)")
    }
    assert columns == {
        "telegram_id",
        "preferred_name",
        "timezone",
        "email_mode",
        "email",
        "updated_at",
    }


def test_user_profile_migration_is_idempotent_and_preserves_explicit_profile(
    temp_db_path,
):
    db = Database(temp_db_path)
    run_migrations(db)
    db.execute_write(
        """
        INSERT INTO user_preferences (
            telegram_id, preferred_name, timezone, email_mode, email, updated_at
        ) VALUES (?, ?, ?, 'saved', ?, ?)
        """,
        (
            123,
            "Alice",
            "Europe/Moscow",
            "alice@example.com",
            "2026-07-21T00:00:00+00:00",
        ),
    )

    run_migrations(db)
    run_migrations(db)

    row = db.execute_one(
        "SELECT * FROM user_preferences WHERE telegram_id = ?", (123,)
    )
    assert row is not None
    assert row["preferred_name"] == "Alice"
    assert row["timezone"] == "Europe/Moscow"
    assert row["email_mode"] == "saved"
    assert row["email"] == "alice@example.com"
