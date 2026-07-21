"""Tests for the production webhook HTTP surface."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets

from app.config import Settings
from app.webhook_server import build_webhook_application, serve_webhook


class LocalServer:
    """Context manager for a local Tornado test server."""

    def __init__(self, app):
        self.app = app
        self.server = HTTPServer(app)
        self.sockets = bind_sockets(0, address="127.0.0.1")
        self.port = self.sockets[0].getsockname()[1]

    async def __aenter__(self):
        self.server.add_sockets(self.sockets)
        return f"http://127.0.0.1:{self.port}"

    async def __aexit__(self, exc_type, exc, tb):
        self.server.stop()
        await self.server.close_all_connections()


@pytest.mark.asyncio
async def test_health_is_available_before_readiness():
    readiness = asyncio.Event()
    web_app = build_webhook_application(
        application=SimpleNamespace(bot=MagicMock(), update_queue=asyncio.Queue()),
        readiness=readiness,
        secret_token="test-secret",
        webhook_path="/telegram/webhook",
        health_path="/healthz",
        readiness_path="/readyz",
    )

    async with LocalServer(web_app) as base_url:
        async with httpx.AsyncClient() as client:
            health = await client.get(f"{base_url}/healthz")
            starting = await client.get(f"{base_url}/readyz")

            readiness.set()
            ready = await client.get(f"{base_url}/readyz")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert starting.status_code == 503
    assert starting.json() == {"status": "starting"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_webhook_requires_secret_and_enqueues_update():
    update_queue = asyncio.Queue()
    application = SimpleNamespace(bot=MagicMock(), update_queue=update_queue)
    web_app = build_webhook_application(
        application=application,
        readiness=asyncio.Event(),
        secret_token="test-secret",
        webhook_path="/telegram/webhook",
        health_path="/healthz",
        readiness_path="/readyz",
    )

    async with LocalServer(web_app) as base_url:
        async with httpx.AsyncClient() as client:
            forbidden = await client.post(
                f"{base_url}/telegram/webhook",
                json={"update_id": 123},
            )
            accepted = await client.post(
                f"{base_url}/telegram/webhook",
                json={"update_id": 123},
                headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
            )

    update = update_queue.get_nowait()

    assert forbidden.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json() == {"status": "accepted"}
    assert update.update_id == 123


@pytest.mark.asyncio
async def test_non_json_webhook_request_returns_unsupported_media_type():
    web_app = build_webhook_application(
        application=SimpleNamespace(bot=MagicMock(), update_queue=asyncio.Queue()),
        readiness=asyncio.Event(),
        secret_token="test-secret",
        webhook_path="/telegram/webhook",
        health_path="/healthz",
        readiness_path="/readyz",
    )

    async with LocalServer(web_app) as base_url:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/telegram/webhook",
                content="{}",
                headers={
                    "Content-Type": "text/plain",
                    "X-Telegram-Bot-Api-Secret-Token": "test-secret",
                },
            )

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_malformed_telegram_update_returns_bad_request():
    update_queue = asyncio.Queue()
    application = SimpleNamespace(bot=MagicMock(), update_queue=update_queue)
    web_app = build_webhook_application(
        application=application,
        readiness=asyncio.Event(),
        secret_token="test-secret",
        webhook_path="/telegram/webhook",
        health_path="/healthz",
        readiness_path="/readyz",
    )

    async with LocalServer(web_app) as base_url:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/telegram/webhook",
                json={"message": {}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
            )

    assert response.status_code == 400
    assert update_queue.empty()


@pytest.mark.asyncio
async def test_webhook_listener_starts_before_telegram_initialization():
    events = []
    application = MagicMock()
    application.initialize = AsyncMock(side_effect=lambda: events.append("initialize"))
    application.post_init = AsyncMock(side_effect=lambda app: events.append("post_init"))
    application.bot.set_webhook = AsyncMock(side_effect=lambda **kwargs: events.append("set_webhook"))
    application.start = AsyncMock(side_effect=lambda: events.append("start"))
    application.running = True
    application.stop = AsyncMock()
    application.post_stop = None
    application.shutdown = AsyncMock()
    application.post_shutdown = None

    server = MagicMock()
    server.listen.side_effect = lambda *args, **kwargs: events.append("listen")
    server.close_all_connections = AsyncMock()
    stop_event = asyncio.Event()
    stop_event.set()
    settings = Settings(
        telegram_delivery_mode="webhook",
        telegram_webhook_url="https://example.com/telegram/webhook",
        telegram_webhook_secret_token="test-secret",
    )

    with patch("app.webhook_server.HTTPServer", return_value=server):
        await serve_webhook(application, settings, stop_event=stop_event)

    assert events[:5] == ["listen", "initialize", "post_init", "set_webhook", "start"]
    application.bot.set_webhook.assert_awaited_once_with(
        url="https://example.com/telegram/webhook",
        drop_pending_updates=False,
        secret_token="test-secret",
    )
