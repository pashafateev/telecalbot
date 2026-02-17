"""Tests for the duration selection step in the booking flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
            result = await select_duration(mock_update_with_query, mock_context)

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
            result = await select_duration(mock_update_with_query, mock_context)

        assert mock_context.user_data["duration"] == 60

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
