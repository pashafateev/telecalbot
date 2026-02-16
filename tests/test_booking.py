"""Tests for the booking conversation handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import BadRequest

from app.constants import RUSSIAN_TIMEZONES
from app.handlers.booking import (
    BookingState,
    _format_duration,
    book_command,
    build_availability_keyboard,
    build_timezone_keyboard,
    cancel,
    change_timezone,
    confirm_booking,
    email_decision,
    enter_email,
    enter_name,
    format_date_header,
    format_time,
    load_more_dates,
    noop,
    select_slot,
    select_timezone,
    slot_to_utc,
)
from app.services.calcom_client import (
    AvailabilityResponse,
    BookingResponse,
    CalComAPIError,
    TimeSlot,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_message():
    msg = AsyncMock()
    msg.reply_text = AsyncMock()
    return msg


@pytest.fixture
def mock_query():
    q = AsyncMock()
    q.answer = AsyncMock()
    q.edit_message_text = AsyncMock()
    q.message = AsyncMock()
    q.message.reply_text = AsyncMock()
    return q


@pytest.fixture
def mock_update(mock_message):
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.first_name = "Alice"
    update.message = mock_message
    update.callback_query = None
    return update


@pytest.fixture
def mock_update_with_query(mock_query):
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.first_name = "Alice"
    update.message = None
    update.callback_query = mock_query
    return update


@pytest.fixture
def mock_calcom_client():
    client = AsyncMock()
    client.get_availability = AsyncMock()
    client.create_booking = AsyncMock()
    return client


@pytest.fixture
def mock_context(mock_calcom_client):
    context = MagicMock()
    context.bot = AsyncMock()
    context.bot_data = {"calcom_client": mock_calcom_client}
    context.user_data = {}
    return context


@pytest.fixture
def availability_response():
    """Sample availability response with two days of slots."""
    return AvailabilityResponse(
        slots={
            "2026-01-06": [
                TimeSlot(time="2026-01-06T10:00:00.000+03:00"),
                TimeSlot(time="2026-01-06T11:00:00.000+03:00"),
                TimeSlot(time="2026-01-06T14:00:00.000+03:00"),
            ],
            "2026-01-07": [
                TimeSlot(time="2026-01-07T09:00:00.000+03:00"),
                TimeSlot(time="2026-01-07T16:00:00.000+03:00"),
            ],
        }
    )


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestFormatDateHeader:
    def test_formats_date_as_russian_weekday_month_day(self):
        result = format_date_header("2026-01-06")
        assert "Вторник" in result
        assert "янв" in result
        assert "6" in result

    def test_no_leading_zero_on_day(self):
        result = format_date_header("2026-01-06")
        assert " 06" not in result
        assert result == "Вторник, 6 янв"


class TestFormatTime:
    def test_formats_as_24_hour(self):
        result = format_time("2026-01-06T10:00:00.000+03:00")
        assert result == "10:00"

    def test_afternoon_stays_24_hour(self):
        result = format_time("2026-01-06T14:00:00.000+03:00")
        assert result == "14:00"

    def test_midnight_is_00_00(self):
        result = format_time("2026-01-06T00:00:00.000+00:00")
        assert result == "00:00"


class TestSlotToUtc:
    def test_converts_offset_aware_to_utc(self):
        result = slot_to_utc("2026-01-06T10:00:00.000+03:00")
        # 10:00 Moscow (UTC+3) -> 07:00 UTC
        assert result == "2026-01-06T07:00:00Z"

    def test_utc_input_unchanged(self):
        result = slot_to_utc("2026-01-06T07:00:00.000+00:00")
        assert result == "2026-01-06T07:00:00Z"


class TestBuildTimezoneKeyboard:
    def test_has_button_for_each_timezone(self):
        keyboard = build_timezone_keyboard()
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_labels = [btn.text for btn in all_buttons]
        for _, label in RUSSIAN_TIMEZONES:
            assert label in button_labels

    def test_has_cancel_button(self):
        keyboard = build_timezone_keyboard()
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        labels = [btn.text for btn in all_buttons]
        assert "Отмена" in labels

    def test_callback_data_uses_tz_prefix(self):
        keyboard = build_timezone_keyboard()
        tz_buttons = [
            btn
            for row in keyboard.inline_keyboard
            for btn in row
            if btn.callback_data and btn.callback_data.startswith("tz:")
        ]
        assert len(tz_buttons) == len(RUSSIAN_TIMEZONES)


class TestBuildAvailabilityKeyboard:
    def test_shows_day_headers(self, availability_response):
        keyboard = build_availability_keyboard(availability_response.slots)
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        noop_buttons = [b for b in all_buttons if b.callback_data == "noop"]
        assert len(noop_buttons) == 2  # One header per day

    def test_shows_slot_buttons(self, availability_response):
        keyboard = build_availability_keyboard(availability_response.slots)
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        slot_buttons = [b for b in all_buttons if b.callback_data and b.callback_data.startswith("slot:")]
        assert len(slot_buttons) == 5  # 3 + 2 slots

    def test_has_navigation_buttons(self, availability_response):
        keyboard = build_availability_keyboard(availability_response.slots)
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        labels = [btn.text for btn in all_buttons]
        assert any("→" in lbl for lbl in labels)

    def test_has_cancel_button(self, availability_response):
        keyboard = build_availability_keyboard(availability_response.slots)
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        labels = [btn.text for btn in all_buttons]
        assert "Отмена" in labels

    def test_uses_short_timezone_button_label(self, availability_response):
        keyboard = build_availability_keyboard(availability_response.slots)
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        labels = [btn.text for btn in all_buttons]
        assert "Часовой пояс" in labels
        assert "Сменить часовой пояс" not in labels

    def test_timezone_button_is_on_separate_row(self, availability_response):
        keyboard = build_availability_keyboard(availability_response.slots)
        timezone_rows = [
            row
            for row in keyboard.inline_keyboard
            if len(row) == 1 and row[0].text == "Часовой пояс"
        ]
        assert len(timezone_rows) == 1

    def test_max_6_slots_per_day(self):
        many_slots = AvailabilityResponse(
            slots={
                "2026-01-06": [
                    TimeSlot(time=f"2026-01-06T{h:02d}:00:00.000+03:00")
                    for h in range(10, 20)  # 10 slots
                ],
            }
        )
        keyboard = build_availability_keyboard(many_slots.slots)
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        slot_buttons = [b for b in all_buttons if b.callback_data and b.callback_data.startswith("slot:")]
        assert len(slot_buttons) == 6

    def test_max_5_days_shown(self):
        many_days = AvailabilityResponse(
            slots={
                f"2026-01-{d:02d}": [TimeSlot(time=f"2026-01-{d:02d}T10:00:00.000+03:00")]
                for d in range(6, 14)  # 8 days
            }
        )
        keyboard = build_availability_keyboard(many_days.slots)
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        noop_buttons = [b for b in all_buttons if b.callback_data == "noop"]
        assert len(noop_buttons) == 5

    def test_sorts_slots_within_day(self):
        unsorted = AvailabilityResponse(
            slots={
                "2026-01-06": [
                    TimeSlot(time="2026-01-06T14:00:00.000+03:00"),
                    TimeSlot(time="2026-01-06T10:00:00.000+03:00"),
                    TimeSlot(time="2026-01-06T11:00:00.000+03:00"),
                ],
            }
        )
        keyboard = build_availability_keyboard(unsorted.slots)
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        slot_buttons = [
            b for b in all_buttons if b.callback_data and b.callback_data.startswith("slot:")
        ]
        assert [b.text for b in slot_buttons] == ["10:00", "11:00", "14:00"]


# ---------------------------------------------------------------------------
# Handler state transition tests
# ---------------------------------------------------------------------------


class TestBookCommand:
    @pytest.mark.asyncio
    async def test_returns_selecting_timezone(self, mock_update, mock_context):
        result = await book_command(mock_update, mock_context)
        assert result == BookingState.SELECTING_TIMEZONE

    @pytest.mark.asyncio
    async def test_sends_timezone_keyboard(self, mock_update, mock_context):
        await book_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        call_kwargs = mock_update.message.reply_text.call_args[1]
        assert "reply_markup" in call_kwargs


class TestSelectTimezone:
    @pytest.mark.asyncio
    async def test_stores_timezone_in_user_data(
        self, mock_update_with_query, mock_context, mock_calcom_client, availability_response
    ):
        mock_update_with_query.callback_query.data = "tz:Europe/Moscow"
        mock_calcom_client.get_availability.return_value = availability_response

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            await select_timezone(mock_update_with_query, mock_context)

        assert mock_context.user_data["timezone"] == "Europe/Moscow"

    @pytest.mark.asyncio
    async def test_returns_viewing_availability(
        self, mock_update_with_query, mock_context, mock_calcom_client, availability_response
    ):
        mock_update_with_query.callback_query.data = "tz:Europe/Moscow"
        mock_calcom_client.get_availability.return_value = availability_response

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            result = await select_timezone(mock_update_with_query, mock_context)

        assert result == BookingState.VIEWING_AVAILABILITY

    @pytest.mark.asyncio
    async def test_shows_loading_then_availability(
        self, mock_update_with_query, mock_context, mock_calcom_client, availability_response
    ):
        mock_update_with_query.callback_query.data = "tz:Europe/Moscow"
        mock_calcom_client.get_availability.return_value = availability_response

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            await select_timezone(mock_update_with_query, mock_context)

        # edit_message_text called twice: loading + availability
        assert mock_update_with_query.callback_query.edit_message_text.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_api_error_gracefully(
        self, mock_update_with_query, mock_context, mock_calcom_client
    ):
        mock_update_with_query.callback_query.data = "tz:Europe/Moscow"
        mock_calcom_client.get_availability.side_effect = CalComAPIError(500, "Server error")

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            result = await select_timezone(mock_update_with_query, mock_context)

        assert result == BookingState.VIEWING_AVAILABILITY
        # Error message shown
        last_call = mock_update_with_query.callback_query.edit_message_text.call_args[0][0]
        assert "извините" in last_call.lower() or "не удалось" in last_call.lower()


class TestSelectSlot:
    @pytest.mark.asyncio
    async def test_stores_date_and_time(self, mock_update_with_query, mock_context):
        time_iso = "2026-01-06T10:00:00.000+03:00"
        mock_update_with_query.callback_query.data = f"slot:2026-01-06:{time_iso}"

        await select_slot(mock_update_with_query, mock_context)

        assert mock_context.user_data["selected_date"] == "2026-01-06"
        assert mock_context.user_data["selected_time"] == time_iso

    @pytest.mark.asyncio
    async def test_returns_entering_name(self, mock_update_with_query, mock_context):
        time_iso = "2026-01-06T10:00:00.000+03:00"
        mock_update_with_query.callback_query.data = f"slot:2026-01-06:{time_iso}"

        result = await select_slot(mock_update_with_query, mock_context)

        assert result == BookingState.ENTERING_NAME

    @pytest.mark.asyncio
    async def test_prompts_for_name(self, mock_update_with_query, mock_context):
        time_iso = "2026-01-06T10:00:00.000+03:00"
        mock_update_with_query.callback_query.data = f"slot:2026-01-06:{time_iso}"

        await select_slot(mock_update_with_query, mock_context)

        mock_update_with_query.callback_query.edit_message_text.assert_called_once()
        prompt = mock_update_with_query.callback_query.edit_message_text.call_args[0][0]
        assert "имя" in prompt.lower()


class TestEnterName:
    @pytest.mark.asyncio
    async def test_stores_name(self, mock_update, mock_context):
        mock_update.message.text = "Alice Smith"

        await enter_name(mock_update, mock_context)

        assert mock_context.user_data["name"] == "Alice Smith"

    @pytest.mark.asyncio
    async def test_returns_email_decision(self, mock_update, mock_context):
        mock_update.message.text = "Alice Smith"

        result = await enter_name(mock_update, mock_context)

        assert result == BookingState.EMAIL_DECISION

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_name(self, mock_update, mock_context):
        mock_update.message.text = "  Alice Smith  "

        await enter_name(mock_update, mock_context)

        assert mock_context.user_data["name"] == "Alice Smith"

    @pytest.mark.asyncio
    async def test_asks_about_email(self, mock_update, mock_context):
        mock_update.message.text = "Alice"

        await enter_name(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_kwargs = mock_update.message.reply_text.call_args[1]
        assert "reply_markup" in call_kwargs

    @pytest.mark.asyncio
    async def test_rejects_empty_name(self, mock_update, mock_context):
        mock_update.message.text = "   "

        result = await enter_name(mock_update, mock_context)

        assert result == BookingState.ENTERING_NAME
        assert "name" not in mock_context.user_data
        mock_update.message.reply_text.assert_called_once()
        msg = mock_update.message.reply_text.call_args[0][0]
        assert "не может быть пустым" in msg.lower()

    @pytest.mark.asyncio
    async def test_rejects_too_long_name(self, mock_update, mock_context):
        mock_update.message.text = "A" * 101

        result = await enter_name(mock_update, mock_context)

        assert result == BookingState.ENTERING_NAME
        assert "name" not in mock_context.user_data
        mock_update.message.reply_text.assert_called_once()
        msg = mock_update.message.reply_text.call_args[0][0]
        assert "слишком длин" in msg.lower()


class TestEmailDecision:
    @pytest.mark.asyncio
    async def test_yes_returns_entering_email(self, mock_update_with_query, mock_context):
        mock_update_with_query.callback_query.data = "email_yes"

        result = await email_decision(mock_update_with_query, mock_context)

        assert result == BookingState.ENTERING_EMAIL

    @pytest.mark.asyncio
    async def test_no_stores_none_email(self, mock_update_with_query, mock_context):
        mock_update_with_query.callback_query.data = "email_no"
        mock_context.user_data = {
            "name": "Alice",
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
        }

        await email_decision(mock_update_with_query, mock_context)

        assert mock_context.user_data.get("email") is None

    @pytest.mark.asyncio
    async def test_no_returns_confirming(self, mock_update_with_query, mock_context):
        mock_update_with_query.callback_query.data = "email_no"
        mock_context.user_data = {
            "name": "Alice",
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
        }

        result = await email_decision(mock_update_with_query, mock_context)

        assert result == BookingState.CONFIRMING


class TestEnterEmail:
    @pytest.mark.asyncio
    async def test_stores_email(self, mock_update, mock_context):
        mock_update.message.text = "alice@example.com"
        mock_context.user_data = {
            "name": "Alice",
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
        }

        await enter_email(mock_update, mock_context)

        assert mock_context.user_data["email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_returns_confirming(self, mock_update, mock_context):
        mock_update.message.text = "alice@example.com"
        mock_context.user_data = {
            "name": "Alice",
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
        }

        result = await enter_email(mock_update, mock_context)

        assert result == BookingState.CONFIRMING

    @pytest.mark.asyncio
    async def test_shows_confirmation(self, mock_update, mock_context):
        mock_update.message.text = "alice@example.com"
        mock_context.user_data = {
            "name": "Alice",
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
        }

        await enter_email(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejects_invalid_email_no_at(self, mock_update, mock_context):
        mock_update.message.text = "notanemail"
        mock_context.user_data = {
            "name": "Alice",
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
        }

        result = await enter_email(mock_update, mock_context)

        assert result == BookingState.ENTERING_EMAIL
        assert "email" not in mock_context.user_data

    @pytest.mark.asyncio
    async def test_rejects_invalid_email_no_dot_in_domain(self, mock_update, mock_context):
        mock_update.message.text = "user@localhost"
        mock_context.user_data = {
            "name": "Alice",
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
        }

        result = await enter_email(mock_update, mock_context)

        assert result == BookingState.ENTERING_EMAIL

    @pytest.mark.asyncio
    async def test_invalid_email_shows_error_message(self, mock_update, mock_context):
        mock_update.message.text = "bad"
        mock_context.user_data = {
            "name": "Alice",
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
        }

        await enter_email(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        msg = mock_update.message.reply_text.call_args[0][0]
        assert "некорректный" in msg.lower() or "ещё раз" in msg.lower()


class TestConfirmBooking:
    @pytest.fixture
    def user_data_ready(self):
        return {
            "name": "Alice",
            "email": "alice@example.com",
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
        }

    @pytest.fixture
    def booking_response(self):
        return BookingResponse(
            id=1,
            uid="abc123",
            title="Meeting with Alice",
            start="2026-01-06T07:00:00Z",
            end="2026-01-06T08:00:00Z",
            status="accepted",
        )

    @pytest.mark.asyncio
    async def test_creates_booking_with_correct_data(
        self,
        mock_update_with_query,
        mock_context,
        mock_calcom_client,
        user_data_ready,
        booking_response,
    ):
        mock_update_with_query.callback_query.data = "confirm"
        mock_context.user_data = user_data_ready
        mock_calcom_client.create_booking.return_value = booking_response

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            await confirm_booking(mock_update_with_query, mock_context)

        mock_calcom_client.create_booking.assert_called_once()
        request = mock_calcom_client.create_booking.call_args[0][0]
        assert request.eventTypeId == 42
        assert request.attendee.name == "Alice"
        assert request.attendee.email == "alice@example.com"
        assert request.attendee.timeZone == "Europe/Moscow"
        assert "telegram_user_id" in request.metadata

    @pytest.mark.asyncio
    async def test_returns_conversation_end_on_success(
        self,
        mock_update_with_query,
        mock_context,
        mock_calcom_client,
        user_data_ready,
        booking_response,
    ):
        from telegram.ext import ConversationHandler

        mock_update_with_query.callback_query.data = "confirm"
        mock_context.user_data = user_data_ready
        mock_calcom_client.create_booking.return_value = booking_response

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            result = await confirm_booking(mock_update_with_query, mock_context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_shows_success_confirmation(
        self,
        mock_update_with_query,
        mock_context,
        mock_calcom_client,
        user_data_ready,
        booking_response,
    ):
        mock_update_with_query.callback_query.data = "confirm"
        mock_context.user_data = user_data_ready
        mock_calcom_client.create_booking.return_value = booking_response

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            await confirm_booking(mock_update_with_query, mock_context)

        final_message = mock_update_with_query.callback_query.edit_message_text.call_args[0][0]
        assert "подтверждена" in final_message.lower() or "готово" in final_message.lower()

    @pytest.mark.asyncio
    async def test_uses_placeholder_email_when_none(
        self,
        mock_update_with_query,
        mock_context,
        mock_calcom_client,
        booking_response,
    ):
        mock_update_with_query.callback_query.data = "confirm"
        mock_update_with_query.effective_user.id = 12345
        mock_context.user_data = {
            "name": "Alice",
            "email": None,
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
        }
        mock_calcom_client.create_booking.return_value = booking_response

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            await confirm_booking(mock_update_with_query, mock_context)

        request = mock_calcom_client.create_booking.call_args[0][0]
        assert "12345" in request.attendee.email
        assert "telecalbot.local" in request.attendee.email

    @pytest.mark.asyncio
    async def test_handles_409_conflict(
        self,
        mock_update_with_query,
        mock_context,
        mock_calcom_client,
        user_data_ready,
    ):
        mock_update_with_query.callback_query.data = "confirm"
        mock_context.user_data = user_data_ready
        mock_calcom_client.create_booking.side_effect = CalComAPIError(409, "Conflict")

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            result = await confirm_booking(mock_update_with_query, mock_context)

        assert result == BookingState.VIEWING_AVAILABILITY
        error_msg = mock_update_with_query.callback_query.edit_message_text.call_args[0][0]
        assert "занято" in error_msg.lower() or "другое" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_handles_generic_api_error(
        self,
        mock_update_with_query,
        mock_context,
        mock_calcom_client,
        user_data_ready,
    ):
        mock_update_with_query.callback_query.data = "confirm"
        mock_context.user_data = user_data_ready
        mock_calcom_client.create_booking.side_effect = CalComAPIError(500, "Server error")

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            result = await confirm_booking(mock_update_with_query, mock_context)

        assert result == BookingState.VIEWING_AVAILABILITY

    @pytest.mark.asyncio
    async def test_shows_dynamic_duration(
        self,
        mock_update_with_query,
        mock_context,
        mock_calcom_client,
        user_data_ready,
    ):
        mock_update_with_query.callback_query.data = "confirm"
        mock_context.user_data = user_data_ready
        # 30-minute booking
        mock_calcom_client.create_booking.return_value = BookingResponse(
            id=1,
            uid="abc123",
            title="Meeting",
            start="2026-01-06T07:00:00Z",
            end="2026-01-06T07:30:00Z",
            status="accepted",
        )

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            await confirm_booking(mock_update_with_query, mock_context)

        final_message = mock_update_with_query.callback_query.edit_message_text.call_args[0][0]
        assert "30 мин." in final_message

    @pytest.mark.asyncio
    async def test_shows_timezone_in_confirmation(
        self,
        mock_update_with_query,
        mock_context,
        mock_calcom_client,
        user_data_ready,
        booking_response,
    ):
        mock_update_with_query.callback_query.data = "confirm"
        mock_context.user_data = user_data_ready
        mock_calcom_client.create_booking.return_value = booking_response

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            await confirm_booking(mock_update_with_query, mock_context)

        final_message = mock_update_with_query.callback_query.edit_message_text.call_args[0][0]
        assert "Europe/Moscow" in final_message

    @pytest.mark.asyncio
    async def test_uses_russian_datetime_in_confirmation(
        self,
        mock_update_with_query,
        mock_context,
        mock_calcom_client,
        user_data_ready,
        booking_response,
    ):
        mock_update_with_query.callback_query.data = "confirm"
        mock_context.user_data = user_data_ready
        mock_calcom_client.create_booking.return_value = booking_response

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            await confirm_booking(mock_update_with_query, mock_context)

        final_message = mock_update_with_query.callback_query.edit_message_text.call_args[0][0]
        assert "Вторник" in final_message
        assert "янв" in final_message
        assert "в 10:00" in final_message


class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_via_callback(self, mock_update_with_query, mock_context):
        from telegram.ext import ConversationHandler

        mock_update_with_query.callback_query.data = "cancel"
        mock_context.user_data = {"name": "Alice", "timezone": "Europe/Moscow"}

        result = await cancel(mock_update_with_query, mock_context)

        assert result == ConversationHandler.END
        assert mock_context.user_data == {}

    @pytest.mark.asyncio
    async def test_cancel_via_command(self, mock_update, mock_context):
        from telegram.ext import ConversationHandler

        mock_update.callback_query = None
        mock_context.user_data = {"name": "Alice"}

        result = await cancel(mock_update, mock_context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_cancel_sends_message(self, mock_update_with_query, mock_context):
        mock_update_with_query.callback_query.data = "cancel"
        mock_context.user_data = {}

        await cancel(mock_update_with_query, mock_context)

        mock_update_with_query.callback_query.edit_message_text.assert_called_once()
        msg = mock_update_with_query.callback_query.edit_message_text.call_args[0][0]
        assert "отменена" in msg.lower()

    @pytest.mark.asyncio
    async def test_cancel_falls_back_to_reply_when_edit_not_allowed(
        self, mock_update_with_query, mock_context
    ):
        mock_update_with_query.callback_query.data = "cancel"
        mock_update_with_query.callback_query.edit_message_text.side_effect = (
            BadRequest("Message can't be edited")
        )

        await cancel(mock_update_with_query, mock_context)

        mock_update_with_query.callback_query.message.reply_text.assert_called_once()
        msg = mock_update_with_query.callback_query.message.reply_text.call_args[0][0]
        assert "отменена" in msg.lower()


class TestLoadMoreDates:
    @pytest.mark.asyncio
    async def test_stores_offset_and_calls_show_availability(
        self, mock_update_with_query, mock_context, mock_calcom_client, availability_response
    ):
        mock_update_with_query.callback_query.data = "dates:5"
        mock_context.user_data = {"timezone": "Europe/Moscow"}
        mock_calcom_client.get_availability.return_value = availability_response

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.calcom_event_type_id = 42
            result = await load_more_dates(mock_update_with_query, mock_context)

        assert mock_context.user_data["offset_days"] == 5
        assert result == BookingState.VIEWING_AVAILABILITY
        mock_calcom_client.get_availability.assert_called_once()


class TestChangeTimezone:
    @pytest.mark.asyncio
    async def test_returns_selecting_timezone(self, mock_update_with_query, mock_context):
        result = await change_timezone(mock_update_with_query, mock_context)

        assert result == BookingState.SELECTING_TIMEZONE

    @pytest.mark.asyncio
    async def test_shows_timezone_keyboard(self, mock_update_with_query, mock_context):
        await change_timezone(mock_update_with_query, mock_context)

        mock_update_with_query.callback_query.edit_message_text.assert_called_once()
        call_kwargs = mock_update_with_query.callback_query.edit_message_text.call_args[1]
        assert "reply_markup" in call_kwargs

    @pytest.mark.asyncio
    async def test_falls_back_to_reply_when_edit_not_allowed(
        self, mock_update_with_query, mock_context
    ):
        mock_update_with_query.callback_query.edit_message_text.side_effect = (
            BadRequest("Message can't be edited")
        )

        await change_timezone(mock_update_with_query, mock_context)

        mock_update_with_query.callback_query.message.reply_text.assert_called_once()
        call_kwargs = mock_update_with_query.callback_query.message.reply_text.call_args[1]
        assert "reply_markup" in call_kwargs


class TestNoop:
    @pytest.mark.asyncio
    async def test_returns_viewing_availability(self, mock_update_with_query, mock_context):
        result = await noop(mock_update_with_query, mock_context)

        assert result == BookingState.VIEWING_AVAILABILITY

    @pytest.mark.asyncio
    async def test_answers_query(self, mock_update_with_query, mock_context):
        await noop(mock_update_with_query, mock_context)

        mock_update_with_query.callback_query.answer.assert_called_once()


class TestFormatDuration:
    def test_one_hour(self):
        booking = BookingResponse(
            id=1, uid="x", title="T",
            start="2026-01-06T07:00:00Z",
            end="2026-01-06T08:00:00Z",
            status="accepted",
        )
        assert _format_duration(booking) == "1 ч."

    def test_two_hours(self):
        booking = BookingResponse(
            id=1, uid="x", title="T",
            start="2026-01-06T07:00:00Z",
            end="2026-01-06T09:00:00Z",
            status="accepted",
        )
        assert _format_duration(booking) == "2 ч."

    def test_30_minutes(self):
        booking = BookingResponse(
            id=1, uid="x", title="T",
            start="2026-01-06T07:00:00Z",
            end="2026-01-06T07:30:00Z",
            status="accepted",
        )
        assert _format_duration(booking) == "30 мин."

    def test_45_minutes(self):
        booking = BookingResponse(
            id=1, uid="x", title="T",
            start="2026-01-06T07:00:00Z",
            end="2026-01-06T07:45:00Z",
            status="accepted",
        )
        assert _format_duration(booking) == "45 мин."
