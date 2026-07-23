"""Booking conversation handler for multi-step appointment booking."""

import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from enum import IntEnum, auto
from types import SimpleNamespace

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from app.config import settings
from app.constants import (
    MAX_EMAIL_LENGTH,
    MAX_NAME_LENGTH,
    RUSSIAN_TIMEZONES,
    SUPPORTED_BOOKING_DURATIONS,
    SUPPORTED_TIMEZONE_IDS,
)
from app.services.booking_service import BookingService
from app.services.calcom_client import (
    Attendee,
    BookingRequest,
    BookingResponse,
    CalComAPIError,
    CalComClient,
)
from app.services.duration_limit import DurationLimitService
from app.services.user_preferences import UserPreferenceService
from app.services.whitelist import WhitelistService

logger = logging.getLogger(__name__)

RUSSIAN_WEEKDAYS = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]

RUSSIAN_MONTHS_ABBR = [
    "янв",
    "фев",
    "мар",
    "апр",
    "мая",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
]

TIMEZONE_BUTTON_LABEL = "Часовой пояс"

DURATION_OPTIONS = {minutes: f"{minutes} минут" for minutes in SUPPORTED_BOOKING_DURATIONS}
FIFTH_STEP_RESTRICTION_TEXT = "двухчасовые встречи предназначены только для работы по 5-му шагу."
FIFTH_STEP_WARNING_TEXT = (
    f"Важно: {FIFTH_STEP_RESTRICTION_TEXT}\n\n"
    "Если вы записываетесь не для 5-го шага, пожалуйста, выберите длительность "
    "30 или 60 минут."
)
FIFTH_STEP_CONFIRM_CALLBACK = "duration_120_confirm"
CHANGE_DURATION_CALLBACK = "change_duration"
CANCEL_SELECT_PREFIX = "cancel_booking_select:"
CANCEL_CONFIRM_PREFIX = "cancel_booking_confirm:"
CANCEL_BACK_CALLBACK = "cancel_booking_back"
CANCEL_BOOKING_TERMINAL_STATUS_CODES = {404, 409}
CANCEL_BOOKING_ACCESS_DENIED_TEXT = (
    "Эта команда доступна только одобренным пользователям.\nИспользуйте /start для запроса доступа."
)
BOOKING_REMINDER_JOB_PREFIX = "booking_timeout_reminder:"
BOOKING_TIMEOUT_REMINDER_TEXT = (
    "Напоминание: сессия записи скоро истечет из-за неактивности.\n"
    "Пожалуйста, завершите запись или начните заново командой /book."
)
BOOKING_SCOPED_USER_DATA_KEYS = frozenset(
    {
        "timezone",
        "offset_days",
        "duration",
        "pending_duration",
        "selected_date",
        "selected_time",
        "name",
        "email",
        "email_mode",
        "remember_choices",
        "remembered_profile_fields",
        "edit_field",
        "internal_ref",
    }
)
EMAIL_DOMAIN_CANNOT_RECEIVE_MAIL = "email_domain_cannot_receive_mail"
PRIVACY_EMAIL_UNAVAILABLE_TEXT = (
    "Запись без личного email временно недоступна. "
    "Вы можете указать email сейчас или попробовать позже."
)


class BookingState(IntEnum):
    SELECTING_TIMEZONE = auto()
    SELECTING_DURATION = auto()
    VIEWING_AVAILABILITY = auto()
    SELECTING_SLOT = auto()
    ENTERING_NAME = auto()
    EMAIL_DECISION = auto()
    ENTERING_EMAIL = auto()
    REMEMBERING_PROFILE = auto()
    CONFIRMING = auto()


class _MessageReplyTarget:
    """Adapter for reusing callback edit flow from a command message."""

    def __init__(self, message, user_id: int, prefix: str | None = None):
        self.message = message
        self.from_user = SimpleNamespace(id=user_id)
        self._prefix = prefix
        self._sent = None

    async def edit_message_text(self, text: str, reply_markup=None) -> None:
        if self._prefix is not None:
            text = f"{self._prefix}\n\n{text}"
        if self._sent is None:
            self._sent = await self.message.reply_text(text, reply_markup=reply_markup)
            return
        await self._sent.edit_text(text, reply_markup=reply_markup)


def _is_non_editable_message_error(error: BadRequest) -> bool:
    text = str(error).lower()
    return "can't be edited" in text or "can not be edited" in text


async def _safe_edit_message_text(query, text: str, reply_markup=None) -> None:
    """Edit callback message, fallback to a new message when editing is not possible."""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except BadRequest as error:
        if _is_non_editable_message_error(error) and query.message:
            await query.message.reply_text(text, reply_markup=reply_markup)
            return
        raise


async def _deny_booking_access(update: Update) -> None:
    """Tell unapproved users they need approval before booking."""
    text = (
        "Доступ к записи доступен только одобренным пользователям.\n"
        "Используйте /start, чтобы запросить доступ."
    )
    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await _safe_edit_message_text(update.callback_query, text)


def _is_whitelisted(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return access status. Missing whitelist service is treated as denied."""
    whitelist_service: WhitelistService | None = context.bot_data.get("whitelist_service")
    if whitelist_service is None:
        logger.warning("whitelist_service missing in bot_data; denying booking access")
        return False
    user_id = update.effective_user.id
    return whitelist_service.is_whitelisted(user_id)


def _get_duration_limit(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
) -> int | None:
    duration_limit_service: DurationLimitService | None = context.bot_data.get(
        "duration_limit_service"
    )
    if duration_limit_service is None:
        return None
    return duration_limit_service.get_limit(user_id)


def _apply_current_duration_limit(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    requested_duration: int,
) -> int:
    max_duration = _get_duration_limit(context, user_id)
    if max_duration is None or requested_duration <= max_duration:
        return requested_duration

    logger.info(
        "Capping booking duration for user_id=%s from %s to %s minutes",
        user_id,
        requested_duration,
        max_duration,
    )
    return max_duration


def _booking_reminder_job_name(user_id: int) -> str:
    return f"{BOOKING_REMINDER_JOB_PREFIX}{user_id}"


def _clear_booking_scoped_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove only transient values owned by the booking conversation."""
    for key in BOOKING_SCOPED_USER_DATA_KEYS:
        context.user_data.pop(key, None)


def _privacy_email() -> str | None:
    configured_email = getattr(settings, "calcom_privacy_email", None)
    if not isinstance(configured_email, str):
        return None
    configured_email = configured_email.strip()
    return configured_email or None


def _booking_reference(data: dict) -> str:
    existing_reference = data.get("internal_ref")
    if isinstance(existing_reference, str) and existing_reference.startswith("tbk_"):
        return existing_reference

    reference = f"tbk_{secrets.token_hex(8)}"
    data["internal_ref"] = reference
    return reference


async def _show_privacy_email_unavailable(query) -> int:
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Указать email", callback_data="email_yes"),
                InlineKeyboardButton("Отмена", callback_data="cancel"),
            ]
        ]
    )
    await _safe_edit_message_text(
        query,
        PRIVACY_EMAIL_UNAVAILABLE_TEXT,
        reply_markup=keyboard,
    )
    return BookingState.EMAIL_DECISION


def _coerce_positive_int(value, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_booking_reminder_delay_seconds() -> int | None:
    timeout_seconds = _coerce_positive_int(
        getattr(settings, "booking_conversation_timeout_seconds", 900),
        900,
    )
    reminder_before_timeout = _coerce_positive_int(
        getattr(settings, "booking_conversation_reminder_seconds_before_timeout", 120),
        120,
    )
    if timeout_seconds <= 0 or reminder_before_timeout <= 0:
        return None

    reminder_delay = timeout_seconds - reminder_before_timeout
    if reminder_delay <= 0:
        return None

    return reminder_delay


def _cancel_booking_timeout_reminder(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
) -> None:
    job_queue = getattr(context, "job_queue", None)
    if job_queue is None:
        return

    get_jobs_by_name = getattr(job_queue, "get_jobs_by_name", None)
    if get_jobs_by_name is None:
        return

    for job in get_jobs_by_name(_booking_reminder_job_name(user_id)):
        job.schedule_removal()


def _refresh_booking_timeout_reminder(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
) -> None:
    reminder_delay = _get_booking_reminder_delay_seconds()
    if reminder_delay is None:
        _cancel_booking_timeout_reminder(context, user_id)
        return

    job_queue = getattr(context, "job_queue", None)
    if job_queue is None:
        return

    run_once = getattr(job_queue, "run_once", None)
    if run_once is None:
        return

    _cancel_booking_timeout_reminder(context, user_id)
    run_once(
        _send_booking_timeout_reminder,
        when=reminder_delay,
        data={"user_id": user_id},
        name=_booking_reminder_job_name(user_id),
    )


async def _send_booking_timeout_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data if context.job else {}
    user_id = job_data.get("user_id")
    if user_id is None:
        return

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=BOOKING_TIMEOUT_REMINDER_TEXT,
        )
    except Exception:
        logger.warning(
            "Failed to send booking timeout reminder for user_id=%s",
            user_id,
        )


def _profile_reuse_message(data: dict) -> str | None:
    lines = []
    if data.get("name"):
        lines.append(f"Имя: {data['name']}")
    if data.get("timezone"):
        lines.append(f"Часовой пояс: {data['timezone']}")
    if data.get("email_mode") == "saved" and data.get("email"):
        lines.append("Email: используем сохраненный адрес")
    elif data.get("email_mode") == "private":
        lines.append("Email: без личного адреса")
    if not lines:
        return None
    return "Используем сохраненные данные:\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def book_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start booking with only the profile fields the user explicitly saved."""
    _clear_booking_scoped_state(context)
    if not _is_whitelisted(update, context):
        _cancel_booking_timeout_reminder(context, update.effective_user.id)
        await _deny_booking_access(update)
        return ConversationHandler.END

    _refresh_booking_timeout_reminder(context, update.effective_user.id)

    preference_service: UserPreferenceService | None = context.bot_data.get(
        "user_preference_service"
    )
    if preference_service is not None:
        try:
            profile = preference_service.get_profile(update.effective_user.id)
        except Exception as error:
            logger.error(
                "Failed to load booking profile for user_id=%s error_type=%s",
                update.effective_user.id,
                type(error).__name__,
            )
        else:
            remembered_fields = set()
            if profile is not None:
                if profile.preferred_name:
                    context.user_data["name"] = profile.preferred_name
                    remembered_fields.add("name")
                context.user_data["email_mode"] = profile.email_mode
                if profile.email_mode == "saved" and profile.email:
                    context.user_data["email"] = profile.email
                    remembered_fields.add("email")
                elif profile.email_mode == "private":
                    context.user_data["email"] = None
                    remembered_fields.add("private")

            if profile is not None and profile.timezone in SUPPORTED_TIMEZONE_IDS:
                context.user_data["timezone"] = profile.timezone
                context.user_data["offset_days"] = 0
                remembered_fields.add("timezone")
                context.user_data["remembered_profile_fields"] = remembered_fields
                target = _MessageReplyTarget(
                    update.message,
                    update.effective_user.id,
                    prefix=_profile_reuse_message(context.user_data),
                )
                return await _handle_duration_selection(target, context)
            if profile is not None and profile.timezone is not None:
                logger.warning(
                    "Ignoring unsupported timezone in booking profile for user_id=%s",
                    update.effective_user.id,
                )
            if remembered_fields:
                context.user_data["remembered_profile_fields"] = remembered_fields

    keyboard = build_timezone_keyboard()
    prefix = _profile_reuse_message(context.user_data)
    message = "Выберите ваш часовой пояс:"
    if prefix:
        message = f"{prefix}\n\n{message}"
    await update.message.reply_text(
        message,
        reply_markup=keyboard,
    )
    return BookingState.SELECTING_TIMEZONE


# ---------------------------------------------------------------------------
# Timezone selection
# ---------------------------------------------------------------------------


async def select_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle timezone selection and show duration options or fetch availability."""
    query = update.callback_query
    await query.answer()

    timezone_id = _timezone_from_callback(query.data)
    if timezone_id is None:
        return BookingState.SELECTING_TIMEZONE

    context.user_data["timezone"] = timezone_id
    context.user_data["offset_days"] = 0
    _refresh_booking_timeout_reminder(context, query.from_user.id)

    if context.user_data.pop("edit_field", None) == "timezone":
        return await _show_remembering_edit(query, context)

    return await _handle_duration_selection(query, context)


def _timezone_from_callback(callback_data: str) -> str | None:
    """Resolve current opaque timezone callbacks and tolerate old rendered keyboards."""
    try:
        value = callback_data.split(":", 1)[1]
    except IndexError:
        return None

    try:
        index = int(value)
    except ValueError:
        return value if value in SUPPORTED_TIMEZONE_IDS else None

    if index < 0 or index >= len(RUSSIAN_TIMEZONES):
        return None
    return RUSSIAN_TIMEZONES[index][0]


async def _handle_duration_selection(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Check duration limits and show duration picker or auto-select."""
    user_id = query.from_user.id
    _refresh_booking_timeout_reminder(context, user_id)
    max_duration = _get_duration_limit(context, user_id)

    if max_duration is not None:
        if max_duration == 120:
            return await _show_fifth_step_warning(query, context)
        # User has a limit — auto-select that duration, skip picker
        context.user_data.pop("pending_duration", None)
        context.user_data["duration"] = max_duration
        return await _show_availability(query, context, offset_days=0)

    return await _show_duration_picker(query, context)


async def _show_duration_picker(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show durations allowed by the user's current limit."""
    max_duration = _get_duration_limit(context, query.from_user.id)
    keyboard = build_duration_keyboard(max_duration=max_duration)
    await _safe_edit_message_text(
        query,
        "Выберите длительность встречи:",
        reply_markup=keyboard,
    )
    return BookingState.SELECTING_DURATION


async def select_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle duration selection and fetch availability."""
    query = update.callback_query
    await query.answer()

    try:
        duration = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return BookingState.SELECTING_DURATION

    if duration not in DURATION_OPTIONS:
        return BookingState.SELECTING_DURATION

    duration = _apply_current_duration_limit(context, query.from_user.id, duration)
    _refresh_booking_timeout_reminder(context, query.from_user.id)

    if duration == 120:
        return await _show_fifth_step_warning(query, context)

    context.user_data["duration"] = duration
    context.user_data.pop("pending_duration", None)
    return await _show_availability(query, context, offset_days=0)


async def _show_fifth_step_warning(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Require acknowledgement before showing 120-minute availability."""
    context.user_data.pop("duration", None)
    context.user_data["pending_duration"] = 120
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Продолжить (5-й шаг)",
                    callback_data=FIFTH_STEP_CONFIRM_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    "Изменить длительность",
                    callback_data=CHANGE_DURATION_CALLBACK,
                )
            ],
        ]
    )
    await _safe_edit_message_text(query, FIFTH_STEP_WARNING_TEXT, reply_markup=keyboard)
    return BookingState.SELECTING_DURATION


async def acknowledge_fifth_step_duration(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Continue to availability after acknowledging fifth-step-only usage."""
    query = update.callback_query
    await query.answer()
    _refresh_booking_timeout_reminder(context, query.from_user.id)

    if context.user_data.get("pending_duration") != 120:
        return await _show_duration_picker(query, context)

    duration = _apply_current_duration_limit(context, query.from_user.id, 120)
    context.user_data.pop("pending_duration", None)
    context.user_data["duration"] = duration
    return await _show_availability(query, context, offset_days=0)


async def change_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return from the fifth-step warning to duration selection."""
    query = update.callback_query
    await query.answer()
    _refresh_booking_timeout_reminder(context, query.from_user.id)
    context.user_data.pop("pending_duration", None)
    context.user_data.pop("duration", None)
    return await _show_duration_picker(query, context)


async def change_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back to timezone selection."""
    query = update.callback_query
    await query.answer()
    _refresh_booking_timeout_reminder(context, query.from_user.id)

    keyboard = build_timezone_keyboard()
    await _safe_edit_message_text(
        query,
        "Выберите ваш часовой пояс:",
        reply_markup=keyboard,
    )
    return BookingState.SELECTING_TIMEZONE


# ---------------------------------------------------------------------------
# Availability display
# ---------------------------------------------------------------------------


async def _show_availability(
    query, context: ContextTypes.DEFAULT_TYPE, offset_days: int = 0
) -> int:
    """Fetch and display availability for the user's timezone."""
    await _safe_edit_message_text(query, "Загружаю доступное время...")
    _refresh_booking_timeout_reminder(context, query.from_user.id)

    calcom_client: CalComClient = context.bot_data["calcom_client"]
    timezone_id = context.user_data["timezone"]
    duration = _apply_current_duration_limit(
        context,
        query.from_user.id,
        context.user_data.get("duration", 30),
    )
    context.user_data["duration"] = duration
    today = date.today()

    try:
        resolved_event_type = settings.resolve_event_type(duration)
        availability = await calcom_client.get_availability(
            event_type_id=resolved_event_type.event_type_id,
            start_date=today + timedelta(days=offset_days),
            end_date=today + timedelta(days=offset_days + 14),
            timezone=timezone_id,
            duration_minutes=resolved_event_type.duration_minutes,
        )

        has_slots = any(availability.slots.values())
        if not has_slots:
            await _safe_edit_message_text(
                query,
                "Нет доступного времени на этот период.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(TIMEZONE_BUTTON_LABEL, callback_data="change_tz"),
                            InlineKeyboardButton("Отмена", callback_data="cancel"),
                        ]
                    ]
                ),
            )
            return BookingState.VIEWING_AVAILABILITY

        keyboard = build_availability_keyboard(availability.slots, offset_days)
        await _safe_edit_message_text(
            query,
            f"Доступное время ({timezone_id}):\n\nНажмите на удобное время:",
            reply_markup=keyboard,
        )
        return BookingState.VIEWING_AVAILABILITY

    except (CalComAPIError, ValueError) as error:
        logger.error(
            "Failed to load availability for user_id=%s duration=%s error_type=%s",
            query.from_user.id,
            duration,
            type(error).__name__,
        )
        await _safe_edit_message_text(
            query,
            "Извините, не удалось загрузить расписание. Попробуйте ещё раз.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Попробовать снова",
                            callback_data="retry:availability",
                        ),
                    ],
                    [
                        InlineKeyboardButton(TIMEZONE_BUTTON_LABEL, callback_data="change_tz"),
                        InlineKeyboardButton("Отмена", callback_data="cancel"),
                    ],
                ]
            ),
        )
        return BookingState.VIEWING_AVAILABILITY


async def load_more_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Load more dates (pagination)."""
    query = update.callback_query
    await query.answer()

    offset_days = int(query.data.split(":")[1])
    context.user_data["offset_days"] = offset_days
    return await _show_availability(query, context, offset_days=offset_days)


async def retry_availability(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Retry availability using transient booking state, not callback values."""
    query = update.callback_query
    await query.answer()
    offset_days = context.user_data.get("offset_days", 0)
    return await _show_availability(query, context, offset_days=offset_days)


async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """No-op handler for day header buttons."""
    query = update.callback_query
    await query.answer()
    _refresh_booking_timeout_reminder(context, query.from_user.id)
    return BookingState.VIEWING_AVAILABILITY


# ---------------------------------------------------------------------------
# Slot selection
# ---------------------------------------------------------------------------


async def select_slot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle a time slot and reuse explicitly remembered contact fields."""
    query = update.callback_query
    await query.answer()
    _refresh_booking_timeout_reminder(context, query.from_user.id)

    # callback_data format: "slot:<date>:<time_iso>"
    parts = query.data.split(":", 2)
    context.user_data["selected_date"] = parts[1]
    context.user_data["selected_time"] = parts[2]

    if context.user_data.get("name"):
        return await _continue_after_name_edit(query, context, reused=True)

    await _safe_edit_message_text(query, "Введите ваше имя:")
    return BookingState.ENTERING_NAME


# ---------------------------------------------------------------------------
# Name collection
# ---------------------------------------------------------------------------


async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store user's name and ask about email."""
    _refresh_booking_timeout_reminder(context, update.effective_user.id)
    name = update.message.text.strip()

    if not name:
        await update.message.reply_text("Имя не может быть пустым. Введите ваше имя:")
        return BookingState.ENTERING_NAME

    if len(name) > MAX_NAME_LENGTH:
        await update.message.reply_text(
            f"Имя слишком длинное (максимум {MAX_NAME_LENGTH} символов). "
            "Введите более короткое имя:"
        )
        return BookingState.ENTERING_NAME

    context.user_data["name"] = name

    if context.user_data.pop("edit_field", None) == "name":
        await _show_remembering_message(update.message, context)
        return BookingState.REMEMBERING_PROFILE

    if _has_reusable_email_choice(context.user_data):
        await _show_remembering_message(update.message, context, reused=True)
        return BookingState.REMEMBERING_PROFILE

    keyboard = _email_decision_keyboard()
    await update.message.reply_text(
        f"Отлично, {name}! Хотите указать email для подтверждения?",
        reply_markup=keyboard,
    )
    return BookingState.EMAIL_DECISION


# ---------------------------------------------------------------------------
# Email decision
# ---------------------------------------------------------------------------


async def email_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle yes/no email decision."""
    query = update.callback_query
    await query.answer()
    _refresh_booking_timeout_reminder(context, query.from_user.id)

    if query.data == "email_yes":
        await _safe_edit_message_text(query, "Введите ваш email:")
        return BookingState.ENTERING_EMAIL
    else:
        context.user_data["email"] = None
        context.user_data["email_mode"] = "private"
        return await _show_remembering_edit(query, context)


async def enter_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store email and show confirmation."""
    _refresh_booking_timeout_reminder(context, update.effective_user.id)
    email = update.message.text.strip()

    if len(email) > MAX_EMAIL_LENGTH:
        await update.message.reply_text(
            f"Email слишком длинный. Введите до {MAX_EMAIL_LENGTH} символов:"
        )
        return BookingState.ENTERING_EMAIL

    if "@" not in email or "." not in email.split("@")[-1]:
        await update.message.reply_text("Некорректный email. Попробуйте ещё раз:")
        return BookingState.ENTERING_EMAIL

    context.user_data["email"] = email
    context.user_data["email_mode"] = "saved"
    context.user_data.pop("edit_field", None)
    await _show_remembering_message(update.message, context)
    return BookingState.REMEMBERING_PROFILE


async def _continue_after_name_edit(query, context, *, reused: bool = False) -> int:
    """Continue from name using only an explicitly remembered email choice."""
    if _has_reusable_email_choice(context.user_data):
        return await _show_remembering_edit(query, context, reused=reused)

    prefix = "Используем сохраненное имя.\n\n" if reused else ""
    await _safe_edit_message_text(
        query,
        f"{prefix}Хотите указать email для подтверждения?",
        reply_markup=_email_decision_keyboard(),
    )
    return BookingState.EMAIL_DECISION


def _has_reusable_email_choice(data: dict) -> bool:
    mode = data.get("email_mode")
    return (mode == "saved" and bool(data.get("email"))) or mode == "private"


def _email_decision_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Да, указать email", callback_data="email_yes"),
                InlineKeyboardButton("Нет, пропустить", callback_data="email_no"),
            ]
        ]
    )


# ---------------------------------------------------------------------------
# Granular profile consent
# ---------------------------------------------------------------------------


async def _show_remembering_edit(query, context, *, reused: bool = False) -> int:
    await _safe_edit_message_text(
        query,
        _remembering_text(context.user_data, reused=reused),
        reply_markup=_remembering_keyboard(context.user_data),
    )
    return BookingState.REMEMBERING_PROFILE


async def _show_remembering_message(message, context, *, reused: bool = False) -> None:
    await message.reply_text(
        _remembering_text(context.user_data, reused=reused),
        reply_markup=_remembering_keyboard(context.user_data),
    )


def _remembering_text(data: dict, *, reused: bool = False) -> str:
    reuse_message = _profile_reuse_message(data) if reused else None
    prefix = f"{reuse_message}\n\n" if reuse_message else ""
    return (
        f"{prefix}Какие данные запомнить для следующих записей?\n\n"
        "Уже сохраненные поля отмечены отдельно. "
        "Сохранится только то, что вы явно выберете. "
        "Можно продолжить, ничего не сохраняя."
    )


def _remembering_keyboard(data: dict) -> InlineKeyboardMarkup:
    choices = set(data.get("remember_choices", set()))
    remembered = set(data.get("remembered_profile_fields", set()))
    buttons = []

    def option(label: str, field: str) -> None:
        if field in remembered:
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"✓ {label} — уже сохранено",
                        callback_data="remember:kept",
                    )
                ]
            )
            return
        marker = "✓ " if field in choices else ""
        buttons.append(
            [InlineKeyboardButton(f"{marker}{label}", callback_data=f"remember:{field}")]
        )

    option("Запомнить имя", "name")
    option("Запомнить часовой пояс", "timezone")
    if data.get("email"):
        option("Запомнить email", "email")
    else:
        option("Предпочитать запись без личного email", "private")
    buttons.append([InlineKeyboardButton("Сохранить выбранное", callback_data="remember:save")])
    buttons.append([InlineKeyboardButton("Ничего не сохранять", callback_data="remember:none")])
    buttons.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


async def remember_profile_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Toggle granular consent or persist only the selected profile fields."""
    query = update.callback_query
    await query.answer()
    _refresh_booking_timeout_reminder(context, query.from_user.id)
    action = query.data.split(":", 1)[1]
    remembered = set(context.user_data.get("remembered_profile_fields", set()))

    if action == "kept":
        return BookingState.REMEMBERING_PROFILE

    if action == "none":
        context.user_data.pop("remember_choices", None)
        return await _show_confirmation_edit(query, context)

    if action == "save":
        notice = _persist_profile_choices(
            context,
            query.from_user.id,
            set(context.user_data.get("remember_choices", set())) - remembered,
        )
        context.user_data.pop("remember_choices", None)
        return await _show_confirmation_edit(query, context, notice=notice)

    available = {"name", "timezone"}
    available.add("email" if context.user_data.get("email") else "private")
    available -= remembered
    if action not in available:
        return BookingState.REMEMBERING_PROFILE

    choices = set(context.user_data.get("remember_choices", set()))
    if action in choices:
        choices.remove(action)
    else:
        choices.add(action)
    context.user_data["remember_choices"] = choices
    return await _show_remembering_edit(query, context)


def _persist_profile_choices(context, user_id: int, choices: set[str]) -> str | None:
    if not choices:
        return "Новые данные не сохранены."

    profile_service: UserPreferenceService | None = context.bot_data.get("user_preference_service")
    if profile_service is None:
        return "Не удалось сохранить выбранные данные. Запись продолжится без изменений профиля."

    data = context.user_data
    operations = {
        "name": lambda: profile_service.save_preferred_name(user_id, data["name"]),
        "timezone": lambda: profile_service.save_timezone(user_id, data["timezone"]),
        "email": lambda: profile_service.save_email(user_id, data["email"]),
        "private": lambda: profile_service.save_private_email_mode(user_id),
    }
    labels = {
        "name": "имя",
        "timezone": "часовой пояс",
        "email": "email",
        "private": "режим без личного email",
    }
    saved = []
    failed = False
    for field in ("name", "timezone", "email", "private"):
        if field not in choices:
            continue
        try:
            operations[field]()
        except Exception as error:
            failed = True
            logger.error(
                "Failed to persist selected booking profile field for user_id=%s error_type=%s",
                user_id,
                type(error).__name__,
            )
        else:
            saved.append(labels[field])

    if failed:
        return "Не все выбранные данные удалось сохранить. Запись продолжится."
    return f"Сохранено для следующих записей: {', '.join(saved)}."


# ---------------------------------------------------------------------------
# Confirmation display helpers
# ---------------------------------------------------------------------------


async def _show_confirmation_edit(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    notice: str | None = None,
) -> int:
    """Edit message to show booking confirmation."""
    text = _build_confirmation_text(context.user_data)
    if notice:
        text = f"{notice}\n\n{text}"
    keyboard = _confirmation_keyboard()
    await _safe_edit_message_text(query, text, reply_markup=keyboard)
    return BookingState.CONFIRMING


async def _show_confirmation_message(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send new message with booking confirmation."""
    text = _build_confirmation_text(context.user_data)
    keyboard = _confirmation_keyboard()
    await message.reply_text(text, reply_markup=keyboard)


def _build_confirmation_text(data: dict) -> str:
    formatted_time = _format_datetime_display(
        data["selected_date"],
        data["selected_time"],
        data["timezone"],
    )
    duration = data.get("duration", 30)
    duration_text = DURATION_OPTIONS.get(duration, f"{duration} мин.")
    email_value = data.get("email") or "без личного email"
    email_line = f"\nEmail: {email_value}"
    fifth_step_warning = f"\n\nВажно: {FIFTH_STEP_RESTRICTION_TEXT}" if duration == 120 else ""
    return (
        f"Подтвердите запись:\n\n"
        f"Время: {formatted_time}\n"
        f"Длительность: {duration_text}\n"
        f"Имя: {data['name']}"
        f"{email_line}"
        f"{fifth_step_warning}\n\n"
        f"Нажмите «Подтвердить запись» для продолжения."
    )


def _confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Подтвердить запись", callback_data="confirm"),
                InlineKeyboardButton("Отмена", callback_data="cancel"),
            ],
            [InlineKeyboardButton("Изменить данные", callback_data="edit:data")],
        ]
    )


async def edit_booking_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show value-free controls for changing effective booking details."""
    query = update.callback_query
    await query.answer()
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Изменить имя", callback_data="edit:name"),
                InlineKeyboardButton("Изменить часовой пояс", callback_data="edit:timezone"),
            ],
            [
                InlineKeyboardButton("Изменить email", callback_data="edit:email"),
                InlineKeyboardButton("Без личного email", callback_data="edit:private"),
            ],
            [InlineKeyboardButton("Назад", callback_data="edit:back")],
        ]
    )
    await _safe_edit_message_text(
        query,
        "Что изменить в данных этой записи?",
        reply_markup=keyboard,
    )
    return BookingState.CONFIRMING


async def edit_booking_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collect one changed booking value without changing saved consent."""
    query = update.callback_query
    await query.answer()
    field = query.data.split(":", 1)[1]

    if field == "back":
        return await _show_confirmation_edit(query, context)
    if field == "name":
        _mark_profile_field_transient(context.user_data, "name")
        context.user_data["edit_field"] = "name"
        await _safe_edit_message_text(query, "Введите имя для этой записи:")
        return BookingState.ENTERING_NAME
    if field == "timezone":
        _mark_profile_field_transient(context.user_data, "timezone")
        context.user_data["edit_field"] = "timezone"
        await _safe_edit_message_text(
            query,
            "Выберите часовой пояс для этой записи:",
            reply_markup=build_timezone_keyboard(),
        )
        return BookingState.SELECTING_TIMEZONE
    if field == "email":
        _mark_profile_field_transient(context.user_data, "email")
        context.user_data["edit_field"] = "email"
        await _safe_edit_message_text(query, "Введите email для этой записи:")
        return BookingState.ENTERING_EMAIL
    if field == "private":
        _mark_profile_field_transient(context.user_data, "private")
        context.user_data["email"] = None
        context.user_data["email_mode"] = "private"
        return await _show_remembering_edit(query, context)
    return BookingState.CONFIRMING


def _mark_profile_field_transient(data: dict, field: str) -> None:
    remembered = set(data.get("remembered_profile_fields", set()))
    if field in {"email", "private"}:
        remembered.difference_update({"email", "private"})
    else:
        remembered.discard(field)
    data["remembered_profile_fields"] = remembered


# ---------------------------------------------------------------------------
# Booking creation
# ---------------------------------------------------------------------------


async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Create the booking via Cal.com API."""
    if not _is_whitelisted(update, context):
        _cancel_booking_timeout_reminder(context, update.effective_user.id)
        await _deny_booking_access(update)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    _refresh_booking_timeout_reminder(context, query.from_user.id)

    await _safe_edit_message_text(query, "Создаю запись...")

    data = context.user_data
    calcom_client: CalComClient = context.bot_data["calcom_client"]
    personal_email = data.get("email")
    email = personal_email or _privacy_email()
    if email is None:
        logger.error("Cal.com privacy email is not configured")
        return await _show_privacy_email_unavailable(query)

    internal_ref = _booking_reference(data)
    duration = _apply_current_duration_limit(
        context,
        update.effective_user.id,
        data.get("duration", 30),
    )
    data["duration"] = duration

    try:
        resolved_event_type = settings.resolve_event_type(duration)
        start_utc = slot_to_utc(data["selected_time"])
        logger.info(
            "Creating booking for user_id=%s event_type_id=%s start_utc=%s",
            update.effective_user.id,
            resolved_event_type.event_type_id,
            start_utc,
        )

        booking = await calcom_client.create_booking(
            BookingRequest(
                eventTypeId=resolved_event_type.event_type_id,
                start=start_utc,
                lengthInMinutes=resolved_event_type.duration_minutes,
                attendee=Attendee(
                    name=data["name"],
                    email=email,
                    timeZone=data["timezone"],
                ),
                metadata={
                    "telecalbot_booking_ref": internal_ref,
                    "booked_via": "telegram_bot",
                },
            )
        )
        booking_service: BookingService | None = context.bot_data.get("booking_service")
        if booking_service is not None:
            try:
                booking_service.save_booking(
                    update.effective_user.id,
                    booking,
                    internal_ref=internal_ref,
                )
            except Exception as error:
                logger.error(
                    "Failed to persist booking for user_id=%s booking_id=%s error_type=%s",
                    update.effective_user.id,
                    booking.id,
                    type(error).__name__,
                )

        logger.info(
            "Booking created for user_id=%s booking_id=%s booking_uid=%s status=%s",
            update.effective_user.id,
            booking.id,
            booking.uid,
            booking.status,
        )

        formatted_time = _format_datetime_display(
            data["selected_date"],
            data["selected_time"],
            data["timezone"],
        )
        duration_str = _format_duration(booking)
        email_note = f"\nПисьмо с подтверждением отправлено на {email}." if personal_email else ""

        await _safe_edit_message_text(
            query,
            f"Готово! Ваша встреча подтверждена.\n\n"
            f"Время: {formatted_time}\n"
            f"Длительность: {duration_str}\n\n"
            f"Мы свяжемся через Telegram в назначенное время."
            f"{email_note}",
        )
        _cancel_booking_timeout_reminder(context, update.effective_user.id)
        return ConversationHandler.END

    except CalComAPIError as e:
        logger.warning(
            "Booking create failed for user_id=%s status=%s code=%s",
            update.effective_user.id,
            e.status_code,
            e.code,
        )
        if e.code == EMAIL_DOMAIN_CANNOT_RECEIVE_MAIL:
            if not personal_email:
                return await _show_privacy_email_unavailable(query)

            _mark_profile_field_transient(data, "email")
            data.pop("email", None)
            await _safe_edit_message_text(
                query,
                "Cal.com не принимает этот email. Укажите другой адрес или отмените запись командой /cancel.",
            )
            return BookingState.ENTERING_EMAIL
        if e.status_code == 409:
            error_msg = "Это время уже занято. Пожалуйста, выберите другое время."
        else:
            error_msg = "Извините, что-то пошло не так. Попробуйте ещё раз."

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Выбрать другое время",
                        callback_data="retry:availability",
                    ),
                    InlineKeyboardButton("Отмена", callback_data="cancel"),
                ]
            ]
        )
        await _safe_edit_message_text(query, error_msg, reply_markup=keyboard)
        return BookingState.VIEWING_AVAILABILITY
    except Exception as error:
        logger.error(
            "Unexpected error while creating booking for user_id=%s error_type=%s",
            update.effective_user.id,
            type(error).__name__,
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Выбрать другое время",
                        callback_data="retry:availability",
                    ),
                    InlineKeyboardButton("Отмена", callback_data="cancel"),
                ]
            ]
        )
        await _safe_edit_message_text(
            query,
            "Извините, что-то пошло не так. Попробуйте ещё раз.",
            reply_markup=keyboard,
        )
        return BookingState.VIEWING_AVAILABILITY


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the booking conversation."""
    query = update.callback_query
    if query:
        await query.answer()
        await _safe_edit_message_text(query, "Запись отменена.")
    else:
        await update.message.reply_text("Запись отменена.")

    if update.effective_user:
        _cancel_booking_timeout_reminder(context, update.effective_user.id)
    context.user_data.clear()
    return ConversationHandler.END


async def booking_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End stale booking conversation and ask user to restart."""
    logger.info(
        "Booking conversation timed out for user_id=%s",
        update.effective_user.id if update.effective_user else "unknown",
    )

    query = update.callback_query
    timeout_text = (
        "Сессия записи истекла из-за неактивности.\nПожалуйста, начните заново командой /book."
    )
    try:
        if query:
            await _safe_edit_message_text(query, timeout_text)
        elif update.message:
            await update.message.reply_text(timeout_text)
    finally:
        if update.effective_user:
            _cancel_booking_timeout_reminder(context, update.effective_user.id)
        context.user_data.clear()

    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Cancel existing booking command
# ---------------------------------------------------------------------------


async def cancel_booking_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user bookings and let them choose one for cancellation."""
    booking_service: BookingService = context.bot_data["booking_service"]
    user_id = update.effective_user.id

    if not _user_can_use_cancel_booking_flow(context, user_id):
        await _deny_cancel_booking_flow_access(update)
        return

    bookings = booking_service.list_upcoming_bookings(user_id)
    if not bookings:
        await update.message.reply_text("У вас нет предстоящих записей для отмены.")
        return

    await update.message.reply_text(
        "Выберите запись для отмены:",
        reply_markup=build_cancel_booking_keyboard(bookings),
    )


async def cancel_booking_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle booking selection and show confirmation prompt."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not _user_can_use_cancel_booking_flow(context, user_id):
        await _deny_cancel_booking_flow_access(update)
        return

    booking_service: BookingService = context.bot_data["booking_service"]
    booking_row_id = _parse_booking_row_id(query.data, CANCEL_SELECT_PREFIX)
    if booking_row_id is None:
        await _safe_edit_message_text(query, "Некорректный выбор записи.")
        return

    booking = booking_service.get_booking_for_user(booking_row_id, user_id)
    if booking is None or booking.status != "active":
        await _safe_edit_message_text(query, "Эта запись не найдена или уже была отменена.")
        return

    await _safe_edit_message_text(
        query,
        (f"Вы уверены, что хотите отменить запись?\n\n{_format_stored_booking_summary(booking)}"),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Да, отменить",
                        callback_data=f"{CANCEL_CONFIRM_PREFIX}{booking.id}",
                    ),
                    InlineKeyboardButton(
                        "Назад",
                        callback_data=CANCEL_BACK_CALLBACK,
                    ),
                ]
            ]
        ),
    )


async def cancel_booking_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel selected booking in Cal.com and mark it cancelled locally."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not _user_can_use_cancel_booking_flow(context, user_id):
        await _deny_cancel_booking_flow_access(update)
        return

    booking_service: BookingService = context.bot_data["booking_service"]
    calcom_client: CalComClient = context.bot_data["calcom_client"]
    booking_row_id = _parse_booking_row_id(query.data, CANCEL_CONFIRM_PREFIX)
    if booking_row_id is None:
        await _safe_edit_message_text(query, "Некорректный выбор записи.")
        return

    booking = booking_service.get_booking_for_user(booking_row_id, user_id)
    if booking is None or booking.status != "active":
        await _safe_edit_message_text(query, "Эта запись не найдена или уже была отменена.")
        return

    try:
        await calcom_client.cancel_booking(booking.calcom_booking_uid)
    except CalComAPIError as error:
        if error.status_code in CANCEL_BOOKING_TERMINAL_STATUS_CODES:
            booking_service.mark_cancelled(booking_row_id, user_id)
            await _safe_edit_message_text(
                query,
                (f"Запись уже была отменена.\n\n{_format_stored_booking_summary(booking)}"),
            )
            return

        await _safe_edit_message_text(
            query,
            "Не удалось отменить запись. Попробуйте позже.",
        )
        return

    booking_service.mark_cancelled(booking_row_id, user_id)
    await _safe_edit_message_text(
        query,
        (f"Запись успешно отменена.\n\n{_format_stored_booking_summary(booking)}"),
    )


async def cancel_booking_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return from confirmation screen to booking list."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not _user_can_use_cancel_booking_flow(context, user_id):
        await _deny_cancel_booking_flow_access(update)
        return

    booking_service: BookingService = context.bot_data["booking_service"]
    bookings = booking_service.list_upcoming_bookings(user_id)
    if not bookings:
        await _safe_edit_message_text(query, "У вас нет предстоящих записей для отмены.")
        return

    await _safe_edit_message_text(
        query,
        "Выберите запись для отмены:",
        reply_markup=build_cancel_booking_keyboard(bookings),
    )


def create_cancel_booking_flow_handlers() -> list:
    """Create handlers for /cancel_booking flow."""
    return [
        CommandHandler("cancel_booking", cancel_booking_command),
        CallbackQueryHandler(
            cancel_booking_select,
            pattern=rf"^{CANCEL_SELECT_PREFIX}\d+$",
        ),
        CallbackQueryHandler(
            cancel_booking_confirm,
            pattern=rf"^{CANCEL_CONFIRM_PREFIX}\d+$",
        ),
        CallbackQueryHandler(
            cancel_booking_back,
            pattern=rf"^{CANCEL_BACK_CALLBACK}$",
        ),
    ]


# ---------------------------------------------------------------------------
# Keyboard builders
# ---------------------------------------------------------------------------


def build_timezone_keyboard() -> InlineKeyboardMarkup:
    """Build timezone selection keyboard."""
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"tz:{index}")]
        for index, (_, label) in enumerate(RUSSIAN_TIMEZONES)
    ]
    buttons.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


def build_duration_keyboard(max_duration: int | None = None) -> InlineKeyboardMarkup:
    """Build duration selection keyboard."""
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"duration:{minutes}")]
        for minutes, label in DURATION_OPTIONS.items()
        if max_duration is None or minutes <= max_duration
    ]
    buttons.append([InlineKeyboardButton(TIMEZONE_BUTTON_LABEL, callback_data="change_tz")])
    buttons.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


def build_availability_keyboard(
    slots: dict,
    offset_days: int = 0,
) -> InlineKeyboardMarkup:
    """Build availability keyboard grouped by day (max 5 days, 6 slots/day)."""
    buttons = []

    for date_str, time_slots in sorted(slots.items())[:5]:
        if not time_slots:
            continue

        day_name = format_date_header(date_str)
        buttons.append([InlineKeyboardButton(f"— {day_name} —", callback_data="noop")])

        sorted_time_slots = sorted(time_slots, key=lambda slot: slot.time)
        time_buttons = []
        for slot in sorted_time_slots[:6]:
            display = format_time(slot.time)
            callback = f"slot:{date_str}:{slot.time}"
            time_buttons.append(InlineKeyboardButton(display, callback_data=callback))
            if len(time_buttons) == 3:
                buttons.append(time_buttons)
                time_buttons = []

        if time_buttons:
            buttons.append(time_buttons)

    nav_row = []
    if offset_days > 0:
        nav_row.append(InlineKeyboardButton("← Назад", callback_data=f"dates:{offset_days - 5}"))
    nav_row.append(InlineKeyboardButton("Ещё даты →", callback_data=f"dates:{offset_days + 5}"))
    buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(TIMEZONE_BUTTON_LABEL, callback_data="change_tz")])
    buttons.append([InlineKeyboardButton("Отмена", callback_data="cancel")])

    return InlineKeyboardMarkup(buttons)


def build_cancel_booking_keyboard(bookings: list) -> InlineKeyboardMarkup:
    """Build keyboard with user's upcoming bookings."""
    buttons = [
        [
            InlineKeyboardButton(
                _format_stored_booking_button_text(booking),
                callback_data=f"{CANCEL_SELECT_PREFIX}{booking.id}",
            )
        ]
        for booking in bookings
    ]
    return InlineKeyboardMarkup(buttons)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_date_header(date_str: str) -> str:
    """Format 'YYYY-MM-DD' to 'Понедельник, 6 янв'."""
    dt = date.fromisoformat(date_str)
    weekday = RUSSIAN_WEEKDAYS[dt.weekday()]
    month_abbr = RUSSIAN_MONTHS_ABBR[dt.month - 1]
    return f"{weekday}, {dt.day} {month_abbr}"


def format_time(time_iso: str) -> str:
    """Format ISO datetime string to '14:00'."""
    dt = datetime.fromisoformat(time_iso)
    return dt.strftime("%H:%M")


def slot_to_utc(time_iso: str) -> str:
    """Convert offset-aware ISO datetime to UTC ISO string."""
    dt = datetime.fromisoformat(time_iso)
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_duration(booking: BookingResponse) -> str:
    """Derive human-readable duration from booking start/end times."""
    start = datetime.fromisoformat(booking.start)
    end = datetime.fromisoformat(booking.end)
    minutes = int((end - start).total_seconds() // 60)
    if minutes >= 60 and minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} ч."
    return f"{minutes} мин."


def _format_datetime_display(date_str: str, time_iso: str, tz_id: str) -> str:
    """Format date and time for user-facing display."""
    dt = datetime.fromisoformat(time_iso)
    weekday = RUSSIAN_WEEKDAYS[dt.weekday()]
    month_abbr = RUSSIAN_MONTHS_ABBR[dt.month - 1]
    time_value = dt.strftime("%H:%M")
    return f"{weekday}, {dt.day} {month_abbr} в {time_value} ({tz_id})"


def _parse_booking_row_id(callback_data: str, prefix: str) -> int | None:
    if not callback_data.startswith(prefix):
        return None
    try:
        return int(callback_data[len(prefix) :])
    except ValueError:
        return None


def _user_can_use_cancel_booking_flow(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
) -> bool:
    whitelist_service: WhitelistService | None = context.bot_data.get("whitelist_service")
    if whitelist_service is None:
        logger.error("Whitelist service is missing in bot_data; denying cancel booking flow")
        return False
    return whitelist_service.is_whitelisted(user_id)


async def _deny_cancel_booking_flow_access(update: Update) -> None:
    query = update.callback_query
    if query:
        await _safe_edit_message_text(query, CANCEL_BOOKING_ACCESS_DENIED_TEXT)
        return

    if update.message:
        await update.message.reply_text(CANCEL_BOOKING_ACCESS_DENIED_TEXT)


def _format_stored_booking_button_text(booking) -> str:
    start = booking.start.astimezone(timezone.utc)
    return f"{start.strftime('%d.%m %H:%M UTC')} — {booking.title}"


def _format_stored_booking_summary(booking) -> str:
    start = booking.start.astimezone(timezone.utc)
    end = booking.end.astimezone(timezone.utc)
    return (
        f"{booking.title}\n"
        f"Начало: {start.strftime('%d.%m.%Y %H:%M UTC')}\n"
        f"Окончание: {end.strftime('%d.%m.%Y %H:%M UTC')}"
    )


# ---------------------------------------------------------------------------
# ConversationHandler factory
# ---------------------------------------------------------------------------


def create_booking_conversation_handler() -> ConversationHandler:
    """Create and return the booking ConversationHandler."""
    return ConversationHandler(
        entry_points=[CommandHandler("book", book_command)],
        states={
            BookingState.SELECTING_TIMEZONE: [
                CallbackQueryHandler(select_timezone, pattern="^tz:"),
                CallbackQueryHandler(cancel, pattern="^cancel$"),
            ],
            BookingState.SELECTING_DURATION: [
                CallbackQueryHandler(select_duration, pattern="^duration:"),
                CallbackQueryHandler(
                    acknowledge_fifth_step_duration,
                    pattern=f"^{FIFTH_STEP_CONFIRM_CALLBACK}$",
                ),
                CallbackQueryHandler(change_duration, pattern=f"^{CHANGE_DURATION_CALLBACK}$"),
                CallbackQueryHandler(change_timezone, pattern="^change_tz$"),
                CallbackQueryHandler(cancel, pattern="^cancel$"),
            ],
            BookingState.VIEWING_AVAILABILITY: [
                CallbackQueryHandler(select_slot, pattern="^slot:"),
                CallbackQueryHandler(load_more_dates, pattern="^dates:"),
                CallbackQueryHandler(retry_availability, pattern="^retry:availability$"),
                CallbackQueryHandler(change_timezone, pattern="^change_tz$"),
                CallbackQueryHandler(select_timezone, pattern="^tz:"),
                CallbackQueryHandler(noop, pattern="^noop$"),
                CallbackQueryHandler(cancel, pattern="^cancel$"),
            ],
            BookingState.ENTERING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name),
            ],
            BookingState.EMAIL_DECISION: [
                CallbackQueryHandler(email_decision, pattern="^email_"),
                CallbackQueryHandler(cancel, pattern="^cancel$"),
            ],
            BookingState.ENTERING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_email),
            ],
            BookingState.REMEMBERING_PROFILE: [
                CallbackQueryHandler(remember_profile_choice, pattern="^remember:"),
                CallbackQueryHandler(cancel, pattern="^cancel$"),
            ],
            BookingState.CONFIRMING: [
                CallbackQueryHandler(confirm_booking, pattern="^confirm$"),
                CallbackQueryHandler(edit_booking_data, pattern="^edit:data$"),
                CallbackQueryHandler(
                    edit_booking_field, pattern="^edit:(name|timezone|email|private|back)$"
                ),
                CallbackQueryHandler(cancel, pattern="^cancel$"),
            ],
            ConversationHandler.TIMEOUT: [TypeHandler(Update, booking_timeout)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        conversation_timeout=timedelta(seconds=settings.booking_conversation_timeout_seconds),
    )


def create_booking_handler() -> ConversationHandler:
    """Backward-compatible alias for booking handler factory."""
    return create_booking_conversation_handler()
