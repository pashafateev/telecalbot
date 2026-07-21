"""Contract tests for the standalone Cal.com research validator."""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from research import calcom_api_validator as validator


def _response(
    method: str,
    path: str,
    payload: dict,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request(method, f"https://api.cal.com/v2{path}")
    return httpx.Response(
        status_code,
        request=request,
        json=payload,
        headers=headers,
    )


@pytest.mark.asyncio
async def test_event_type_research_uses_endpoint_version():
    client = SimpleNamespace(
        get=AsyncMock(
            return_value=_response(
                "GET",
                "/event-types",
                {"data": [{"id": 123, "slug": validator.EVENT_SLUG}]},
            )
        )
    )
    results = validator.ResearchResults()

    await validator.fetch_event_types(client, results)

    assert client.get.call_args.args == ("/event-types",)
    assert client.get.call_args.kwargs["headers"]["cal-api-version"] == "2024-06-14"
    assert results.event_type_id == 123


@pytest.mark.asyncio
async def test_availability_research_uses_current_slots_contract():
    slots = {
        "2026-01-01": [{"start": "2026-01-01T10:00:00.000Z"}],
    }
    client = SimpleNamespace(
        get=AsyncMock(
            return_value=_response(
                "GET",
                "/slots",
                {"data": slots},
                headers={"x-ratelimit-limit-default": "120"},
            )
        )
    )
    results = validator.ResearchResults()
    results.event_type_id = 123

    await validator.test_availability(client, results)

    assert client.get.call_args.args == ("/slots",)
    kwargs = client.get.call_args.kwargs
    assert kwargs["headers"]["cal-api-version"] == "2024-09-04"
    params = kwargs["params"]
    assert set(params) == {"eventTypeId", "start", "end", "timeZone"}
    assert params["eventTypeId"] == 123
    assert params["timeZone"] == "Europe/Moscow"
    assert date.fromisoformat(params["end"]) - date.fromisoformat(params["start"]) == timedelta(
        days=7
    )
    assert results.availability_sample == slots
    assert results.rate_limit_headers == {"x-ratelimit-limit-default": "120"}


@pytest.mark.asyncio
async def test_booking_research_requires_explicit_live_write_opt_in(monkeypatch):
    monkeypatch.setattr(validator, "ALLOW_LIVE_WRITES", False)
    client = SimpleNamespace(post=AsyncMock())
    results = validator.ResearchResults()
    results.event_type_id = 123
    results.availability_sample = {
        "2026-01-01": [{"start": "2026-01-01T10:00:00.000Z"}],
    }

    await validator.test_placeholder_email(client, results)

    client.post.assert_not_awaited()
    assert results.test_booking_id is None
    assert results.booking_cleanup_succeeded is None


@pytest.mark.asyncio
async def test_booking_research_creates_and_cancels_by_uid(monkeypatch):
    monkeypatch.setattr(validator, "ALLOW_LIVE_WRITES", True)
    client = SimpleNamespace(
        post=AsyncMock(
            side_effect=[
                _response(
                    "POST",
                    "/bookings",
                    {"data": {"id": 456, "uid": "booking_uid_456"}},
                    status_code=201,
                ),
                _response(
                    "POST",
                    "/bookings/booking_uid_456/cancel",
                    {"data": {}},
                ),
            ]
        )
    )
    results = validator.ResearchResults()
    results.event_type_id = 123
    results.availability_sample = {
        "2026-01-01": [{"start": "2026-01-01T10:00:00.000Z"}],
    }

    await validator.test_placeholder_email(client, results)

    create_call, cancel_call = client.post.await_args_list
    assert create_call.args == ("/bookings",)
    assert create_call.kwargs["headers"]["cal-api-version"] == "2026-02-25"
    assert create_call.kwargs["json"]["start"] == "2026-01-01T10:00:00.000Z"
    assert cancel_call.args == ("/bookings/booking_uid_456/cancel",)
    assert cancel_call.kwargs["headers"]["cal-api-version"] == "2026-02-25"
    assert cancel_call.kwargs["json"] == {}
    assert results.test_booking_id == 456
    assert results.test_booking_uid == "booking_uid_456"
    assert results.booking_cleanup_succeeded is True


@pytest.mark.asyncio
async def test_booking_research_reports_uid_when_cleanup_fails(monkeypatch):
    monkeypatch.setattr(validator, "ALLOW_LIVE_WRITES", True)
    client = SimpleNamespace(
        post=AsyncMock(
            side_effect=[
                _response(
                    "POST",
                    "/bookings",
                    {"data": {"id": 456, "uid": "booking_uid_456"}},
                    status_code=201,
                ),
                _response(
                    "POST",
                    "/bookings/booking_uid_456/cancel",
                    {"error": "cleanup failed"},
                    status_code=500,
                ),
            ]
        )
    )
    results = validator.ResearchResults()
    results.event_type_id = 123
    results.availability_sample = {
        "2026-01-01": [{"start": "2026-01-01T10:00:00.000Z"}],
    }

    await validator.test_placeholder_email(client, results)

    assert results.booking_cleanup_succeeded is False
    assert results.test_booking_uid == "booking_uid_456"
    assert any(
        "booking_uid_456" in error and "cleanup failed" in error.lower()
        for error in results.errors
    )
