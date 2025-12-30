"""Handler for the /start command."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.first_name}) started the bot")

    await update.message.reply_text(
        f"Hello, {user.first_name}! I can help you book appointments."
    )
