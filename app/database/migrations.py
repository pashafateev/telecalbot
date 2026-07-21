"""Database schema initialization and migrations."""

import logging

from app.database.connection import Database

logger = logging.getLogger(__name__)

USER_PREFERENCES_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_preferences (
    telegram_id INTEGER PRIMARY KEY,
    preferred_name TEXT,
    timezone TEXT,
    email_mode TEXT NOT NULL DEFAULT 'ask'
        CHECK (email_mode IN ('ask', 'private', 'saved')),
    email TEXT,
    updated_at TEXT NOT NULL,
    CHECK (
        (email_mode = 'saved' AND email IS NOT NULL AND trim(email) <> '')
        OR (email_mode IN ('ask', 'private') AND email IS NULL)
    )
);
"""

USER_PREFERENCES_COLUMNS = {
    "telegram_id",
    "preferred_name",
    "timezone",
    "email_mode",
    "email",
    "updated_at",
}

SCHEMA = f"""
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

-- Explicitly consented booking profile preferences
{USER_PREFERENCES_SCHEMA}

-- Duration limits per user (admin-managed)
CREATE TABLE IF NOT EXISTS duration_limits (
    telegram_id INTEGER PRIMARY KEY,
    max_duration_minutes INTEGER NOT NULL,
    set_at TEXT NOT NULL,
    set_by INTEGER NOT NULL
);

-- Persisted bookings for /cancel_booking flow
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    internal_ref TEXT,
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
    _migrate_user_preferences_profile(db)
    _migrate_bookings_time_columns(db)
    _ensure_bookings_internal_ref(db)
    _ensure_bookings_indexes(db)


def _migrate_user_preferences_profile(db: Database) -> None:
    """Replace the legacy auto-saved timezone table with consented profile fields."""
    table_info = db.execute("PRAGMA table_info(user_preferences)")
    columns = {row["name"] for row in table_info}
    if columns == USER_PREFERENCES_COLUMNS:
        return

    logger.info(
        "Resetting legacy user preferences while migrating to explicit profile consent"
    )
    with db.get_connection() as conn:
        conn.execute("ALTER TABLE user_preferences RENAME TO user_preferences_legacy")
        conn.execute(USER_PREFERENCES_SCHEMA)
        conn.execute("DROP TABLE user_preferences_legacy")


def _migrate_bookings_time_columns(db: Database) -> None:
    """Backfill renamed bookings time columns for existing databases."""
    table_exists = db.execute_one(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bookings'"
    )
    if table_exists is None:
        return

    columns = {row["name"] for row in db.execute("PRAGMA table_info(bookings)")}
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


def _ensure_bookings_internal_ref(db: Database) -> None:
    """Add private booking references to existing databases."""
    table_exists = db.execute_one(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bookings'"
    )
    if table_exists is None:
        return

    columns = {row["name"] for row in db.execute("PRAGMA table_info(bookings)")}
    if "internal_ref" not in columns:
        logger.info("Adding internal_ref column to bookings table")
        db.execute_write("ALTER TABLE bookings ADD COLUMN internal_ref TEXT")

    db.execute_write(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_internal_ref
        ON bookings(internal_ref)
        WHERE internal_ref IS NOT NULL
        """
    )
