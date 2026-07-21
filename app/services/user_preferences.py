"""Service for explicitly consented booking profile preferences."""

from datetime import datetime, timezone

from app.constants import SUPPORTED_TIMEZONE_IDS
from app.database import Database
from app.database.models import UserProfile


class UserPreferenceService:
    """Store, retrieve, and remove granular booking profile consent."""

    def __init__(self, db: Database):
        self.db = db

    def get_profile(self, telegram_id: int) -> UserProfile | None:
        """Return the user's explicitly remembered booking profile, if any."""
        row = self.db.execute_one(
            "SELECT * FROM user_preferences WHERE telegram_id = ?",
            (telegram_id,),
        )
        if row is None:
            return None

        return UserProfile(
            telegram_id=row["telegram_id"],
            preferred_name=row["preferred_name"],
            timezone=row["timezone"],
            email_mode=row["email_mode"],
            email=row["email"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save_preferred_name(self, telegram_id: int, preferred_name: str) -> None:
        """Explicitly remember the user's preferred booking name."""
        value = preferred_name.strip()
        if not value:
            raise ValueError("Preferred name must not be blank")
        self._upsert(telegram_id, "preferred_name", value)

    def clear_preferred_name(self, telegram_id: int) -> None:
        """Forget only the preferred booking name."""
        self._clear(telegram_id, "preferred_name")

    def save_timezone(self, telegram_id: int, timezone_id: str) -> None:
        """Explicitly remember a supported booking timezone."""
        if timezone_id not in SUPPORTED_TIMEZONE_IDS:
            raise ValueError(f"Unsupported timezone: {timezone_id}")
        self._upsert(telegram_id, "timezone", timezone_id)

    def clear_timezone(self, telegram_id: int) -> None:
        """Forget only the booking timezone."""
        self._clear(telegram_id, "timezone")

    def save_email(self, telegram_id: int, email: str) -> None:
        """Explicitly remember a personal booking email."""
        value = email.strip()
        if not value:
            raise ValueError("Email must not be blank")
        now = self._now()
        self.db.execute_write(
            """
            INSERT INTO user_preferences (
                telegram_id, email_mode, email, updated_at
            ) VALUES (?, 'saved', ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                email_mode = 'saved',
                email = excluded.email,
                updated_at = excluded.updated_at
            """,
            (telegram_id, value, now),
        )

    def save_private_email_mode(self, telegram_id: int) -> None:
        """Remember the preference to book without a personal email."""
        now = self._now()
        self.db.execute_write(
            """
            INSERT INTO user_preferences (telegram_id, email_mode, email, updated_at)
            VALUES (?, 'private', NULL, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                email_mode = 'private',
                email = NULL,
                updated_at = excluded.updated_at
            """,
            (telegram_id, now),
        )

    def clear_email(self, telegram_id: int) -> None:
        """Forget email consent and return to asking on each booking."""
        now = self._now()
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE user_preferences
                SET email_mode = 'ask', email = NULL, updated_at = ?
                WHERE telegram_id = ?
                """,
                (now, telegram_id),
            )
            self._prune_empty_profile(conn, telegram_id)

    def clear_profile(self, telegram_id: int) -> None:
        """Delete every remembered booking profile field."""
        self.db.execute_write(
            "DELETE FROM user_preferences WHERE telegram_id = ?",
            (telegram_id,),
        )

    def _upsert(self, telegram_id: int, column: str, value: str) -> None:
        if column not in {"preferred_name", "timezone"}:
            raise ValueError("Unsupported profile field")
        now = self._now()
        self.db.execute_write(
            f"""
            INSERT INTO user_preferences (telegram_id, {column}, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                {column} = excluded.{column},
                updated_at = excluded.updated_at
            """,
            (telegram_id, value, now),
        )

    def _clear(self, telegram_id: int, column: str) -> None:
        if column not in {"preferred_name", "timezone"}:
            raise ValueError("Unsupported profile field")
        now = self._now()
        with self.db.get_connection() as conn:
            conn.execute(
                f"""
                UPDATE user_preferences
                SET {column} = NULL, updated_at = ?
                WHERE telegram_id = ?
                """,
                (now, telegram_id),
            )
            self._prune_empty_profile(conn, telegram_id)

    @staticmethod
    def _prune_empty_profile(conn, telegram_id: int) -> None:
        conn.execute(
            """
            DELETE FROM user_preferences
            WHERE telegram_id = ?
              AND preferred_name IS NULL
              AND timezone IS NULL
              AND email_mode = 'ask'
              AND email IS NULL
            """,
            (telegram_id,),
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
