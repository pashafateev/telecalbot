"""Main entry point for the Telecalbot application."""

import logging
import sys

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app.config import settings
from app.database import db, run_migrations
from app.handlers import (
    approve_command,
    create_booking_conversation_handler,
    create_cancel_booking_flow_handlers,
    help_command,
    pending_command,
    reject_command,
    start_command,
    text_onboarding_or_help,
)
from app.services.booking_service import BookingService
from app.services.calcom_client import CalComClient
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
    application.bot_data["booking_service"] = BookingService(db)
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
    application.add_handler(create_booking_conversation_handler())
    for handler in create_cancel_booking_flow_handlers():
        application.add_handler(handler)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_onboarding_or_help)
    )

    logger.info("Bot started. Press Ctrl+C to stop.")

    # Start polling
    application.run_polling()


if __name__ == "__main__":
    main()
