"""Constants used throughout the application."""

# Russian timezones sorted by UTC offset
RUSSIAN_TIMEZONES = [
    ("Europe/Kaliningrad", "Kaliningrad (UTC+2)"),
    ("Europe/Moscow", "Moscow (UTC+3)"),
    ("Europe/Samara", "Samara (UTC+4)"),
    ("Asia/Yekaterinburg", "Yekaterinburg (UTC+5)"),
    ("Asia/Omsk", "Omsk (UTC+6)"),
    ("Asia/Krasnoyarsk", "Krasnoyarsk (UTC+7)"),
    ("Asia/Irkutsk", "Irkutsk (UTC+8)"),
    ("Asia/Yakutsk", "Yakutsk (UTC+9)"),
    ("Asia/Vladivostok", "Vladivostok (UTC+10)"),
    ("Asia/Magadan", "Magadan (UTC+11)"),
    ("Asia/Kamchatka", "Kamchatka (UTC+12)"),
]

# Default timezone
DEFAULT_TIMEZONE = "Europe/Moscow"

# Message templates
MESSAGES = {
    "welcome": "Welcome! I can help you book appointments.",
    "access_denied": (
        "This bot is for approved users only.\n\n"
        "Your Chat ID: `{chat_id}`\n\n"
        "An access request has been sent to the admin."
    ),
    "access_request_sent": "Access request sent. Please wait for admin approval.",
    "access_approved": "You've been approved! Use /start to begin booking.",
    "access_rejected": "Your access request was denied.",
    "error_generic": "Sorry, something went wrong. Please try again later.",
}
