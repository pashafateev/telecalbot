"""Service for storing and retrieving user bookings."""

from datetime import datetime, timezone

from app.database import Database
from app.database.models import StoredBooking
from app.services.calcom_client import BookingResponse


def _parse_iso_datetime(value: str) -> datetime:
    """Parse ISO datetime strings, accepting UTC Z suffix."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class BookingService:
    """Persist booking records used by /cancel_booking flow."""

    def __init__(self, db: Database):
        self.db = db

    def save_booking(self, telegram_id: int, booking: BookingResponse) -> int:
        """Insert or refresh an active booking record for a user."""
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute_write(
            """
            INSERT INTO bookings (
                telegram_id,
                calcom_booking_id,
                calcom_booking_uid,
                title,
                start,
                "end",
                status,
                created_at,
                cancelled_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, NULL)
            ON CONFLICT(telegram_id, calcom_booking_id) DO UPDATE SET
                calcom_booking_uid = excluded.calcom_booking_uid,
                title = excluded.title,
                start = excluded.start,
                "end" = excluded."end",
                status = 'active',
                cancelled_at = NULL
            """,
            (
                telegram_id,
                booking.id,
                booking.uid,
                booking.title,
                booking.start,
                booking.end,
                now,
            ),
        )
        row = self.db.execute_one(
            """
            SELECT id
            FROM bookings
            WHERE telegram_id = ? AND calcom_booking_id = ?
            """,
            (telegram_id, booking.id),
        )
        return row["id"]

    def list_upcoming_bookings(self, telegram_id: int) -> list[StoredBooking]:
        """Return active bookings that haven't ended yet."""
        now = datetime.now(timezone.utc)
        rows = self.db.execute(
            """
            SELECT *
            FROM bookings
            WHERE telegram_id = ? AND status = 'active'
            ORDER BY start
            """,
            (telegram_id,),
        )
        bookings = [self._row_to_booking(row) for row in rows]
        return [booking for booking in bookings if booking.end >= now]

    def get_booking_for_user(self, booking_row_id: int, telegram_id: int) -> StoredBooking | None:
        """Get a single booking owned by a user."""
        row = self.db.execute_one(
            """
            SELECT *
            FROM bookings
            WHERE id = ? AND telegram_id = ?
            """,
            (booking_row_id, telegram_id),
        )
        if row is None:
            return None
        return self._row_to_booking(row)

    def mark_cancelled(self, booking_row_id: int, telegram_id: int) -> bool:
        """Mark an active booking as cancelled."""
        cancelled_at = datetime.now(timezone.utc).isoformat()
        rowcount = self.db.execute_write(
            """
            UPDATE bookings
            SET status = 'cancelled', cancelled_at = ?
            WHERE id = ? AND telegram_id = ? AND status = 'active'
            """,
            (cancelled_at, booking_row_id, telegram_id),
        )
        return rowcount > 0

    @staticmethod
    def _row_to_booking(row) -> StoredBooking:
        return StoredBooking(
            id=row["id"],
            telegram_id=row["telegram_id"],
            calcom_booking_id=row["calcom_booking_id"],
            calcom_booking_uid=row["calcom_booking_uid"],
            title=row["title"],
            start=_parse_iso_datetime(row["start"]),
            end=_parse_iso_datetime(row["end"]),
            status=row["status"],
            created_at=_parse_iso_datetime(row["created_at"]),
            cancelled_at=_parse_iso_datetime(row["cancelled_at"])
            if row["cancelled_at"]
            else None,
        )
