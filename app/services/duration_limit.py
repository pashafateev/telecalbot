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
        self,
        telegram_id: int,
        max_duration_minutes: int,
        set_by: int,
        one_time: bool = True,
    ) -> None:
        """Set or update a duration limit for a user.

        A one-time limit applies to the user's next successful booking and is
        cleared automatically afterwards. An ongoing limit (one_time=False)
        persists until an admin removes it.
        """
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute_write(
            """
            INSERT INTO duration_limits
                (telegram_id, max_duration_minutes, set_at, set_by, one_time)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                max_duration_minutes = excluded.max_duration_minutes,
                set_at = excluded.set_at,
                set_by = excluded.set_by,
                one_time = excluded.one_time
            """,
            (telegram_id, max_duration_minutes, now, set_by, 1 if one_time else 0),
        )

    def remove_limit(self, telegram_id: int) -> bool:
        """Remove a duration limit. Returns True if a limit was removed."""
        rowcount = self.db.execute_write(
            "DELETE FROM duration_limits WHERE telegram_id = ?",
            (telegram_id,),
        )
        return rowcount > 0

    def consume_one_time_limit(self, telegram_id: int) -> bool:
        """Clear the user's limit if it is one-time. Returns True if cleared.

        Called after a successful booking so a single-use limit does not carry
        over to future bookings. Ongoing limits are left untouched.
        """
        rowcount = self.db.execute_write(
            "DELETE FROM duration_limits WHERE telegram_id = ? AND one_time = 1",
            (telegram_id,),
        )
        return rowcount > 0

    def get_all_limits(self) -> list[dict]:
        """Get all duration limits."""
        rows = self.db.execute(
            "SELECT telegram_id, max_duration_minutes, set_at, set_by, one_time "
            "FROM duration_limits ORDER BY set_at DESC"
        )
        return [
            {
                "telegram_id": row["telegram_id"],
                "max_duration_minutes": row["max_duration_minutes"],
                "set_at": row["set_at"],
                "set_by": row["set_by"],
                "one_time": bool(row["one_time"]),
            }
            for row in rows
        ]
