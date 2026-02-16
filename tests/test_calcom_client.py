"""Tests for Cal.com API client."""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.calcom_client import (
    Attendee,
    AvailabilityResponse,
    BookingRequest,
    BookingResponse,
    CalComAPIError,
    CalComClient,
    TimeSlot,
)


class TestCalComAPIError:
    """Test CalComAPIError user-friendly messages."""

    def test_user_message_returns_generic_message(self):
        """All errors return the same generic message."""
        for status in (400, 422, 429, 500, 0):
            error = CalComAPIError(status_code=status, message="Some error")
            assert error.user_message() == "Something went wrong. Please try again."


class TestTimeSlotModel:
    """Test TimeSlot Pydantic model."""

    def test_timeslot_from_api_response(self):
        """Parse time slot from Cal.com API format."""
        slot = TimeSlot(time="2026-01-01T10:00:00.000+03:00")
        assert slot.time == "2026-01-01T10:00:00.000+03:00"


class TestAvailabilityResponse:
    """Test AvailabilityResponse Pydantic model."""

    def test_parse_slots_response(self):
        """Parse slots from Cal.com API response."""
        data = {
            "slots": {
                "2026-01-01": [{"time": "2026-01-01T10:00:00.000+03:00"}],
                "2026-01-02": [
                    {"time": "2026-01-02T09:00:00.000+03:00"},
                    {"time": "2026-01-02T14:00:00.000+03:00"},
                ],
            }
        }
        response = AvailabilityResponse.model_validate(data)
        assert len(response.slots) == 2
        assert len(response.slots["2026-01-01"]) == 1
        assert len(response.slots["2026-01-02"]) == 2
        assert response.slots["2026-01-01"][0].time == "2026-01-01T10:00:00.000+03:00"

    def test_empty_slots(self):
        """Handle empty availability response."""
        data = {"slots": {}}
        response = AvailabilityResponse.model_validate(data)
        assert response.slots == {}


class TestBookingModels:
    """Test Attendee, BookingRequest, and BookingResponse models."""

    def test_attendee_model(self):
        """Create attendee with required fields."""
        attendee = Attendee(
            name="Test User",
            email="test@example.com",
            timeZone="Europe/Moscow",
        )
        assert attendee.name == "Test User"
        assert attendee.language == "en"  # default

    def test_booking_request_model(self):
        """Create booking request with all fields."""
        request = BookingRequest(
            eventTypeId=123,
            start="2026-01-01T10:00:00Z",
            attendee=Attendee(
                name="Test User",
                email="test@example.com",
                timeZone="Europe/Moscow",
            ),
            metadata={"telegram_user_id": "12345"},
        )
        assert request.eventTypeId == 123
        assert request.metadata["telegram_user_id"] == "12345"

    def test_booking_response_model(self):
        """Parse booking response from Cal.com API."""
        data = {
            "id": 123,
            "uid": "abc-123-def",
            "title": "Test Booking",
            "start": "2026-01-01T10:00:00.000Z",
            "end": "2026-01-01T11:00:00.000Z",
            "status": "accepted",
        }
        response = BookingResponse.model_validate(data)
        assert response.id == 123
        assert response.uid == "abc-123-def"
        assert response.status == "accepted"


class TestCalComClient:
    """Test CalComClient methods."""

    @pytest.fixture
    def client(self):
        """Create a CalComClient instance for testing."""
        return CalComClient(
            api_key="test_key",
            api_version="2024-06-14",
            cache_ttl=300,
        )

    @pytest.mark.asyncio
    async def test_get_availability_returns_parsed_response(self, client):
        """get_availability returns parsed AvailabilityResponse."""
        mock_response = {
            "status": "success",
            "data": {
                "slots": {
                    "2026-01-01": [{"time": "2026-01-01T10:00:00.000+03:00"}],
                }
            },
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await client.get_availability(
                event_type_id=123,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                timezone="Europe/Moscow",
            )

            assert isinstance(result, AvailabilityResponse)
            assert len(result.slots) == 1
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_availability_uses_cache(self, client):
        """Second call with same params uses cached response."""
        mock_response = {
            "status": "success",
            "data": {
                "slots": {
                    "2026-01-01": [{"time": "2026-01-01T10:00:00.000+03:00"}],
                }
            },
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            # First call
            result1 = await client.get_availability(
                event_type_id=123,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                timezone="Europe/Moscow",
            )

            # Second call with same params
            result2 = await client.get_availability(
                event_type_id=123,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                timezone="Europe/Moscow",
            )

            # Only one API call should be made
            assert mock_request.call_count == 1
            assert result1.slots == result2.slots

    @pytest.mark.asyncio
    async def test_get_availability_different_params_no_cache(self, client):
        """Different params bypass cache."""
        mock_response = {
            "status": "success",
            "data": {"slots": {}},
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            await client.get_availability(
                event_type_id=123,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                timezone="Europe/Moscow",
            )

            await client.get_availability(
                event_type_id=123,
                start_date=date(2026, 1, 8),  # Different date
                end_date=date(2026, 1, 14),
                timezone="Europe/Moscow",
            )

            # Two API calls should be made
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(self, client):
        """Cache expires after TTL seconds."""
        # Set a very short TTL for testing
        client.cache_ttl = 0.1

        mock_response = {
            "status": "success",
            "data": {"slots": {}},
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            await client.get_availability(
                event_type_id=123,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                timezone="Europe/Moscow",
            )

            # Wait for cache to expire
            await asyncio.sleep(0.15)

            await client.get_availability(
                event_type_id=123,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                timezone="Europe/Moscow",
            )

            # Two API calls should be made after cache expired
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_create_booking_success(self, client):
        """create_booking returns parsed BookingResponse."""
        mock_response = {
            "status": "success",
            "data": {
                "id": 123,
                "uid": "abc-123",
                "title": "Step work",
                "start": "2026-01-01T10:00:00.000Z",
                "end": "2026-01-01T11:00:00.000Z",
                "status": "accepted",
            },
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            request = BookingRequest(
                eventTypeId=123,
                start="2026-01-01T10:00:00Z",
                attendee=Attendee(
                    name="Test User",
                    email="test@example.com",
                    timeZone="Europe/Moscow",
                ),
            )

            result = await client.create_booking(request)

            assert isinstance(result, BookingResponse)
            assert result.id == 123
            assert result.status == "accepted"

    @pytest.mark.asyncio
    async def test_create_booking_clears_cache(self, client):
        """Successful booking clears availability cache."""
        avail_response = {
            "status": "success",
            "data": {"slots": {"2026-01-01": [{"time": "2026-01-01T10:00:00.000+03:00"}]}},
        }
        booking_response = {
            "status": "success",
            "data": {
                "id": 123,
                "uid": "abc-123",
                "title": "Step work",
                "start": "2026-01-01T10:00:00.000Z",
                "end": "2026-01-01T11:00:00.000Z",
                "status": "accepted",
            },
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock
        ) as mock_request:
            # First call: get availability (populates cache)
            mock_request.return_value = avail_response
            await client.get_availability(
                event_type_id=123,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                timezone="Europe/Moscow",
            )
            assert mock_request.call_count == 1

            # Create booking (should clear cache)
            mock_request.return_value = booking_response
            await client.create_booking(
                BookingRequest(
                    eventTypeId=123,
                    start="2026-01-01T10:00:00Z",
                    attendee=Attendee(
                        name="Test",
                        email="test@example.com",
                        timeZone="Europe/Moscow",
                    ),
                )
            )
            assert mock_request.call_count == 2

            # Get availability again (should hit API, not cache)
            mock_request.return_value = avail_response
            await client.get_availability(
                event_type_id=123,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                timezone="Europe/Moscow",
            )
            assert mock_request.call_count == 3  # Cache was cleared


class TestCalComClientRetry:
    """Test retry behavior in low-level request method."""

    @pytest.fixture
    def client(self):
        return CalComClient(
            api_key="test_key",
            api_version="2024-06-14",
            cache_ttl=300,
        )

    @staticmethod
    def _http_status_error(status_code: int, text: str) -> httpx.HTTPStatusError:
        request = httpx.Request("GET", "https://api.cal.com/v2/test")
        response = httpx.Response(status_code, text=text, request=request)
        return httpx.HTTPStatusError(
            message=f"Error response {status_code}",
            request=request,
            response=response,
        )

    @pytest.mark.asyncio
    async def test_retries_retryable_status_then_succeeds(self, client):
        with (
            patch.object(
                client._client, "request", new_callable=AsyncMock
            ) as mock_request,
            patch(
                "app.services.calcom_client.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep,
        ):
            mock_request.side_effect = [
                self._http_status_error(429, "rate limited"),
                httpx.Response(
                    200,
                    request=httpx.Request("GET", "https://api.cal.com/v2/test"),
                    json={"status": "success", "data": {"ok": True}},
                ),
            ]

            result = await client._request("GET", "/test")

            assert result == {"status": "success", "data": {"ok": True}}
            assert mock_request.call_count == 2
            mock_sleep.assert_awaited_once_with(0.5)

    @pytest.mark.asyncio
    async def test_does_not_retry_non_retryable_status(self, client):
        with (
            patch.object(
                client._client, "request", new_callable=AsyncMock
            ) as mock_request,
            patch(
                "app.services.calcom_client.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep,
        ):
            mock_request.side_effect = [self._http_status_error(400, "bad request")]

            with pytest.raises(CalComAPIError) as exc_info:
                await client._request("GET", "/test")

            assert exc_info.value.status_code == 400
            assert mock_request.call_count == 1
            mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_after_retry_exhausted(self, client):
        with (
            patch.object(
                client._client, "request", new_callable=AsyncMock
            ) as mock_request,
            patch(
                "app.services.calcom_client.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep,
        ):
            mock_request.side_effect = [
                self._http_status_error(503, "unavailable") for _ in range(4)
            ]

            with pytest.raises(CalComAPIError) as exc_info:
                await client._request("GET", "/test")

            assert exc_info.value.status_code == 503
            assert mock_request.call_count == 4
            assert mock_sleep.await_count == 3


class TestCalComClientClose:
    """Test client cleanup."""

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Client can be closed properly."""
        client = CalComClient(
            api_key="test_key",
            api_version="2024-06-14",
        )

        with patch.object(client._client, "aclose", new_callable=AsyncMock) as mock:
            await client.close()
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Client works as async context manager."""
        async with CalComClient(
            api_key="test_key",
            api_version="2024-06-14",
        ) as client:
            assert client is not None

        # Verify client was closed (internal state)
        assert client._client.is_closed
