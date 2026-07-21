"""Consent-aware booking profile regressions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database import Database
from app.database.migrations import initialize_schema
from app.handlers import booking
from app.services.user_preferences import UserPreferenceService


def _context(*, profile_service=None):
    context = MagicMock()
    context.user_data = {}
    context.job_queue = None
    context.bot_data = {
        "whitelist_service": MagicMock(),
        "calcom_client": AsyncMock(),
    }
    context.bot_data["whitelist_service"].is_whitelisted.return_value = True
    if profile_service is not None:
        context.bot_data["user_preference_service"] = profile_service
    return context


def _message_update(user_id=12345):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


def _callback_update(data, user_id=12345):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = None
    update.callback_query = AsyncMock()
    update.callback_query.data = data
    update.callback_query.from_user.id = user_id
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message = AsyncMock()
    return update


def _ready_booking_data(**overrides):
    data = {
        "name": "Alice",
        "email": "alice@example.com",
        "email_mode": "saved",
        "selected_date": "2026-01-06",
        "selected_time": "2026-01-06T10:00:00.000+03:00",
        "timezone": "Europe/Moscow",
        "duration": 30,
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_selecting_timezone_is_booking_scoped_until_remembered():
    profile_service = MagicMock()
    context = _context(profile_service=profile_service)
    update = _callback_update("tz:1")

    result = await booking.select_timezone(update, context)

    assert result == booking.BookingState.SELECTING_DURATION
    assert context.user_data["timezone"] == "Europe/Moscow"
    profile_service.save_timezone.assert_not_called()
    profile_service.set_timezone.assert_not_called()


def test_timezone_callbacks_are_opaque_and_contain_no_profile_values():
    keyboard = booking.build_timezone_keyboard()
    callback_data = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data != "cancel"
    ]

    assert callback_data == [f"tz:{index}" for index in range(11)]
    assert not any("/" in value for value in callback_data)


@pytest.mark.asyncio
async def test_remembered_profile_is_reused_after_service_restart(temp_db_path):
    db = Database(temp_db_path)
    initialize_schema(db)
    first_service = UserPreferenceService(db)
    first_service.save_preferred_name(12345, "Alice")
    first_service.save_timezone(12345, "Europe/Moscow")
    first_service.save_email(12345, "alice@example.com")

    restarted_service = UserPreferenceService(db)
    context = _context(profile_service=restarted_service)
    update = _message_update()

    result = await booking.book_command(update, context)

    assert result == booking.BookingState.SELECTING_DURATION
    assert context.user_data["name"] == "Alice"
    assert context.user_data["timezone"] == "Europe/Moscow"
    assert context.user_data["email"] == "alice@example.com"
    assert context.user_data["email_mode"] == "saved"
    message = update.message.reply_text.call_args.args[0]
    assert "Alice" in message
    assert "Europe/Moscow" in message
    assert "сохран" in message.lower()


@pytest.mark.asyncio
async def test_saved_name_and_email_skip_repeated_prompts_after_slot():
    context = _context()
    context.user_data = _ready_booking_data()
    update = _callback_update("slot:2026-01-06:2026-01-06T10:00:00.000+03:00")

    result = await booking.select_slot(update, context)

    assert result == booking.BookingState.REMEMBERING_PROFILE
    message = update.callback_query.edit_message_text.call_args.args[0]
    assert "сохран" in message.lower()
    assert "имя" in message.lower()
    assert "email" in message.lower()


@pytest.mark.asyncio
async def test_private_email_choice_opens_granular_remembering_screen():
    context = _context()
    context.user_data = _ready_booking_data(email=None, email_mode="private")
    update = _callback_update("email_no")

    result = await booking.email_decision(update, context)

    assert result == booking.BookingState.REMEMBERING_PROFILE
    keyboard = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
    callbacks = {button.callback_data for row in keyboard.inline_keyboard for button in row}
    assert callbacks == {
        "remember:name",
        "remember:timezone",
        "remember:private",
        "remember:save",
        "remember:none",
    }


@pytest.mark.asyncio
async def test_remembering_saves_only_explicitly_selected_fields():
    profile_service = MagicMock()
    context = _context(profile_service=profile_service)
    context.user_data = _ready_booking_data()
    update = _callback_update("remember:name")

    await booking.remember_profile_choice(update, context)
    update.callback_query.data = "remember:timezone"
    await booking.remember_profile_choice(update, context)
    update.callback_query.data = "remember:save"
    result = await booking.remember_profile_choice(update, context)

    assert result == booking.BookingState.CONFIRMING
    profile_service.save_preferred_name.assert_called_once_with(12345, "Alice")
    profile_service.save_timezone.assert_called_once_with(12345, "Europe/Moscow")
    profile_service.save_email.assert_not_called()
    profile_service.save_private_email_mode.assert_not_called()


@pytest.mark.asyncio
async def test_save_nothing_keeps_values_transient_and_shows_confirmation():
    profile_service = MagicMock()
    context = _context(profile_service=profile_service)
    context.user_data = _ready_booking_data()
    update = _callback_update("remember:none")

    result = await booking.remember_profile_choice(update, context)

    assert result == booking.BookingState.CONFIRMING
    assert profile_service.mock_calls == []
    message = update.callback_query.edit_message_text.call_args.args[0]
    assert "Alice" in message
    assert "alice@example.com" in message
    keyboard = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
    assert any(
        button.text == "Изменить данные" and button.callback_data == "edit:data"
        for row in keyboard.inline_keyboard
        for button in row
    )


def test_confirmation_always_shows_effective_private_booking_details():
    text = booking._build_confirmation_text(_ready_booking_data(email=None, email_mode="private"))

    assert "Alice" in text
    assert "Europe/Moscow" in text
    assert "Email: без личного email" in text


@pytest.mark.asyncio
async def test_change_controls_use_opaque_callbacks():
    context = _context()
    context.user_data = _ready_booking_data()
    update = _callback_update("edit:data")

    result = await booking.edit_booking_data(update, context)

    assert result == booking.BookingState.CONFIRMING
    keyboard = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
    callbacks = {button.callback_data for row in keyboard.inline_keyboard for button in row}
    assert callbacks == {
        "edit:name",
        "edit:timezone",
        "edit:email",
        "edit:private",
        "edit:back",
    }
    serialized = " ".join(callbacks)
    assert "Alice" not in serialized
    assert "Europe/Moscow" not in serialized
    assert "alice@example.com" not in serialized
