"""Admin command handlers for managing per-user duration limits."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.handlers.admin import admin_only
from app.services.duration_limit import DurationLimitService

logger = logging.getLogger(__name__)

VALID_DURATIONS = (30, 60)


def _parse_target_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Parse target telegram_id from args or reply."""
    # If replying to a message, use that user's ID
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        return update.message.reply_to_message.from_user.id

    if not context.args:
        return None

    try:
        return int(context.args[0])
    except ValueError:
        return None


@admin_only
async def setlimit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /setlimit command to set a duration limit for a user.

    Usage: /setlimit <telegram_id> <minutes>
    Or reply to a user's message: /setlimit <minutes>
    """
    duration_limit_service: DurationLimitService = context.bot_data["duration_limit_service"]

    # Parse arguments
    reply_target = (
        update.message.reply_to_message.from_user.id
        if update.message.reply_to_message and update.message.reply_to_message.from_user
        else None
    )

    if reply_target:
        # /setlimit <minutes> (as reply)
        if not context.args:
            await update.message.reply_text("Использование: /setlimit <минуты> (в ответ на сообщение)")
            return
        try:
            minutes = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Минуты должны быть числом.")
            return
        telegram_id = reply_target
    else:
        # /setlimit <telegram_id> <minutes>
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "Использование: /setlimit <telegram_id> <минуты>\n"
                "Или ответьте на сообщение: /setlimit <минуты>"
            )
            return
        try:
            telegram_id = int(context.args[0])
            minutes = int(context.args[1])
        except ValueError:
            await update.message.reply_text("Telegram ID и минуты должны быть числами.")
            return

    if minutes not in VALID_DURATIONS:
        await update.message.reply_text(
            f"Допустимые значения: {', '.join(str(d) for d in VALID_DURATIONS)} минут."
        )
        return

    duration_limit_service.set_limit(
        telegram_id=telegram_id,
        max_duration_minutes=minutes,
        set_by=update.effective_user.id,
    )

    logger.info(
        "Admin %s set duration limit %d min for user %s",
        update.effective_user.id,
        minutes,
        telegram_id,
    )

    await update.message.reply_text(
        f"Лимит установлен: пользователь {telegram_id} — максимум {minutes} мин."
    )


@admin_only
async def removelimit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /removelimit command to remove a duration limit.

    Usage: /removelimit <telegram_id>
    Or reply to a user's message: /removelimit
    """
    duration_limit_service: DurationLimitService = context.bot_data["duration_limit_service"]

    reply_target = (
        update.message.reply_to_message.from_user.id
        if update.message.reply_to_message and update.message.reply_to_message.from_user
        else None
    )

    if reply_target:
        telegram_id = reply_target
    elif context.args:
        try:
            telegram_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Telegram ID должен быть числом.")
            return
    else:
        await update.message.reply_text(
            "Использование: /removelimit <telegram_id>\n"
            "Или ответьте на сообщение: /removelimit"
        )
        return

    removed = duration_limit_service.remove_limit(telegram_id)

    if removed:
        logger.info(
            "Admin %s removed duration limit for user %s",
            update.effective_user.id,
            telegram_id,
        )
        await update.message.reply_text(f"Лимит для пользователя {telegram_id} удалён.")
    else:
        await update.message.reply_text(f"Лимит для пользователя {telegram_id} не найден.")


@admin_only
async def limits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /limits command to list all duration limits.

    Usage: /limits
    """
    duration_limit_service: DurationLimitService = context.bot_data["duration_limit_service"]

    limits = duration_limit_service.get_all_limits()

    if not limits:
        await update.message.reply_text("Лимитов нет.")
        return

    lines = ["Установленные лимиты:\n"]
    for limit in limits:
        lines.append(
            f"• ID {limit['telegram_id']} — макс. {limit['max_duration_minutes']} мин."
        )

    await update.message.reply_text("\n".join(lines))
