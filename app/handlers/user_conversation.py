"""Mutually exclusive routing for booking and privacy conversations."""

import asyncio
import logging
from datetime import timedelta

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from app.config import settings
from app.handlers.booking import (
    ACTIVE_USER_CONVERSATION_KEY,
    BOOKING_CONVERSATION_NAME,
    _cancel_booking_timeout_reminder,
    _clear_booking_scoped_state,
    book_command,
    booking_timeout,
    booking_timeout_is_premature,
    create_booking_conversation_handler,
)
from app.handlers.booking import (
    cancel as cancel_booking,
)
from app.handlers.privacy import (
    create_privacy_conversation_handler,
    invalidate_pending_privacy_input,
    privacy_cancel,
    privacy_command,
    privacy_timeout,
)

logger = logging.getLogger(__name__)

BOOKING_CONVERSATION = BOOKING_CONVERSATION_NAME
PRIVACY_CONVERSATION = "privacy"


async def _book_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await invalidate_pending_privacy_input(update, context)
    result = await book_command(update, context)
    _record_active_conversation(context, BOOKING_CONVERSATION, result)
    return result


async def _privacy_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user:
        _cancel_booking_timeout_reminder(context, update.effective_user.id)
    _clear_booking_scoped_state(context)
    result = await privacy_command(update, context)
    _record_active_conversation(context, PRIVACY_CONVERSATION, result)
    return result


async def _cancel_active_conversation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    active = context.user_data.get(ACTIVE_USER_CONVERSATION_KEY)
    try:
        if active == PRIVACY_CONVERSATION:
            return await privacy_cancel(update, context)
        return await cancel_booking(update, context)
    finally:
        context.user_data.pop(ACTIVE_USER_CONVERSATION_KEY, None)


async def _cancel_for_other_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    await _cancel_active_conversation(update, context)
    await update.effective_message.reply_text(
        "Предыдущий диалог завершен. Повторите команду."
    )
    return ConversationHandler.END


async def _conversation_timeout(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    conversation: ConversationHandler | None = None,
) -> int:
    active = context.user_data.get(ACTIVE_USER_CONVERSATION_KEY)
    premature = active != PRIVACY_CONVERSATION and booking_timeout_is_premature(context)

    try:
        if active == PRIVACY_CONVERSATION:
            return await privacy_timeout(update, context)
        return await booking_timeout(update, context)
    finally:
        if premature:
            # booking_timeout() declined to expire this session, so its state has
            # to survive too - see _keep_conversation_alive().
            _keep_conversation_alive(conversation, update)
        else:
            context.user_data.pop(ACTIVE_USER_CONVERSATION_KEY, None)


def _keep_conversation_alive(
    conversation: ConversationHandler | None,
    update: Update,
) -> None:
    """Undo the framework's unconditional END for a session that is still live.

    ``ConversationHandler._trigger_timeout`` discards whatever the TIMEOUT
    callback returns and ends the conversation the moment that callback comes
    back, so the only way to keep a wrongly-timed-out session usable is to write
    its state back afterwards. Nothing between here and that END awaits, which is
    why ``call_soon`` is guaranteed to run after it.
    """
    if conversation is None:
        return

    try:
        key = conversation._get_key(update)
        state = conversation._conversations.get(key)
    except Exception as error:
        logger.warning(
            "Could not read conversation state after a premature timeout error_type=%s",
            type(error).__name__,
        )
        return

    if state is None:
        return

    def _restore() -> None:
        conversation._conversations[key] = state

    try:
        asyncio.get_running_loop().call_soon(_restore)
    except RuntimeError:
        _restore()


def _record_active_conversation(context, name: str, result: int) -> None:
    if result == ConversationHandler.END:
        context.user_data.pop(ACTIVE_USER_CONVERSATION_KEY, None)
        return
    context.user_data[ACTIVE_USER_CONVERSATION_KEY] = name


def create_user_conversation_handler() -> ConversationHandler:
    """Create one state machine so /book and /privacy replace each other."""
    booking = create_booking_conversation_handler()
    privacy = create_privacy_conversation_handler()
    states = {
        state: handlers
        for state, handlers in booking.states.items()
        if state != ConversationHandler.TIMEOUT
    }
    privacy_states = {
        state: handlers
        for state, handlers in privacy.states.items()
        if state != ConversationHandler.TIMEOUT
    }
    if states.keys() & privacy_states.keys():
        raise RuntimeError("Booking and privacy conversation states overlap")
    states.update(privacy_states)
    conversation: ConversationHandler | None = None

    async def timeout_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        return await _conversation_timeout(update, context, conversation)

    states[ConversationHandler.TIMEOUT] = [TypeHandler(Update, timeout_callback)]

    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("book", _book_entry),
            CommandHandler("privacy", _privacy_entry),
        ],
        states=states,
        fallbacks=[
            CommandHandler("cancel", _cancel_active_conversation),
            MessageHandler(filters.COMMAND, _cancel_for_other_command),
        ],
        allow_reentry=True,
        conversation_timeout=timedelta(
            seconds=settings.booking_conversation_timeout_seconds
        ),
    )
    return conversation
