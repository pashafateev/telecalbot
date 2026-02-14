"""Constants used throughout the application."""

# Russian timezones sorted by UTC offset
RUSSIAN_TIMEZONES = [
    ("Europe/Kaliningrad", "Калининград (UTC+2)"),
    ("Europe/Moscow", "Москва (UTC+3)"),
    ("Europe/Samara", "Самара (UTC+4)"),
    ("Asia/Yekaterinburg", "Екатеринбург (UTC+5)"),
    ("Asia/Omsk", "Омск (UTC+6)"),
    ("Asia/Krasnoyarsk", "Красноярск (UTC+7)"),
    ("Asia/Irkutsk", "Иркутск (UTC+8)"),
    ("Asia/Yakutsk", "Якутск (UTC+9)"),
    ("Asia/Vladivostok", "Владивосток (UTC+10)"),
    ("Asia/Magadan", "Магадан (UTC+11)"),
    ("Asia/Kamchatka", "Камчатка (UTC+12)"),
]

# Default timezone
DEFAULT_TIMEZONE = "Europe/Moscow"

# Message templates
MESSAGES = {
    "welcome": "Добро пожаловать! Я помогу вам записаться на встречу.",
    "access_denied": (
        "Этот бот доступен только для одобренных пользователей.\n\n"
        "Ваш Chat ID: `{chat_id}`\n\n"
        "Запрос на доступ отправлен администратору."
    ),
    "access_request_sent": "Запрос на доступ отправлен. Пожалуйста, дождитесь одобрения.",
    "access_approved": "Вы одобрены! Используйте /start, чтобы начать запись.",
    "access_rejected": "Ваш запрос на доступ отклонён.",
    "error_generic": "Извините, что-то пошло не так. Попробуйте позже.",
}
