"""Service for persisted user profile preferences."""

from datetime import datetime, timezone

from app.database import Database
from app.database.models import UserPreference


class UserPreferenceService:
    """Store and retrieve user-level profile preferences."""

    def __init__(self, db: Database):
        self.db = db

    def get_timezone(self, telegram_id: int) -> UserPreference | None:
        """Return the persisted timezone preference for a user, if present."""
        row = self.db.execute_one(
            "SELECT * FROM user_preferences WHERE telegram_id = ?",
            (telegram_id,),
        )
        if row is None:
            return None

        return UserPreference(
            telegram_id=row["telegram_id"],
            timezone=row["timezone"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def set_timezone(self, telegram_id: int, timezone_id: str) -> None:
        """Create or update the user's selected timezone."""
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute_write(
            """
            INSERT INTO user_preferences (telegram_id, timezone, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                timezone = excluded.timezone,
                updated_at = excluded.updated_at
            """,
            (telegram_id, timezone_id, now),
        )
