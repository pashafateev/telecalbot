# Phase 0 Research Findings

**Date**: 2025-12-29
**Script**: `research/calcom_api_validator.py`
**Results**: `research/api_research_results.json`

---

## Executive Summary

✅ **All critical research questions answered successfully**

The Cal.com API v2 is fully functional and supports all requirements for the Telecalbot MVP. Placeholder emails ARE accepted, which means email collection can be optional for users.

---

## Key Findings

### 1. Event Type Discovery ✅

**Finding**: Event Type ID successfully discovered
**Value**: `2442700`
**Slug**: `step`

**Implementation Decision**:
- Add `CALCOM_EVENT_TYPE_ID=2442700` to `.env`
- Use this ID for all availability and booking requests

---

### 2. API Versioning ✅

**Finding**: Different endpoints require different API versions

**Current verification (2026-07-20)**: Cal.com requires endpoint-specific
`cal-api-version` headers, but the required versions have changed since this
research was first captured. The production client now pins:

| Endpoint | Required Version |
|----------|-----------------|
| `GET /v2/event-types` | `2024-06-14` |
| `GET /v2/slots` | `2024-09-04` |
| `POST /v2/bookings` | `2026-02-25` |
| `POST /v2/bookings/{bookingUid}/cancel` | `2026-02-25` |

**Implementation Decision**:
- Pin each endpoint's required version in the Cal.com client wrapper
- Do not expose a global `CAL_API_VERSION` setting that cannot affect pinned endpoints
- Require every low-level client request to declare its endpoint version

---

### 3. Availability Response Format ✅

**Finding**: Current slots are grouped directly by date and use a `start` field

**Response Structure**:
```json
{
  "2026-01-01": [
    {"start": "2026-01-01T04:00:00.000+03:00"}
  ],
  "2026-01-02": [
    {"start": "2026-01-02T05:00:00.000+03:00"},
    {"start": "2026-01-02T06:00:00.000+03:00"}
  ]
}
```

**Implementation Decision**:
- Normalize current `slot.start` values into the application's `TimeSlot.time` model
- Continue accepting the legacy `{"slots": {date: [{"time": ...}]}}` shape defensively
- Times are already in the requested timezone (ISO format with offset)
- Use `datetime.fromisoformat()` to parse

---

### 4. Placeholder Email Support ✅ 🎉

**Finding**: Placeholder emails ARE ACCEPTED!

**Test Result**:
- Booking created successfully with email: `telegram-user-test@telecalbot.local`
- Booking ID: `14124132`
- Status: `201 Created`

**Implementation Decision**:
- ✅ **Email collection is OPTIONAL**
- Use format: `telegram-user-{telegram_id}@telecalbot.local`
- Allow users to provide real email if they want confirmation emails
- Conversation flow: "Would you like a confirmation email? (Skip / Provide Email)"

**UX Impact**: Reduces friction - users can book without sharing email

---

### 5. Rate Limits ✅

**Finding**: Rate limit headers present in responses

**Headers Observed**:
```
x-ratelimit-limit-default: 120
x-ratelimit-remaining-default: 118
x-ratelimit-reset-default: 60
```

**Limit**: 120 requests per minute (per API key)

Cal.com responses observed during research exposed `x-ratelimit-*` headers rather
than `Retry-After`. The client's bounded `Retry-After` handling is defensive for
429 responses from Cal.com or an intermediary, not the primary observed signal.

**Implementation Decision**:
- Implement exponential backoff for 429 errors
- Cache availability for 5-10 minutes to reduce API calls
- Track rate limit headers and pause if approaching limit
- 120 req/min is generous for expected usage (50-100 users)

---

### 6. Meeting Method Field ✅

**Finding**: `meetingUrl` field identified in booking response

**Implementation Decision**:
- After booking creation, meeting method can be retrieved from `meetingUrl` field
- For Telegram meetings, we can set this via Cal.com event configuration
- Meeting instructions in booking confirmation should reference Telegram

---

### 7. Booking Request Format ✅

**Finding**: Successful booking format validated

**Working Payload**:
```json
{
  "eventTypeId": 2442700,
  "start": "2026-01-01T04:00:00.000+03:00",
  "attendee": {
    "name": "User Name",
    "email": "telegram-user-{id}@telecalbot.local",
    "timeZone": "Europe/Moscow",
    "language": "en"
  },
  "metadata": {
    "telegram_user_id": "123456",
    "booked_via": "telegram_bot"
  }
}
```

**Key Points**:
- `start` must be ISO 8601 timestamp (can include timezone offset)
- `attendee` object required with name, email, timeZone, language
- `metadata` can store additional context (Telegram user ID, etc.)
- Use API version `2026-02-25` for the bookings endpoint

---

## Implementation Impacts

### Configuration Updates Required

**`.env` additions**:
```bash
CALCOM_EVENT_TYPE_ID=2442700
```

### Architecture Changes

1. **Email Collection Flow**: Make email optional
   - Add "Skip" button in email step
   - Use placeholder format for skipped emails
   - Store user preference in database

2. **API Client**:
   - Handle different API versions per endpoint
   - Parse slot times from object format `slot.time`
   - Implement rate limit tracking
   - Cache availability responses

3. **Conversation Handler**:
   - Optional email step with skip option
   - No need to explain why email is required

### Success Criteria Met

- [x] Event Type ID obtained and documented
- [x] Booking creation tested end-to-end
- [x] Email handling decision made with evidence (OPTIONAL ✅)
- [x] Meeting method field identified (`meetingUrl`)
- [x] Rate limits documented (120 req/min)

---

## Historical Test Booking Verification

**Booking Created**: `14124132`
**Time**: 2026-01-01T04:00:00.000+03:00
**Email**: telegram-user-test@telecalbot.local

This records the original research run. The current validator defaults to read-only;
its opt-in booking smoke test captures the booking UID and cancels the booking
automatically, failing with a recovery reference if cleanup does not succeed.

---

## Next Steps

1. ✅ Update `.env` with `CALCOM_EVENT_TYPE_ID=2442700`
2. ✅ Update `.env.sample` to reflect correct API version
3. ✅ Close Issue #4 (Phase 0 complete)
4. 🔜 Proceed to Phase 1 (Project Foundation)
5. 🔜 Create Cal.com client with API version handling
6. 🔜 Implement optional email collection in conversation flow

---

## References

- [Cal.com API v2 Documentation](https://cal.com/docs/api-reference/v2/introduction)
- [Get all event types](https://cal.com/docs/api-reference/v2/event-types/get-all-event-types)
- [Create a booking](https://cal.com/docs/api-reference/v2/bookings/create-a-booking)
- [Cal.com API version discussion](https://github.com/calcom/cal.com/discussions/17646)

---

**Status**: ✅ Research Complete
**Blockers Resolved**: All
**Ready for Implementation**: Yes
