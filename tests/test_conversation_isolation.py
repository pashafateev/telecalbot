"""Application-level regressions for overlapping user conversations."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Chat, Message, MessageEntity, Update, User
from telegram.ext import MessageHandler, filters

from app.handlers.booking import BookingState, create_booking_conversation_handler
from app.handlers.privacy import PrivacyState, create_privacy_conversation_handler
from app.services.user_preferences import UserPreferenceService


def _message_update(application, update_id: int, text: str) -> Update:
    user = User(id=12345, first_name="Test", is_bot=False)
    chat = Chat(id=12345, type=Chat.PRIVATE)
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
        chat=chat,
        from_user=user,
        text=text,
        entities=entities,
    )
    message.set_bot(application.bot)
    return Update(update_id=update_id, message=message)


@pytest.mark.asyncio
async def test_booking_name_wins_over_abandoned_privacy_name_input(
    monkeypatch,
    temp_db_path,
):
    from telegram.ext import Application

    from app.database import Database
    from app.database.migrations import initialize_schema
    from app.handlers.privacy import invalidate_pending_privacy_input

    application = Application.builder().token("123456:test-token").build()
    application._initialized = True
    application.bot._initialized = True
    application.bot._bot_user = User(
        id=999,
        first_name="Telecalbot",
        is_bot=True,
        username="telecalbot_test_bot",
    )
    monkeypatch.setattr(application.bot, "send_message", AsyncMock())

    db = Database(temp_db_path)
    initialize_schema(db)
    profile_service = UserPreferenceService(db)
    whitelist_service = MagicMock()
    whitelist_service.is_whitelisted.return_value = True
    application.bot_data.update(
        {
            "user_preference_service": profile_service,
            "whitelist_service": whitelist_service,
            "duration_limit_service": MagicMock(),
        }
    )

    booking = create_booking_conversation_handler()
    privacy = create_privacy_conversation_handler()
    application.add_handler(
        MessageHandler(filters.COMMAND, invalidate_pending_privacy_input),
        group=-1,
    )
    application.add_handler(booking)
    application.add_handler(privacy)

    conversation_key = (12345, 12345)
    privacy._conversations[conversation_key] = PrivacyState.ENTERING_NAME
    application.user_data[12345]["privacy_pending_input"] = "name"

    await application.process_update(_message_update(application, 1, "/book"))
    booking._conversations[conversation_key] = BookingState.ENTERING_NAME
    await application.process_update(_message_update(application, 2, "Booking Name"))

    assert application.user_data[12345]["name"] == "Booking Name"
    assert profile_service.get_profile(12345) is None
