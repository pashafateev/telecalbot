"""Booking conversation handler for multi-step appointment booking."""

import logging
from datetime import date, datetime, timedelta, timezone
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

from app.config import settings
from app.constants import RUSSIAN_TIMEZONES
from app.services.calcom_client import (
    Attendee,
    BookingRequest,
    BookingResponse,
    CalComAPIError,
    CalComClient,
)

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

TIMEZONE_BUTTON_LABEL = "Часовой пояс ⚙️"


class BookingState(IntEnum):
    SELECTING_TIMEZONE = auto()
    VIEWING_AVAILABILITY = auto()
    SELECTING_SLOT = auto()
    ENTERING_NAME = auto()
    EMAIL_DECISION = auto()
    ENTERING_EMAIL = auto()
    CONFIRMING = auto()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def book_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the booking conversation with timezone selection."""
    keyboard = build_timezone_keyboard()
    await update.message.reply_text(
        "Выберите ваш часовой пояс:",
        reply_markup=keyboard,
    )
    return BookingState.SELECTING_TIMEZONE


# ---------------------------------------------------------------------------
# Timezone selection
# ---------------------------------------------------------------------------


async def select_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle timezone selection and fetch availability."""
    query = update.callback_query
    await query.answer()

    timezone_id = query.data.split(":", 1)[1]
    context.user_data["timezone"] = timezone_id
    context.user_data["offset_days"] = 0

    return await _show_availability(query, context, offset_days=0)


async def change_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back to timezone selection."""
    query = update.callback_query
    await query.answer()

    keyboard = build_timezone_keyboard()
    await query.edit_message_text(
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
    await query.edit_message_text("Загружаю доступное время...")

    calcom_client: CalComClient = context.bot_data["calcom_client"]
    timezone_id = context.user_data["timezone"]
    today = date.today()

    try:
        availability = await calcom_client.get_availability(
            event_type_id=settings.calcom_event_type_id,
            start_date=today + timedelta(days=offset_days),
            end_date=today + timedelta(days=offset_days + 14),
            timezone=timezone_id,
        )

        has_slots = any(availability.slots.values())
        if not has_slots:
            await query.edit_message_text(
                "Нет доступного времени на этот период.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                TIMEZONE_BUTTON_LABEL, callback_data="change_tz"
                            ),
                            InlineKeyboardButton("Отмена", callback_data="cancel"),
                        ]
                    ]
                ),
            )
            return BookingState.VIEWING_AVAILABILITY

        keyboard = build_availability_keyboard(availability.slots, offset_days)
        await query.edit_message_text(
            f"Доступное время ({timezone_id}):\n\nВыберите время:",
            reply_markup=keyboard,
        )
        return BookingState.VIEWING_AVAILABILITY

    except CalComAPIError:
        await query.edit_message_text(
            "Извините, не удалось загрузить расписание. Попробуйте ещё раз.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Попробовать снова",
                            callback_data=f"tz:{timezone_id}",
                        ),
                        InlineKeyboardButton("Отмена", callback_data="cancel"),
                    ]
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


async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """No-op handler for day header buttons."""
    query = update.callback_query
    await query.answer()
    return BookingState.VIEWING_AVAILABILITY


# ---------------------------------------------------------------------------
# Slot selection
# ---------------------------------------------------------------------------


async def select_slot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle time slot selection and prompt for name."""
    query = update.callback_query
    await query.answer()

    # callback_data format: "slot:<date>:<time_iso>"
    parts = query.data.split(":", 2)
    context.user_data["selected_date"] = parts[1]
    context.user_data["selected_time"] = parts[2]

    await query.edit_message_text("Введите ваше имя:")
    return BookingState.ENTERING_NAME


# ---------------------------------------------------------------------------
# Name collection
# ---------------------------------------------------------------------------


async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store user's name and ask about email."""
    name = update.message.text.strip()
    context.user_data["name"] = name

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Да, указать email", callback_data="email_yes"),
                InlineKeyboardButton("Нет, пропустить", callback_data="email_no"),
            ]
        ]
    )
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

    if query.data == "email_yes":
        await query.edit_message_text("Введите ваш email:")
        return BookingState.ENTERING_EMAIL
    else:
        context.user_data["email"] = None
        return await _show_confirmation_edit(query, context)


async def enter_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store email and show confirmation."""
    email = update.message.text.strip()

    if "@" not in email or "." not in email.split("@")[-1]:
        await update.message.reply_text(
            "Некорректный email. Попробуйте ещё раз:"
        )
        return BookingState.ENTERING_EMAIL

    context.user_data["email"] = email
    await _show_confirmation_message(update.message, context)
    return BookingState.CONFIRMING


# ---------------------------------------------------------------------------
# Confirmation display helpers
# ---------------------------------------------------------------------------


async def _show_confirmation_edit(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Edit message to show booking confirmation."""
    text = _build_confirmation_text(context.user_data)
    keyboard = _confirmation_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard)
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
    email_line = f"\nEmail: {data['email']}" if data.get("email") else ""
    return (
        f"Подтвердите запись:\n\n"
        f"Время: {formatted_time}\n"
        f"Имя: {data['name']}"
        f"{email_line}\n\n"
        f"Нажмите «Подтвердить запись» для продолжения."
    )


def _confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Подтвердить запись", callback_data="confirm"),
                InlineKeyboardButton("Отмена", callback_data="cancel"),
            ]
        ]
    )


# ---------------------------------------------------------------------------
# Booking creation
# ---------------------------------------------------------------------------


async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Create the booking via Cal.com API."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("Создаю запись...")

    data = context.user_data
    calcom_client: CalComClient = context.bot_data["calcom_client"]
    email = data.get("email") or f"telegram-{update.effective_user.id}@telecalbot.local"

    try:
        start_utc = slot_to_utc(data["selected_time"])

        booking = await calcom_client.create_booking(
            BookingRequest(
                eventTypeId=settings.calcom_event_type_id,
                start=start_utc,
                attendee=Attendee(
                    name=data["name"],
                    email=email,
                    timeZone=data["timezone"],
                ),
                metadata={
                    "telegram_user_id": str(update.effective_user.id),
                    "booked_via": "telegram_bot",
                },
            )
        )

        formatted_time = _format_datetime_display(
            data["selected_date"],
            data["selected_time"],
            data["timezone"],
        )
        duration = _format_duration(booking)
        email_note = (
            f"\nПисьмо с подтверждением отправлено на {email}."
            if data.get("email")
            else ""
        )

        await query.edit_message_text(
            f"Готово! Ваша встреча подтверждена.\n\n"
            f"Время: {formatted_time}\n"
            f"Длительность: {duration}\n\n"
            f"Мы свяжемся через Telegram в назначенное время."
            f"{email_note}"
        )
        return ConversationHandler.END

    except CalComAPIError as e:
        if e.status_code == 409:
            error_msg = (
                "Это время уже занято. Пожалуйста, выберите другое время."
            )
        else:
            error_msg = "Извините, что-то пошло не так. Попробуйте ещё раз."

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Выбрать другое время",
                        callback_data=f"tz:{data['timezone']}",
                    ),
                    InlineKeyboardButton("Отмена", callback_data="cancel"),
                ]
            ]
        )
        await query.edit_message_text(error_msg, reply_markup=keyboard)
        return BookingState.VIEWING_AVAILABILITY


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the booking conversation."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Запись отменена.")
    else:
        await update.message.reply_text("Запись отменена.")

    context.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Keyboard builders
# ---------------------------------------------------------------------------


def build_timezone_keyboard() -> InlineKeyboardMarkup:
    """Build timezone selection keyboard."""
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"tz:{tz_id}")]
        for tz_id, label in RUSSIAN_TIMEZONES
    ]
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
        buttons.append(
            [InlineKeyboardButton(f"— {day_name} —", callback_data="noop")]
        )

        time_buttons = []
        for slot in time_slots[:6]:
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
        nav_row.append(
            InlineKeyboardButton(
                "← Назад", callback_data=f"dates:{offset_days - 5}"
            )
        )
    nav_row.append(
        InlineKeyboardButton(
            "Ещё даты →", callback_data=f"dates:{offset_days + 5}"
        )
    )
    nav_row.append(
        InlineKeyboardButton(TIMEZONE_BUTTON_LABEL, callback_data="change_tz")
    )
    buttons.append(nav_row)
    buttons.append([InlineKeyboardButton("Отмена", callback_data="cancel")])

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
    """Format ISO datetime string to '2:00 PM'."""
    dt = datetime.fromisoformat(time_iso)
    return dt.strftime("%-I:%M %p")


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
    return f"{dt.strftime('%A, %B %-d at %-I:%M %p')} ({tz_id})"


# ---------------------------------------------------------------------------
# ConversationHandler factory
# ---------------------------------------------------------------------------


def create_booking_handler() -> ConversationHandler:
    """Create and return the booking ConversationHandler."""
    return ConversationHandler(
        entry_points=[CommandHandler("book", book_command)],
        states={
            BookingState.SELECTING_TIMEZONE: [
                CallbackQueryHandler(select_timezone, pattern="^tz:"),
                CallbackQueryHandler(cancel, pattern="^cancel$"),
            ],
            BookingState.VIEWING_AVAILABILITY: [
                CallbackQueryHandler(select_slot, pattern="^slot:"),
                CallbackQueryHandler(load_more_dates, pattern="^dates:"),
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
            BookingState.CONFIRMING: [
                CallbackQueryHandler(confirm_booking, pattern="^confirm$"),
                CallbackQueryHandler(select_timezone, pattern="^tz:"),
                CallbackQueryHandler(cancel, pattern="^cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
