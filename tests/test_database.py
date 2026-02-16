"""Tests for database functionality."""

from app.database import Database
from app.database.migrations import initialize_schema


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
