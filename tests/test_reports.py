from datetime import UTC, datetime
from statistics import mean
from zoneinfo import ZoneInfo

import pytest

from google_health_mcp.config import HEALTH_SCOPES
from google_health_mcp.google import SPEC_BY_ID
from google_health_mcp.models import MetricHistory, MetricStatistics, QueryRange
from google_health_mcp.reports import compare_baseline


def history(metric, values):
    return MetricHistory(
        metric=SPEC_BY_ID[metric].info(HEALTH_SCOPES),
        query=QueryRange(start_date="2026-10-01", end_date="2026-10-14"),
        status="available" if values else "no_data",
        fetched_at=datetime.now(UTC),
        statistics=MetricStatistics(
            recorded_days=len(values),
            requested_days=7,
            latest_value=values[-1] if values else None,
            average=mean(values) if values else None,
        ),
    )


def test_baselines_require_three_recorded_days_and_are_not_clinical_ranges():
    result = compare_baseline(history("hrv", [60]), history("hrv", [40, 50]))
    assert result.status == "insufficient_baseline"
    assert result.absolute_change is None
    assert result.clinical_reference_status == "not_assessed"
    result = compare_baseline(history("hrv", [60]), history("hrv", [40, 50, 60]))
    assert result.status == "compared"
    assert result.absolute_change == 10 and result.relative_change_percent == 20
    assert result.basis == "personal_recorded_baseline"
    assert result.clinical_reference_status == "not_assessed"


def test_zero_baseline_and_celsius_do_not_produce_invalid_percentages():
    result = compare_baseline(history("steps", [100]), history("steps", [0, 0, 0]))
    assert result.status == "compared" and result.absolute_change == 100
    assert result.relative_change_percent is None
    result = compare_baseline(history("skin_temperature", [35]), history("skin_temperature", [34, 34, 34]))
    assert result.absolute_change == 1 and result.relative_change_percent is None


def test_missing_day_measurement_has_no_fabricated_change():
    result = compare_baseline(history("steps", []), history("steps", [5000, 6000, 7000]))
    assert result.status == "missing_day_value"
    assert result.day_value is None and result.absolute_change is None


async def call_context(oauth, account, **arguments):
    response = await oauth.rpc(
        account["access_token"], "tools/call", {"name": "get_daily_health_context", "arguments": arguments}
    )
    assert response.status_code == 200
    return response.json()["result"]


async def test_daily_context_fetches_only_previous_calendar_days_for_the_same_user(oauth):
    account = await oauth.login()
    result = (
        await call_context(oauth, account, day="2026-10-12", timezone="Europe/Istanbul", metrics=["steps"])
    )["structuredContent"]
    assert result["provider_coverage_complete"] is None
    metric = result["metrics"][0]
    assert metric["day"]["query"]["start_date"] == "2026-10-12"
    assert metric["day"]["query"]["end_date"] == "2026-10-13"
    assert metric["baseline"]["query"]["start_date"] == "2026-10-05"
    assert metric["baseline"]["query"]["end_date"] == "2026-10-12"
    assert metric["comparison"]["baseline_recorded_days"] == 3
    assert metric["comparison"]["baseline_average"] == 6000
    assert metric["comparison"]["absolute_change"] == 2120
    assert metric["comparison"]["relative_change_percent"] == pytest.approx(35.3333333333)
    assert metric["comparison"]["clinical_reference_status"] == "not_assessed"
    assert "google-person" not in str(result)


async def test_daily_context_respects_partial_consent_and_bounds(oauth):
    account = await oauth.login("b")
    result = (await call_context(oauth, account, day="2026-10-12", metrics=["steps"]))["structuredContent"]
    metric = result["metrics"][0]
    assert metric["day"]["status"] == metric["baseline"]["status"] == "missing_permission"
    assert metric["comparison"]["status"] == "missing_day_value"
    for arguments in [
        {"day": "2099-01-01"},
        {"day": "2026-10-12", "baseline_days": 1},
        {"day": "2026-10-12", "baseline_days": 31},
        {"day": "2026-10-12", "metrics": ["steps", "steps"]},
    ]:
        assert (await call_context(oauth, account, **arguments))["isError"] is True
    assert not any("health.googleapis.com" in str(request.url) for request in oauth.calls)


async def test_scheduled_prompts_resolve_local_dates_and_keep_goals_out_of_storage(oauth):
    account = await oauth.login()
    response = await oauth.rpc(
        account["access_token"],
        "prompts/get",
        {"name": "morning_sleep_review", "arguments": {"timezone": "Europe/Istanbul"}},
    )
    assert response.status_code == 200
    text = response.json()["result"]["messages"][0]["content"]["text"]
    assert str(datetime.now(ZoneInfo("Europe/Istanbul")).date()) in text
    assert "get_daily_health_context" in text and "get_sleep_sessions" in text
    assert "clinical abnormality" in text
    unique_goal = "User goal: 8123 steps, with goal confidentiality marker 63cb1b"
    response = await oauth.rpc(
        account["access_token"],
        "prompts/get",
        {
            "name": "evening_goal_review",
            "arguments": {"goals": unique_goal, "report_date": "2026-10-12", "timezone": "Europe/Istanbul"},
        },
    )
    text = response.json()["result"]["messages"][0]["content"]["text"]
    assert unique_goal in text and "not assessed" in text and "reference intervals" in text
    for path in oauth.settings.data_dir.rglob("*"):
        if path.is_file():
            assert unique_goal.encode() not in path.read_bytes()
