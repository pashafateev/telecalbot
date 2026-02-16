"""Tests for database functionality."""

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
