import asyncio
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastmcp.server.auth import AccessToken

from google_health_mcp.google import GoogleHealthClient
from google_health_mcp.models import (
    BaselineComparison,
    DailyHealthContext,
    DailyMetricContext,
    MetricHistory,
    QueryRange,
)


def compare_baseline(day: MetricHistory, baseline: MetricHistory) -> BaselineComparison:
    latest = day.statistics.latest_value
    average = baseline.statistics.average
    result = BaselineComparison(
        status="missing_day_value" if latest is None else "insufficient_baseline",
        baseline_recorded_days=baseline.statistics.recorded_days,
        day_value=latest,
        baseline_average=average,
    )
    if (
        day.status == "available"
        and baseline.status == "available"
        and latest is not None
        and average is not None
        and baseline.statistics.recorded_days >= result.minimum_baseline_days
    ):
        result.status = "compared"
        result.absolute_change = latest - average
        # Celsius has an arbitrary zero, so a relative percentage is not meaningful.
        if average != 0 and day.metric.unit != "°C":
            result.relative_change_percent = (latest - average) / average * 100
    return result


async def daily_context(
    provider: GoogleHealthClient,
    token: AccessToken,
    day: date,
    timezone: str,
    metrics: list[str],
    baseline_days: int,
) -> DailyHealthContext:
    target = QueryRange(start_date=day, end_date=day + timedelta(days=1), timezone=timezone)
    baseline = QueryRange(start_date=day - timedelta(days=baseline_days), end_date=day, timezone=timezone)
    limit = asyncio.Semaphore(4)

    async def fetch(metric: str) -> DailyMetricContext:
        async with limit:
            current = await provider.history(token, metric, target)
            previous = await provider.history(token, metric, baseline)
            return DailyMetricContext(
                day=current, baseline=previous, comparison=compare_baseline(current, previous)
            )

    values = await asyncio.gather(*(fetch(metric) for metric in metrics))
    return DailyHealthContext(
        date=day,
        timezone=timezone,
        fetched_at=datetime.now(UTC),
        calendar_day_finished=day < datetime.now(ZoneInfo(timezone)).date(),
        metrics=values,
        notes=[
            "Comparisons use only this person's recorded preceding calendar days and need at least three baseline days.",
            "Personal baseline differences are not clinical reference-range classifications or evidence of causation.",
            "The calendar-day flag does not prove device synchronization or complete provider coverage. Late records can arrive after a day ends.",
            "No goals or clinical ranges are stored or inferred by this server. The assistant evaluates user-supplied goals and separately sourced reference information.",
        ],
    )
