"""SQLite database connection manager."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


class Database:
    """SQLite database manager with connection-per-request pattern."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.database_path
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """Ensure database file and parent directories exist."""
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """Get a database connection with WAL mode enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute a query and return all results."""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def execute_one(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        """Execute a query and return the first result."""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchone()

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Execute a write query and return the lastrowid."""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid


# Global database instance
db = Database()
