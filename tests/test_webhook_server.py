"""Tests for the production webhook HTTP surface."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets

from app.webhook_server import build_webhook_application


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
        secret_token=None,
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
