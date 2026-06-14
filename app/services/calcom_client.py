"""Cal.com API client with caching."""

import asyncio
import logging
import time
from datetime import date
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CalComAPIError(Exception):
    """Exception for Cal.com API errors with user-friendly messages."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Cal.com API error {status_code}: {message}")

    def user_message(self) -> str:
        """Return user-friendly error message."""
        return "Something went wrong. Please try again."


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
    metadata: dict[str, Any] = Field(default_factory=dict)


class BookingResponse(BaseModel):
    """Response from Cal.com booking creation."""

    id: int
    uid: str
    title: str
    start: str
    end: str
    status: str


class CalComClient:
    """Async Cal.com API client with caching."""

    BASE_URL = "https://api.cal.com/v2"
    DEFAULT_API_VERSION = "2024-06-14"
    SLOTS_API_VERSION = "2024-09-04"
    BOOKINGS_API_VERSION = "2026-02-25"
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY_SECONDS = 0.5
    RETRYABLE_STATUS_CODES = {429, 502, 503, 504}

    def __init__(
        self,
        api_key: str,
        api_version: str,
        cache_ttl: int = 300,
    ):
        """Initialize the Cal.com client.

        Args:
            api_key: Cal.com API key.
            api_version: Fallback Cal.com API version for endpoints without
                an explicit endpoint-specific version.
            cache_ttl: Cache TTL in seconds (default 300 = 5 minutes).
        """
        self.api_version = api_version or self.DEFAULT_API_VERSION
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "cal-api-version": self.api_version,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self.cache_ttl = cache_ttl
        self._availability_cache: dict[tuple, tuple[float, AvailabilityResponse]] = {}

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
        cache_key = (event_type_id, start_date, end_date, timezone)

        # Check cache
        if cache_key in self._availability_cache:
            cached_at, data = self._availability_cache[cache_key]
            if time.time() - cached_at < self.cache_ttl:
                logger.debug("Cache hit for availability: %s", cache_key)
                return data

        logger.debug("Cache miss for availability: %s", cache_key)

        # Fetch from API
        response = await self._request(
            "GET",
            "/slots",
            api_version=self.SLOTS_API_VERSION,
            params={
                "eventTypeId": event_type_id,
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "timeZone": timezone,
            },
        )

        data = self._parse_availability(response["data"])
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
        response = await self._request(
            "POST",
            "/bookings",
            api_version=self.BOOKINGS_API_VERSION,
            json=request.model_dump(),
        )

        # Clear availability cache on successful booking
        self._availability_cache.clear()
        logger.debug("Cleared availability cache after successful booking")

        return BookingResponse.model_validate(response["data"])

    async def cancel_booking(self, booking_uid: str) -> None:
        """Cancel an existing booking by Cal.com booking UID."""
        await self._request(
            "POST",
            f"/bookings/{booking_uid}/cancel",
            api_version=self.BOOKINGS_API_VERSION,
            json={},
        )
        # Keep cache consistent with changed availability
        self._availability_cache.clear()
        logger.debug("Cleared availability cache after booking cancellation")

    async def _request(
        self,
        method: str,
        path: str,
        api_version: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make HTTP request to Cal.com API.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API endpoint path.
            api_version: Endpoint-specific Cal.com API version.
            **kwargs: Additional arguments for httpx request.

        Returns:
            Parsed JSON response.

        Raises:
            CalComAPIError: If request fails.
        """
        delay_seconds = self.INITIAL_RETRY_DELAY_SECONDS
        last_error: CalComAPIError | None = None

        for attempt in range(1, self.MAX_RETRIES + 2):
            request_kwargs = self._with_api_version_header(kwargs, api_version)
            try:
                response = await self._client.request(method, path, **request_kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                message = e.response.text
                logger.error("Cal.com API error %d: %s", status_code, message)

                last_error = CalComAPIError(status_code=status_code, message=message)
                should_retry = status_code in self.RETRYABLE_STATUS_CODES
                sleep_seconds = self._retry_delay_seconds(e.response, delay_seconds)
            except httpx.RequestError as e:
                message = str(e)
                logger.error("Cal.com API network error: %s", message)

                last_error = CalComAPIError(status_code=0, message=message)
                should_retry = True
                sleep_seconds = delay_seconds

            if not should_retry or attempt > self.MAX_RETRIES:
                raise last_error

            logger.warning(
                "Retrying Cal.com request %s %s (attempt %d/%d) after %.1fs",
                method,
                path,
                attempt + 1,
                self.MAX_RETRIES + 1,
                sleep_seconds,
            )
            await asyncio.sleep(sleep_seconds)
            delay_seconds *= 2

        raise last_error

    def _with_api_version_header(
        self,
        kwargs: dict[str, Any],
        api_version: str | None,
    ) -> dict[str, Any]:
        """Return request kwargs with the correct Cal.com API version header."""
        request_kwargs = dict(kwargs)
        headers = dict(request_kwargs.pop("headers", {}))
        headers.setdefault("cal-api-version", api_version or self.api_version)
        request_kwargs["headers"] = headers
        return request_kwargs

    @staticmethod
    def _retry_delay_seconds(response: httpx.Response, fallback_seconds: float) -> float:
        """Use Retry-After for rate limits when Cal.com provides it."""
        if response.status_code != 429:
            return fallback_seconds

        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return fallback_seconds

        try:
            seconds = float(retry_after)
        except ValueError:
            return fallback_seconds

        return max(seconds, 0.0)

    @staticmethod
    def _parse_availability(data: dict[str, Any]) -> AvailabilityResponse:
        """Normalize supported Cal.com slot response shapes."""
        raw_slots = data.get("slots", data)
        normalized_slots: dict[str, list[dict[str, str]]] = {}

        for day, slots in raw_slots.items():
            normalized_slots[day] = []
            for slot in slots:
                if isinstance(slot, str):
                    normalized_slots[day].append({"time": slot})
                    continue

                slot_time = slot.get("time") or slot.get("start")
                if slot_time is not None:
                    normalized_slots[day].append({"time": slot_time})

        return AvailabilityResponse.model_validate({"slots": normalized_slots})
