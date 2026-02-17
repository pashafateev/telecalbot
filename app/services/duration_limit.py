"""Service for managing per-user duration limits."""

from datetime import datetime, timezone

from app.database.connection import Database


class DurationLimitService:
    """Service for managing duration limits set by admin."""

    def __init__(self, db: Database):
        self.db = db

    def get_limit(self, telegram_id: int) -> int | None:
        """Get the max duration limit for a user. Returns None if no limit."""
        row = self.db.execute_one(
            "SELECT max_duration_minutes FROM duration_limits WHERE telegram_id = ?",
            (telegram_id,),
        )
        if row is None:
            return None
        return row["max_duration_minutes"]

    def set_limit(
        self, telegram_id: int, max_duration_minutes: int, set_by: int
    ) -> None:
        """Set or update a duration limit for a user."""
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute_write(
            """
            INSERT INTO duration_limits (telegram_id, max_duration_minutes, set_at, set_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                max_duration_minutes = excluded.max_duration_minutes,
                set_at = excluded.set_at,
                set_by = excluded.set_by
            """,
            (telegram_id, max_duration_minutes, now, set_by),
        )

    def remove_limit(self, telegram_id: int) -> bool:
        """Remove a duration limit. Returns True if a limit was removed."""
        rowcount = self.db.execute_write(
            "DELETE FROM duration_limits WHERE telegram_id = ?",
            (telegram_id,),
        )
        return rowcount > 0

    def get_all_limits(self) -> list[dict]:
        """Get all duration limits."""
        rows = self.db.execute(
            "SELECT telegram_id, max_duration_minutes, set_at, set_by "
            "FROM duration_limits ORDER BY set_at DESC"
        )
        return [
            {
                "telegram_id": row["telegram_id"],
                "max_duration_minutes": row["max_duration_minutes"],
                "set_at": row["set_at"],
                "set_by": row["set_by"],
            }
            for row in rows
        ]
