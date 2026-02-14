# Telecalbot

A Telegram bot that lets users book [Cal.com](https://cal.com) appointments entirely through Telegram -- designed for regions where Cal.com is blocked or restricted.

## Why This Exists

Cal.com is inaccessible in certain countries (notably Russia), which prevents users from reaching the web-based booking interface. Telecalbot bridges that gap by exposing the same scheduling workflow through Telegram's chat and inline-button interface. Every booking created through the bot syncs automatically to Google Calendar via Cal.com's built-in integration, so the host's calendar stays up to date without any extra work.

## Features

- **Conversational booking flow** -- users pick a timezone, browse available slots, enter their name, and confirm the appointment, all through inline buttons and short text prompts.
- **Russian timezone support** -- the bot ships with all 11 Russian timezones (Kaliningrad through Kamchatka) pre-configured with Cyrillic labels.
- **Whitelist-based access control** -- only admin-approved users can book. New users automatically trigger an approval request that the admin sees in Telegram.
- **Admin commands** -- approve, reject, or list pending access requests without leaving the chat.
- **Availability caching** -- Cal.com availability responses are cached for 5 minutes to keep the bot responsive and reduce API calls.
- **Optional email confirmation** -- attendees can supply an email to receive a Cal.com confirmation, or skip it entirely.
- **Google Calendar sync** -- every booking lands on the host's Google Calendar through Cal.com's native integration.

## Prerequisites

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** -- used as the package manager and task runner
- A **Telegram Bot Token** (create one via [@BotFather](https://t.me/botfather))
- A **Cal.com API Key** (found in your Cal.com account settings)
- A Cal.com account with at least one event type configured

## Installation

```bash
# Clone the repository
git clone https://github.com/pashafateev/telecalbot.git
cd telecalbot

# Create a virtual environment and install dependencies
uv sync

# Copy the sample environment file
cp .env.sample .env
```

Edit `.env` and fill in the required values (see [Configuration](#configuration) below).

## Configuration

All configuration is loaded from environment variables (or a `.env` file in the project root). A fully commented template is provided in `.env.sample`.

### Required Variables

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token obtained from [@BotFather](https://t.me/botfather) |
| `CALCOM_API_KEY` | API key from your Cal.com account settings |
| `ADMIN_TELEGRAM_ID` | Telegram user ID of the bot administrator |
| `CALCOM_EVENT_TYPE_ID` | Numeric ID of the Cal.com event type to offer for booking |

### Optional Variables

| Variable | Default | Description |
|---|---|---|
| `CAL_API_VERSION` | `2024-08-13` | Cal.com API version header |
| `CALCOM_EVENT_SLUG` | `step` | Event slug from your Cal.com event URL |
| `DATABASE_PATH` | `telecalbot.db` | Path to the SQLite database file |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |

### Finding Your Cal.com Event Type ID

If you do not know your event type ID, run the included research script:

```bash
uv run python research/calcom_api_validator.py
```

## Usage

Start the bot:

```bash
uv run python -m app.main
```

### User Commands

| Command | Description |
|---|---|
| `/start` | Begin interaction; requests access if not yet approved |
| `/book` | Start the multi-step booking conversation |
| `/help` | Show available commands |
| `/cancel` | Cancel an in-progress booking |

### Admin Commands

These commands are restricted to the Telegram user whose ID matches `ADMIN_TELEGRAM_ID`.

| Command | Description |
|---|---|
| `/approve <id>` | Approve a pending access request |
| `/reject <id>` | Reject a pending access request |
| `/pending` | List all pending access requests |

### Booking Flow

1. The user sends `/book`.
2. The bot presents a list of Russian timezones as inline buttons.
3. After selecting a timezone, the bot fetches available slots from Cal.com and displays them grouped by day.
4. The user picks a time slot.
5. The bot asks for the user's name.
6. The user is offered the option to provide an email for confirmation (or skip).
7. A summary is displayed for confirmation.
8. On confirmation the bot creates the booking via the Cal.com API and reports success.

## Project Structure

```
telecalbot/
├── app/
│   ├── __init__.py
│   ├── main.py                  # Entry point -- sets up handlers and starts polling
│   ├── config.py                # Pydantic-based settings loaded from .env
│   ├── constants.py             # Russian timezone list and message templates
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py        # SQLite connection manager (WAL mode)
│   │   ├── migrations.py        # Schema initialization
│   │   └── models.py            # Pydantic models for DB entities
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── admin.py             # /approve, /reject, /pending handlers
│   │   ├── booking.py           # Multi-step /book conversation handler
│   │   ├── help.py              # /help handler
│   │   └── start.py             # /start handler with access control
│   └── services/
│       ├── __init__.py
│       ├── calcom_client.py     # Async Cal.com API client with caching
│       └── whitelist.py         # Whitelist and access-request service
├── tests/                       # pytest test suite
├── specs/                       # Project specifications and roadmap
├── research/                    # API research and validation scripts
├── pyproject.toml               # Project metadata and dependencies
├── uv.lock                      # Locked dependency versions
├── .env.sample                  # Environment variable template
└── .gitignore
```

## Development

### Running Tests

```bash
uv run pytest tests/ -v
```

### Linting

```bash
uv run ruff check
```

### Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Bot framework | [python-telegram-bot](https://python-telegram-bot.org/) v20+ |
| HTTP client | [httpx](https://www.python-httpx.org/) |
| Settings | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| Data validation | [Pydantic](https://docs.pydantic.dev/) v2 |
| Database | SQLite (WAL mode) |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Linter | [Ruff](https://docs.astral.sh/ruff/) |
| Tests | [pytest](https://docs.pytest.org/) + pytest-asyncio |

## Contributing

Contributions are welcome. Please open an issue or submit a pull request.

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/my-change`).
3. Write tests for any new functionality.
4. Make sure all tests pass (`uv run pytest tests/ -v`) and the linter is clean (`uv run ruff check`).
5. Commit using [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat:`, `fix:`, `docs:`).
6. Open a pull request against `main`.

## License

This project does not yet specify a license. Contact the maintainer for usage terms.
