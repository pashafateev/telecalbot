"""Admin command handlers for access control management."""

import logging
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from app.config import settings
from app.services.whitelist import WhitelistService

logger = logging.getLogger(__name__)


def admin_only(func):
    """Decorator to restrict handler to admin user only."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != settings.admin_telegram_id:
            logger.warning(f"Unauthorized admin access attempt by user {user_id}")
            await update.message.reply_text("You are not authorized to use this command.")
            return
        return await func(update, context)

    return wrapper


@admin_only
async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /approve command to approve an access request.

    Usage: /approve <telegram_id>
    """
    whitelist_service: WhitelistService = context.bot_data["whitelist_service"]

    if not context.args:
        await update.message.reply_text("Usage: /approve <telegram_id>")
        return

    try:
        telegram_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid telegram ID. Must be a number.")
        return

    request = whitelist_service.get_access_request(telegram_id)
    if request is None or request.status != "pending":
        await update.message.reply_text(f"No pending request found for ID {telegram_id}.")
        return

    approved = whitelist_service.approve_request(
        telegram_id=telegram_id,
        approved_by=update.effective_user.id,
    )

    if approved:
        logger.info(f"Admin {update.effective_user.id} approved user {telegram_id}")

        await update.message.reply_text(
            f"Approved {request.display_name} ({telegram_id})."
        )

        # Notify the user
        try:
            await context.bot.send_message(
                chat_id=telegram_id,
                text="You've been approved! Use /start to begin booking.",
            )
        except Exception as e:
            logger.warning(f"Failed to notify user {telegram_id}: {e}")
            await update.message.reply_text(
                "(Note: Could not notify the user - they may have blocked the bot.)"
            )
    else:
        await update.message.reply_text(f"Failed to approve request for {telegram_id}.")


@admin_only
async def reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /reject command to reject an access request.

    Usage: /reject <telegram_id>
    """
    whitelist_service: WhitelistService = context.bot_data["whitelist_service"]

    if not context.args:
        await update.message.reply_text("Usage: /reject <telegram_id>")
        return

    try:
        telegram_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid telegram ID. Must be a number.")
        return

    request = whitelist_service.get_access_request(telegram_id)
    if request is None or request.status != "pending":
        await update.message.reply_text(f"No pending request found for ID {telegram_id}.")
        return

    rejected = whitelist_service.reject_request(telegram_id)

    if rejected:
        logger.info(f"Admin {update.effective_user.id} rejected user {telegram_id}")
        await update.message.reply_text(
            f"Rejected {request.display_name} ({telegram_id})."
        )
    else:
        await update.message.reply_text(f"Failed to reject request for {telegram_id}.")


@admin_only
async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /pending command to list all pending access requests.

    Usage: /pending
    """
    whitelist_service: WhitelistService = context.bot_data["whitelist_service"]

    requests = whitelist_service.get_pending_requests()

    if not requests:
        await update.message.reply_text("No pending access requests.")
        return

    lines = ["Pending access requests:\n"]
    for req in requests:
        username_str = f"@{req.username}" if req.username else "(no username)"
        lines.append(f"• {req.display_name} {username_str}\n  ID: {req.telegram_id}\n  /approve {req.telegram_id}")

    await update.message.reply_text("\n".join(lines))
