"""Tests for Cal.com API client."""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_conflict_error_message(self):
        """409 Conflict returns slot unavailable message."""
        error = CalComAPIError(status_code=409, message="Slot taken")
        assert "no longer available" in error.user_message().lower()

    def test_bad_request_error_message(self):
        """400/422 errors return generic problem message."""
        for status in (400, 422):
            error = CalComAPIError(status_code=status, message="Invalid data")
            assert "problem" in error.user_message().lower()

    def test_rate_limit_error_message(self):
        """429 Too Many Requests returns wait message."""
        error = CalComAPIError(status_code=429, message="Rate limited")
        assert "wait" in error.user_message().lower()

    def test_server_error_message(self):
        """5xx errors return temporarily unavailable message."""
        error = CalComAPIError(status_code=500, message="Server error")
        assert "temporarily unavailable" in error.user_message().lower()

    def test_network_error_message(self):
        """Status code 0 (network error) returns unavailable message."""
        error = CalComAPIError(status_code=0, message="Connection failed")
        assert "temporarily unavailable" in error.user_message().lower()


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
            "startTime": "2026-01-01T10:00:00.000Z",
            "endTime": "2026-01-01T11:00:00.000Z",
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
            client, "_request_with_retry", new_callable=AsyncMock
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
            client, "_request_with_retry", new_callable=AsyncMock
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
            client, "_request_with_retry", new_callable=AsyncMock
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
            client, "_request_with_retry", new_callable=AsyncMock
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
                "startTime": "2026-01-01T10:00:00.000Z",
                "endTime": "2026-01-01T11:00:00.000Z",
                "status": "accepted",
            },
        }

        with patch.object(
            client, "_request_with_retry", new_callable=AsyncMock
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
                "startTime": "2026-01-01T10:00:00.000Z",
                "endTime": "2026-01-01T11:00:00.000Z",
                "status": "accepted",
            },
        }

        with patch.object(
            client, "_request_with_retry", new_callable=AsyncMock
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


class TestCalComClientRetryLogic:
    """Test retry logic for transient failures."""

    @pytest.fixture
    def client(self):
        """Create a CalComClient instance for testing."""
        return CalComClient(
            api_key="test_key",
            api_version="2024-06-14",
            cache_ttl=300,
        )

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, client):
        """Retries on 429 with exponential backoff."""
        # Mock the httpx client's request method
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "1"}

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"status": "success", "data": {}}
        mock_response_200.raise_for_status = MagicMock()

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock:
            # First call returns 429, second returns 200
            mock.side_effect = [mock_response_429, mock_response_200]

            # Use a short base delay for testing
            result = await client._request_with_retry(
                "GET",
                "/test",
                max_retries=3,
                base_delay=0.01,
            )

            assert mock.call_count == 2
            assert result == {"status": "success", "data": {}}

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self, client):
        """Does not retry on 400/401/404/422 errors."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        http_error = httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=mock_response,
        )
        mock_response.raise_for_status.side_effect = http_error

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            with pytest.raises(CalComAPIError) as exc_info:
                await client._request_with_retry(
                    "GET",
                    "/test",
                    max_retries=3,
                    base_delay=0.01,
                )

            # Only one call - no retries for client errors
            assert mock.call_count == 1
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_retry_on_network_error(self, client):
        """Retries on network errors (RequestError)."""
        request_error = httpx.RequestError("Connection failed")

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"status": "success", "data": {}}
        mock_response_200.raise_for_status = MagicMock()

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock:
            # First two calls fail, third succeeds
            mock.side_effect = [request_error, request_error, mock_response_200]

            result = await client._request_with_retry(
                "GET",
                "/test",
                max_retries=3,
                base_delay=0.01,
            )

            assert mock.call_count == 3
            assert result == {"status": "success", "data": {}}

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, client):
        """Raises CalComAPIError after max retries exceeded."""
        request_error = httpx.RequestError("Connection failed")

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock:
            mock.side_effect = request_error

            with pytest.raises(CalComAPIError) as exc_info:
                await client._request_with_retry(
                    "GET",
                    "/test",
                    max_retries=3,
                    base_delay=0.01,
                )

            assert mock.call_count == 3
            assert exc_info.value.status_code == 0
            assert "retries" in exc_info.value.message.lower()


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
