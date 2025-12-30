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
   # Run instructions coming soon
   ```

## Configuration

Required environment variables:
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `CALCOM_API_KEY` - Your Cal.com API key
- `ADMIN_TELEGRAM_ID` - Your Telegram user ID for admin access

See `.env.sample` for a complete list of configuration options.

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
