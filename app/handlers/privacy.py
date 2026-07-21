"""Reversible management of explicitly remembered booking profile fields."""

import logging
from enum import IntEnum, auto

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.constants import RUSSIAN_TIMEZONES
from app.services.user_preferences import UserPreferenceService

logger = logging.getLogger(__name__)

PROFILE_DELETE_NOTICE = "Удаление настроек не отменяет и не удаляет активные записи."
TELEGRAM_ACCESS_NOTICE = (
    "Данные доступа Telegram управляются отдельно и в этом разделе не изменяются."
)
PROFILE_LOAD_FAILED = object()


class PrivacyState(IntEnum):
    """States for the /privacy profile-management conversation."""

    VIEWING = auto()
    ENTERING_NAME = auto()
    SELECTING_TIMEZONE = auto()
    ENTERING_EMAIL = auto()
    END = ConversationHandler.END


async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display remembered fields without requiring current whitelist access."""
    profile = _load_profile(context, update.effective_user.id)
    await update.message.reply_text(
        _privacy_summary(profile),
        reply_markup=_privacy_keyboard(profile),
    )
    return PrivacyState.VIEWING


async def privacy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Change, forget, or delete remembered profile fields."""
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]
    user_id = query.from_user.id
    service = _profile_service(context)

    if action == "edit_name":
        await query.edit_message_text("Введите имя, которое нужно запомнить:")
        return PrivacyState.ENTERING_NAME
    if action == "edit_timezone":
        await query.edit_message_text(
            "Выберите часовой пояс, который нужно запомнить:",
            reply_markup=_privacy_timezone_keyboard(),
        )
        return PrivacyState.SELECTING_TIMEZONE
    if action == "edit_email":
        await query.edit_message_text("Введите email, который нужно запомнить:")
        return PrivacyState.ENTERING_EMAIL
    if action == "delete_confirm":
        await query.edit_message_text(
            f"Удалить все сохраненные настройки профиля?\n\n{PROFILE_DELETE_NOTICE}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Удалить профиль", callback_data="privacy:delete_profile"
                        ),
                        InlineKeyboardButton("Назад", callback_data="privacy:back"),
                    ]
                ]
            ),
        )
        return PrivacyState.VIEWING
    if action == "delete_profile":
        try:
            service.clear_profile(user_id)
        except Exception as error:
            _log_storage_failure("delete", user_id, error)
            await query.edit_message_text(
                "Не удалось удалить сохраненный профиль. Попробуйте позже.\n\n"
                f"{PROFILE_DELETE_NOTICE}"
            )
            return PrivacyState.VIEWING
        await query.edit_message_text(
            f"Сохраненный профиль удален.\n\n{PROFILE_DELETE_NOTICE}\n{TELEGRAM_ACCESS_NOTICE}"
        )
        return PrivacyState.END

    operations = {
        "forget_name": lambda: service.clear_preferred_name(user_id),
        "forget_timezone": lambda: service.clear_timezone(user_id),
        "ask_email": lambda: service.clear_email(user_id),
        "private_email": lambda: service.save_private_email_mode(user_id),
    }
    operation = operations.get(action)
    if operation is not None:
        try:
            operation()
        except Exception as error:
            _log_storage_failure("update", user_id, error)
            await query.edit_message_text(
                "Не удалось изменить сохраненные данные. Попробуйте позже."
            )
            return PrivacyState.VIEWING

    profile = _load_profile(context, user_id)
    await query.edit_message_text(
        _privacy_summary(profile),
        reply_markup=_privacy_keyboard(profile),
    )
    return PrivacyState.VIEWING


async def privacy_enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save a new preferred booking name."""
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Имя не может быть пустым. Попробуйте ещё раз:")
        return PrivacyState.ENTERING_NAME
    if len(name) > 100:
        await update.message.reply_text("Имя слишком длинное. Введите до 100 символов:")
        return PrivacyState.ENTERING_NAME

    try:
        _profile_service(context).save_preferred_name(update.effective_user.id, name)
    except Exception as error:
        _log_storage_failure("save_name", update.effective_user.id, error)
        await update.message.reply_text(
            "Не удалось сохранить имя. Попробуйте позже или вернитесь командой /privacy."
        )
        return PrivacyState.ENTERING_NAME
    await _reply_with_profile(update, context)
    return PrivacyState.VIEWING


async def privacy_select_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save a timezone selected through an opaque numeric callback."""
    query = update.callback_query
    await query.answer()
    try:
        index = int(query.data.split(":", 1)[1])
        if index < 0:
            return PrivacyState.SELECTING_TIMEZONE
        timezone_id = RUSSIAN_TIMEZONES[index][0]
    except (IndexError, ValueError):
        return PrivacyState.SELECTING_TIMEZONE

    try:
        _profile_service(context).save_timezone(query.from_user.id, timezone_id)
    except Exception as error:
        _log_storage_failure("save_timezone", query.from_user.id, error)
        await query.edit_message_text("Не удалось сохранить часовой пояс. Попробуйте позже.")
        return PrivacyState.SELECTING_TIMEZONE
    profile = _load_profile(context, query.from_user.id)
    await query.edit_message_text(
        _privacy_summary(profile),
        reply_markup=_privacy_keyboard(profile),
    )
    return PrivacyState.VIEWING


async def privacy_enter_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save a separately consented personal booking email."""
    email = update.message.text.strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        await update.message.reply_text("Некорректный email. Попробуйте ещё раз:")
        return PrivacyState.ENTERING_EMAIL

    try:
        _profile_service(context).save_email(update.effective_user.id, email)
    except Exception as error:
        _log_storage_failure("save_email", update.effective_user.id, error)
        await update.message.reply_text(
            "Не удалось сохранить email. Попробуйте позже или вернитесь командой /privacy."
        )
        return PrivacyState.ENTERING_EMAIL
    await _reply_with_profile(update, context)
    return PrivacyState.VIEWING


async def _reply_with_profile(update, context) -> None:
    profile = _load_profile(context, update.effective_user.id)
    await update.message.reply_text(
        _privacy_summary(profile),
        reply_markup=_privacy_keyboard(profile),
    )


def _profile_service(context) -> UserPreferenceService:
    return context.bot_data["user_preference_service"]


def _load_profile(context, user_id: int):
    try:
        return _profile_service(context).get_profile(user_id)
    except Exception as error:
        _log_storage_failure("load", user_id, error)
        return PROFILE_LOAD_FAILED


def _log_storage_failure(action: str, user_id: int, error: Exception) -> None:
    logger.error(
        "Booking profile storage failure action=%s user_id=%s error_type=%s",
        action,
        user_id,
        type(error).__name__,
    )


def _privacy_summary(profile) -> str:
    if profile is PROFILE_LOAD_FAILED:
        return (
            "Не удалось загрузить сохраненные данные. Попробуйте позже.\n\n"
            f"{PROFILE_DELETE_NOTICE}\n"
            f"{TELEGRAM_ACCESS_NOTICE}"
        )

    name = profile.preferred_name if profile and profile.preferred_name else "не сохранено"
    timezone = profile.timezone if profile and profile.timezone else "не сохранен"
    if profile is None or profile.email_mode == "ask":
        email = "спрашивать каждый раз"
    elif profile.email_mode == "private":
        email = "без личного email"
    else:
        email = _mask_email(profile.email)

    return (
        "Сохраненные данные для записи:\n\n"
        f"Имя: {name}\n"
        f"Часовой пояс: {timezone}\n"
        f"Email: {email}\n\n"
        f"{PROFILE_DELETE_NOTICE}\n"
        f"{TELEGRAM_ACCESS_NOTICE}"
    )


def _privacy_keyboard(profile) -> InlineKeyboardMarkup:
    if profile is PROFILE_LOAD_FAILED:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("Попробовать снова", callback_data="privacy:back")]]
        )

    buttons = [
        [InlineKeyboardButton("Изменить имя", callback_data="privacy:edit_name")],
    ]
    if profile and profile.preferred_name:
        buttons[-1].append(InlineKeyboardButton("Забыть имя", callback_data="privacy:forget_name"))

    buttons.append(
        [InlineKeyboardButton("Изменить часовой пояс", callback_data="privacy:edit_timezone")]
    )
    if profile and profile.timezone:
        buttons[-1].append(
            InlineKeyboardButton("Забыть часовой пояс", callback_data="privacy:forget_timezone")
        )

    buttons.extend(
        [
            [InlineKeyboardButton("Сохранить email", callback_data="privacy:edit_email")],
            [
                InlineKeyboardButton("Без личного email", callback_data="privacy:private_email"),
                InlineKeyboardButton("Спрашивать email", callback_data="privacy:ask_email"),
            ],
            [InlineKeyboardButton("Удалить весь профиль", callback_data="privacy:delete_confirm")],
        ]
    )
    return InlineKeyboardMarkup(buttons)


def _privacy_timezone_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"privacy_tz:{index}")]
        for index, (_, label) in enumerate(RUSSIAN_TIMEZONES)
    ]
    buttons.append([InlineKeyboardButton("Назад", callback_data="privacy:back")])
    return InlineKeyboardMarkup(buttons)


def _mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "сохранен"
    local, domain = email.rsplit("@", 1)
    first = local[:1] or "*"
    return f"{first}***@{domain}"


def create_privacy_conversation_handler() -> ConversationHandler:
    """Create the /privacy profile-management conversation."""
    return ConversationHandler(
        entry_points=[CommandHandler("privacy", privacy_command)],
        states={
            PrivacyState.VIEWING: [
                CallbackQueryHandler(privacy_callback, pattern="^privacy:"),
            ],
            PrivacyState.ENTERING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, privacy_enter_name),
            ],
            PrivacyState.SELECTING_TIMEZONE: [
                CallbackQueryHandler(privacy_select_timezone, pattern="^privacy_tz:"),
                CallbackQueryHandler(privacy_callback, pattern="^privacy:back$"),
            ],
            PrivacyState.ENTERING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, privacy_enter_email),
            ],
        },
        fallbacks=[CommandHandler("privacy", privacy_command)],
        allow_reentry=True,
    )
