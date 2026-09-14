"""Run the real application, services, migrations, update queue and JobQueue."""

import asyncio
import copy
import socket
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from telegram import Update

from app import main
from app.database import Database, run_migrations

from .fakes import FakeServer

USER_ID = 4242


class Journey:
    def __init__(self, application, db, services, errors):
        self.application = application
        self.db = db
        self.services = services
        self.errors = errors
        self.update_id = 0

    @property
    def screen(self):
        messages = self.services.snapshot()["messages"]
        return next(message for message in reversed(messages) if message["chat"]["id"] == USER_ID)

    @property
    def text(self):
        return self.screen["text"]

    @property
    def booking_requests(self):
        return [r for r in self.services.snapshot()["requests"] if r["path"] == "/v2/bookings"]

    def bookings(self):
        # Fresh SQLite connections prove persistence independently of application memory.
        return self.db.execute("SELECT * FROM bookings ORDER BY id")

    def callback(self, label, *, screen=None):
        screen = copy.deepcopy(screen or self.screen)
        buttons = [b for row in screen.get("reply_markup", {}).get("inline_keyboard", []) for b in row]
        matches = [button for button in buttons if button["text"] == label]
        assert len(matches) == 1, f"Button {label!r} missing or ambiguous on {screen}"
        return {
            "callback_query": {
                "id": f"callback-{self.update_id + 1}", "from": self.user(),
                "chat_instance": "integration-chat", "message": screen,
                "data": matches[0]["callback_data"],
            }
        }

    @staticmethod
    def user():
        return {"id": USER_ID, "is_bot": False, "first_name": "Test User", "username": "test_user"}

    async def send(self, text):
        message = {
            "message_id": self.update_id + 1,
            "date": int(datetime.now(timezone.utc).timestamp()),
            "chat": {"id": USER_ID, "type": "private"}, "from": self.user(), "text": text,
        }
        if text.startswith("/"):
            message["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
        await self.deliver({"message": message})

    async def click(self, label, *, screen=None):
        await self.deliver(self.callback(label, screen=screen))

    async def deliver(self, *payloads):
        for payload in payloads:
            self.update_id += 1
            if "callback_query" in payload:
                payload = copy.deepcopy(payload)
                payload["callback_query"]["id"] = f"callback-{self.update_id}"
            update = Update.de_json({**payload, "update_id": self.update_id}, self.application.bot)
            await self.application.update_queue.put(update)
        await asyncio.wait_for(self.application.update_queue.join(), timeout=5)
        assert not self.errors, f"Application errors: {self.errors}"
        assert not self.services.snapshot()["unexpected_requests"]

    async def choose_slot(self, *, time="10:00", duration="30 минут"):
        await self.click("Москва (UTC+3)")
        await self.click(duration)
        assert "Доступное время (Europe/Moscow)" in self.text
        await self.click(time)
        assert "Введите ваше имя" in self.text

    async def details(self, *, name="Integration Guest", email=None):
        await self.send(name)
        if email:
            await self.click("Да, указать email")
            await self.send(email)
        else:
            await self.click("Нет, пропустить")
        await self.click("Ничего не сохранять")
        assert "Подтвердите запись" in self.text
        assert name in self.text
        assert (email or "без личного email") in self.text

    async def to_confirmation(self, **details):
        await self.send("/book")
        assert "Выберите ваш часовой пояс" in self.text
        await self.choose_slot()
        await self.details(**details)

    async def wait_for_text(self, text, *, after=0, timeout=5):
        async with asyncio.timeout(timeout):
            while not any(
                text in message["text"]
                for message in self.services.snapshot()["messages"][after:]
            ):
                assert not self.errors
                await asyncio.sleep(0.02)


@pytest.fixture
def journey_factory(monkeypatch, tmp_path):
    # Endpoint-wiring regressions must fail locally, even if developer credentials
    # or proxy settings exist in the environment. No provider connection is allowed.
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo

    def local_connect(sock, address):
        if sock.family in {socket.AF_INET, socket.AF_INET6}:
            assert address[0] in {"127.0.0.1", "::1"}, f"Non-local connection: {address}"
        return original_connect(sock, address)

    def local_getaddrinfo(host, *args, **kwargs):
        assert host in {"127.0.0.1", "::1", "localhost", b"127.0.0.1"}, f"Non-local DNS: {host}"
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", local_connect)
    monkeypatch.setattr(socket, "getaddrinfo", local_getaddrinfo)

    @asynccontextmanager
    async def start(*, timeout=60, reminder_before=0):
        with FakeServer() as server:
            test_db = Database(str(tmp_path / "journey.sqlite"))
            run_migrations(test_db)
            monkeypatch.setattr(main, "db", test_db)
            for key, value in {
                "telegram_bot_token": "123456:integration-test",
                "telegram_api_base_url": f"{server.url}/bot",
                "calcom_api_key": "integration-calcom-key",
                "calcom_api_base_url": f"{server.url}/v2",
                "calcom_privacy_email": "privacy@example.test",
                "calcom_event_type_id": 777,
                "calcom_event_type_id_30": None,
                "calcom_event_type_id_60": None,
                "admin_telegram_id": 9999,
                "booking_conversation_timeout_seconds": timeout,
                "booking_conversation_reminder_seconds_before_timeout": reminder_before,
            }.items():
                monkeypatch.setattr(main.settings, key, value)
            application = main.create_application()
            errors = []

            async def collect_error(update, context):
                errors.append(context.error)

            application.add_error_handler(collect_error)
            application.bot_data["whitelist_service"].add_to_whitelist(
                USER_ID, "Test User", "test_user", main.settings.admin_telegram_id,
            )
            try:
                async with application:
                    await application.post_init(application)
                    await application.start()
                    try:
                        yield Journey(application, test_db, server.services, errors)
                    finally:
                        await asyncio.wait_for(application.stop(), timeout=5)
            finally:
                await application.bot_data["calcom_client"].close()
            assert not errors, f"Application errors: {errors}"
            assert not server.services.snapshot()["unexpected_requests"]

    return start


@pytest.fixture
async def journey(journey_factory):
    async with journey_factory() as instance:
        yield instance
