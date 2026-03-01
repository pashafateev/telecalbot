"""Tests for persisted booking storage service."""

from datetime import datetime, timedelta, timezone

from app.database import Database
from app.database.migrations import initialize_schema
from app.services.booking_service import BookingService
from app.services.calcom_client import BookingResponse


def _make_booking_response(
    booking_id: int,
    start: datetime,
    end: datetime,
) -> BookingResponse:
    return BookingResponse(
        id=booking_id,
        uid=f"uid-{booking_id}",
        title=f"Meeting {booking_id}",
        start=start.isoformat().replace("+00:00", "Z"),
        end=end.isoformat().replace("+00:00", "Z"),
        status="accepted",
    )


def test_save_and_list_upcoming_bookings(temp_db_path):
    db = Database(temp_db_path)
    initialize_schema(db)
    service = BookingService(db)

    now = datetime.now(timezone.utc)
    upcoming = _make_booking_response(1001, now + timedelta(hours=1), now + timedelta(hours=2))
    past = _make_booking_response(1002, now - timedelta(hours=3), now - timedelta(hours=2))

    service.save_booking(telegram_id=12345, booking=upcoming)
    service.save_booking(telegram_id=12345, booking=past)

    results = service.list_upcoming_bookings(12345)

    assert len(results) == 1
    assert results[0].calcom_booking_id == 1001


def test_get_booking_for_user_enforces_ownership(temp_db_path):
    db = Database(temp_db_path)
    initialize_schema(db)
    service = BookingService(db)

    now = datetime.now(timezone.utc)
    booking = _make_booking_response(2001, now + timedelta(hours=1), now + timedelta(hours=2))
    row_id = service.save_booking(telegram_id=111, booking=booking)

    assert service.get_booking_for_user(row_id, telegram_id=111) is not None
    assert service.get_booking_for_user(row_id, telegram_id=222) is None


def test_mark_cancelled_hides_booking_from_upcoming(temp_db_path):
    db = Database(temp_db_path)
    initialize_schema(db)
    service = BookingService(db)

    now = datetime.now(timezone.utc)
    booking = _make_booking_response(3001, now + timedelta(hours=1), now + timedelta(hours=2))
    row_id = service.save_booking(telegram_id=12345, booking=booking)

    assert service.mark_cancelled(row_id, telegram_id=12345) is True
    assert service.mark_cancelled(row_id, telegram_id=12345) is False
    assert service.list_upcoming_bookings(12345) == []
