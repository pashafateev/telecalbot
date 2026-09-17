"""Main entry point for the Telecalbot application."""

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegram import BotCommand
from telegram.error import NetworkError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import settings
from app.database import db, run_migrations
from app.handlers import (
    approve_command,
    create_cancel_booking_flow_handlers,
    create_user_conversation_handler,
    help_command,
    invalidate_pending_privacy_input,
    pending_command,
    reject_command,
    start_command,
    text_onboarding_or_help,
)
from app.handlers.duration_limit import (
    limits_command,
    removelimit_command,
    setlimit_command,
)
from app.services.booking_service import BookingService
from app.services.calcom_client import CalComClient
from app.services.duration_limit import DurationLimitService
from app.services.user_preferences import UserPreferenceService
from app.services.whitelist import WhitelistService
from app.webhook_server import run_webhook


def _build_log_file_handler() -> RotatingFileHandler | None:
    """Open the rotating log file on the volume, or None if it is unusable."""
    log_file_path = getattr(settings, "log_file_path", None)
    if not log_file_path:
        return None

    try:
        path = Path(log_file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return RotatingFileHandler(
            path,
            maxBytes=settings.log_file_max_bytes,
            backupCount=settings.log_file_backup_count,
            encoding="utf-8",
        )
    except OSError as error:
        # A missing or read-only volume must never keep the bot from starting.
        print(
            f"Could not open log file {log_file_path!r} "
            f"({type(error).__name__}); logging to stdout only",
            file=sys.stderr,
        )
        return None


def setup_logging() -> None:
    """Configure logging for the application."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    file_handler = _build_log_file_handler()
    if file_handler is not None:
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )
    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if file_handler is not None:
        total_cap_mb = (
            settings.log_file_max_bytes * (settings.log_file_backup_count + 1) / 1_000_000
        )
        logging.getLogger(__name__).info(
            "Durable logging to %s capped at %.0fMB across %s files",
            file_handler.baseFilename,
            total_cap_mb,
            settings.log_file_backup_count + 1,
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log uncaught exceptions from handlers and polling."""
    logger = logging.getLogger(__name__)
    error = context.error

    if isinstance(error, NetworkError):
        logger.warning("Transient Telegram network error type=%s", type(error).__name__)
        return

    logger.error(
        "Unhandled exception while processing update error_type=%s traceback_frames=\n%s",
        type(error).__name__,
        "".join(traceback.format_tb(error.__traceback__)).rstrip(),
    )


def create_application() -> Application:
    """Create and configure the Telegram application."""
    application = Application.builder().token(settings.telegram_bot_token).build()

    # Inject services
    application.bot_data["whitelist_service"] = WhitelistService(db)
    application.bot_data["user_preference_service"] = UserPreferenceService(db)
    application.bot_data["duration_limit_service"] = DurationLimitService(db)
    application.bot_data["booking_service"] = BookingService(db)
    application.bot_data["calcom_client"] = CalComClient(api_key=settings.calcom_api_key)

    # Register handlers
    application.add_handler(
        MessageHandler(filters.COMMAND, invalidate_pending_privacy_input),
        group=-1,
    )
    application.add_handler(create_user_conversation_handler())
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("approve", approve_command))
    application.add_handler(CommandHandler("reject", reject_command))
    application.add_handler(CommandHandler("pending", pending_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("setlimit", setlimit_command))
    application.add_handler(CommandHandler("removelimit", removelimit_command))
    application.add_handler(CommandHandler("limits", limits_command))
    for handler in create_cancel_booking_flow_handlers():
        application.add_handler(handler)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_onboarding_or_help)
    )
    application.add_error_handler(error_handler)

    # Register command menus for Telegram's UI button
    async def post_init(app: Application) -> None:
        from telegram import BotCommandScopeChat

        # Default commands for all users
        await app.bot.set_my_commands(
            [
                BotCommand("start", "Начать работу с ботом"),
                BotCommand("book", "Записаться на встречу"),
                BotCommand("cancel_booking", "Отменить запись"),
                BotCommand("privacy", "Управлять сохраненными данными"),
                BotCommand("help", "Показать список команд"),
            ]
        )

        # Admin gets additional commands
        await app.bot.set_my_commands(
            [
                BotCommand("start", "Начать работу с ботом"),
                BotCommand("book", "Записаться на встречу"),
                BotCommand("cancel_booking", "Отменить запись"),
                BotCommand("privacy", "Управлять сохраненными данными"),
                BotCommand("help", "Показать список команд"),
                BotCommand("pending", "Список ожидающих запросов"),
                BotCommand("setlimit", "Установить лимит длительности"),
                BotCommand("removelimit", "Удалить лимит длительности"),
                BotCommand("limits", "Показать все лимиты"),
                BotCommand("approve", "Одобрить запрос на доступ"),
                BotCommand("reject", "Отклонить запрос на доступ"),
            ],
            scope=BotCommandScopeChat(chat_id=settings.admin_telegram_id),
        )

    application.post_init = post_init
    return application


def main() -> None:
    """Start the bot."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Initializing Telecalbot...")

    settings.validate_event_type_configuration()

    # Initialize database
    run_migrations(db)
    logger.info(f"Database initialized at {settings.database_path}")

    application = create_application()

    if settings.telegram_delivery_mode == "webhook":
        logger.info("Starting Telegram webhook delivery.")
        run_webhook(application, settings)
        return

    logger.info("Starting Telegram polling. Press Ctrl+C to stop.")
    application.run_polling()


if __name__ == "__main__":
    main()
