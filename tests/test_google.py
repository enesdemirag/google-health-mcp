import json
from datetime import date

import httpx
import pytest
from fastmcp.server.auth import AccessToken

from google_health_mcp.config import HEALTH_SCOPES
from google_health_mcp.google import (
    SPEC_BY_ID,
    GoogleHealthClient,
    normalize_metric,
    normalize_sleep,
    normalize_workout,
)
from google_health_mcp.models import QueryRange


@pytest.fixture
def token():
    return AccessToken(
        token="test-user-private-token",
        client_id="user-a",
        subject="user-a",
        scopes=["openid", *HEALTH_SCOPES],
    )


def query(start="2026-10-01", end="2026-10-29", timezone="UTC"):
    return QueryRange(start_date=start, end_date=end, timezone=timezone)


def test_zero_missing_values_units_and_calendar_context():
    samples, _ = normalize_metric(
        [
            {"civilStartTime": {"date": {"year": 2026, "month": 10, "day": 12}}, "steps": {"countSum": "0"}},
            {"civilStartTime": {"date": {"year": 2026, "month": 10, "day": 13}}, "steps": {}},
        ],
        SPEC_BY_ID["steps"],
        query(),
    )
    assert [(sample.date, sample.value) for sample in samples] == [(date(2026, 10, 12), 0)]
    samples, sources = normalize_metric(
        [
            {
                "weight": {"sampleTime": {"physicalTime": "2026-10-12T23:30:00Z"}, "weightGrams": 74500},
                "dataSource": {"name": "scale"},
            },
            {"weight": {"sampleTime": {"physicalTime": "2026-10-12T23:30:00Z"}, "weightGrams": "NaN"}},
        ],
        SPEC_BY_ID["weight"],
        query(timezone="Europe/Istanbul"),
    )
    assert samples[0].date == date(2026, 10, 13)
    assert samples[0].value == 74.5
    assert sources == [{"name": "scale"}]


async def test_daily_rollups_use_14_day_chunks_and_follow_all_pages(token):
    calls = []

    def response(request):
        body = json.loads(request.content)
        calls.append(body)
        assert request.headers["Authorization"] == "Bearer test-user-private-token"
        point = {"civilStartTime": body["range"]["start"], "steps": {"countSum": "50"}}
        return httpx.Response(
            200,
            json={
                "rollupDataPoints": [point],
                **({"nextPageToken": "page-2"} if "pageToken" not in body else {}),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        result = await GoogleHealthClient(client).history(token, "steps", query())
    assert result.status == "available" and len(calls) == 4
    assert all(
        (date(**body["range"]["end"]["date"]) - date(**body["range"]["start"]["date"])).days == 14
        for body in calls
    )
    assert calls[0]["range"] == calls[1]["range"]
    assert calls[1]["pageToken"] == "page-2"
    assert result.statistics.total == 100  # Duplicate returned daily buckets were not summed twice.


async def test_failed_second_page_never_becomes_a_partial_success(token):
    def response(request):
        body = json.loads(request.content)
        if "pageToken" in body:
            return httpx.Response(400, json={"error": "bad page"})
        return httpx.Response(
            200,
            json={
                "rollupDataPoints": [
                    {"civilStartTime": body["range"]["start"], "steps": {"countSum": "8120"}}
                ],
                "nextPageToken": "next",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        result = await GoogleHealthClient(client).history(token, "steps", query())
    assert result.status == "provider_error" and result.samples == []
    assert result.statistics.total is None


async def test_repeated_pagination_token_is_rejected(token):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"rollupDataPoints": [], "nextPageToken": "repeated"})
        )
    ) as client:
        result = await GoogleHealthClient(client).history(token, "steps", query())
    assert result.status == "provider_error" and result.samples == []


async def test_daily_summary_types_use_lists_and_scoped_filters(token):
    calls = []

    def response(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "dataPoints": [
                    {
                        "dailyHeartRateVariability": {
                            "date": {"year": 2026, "month": 10, "day": 12},
                            "averageHeartRateVariabilityMilliseconds": 42,
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        result = await GoogleHealthClient(client).history(token, "hrv", query())
    assert result.samples[0].value == 42
    assert result.statistics.total is None
    assert calls[0].method == "GET"
    assert (
        calls[0].url.params["filter"]
        == 'daily_heart_rate_variability.date >= "2026-10-01" AND daily_heart_rate_variability.date < "2026-10-29"'
    )


def test_documented_sleep_stages_workout_units_and_unknown_duration():
    interval = {"startTime": "2026-10-12T22:00:00Z", "endTime": "2026-10-13T06:00:00Z"}
    sleep = normalize_sleep(
        {
            "name": "sleep-1",
            "sleep": {
                "interval": interval,
                "summary": {"minutesAsleep": "445"},
                "stages": [
                    {"type": "DEEP", "startTime": "2026-10-12T22:00:00Z", "endTime": "2026-10-12T23:00:00Z"}
                ],
            },
        }
    )
    assert sleep.total_sleep_minutes == 445
    assert sleep.stages[0].stage == "deep"
    assert normalize_sleep({"sleep": {"interval": interval}}).total_sleep_minutes is None
    workout = normalize_workout(
        {
            "exercise": {
                "interval": interval,
                "exerciseType": "RUNNING",
                "activeDuration": "1800s",
                "metricsSummary": {
                    "distanceMillimeters": 5000000,
                    "averageHeartRateBeatsPerMinute": "140",
                    "caloriesKcal": 340,
                },
            }
        }
    )
    assert workout.duration_minutes == 30
    assert workout.distance_km == 5 and workout.average_heart_rate_bpm == 140


def test_invalid_sleep_stages_and_negative_workout_duration_are_rejected():
    interval = {"startTime": "2026-10-12T22:00:00Z", "endTime": "2026-10-13T06:00:00Z"}
    with pytest.raises(ValueError):
        normalize_sleep(
            {
                "sleep": {
                    "interval": interval,
                    "stages": [
                        {
                            "type": "DEEP",
                            "startTime": "2026-10-13T07:00:00Z",
                            "endTime": "2026-10-13T08:00:00Z",
                        }
                    ],
                }
            }
        )
    with pytest.raises(ValueError):
        normalize_workout({"exercise": {"interval": interval, "activeDuration": "-1s"}})


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (400, {"error": {"details": [{"reason": "ACCOUNT_NOT_LINKED"}]}}, "account_not_linked"),
        (401, {"error": "revoked"}, "unavailable"),
        (403, {"error": "forbidden"}, "unavailable"),
        (200, {"rollupDataPoints": []}, "no_data"),
    ],
)
async def test_provider_states_do_not_fabricate_data_or_expose_credentials(token, status, body, expected):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body))
    ) as client:
        result = await GoogleHealthClient(client).history(token, "steps", query())
    assert result.status == expected and result.samples == []
    assert "test-user-private-token" not in result.model_dump_json()


async def test_retries_are_bounded_and_errors_are_sanitized(token):
    calls = []

    def response(request):
        calls.append(request)
        return httpx.Response(503, json={"error": "internal details and test-user-private-token"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        result = await GoogleHealthClient(client).history(token, "steps", query())
    assert len(calls) == 3
    assert result.status == "provider_error" and result.samples == []
    assert "test-user-private-token" not in result.model_dump_json()
