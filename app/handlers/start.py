"""Handler for the /start command."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.config import settings
from app.handlers.help import help_command
from app.services.whitelist import WhitelistService

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command with access control."""
    whitelist_service: WhitelistService = context.bot_data["whitelist_service"]

    user = update.effective_user
    chat_id = user.id

    logger.info(f"User {chat_id} ({user.first_name}) started the bot")

    # Auto-whitelist admin user
    if chat_id == settings.admin_telegram_id and not whitelist_service.is_whitelisted(chat_id):
        whitelist_service.add_to_whitelist(
            telegram_id=chat_id,
            display_name=user.first_name,
            username=user.username,
            approved_by=chat_id,  # Self-approved as admin
        )
        logger.info(f"Admin user {chat_id} auto-whitelisted")

    if whitelist_service.is_whitelisted(chat_id):
        # Whitelisted user - show welcome + help menu
        await update.message.reply_text(
            f"Добро пожаловать, {user.first_name}! Я помогу вам записаться на встречу."
        )
        await help_command(update, context)
    else:
        # Not whitelisted - create access request and notify admin
        is_new = whitelist_service.create_access_request(
            telegram_id=chat_id,
            display_name=user.first_name,
            username=user.username,
        )

        if is_new:
            # Notify admin of new request
            await _notify_admin_of_request(context, user)

        await update.message.reply_text(
            f"Этот бот доступен только для одобренных пользователей.\n\n"
            f"Ваш Chat ID: `{chat_id}`\n\n"
            f"Запрос на доступ отправлен администратору.",
            parse_mode="Markdown",
        )


async def text_onboarding_or_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain-text messages outside commands/conversations.

    - Whitelisted users see help immediately.
    - New users get the same access-request flow as /start.
    """
    whitelist_service: WhitelistService = context.bot_data["whitelist_service"]
    user_id = update.effective_user.id

    if whitelist_service.is_whitelisted(user_id):
        await help_command(update, context)
        return

    await start_command(update, context)


async def _notify_admin_of_request(context: ContextTypes.DEFAULT_TYPE, user) -> None:
    """Send notification to admin about new access request."""
    username_str = f"@{user.username}" if user.username else "(no username)"

    try:
        await context.bot.send_message(
            chat_id=settings.admin_telegram_id,
            text=(
                f"New access request:\n\n"
                f"Name: {user.first_name}\n"
                f"Username: {username_str}\n"
                f"Chat ID: {user.id}\n\n"
                f"To approve: /approve {user.id}"
            ),
        )
    except Exception as e:
        logger.error(f"Failed to notify admin of access request: {e}")
