"""Cal.com API client with caching and retry logic."""

import asyncio
import logging
import time
from datetime import date
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CalComAPIError(Exception):
    """Exception for Cal.com API errors with user-friendly messages."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Cal.com API error {status_code}: {message}")

    def user_message(self) -> str:
        """Return user-friendly error message."""
        if self.status_code == 409:
            return "This time is no longer available. Please select another."
        elif self.status_code in (400, 422):
            return "There was a problem with your booking. Please try again."
        elif self.status_code == 429:
            return "Too many requests. Please wait a moment and try again."
        else:
            return "Cal.com is temporarily unavailable. Please try again later."


class TimeSlot(BaseModel):
    """A single time slot from Cal.com availability."""

    time: str  # ISO 8601 datetime with timezone, e.g., "2026-01-01T10:00:00.000+03:00"


class AvailabilityResponse(BaseModel):
    """Response from Cal.com availability endpoint."""

    slots: dict[str, list[TimeSlot]]  # date string -> list of time slots


class Attendee(BaseModel):
    """Attendee information for booking."""

    name: str
    email: str
    timeZone: str
    language: str = "en"


class BookingRequest(BaseModel):
    """Request payload for creating a booking."""

    eventTypeId: int
    start: str  # ISO 8601 UTC datetime
    attendee: Attendee
    metadata: dict[str, Any] = {}


class BookingResponse(BaseModel):
    """Response from Cal.com booking creation."""

    id: int
    uid: str
    title: str
    startTime: str
    endTime: str
    status: str


class CalComClient:
    """Async Cal.com API client with caching and retry logic."""

    BASE_URL = "https://api.cal.com/v2"

    def __init__(
        self,
        api_key: str,
        api_version: str,
        cache_ttl: int = 300,
    ):
        """Initialize the Cal.com client.

        Args:
            api_key: Cal.com API key.
            api_version: Cal.com API version (e.g., "2024-06-14").
            cache_ttl: Cache TTL in seconds (default 300 = 5 minutes).
        """
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "cal-api-version": api_version,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self.cache_ttl = cache_ttl
        self._availability_cache: dict[str, tuple[float, AvailabilityResponse]] = {}

    async def __aenter__(self) -> "CalComClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def get_availability(
        self,
        event_type_id: int,
        start_date: date,
        end_date: date,
        timezone: str,
    ) -> AvailabilityResponse:
        """Get available time slots for an event type.

        Args:
            event_type_id: Cal.com event type ID.
            start_date: Start date for availability search.
            end_date: End date for availability search.
            timezone: User's timezone (e.g., "Europe/Moscow").

        Returns:
            AvailabilityResponse with available slots grouped by date.

        Raises:
            CalComAPIError: If API request fails.
        """
        cache_key = f"{event_type_id}:{start_date}:{end_date}:{timezone}"

        # Check cache
        if cache_key in self._availability_cache:
            cached_at, data = self._availability_cache[cache_key]
            if time.time() - cached_at < self.cache_ttl:
                logger.debug("Cache hit for availability: %s", cache_key)
                return data

        logger.debug("Cache miss for availability: %s", cache_key)

        # Fetch from API
        response = await self._request_with_retry(
            "GET",
            "/slots/available",
            params={
                "eventTypeId": event_type_id,
                "startTime": f"{start_date}T00:00:00Z",
                "endTime": f"{end_date}T23:59:59Z",
                "timeZone": timezone,
            },
        )

        data = AvailabilityResponse.model_validate(response["data"])
        self._availability_cache[cache_key] = (time.time(), data)
        return data

    async def create_booking(self, request: BookingRequest) -> BookingResponse:
        """Create a new booking.

        Args:
            request: Booking request with event type, time, and attendee info.

        Returns:
            BookingResponse with booking confirmation details.

        Raises:
            CalComAPIError: If booking creation fails.
        """
        response = await self._request_with_retry(
            "POST",
            "/bookings",
            json=request.model_dump(),
        )

        # Clear availability cache on successful booking
        self._availability_cache.clear()
        logger.debug("Cleared availability cache after successful booking")

        return BookingResponse.model_validate(response["data"])

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make HTTP request with exponential backoff retry logic.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API endpoint path.
            max_retries: Maximum number of retry attempts.
            base_delay: Base delay in seconds for exponential backoff.
            **kwargs: Additional arguments for httpx request.

        Returns:
            Parsed JSON response.

        Raises:
            CalComAPIError: If request fails after all retries.
        """
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                response = await self._client.request(method, path, **kwargs)

                if response.status_code == 429:
                    # Rate limited - exponential backoff
                    wait = base_delay * (2**attempt)
                    logger.warning(
                        "Rate limited (attempt %d/%d), waiting %.1fs",
                        attempt + 1,
                        max_retries,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code

                if status_code in (400, 401, 404, 422):
                    # Client error - don't retry
                    logger.error(
                        "Cal.com API client error %d: %s",
                        status_code,
                        e.response.text,
                    )
                    raise CalComAPIError(
                        status_code=status_code,
                        message=e.response.text,
                    )

                # Server error - retry with backoff
                wait = base_delay * (2**attempt)
                logger.warning(
                    "Cal.com API server error %d (attempt %d/%d), waiting %.1fs",
                    status_code,
                    attempt + 1,
                    max_retries,
                    wait,
                )
                await asyncio.sleep(wait)

            except httpx.RequestError as e:
                last_error = e
                # Network error - retry with backoff
                wait = base_delay * (2**attempt)
                logger.warning(
                    "Cal.com API network error (attempt %d/%d): %s, waiting %.1fs",
                    attempt + 1,
                    max_retries,
                    str(e),
                    wait,
                )
                await asyncio.sleep(wait)

        # All retries exhausted
        raise CalComAPIError(
            status_code=0,
            message=f"Failed after {max_retries} retries: {last_error}",
        )
