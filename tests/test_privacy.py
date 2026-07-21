"""Tests for the reversible /privacy booking-profile flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app import handlers
from app.database import Database
from app.database.migrations import initialize_schema
from app.services.user_preferences import UserPreferenceService


@pytest.fixture
def profile_service(temp_db_path):
    db = Database(temp_db_path)
    initialize_schema(db)
    return UserPreferenceService(db)


def _context(profile_service, *, whitelisted=False):
    context = MagicMock()
    context.user_data = {}
    context.bot_data = {
        "user_preference_service": profile_service,
        "whitelist_service": MagicMock(),
    }
    context.bot_data["whitelist_service"].is_whitelisted.return_value = whitelisted
    return context


def _message_update(text="/privacy", user_id=12345):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.text = text
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


@pytest.mark.asyncio
async def test_privacy_displays_masked_profile_without_whitelist_access(profile_service):
    profile_service.save_preferred_name(12345, "Alice")
    profile_service.save_timezone(12345, "Europe/Moscow")
    profile_service.save_email(12345, "alice@example.com")
    context = _context(profile_service, whitelisted=False)
    update = _message_update()

    await handlers.privacy_command(update, context)

    response = update.message.reply_text.call_args.args[0]
    assert "Alice" in response
    assert "Europe/Moscow" in response
    assert "a***@example.com" in response
    assert "alice@example.com" not in response
    assert "не отменяет" in response.lower()
    assert "telegram" in response.lower()
    context.bot_data["whitelist_service"].is_whitelisted.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected"),
    [("private", "без личного email"), ("ask", "спрашивать каждый раз")],
)
async def test_privacy_displays_private_and_ask_email_modes(
    profile_service, mode, expected
):
    profile_service.save_preferred_name(12345, "Alice")
    if mode == "private":
        profile_service.save_private_email_mode(12345)
    context = _context(profile_service)
    update = _message_update()

    await handlers.privacy_command(update, context)

    assert expected in update.message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_privacy_callbacks_are_opaque(profile_service):
    profile_service.save_preferred_name(12345, "Alice")
    profile_service.save_timezone(12345, "Europe/Moscow")
    profile_service.save_email(12345, "alice@example.com")
    context = _context(profile_service)
    update = _message_update()

    await handlers.privacy_command(update, context)

    keyboard = update.message.reply_text.call_args.kwargs["reply_markup"]
    callbacks = [
        button.callback_data for row in keyboard.inline_keyboard for button in row
    ]
    serialized = " ".join(callbacks)
    assert "Alice" not in serialized
    assert "Europe/Moscow" not in serialized
    assert "alice@example.com" not in serialized
    assert set(callbacks) >= {
        "privacy:edit_name",
        "privacy:forget_name",
        "privacy:edit_timezone",
        "privacy:forget_timezone",
        "privacy:edit_email",
        "privacy:private_email",
        "privacy:ask_email",
        "privacy:delete_confirm",
    }


@pytest.mark.asyncio
async def test_privacy_forgets_one_field_without_removing_others(profile_service):
    profile_service.save_preferred_name(12345, "Alice")
    profile_service.save_timezone(12345, "Europe/Moscow")
    profile_service.save_private_email_mode(12345)
    context = _context(profile_service)
    update = _callback_update("privacy:forget_name")

    await handlers.privacy_callback(update, context)

    profile = profile_service.get_profile(12345)
    assert profile is not None
    assert profile.preferred_name is None
    assert profile.timezone == "Europe/Moscow"
    assert profile.email_mode == "private"


@pytest.mark.asyncio
async def test_privacy_deletes_complete_profile_for_non_whitelisted_user(
    profile_service,
):
    profile_service.save_preferred_name(12345, "Alice")
    profile_service.save_timezone(12345, "Europe/Moscow")
    profile_service.save_email(12345, "alice@example.com")
    context = _context(profile_service, whitelisted=False)
    update = _callback_update("privacy:delete_profile")

    result = await handlers.privacy_callback(update, context)

    assert result == handlers.PrivacyState.END
    assert profile_service.get_profile(12345) is None
    response = update.callback_query.edit_message_text.call_args.args[0]
    assert "удален" in response.lower()
    assert "не отмен" in response.lower()
    context.bot_data["whitelist_service"].is_whitelisted.assert_not_called()


@pytest.mark.asyncio
async def test_privacy_changes_name_timezone_and_email(profile_service):
    profile_service.save_private_email_mode(12345)
    context = _context(profile_service)

    name_update = _message_update("New Name")
    assert (
        await handlers.privacy_enter_name(name_update, context)
        == handlers.PrivacyState.END
    )

    timezone_update = _callback_update("privacy_tz:3")
    assert (
        await handlers.privacy_select_timezone(timezone_update, context)
        == handlers.PrivacyState.END
    )

    email_update = _message_update("new@example.com")
    assert (
        await handlers.privacy_enter_email(email_update, context)
        == handlers.PrivacyState.END
    )

    profile = profile_service.get_profile(12345)
    assert profile is not None
    assert profile.preferred_name == "New Name"
    assert profile.timezone == "Asia/Yekaterinburg"
    assert profile.email_mode == "saved"
    assert profile.email == "new@example.com"


def test_privacy_conversation_registers_command_and_edit_states():
    conversation = handlers.create_privacy_conversation_handler()

    assert conversation.entry_points[0].commands == frozenset({"privacy"})
    assert handlers.PrivacyState.ENTERING_NAME in conversation.states
    assert handlers.PrivacyState.SELECTING_TIMEZONE in conversation.states
    assert handlers.PrivacyState.ENTERING_EMAIL in conversation.states
