"""Webhook HTTP server for production Telegram delivery."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from http import HTTPStatus

import tornado.web
from telegram import Update
from telegram.ext import Application
from tornado.httpserver import HTTPServer

from app.config import Settings

logger = logging.getLogger(__name__)


def normalize_route_path(path: str) -> str:
    """Return a Tornado route path with one leading slash and no trailing slash."""
    normalized = f"/{path.strip('/')}"
    return "/" if normalized == "/" else normalized


def normalize_optional_token(token: str | None) -> str | None:
    """Return None for blank optional secret-token settings."""
    if token is None:
        return None
    if token.strip() == "":
        return None
    return token


class HealthHandler(tornado.web.RequestHandler):
    """Liveness endpoint for Fly HTTP health checks."""

    SUPPORTED_METHODS = ("GET",)  # type: ignore[assignment]

    def get(self) -> None:
        self.set_status(HTTPStatus.OK)
        self.write({"status": "ok"})


class ReadinessHandler(tornado.web.RequestHandler):
    """Readiness endpoint that flips after the Telegram application is started."""

    SUPPORTED_METHODS = ("GET",)  # type: ignore[assignment]

    def initialize(self, readiness: asyncio.Event) -> None:
        self.readiness = readiness

    def get(self) -> None:
        if self.readiness.is_set():
            self.set_status(HTTPStatus.OK)
            self.write({"status": "ready"})
            return

        self.set_status(HTTPStatus.SERVICE_UNAVAILABLE)
        self.write({"status": "starting"})


class TelegramWebhookHandler(tornado.web.RequestHandler):
    """Accept Telegram webhook updates and enqueue them for python-telegram-bot."""

    SUPPORTED_METHODS = ("POST",)  # type: ignore[assignment]

    def initialize(
        self,
        telegram_application: Application,
        secret_token: str | None,
    ) -> None:
        self.telegram_application = telegram_application
        self.secret_token = secret_token

    def set_default_headers(self) -> None:
        self.set_header("Content-Type", "application/json; charset=utf-8")

    async def post(self) -> None:
        self._validate_request()

        try:
            payload = json.loads(self.request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise tornado.web.HTTPError(
                HTTPStatus.BAD_REQUEST,
                reason="Request body is not valid JSON",
            ) from exc

        try:
            update = Update.de_json(payload, self.telegram_application.bot)
        except Exception as exc:
            raise tornado.web.HTTPError(
                HTTPStatus.BAD_REQUEST,
                reason="Request body is not a valid Telegram update",
            ) from exc

        if update:
            bot = self.telegram_application.bot
            if hasattr(bot, "insert_callback_data"):
                bot.insert_callback_data(update)
            await self.telegram_application.update_queue.put(update)

        self.set_status(HTTPStatus.OK)
        self.write({"status": "accepted"})

    def _validate_request(self) -> None:
        content_type = self.request.headers.get("Content-Type", "")
        if content_type.split(";", maxsplit=1)[0].strip() != "application/json":
            raise tornado.web.HTTPError(
                HTTPStatus.FORBIDDEN,
                reason="Webhook requests must be JSON",
            )

        if self.secret_token is None:
            return

        actual = self.request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if actual != self.secret_token:
            raise tornado.web.HTTPError(
                HTTPStatus.FORBIDDEN,
                reason="Webhook secret token is missing or invalid",
            )


def build_webhook_application(
    *,
    application: Application,
    readiness: asyncio.Event,
    secret_token: str | None,
    webhook_path: str,
    health_path: str,
    readiness_path: str,
) -> tornado.web.Application:
    """Build the Tornado application that Fly and Telegram call."""
    webhook_route = normalize_route_path(webhook_path)
    health_route = normalize_route_path(health_path)
    readiness_route = normalize_route_path(readiness_path)
    normalized_secret_token = normalize_optional_token(secret_token)

    return tornado.web.Application(
        [
            (rf"{health_route}/?", HealthHandler),
            (rf"{readiness_route}/?", ReadinessHandler, {"readiness": readiness}),
            (
                rf"{webhook_route}/?",
                TelegramWebhookHandler,
                {"telegram_application": application, "secret_token": normalized_secret_token},
            ),
        ]
    )


def run_webhook(application: Application, app_settings: Settings) -> None:
    """Run the Telegram application behind a webhook HTTP server."""
    asyncio.run(serve_webhook(application, app_settings))


async def serve_webhook(application: Application, app_settings: Settings) -> None:
    """Start Telegram webhook delivery and block until the process is stopped."""
    if not app_settings.telegram_webhook_url:
        raise ValueError("TELEGRAM_WEBHOOK_URL is required when TELEGRAM_DELIVERY_MODE=webhook")

    secret_token = normalize_optional_token(app_settings.telegram_webhook_secret_token)
    readiness = asyncio.Event()
    stop_event = asyncio.Event()
    web_app = build_webhook_application(
        application=application,
        readiness=readiness,
        secret_token=secret_token,
        webhook_path=app_settings.telegram_webhook_path,
        health_path=app_settings.health_check_path,
        readiness_path=app_settings.readiness_check_path,
    )
    server = HTTPServer(web_app)
    initialized = False

    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        signum = getattr(signal, signame, None)
        if signum is None:
            continue
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except NotImplementedError:
            pass

    try:
        await application.initialize()
        initialized = True
        if application.post_init:
            await application.post_init(application)

        await application.bot.set_webhook(
            url=app_settings.telegram_webhook_url,
            drop_pending_updates=app_settings.telegram_drop_pending_updates,
            secret_token=secret_token,
        )
        await application.start()
        readiness.set()

        server.listen(
            app_settings.telegram_webhook_port,
            address=app_settings.telegram_webhook_listen,
        )
        logger.info(
            "Webhook server listening on %s:%s",
            app_settings.telegram_webhook_listen,
            app_settings.telegram_webhook_port,
        )
        await stop_event.wait()
    finally:
        readiness.clear()
        server.stop()
        await server.close_all_connections()
        await _shutdown_application(application, initialized=initialized)


async def _shutdown_application(application: Application, *, initialized: bool) -> None:
    if application.running:
        await application.stop()
        if application.post_stop:
            await application.post_stop(application)

    if not initialized:
        return

    await application.shutdown()
    post_shutdown = getattr(application, "post_shutdown", None)
    if post_shutdown:
        await post_shutdown(application)
