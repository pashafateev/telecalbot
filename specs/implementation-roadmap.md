# Telecalbot Phase 1 (MVP) Implementation Roadmap

**Created**: 2025-12-29
**Based on Specification**: telecalbot-specification.md v2.0 (2025-12-26)
**Total Estimated Duration**: 2-3 weeks
**Tracking Issue**: [#3](https://github.com/pashafateev/telecalbot/issues/3)

## GitHub Issues

- [x] [#4 Phase 0: Cal.com API Research & Validation](https://github.com/pashafateev/telecalbot/issues/4)
- [x] [#5 Phase 1: Project Foundation & Basic Bot Setup](https://github.com/pashafateev/telecalbot/issues/5)
- [x] [#6 Phase 2: Access Control & Whitelist System](https://github.com/pashafateev/telecalbot/issues/6)
- [ ] [#7 Phase 3: Cal.com API Client with Caching & Retry Logic](https://github.com/pashafateev/telecalbot/issues/7)
- [ ] [#8 Phase 4: Booking Conversation Flow with Telegram ConversationHandler](https://github.com/pashafateev/telecalbot/issues/8)
- [ ] [#9 Phase 5: Integration Testing, Polish & Deployment](https://github.com/pashafateev/telecalbot/issues/9)

---

## Specification Essence

After analyzing the 1592-line specification, here are the **5 core technical challenges** that must be solved for MVP:

1. **Cal.com API Integration Uncertainty**: Critical unknowns exist around placeholder email support, event type ID discovery, meeting method configuration, and rate limits. These must be validated before committing to implementation patterns.

2. **Telegram Conversation State Machine**: Build a multi-step booking flow (timezone selection → availability display → slot selection → user info collection → confirmation) using python-telegram-bot's ConversationHandler with in-memory state and dynamic message editing.

3. **Access Control with Request-Based Approval**: Implement whitelist enforcement using Telegram Chat IDs (not usernames), with a workflow where blocked users can request access and admin receives notifications to approve/reject via bot commands.

4. **Timezone-Aware Availability Display**: Fetch UTC slots from Cal.com, convert to user's selected Russian timezone, group by day, and present via inline keyboard buttons with pagination.

5. **Reliable Booking Creation**: Submit bookings to Cal.com API with proper error handling, retry logic (exponential backoff), graceful degradation, and confirmation messaging.

---

## Architectural Approach

### High-Level Strategy

```
                           TELEGRAM USERS
                                 |
                    Long Polling (no webhook)
                                 |
                    +------------v-----------+
                    |     BOT APPLICATION     |
                    |   (Python 3.11+)        |
                    +-------------------------+
                    |                         |
       +------------+           +-------------+
       |                        |             |
+------v------+    +------------v--+    +-----v-----+
|  HANDLERS   |    |  CAL.COM      |    |  DATA     |
|  Layer      |    |  CLIENT       |    |  LAYER    |
+-------------+    +---------------+    +-----------+
| /start      |    | GET /slots    |    | SQLite    |
| callbacks   |    | POST /bookings|    | whitelist |
| conv state  |    | retry logic   |    | prefs     |
| keyboards   |    | caching       |    | requests  |
+-------------+    +---------------+    +-----------+
```

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **State Management** | In-memory ConversationHandler | Simple, acceptable to lose on restart per spec |
| **API Client** | httpx (async-capable) | Modern, timeout handling, retry support |
| **Database** | SQLite with simple wrapper | Built-in, sufficient for 50-100 users |
| **Validation** | Pydantic models | Type safety, validation, serialization |
| **Config** | python-decouple + .env | Already established pattern in project |
| **Timezone** | zoneinfo (stdlib) | No external dependency, Python 3.9+ |
| **Loading UX** | message.edit_text() | Better UX than new messages |

---

## Phase 0: Critical Research (Blockers Resolution)

**GitHub Issue**: #4
**Status**: 🔴 **BLOCKING** - Must complete before implementation
**Effort Estimate**: S (2-4 hours)
**Spec References**: Section 6.4 (API Contracts), Section 8.3 (Open Questions)

### Goal
Resolve Cal.com API unknowns that could change implementation approach

### Deliverables
- ✅ Validated API behavior documentation
- ✅ Event Type ID for "step" event
- ✅ Confirmed booking creation payload structure
- ✅ Decision on email handling (placeholder vs required)

### Technical Approach

**Research Script** (to be created):
```python
# research/calcom_api_validator.py
# Run manually before implementation begins

import httpx
import os
from datetime import date, timedelta

API_KEY = os.environ["CALCOM_API_KEY"]
BASE_URL = "https://api.cal.com/v2"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "cal-api-version": "2024-08-13",
    "Content-Type": "application/json"
}

# 1. Fetch event types to get ID
# GET /v2/event-types

# 2. Test availability endpoint
# GET /v2/slots/available?eventTypeId=XXX&...

# 3. Test booking with placeholder email
# POST /v2/bookings with email="telegram-user-123@telecalbot.local"

# 4. Verify booking appears in Google Calendar
```

### Research Questions

| Question | Test Method | Fallback if Fails |
|----------|-------------|-------------------|
| Placeholder email accepted? | POST booking with `telegram-user-X@telecalbot.local` | Make email required |
| Event Type ID discovery? | GET /v2/event-types, filter by slug | Manual dashboard lookup |
| Meeting method field? | Test `meetingUrl` vs `metadata.meeting_method` | Use notes field |
| Rate limits? | Check response headers (X-RateLimit-*) | Implement 60 req/min ceiling |
| API version current? | Check Cal.com docs | Use documented version |

### Success Criteria
- [ ] Event Type ID obtained and documented
- [ ] Booking creation tested end-to-end
- [ ] Email handling decision made with evidence
- [ ] Meeting method field identified
- [ ] Rate limits documented

### Risks & Mitigations
- **Risk**: Placeholder email rejected (400/422 error)
  - **Mitigation**: Make email required; adjust UX flow to explain why
- **Risk**: API rate limits lower than expected
  - **Mitigation**: Aggressive caching (10-15 min TTL)

### Dependencies
None (first phase)

---

## Phase 1: Project Foundation

**GitHub Issue**: #5
**Status**: ⚪ Not Started
**Effort Estimate**: M (2-3 days)
**Spec References**: Section 6.3 (Technology Choices), Section 5.5 (Hosting)

### Goal
Establish project structure, dependencies, and basic bot connectivity

### Deliverables
- ✅ Complete Python project structure
- ✅ Dependency management (pyproject.toml)
- ✅ Basic bot that responds to /start
- ✅ Configuration loading from .env
- ✅ SQLite database initialization
- ✅ Logging infrastructure

### Technical Approach

**File Structure**:
```
telecalbot/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Entry point, Application setup
│   ├── config.py               # Settings from .env via pydantic-settings
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py       # SQLite connection manager
│   │   ├── models.py           # Pydantic models for DB entities
│   │   └── migrations.py       # Schema initialization
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py            # /start command, access check
│   │   ├── booking.py          # Booking conversation flow
│   │   ├── admin.py            # /approve, /reject commands
│   │   └── common.py           # Shared utilities, keyboards
│   ├── services/
│   │   ├── __init__.py
│   │   ├── calcom_client.py    # Cal.com API wrapper
│   │   ├── whitelist.py        # Access control logic
│   │   └── timezone.py         # Timezone utilities
│   └── constants.py            # Russian timezones, messages
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_calcom_client.py
│   ├── test_whitelist.py
│   └── test_timezone.py
├── pyproject.toml
├── .env                        # (gitignored)
├── .env.sample                 # (exists)
└── README.md
```

**pyproject.toml**:
```toml
[project]
name = "telecalbot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "python-telegram-bot>=20.0",
    "httpx>=0.25.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "python-decouple>=3.8",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
]
```

**config.py**:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    telegram_bot_token: str
    calcom_api_key: str
    cal_api_version: str = "2024-08-13"
    admin_telegram_id: int
    calcom_event_slug: str = "step"
    calcom_event_type_id: int | None = None
    database_path: str = "telecalbot.db"
    log_level: str = "INFO"
    availability_cache_ttl: int = 300

    class Config:
        env_file = ".env"
```

### Success Criteria
- [ ] `python -m app.main` starts bot successfully
- [ ] Bot responds to /start with "Hello" message
- [ ] Config loads from .env without errors
- [ ] SQLite database file created with schema
- [ ] Logs output to stdout with configured level

### Risks & Mitigations
- **Risk**: python-telegram-bot v20+ async patterns unfamiliar
  - **Mitigation**: Follow official v20 migration guide; async/await patterns
- **Risk**: SQLite concurrency issues (unlikely at this scale)
  - **Mitigation**: Use connection-per-request pattern; WAL mode

### Dependencies
Phase 0 (research findings inform config structure)

---

## Phase 2: Access Control & Whitelist

**GitHub Issue**: #6
**Status**: ⚪ Not Started
**Effort Estimate**: M (2-3 days)
**Spec References**: Section 4.2 (US-1.1, US-1.2), Section 5.4 (Whitelist Management Flow)

### Goal
Implement whitelist-based access control with request-based approval workflow

### Deliverables
- ✅ Whitelist table with CRUD operations
- ✅ Access request table for pending approvals
- ✅ Chat ID extraction and validation
- ✅ Admin notification for access requests
- ✅ /approve and /reject admin commands
- ✅ User-facing access denied message with Chat ID display

### Technical Approach

**Database Schema** (`database/migrations.py`):
```sql
CREATE TABLE IF NOT EXISTS whitelist (
    telegram_id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    username TEXT,
    approved_at TEXT NOT NULL,
    approved_by INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS access_requests (
    telegram_id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    username TEXT,
    requested_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending'  -- pending, approved, rejected
);

CREATE TABLE IF NOT EXISTS user_preferences (
    telegram_id INTEGER PRIMARY KEY,
    timezone TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

**Whitelist Service** (`services/whitelist.py`):
```python
class WhitelistService:
    def __init__(self, db: Database):
        self.db = db

    async def is_whitelisted(self, telegram_id: int) -> bool:
        ...

    async def add_to_whitelist(
        self, telegram_id: int, display_name: str,
        username: str | None, approved_by: int
    ) -> None:
        ...

    async def create_access_request(
        self, telegram_id: int, display_name: str, username: str | None
    ) -> bool:  # Returns True if new request, False if already pending
        ...

    async def get_pending_requests(self) -> list[AccessRequest]:
        ...
```

**Start Handler Flow** (`handlers/start.py`):
```python
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = user.id

    if await whitelist_service.is_whitelisted(chat_id):
        # Show main menu
        await update.message.reply_text(
            f"Welcome, {user.first_name}! I can help you book appointments.",
            reply_markup=main_menu_keyboard()
        )
    else:
        # Create access request, notify admin
        is_new = await whitelist_service.create_access_request(
            chat_id, user.first_name, user.username
        )
        if is_new:
            await notify_admin_of_request(context, user)

        await update.message.reply_text(
            f"This bot is for approved users only.\n\n"
            f"Your Chat ID: `{chat_id}`\n\n"
            f"An access request has been sent to the admin.",
            parse_mode="Markdown"
        )
```

**Admin Commands** (`handlers/admin.py`):
```python
@admin_only  # Decorator checks ADMIN_TELEGRAM_ID
async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /approve 123456789
    if not context.args:
        await update.message.reply_text("Usage: /approve <telegram_id>")
        return

    telegram_id = int(context.args[0])
    await whitelist_service.add_to_whitelist(
        telegram_id, ..., approved_by=update.effective_user.id
    )

    # Notify user they've been approved
    await context.bot.send_message(
        chat_id=telegram_id,
        text="You've been approved! Use /start to begin booking."
    )
```

### Success Criteria
- [ ] Non-whitelisted user sees access denied message with Chat ID
- [ ] Admin receives notification with user info when access requested
- [ ] `/approve <id>` adds user to whitelist
- [ ] `/reject <id>` denies request
- [ ] `/pending` shows all pending requests
- [ ] Approved user can access bot on next /start

### Risks & Mitigations
- **Risk**: Admin misses approval notification
  - **Mitigation**: Include `/pending` command to list all pending requests
- **Risk**: Race condition if user spams /start
  - **Mitigation**: Use INSERT OR IGNORE for access requests

### Dependencies
Phase 1 (database, config, basic handlers)

---

## Phase 3: Cal.com API Client

**GitHub Issue**: #7
**Status**: ⚪ Not Started
**Effort Estimate**: M (2-3 days)
**Spec References**: Section 6.4 (API Contracts), Section 8.1 (Technical Risks)

### Goal
Build robust Cal.com API client with caching, retry logic, and error handling

### Deliverables
- ✅ Async HTTP client wrapper for Cal.com API v2
- ✅ Availability fetching with timezone support
- ✅ Booking creation with all required fields
- ✅ In-memory availability cache (TTL-based)
- ✅ Exponential backoff retry logic
- ✅ Pydantic models for API responses

### Technical Approach

**API Models** (`services/calcom_client.py`):
```python
from pydantic import BaseModel
from datetime import datetime

class TimeSlot(BaseModel):
    date: str  # "2025-01-06"
    times: list[str]  # ["10:00:00", "14:00:00"]

class AvailabilityResponse(BaseModel):
    slots: dict[str, list[str]]  # date -> times

class Attendee(BaseModel):
    name: str
    email: str
    timeZone: str
    language: str = "en"

class BookingRequest(BaseModel):
    eventTypeId: int
    start: str  # ISO 8601 UTC
    attendee: Attendee
    metadata: dict = {}

class BookingResponse(BaseModel):
    id: str
    uid: str
    title: str
    startTime: datetime
    endTime: datetime
    status: str
```

**Client Implementation**:
```python
class CalComClient:
    def __init__(self, api_key: str, api_version: str):
        self.client = httpx.AsyncClient(
            base_url="https://api.cal.com/v2",
            headers={
                "Authorization": f"Bearer {api_key}",
                "cal-api-version": api_version,
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        self._availability_cache: dict[str, tuple[float, AvailabilityResponse]] = {}
        self.cache_ttl = 300  # 5 minutes

    async def get_availability(
        self,
        event_type_id: int,
        start_date: date,
        end_date: date,
        timezone: str
    ) -> AvailabilityResponse:
        cache_key = f"{event_type_id}:{start_date}:{end_date}:{timezone}"

        # Check cache
        if cache_key in self._availability_cache:
            cached_at, data = self._availability_cache[cache_key]
            if time.time() - cached_at < self.cache_ttl:
                return data

        # Fetch from API
        response = await self._request_with_retry(
            "GET", "/slots/available",
            params={
                "eventTypeId": event_type_id,
                "startTime": f"{start_date}T00:00:00Z",
                "endTime": f"{end_date}T23:59:59Z",
                "timeZone": timezone
            }
        )

        data = AvailabilityResponse(**response["data"])
        self._availability_cache[cache_key] = (time.time(), data)
        return data

    async def create_booking(self, request: BookingRequest) -> BookingResponse:
        response = await self._request_with_retry(
            "POST", "/bookings",
            json=request.model_dump()
        )

        # Invalidate availability cache on successful booking
        self._availability_cache.clear()

        return BookingResponse(**response["data"])

    async def _request_with_retry(
        self, method: str, path: str,
        max_retries: int = 3, **kwargs
    ) -> dict:
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await self.client.request(method, path, **kwargs)

                if response.status_code == 429:
                    # Rate limited - exponential backoff
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (400, 401, 404, 422):
                    # Client error - don't retry
                    raise CalComAPIError(
                        status_code=e.response.status_code,
                        message=e.response.text
                    )
            except httpx.RequestError as e:
                last_error = e
                # Network error - retry with backoff
                await asyncio.sleep(2 ** attempt)

        raise CalComAPIError(
            status_code=0,
            message=f"Failed after {max_retries} retries: {last_error}"
        )
```

**Error Handling**:
```python
class CalComAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message

    def user_message(self) -> str:
        """Return user-friendly error message"""
        if self.status_code == 409:
            return "This time is no longer available. Please select another."
        elif self.status_code in (400, 422):
            return "There was a problem with your booking. Please try again."
        elif self.status_code == 429:
            return "Too many requests. Please wait a moment and try again."
        else:
            return "Cal.com is temporarily unavailable. Please try again later."
```

### Success Criteria
- [ ] `get_availability()` returns parsed slots for date range
- [ ] `create_booking()` successfully creates Cal.com booking
- [ ] Cache prevents duplicate API calls within TTL
- [ ] Retry logic handles transient failures gracefully
- [ ] Error messages are user-friendly, not technical

### Risks & Mitigations
- **Risk**: Unexpected API response format
  - **Mitigation**: Log raw responses; use Pydantic's `model_validate` with `strict=False`
- **Risk**: Cache serves stale data after booking
  - **Mitigation**: Clear cache on successful booking creation
- **Risk**: httpx connection pool exhaustion
  - **Mitigation**: Use context manager; close client on shutdown

### Dependencies
Phase 1 (config, basic structure)

---

## Phase 4: Booking Conversation Flow

**GitHub Issue**: #8
**Status**: ⚪ Not Started
**Effort Estimate**: L (4-6 days)
**Spec References**: Section 4.3 (Workflow 2), Section 4.2 (US-2.1 through US-2.5)

### Goal
Implement complete booking flow with timezone selection, availability display, slot selection, and user info collection

### Deliverables
- ✅ ConversationHandler for multi-step booking flow
- ✅ Timezone selection with Russian timezone buttons
- ✅ Availability display grouped by day
- ✅ Time slot selection via inline buttons
- ✅ User info collection (name, optional email)
- ✅ Booking confirmation with summary
- ✅ Dynamic message editing for loading states

### Technical Approach

**Conversation States** (`handlers/booking.py`):
```python
from enum import IntEnum, auto

class BookingState(IntEnum):
    SELECTING_TIMEZONE = auto()
    VIEWING_AVAILABILITY = auto()
    SELECTING_SLOT = auto()
    ENTERING_NAME = auto()
    EMAIL_DECISION = auto()
    ENTERING_EMAIL = auto()
    CONFIRMING = auto()
```

**Russian Timezones** (`constants.py`):
```python
RUSSIAN_TIMEZONES = [
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
```

**Availability Display**:
```python
async def show_availability(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Show loading indicator
    loading_msg = await query.edit_message_text("Fetching available times...")

    try:
        timezone = context.user_data["timezone"]
        today = date.today()

        availability = await calcom_client.get_availability(
            event_type_id=settings.calcom_event_type_id,
            start_date=today,
            end_date=today + timedelta(days=14),
            timezone=timezone
        )

        # Build keyboard with available slots
        keyboard = build_availability_keyboard(availability.slots, timezone)

        await loading_msg.edit_text(
            f"Available times ({timezone}):\n\nSelect a time slot:",
            reply_markup=keyboard
        )

    except CalComAPIError as e:
        await loading_msg.edit_text(
            f"Sorry, {e.user_message()}\n\n[Try Again]",
            reply_markup=retry_keyboard()
        )
        return BookingState.VIEWING_AVAILABILITY

def build_availability_keyboard(
    slots: dict[str, list[str]],
    timezone: str
) -> InlineKeyboardMarkup:
    """Build paginated keyboard grouped by day"""
    buttons = []

    for date_str, times in sorted(slots.items())[:5]:  # Show 5 days max
        # Date header
        day_name = format_date_header(date_str)  # "Monday, Jan 6"
        buttons.append([InlineKeyboardButton(
            f"-- {day_name} --",
            callback_data="noop"
        )])

        # Time slots in rows of 3
        time_buttons = []
        for time_str in times[:6]:  # Max 6 slots per day
            display_time = format_time(time_str)  # "2:00 PM"
            callback = f"slot:{date_str}:{time_str}"
            time_buttons.append(InlineKeyboardButton(display_time, callback_data=callback))

            if len(time_buttons) == 3:
                buttons.append(time_buttons)
                time_buttons = []

        if time_buttons:
            buttons.append(time_buttons)

    # Navigation buttons
    buttons.append([
        InlineKeyboardButton("Load More Dates", callback_data="more_dates"),
        InlineKeyboardButton("Change Timezone", callback_data="change_tz"),
    ])
    buttons.append([InlineKeyboardButton("Cancel", callback_data="cancel")])

    return InlineKeyboardMarkup(buttons)
```

**Booking Confirmation**:
```python
async def create_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Show loading
    await query.edit_message_text("Creating your booking...")

    data = context.user_data

    # Build email - placeholder or user-provided
    email = data.get("email") or f"telegram-{update.effective_user.id}@telecalbot.local"

    try:
        # Convert to UTC for API
        start_utc = to_utc(
            data["selected_date"],
            data["selected_time"],
            data["timezone"]
        )

        booking = await calcom_client.create_booking(
            BookingRequest(
                eventTypeId=settings.calcom_event_type_id,
                start=start_utc.isoformat(),
                attendee=Attendee(
                    name=data["name"],
                    email=email,
                    timeZone=data["timezone"]
                ),
                metadata={
                    "telegram_user_id": str(update.effective_user.id),
                    "booked_via": "telegram_bot"
                }
            )
        )

        # Success message
        await query.edit_message_text(
            f"All set! Your appointment is confirmed.\n\n"
            f"Time: {format_datetime(data['selected_date'], data['selected_time'], data['timezone'])}\n"
            f"Duration: 1 hour\n\n"
            f"We'll connect via Telegram at that time.\n"
            + (f"\nA confirmation email has been sent to {email}." if data.get("email") else ""),
            reply_markup=post_booking_keyboard()
        )

        return ConversationHandler.END

    except CalComAPIError as e:
        await query.edit_message_text(
            f"Sorry, {e.user_message()}",
            reply_markup=error_keyboard()
        )
        return BookingState.VIEWING_AVAILABILITY
```

### Success Criteria
- [ ] User can select timezone from Russian timezone list
- [ ] Availability displays grouped by day with time slot buttons
- [ ] Selected slot stored in conversation state
- [ ] Name and optional email collected
- [ ] Confirmation summary shows all details
- [ ] Booking created successfully in Cal.com
- [ ] Confirmation message sent with booking details
- [ ] Errors handled gracefully at each step

### Risks & Mitigations
- **Risk**: User abandons mid-flow, state lingers
  - **Mitigation**: ConversationHandler timeout; `/cancel` command
- **Risk**: Telegram 48-hour message edit limit
  - **Mitigation**: Try/except around edit_text; fall back to new message
- **Risk**: User selects slot that becomes unavailable
  - **Mitigation**: API returns 409; handle gracefully with "try another time"

### Dependencies
Phase 2 (whitelist), Phase 3 (Cal.com client)

---

## Phase 5: Integration Testing & Polish

**GitHub Issue**: #9
**Status**: ⚪ Not Started
**Effort Estimate**: M (2-4 days)
**Spec References**: Section 7.2 (Testing Strategy), Section 9 (Milestones M4, M5)

### Goal
End-to-end testing, error handling refinement, UX polish, and documentation

### Deliverables
- ✅ End-to-end test suite (pytest)
- ✅ Manual testing checklist completed
- ✅ Error handling refined for all edge cases
- ✅ Loading indicators and message formatting polished
- ✅ User-facing documentation
- ✅ Developer documentation (README updates)
- ✅ Deployment preparation (fly.io config)

### Technical Approach

**Test Structure**:
```python
# tests/test_calcom_client.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_get_availability_caches_response():
    client = CalComClient(api_key="test", api_version="2024-08-13")

    with patch.object(client, '_request_with_retry', new_callable=AsyncMock) as mock:
        mock.return_value = {"data": {"slots": {"2025-01-06": ["10:00:00"]}}}

        # First call
        result1 = await client.get_availability(...)
        # Second call should use cache
        result2 = await client.get_availability(...)

        assert mock.call_count == 1  # Only one API call
        assert result1 == result2

@pytest.mark.asyncio
async def test_create_booking_clears_cache():
    ...

@pytest.mark.asyncio
async def test_retry_on_rate_limit():
    ...
```

**Manual Testing Checklist**:

#### Access Control
- [ ] Non-whitelisted user sees rejection with Chat ID
- [ ] Admin receives request notification
- [ ] /approve adds user to whitelist
- [ ] /reject denies access
- [ ] Approved user can access bot

#### Booking Flow
- [ ] Timezone selection displays all 10 Russian timezones
- [ ] Availability fetches and displays correctly
- [ ] Times shown in user's selected timezone
- [ ] Slot selection stores correct date/time
- [ ] Name validation rejects empty/long names
- [ ] Email optional flow works (skip and provide)
- [ ] Confirmation shows correct summary
- [ ] Booking creates in Cal.com
- [ ] Booking appears in Google Calendar
- [ ] Confirmation message sent

#### Error Handling
- [ ] Invalid API key shows generic error
- [ ] Slot no longer available (409) handled
- [ ] Rate limit (429) triggers retry
- [ ] Network timeout retries and fails gracefully
- [ ] 48-hour message edit limit handled

#### Edge Cases
- [ ] User with no Telegram username works
- [ ] Multiple users booking simultaneously
- [ ] Bot restart doesn't break active conversations (acceptable loss)
- [ ] Very long day with many slots

**fly.io Deployment Config**:
```toml
# fly.toml
app = "telecalbot"
primary_region = "fra"  # Frankfurt - close to Russia

[build]
  dockerfile = "Dockerfile"

[env]
  LOG_LEVEL = "INFO"

[mounts]
  source = "telecalbot_data"
  destination = "/data"

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.http_checks]]
    interval = 10000
    grace_period = "5s"
    method = "get"
    path = "/health"
    timeout = 2000
```

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY app/ ./app/

ENV DATABASE_PATH=/data/telecalbot.db

CMD ["python", "-m", "app.main"]
```

### Success Criteria
- [ ] All unit tests pass
- [ ] Manual testing checklist 100% complete
- [ ] Booking confirmed to appear in Google Calendar
- [ ] Error messages are clear and actionable
- [ ] README documents setup and deployment
- [ ] fly.io deployment works end-to-end
- [ ] Bot token and API keys not exposed in logs

### Risks & Mitigations
- **Risk**: Production environment differs from local
  - **Mitigation**: Test in fly.io staging before go-live
- **Risk**: SQLite file permissions on fly.io
  - **Mitigation**: Mount persistent volume; verify write access

### Dependencies
Phase 4 (complete booking flow)

---

## Implementation Order Summary

```
Phase 0: Research (S: 2-4 hours) 🔴 BLOCKING
    ├── Validate Cal.com API behavior
    ├── Obtain Event Type ID
    └── Document findings
           │
           v
Phase 1: Foundation (M: 2-3 days)
    ├── Project structure
    ├── Dependencies
    ├── Config loading
    └── Basic bot
           │
           v
Phase 2: Access Control (M: 2-3 days)
    ├── Whitelist CRUD
    ├── Request workflow
    └── Admin commands
           │
           v
Phase 3: Cal.com Client (M: 2-3 days)
    ├── API wrapper
    ├── Caching
    └── Error handling
           │
           v
Phase 4: Booking Flow (L: 4-6 days)
    ├── Conversation states
    ├── Timezone selection
    ├── Availability display
    ├── User info collection
    └── Booking creation
           │
           v
Phase 5: Polish & Deploy (M: 2-4 days)
    ├── Testing
    ├── Documentation
    └── fly.io deployment
```

**Total Estimated Duration**: 2-3 weeks

---

## Critical Path

The critical path for MVP delivery is:

1. **Phase 0 (Research)** - 🔴 **BLOCKING** - If placeholder email fails, the entire email handling flow changes
2. **Phase 3 (Cal.com Client)** - 🔴 **BLOCKING** - Without working API integration, no bookings possible
3. **Phase 4 (Booking Flow)** - 🔴 **BLOCKING** - Core user value proposition

**Note**: Phases 1-2 (Foundation, Access Control) can be developed in parallel with Phase 0 research since they don't depend on Cal.com API specifics.

---

## Open Questions (Requiring Stakeholder Input)

### Resolved
1. **Email placeholder domain**: Will test during Phase 0; fallback to required email if rejected
2. **Calendar entry details**: Cal.com handles Google Calendar sync automatically
3. **Admin notification format**: Include `/approve <id>` command in notification for convenience
4. **Timeout behavior**: Silent timeout after 30 minutes; user can restart with /start
5. **Post-MVP priority**: No preference; will tackle Phase 2 features as needed

### Remaining
None - all implementation details have reasonable defaults.

---

## Success Metrics

### Primary Metrics (from Specification)
1. **Booking Success Rate**: >95% of booking attempts succeed
2. **User Adoption**: All sponsees using bot within 1 month
3. **Time Saved**: 80% reduction in scheduling coordination time

### Secondary Metrics
1. **Error Rate**: <5% of interactions result in errors
2. **User Satisfaction**: Sponsees find it "easy to use"
3. **Calendar Sync Accuracy**: 100% of bookings appear in Google Calendar

---

## Next Steps

1. **Create GitHub Issues** for each phase using this roadmap
2. **Begin Phase 0** (Cal.com API Research) - CRITICAL BLOCKER
3. **Parallel work**: Can start Phase 1 (Foundation) while Phase 0 research is in progress
4. **After Phase 0**: Update config and models based on research findings

---

**Document Version**: 1.0
**Agent**: spec-architect (agentId: a2f9ca6)
**Ready for**: Issue creation and implementation kickoff
