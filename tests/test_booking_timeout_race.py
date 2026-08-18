"""Regression tests for the booking session timeout/reminder lifecycle.

These drive a real :class:`telegram.ext.Application`, the real unified
:class:`telegram.ext.ConversationHandler` and a real ``JobQueue`` so that the
conversation-timeout job and the reminder job actually fire through APScheduler.
The pre-existing timer tests only assert against mocked job queues, so they
cannot observe what happens when a timer callback runs *while* a booking update
is being processed - which is the failure reported from production on
August 11 (a brand-new session was expired, and its reminder outlived it).
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from telegram import Chat, Message, MessageEntity, Update, User
from telegram.ext import Application, ConversationHandler

from app.config import settings
from app.handlers import booking as booking_module
from app.handlers.booking import BOOKING_TIMEOUT_REMINDER_TEXT, BookingState

USER_ID = 12345
CHAT_ID = 12345
CONVERSATION_KEY = (CHAT_ID, USER_ID)
TIMEOUT_TEXT = "Сессия записи истекла из-за неактивности."


def _was_sent(sent: list[str], text: str) -> bool:
    return any(text in (message or "") for message in sent)


def _user() -> User:
    return User(id=USER_ID, first_name="Test", is_bot=False)


def _chat() -> Chat:
    return Chat(id=CHAT_ID, type=Chat.PRIVATE)


def _message_update(application: Application, update_id: int, text: str) -> Update:
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


class _Gate:
    """Suspend a callback so another update can be processed while it runs."""

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def wait_until_entered(self) -> None:
        await asyncio.wait_for(self.entered.wait(), timeout=10)

    async def let_it_finish(self) -> None:
        self.release.set()
        await asyncio.sleep(0.05)


async def _build_application(
    monkeypatch,
    *,
    timeout_seconds: float,
    reminder_lead_seconds: float,
):
    """Build a running application whose timers fire on a compressed schedule."""
    monkeypatch.setattr(
        settings,
        "booking_conversation_timeout_seconds",
        timeout_seconds,
        raising=False,
    )
    monkeypatch.setattr(
        settings,
        "booking_conversation_reminder_seconds_before_timeout",
        reminder_lead_seconds,
        raising=False,
    )

    from app.handlers.user_conversation import create_user_conversation_handler

    application = Application.builder().token("123456:test-token").build()
    application._initialized = True
    application.bot._initialized = True
    application.bot._bot_user = User(
        id=999,
        first_name="Telecalbot",
        is_bot=True,
        username="telecalbot_test_bot",
    )

    sent: list[str] = []

    async def fake_send_message(self, chat_id=None, text=None, **kwargs):
        sent.append(text)
        return MagicMock()

    async def fake_edit_message_text(self, *args, **kwargs):
        sent.append(kwargs.get("text", args[0] if args else None))
        return MagicMock()

    async def fake_answer_callback_query(self, *args, **kwargs):
        return True

    monkeypatch.setattr(application.bot.__class__, "send_message", fake_send_message)
    monkeypatch.setattr(
        application.bot.__class__, "edit_message_text", fake_edit_message_text
    )
    monkeypatch.setattr(
        application.bot.__class__,
        "answer_callback_query",
        fake_answer_callback_query,
    )

    whitelist_service = MagicMock()
    whitelist_service.is_whitelisted.return_value = True
    duration_limit_service = MagicMock()
    duration_limit_service.get_limit.return_value = None
    preference_service = MagicMock()
    preference_service.get_profile.return_value = None
    application.bot_data.update(
        {
            "whitelist_service": whitelist_service,
            "duration_limit_service": duration_limit_service,
            "user_preference_service": preference_service,
        }
    )

    conversation = create_user_conversation_handler()
    application.add_handler(conversation)
    await application.job_queue.start()
    return application, conversation, sent


def _gate_conversation_timeout(conversation: ConversationHandler) -> _Gate:
    """Hold the conversation-timeout callback open once its job has fired.

    A real ``booking_timeout`` awaits Telegram while sending the expiry notice,
    so the application keeps handling updates for the same conversation during
    that window. The gate makes that window deterministic.
    """
    gate = _Gate()
    handler = conversation.states[ConversationHandler.TIMEOUT][0]
    real_callback = handler.callback

    async def gated(update, context):
        gate.entered.set()
        await gate.release.wait()
        return await real_callback(update, context)

    handler.callback = gated
    return gate


def _gate_reminder(monkeypatch) -> _Gate:
    """Hold the reminder callback open after APScheduler has dispatched it.

    Once a job is handed to the executor, ``schedule_removal()`` can no longer
    stop it, so the callback itself has to decide whether it is still relevant.
    """
    gate = _Gate()
    real_callback = booking_module._send_booking_timeout_reminder

    async def gated(context):
        gate.entered.set()
        await gate.release.wait()
        return await real_callback(context)

    monkeypatch.setattr(booking_module, "_send_booking_timeout_reminder", gated)
    return gate


async def _shutdown(application: Application) -> None:
    if application.job_queue.scheduler.running:
        await application.job_queue.stop(wait=False)


@pytest.mark.asyncio
async def test_conversation_timeout_does_not_expire_a_session_that_just_replied(
    monkeypatch,
):
    """A session that received input must survive a timeout firing beside it."""
    application, conversation, sent = await _build_application(
        monkeypatch,
        timeout_seconds=1,
        # Larger than the timeout, so no reminder is scheduled for this test.
        reminder_lead_seconds=120,
    )
    try:
        gate = _gate_conversation_timeout(conversation)

        await application.process_update(_message_update(application, 1, "/book"))
        conversation._conversations[CONVERSATION_KEY] = BookingState.ENTERING_NAME

        # The timeout job fires; python-telegram-bot has already committed to
        # ending the conversation once this callback returns.
        await gate.wait_until_entered()

        # The user answers "Введите ваше имя" inside that window.
        await application.process_update(_message_update(application, 2, "Nikolai"))
        await gate.let_it_finish()
        await asyncio.sleep(0.05)

        assert not _was_sent(sent, TIMEOUT_TEXT), (
            "the bot told a user their session expired one message after they "
            f"answered it; sent={sent}"
        )
        assert application.user_data[USER_ID].get("name") == "Nikolai"
        assert (
            conversation._conversations.get(CONVERSATION_KEY)
            == BookingState.EMAIL_DECISION
        ), "the live booking conversation was ended by a stale timeout"
    finally:
        await _shutdown(application)


@pytest.mark.asyncio
async def test_conversation_timeout_still_expires_a_genuinely_idle_session(monkeypatch):
    """The guard must not disable the timeout it is protecting."""
    application, conversation, sent = await _build_application(
        monkeypatch,
        timeout_seconds=1,
        reminder_lead_seconds=120,
    )
    try:
        await application.process_update(_message_update(application, 1, "/book"))
        conversation._conversations[CONVERSATION_KEY] = BookingState.ENTERING_NAME

        # Nobody touches the session for the whole timeout window.
        await asyncio.sleep(1.4)

        assert _was_sent(sent, TIMEOUT_TEXT), f"the session was never expired; sent={sent}"
        assert conversation._conversations.get(CONVERSATION_KEY) is None
        assert application.user_data[USER_ID] == {}
    finally:
        await _shutdown(application)


@pytest.mark.asyncio
async def test_reminder_does_not_fire_after_the_booking_conversation_ended(
    monkeypatch,
):
    """An already-dispatched reminder must stay silent once the session is over."""
    gate = _gate_reminder(monkeypatch)
    application, conversation, sent = await _build_application(
        monkeypatch,
        timeout_seconds=60,
        reminder_lead_seconds=59,
    )
    try:
        await application.process_update(_message_update(application, 1, "/book"))

        # The reminder job is now running: cancelling it can no longer stop it.
        await gate.wait_until_entered()

        await application.process_update(_message_update(application, 2, "/cancel"))
        assert conversation._conversations.get(CONVERSATION_KEY) is None

        await gate.let_it_finish()

        assert not _was_sent(sent, BOOKING_TIMEOUT_REMINDER_TEXT), (
            "a booking reminder was delivered after the conversation ended; "
            f"sent={sent}"
        )
    finally:
        await _shutdown(application)


@pytest.mark.asyncio
async def test_reminder_from_a_previous_booking_attempt_stays_silent(monkeypatch):
    """A reminder belongs to the attempt that armed it, not to the user."""
    gate = _gate_reminder(monkeypatch)
    application, conversation, sent = await _build_application(
        monkeypatch,
        timeout_seconds=60,
        reminder_lead_seconds=59,
    )
    try:
        await application.process_update(_message_update(application, 1, "/book"))
        await gate.wait_until_entered()

        # The user restarts booking while the first reminder is already running.
        await application.process_update(_message_update(application, 2, "/book"))
        await gate.let_it_finish()

        assert not _was_sent(sent, BOOKING_TIMEOUT_REMINDER_TEXT), (
            "a reminder from an abandoned booking attempt was delivered against "
            f"a freshly started one; sent={sent}"
        )
    finally:
        await _shutdown(application)
