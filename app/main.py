"""Main entry point for the Telecalbot application."""

import logging
import sys

from telegram.error import NetworkError
from telegram import BotCommand
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
    create_booking_handler,
    help_command,
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
from app.services.calcom_client import CalComClient
from app.services.duration_limit import DurationLimitService
from app.services.whitelist import WhitelistService


def setup_logging() -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log uncaught exceptions from handlers and polling."""
    logger = logging.getLogger(__name__)
    error = context.error

    if isinstance(error, NetworkError):
        logger.warning("Transient Telegram network error: %s", error)
        return

    logger.error("Unhandled exception while processing update %r", update, exc_info=error)


def main() -> None:
    """Start the bot."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Initializing Telecalbot...")

    # Initialize database
    run_migrations(db)
    logger.info(f"Database initialized at {settings.database_path}")

    # Create application
    application = Application.builder().token(settings.telegram_bot_token).build()

    # Inject services
    application.bot_data["whitelist_service"] = WhitelistService(db)
    application.bot_data["duration_limit_service"] = DurationLimitService(db)
    application.bot_data["calcom_client"] = CalComClient(
        api_key=settings.calcom_api_key,
        api_version=settings.cal_api_version,
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("approve", approve_command))
    application.add_handler(CommandHandler("reject", reject_command))
    application.add_handler(CommandHandler("pending", pending_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("setlimit", setlimit_command))
    application.add_handler(CommandHandler("removelimit", removelimit_command))
    application.add_handler(CommandHandler("limits", limits_command))
    application.add_handler(create_booking_handler())
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_onboarding_or_help)
    )
    application.add_error_handler(error_handler)

    # Register command menus for Telegram's UI button
    async def post_init(app: Application) -> None:
        from telegram import BotCommandScopeChat

        # Default commands for all users
        await app.bot.set_my_commands([
            BotCommand("start", "Начать работу с ботом"),
            BotCommand("book", "Записаться на встречу"),
            BotCommand("help", "Показать список команд"),
        ])

        # Admin gets additional commands
        await app.bot.set_my_commands(
            [
                BotCommand("start", "Начать работу с ботом"),
                BotCommand("book", "Записаться на встречу"),
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

    logger.info("Bot started. Press Ctrl+C to stop.")

    # Start polling
    application.run_polling()


if __name__ == "__main__":
    main()
