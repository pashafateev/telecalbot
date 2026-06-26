# Telecalbot

A Telegram bot that provides Cal.com booking functionality for users in regions where Cal.com is restricted or blocked.

## Overview

Telecalbot acts as a bridge between Telegram and Cal.com, allowing users to schedule appointments through Telegram messages and buttons. All bookings sync automatically to Google Calendar via Cal.com's existing integration.

## Problem It Solves

Cal.com is blocked in some regions (like Russia), preventing users from accessing the web booking interface. This bot provides the same scheduling functionality through Telegram, which is accessible globally.

## Features

- **Button-Driven Interface**: No command memorization required
- **Timezone Support**: Displays available times in user's timezone (with special support for Russian timezones)
- **Access Control**: Whitelist-based system to manage approved users
- **Google Calendar Sync**: Bookings automatically sync through Cal.com's integration
- **Request-Based Approval**: Admin receives notifications when new users request access

## Prerequisites

- Python 3.11+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Cal.com API Key
- Cal.com account with Google Calendar integration

## Project Structure

```
.
├── app/                    # Application code
├── specs/                  # Project specifications
│   └── telecalbot-specification.md
├── logs/                   # Application logs
├── .claude/                # Claude Code configuration
├── .env                    # Environment variables (not committed)
└── .env.sample             # Environment variables template
```

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd telecalbot
   ```

2. **Set up environment variables**
   ```bash
   cp .env.sample .env
   # Edit .env and add your API keys
   ```

3. **Install dependencies**
   ```bash
   # Installation instructions coming soon
   ```

4. **Run the bot**
   ```bash
   uv run python -m app.main
   ```

## Configuration

Required environment variables:
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `CALCOM_API_KEY` - Your Cal.com API key
- `ADMIN_TELEGRAM_ID` - Your Telegram user ID for admin access

Delivery mode:
- `TELEGRAM_DELIVERY_MODE=polling` is the default and is intended for local development.
- `TELEGRAM_DELIVERY_MODE=webhook` starts an HTTP server for Telegram webhooks and health checks.
- `TELEGRAM_WEBHOOK_URL` is required in webhook mode.
- `TELEGRAM_WEBHOOK_SECRET_TOKEN` is optional locally and recommended in production.

See `.env.sample` for a complete list of configuration options.

## Deployment

Fly runs the bot in webhook mode on port `8080`. The configured production webhook endpoint is:

```text
https://telecalbot.fly.dev/telegram/webhook
```

Set production secrets before deploying:

```bash
fly secrets set \
  TELEGRAM_BOT_TOKEN=<telegram-bot-token> \
  CALCOM_API_KEY=<calcom-api-key> \
  ADMIN_TELEGRAM_ID=<telegram-admin-id> \
  TELEGRAM_WEBHOOK_SECRET_TOKEN=<random-secret-token>
```

Deploy the app:

```bash
fly deploy --remote-only
```

After deploy, register the webhook with Telegram. The application also calls `setWebhook` on startup, but this command is useful for explicit verification:

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=https://telecalbot.fly.dev/telegram/webhook" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET_TOKEN}"
```

Check runtime health:

```bash
curl https://telecalbot.fly.dev/healthz
curl https://telecalbot.fly.dev/readyz
```

## Development Status

🚧 **In Development** - MVP Phase

Current progress:
- ✅ Requirements gathering complete
- ✅ Technical architecture designed
- 🚧 Implementation in progress

See [specs/telecalbot-specification.md](specs/telecalbot-specification.md) for detailed project specification.

## Use Case

Primary use case: AA/NA sponsorship scheduling
- Sponsor uses Cal.com for appointment management
- Sponsees in Russia cannot access Cal.com directly
- Bot provides equivalent booking experience through Telegram
- All appointments sync to sponsor's Google Calendar

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: python-telegram-bot v20+
- **API Client**: httpx
- **Database**: SQLite
- **Deployment**: fly.io

## Documentation

- [Full Specification](specs/telecalbot-specification.md) - Comprehensive project requirements and technical design
- User Guide - Coming soon
- Admin Guide - Coming soon

## License

[License information to be added]

## Contributing

This is currently a personal project. Contributions welcome after initial MVP release.
