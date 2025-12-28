# Telecalbot - Telegram Cal.com Integration Bot
## Project Specification Document

**Last Updated:** 2025-12-25
**Status:** In Progress - Requirements Gathering

---

## 1. Executive Summary

### Problem Statement
The user provides AA/NA sponsorship to Russian-speaking individuals, many of whom cannot access Cal.com directly due to internet restrictions in Russia. This creates a barrier for sponsees to schedule appointments, forcing them to use less efficient workarounds (manual coordination, alternative tools, or going without proper scheduling).

### Proposed Solution
A Telegram bot that acts as a Cal.com booking interface, allowing sponsees in restricted regions to schedule appointments through Telegram. The bot will use the Cal.com API to create bookings that automatically sync to the user's Google Calendar via existing Cal.com integration, providing identical functionality to the web booking experience.

### Success Criteria
- Sponsees in Russia can book appointments without accessing Cal.com directly
- Bookings appear in user's Google Calendar identically to web bookings
- Button-driven interface requires no command memorization
- Access control prevents spam while accommodating users without Telegram usernames

### High-Level Timeline
- **Phase 1:** Core booking flow (view availability, create bookings)
- **Phase 2 (Future):** Booking management (cancel/reschedule)
- **Phase 3 (Future):** Reminder system

---

## 2. Project Glossary

| Term | Definition |
|------|------------|
| **Sponsee** | Individual receiving AA/NA sponsorship from the user |
| **Cal.com** | Online scheduling platform (like Calendly) that integrates with Google Calendar |
| **Event Type** | Specific type of appointment in Cal.com (e.g., "30-minute Step Work Session") |
| **Telegram Bot** | Automated account on Telegram that responds to user messages |
| **Cal.com API** | Programming interface to create/manage Cal.com bookings programmatically |
| **Whitelist** | Approved list of Telegram users who can access the bot |
| **Chat ID** | Telegram's unique numeric identifier for each user (independent of username) |
| **Username** | Optional Telegram handle (e.g., @username) - not all users have one |
| **Inline Button** | Clickable button embedded in Telegram message |
| **Event Slug** | URL-friendly identifier for Cal.com event type (e.g., "step-work-session") |

---

## 3. User Research

### User Personas

#### Primary User (Bot Owner)
- **Role:** AA/NA sponsor, meeting organizer
- **Location:** Outside Russia (has Cal.com access)
- **Technical Sophistication:** Moderate (can set up integrations, comfortable with APIs)
- **Current Tools:** Cal.com, Google Calendar, Telegram
- **Pain Point:** Sponsees cannot access Cal.com to book appointments
- **Goal:** Provide seamless booking experience for sponsees regardless of location

#### Secondary Users (Sponsees)
- **Role:** Individuals receiving sponsorship
- **Location:** Primarily Russia (Cal.com blocked/restricted)
- **Technical Sophistication:** Varies (basic Telegram users)
- **Current Tools:** Telegram
- **Pain Point:** Cannot access Cal.com to schedule; must use workarounds
- **Goal:** Easily schedule appointments without technical barriers
- **Key Characteristic:** Not all have Telegram usernames (some are "private" accounts)

### Current Workflow

**Without Bot:**
1. Sponsee messages sponsor directly on Telegram: "When can we meet?"
2. Manual back-and-forth to find available time
3. Sponsor manually adds to Google Calendar
4. Manual reminders required
5. Inefficient, time-consuming, error-prone

**With Cal.com (When Accessible):**
1. User shares Cal.com link (e.g., cal.com/username/step)
2. Sponsee views availability
3. Sponsee provides: name, email, meeting method preference
4. Cal.com creates booking → syncs to Google Calendar
5. Automatic confirmation email sent
6. Both parties receive calendar invites

**Desired Workflow (With Bot):**
1. Sponsee (pre-approved) opens bot in Telegram
2. Clicks buttons to view availability and select time
3. Provides required info (first name, timezone, optional email)
4. Bot creates booking via Cal.com API
5. Booking appears in Google Calendar (identical to web booking)
6. Bot sends confirmation message
7. (Optional) Cal.com sends email if email provided

---

## 4. Functional Requirements

### 4.1 Feature Prioritization (MoSCoW)

#### MUST HAVE (Phase 1 - MVP)
1. **Access Control System**
   - Whitelist management (add/remove approved users)
   - User identification by Chat ID (not username dependency)
   - Block unauthorized users with helpful message

2. **View Available Time Slots**
   - Fetch availability from Cal.com for specific event type
   - Display in sponsee's timezone
   - Handle timezone conversion correctly

3. **Create Booking**
   - Collect required information (first name, timezone)
   - Optional email collection
   - Submit booking to Cal.com API
   - Confirm booking created successfully

4. **Button-Driven Interface**
   - No command memorization required
   - Inline buttons for all interactions
   - Clear, intuitive flow

5. **Booking Confirmation**
   - Immediate Telegram message confirming booking details
   - Include: date, time (in user's timezone), meeting method (Telegram)

#### SHOULD HAVE (Phase 2)
1. **View My Bookings**
   - Show upcoming appointments for this sponsee
   - Display in user's timezone

2. **Cancel Booking**
   - Allow user to cancel their own booking
   - Update Cal.com via API
   - Send cancellation confirmation

3. **Reschedule Booking**
   - Cancel existing + book new time in one flow
   - Or update existing booking if API supports

#### COULD HAVE (Phase 3)
1. **Reminder System**
   - Send Telegram reminder before appointment (24h, 1h options)
   - Configurable reminder timing

2. **Admin Dashboard**
   - View all upcoming bookings via bot
   - Manage whitelist via bot interface
   - Bot analytics/usage stats

#### WON'T HAVE (Explicitly Deferred)
1. Multi-language support (Russian/English) - English only for now
2. Group booking/scheduling
3. Payment integration
4. Meeting notes/summary features
5. Integration with other calendar systems beyond Cal.com

---

### 4.2 User Stories

#### Epic 1: Access Control

**US-1.1:** As a **sponsor**, I want to **whitelist specific Telegram users** so that **only my sponsees can book my time and I avoid spam**.

**Acceptance Criteria:**
- Admin can add user by Chat ID
- Admin can remove user from whitelist
- System blocks non-whitelisted users with clear message
- Works even if user has no Telegram username

**US-1.2:** As a **sponsee**, when I **first interact with the bot**, I want to **know if I have access** so that **I understand whether I can proceed**.

**Acceptance Criteria:**
- Non-whitelisted user receives friendly message: "Please contact [sponsor] to request access"
- Whitelisted user sees welcome message and booking options
- Bot provides user's Chat ID in rejection message (for easy whitelisting)

#### Epic 2: Core Booking Flow

**US-2.1:** As a **sponsee**, I want to **see available appointment times** so that **I can choose a time that works for me**.

**Acceptance Criteria:**
- Bot displays available time slots for configured Cal.com event type
- Times shown in sponsee's selected timezone
- Grouped by day for easy scanning
- Shows reasonable range (e.g., next 14 days)

**US-2.2:** As a **sponsee**, I want to **select a time slot using buttons** so that **I don't have to type or remember commands**.

**Acceptance Criteria:**
- Each time slot is a clickable button
- Clear date/time formatting
- "Load more dates" option if needed
- "Go back" navigation

**US-2.3:** As a **sponsee**, I want to **provide my information** so that **the booking is created with my details**.

**Acceptance Criteria:**
- Bot asks for: First name, Timezone (from dropdown/search)
- Bot optionally asks for: Email
- Validates input (timezone is valid, name is not empty)
- Allows editing before confirmation

**US-2.4:** As a **sponsee**, I want to **confirm the booking before it's created** so that **I can catch any mistakes**.

**Acceptance Criteria:**
- Summary shows: Name, Date/Time (in their timezone), Email (if provided)
- [Confirm] and [Cancel] buttons
- Confirmation creates booking via Cal.com API
- Error handling if booking fails

**US-2.5:** As a **sponsee**, I want to **receive a confirmation message** so that **I have a record of my appointment**.

**Acceptance Criteria:**
- Message includes: Date, Time (in their timezone), Duration
- Mentions meeting method (Telegram)
- Friendly, reassuring tone
- If email provided, mentions Cal.com email confirmation

#### Epic 3: Integration with Cal.com

**US-3.1:** As the **system**, I need to **authenticate with Cal.com API** so that **I can create bookings on behalf of the sponsor**.

**Acceptance Criteria:**
- Secure API key storage
- Handles authentication errors gracefully
- Refreshes tokens if needed (depending on Cal.com API design)

**US-3.2:** As the **system**, I need to **create bookings via Cal.com API** so that **they appear in Google Calendar identically to web bookings**.

**Acceptance Criteria:**
- Booking created with correct event type
- Attendee name matches sponsee's first name
- Email included if provided, placeholder (example@example.com) if not
- Timezone correctly passed to API
- Meeting method set to "Telegram" or similar
- Booking appears in sponsor's Google Calendar via Cal.com integration

**US-3.3:** As the **system**, I need to **fetch available time slots** so that **I only show times the sponsor is truly available**.

**Acceptance Criteria:**
- Respects Cal.com event type availability rules
- Accounts for existing bookings (no double-booking)
- Handles timezone conversion correctly
- Caches availability briefly to reduce API calls

---

### 4.3 Workflows

#### Workflow 1: First-Time User Interaction

```
1. Sponsee opens bot link
2. Sponsee clicks /start
3. Bot checks if Chat ID is whitelisted

   IF NOT WHITELISTED:
   4a. Bot: "Hi! This bot is for approved users only.
            Your Chat ID is: 123456789
            Please share this with [sponsor name] to request access."
   5a. END

   IF WHITELISTED:
   4b. Bot: "Welcome! I can help you schedule appointments with [sponsor name]."
   5b. Bot shows menu: [Book Appointment] [View My Bookings] [Help]
   6b. Continue to Workflow 2 if [Book Appointment] selected
```

#### Workflow 2: Booking an Appointment

```
1. User clicks [Book Appointment]
2. Bot: "First, I need to know your timezone for accurate times."
   Shows timezone selector (dropdown or search)
3. User selects timezone (e.g., "Europe/Moscow")
4. Bot stores timezone preference
5. Bot: "Great! Fetching available times..."
   Calls Cal.com API to get availability
6. Bot displays time slots grouped by day:
   "Available times (Europe/Moscow timezone):

   Monday, Jan 6
   [10:00 AM] [2:00 PM] [4:00 PM]

   Tuesday, Jan 7
   [10:00 AM] [11:00 AM] [3:00 PM]

   [Load More Dates] [Change Timezone]"

7. User clicks a time slot button (e.g., [2:00 PM] on Jan 6)
8. Bot: "What's your first name?"
9. User types: "Ivan"
10. Bot: "Would you like to provide an email for Cal.com confirmations?"
    [Yes, I'll enter email] [No, skip]
11a. IF YES: Bot: "Please enter your email:"
     User types: "ivan@example.com"
     Bot validates email format
12.  Bot: "Please confirm your booking:
     Name: Ivan
     Time: Monday, January 6, 2:00 PM (Europe/Moscow)
     Duration: 30 minutes
     Email: ivan@example.com (or 'None' if skipped)

     [Confirm Booking] [Cancel]"
13.  User clicks [Confirm Booking]
14.  Bot: "Creating your booking..."
     Calls Cal.com API to create booking
15a. IF SUCCESS:
     Bot: "All set! Your appointment is confirmed for:
          Monday, January 6 at 2:00 PM (Europe/Moscow)

          We'll connect via Telegram at that time.
          [email notice if provided]

          [Book Another] [View My Bookings] [Main Menu]"
15b. IF FAILURE:
     Bot: "Sorry, something went wrong. This time may no longer be available.
          [Try Again] [View Available Times]"
```

#### Workflow 3: Admin Whitelisting User (Manual Process)

```
1. Sponsee contacts sponsor outside bot: "Can I get access to your booking bot?"
2. Sponsee shares their Chat ID (from bot's rejection message)
   OR sponsor asks them to message the bot and share the Chat ID from response
3. Sponsor adds Chat ID to whitelist (via config file or admin command)
   Methods TBD: environment variable, database, bot admin command
4. Sponsor: "You're all set! Try the bot now."
5. Sponsee can now use bot (returns to Workflow 1, whitelisted path)
```

---

### 4.4 Data Requirements

#### Data to Capture (Per Booking)

| Field | Source | Required | Notes |
|-------|--------|----------|-------|
| **Chat ID** | Telegram API | Yes | Unique user identifier |
| **First Name** | User input | Yes | For booking record |
| **Timezone** | User selection | Yes | For display and API |
| **Email** | User input | No | Optional; use placeholder if not provided |
| **Selected DateTime** | User selection | Yes | In UTC for API |
| **Event Type ID** | Configuration | Yes | Which Cal.com event type |

#### Data to Store (Bot State)

| Data | Purpose | Storage Method |
|------|---------|----------------|
| **Whitelist** | Access control | Config file / Database / Env var |
| **User Timezone Preferences** | Remember for future bookings | Database / In-memory cache |
| **Conversation State** | Track where user is in booking flow | In-memory / Redis / Database |
| **Cal.com API Credentials** | Authentication | Environment variables (secure) |

#### Data to Fetch (From Cal.com API)

- Available time slots for event type
- Event type details (duration, name, description)
- Booking confirmation details
- (Future) Existing bookings for user

---

## 5. Non-Functional Requirements

### 5.1 Performance & Scale

**Expected Usage:**
- **Current Active Users:** 2 sponsees need bot immediately
- **Total Sponsees:** Works with 10+ total, scalability to ~50 users
- **Booking Frequency:** Multiple bookings per week
- **Concurrent Users:** Unlikely, but possible (not a primary concern)

**Performance Expectations:**
- **Target:** <10 seconds response time
- **Acceptable:** Up to 10 seconds with loading indicators
- **Key insight:** Loading messages ("Fetching times...") make longer waits acceptable
- **Booking creation:** <10 seconds
- **Button interactions:** <3 seconds for non-API operations

**Architecture Implications:**
- Low concurrency needs - simple locking or no locking required
- No aggressive performance optimization needed at this scale
- Caching strategy for availability to reduce API calls and improve response time

**Scalability Considerations:**
- Design should work for 50-100+ users without major rewrite
- API rate limiting awareness (Cal.com API limits TBD)
- SQLite sufficient for this scale; can migrate to PostgreSQL if needed

---

### 5.2 Security Requirements

**Authentication & Authorization:**
- **Cal.com API key:** Environment variables only (NEVER hardcoded or committed to git)
- **Critical:** User exposed API key in conversation - must be rotated immediately
- **Whitelist:** Prevents unauthorized access via Telegram User ID
- **Request-based approval:** Admin sees who is requesting access before approving

**Data Protection:**
- **Privacy requirement:** Sponsees cannot see each other (isolated interactions)
- **Booking data:** Not sensitive, logging OK for debugging
- Email addresses not stored long-term (Cal.com manages them)
- HTTPS for all API communication
- Telegram Bot API uses encryption by default

**API Security:**
- API keys in .env file (added to .gitignore)
- Input validation (prevent injection attacks)
- Error messages don't leak sensitive information
- Rate limiting consideration (low volume, not critical)

**Data Sensitivity:**
- Booking data is NOT sensitive (user confirmed)
- Logging enabled for debugging (acceptable)
- No PII concerns beyond first name + optional email

---

### 5.3 Reliability & Availability

**Acceptable Downtime:**
- Not mission-critical; brief outages acceptable
- Goal: 95%+ uptime during business hours

**Error Handling Strategy:**
- **User-facing:** Notify user of error, suggest trying again later or messaging directly
- **Retry logic:** Attempt 2-3 retries for transient failures, then fail gracefully
- **Acceptable:** Simple retry implementation (no complex queue system)
- **Fallback:** Clear message to contact admin directly if bot fails

**Example Error Messages:**
- "Sorry, the booking service is temporarily unavailable. Please try again in a few minutes or message @[admin] directly."
- "Something went wrong creating your booking. This time slot may no longer be available. Please try selecting a different time."

**Backup & Recovery:**
- Whitelist and user preferences stored in SQLite (must be backed up)
- Conversation state can be in-memory (acceptable to lose on restart)
- No critical data loss if bot restarts

**Monitoring:**
- Log errors and API failures for debugging
- Basic file-based logging sufficient
- Optional: Alert on repeated failures (not critical for MVP)

---

### 5.4 Data Storage & Persistence

**Storage Technology:** SQLite database

**Data to Store:**

1. **Whitelist Table:**
   ```sql
   CREATE TABLE whitelist (
       telegram_id INTEGER PRIMARY KEY,
       display_name TEXT,
       username TEXT,  -- NULL if user doesn't have username
       approved_at TIMESTAMP,
       approved_by INTEGER  -- admin's telegram_id
   );
   ```

2. **User Preferences Table:**
   ```sql
   CREATE TABLE user_preferences (
       telegram_id INTEGER PRIMARY KEY,
       timezone TEXT NOT NULL,
       created_at TIMESTAMP,
       updated_at TIMESTAMP
   );
   ```

**Persistence Requirements:**
- **Timezone preferences:** Remember forever (user selects once)
- **Whitelist:** Persistent, backed up regularly
- **Conversation state:** In-memory is acceptable (can lose on restart)
- **Booking history:** NOT stored (Cal.com is source of truth)

**Timezone Selection UX:**
- **Approach:** Button-based timezone selection
- **Context:** All sponsees are in Russia
- **Implementation:** Inline keyboard with Russian timezones:
  - Moscow Time (MSK - Europe/Moscow) UTC+3
  - Samara Time (SAMT - Europe/Samara) UTC+4
  - Yekaterinburg Time (YEKT - Asia/Yekaterinburg) UTC+5
  - Omsk Time (OMST - Asia/Omsk) UTC+6
  - Krasnoyarsk Time (KRAT - Asia/Krasnoyarsk) UTC+7
  - Irkutsk Time (IRKT - Asia/Irkutsk) UTC+8
  - Yakutsk Time (YAKT - Asia/Yakutsk) UTC+9
  - Vladivostok Time (VLAT - Asia/Vladivostok) UTC+10
  - Magadan Time (MAGT - Asia/Magadan) UTC+11
  - Kamchatka Time (PETT - Asia/Kamchatka) UTC+12
  - "Other" option if user is traveling

**Whitelist Management Flow:**
- **Approach:** Request-based approval (Option C from requirements)
- **User experience:**
  1. New user messages bot → Bot rejects with "access request sent"
  2. Admin receives notification with: Name, Username (if available), Telegram ID
  3. Admin replies `/approve <telegram_id>` to grant access
  4. User receives approval notification
- **Critical requirement:** Admin must see who is requesting (name/username)
- **User identification:** Use Telegram User ID for security, show display name for convenience

**User Identity Handling:**
- **Not all users have usernames** (username is optional on Telegram)
- **All users have display names**
- **Implementation:**
  - Store and use Telegram User ID for whitelist/security
  - Show display name in admin notifications for convenience
  - Show username too if available: "John Smith (@johnsmith)"

---

### 5.5 Hosting & Deployment

**Deployment Platform:** fly.io

**Rationale:**
- Free tier sufficient for this use case
- Simple Docker-based deployment
- Scalable if needs grow
- User comfortable with deployment process

**Environment:**
- **Production:** fly.io cloud deployment
- **Development:** Local testing

**Infrastructure Requirements:**
- Persistent storage for SQLite database
- Environment variable management (.env file)
- Logging output accessible for debugging

---

### 5.6 Maintainability

**Code Quality:**
- Well-documented code
- Modular design (separate Cal.com API client, Telegram handler, business logic)
- Type hints (if using Python)

**Testing:**
- Unit tests for Cal.com API integration
- Mock API responses for testing
- Manual testing flow for Telegram interactions

**Configuration:**
- Externalized configuration (event type ID, API keys, whitelist)
- Easy to update without code changes

---

## 6. Technical Architecture

**Last Updated:** Phase 4 Complete - 2025-12-26

### 6.1 System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         TELEGRAM                            │
│                     (User Interface)                        │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ Telegram Bot API (Long Polling)
                 │
┌────────────────▼────────────────────────────────────────────┐
│                      TELECALBOT                             │
│                 (Python 3.11+ Application)                  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │         Telegram Bot Handler                         │  │
│  │  Library: python-telegram-bot v20+                   │  │
│  │  - Message routing                                   │  │
│  │  - Button callbacks                                  │  │
│  │  - ConversationHandler (in-memory state)             │  │
│  │  - Dynamic message editing (loading indicators)      │  │
│  └──────────────────┬──────────────────────────────────┘  │
│                     │                                       │
│  ┌──────────────────▼──────────────────────────────────┐  │
│  │         Business Logic Layer                         │  │
│  │  - Access control (whitelist check)                  │  │
│  │  - Booking flow orchestration                        │  │
│  │  - Data validation (Pydantic)                        │  │
│  │  - Timezone conversion (pytz/zoneinfo)               │  │
│  │  - Request-based approval workflow                   │  │
│  └──────────────────┬──────────────────────────────────┘  │
│                     │                                       │
│  ┌──────────────────▼──────────────────────────────────┐  │
│  │         Cal.com API Client                           │  │
│  │  Library: httpx or requests                          │  │
│  │  - API Key authentication                            │  │
│  │  - GET /availability (slots)                         │  │
│  │  - POST /bookings (create)                           │  │
│  │  - Error handling & 2-3 retries                      │  │
│  │  - Brief availability caching                        │  │
│  └──────────────────┬──────────────────────────────────┘  │
│                     │                                       │
│  ┌──────────────────▼──────────────────────────────────┐  │
│  │         Data Store (SQLite)                          │  │
│  │  - Whitelist (telegram_id, display_name, username)   │  │
│  │  - User preferences (timezone)                       │  │
│  │  - Access requests (pending approvals)               │  │
│  │  - Conversation state: IN-MEMORY (acceptable loss)   │  │
│  └─────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ Cal.com API v2 (HTTPS REST)
                 │
┌────────────────▼────────────────────────────────────────────┐
│                        CAL.COM                              │
│                                                             │
│  - Event type: "step" (1-hour sessions)                    │
│  - Availability calculation & slot generation              │
│  - Booking creation & management                           │
│  - Google Calendar integration (automatic sync)            │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Component Interactions

**1. User Interaction Flow**
```
Telegram User → Telegram Servers → Bot Handler → Business Logic → Cal.com Client → Cal.com API
```

**2. Access Control Check**
```
Message Received → Extract Chat ID → Check Whitelist → Allow/Deny
```

**3. Booking Creation**
```
User Input → Validate Data → Convert Timezone → Call Cal.com API → Confirm to User
```

### 6.3 Technology Choices (FINALIZED)

#### Core Technologies

**Programming Language:**
- **Python 3.11+** ✅ **APPROVED**
  - Rationale: Excellent Telegram bot libraries (python-telegram-bot v20+), rich ecosystem, easy timezone handling (pytz/zoneinfo)
  - Type hints for safety
  - Simple deployment to fly.io

**Telegram Bot Framework:**
- **python-telegram-bot v20+** ✅ **APPROVED**
  - Rationale: Mature, well-documented, excellent ConversationHandler for state management
  - Built-in support for inline keyboards and callback queries
  - Supports message editing for loading indicators
  - Long polling mode (no webhook setup needed)

**Cal.com API Client:**
- **Custom implementation using httpx or requests** ✅ **APPROVED**
  - Rationale: Cal.com API v2 is REST-based, no official Python SDK
  - Direct HTTP calls give full control
  - **Choice:** httpx preferred (modern, async support if needed later)
  - Fallback: requests (simpler, synchronous)

**Data Storage:**
- **SQLite** ✅ **APPROVED**
  - Rationale: Simple, no infrastructure needed, sufficient for 50-100 users
  - Whitelist management
  - User timezone preferences
  - Access request tracking
  - Built into Python standard library
  - **Future migration path:** PostgreSQL if scale exceeds 100+ users

**Conversation State Management:**
- **In-memory (python-telegram-bot ConversationHandler)** ✅ **APPROVED**
  - Rationale: Simple, built-in to library
  - State loss on restart is acceptable per user requirements
  - No external dependencies (no Redis/database needed for state)

**Loading Indicators:**
- **Dynamic message editing (message.edit_text)** ✅ **APPROVED**
  - Better UX: messages update in place
  - Minimal complexity increase (~3 extra lines of code)
  - Graceful fallback for 48-hour Telegram edit limit

**Hosting:**
- **fly.io** ✅ **APPROVED**
  - Rationale: Free tier sufficient, Docker-based deployment, user comfortable with platform
  - Persistent storage for SQLite database
  - Simple scaling if needed

**Admin Configuration:**
- **Admin Telegram User ID:** `7919030739` ✅ **CONFIRMED**
  - Receives access requests from new users
  - Approves/rejects via bot commands

**Cal.com Event Configuration:**
- **Event Slug:** `"step"` ✅ **CONFIRMED**
  - Event URL: cal.com/pashaf/step
  - Event Type: 1-hour sessions (hardcoded for MVP)
  - Future: Support multiple event types (30-min, 60-min selection)

**Configuration Management:**
- **Environment Variables** (.env file with python-decouple)
  - Store: Cal.com API key, Telegram bot token, admin user ID
  - **.gitignore:** Ensure .env is NEVER committed

- **SQLite Database** (telecalbot.db)
  - Store: Whitelist, user preferences, access requests

#### Key Libraries (Python Stack)

| Library | Purpose | Status |
|---------|---------|--------|
| `python-telegram-bot>=20.0` | Telegram Bot API wrapper | ✅ Required |
| `httpx` | HTTP client for Cal.com API | ✅ Preferred |
| `pytz` or `zoneinfo` (stdlib) | Timezone handling | ✅ Required |
| `python-decouple` | Environment variable management | ✅ Required |
| `pydantic` | Data validation | ✅ Recommended |
| `sqlite3` (stdlib) | Lightweight database | ✅ Built-in |

### 6.4 API Contracts

#### Cal.com API Integration (v2 REST API)

**Base URL:** `https://api.cal.com/v2`

**Authentication:**
- Method: API Key in header
- Header: `cal-api-version: 2024-08-13` (or latest stable version)
- Header: `Authorization: Bearer {API_KEY}`
- API Key: Obtained from Cal.com account settings

**Required Endpoints:**

---

**1. Get Availability (Slots)**

**Endpoint:** `GET /v2/slots/available`

**Query Parameters:**
```
startTime: ISO 8601 datetime (e.g., "2025-01-06T00:00:00Z")
endTime: ISO 8601 datetime
eventTypeId: integer (Cal.com event type ID)
timeZone: IANA timezone string (e.g., "Europe/Moscow")
```

**Example Request:**
```bash
GET https://api.cal.com/v2/slots/available?startTime=2025-01-06T00:00:00Z&endTime=2025-01-20T23:59:59Z&eventTypeId=12345&timeZone=Europe/Moscow
Authorization: Bearer {API_KEY}
cal-api-version: 2024-08-13
```

**Example Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "slots": {
      "2025-01-06": ["10:00:00", "14:00:00", "16:00:00"],
      "2025-01-07": ["10:00:00", "11:00:00", "15:00:00"]
    }
  }
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid API key
- `404 Not Found`: Invalid event type ID
- `429 Too Many Requests`: Rate limit exceeded (likely 100-300 requests/minute)

**Caching Strategy:**
- Cache availability for 5-10 minutes to reduce API calls
- Invalidate cache after booking creation
- Use in-memory cache (simple dict with timestamp)

---

**2. Create Booking**

**Endpoint:** `POST /v2/bookings`

**Request Body:**
```json
{
  "eventTypeId": 12345,
  "start": "2025-01-06T14:00:00Z",
  "attendee": {
    "name": "Ivan",
    "email": "ivan@example.com",
    "timeZone": "Europe/Moscow",
    "language": "en"
  },
  "meetingUrl": "telegram",
  "metadata": {
    "telegram_user_id": "123456789",
    "booked_via": "telegram_bot"
  }
}
```

**Field Notes:**
- `eventTypeId`: Integer event type ID (obtain from Cal.com dashboard)
- `start`: ISO 8601 datetime in UTC
- `attendee.name`: First name (required)
- `attendee.email`: Email address
  - **CRITICAL RESEARCH NEEDED:** Can we use placeholder email (e.g., "telegram-user@placeholder.com")?
  - **Fallback:** Make email required if placeholder not supported
- `attendee.timeZone`: User's timezone for confirmation emails
- `meetingUrl`: Custom field - set to "telegram" or similar to indicate meeting method
- `metadata`: Custom fields for tracking (Telegram user ID, bot source)

**Example Response (201 Created):**
```json
{
  "status": "success",
  "data": {
    "id": "booking_abc123",
    "uid": "unique_booking_uid",
    "eventTypeId": 12345,
    "title": "Step Work Session",
    "startTime": "2025-01-06T14:00:00Z",
    "endTime": "2025-01-06T15:00:00Z",
    "attendees": [
      {
        "name": "Ivan",
        "email": "ivan@example.com",
        "timeZone": "Europe/Moscow"
      }
    ],
    "status": "ACCEPTED"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid data (e.g., time slot no longer available, invalid email format)
- `401 Unauthorized`: Invalid API key
- `404 Not Found`: Invalid event type ID
- `409 Conflict`: Time slot already booked (race condition)
- `422 Unprocessable Entity`: Validation errors (e.g., required field missing)
- `429 Too Many Requests`: Rate limit exceeded

**Bot Error Handling Strategy:**
- `400/409`: "Sorry, this time is no longer available. Please select another time."
- `401`: Log error, notify admin, show generic error to user
- `422`: "There was a problem with your booking information. Please try again."
- `429`: Retry after delay (exponential backoff: 1s, 2s, 4s)
- `500/502/503`: Retry 2-3 times, then: "Cal.com is temporarily unavailable. Please try again in a few minutes."

---

**3. Get Event Type Details (Optional - for validation)**

**Endpoint:** `GET /v2/event-types/{eventTypeId}`

**Purpose:** Fetch event type metadata (duration, name, availability rules)

**Use Case:** Validate event type configuration on bot startup

---

**4. Get Bookings** (Future - Phase 2)

**Endpoint:** `GET /v2/bookings`

**Query Parameters:**
```
afterStart: ISO datetime (filter bookings after this time)
status: "upcoming" | "past" | "cancelled"
```

**Purpose:** Fetch user's bookings for "View My Bookings" feature

---

**5. Cancel Booking** (Future - Phase 2)

**Endpoint:** `DELETE /v2/bookings/{bookingId}`

**Purpose:** Cancel a booking

---

#### Cal.com API Research - Open Questions

**CRITICAL QUESTIONS TO RESEARCH:**

1. **Placeholder Email Support:**
   - Can we create bookings with placeholder email like "telegram-user-{chat_id}@placeholder.com"?
   - Or does Cal.com require valid email format and send verification?
   - **Test approach:** Create test booking with placeholder email and observe behavior
   - **Fallback:** Make email required if placeholder rejected

2. **Event Type ID Discovery:**
   - How to find event type ID for "step" event?
   - **Method:** Cal.com dashboard → Event Types → Inspect URL or API call
   - **Alternative:** GET /v2/event-types and search by slug "step"

3. **Rate Limits:**
   - What are exact rate limits for Cal.com API v2?
   - **Typical:** 100-300 requests/minute for paid plans, 60/minute for free
   - **Mitigation:** Implement caching, exponential backoff

4. **Meeting URL/Method:**
   - How to specify meeting method as "Telegram" instead of Zoom/Google Meet?
   - **Research:** Check if `meetingUrl` field accepts custom values
   - **Fallback:** Use `metadata` or `notes` field to indicate Telegram meeting

5. **API Version Stability:**
   - Is `cal-api-version: 2024-08-13` the current stable version?
   - **Action:** Check Cal.com API docs for latest version header

**Research Resources:**
- Official Docs: https://cal.com/docs/api-reference/v2
- API Explorer: https://api.cal.com/docs
- Community: Cal.com Discord/GitHub issues

---

**Error Handling Contract Summary:**

| Status Code | Meaning | Bot Action |
|------------|---------|------------|
| `200/201` | Success | Process response normally |
| `400` | Bad request (invalid data) | User-friendly error: "Invalid booking data" |
| `401` | Unauthorized | Log error, notify admin, generic message to user |
| `404` | Not found (invalid event type) | Configuration error - notify admin |
| `409` | Conflict (slot taken) | "This time is no longer available. Please select another." |
| `422` | Validation error | "Please check your information and try again." |
| `429` | Rate limit | Retry with exponential backoff (1s, 2s, 4s) |
| `500/502/503` | Server error | Retry 2-3 times, then friendly error message |

Bot must handle all error codes gracefully with user-friendly messages and retry logic.

#### Telegram Bot API

**Webhook vs. Polling:**
- **Phase 1:** Long polling (simpler setup, no public URL needed)
- **Future:** Webhook (more efficient for production)

**Message Types:**
- Text messages (for name, email input)
- Inline keyboard buttons (for selections)
- Callback queries (button clicks)

---

## 7. Development Approach

### 7.1 Iteration Strategy

**Phase 1: Tracer Bullet - End-to-End MVP**

*Goal: Minimal working system that demonstrates full flow*

**Sprint 1:** Infrastructure Setup
- Set up Python project structure
- Configure Telegram bot (create bot via BotFather)
- Test basic "Hello World" bot
- Set up Cal.com API authentication
- Test API connection (fetch availability)

**Sprint 2:** Access Control
- Implement whitelist loading from config file
- Add Chat ID check on /start
- Test with whitelisted and non-whitelisted users

**Sprint 3:** Core Booking Flow
- Implement timezone selection
- Fetch and display availability
- Handle time slot selection
- Collect user information (name, email)
- Create booking via Cal.com API
- Send confirmation message

**Sprint 4:** Refinement & Error Handling
- Add input validation
- Improve error messages
- Add "go back" navigation
- Test edge cases
- Documentation

**Delivery:** Working bot that allows whitelisted users to book appointments

---

**Phase 2: Booking Management** (Future)

- View my bookings
- Cancel booking
- Reschedule booking
- Admin commands for whitelist management

---

**Phase 3: Enhancements** (Future)

- Reminder system
- Analytics
- Multi-language support
- Advanced admin features

---

### 7.2 Testing Strategy

**Manual Testing (Primary):**
- Test each user flow with real Telegram bot
- Verify bookings appear in Google Calendar
- Test with multiple timezones
- Test error scenarios (bad API key, invalid input)

**Automated Testing:**
- Unit tests for Cal.com API client
  - Mock API responses
  - Test timezone conversion
  - Test data validation

- Unit tests for business logic
  - Whitelist checking
  - Input validation
  - Timezone handling

**Integration Testing:**
- Test against Cal.com API staging/sandbox (if available)
- Test Telegram bot in test environment before production

**User Acceptance Testing:**
- User tests with one trusted sponsee
- Gather feedback on UX
- Iterate based on real usage

---

### 7.3 Quality Standards

**Code Quality:**
- Follow PEP 8 (Python style guide)
- Type hints for all functions
- Docstrings for complex functions
- No hardcoded values (use config)

**Error Handling:**
- Never show raw exceptions to users
- Log all errors for debugging
- Graceful degradation (if API down, show friendly message)

**Security:**
- Never commit API keys to git (.env in .gitignore)
- Validate all user input
- Use HTTPS for all API calls

**"No Broken Windows" Policy:**
- Fix bugs immediately
- Don't leave TODO comments for critical issues
- Refactor as you go (don't accumulate technical debt)

---

## 8. Risks and Mitigation (UPDATED)

### 8.1 Technical Risks

| Risk | Impact | Probability | Mitigation | Status |
|------|--------|-------------|------------|--------|
| **Cal.com API changes** | High | Medium | Version API endpoints; monitor Cal.com changelog; have fallback to manual booking | ⚠️ Monitor |
| **Telegram username assumption** | High | Low | Use Chat ID (not username) for whitelist | ✅ **RESOLVED** |
| **Timezone conversion bugs** | Medium | Medium | Extensive testing; use well-established library (pytz); include tests for common timezones | ⚠️ Mitigate |
| **Cal.com API rate limits** | Medium | Low | Implement caching (5-10 min); exponential backoff retry; monitor usage | ⚠️ Mitigate |
| **Bot hosting downtime (fly.io)** | Medium | Low | fly.io free tier reliable; document restart procedure; health check endpoint | ⚠️ Monitor |
| **Email placeholder rejection** | Medium | Medium | Test with Cal.com API during development; make email required if placeholder not supported | ⚠️ **RESEARCH NEEDED** |
| **Event Type ID discovery** | Low | Low | GET /v2/event-types API call; inspect Cal.com dashboard | ⚠️ **RESEARCH NEEDED** |
| **Placeholder email not syncing to Google Calendar** | Medium | Medium | Test end-to-end: bot → Cal.com → Google Calendar; validate calendar entry | ⚠️ **TEST REQUIRED** |
| **Message edit failures (48-hour limit)** | Low | Very Low | Try/except block; fallback to new message if edit fails | ✅ **HANDLED** |

---

### 8.2 User Experience Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Users confused by timezone selection** | Low | Medium | Provide clear examples; default to common timezone (Europe/Moscow); allow easy change |
| **Users book wrong time due to timezone confusion** | High | Low | Always show time in THEIR timezone; confirm before booking; show timezone name in confirmation |
| **Users forget they booked** | Medium | Medium | Phase 3: Implement reminders; Phase 1: Clear confirmation message |
| **Whitelist management friction** | Medium | High | Document clear process; consider admin bot commands in Phase 2 |

---

### 8.3 Open Questions Requiring Research (UPDATED)

**RESOLVED:**
- ✅ Telegram Bot Hosting: fly.io (approved)
- ✅ Polling vs. webhook: Long polling (approved)
- ✅ Whitelist Management: Request-based approval via bot commands (approved)
- ✅ Timezone UX: Button-based selection with Russian timezones (approved)
- ✅ Admin User ID: 7919030739 (confirmed)
- ✅ Event Type: "step" (confirmed)

**STILL OPEN (Research Required):**

1. **Cal.com API Specifics:**
   - ⚠️ **CRITICAL:** Does API accept placeholder email (e.g., "telegram-user-123@placeholder.com")?
   - ⚠️ **CRITICAL:** How to find Event Type ID for "step" event?
   - ⚠️ What are exact rate limits for Cal.com API v2?
   - ⚠️ How to set meeting method to "Telegram" (meetingUrl field or metadata)?
   - ⚠️ What is the current stable API version header (cal-api-version)?
   - ⚠️ Does Cal.com support webhook notifications for booking changes? (Future use)

2. **End-to-End Testing:**
   - ⚠️ Test booking creation flow: Bot → Cal.com API → Google Calendar sync
   - ⚠️ Verify placeholder email (if supported) appears correctly in Google Calendar
   - ⚠️ Confirm timezone conversion accuracy across all Russian timezones
   - ⚠️ Test error scenarios (rate limits, invalid data, API downtime)

**Action Items Before Implementation:**
1. Research Cal.com API documentation (https://cal.com/docs/api-reference/v2)
2. Test placeholder email support with Cal.com API
3. Obtain Event Type ID from Cal.com dashboard
4. Create test booking via API to validate end-to-end flow
5. Document actual API behavior vs. assumptions

---

## 9. Timeline and Milestones

### Phase 1: MVP (Core Booking Flow)

**Estimated Duration:** 2-3 weeks (depends on development pace)

**Milestones:**

1. **M1: Project Setup** (2-3 days)
   - Development environment ready
   - Telegram bot created and tested
   - Cal.com API access confirmed
   - Repository initialized

2. **M2: Access Control Working** (2-3 days)
   - Whitelist implementation complete
   - Bot blocks unauthorized users
   - Testing with multiple Chat IDs

3. **M3: Booking Flow Complete** (5-7 days)
   - Timezone selection working
   - Availability display working
   - Booking creation working
   - End-to-end flow tested

4. **M4: MVP Ready for User Testing** (3-4 days)
   - Error handling polished
   - User messages refined
   - Documentation written
   - Deployed to hosting environment

5. **M5: Production Launch** (After user testing)
   - Feedback incorporated
   - Real sponsees onboarded
   - Monitoring in place

---

### Phase 2: Booking Management (Future)

**Estimated Duration:** 1-2 weeks

**Features:**
- View bookings
- Cancel bookings
- Reschedule bookings
- Admin whitelist management via bot

---

### Phase 3: Enhancements (Future)

**Estimated Duration:** 2-4 weeks

**Features:**
- Reminder system
- Analytics
- Advanced admin features

---

## 10. Success Metrics

### How We'll Measure Success

**Primary Metrics:**
1. **Booking Success Rate**
   - Target: >95% of booking attempts succeed
   - Measure: Track successful vs. failed booking API calls

2. **User Adoption**
   - Target: All sponsees using bot instead of manual scheduling within 1 month
   - Measure: Number of active users

3. **Time Saved**
   - Target: Reduce scheduling coordination time by 80%
   - Measure: Qualitative feedback from user

**Secondary Metrics:**
1. **Error Rate**
   - Target: <5% of interactions result in errors
   - Measure: Error logs vs. total interactions

2. **User Satisfaction**
   - Target: Sponsees find it "easy to use"
   - Measure: Direct feedback, willingness to use repeatedly

3. **Calendar Sync Accuracy**
   - Target: 100% of bookings appear correctly in Google Calendar
   - Measure: Manual verification, user confirmation

---

### Feedback Mechanisms

1. **Direct User Feedback**
   - Ask sponsees after first use: "How was the experience?"
   - Note any confusion points or errors

2. **Usage Analytics**
   - Track: Number of bookings created
   - Track: Common drop-off points in flow
   - Track: Most common errors

3. **Sponsor Feedback**
   - Weekly review: Any issues? Any booking confusion?
   - Review calendar for accuracy

---

---

## 11. Phase 5-8: Final Specification Phases (COMPLETE)

### Phase 5: Development Approach (APPROVED)

**Iteration Strategy:** ✅ Confirmed
- Tracer bullet approach: End-to-end MVP first
- Iterative refinement based on feedback
- Phase 1 (MVP), Phase 2 (Management), Phase 3 (Enhancements)

**Testing Strategy:** ✅ Confirmed
- Manual testing primary (real Telegram bot testing)
- Unit tests for Cal.com API client (mock responses)
- Unit tests for timezone conversion
- User acceptance testing with trusted sponsee

**Quality Standards:** ✅ Confirmed
- PEP 8 style guide
- Type hints for all functions
- No hardcoded values (use .env and config)
- No broken windows policy

---

### Phase 6: Documentation & Communication

**Documentation Plan:**

1. **README.md** (User-facing):
   - Installation instructions
   - Configuration guide (API keys, admin ID)
   - How to obtain Cal.com API key
   - How to create Telegram bot via BotFather
   - Deployment to fly.io instructions
   - Troubleshooting common issues

2. **Code Documentation**:
   - Docstrings for all functions
   - Type hints (Python 3.11+)
   - Inline comments for complex logic
   - API client contract documentation

3. **Admin Guide**:
   - How to approve/reject access requests
   - How to view bot logs
   - How to restart bot on fly.io
   - How to rotate API keys if compromised

4. **User Guide** (for sponsees):
   - How to request access to bot
   - How to book an appointment
   - Timezone selection guide
   - What to do if errors occur

**Communication Plan:**

**Stakeholder:** Admin (You)
- **Interest:** High - monitoring bot health
- **Sophistication:** High - technical user
- **Detail:** Full technical details, logs, error tracking
- **Motivation:** Bot saves time; errors disrupt workflow

**Stakeholder:** Sponsees
- **Interest:** Medium - just want to book appointments
- **Sophistication:** Low-Medium - basic Telegram users
- **Detail:** Simple instructions, clear error messages
- **Motivation:** Easy scheduling; avoid manual coordination

---

### Phase 7: Risk Assessment (COMPLETE)

**See Section 8 for full risk analysis.**

**Summary of Critical Risks:**

1. **Cal.com API placeholder email rejection** (Medium probability, Medium impact)
   - **Mitigation:** Research during development; fallback to required email

2. **Timezone conversion bugs** (Medium probability, Medium impact)
   - **Mitigation:** Extensive testing with Russian timezones; use pytz library

3. **Cal.com API rate limits** (Low probability, Medium impact)
   - **Mitigation:** Implement caching; exponential backoff retry

4. **Event Type ID discovery** (Low probability, Low impact)
   - **Mitigation:** GET /v2/event-types API call; Cal.com dashboard inspection

**All risks have documented mitigation strategies.**

---

### Phase 8: Ethical Considerations

**Principle: Do No Harm** (Tip 98, 99)

**Analysis:**

1. **Who might be harmed by this system?**
   - **Sponsees:** Privacy concerns if booking data exposed
   - **Admin:** API key compromise could allow unauthorized bookings
   - **Mitigation:**
     - Isolated interactions (sponsees cannot see each other)
     - API keys stored in .env (never committed)
     - Access control via whitelist (no public access)

2. **What safeguards are needed?**
   - **Access control:** Request-based approval prevents spam
   - **Data privacy:** No long-term storage of sensitive data
   - **Secure API handling:** Environment variables, HTTPS only
   - **Error messages:** Don't leak sensitive information

3. **What are the ethical implications?**
   - **Positive:** Enables sponsees in restricted regions to access support
   - **Positive:** Reduces manual coordination burden
   - **Neutral:** No financial transactions or sensitive data handling
   - **No harmful use cases identified**

4. **Are there use cases we should refuse to support?**
   - **No:** This is a scheduling bot for AA/NA sponsorship
   - **No public API access:** Bot is private, access-controlled
   - **No commercial use:** Personal use only

**Ethical Assessment:** ✅ **APPROVED**
- System promotes accessibility (sponsees in Russia)
- No harm to users or third parties
- Privacy-preserving design
- Secure implementation planned

**Agency & Responsibility:**
- We have designed for ethical use
- Access control prevents abuse
- Privacy-first architecture
- No concerning use cases

---

## 12. Final Specification Summary

### Specification Status: ✅ **COMPLETE**

All 8 phases of requirements gathering completed:

| Phase | Status | Key Outcomes |
|-------|--------|--------------|
| **Phase 1: Initial Discovery** | ✅ Complete | Problem domain understood, constraints identified, glossary created |
| **Phase 2: Functional Requirements** | ✅ Complete | Features prioritized (MoSCoW), user stories documented, workflows mapped |
| **Phase 3: Non-Functional Requirements** | ✅ Complete | Performance, security, reliability requirements defined |
| **Phase 4: Technical Architecture** | ✅ Complete | Tech stack finalized (Python, SQLite, fly.io), API contracts documented |
| **Phase 5: Development Approach** | ✅ Complete | Iteration strategy, testing plan, quality standards approved |
| **Phase 6: Documentation & Communication** | ✅ Complete | Documentation plan, stakeholder communication strategy defined |
| **Phase 7: Risk Assessment** | ✅ Complete | All risks identified, mitigation strategies documented |
| **Phase 8: Ethical Considerations** | ✅ Complete | Ethical review passed, no harmful use cases identified |

---

## 13. Implementation Readiness Checklist

### Pre-Implementation Research (REQUIRED)

- [ ] **Cal.com API Research:**
  - [ ] Confirm placeholder email support (or require email)
  - [ ] Obtain Event Type ID for "step" event
  - [ ] Verify API version header (cal-api-version)
  - [ ] Test booking creation API call
  - [ ] Confirm meeting method field (meetingUrl or metadata)

- [ ] **End-to-End Testing:**
  - [ ] Test booking: Bot → Cal.com API → Google Calendar
  - [ ] Verify timezone conversion accuracy
  - [ ] Test error scenarios (rate limits, invalid data)

### Ready to Implement (After Research)

- [ ] **Environment Setup:**
  - [ ] Create Telegram bot via BotFather (get bot token)
  - [ ] Obtain Cal.com API key from dashboard
  - [ ] Set up fly.io account (if not already)
  - [ ] Create .env file template

- [ ] **Project Initialization:**
  - [ ] Initialize Python project structure
  - [ ] Set up virtual environment
  - [ ] Install dependencies (python-telegram-bot, httpx, pytz, etc.)
  - [ ] Create SQLite database schema
  - [ ] Write initial configuration loader

- [ ] **Development Phases:**
  - [ ] Sprint 1: Infrastructure setup (1-2 days)
  - [ ] Sprint 2: Access control (2-3 days)
  - [ ] Sprint 3: Core booking flow (5-7 days)
  - [ ] Sprint 4: Refinement & error handling (3-4 days)
  - [ ] User testing with trusted sponsee
  - [ ] Production launch

---

## 14. Next Steps

### Immediate Actions (Priority Order)

**1. Cal.com API Research** (CRITICAL - 1-2 hours)
   - Visit: https://cal.com/docs/api-reference/v2
   - Test API endpoints with your API key
   - Document findings on placeholder email support
   - Obtain Event Type ID for "step" event
   - Test booking creation flow

**2. Review & Approve Specification** (30 minutes)
   - Read through this complete specification
   - Validate all assumptions
   - Confirm technical decisions
   - Note any missed requirements

**3. Environment Preparation** (1 hour)
   - Create Telegram bot via @BotFather
   - Generate Telegram bot token
   - Obtain Cal.com API key (if not already)
   - Set up fly.io account (if not already)

**4. Begin Implementation** (After steps 1-3)
   - Clone/create project repository
   - Set up Python project structure
   - Install dependencies
   - Begin Sprint 1: Infrastructure setup

---

### Recommended Next Action

**OPTION A: Research Cal.com API First**
- Spend 1-2 hours researching Cal.com API v2 documentation
- Test placeholder email support
- Obtain Event Type ID
- Document findings
- **Then** proceed to implementation

**OPTION B: Begin Implementation (Iterative Discovery)**
- Start building bot infrastructure
- Research Cal.com API as needed during development
- Discover API behavior through experimentation
- More pragmatic, faster to working prototype

**Recommendation:** **Option A** (Research first)
- Reduces risk of discovering blockers mid-implementation
- Critical unknowns (placeholder email, event type ID) could change architecture
- 1-2 hours research saves potential days of rework

---

### Transition to Implementation

**When ready to implement, consider:**

1. **Use spec-architect agent** to create detailed implementation roadmap
   - Translates this specification into step-by-step development plan
   - Breaks down into implementable tasks
   - Generates project structure and file templates

2. **Manual implementation**
   - Follow Sprint 1-4 plan in Section 7.1
   - Reference this specification for all requirements
   - Test frequently against acceptance criteria in Section 4.2

---

## 15. Specification Validation

### Critical Thinking Review (Tip 2: Think! About Your Work)

**Have we truly understood the problem?**
- ✅ Yes: Sponsees in Russia cannot access Cal.com; need Telegram interface
- ✅ Success criteria clear: Parity with Cal.com automated booking flow

**Are we solving the right problem?**
- ✅ Yes: Bot eliminates manual booking coordination
- ✅ Addresses root cause: Cal.com accessibility in Russia

**Have we questioned our assumptions?**
- ✅ Telegram username assumption: RESOLVED (use Chat ID instead)
- ⚠️ Placeholder email assumption: NEEDS RESEARCH
- ⚠️ Event Type ID discovery: NEEDS RESEARCH

**Is this pragmatic or over-engineered?**
- ✅ Pragmatic: SQLite (not PostgreSQL), in-memory state (not Redis), long polling (not webhook)
- ✅ Right-sized for 50-100 users
- ✅ Simple tech stack (Python, SQLite, fly.io)

**What have we designed to be easier to change?**
- ✅ Event type configuration (can add 30-min sessions later)
- ✅ Storage (SQLite → PostgreSQL migration path)
- ✅ Conversation state (in-memory → persistent later if needed)
- ✅ Deployment (fly.io → other platforms if needed)

**Where are we most likely wrong?**
- ⚠️ Cal.com API behavior (placeholder email, meeting method field)
- ⚠️ Rate limits assumptions (need to verify actual limits)
- ⚠️ Error handling scenarios (need real-world testing)

**Mitigation:** Research Cal.com API before implementation begins.

---

### User Delight Focus (Tip 96: Delight Users, Don't Just Deliver Code)

**Does this spec lead to software that will delight users?**
- ✅ Button-driven interface (no command memorization)
- ✅ Dynamic loading indicators (polished UX)
- ✅ Timezone selection with Russian timezones (user-centric)
- ✅ Clear confirmation messages (reassuring)
- ✅ Graceful error handling (no cryptic errors)

**Are we focused on user value, not just technical features?**
- ✅ Success criteria: "Hands-off approach parity"
- ✅ User stories centered on sponsee experience
- ✅ Workflow designed around actual user behavior

**Opportunities to gently exceed expectations:**
- ✅ Remember timezone preference (don't ask every time)
- ✅ Request-based approval (admin sees who's requesting)
- ✅ Friendly error messages with actionable guidance
- ⚠️ Future: Reminder system (Phase 3)

---

## 16. Final Approval & Sign-Off

**Specification Author:** Pragmatic Requirements Gatherer Agent
**Date:** 2025-12-26
**Status:** ✅ **READY FOR REVIEW**

**User Review Required:**
- [ ] Review specification completeness
- [ ] Validate all technical decisions
- [ ] Confirm no missed requirements
- [ ] Approve or request changes

**After Approval:**
- [ ] Research Cal.com API (1-2 hours)
- [ ] Begin implementation OR invoke spec-architect agent for detailed roadmap

---

**END OF SPECIFICATION DOCUMENT**

---

**Document Version:** 2.0 (Complete - All 8 Phases)
**Last Updated:** 2025-12-26
**File Path:** `/Users/pasha/Documents/Programming/projects/active/telecalbot/SPECIFICATION.md`
