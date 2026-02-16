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
    start TEXT NOT NULL,
    "end" TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
    created_at TEXT NOT NULL,
    cancelled_at TEXT,
    UNIQUE(telegram_id, calcom_booking_id)
);

CREATE INDEX IF NOT EXISTS idx_bookings_user_status_start
ON bookings(telegram_id, status, start);
"""


def initialize_schema(db: Database) -> None:
    """Create all database tables if they don't exist."""
    logger.info("Initializing database schema...")

    with db.get_connection() as conn:
        conn.executescript(SCHEMA)

    logger.info("Database schema initialized successfully")


def run_migrations(db: Database) -> None:
    """Run any pending database migrations."""
    # For now, just initialize schema
    # Future migrations can be added here with version tracking
    initialize_schema(db)
