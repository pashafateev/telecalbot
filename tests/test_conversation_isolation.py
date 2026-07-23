"""Application-level regressions for switching between user conversations."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import (
    CallbackQuery,
    Chat,
    Message,
    MessageEntity,
    Update,
    User,
)
from telegram.ext import Application, MessageHandler, filters

from app.database import Database
from app.database.migrations import initialize_schema
from app.handlers.booking import BookingState
from app.handlers.privacy import (
    PrivacyState,
    invalidate_pending_privacy_input,
)
from app.services.user_preferences import UserPreferenceService


def _user() -> User:
    return User(id=12345, first_name="Test", is_bot=False)


def _chat() -> Chat:
    return Chat(id=12345, type=Chat.PRIVATE)


def _message_update(application, update_id: int, text: str) -> Update:
    entities = None
    if text.startswith("/"):
        entities = [
            MessageEntity(
                type=MessageEntity.BOT_COMMAND,
                offset=0,
                length=len(text.split()[0]),
            )
        ]
    message = Message(
        message_id=update_id,
        date=datetime.now(timezone.utc),
        chat=_chat(),
        from_user=_user(),
        text=text,
        entities=entities,
    )
    message.set_bot(application.bot)
    return Update(update_id=update_id, message=message)


def _callback_update(application, update_id: int, data: str) -> Update:
    message = Message(
        message_id=update_id,
        date=datetime.now(timezone.utc),
        chat=_chat(),
        from_user=application.bot._bot_user,
        text="privacy",
    )
    message.set_bot(application.bot)
    query = CallbackQuery(
        id=f"callback-{update_id}",
        from_user=_user(),
        chat_instance="test-chat",
        message=message,
        data=data,
    )
    query.set_bot(application.bot)
    return Update(update_id=update_id, callback_query=query)


def _application(monkeypatch, temp_db_path):
    from app.handlers.user_conversation import (
        create_user_conversation_handler,
    )

    application = Application.builder().token("123456:test-token").build()
    application._initialized = True
    application.bot._initialized = True
    application.bot._bot_user = User(
        id=999,
        first_name="Telecalbot",
        is_bot=True,
        username="telecalbot_test_bot",
    )
    monkeypatch.setattr(application.bot.__class__, "send_message", AsyncMock())
    monkeypatch.setattr(
        application.bot.__class__,
        "answer_callback_query",
        AsyncMock(),
    )
    monkeypatch.setattr(
        application.bot.__class__,
        "edit_message_text",
        AsyncMock(),
    )

    db = Database(temp_db_path)
    initialize_schema(db)
    profile_service = UserPreferenceService(db)
    whitelist_service = MagicMock()
    whitelist_service.is_whitelisted.return_value = True
    duration_limit_service = MagicMock()
    duration_limit_service.get_limit.return_value = None
    application.bot_data.update(
        {
            "user_preference_service": profile_service,
            "whitelist_service": whitelist_service,
            "duration_limit_service": duration_limit_service,
        }
    )

    conversation = create_user_conversation_handler()
    application.add_handler(
        MessageHandler(
            filters.COMMAND,
            invalidate_pending_privacy_input,
        ),
        group=-1,
    )
    application.add_handler(conversation)
    return application, conversation, profile_service


@pytest.mark.asyncio
async def test_book_replaces_abandoned_privacy_name_input(
    monkeypatch,
    temp_db_path,
):
    application, conversation, profile_service = _application(
        monkeypatch,
        temp_db_path,
    )
    key = (12345, 12345)

    await application.process_update(
        _message_update(application, 1, "/privacy")
    )
    await application.process_update(
        _callback_update(application, 2, "privacy:edit_name")
    )
    assert conversation._conversations[key] == PrivacyState.ENTERING_NAME

    await application.process_update(_message_update(application, 3, "/book"))
    conversation._conversations[key] = BookingState.ENTERING_NAME
    await application.process_update(
        _message_update(application, 4, "Booking Name")
    )

    assert application.user_data[12345]["name"] == "Booking Name"
    assert profile_service.get_profile(12345) is None


@pytest.mark.asyncio
async def test_privacy_replaces_booking_and_receives_its_name_input(
    monkeypatch,
    temp_db_path,
):
    application, conversation, profile_service = _application(
        monkeypatch,
        temp_db_path,
    )
    key = (12345, 12345)

    await application.process_update(_message_update(application, 1, "/book"))
    conversation._conversations[key] = BookingState.ENTERING_NAME
    application.user_data[12345]["selected_date"] = "2026-01-06"

    await application.process_update(
        _message_update(application, 2, "/privacy")
    )
    await application.process_update(
        _callback_update(application, 3, "privacy:edit_name")
    )
    await application.process_update(
        _message_update(application, 4, "Privacy Name")
    )

    profile = profile_service.get_profile(12345)
    assert profile is not None
    assert profile.preferred_name == "Privacy Name"
    assert "selected_date" not in application.user_data[12345]
