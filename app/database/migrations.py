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

-- Duration limits per user (admin-managed)
CREATE TABLE IF NOT EXISTS duration_limits (
    telegram_id INTEGER PRIMARY KEY,
    max_duration_minutes INTEGER NOT NULL,
    set_at TEXT NOT NULL,
    set_by INTEGER NOT NULL
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
