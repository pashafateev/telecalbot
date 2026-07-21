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
async def test_booking_research_uses_current_slot_shape_and_version():
    client = SimpleNamespace(
        post=AsyncMock(
            return_value=_response(
                "POST",
                "/bookings",
                {"data": {"id": 456}},
                status_code=201,
            )
        )
    )
    results = validator.ResearchResults()
    results.event_type_id = 123
    results.availability_sample = {
        "2026-01-01": [{"start": "2026-01-01T10:00:00.000Z"}],
    }

    await validator.test_placeholder_email(client, results)

    assert client.post.call_args.args == ("/bookings",)
    kwargs = client.post.call_args.kwargs
    assert kwargs["headers"]["cal-api-version"] == "2026-02-25"
    assert kwargs["json"]["start"] == "2026-01-01T10:00:00.000Z"
    assert results.test_booking_id == 456
