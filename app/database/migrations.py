"""Database schema initialization and migrations."""

import logging

from app.database.connection import Database

logger = logging.getLogger(__name__)

SCHEMA = """
-- Whitelist of approved users
CREATE TABLE IF NOT EXISTS whitelist (
    telegram_id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    username TEXT,
    approved_at TEXT NOT NULL,
    approved_by INTEGER NOT NULL
);

-- Pending access requests
CREATE TABLE IF NOT EXISTS access_requests (
    telegram_id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    username TEXT,
    requested_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected'))
);

-- User preferences (timezone, etc.)
CREATE TABLE IF NOT EXISTS user_preferences (
    telegram_id INTEGER PRIMARY KEY,
    timezone TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Persisted bookings for /cancel_booking flow
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    calcom_booking_id INTEGER NOT NULL,
    calcom_booking_uid TEXT NOT NULL,
    title TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
    created_at TEXT NOT NULL,
    cancelled_at TEXT,
    UNIQUE(telegram_id, calcom_booking_id)
);

"""


def initialize_schema(db: Database) -> None:
    """Create all database tables if they don't exist."""
    logger.info("Initializing database schema...")

    with db.get_connection() as conn:
        conn.executescript(SCHEMA)

    logger.info("Database schema initialized successfully")


def run_migrations(db: Database) -> None:
    """Run any pending database migrations."""
    initialize_schema(db)
    _migrate_bookings_time_columns(db)
    _ensure_bookings_indexes(db)


def _migrate_bookings_time_columns(db: Database) -> None:
    """Backfill renamed bookings time columns for existing databases."""
    table_exists = db.execute_one(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bookings'"
    )
    if table_exists is None:
        return

    columns = {
        row["name"] for row in db.execute("PRAGMA table_info(bookings)")
    }
    has_old = "start" in columns and "end" in columns
    has_new = "start_at" in columns and "end_at" in columns

    if has_new:
        return
    if not has_old:
        return

    logger.info("Migrating bookings table columns start/end -> start_at/end_at")
    db.execute_write("ALTER TABLE bookings ADD COLUMN start_at TEXT")
    db.execute_write("ALTER TABLE bookings ADD COLUMN end_at TEXT")
    db.execute_write(
        """
        UPDATE bookings
        SET start_at = start, end_at = "end"
        WHERE start_at IS NULL OR end_at IS NULL
        """
    )


def _ensure_bookings_indexes(db: Database) -> None:
    """Ensure bookings indexes are aligned with current schema."""
    table_exists = db.execute_one(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bookings'"
    )
    if table_exists is None:
        return

    columns = {row["name"] for row in db.execute("PRAGMA table_info(bookings)")}
    if "start_at" not in columns:
        return

    db.execute_write("DROP INDEX IF EXISTS idx_bookings_user_status_start")
    db.execute_write(
        """
        CREATE INDEX IF NOT EXISTS idx_bookings_user_status_start
        ON bookings(telegram_id, status, start_at)
        """
    )
