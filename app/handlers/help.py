"""Handler for the /help command."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.config import settings
from app.services.whitelist import WhitelistService

logger = logging.getLogger(__name__)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available commands based on user's access level."""
    whitelist_service: WhitelistService = context.bot_data["whitelist_service"]
    user_id = update.effective_user.id

    if not whitelist_service.is_whitelisted(user_id):
        await update.message.reply_text(
            "Доступные команды:\n\n"
            "/start — Запросить доступ к боту"
        )
        return

    lines = [
        "Доступные команды:\n",
        "/book — Записаться на встречу",
        "/cancel_booking — Отменить существующую запись",
        "/help — Показать список команд",
    ]

    if user_id == settings.admin_telegram_id:
        lines.append("\nAdmin commands:\n")
        lines.append("/approve <id> — Approve access request")
        lines.append("/reject <id> — Reject access request")
        lines.append("/pending — List pending access requests")

    await update.message.reply_text("\n".join(lines))
