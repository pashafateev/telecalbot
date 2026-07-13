"""Tests for the duration selection step in the booking flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.handlers import booking as booking_handler
from app.handlers.booking import (
    BookingState,
    select_duration,
    select_timezone,
)
from app.services.duration_limit import DurationLimitService


@pytest.fixture
def mock_update_with_query():
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.from_user = MagicMock()
    update.callback_query.from_user.id = 12345
    update.callback_query.message = MagicMock()
    update.callback_query.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.user_data = {}
    context.bot_data = {}
    return context


class TestDurationSelection:
    """Tests for the duration picker step."""

    @pytest.mark.asyncio
    async def test_select_duration_stores_duration(self, mock_update_with_query, mock_context):
        mock_update_with_query.callback_query.data = "duration:30"
        mock_calcom = AsyncMock()
        mock_calcom.get_availability = AsyncMock(return_value=MagicMock(slots={}))
        mock_context.bot_data = {"calcom_client": mock_calcom}
        mock_context.user_data = {"timezone": "Europe/Moscow", "offset_days": 0}

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.get_event_type_id = MagicMock(return_value=42)
            await select_duration(mock_update_with_query, mock_context)

        assert mock_context.user_data["duration"] == 30

    @pytest.mark.asyncio
    async def test_select_duration_60(self, mock_update_with_query, mock_context):
        mock_update_with_query.callback_query.data = "duration:60"
        mock_calcom = AsyncMock()
        mock_calcom.get_availability = AsyncMock(return_value=MagicMock(slots={}))
        mock_context.bot_data = {"calcom_client": mock_calcom}
        mock_context.user_data = {"timezone": "Europe/Moscow", "offset_days": 0}

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.get_event_type_id = MagicMock(return_value=99)
            await select_duration(mock_update_with_query, mock_context)

        assert mock_context.user_data["duration"] == 60

    @pytest.mark.asyncio
    async def test_select_duration_120_requires_fifth_step_acknowledgement(
        self, mock_update_with_query, mock_context
    ):
        mock_update_with_query.callback_query.data = "duration:120"
        mock_calcom = AsyncMock()
        mock_context.bot_data = {"calcom_client": mock_calcom}
        mock_context.user_data = {"timezone": "Europe/Moscow", "offset_days": 0}

        result = await select_duration(mock_update_with_query, mock_context)

        assert result == BookingState.SELECTING_DURATION
        assert mock_context.user_data["pending_duration"] == 120
        mock_calcom.get_availability.assert_not_called()
        warning_call = mock_update_with_query.callback_query.edit_message_text.call_args
        warning_text = warning_call.args[0]
        assert "двухчасовые встречи" in warning_text
        assert "5-му шагу" in warning_text
        button_texts = [
            button.text
            for row in warning_call.kwargs["reply_markup"].inline_keyboard
            for button in row
        ]
        assert button_texts == ["Продолжить (5-й шаг)", "Изменить длительность"]

    @pytest.mark.asyncio
    async def test_select_duration_caps_stale_callback_for_limited_user(
        self, mock_update_with_query, mock_context
    ):
        mock_update_with_query.callback_query.data = "duration:60"
        mock_calcom = AsyncMock()
        mock_calcom.get_availability = AsyncMock(return_value=MagicMock(slots={}))
        mock_duration_service = MagicMock(spec=DurationLimitService)
        mock_duration_service.get_limit.return_value = 30
        mock_context.bot_data = {
            "calcom_client": mock_calcom,
            "duration_limit_service": mock_duration_service,
        }
        mock_context.user_data = {"timezone": "Europe/Moscow", "offset_days": 0}

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.get_event_type_id = MagicMock(side_effect=lambda duration: duration)
            await select_duration(mock_update_with_query, mock_context)

        assert mock_context.user_data["duration"] == 30
        mock_settings.get_event_type_id.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_select_duration_proceeds_to_availability(self, mock_update_with_query, mock_context):
        mock_update_with_query.callback_query.data = "duration:30"
        mock_calcom = AsyncMock()
        mock_calcom.get_availability = AsyncMock(return_value=MagicMock(slots={}))
        mock_context.bot_data = {"calcom_client": mock_calcom}
        mock_context.user_data = {"timezone": "Europe/Moscow", "offset_days": 0}

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.get_event_type_id = MagicMock(return_value=42)
            result = await select_duration(mock_update_with_query, mock_context)

        assert result == BookingState.VIEWING_AVAILABILITY

    @pytest.mark.asyncio
    async def test_missing_event_mapping_shows_availability_error(
        self, mock_update_with_query, mock_context
    ):
        mock_update_with_query.callback_query.data = "duration:30"
        mock_calcom = AsyncMock()
        mock_context.bot_data = {"calcom_client": mock_calcom}
        mock_context.user_data = {"timezone": "Europe/Moscow", "offset_days": 0}

        with patch("app.handlers.booking.settings") as mock_settings:
            error = ValueError("No event type ID configured")
            mock_settings.get_event_type_id.side_effect = error
            mock_settings.resolve_event_type.side_effect = error
            result = await select_duration(mock_update_with_query, mock_context)

        assert result == BookingState.VIEWING_AVAILABILITY
        mock_calcom.get_availability.assert_not_called()
        message = mock_update_with_query.callback_query.edit_message_text.call_args.args[0]
        assert "не удалось загрузить расписание" in message


class TestFifthStepAcknowledgement:
    @pytest.mark.asyncio
    async def test_acknowledgement_fetches_120_minute_availability(
        self, mock_update_with_query, mock_context
    ):
        mock_update_with_query.callback_query.data = "duration_120_confirm"
        mock_calcom = AsyncMock()
        mock_calcom.get_availability.return_value = MagicMock(slots={})
        mock_context.bot_data = {"calcom_client": mock_calcom}
        mock_context.user_data = {
            "timezone": "Europe/Moscow",
            "offset_days": 0,
            "pending_duration": 120,
        }

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.get_event_type_id.return_value = 42
            result = await booking_handler.acknowledge_fifth_step_duration(
                mock_update_with_query, mock_context
            )

        assert result == BookingState.VIEWING_AVAILABILITY
        assert mock_context.user_data["duration"] == 120
        assert "pending_duration" not in mock_context.user_data
        assert mock_calcom.get_availability.call_args.kwargs["duration_minutes"] == 120

    @pytest.mark.asyncio
    async def test_acknowledgement_reapplies_a_lowered_duration_limit(
        self, mock_update_with_query, mock_context
    ):
        mock_update_with_query.callback_query.data = "duration_120_confirm"
        mock_calcom = AsyncMock()
        mock_calcom.get_availability.return_value = MagicMock(slots={})
        mock_duration_service = MagicMock(spec=DurationLimitService)
        mock_duration_service.get_limit.return_value = 60
        mock_context.bot_data = {
            "calcom_client": mock_calcom,
            "duration_limit_service": mock_duration_service,
        }
        mock_context.user_data = {
            "timezone": "Europe/Moscow",
            "offset_days": 0,
            "pending_duration": 120,
        }

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.get_event_type_id.side_effect = lambda duration: duration
            await booking_handler.acknowledge_fifth_step_duration(
                mock_update_with_query, mock_context
            )

        assert mock_context.user_data["duration"] == 60
        assert mock_calcom.get_availability.call_args.kwargs["duration_minutes"] == 60

    @pytest.mark.asyncio
    async def test_change_duration_returns_to_all_allowed_options(
        self, mock_update_with_query, mock_context
    ):
        mock_update_with_query.callback_query.data = "change_duration"
        mock_duration_service = MagicMock(spec=DurationLimitService)
        mock_duration_service.get_limit.return_value = 120
        mock_context.bot_data = {"duration_limit_service": mock_duration_service}
        mock_context.user_data = {"pending_duration": 120}

        result = await booking_handler.change_duration(
            mock_update_with_query, mock_context
        )

        assert result == BookingState.SELECTING_DURATION
        assert "pending_duration" not in mock_context.user_data
        call = mock_update_with_query.callback_query.edit_message_text.call_args
        button_texts = [
            button.text
            for row in call.kwargs["reply_markup"].inline_keyboard
            for button in row
        ]
        assert button_texts == ["30 минут", "60 минут", "120 минут", "Отмена"]

    @pytest.mark.asyncio
    async def test_stale_acknowledgement_without_pending_duration_returns_to_picker(
        self, mock_update_with_query, mock_context
    ):
        mock_update_with_query.callback_query.data = "duration_120_confirm"
        mock_context.user_data = {"timezone": "Europe/Moscow"}

        result = await booking_handler.acknowledge_fifth_step_duration(
            mock_update_with_query, mock_context
        )

        assert result == BookingState.SELECTING_DURATION
        call_text = mock_update_with_query.callback_query.edit_message_text.call_args.args[0]
        assert "длительность" in call_text.lower()


class TestSelectDurationValidation:
    """Tests for invalid callback data in duration selection."""

    @pytest.mark.asyncio
    async def test_rejects_invalid_duration(self, mock_update_with_query, mock_context):
        mock_update_with_query.callback_query.data = "duration:999"
        result = await select_duration(mock_update_with_query, mock_context)
        assert result == BookingState.SELECTING_DURATION
        assert "duration" not in mock_context.user_data

    @pytest.mark.asyncio
    async def test_rejects_non_numeric_duration(self, mock_update_with_query, mock_context):
        mock_update_with_query.callback_query.data = "duration:abc"
        result = await select_duration(mock_update_with_query, mock_context)
        assert result == BookingState.SELECTING_DURATION

    @pytest.mark.asyncio
    async def test_rejects_malformed_data(self, mock_update_with_query, mock_context):
        mock_update_with_query.callback_query.data = "duration:"
        result = await select_duration(mock_update_with_query, mock_context)
        assert result == BookingState.SELECTING_DURATION


class TestDurationLimitAutoSelect:
    """Tests for auto-selection when user has a duration limit."""

    @pytest.mark.asyncio
    async def test_limited_user_skips_picker(self, mock_update_with_query, mock_context):
        """User with a limit should skip duration picker and go to availability."""
        mock_update_with_query.callback_query.data = "tz:Europe/Moscow"
        mock_calcom = AsyncMock()
        mock_calcom.get_availability = AsyncMock(return_value=MagicMock(slots={}))

        mock_duration_service = MagicMock(spec=DurationLimitService)
        mock_duration_service.get_limit.return_value = 30

        mock_context.bot_data = {
            "calcom_client": mock_calcom,
            "duration_limit_service": mock_duration_service,
        }

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.get_event_type_id = MagicMock(return_value=42)
            result = await select_timezone(mock_update_with_query, mock_context)

        assert result == BookingState.VIEWING_AVAILABILITY
        assert mock_context.user_data["duration"] == 30

    @pytest.mark.asyncio
    async def test_limited_user_auto_select_clears_pending_duration(
        self, mock_update_with_query, mock_context
    ):
        mock_update_with_query.callback_query.data = "tz:Europe/Moscow"
        mock_calcom = AsyncMock()
        mock_calcom.get_availability.return_value = MagicMock(slots={})
        mock_duration_service = MagicMock(spec=DurationLimitService)
        mock_duration_service.get_limit.return_value = 60
        mock_context.bot_data = {
            "calcom_client": mock_calcom,
            "duration_limit_service": mock_duration_service,
        }
        mock_context.user_data = {"pending_duration": 120}

        with patch("app.handlers.booking.settings") as mock_settings:
            mock_settings.get_event_type_id.return_value = 42
            await select_timezone(mock_update_with_query, mock_context)

        assert "pending_duration" not in mock_context.user_data

    @pytest.mark.asyncio
    async def test_120_minute_limit_requires_fifth_step_acknowledgement(
        self, mock_update_with_query, mock_context
    ):
        mock_update_with_query.callback_query.data = "tz:Europe/Moscow"
        mock_calcom = AsyncMock()
        mock_duration_service = MagicMock(spec=DurationLimitService)
        mock_duration_service.get_limit.return_value = 120
        mock_context.bot_data = {
            "calcom_client": mock_calcom,
            "duration_limit_service": mock_duration_service,
        }

        result = await select_timezone(mock_update_with_query, mock_context)

        assert result == BookingState.SELECTING_DURATION
        assert mock_context.user_data["pending_duration"] == 120
        mock_calcom.get_availability.assert_not_called()

    @pytest.mark.asyncio
    async def test_unlimited_user_sees_picker(self, mock_update_with_query, mock_context):
        """User without a limit should see the duration picker."""
        mock_update_with_query.callback_query.data = "tz:Europe/Moscow"

        mock_duration_service = MagicMock(spec=DurationLimitService)
        mock_duration_service.get_limit.return_value = None

        mock_context.bot_data = {
            "duration_limit_service": mock_duration_service,
        }

        result = await select_timezone(mock_update_with_query, mock_context)

        assert result == BookingState.SELECTING_DURATION

    @pytest.mark.asyncio
    async def test_no_service_shows_picker(self, mock_update_with_query, mock_context):
        """When no duration limit service exists, show the picker."""
        mock_update_with_query.callback_query.data = "tz:Europe/Moscow"
        mock_context.bot_data = {}

        result = await select_timezone(mock_update_with_query, mock_context)

        assert result == BookingState.SELECTING_DURATION


class TestDurationInConfirmation:
    """Test that duration is displayed in booking confirmation text."""

    def test_confirmation_text_includes_duration(self):
        from app.handlers.booking import _build_confirmation_text

        data = {
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
            "name": "Alice",
            "email": "alice@example.com",
            "duration": 60,
        }
        text = _build_confirmation_text(data)
        assert "60 минут" in text

    def test_confirmation_text_30min(self):
        from app.handlers.booking import _build_confirmation_text

        data = {
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
            "name": "Bob",
            "duration": 30,
        }
        text = _build_confirmation_text(data)
        assert "30 минут" in text
        assert "только для работы по 5-му шагу" not in text

    def test_confirmation_text_repeats_fifth_step_warning_for_120_minutes(self):
        from app.handlers.booking import _build_confirmation_text

        data = {
            "selected_date": "2026-01-06",
            "selected_time": "2026-01-06T10:00:00.000+03:00",
            "timezone": "Europe/Moscow",
            "name": "Alice",
            "duration": 120,
        }

        text = _build_confirmation_text(data)

        assert "120 минут" in text
        assert "только для работы по 5-му шагу" in text


def test_duration_state_registers_fifth_step_warning_callbacks():
    handler = booking_handler.create_booking_conversation_handler()
    callbacks = {
        callback.callback
        for callback in handler.states[BookingState.SELECTING_DURATION]
    }

    assert booking_handler.acknowledge_fifth_step_duration in callbacks
    assert booking_handler.change_duration in callbacks
