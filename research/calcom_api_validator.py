#!/usr/bin/env python3
"""
Cal.com API Research & Validation Script
Phase 0 - Critical Research

This script validates Cal.com API behavior to inform implementation decisions:
1. Event Type ID discovery
2. Availability endpoint behavior
3. Placeholder email acceptance with automatic booking cleanup
4. Rate limits
5. Meeting method field structure
"""

import asyncio
import json
import sys
from datetime import date, timedelta
from typing import Any

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.calcom_client import CalComClient


class ResearchSettings(BaseSettings):
    """Configuration for live Cal.com contract research."""

    calcom_api_key: str = ""
    calcom_event_slug: str = "step"
    calcom_research_allow_write: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Configuration
settings = ResearchSettings()
API_KEY = settings.calcom_api_key
BASE_URL = "https://api.cal.com/v2"
EVENT_SLUG = settings.calcom_event_slug
ALLOW_LIVE_WRITES = settings.calcom_research_allow_write
EVENT_TYPES_API_VERSION = "2024-06-14"
SLOTS_API_VERSION = CalComClient.SLOTS_API_VERSION
BOOKINGS_API_VERSION = CalComClient.BOOKINGS_API_VERSION


def api_headers(api_version: str) -> dict[str, str]:
    """Build headers for one versioned Cal.com endpoint."""
    return {
        "Authorization": f"Bearer {API_KEY}",
        "cal-api-version": api_version,
        "Content-Type": "application/json",
    }


class ResearchResults:
    """Container for research findings"""
    def __init__(self):
        self.event_types = []
        self.event_type_id = None
        self.availability_sample = None
        self.placeholder_email_works = None
        self.rate_limit_headers = {}
        self.meeting_method_field = None
        self.test_booking_id = None
        self.test_booking_uid = None
        self.booking_cleanup_succeeded = None
        self.errors = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_types": self.event_types,
            "event_type_id": self.event_type_id,
            "availability_sample": self.availability_sample,
            "placeholder_email_works": self.placeholder_email_works,
            "rate_limit_headers": self.rate_limit_headers,
            "meeting_method_field": self.meeting_method_field,
            "test_booking_id": self.test_booking_id,
            "test_booking_uid": self.test_booking_uid,
            "booking_cleanup_succeeded": self.booking_cleanup_succeeded,
            "errors": self.errors,
        }

    def print_summary(self):
        """Print human-readable summary"""
        print("\n" + "="*70)
        print("CAL.COM API RESEARCH RESULTS")
        print("="*70 + "\n")

        print("API Versions:")
        print(f"  Event types: {EVENT_TYPES_API_VERSION}")
        print(f"  Slots: {SLOTS_API_VERSION}")
        print(f"  Bookings: {BOOKINGS_API_VERSION}")
        print(f"Base URL: {BASE_URL}\n")

        print("1. EVENT TYPE DISCOVERY")
        print("-" * 70)
        if self.event_type_id:
            print(f"✅ Event Type ID for '{EVENT_SLUG}': {self.event_type_id}")
        else:
            print(f"❌ Failed to find event type for slug '{EVENT_SLUG}'")
        print(f"   Total event types found: {len(self.event_types)}")
        print()

        print("2. AVAILABILITY ENDPOINT")
        print("-" * 70)
        if self.availability_sample:
            print("✅ Availability endpoint working")
            print(f"   Sample response structure: {json.dumps(self.availability_sample, indent=2)}")
        else:
            print("❌ Failed to fetch availability")
        print()

        print("3. PLACEHOLDER EMAIL HANDLING")
        print("-" * 70)
        if self.placeholder_email_works is True:
            print("✅ Placeholder emails ARE accepted")
            print("   Decision: Use telegram-user-{id}@telecalbot.local format")
            print("   Impact: Email collection is OPTIONAL")
        elif self.placeholder_email_works is False:
            print("❌ Placeholder emails are REJECTED")
            print("   Decision: Email collection is REQUIRED")
            print("   Impact: Must adjust UX flow to collect email")
        else:
            print("⚠️  Could not test placeholder email (skipped or error)")
        print()

        print("4. RATE LIMITS")
        print("-" * 70)
        if self.rate_limit_headers:
            print("✅ Rate limit headers found:")
            for key, value in self.rate_limit_headers.items():
                print(f"   {key}: {value}")
        else:
            print("⚠️  No rate limit headers in response")
            print("   Decision: Use conservative 60 req/min ceiling")
        print()

        print("5. MEETING METHOD FIELD")
        print("-" * 70)
        if self.meeting_method_field:
            print(f"✅ Meeting method field: {self.meeting_method_field}")
        else:
            print("⚠️  Meeting method field not identified")
            print("   Decision: Use metadata or notes field")
        print()

        if self.test_booking_id:
            print("6. TEST BOOKING")
            print("-" * 70)
            print(f"✅ Test booking created: {self.test_booking_id}")
            print(f"   UID: {self.test_booking_uid or 'missing'}")
            if self.booking_cleanup_succeeded:
                print("✅ Test booking cancelled automatically")
            elif self.booking_cleanup_succeeded is False:
                print("❌ Automatic cleanup failed; use the UID above for manual recovery")
            print()

        if self.errors:
            print("ERRORS ENCOUNTERED")
            print("-" * 70)
            for error in self.errors:
                print(f"❌ {error}")
            print()

        print("="*70)
        print("IMPLEMENTATION DECISIONS")
        print("="*70 + "\n")

        decisions = []
        if self.event_type_id:
            decisions.append(f"✅ Use Event Type ID: {self.event_type_id}")

        if self.placeholder_email_works:
            decisions.append("✅ Email is OPTIONAL - use placeholder format")
        elif self.placeholder_email_works is False:
            decisions.append("❌ Email is REQUIRED - adjust UX flow")

        if self.rate_limit_headers:
            decisions.append("✅ Respect rate limits from headers")
        else:
            decisions.append("⚠️  Use conservative 60 req/min ceiling")

        for decision in decisions:
            print(decision)

        print("\n" + "="*70 + "\n")


async def fetch_event_types(client: httpx.AsyncClient, results: ResearchResults):
    """
    Test 1: Fetch event types to get ID for the event slug
    """
    print(f"[1/5] Fetching event types to find '{EVENT_SLUG}'...")

    try:
        response = await client.get(
            "/event-types",
            headers=api_headers(EVENT_TYPES_API_VERSION),
        )
        response.raise_for_status()

        data = response.json()
        results.event_types = data.get("data", [])

        # Find event by slug
        for event in results.event_types:
            if event.get("slug") == EVENT_SLUG:
                results.event_type_id = event.get("id")
                print(f"  ✅ Found event type ID: {results.event_type_id}")
                return

        print(f"  ❌ Event type '{EVENT_SLUG}' not found")
        print(f"  Available slugs: {[e.get('slug') for e in results.event_types]}")
        results.errors.append(f"Event type '{EVENT_SLUG}' not found in account")

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
        print(f"  ❌ {error_msg}")
        results.errors.append(f"Event types fetch failed: {error_msg}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.errors.append(f"Event types fetch error: {str(e)}")


async def test_availability(client: httpx.AsyncClient, results: ResearchResults):
    """
    Test 2: Test availability endpoint
    """
    if not results.event_type_id:
        print("[2/5] Skipping availability test (no event type ID)")
        results.errors.append("Availability test skipped - no event type ID")
        return

    print("[2/5] Testing availability endpoint...")

    try:
        today = date.today()
        end_date = today + timedelta(days=7)

        params = {
            "eventTypeId": results.event_type_id,
            "start": today.isoformat(),
            "end": end_date.isoformat(),
            "timeZone": "Europe/Moscow",
        }

        response = await client.get(
            "/slots",
            params=params,
            headers=api_headers(SLOTS_API_VERSION),
        )
        response.raise_for_status()

        # Check for rate limit headers
        for header in response.headers:
            if "rate" in header.lower() or "limit" in header.lower():
                results.rate_limit_headers[header] = response.headers[header]

        data = response.json()
        results.availability_sample = data.get("data", {})

        slot_count = sum(
            len(slots)
            for slots in results.availability_sample.values()
            if isinstance(slots, list)
        )
        print(
            f"  ✅ Availability fetched: {slot_count} slots "
            f"across {len(results.availability_sample)} days"
        )

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
        print(f"  ❌ {error_msg}")
        results.errors.append(f"Availability test failed: {error_msg}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.errors.append(f"Availability test error: {str(e)}")


async def test_placeholder_email(client: httpx.AsyncClient, results: ResearchResults):
    """
    Test 3: Test booking creation with placeholder email
    """
    if not results.event_type_id:
        print("[3/5] Skipping placeholder email test (no event type ID)")
        results.errors.append("Placeholder email test skipped - no event type ID")
        return

    if not results.availability_sample:
        print("[3/5] Skipping placeholder email test (no available slots)")
        results.errors.append("Placeholder email test skipped - no available slots")
        return

    if not ALLOW_LIVE_WRITES:
        print("[3/5] Skipping live booking test (CALCOM_RESEARCH_ALLOW_WRITE is not true)")
        return

    print("[3/5] Testing placeholder email acceptance...")

    booking_uid = None
    try:
        # Get first available slot
        slots = results.availability_sample
        first_date = sorted(slots.keys())[0]
        first_slot = slots[first_date][0]

        # Current slots use "start"; retain "time" for older captured responses.
        if isinstance(first_slot, dict):
            start_datetime = first_slot.get("start") or first_slot.get("time")
        else:
            start_datetime = first_slot

        # Test booking with placeholder email
        test_booking = {
            "eventTypeId": results.event_type_id,
            "start": start_datetime,
            "attendee": {
                "name": "Test User (API Research)",
                "email": "telegram-user-test@telecalbot.local",
                "timeZone": "Europe/Moscow",
                "language": "en"
            },
            "metadata": {
                "test": "true",
                "source": "api_research_script"
            }
        }

        # Use booking-specific API version header
        print(f"  Testing booking at: {start_datetime}")
        response = await client.post(
            "/bookings",
            json=test_booking,
            headers=api_headers(BOOKINGS_API_VERSION),
        )

        if response.status_code == 201:
            data = response.json()
            booking_data = data.get("data", {})
            results.test_booking_id = booking_data.get("id")
            results.test_booking_uid = booking_data.get("uid")
            if isinstance(results.test_booking_uid, str) and results.test_booking_uid:
                booking_uid = results.test_booking_uid
            else:
                results.booking_cleanup_succeeded = False
                error_msg = (
                    "Test booking was created without a UID; automatic cleanup is impossible "
                    f"(booking ID: {results.test_booking_id})"
                )
                print(f"  ❌ {error_msg}")
                results.errors.append(error_msg)

            results.placeholder_email_works = True
            print(
                "  ✅ Placeholder email ACCEPTED - "
                f"Booking ID: {results.test_booking_id}, UID: {results.test_booking_uid}"
            )

            # Try to identify meeting method field
            if "meetingUrl" in booking_data:
                results.meeting_method_field = "meetingUrl"
            elif "metadata" in booking_data and "meeting_method" in booking_data["metadata"]:
                results.meeting_method_field = "metadata.meeting_method"

        elif response.status_code in (400, 422):
            results.placeholder_email_works = False
            print(f"  ❌ Placeholder email REJECTED - Status: {response.status_code}")
            print(f"  Response: {response.text}")
        else:
            response.raise_for_status()

    except httpx.HTTPStatusError as e:
        if e.response.status_code in (400, 422):
            results.placeholder_email_works = False
            print(f"  ❌ Placeholder email REJECTED - Status: {e.response.status_code}")
            print(f"  Response: {e.response.text}")
        else:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            print(f"  ❌ {error_msg}")
            results.errors.append(f"Placeholder email test failed: {error_msg}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.errors.append(f"Placeholder email test error: {str(e)}")
    finally:
        if booking_uid:
            await cancel_test_booking(client, booking_uid, results)


async def cancel_test_booking(
    client: httpx.AsyncClient,
    booking_uid: str,
    results: ResearchResults,
) -> None:
    """Cancel a live research booking and retain its UID if cleanup fails."""
    print(f"  Cleaning up test booking UID: {booking_uid}...")
    try:
        response = await client.post(
            f"/bookings/{booking_uid}/cancel",
            json={},
            headers=api_headers(BOOKINGS_API_VERSION),
        )
        response.raise_for_status()
    except Exception as error:
        results.booking_cleanup_succeeded = False
        error_msg = f"Test booking cleanup failed for UID {booking_uid}: {error}"
        print(f"  ❌ {error_msg}")
        results.errors.append(error_msg)
    else:
        results.booking_cleanup_succeeded = True
        print("  ✅ Test booking cancelled")


async def test_rate_limits(client: httpx.AsyncClient, results: ResearchResults):
    """
    Test 4: Check for rate limit information
    """
    print("[4/5] Checking rate limit headers...")

    if results.rate_limit_headers:
        print("  ✅ Rate limit headers found in previous responses")
    else:
        print("  ⚠️  No rate limit headers detected")
        print("  Decision: Use conservative 60 requests/minute ceiling")


async def check_api_versions(client: httpx.AsyncClient, results: ResearchResults):
    """
    Test 5: Verify API version is current
    """
    print("[5/5] Verifying API version...")
    print(f"  Event types: {EVENT_TYPES_API_VERSION}")
    print(f"  Slots: {SLOTS_API_VERSION}")
    print(f"  Bookings: {BOOKINGS_API_VERSION}")
    print("  ✅ Endpoint-specific version headers will be sent")


async def save_results(results: ResearchResults):
    """Save results to JSON file"""
    output_file = "research/api_research_results.json"

    try:
        with open(output_file, "w") as f:
            json.dump(results.to_dict(), f, indent=2, default=str)
        print(f"\n📝 Results saved to: {output_file}")
    except Exception as e:
        print(f"\n❌ Failed to save results: {e}")


async def main():
    """Run all research tests"""

    # Validate API key
    if not API_KEY:
        print("❌ Error: CALCOM_API_KEY not set in .env file")
        print("Please add your Cal.com API key to .env")
        sys.exit(1)

    print("\n" + "="*70)
    print("CAL.COM API VALIDATION - PHASE 0 RESEARCH")
    print("="*70 + "\n")

    results = ResearchResults()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # Run tests sequentially
        await fetch_event_types(client, results)
        await test_availability(client, results)
        await test_placeholder_email(client, results)
        await test_rate_limits(client, results)
        await check_api_versions(client, results)

    # Print summary
    results.print_summary()

    # Save results
    await save_results(results)

    # Exit with error code if critical tests failed
    if not results.event_type_id:
        print("❌ CRITICAL: Event Type ID not found - cannot proceed with implementation")
        sys.exit(1)

    if results.booking_cleanup_succeeded is False:
        recovery_reference = (
            f"UID {results.test_booking_uid}"
            if results.test_booking_uid
            else f"numeric booking ID {results.test_booking_id}"
        )
        print(
            "❌ CRITICAL: Test booking cleanup failed; "
            f"manual recovery reference: {recovery_reference}"
        )
        sys.exit(1)

    print("✅ Research complete! Review findings above to inform implementation.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Research interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
