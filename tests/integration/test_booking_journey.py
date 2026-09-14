"""Behavioral coverage through real commands and the bot's own callback buttons."""

from datetime import datetime, timezone

from .conftest import USER_ID


async def test_book_then_cancel_persists_provider_booking_and_correct_confirmation(journey):
    await journey.to_confirmation(email="guest@example.test")
    assert not journey.booking_requests
    assert not journey.bookings()

    await journey.click("Подтвердить запись")

    assert len(journey.booking_requests) == 1
    payload = journey.booking_requests[0]["body"]
    assert payload["eventTypeId"] == 777
    assert payload["lengthInMinutes"] == 30
    assert payload["attendee"] == {
        "name": "Integration Guest", "email": "guest@example.test",
        "timeZone": "Europe/Moscow", "language": "en",
    }
    selected = datetime.fromisoformat(journey.services.slots[0])
    assert datetime.fromisoformat(payload["start"].replace("Z", "+00:00")) == selected
    assert "Ваша встреча подтверждена" in journey.text
    assert "10:00" in journey.text and "Europe/Moscow" in journey.text
    assert "30 мин" in journey.text
    assert "guest@example.test" in journey.text

    rows = journey.bookings()
    assert len(rows) == 1
    assert rows[0]["telegram_id"] == USER_ID
    assert rows[0]["calcom_booking_uid"] == "local-booking-700"
    assert rows[0]["status"] == "active"
    assert rows[0]["internal_ref"] == payload["metadata"]["telecalbot_booking_ref"]
    assert datetime.fromisoformat(rows[0]["start_at"].replace("Z", "+00:00")) == selected
    assert not journey.db.execute("SELECT * FROM user_preferences")

    await journey.send("/cancel_booking")
    buttons = journey.screen["reply_markup"]["inline_keyboard"]
    assert len(buttons) == 1
    await journey.click(buttons[0][0]["text"])
    assert "Вы уверены" in journey.text
    await journey.click("Да, отменить")

    cancellations = [r for r in journey.services.snapshot()["requests"] if r["path"].endswith("/cancel")]
    assert [r["path"] for r in cancellations] == ["/v2/bookings/local-booking-700/cancel"]
    assert "Запись успешно отменена" in journey.text
    cancelled = journey.bookings()[0]
    assert cancelled["status"] == "cancelled"
    assert datetime.fromisoformat(cancelled["cancelled_at"]) <= datetime.now(timezone.utc)
    await journey.send("/cancel_booking")
    assert "нет предстоящих записей" in journey.text


async def test_rejected_privacy_email_can_recover_with_voluntary_email(journey):
    journey.services.booking_failures.append((400, {"code": "email_domain_cannot_receive_mail"}))
    await journey.to_confirmation()
    await journey.click("Подтвердить запись")

    assert "без личного email временно недоступна" in journey.text
    assert not journey.bookings()
    assert len(journey.booking_requests) == 1
    assert journey.booking_requests[0]["body"]["attendee"]["email"] == "privacy@example.test"

    await journey.click("Указать email")
    await journey.send("voluntary@example.test")
    await journey.click("Ничего не сохранять")
    await journey.click("Подтвердить запись")

    assert "Ваша встреча подтверждена" in journey.text
    assert "voluntary@example.test" in journey.text
    assert len(journey.booking_requests) == 2
    assert journey.booking_requests[1]["body"]["attendee"]["email"] == "voluntary@example.test"
    assert len(journey.bookings()) == 1
    assert not journey.db.execute("SELECT * FROM user_preferences")


async def test_slot_conflict_allows_selecting_another_slot_and_booking(journey):
    journey.services.booking_failures.append((409, {"message": "slot_conflict"}))
    await journey.to_confirmation()
    await journey.click("Подтвердить запись")

    assert "время уже занято" in journey.text
    assert not journey.bookings()
    assert len(journey.booking_requests) == 1
    await journey.click("Выбрать другое время")
    await journey.click("11:00")
    # Retry keeps contact details within this conversation and asks for consent again.
    await journey.click("Ничего не сохранять")
    assert "Integration Guest" in journey.text
    await journey.click("Подтвердить запись")

    assert "Ваша встреча подтверждена" in journey.text
    assert "11:00" in journey.text
    assert len(journey.booking_requests) == 2
    assert len(journey.bookings()) == 1
    start = journey.booking_requests[1]["body"]["start"]
    assert datetime.fromisoformat(start.replace("Z", "+00:00")) == datetime.fromisoformat(journey.services.slots[1])


async def test_duplicate_queued_confirmation_creates_only_one_booking(journey):
    await journey.to_confirmation()
    screen = journey.screen
    # Queue both taps before processing finishes, as a rapid double tap would arrive.
    await journey.deliver(
        journey.callback("Подтвердить запись", screen=screen),
        journey.callback("Подтвердить запись", screen=screen),
    )
    # Also deliver a late callback from the already displayed confirmation keyboard.
    await journey.click("Подтвердить запись", screen=screen)
    assert "Ваша встреча подтверждена" in journey.text
    assert len(journey.booking_requests) == 1
    assert len(journey.bookings()) == 1


async def test_book_restart_discards_old_details_and_confirmation_button(journey):
    await journey.to_confirmation(name="Abandoned Guest", email="old@example.test")
    old_screen = journey.screen
    await journey.send("/book")
    assert "Выберите ваш часовой пояс" in journey.text
    await journey.click("Подтвердить запись", screen=old_screen)
    assert not journey.booking_requests

    await journey.choose_slot(time="11:00", duration="60 минут")
    await journey.details(name="Replacement Guest", email="new@example.test")
    assert "Abandoned Guest" not in journey.text and "old@example.test" not in journey.text
    await journey.click("Подтвердить запись")
    assert "Ваша встреча подтверждена" in journey.text
    assert len(journey.booking_requests) == 1
    payload = journey.booking_requests[0]["body"]
    assert payload["attendee"]["name"] == "Replacement Guest"
    assert payload["attendee"]["email"] == "new@example.test"
    assert payload["lengthInMinutes"] == 60
    assert len(journey.bookings()) == 1


async def test_jobqueue_timeout_ignores_expired_keyboard_and_allows_new_booking(journey_factory):
    async with journey_factory(timeout=2, reminder_before=1) as journey:
        await journey.to_confirmation()
        expired_screen = journey.screen
        messages_before_wait = len(journey.services.snapshot()["messages"])
        await journey.wait_for_text("сессия записи скоро истечет", after=messages_before_wait)
        await journey.wait_for_text("Сессия записи истекла", after=messages_before_wait)
        await journey.click("Подтвердить запись", screen=expired_screen)
        assert not journey.booking_requests
        assert not journey.bookings()

        await journey.to_confirmation()
        await journey.click("Подтвердить запись")
        assert "Ваша встреча подтверждена" in journey.text
        assert len(journey.booking_requests) == 1
        assert len(journey.bookings()) == 1
        assert not journey.application.job_queue.jobs()
