import asyncio
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from fastmcp.server.auth import AccessToken

from google_health_mcp.config import HEALTH_SCOPES, SCOPE_PREFIX
from google_health_mcp.models import (
    ConnectionStatus,
    DailySample,
    DataStatus,
    MetricCatalog,
    MetricHistory,
    MetricInfo,
    MetricStatistics,
    QueryRange,
    SleepResult,
    SleepSession,
    SleepStage,
    Workout,
    WorkoutResult,
)

BASE = "https://health.googleapis.com/v4/users/me"
CALENDAR_NOTE = (
    "Google daily buckets use the provider's recorded civil dates. The requested time zone is used "
    "when converting physical timestamps without a civil date. Missing values are unknown, not zero."
)


@dataclass(frozen=True)
class MetricSpec:
    id: str
    label: str
    unit: str
    data_type: str
    member: str
    value_path: str
    scope_group: str
    mode: str = "rollup"
    factor: float = 1
    aggregation: str = "Daily total"

    @property
    def scope(self) -> str:
        return f"{SCOPE_PREFIX}{self.scope_group}.readonly"

    def info(self, scopes: list[str]) -> MetricInfo:
        return MetricInfo(
            id=self.id,
            label=self.label,
            unit=self.unit,
            aggregation=self.aggregation,
            data_type=self.data_type,
            required_scope=self.scope,
            permission_granted=self.scope in scopes,
        )


# The independent service follows the existing adapter's verified v4 field mappings.
# It imports no backend modules and does not read the backend's database or credentials.
SPECS = [
    MetricSpec("steps", "Steps", "steps", "steps", "steps", "countSum", "activity_and_fitness"),
    MetricSpec(
        "calories",
        "Total calories burned",
        "kcal",
        "total-calories",
        "totalCalories",
        "kcalSum",
        "activity_and_fitness",
    ),
    MetricSpec(
        "active_calories",
        "Active calories burned",
        "kcal",
        "active-energy-burned",
        "activeEnergyBurned",
        "kcalSum",
        "activity_and_fitness",
    ),
    MetricSpec(
        "distance",
        "Distance",
        "km",
        "distance",
        "distance",
        "millimetersSum",
        "activity_and_fitness",
        factor=1e-6,
    ),
    MetricSpec("floors", "Floors climbed", "floors", "floors", "floors", "countSum", "activity_and_fitness"),
    MetricSpec(
        "heart_rate",
        "Average heart rate",
        "bpm",
        "heart-rate",
        "heartRate",
        "beatsPerMinuteAvg",
        "health_metrics_and_measurements",
        aggregation="Daily average",
    ),
    MetricSpec(
        "resting_heart_rate",
        "Resting heart rate",
        "bpm",
        "daily-resting-heart-rate",
        "dailyRestingHeartRate",
        "beatsPerMinute",
        "health_metrics_and_measurements",
        mode="daily",
        aggregation="Provider daily summary",
    ),
    MetricSpec(
        "hrv",
        "Heart rate variability",
        "ms",
        "daily-heart-rate-variability",
        "dailyHeartRateVariability",
        "averageHeartRateVariabilityMilliseconds",
        "health_metrics_and_measurements",
        mode="daily",
        aggregation="Daily RMSSD",
    ),
    MetricSpec(
        "spo2",
        "Blood oxygen",
        "%",
        "daily-oxygen-saturation",
        "dailyOxygenSaturation",
        "averagePercentage",
        "health_metrics_and_measurements",
        mode="daily",
        aggregation="Provider daily average",
    ),
    MetricSpec(
        "respiratory_rate",
        "Respiratory rate",
        "breaths/min",
        "daily-respiratory-rate",
        "dailyRespiratoryRate",
        "breathsPerMinute",
        "health_metrics_and_measurements",
        mode="daily",
        aggregation="Main sleep average",
    ),
    MetricSpec(
        "skin_temperature",
        "Sleep skin temperature",
        "°C",
        "daily-sleep-temperature-derivations",
        "dailySleepTemperatureDerivations",
        "nightlyTemperatureCelsius",
        "health_metrics_and_measurements",
        mode="daily",
        aggregation="Nightly average",
    ),
    MetricSpec(
        "weight",
        "Body weight",
        "kg",
        "weight",
        "weight",
        "weightGrams",
        "health_metrics_and_measurements",
        mode="sample",
        factor=0.001,
        aggregation="Daily average of recorded samples",
    ),
    MetricSpec(
        "body_fat",
        "Body fat",
        "%",
        "body-fat",
        "bodyFat",
        "percentage",
        "health_metrics_and_measurements",
        mode="sample",
        aggregation="Daily average of recorded samples",
    ),
    MetricSpec(
        "vo2_max",
        "VO2 max",
        "ml/kg/min",
        "daily-vo2-max",
        "dailyVo2Max",
        "vo2Max",
        "activity_and_fitness",
        mode="daily",
        aggregation="Provider daily summary",
    ),
    MetricSpec(
        "water",
        "Water logged",
        "ml",
        "hydration-log",
        "hydrationLog",
        "amountConsumed.millilitersSum",
        "nutrition",
    ),
    MetricSpec(
        "food_calories",
        "Food calories logged",
        "kcal",
        "nutrition-log",
        "nutritionLog",
        "energy.kcalSum",
        "nutrition",
    ),
    MetricSpec(
        "sleep_duration",
        "Sleep duration",
        "hours",
        "sleep",
        "sleep",
        "",
        "sleep",
        mode="sleep",
        aggregation="Longest recorded sleep session per day",
    ),
]
SPEC_BY_ID = {spec.id: spec for spec in SPECS}


class ProviderError(Exception):
    def __init__(self, status: DataStatus, message: str):
        super().__init__(message)
        self.status = status


def numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def get_path(value: dict, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def civil_date(value: dict) -> date:
    parts = value.get("date", value)
    return date(int(parts["year"]), int(parts["month"]), int(parts["day"]))


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Provider timestamps must include a time zone.")
    return parsed


def metric_day(point: dict, spec: MetricSpec, timezone: str) -> date:
    if spec.mode == "rollup":
        return civil_date(point["civilStartTime"])
    member = point[spec.member]
    if spec.mode == "daily":
        return civil_date(member["date"])
    moment = member["sampleTime"]
    if moment.get("civilTime"):
        return civil_date(moment["civilTime"])
    return timestamp(moment["physicalTime"]).astimezone(ZoneInfo(timezone)).date()


def source(point: dict) -> dict | None:
    value = point.get("dataSource")
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return {"name": value}
    return None


def normalize_metric(
    points: list[dict], spec: MetricSpec, query: QueryRange
) -> tuple[list[DailySample], list[dict]]:
    by_day = defaultdict(list)
    sources: dict[str, dict] = {}
    for point in points:
        value = numeric(get_path(point.get(spec.member, {}), spec.value_path))
        if value is None:
            continue
        day = metric_day(point, spec, query.timezone)
        if query.start_date <= day < query.end_date:
            by_day[day].append(value * spec.factor)
            if item := source(point):
                sources[json.dumps(item, sort_keys=True)] = item
    # Provider rollups reconcile overlapping sources; duplicate buckets must not be summed.
    samples = [DailySample(date=day, value=mean(values)) for day, values in sorted(by_day.items())]
    return samples, list(sources.values())


def normalize_sleep(point: dict) -> SleepSession:
    value = point["sleep"]
    start = timestamp(value["interval"]["startTime"])
    end = timestamp(value["interval"]["endTime"])
    if end <= start:
        raise ValueError("Invalid sleep interval.")
    stages = [
        SleepStage(
            stage=item["type"].lower(), start=timestamp(item["startTime"]), end=timestamp(item["endTime"])
        )
        for item in value.get("stages", [])
    ]
    ordered_stages = sorted(stages, key=lambda item: item.start)
    if any(stage.end <= stage.start or stage.start < start or stage.end > end for stage in stages):
        raise ValueError("Invalid sleep stage interval.")
    if any(
        previous.end > following.start
        for previous, following in zip(ordered_stages, ordered_stages[1:], strict=False)
    ):
        raise ValueError("Overlapping sleep stages cannot be interpreted safely.")
    minutes = numeric(value.get("summary", {}).get("minutesAsleep"))
    if minutes is None:
        sleeping = [stage for stage in stages if stage.stage in {"light", "deep", "rem", "asleep"}]
        if sleeping:
            minutes = sum((stage.end - stage.start).total_seconds() / 60 for stage in sleeping)
    if minutes is not None and minutes < 0:
        raise ValueError("Invalid sleep duration.")
    return SleepSession(
        id=point.get("name"),
        start=start,
        end=end,
        total_sleep_minutes=minutes,
        stages=stages,
        source=source(point),
    )


def normalize_workout(point: dict) -> Workout:
    value = point["exercise"]
    start = timestamp(value["interval"]["startTime"])
    end = timestamp(value["interval"]["endTime"])
    if end <= start:
        raise ValueError("Invalid workout interval.")
    summary = value.get("metricsSummary", {})
    duration = numeric(str(value.get("activeDuration", "")).removesuffix("s"))
    if duration is not None and duration < 0:
        raise ValueError("Invalid workout duration.")
    distance = numeric(summary.get("distanceMillimeters"))
    kind = value.get("exerciseType", "WORKOUT")
    return Workout(
        id=point.get("name"),
        title=value.get("displayName") or kind.replace("_", " ").title(),
        activity_type=kind.lower(),
        start=start,
        end=end,
        duration_minutes=(duration if duration is not None else (end - start).total_seconds()) / 60,
        calories_kcal=numeric(summary.get("caloriesKcal")),
        distance_km=distance / 1e6 if distance is not None else None,
        average_heart_rate_bpm=numeric(summary.get("averageHeartRateBeatsPerMinute")),
        source=source(point),
    )


class GoogleHealthClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def request(self, token: AccessToken, method: str, path: str, **kwargs) -> dict:
        for attempt in range(3):
            try:
                response = await self.client.request(
                    method, f"{BASE}{path}", headers={"Authorization": f"Bearer {token.token}"}, **kwargs
                )
            except httpx.RequestError:
                if attempt < 2:
                    await asyncio.sleep(0.25 * 2**attempt)
                    continue
                raise ProviderError(
                    "provider_error", "Google Health could not be reached. Retry later."
                ) from None
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                await asyncio.sleep(0.25 * 2**attempt)
                continue
            if response.status_code == 401:
                raise ProviderError(
                    "unavailable",
                    "Google authorization expired or was revoked. Reconnect this MCP connector.",
                )
            if response.status_code == 403:
                raise ProviderError(
                    "unavailable",
                    "Google did not allow this data request. Check consent and operator API access.",
                )
            if response.status_code == 400 and "ACCOUNT_NOT_LINKED" in response.text:
                raise ProviderError(
                    "account_not_linked",
                    "Sign in to the Google Health mobile app with this Google account, then reconnect.",
                )
            if not response.is_success:
                raise ProviderError(
                    "provider_error",
                    "Google Health rejected this request. Retry or use a shorter date range.",
                )
            try:
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Invalid provider response.")
                return data
            except ValueError:
                raise ProviderError("provider_error", "Google Health returned an invalid response.") from None
        raise RuntimeError("Unreachable request state.")

    async def pages(
        self,
        token: AccessToken,
        data_type: str,
        *,
        body: dict | None = None,
        expression: str | None = None,
        sessions: bool = False,
    ) -> list[dict]:
        path = f"/dataTypes/{data_type}/dataPoints" + (":dailyRollUp" if body is not None else "")
        params = {"filter": expression, "pageSize": 25 if sessions else 1440}
        points, seen = [], set()
        for _ in range(100):
            page = await self.request(
                token,
                "POST" if body is not None else "GET",
                path,
                **({"json": body} if body is not None else {"params": params}),
            )
            items = page.get("rollupDataPoints" if body is not None else "dataPoints", [])
            if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                raise ProviderError("provider_error", "Google Health returned invalid records.")
            points.extend(items)
            if len(points) > 20000:
                raise ProviderError("provider_error", "Too many records. Request a shorter date range.")
            cursor = page.get("nextPageToken")
            if not cursor:
                return points
            if not isinstance(cursor, str) or cursor in seen:
                raise ProviderError(
                    "provider_error",
                    "Google Health returned invalid pagination. No partial results were used.",
                )
            seen.add(cursor)
            if body is not None:
                body = {**body, "pageToken": cursor}
            else:
                params = {**params, "pageToken": cursor}
        raise ProviderError("provider_error", "Too many pages. Request a shorter date range.")

    async def metric_points(self, token: AccessToken, spec: MetricSpec, query: QueryRange) -> list[dict]:
        if spec.mode == "rollup":
            result = []
            cursor = query.start_date
            while cursor < query.end_date:
                stop = min(cursor + timedelta(days=14), query.end_date)

                def civil(day: date) -> dict:
                    return {"date": {"year": day.year, "month": day.month, "day": day.day}, "time": {}}

                result.extend(
                    await self.pages(
                        token,
                        spec.data_type,
                        body={
                            "range": {"start": civil(cursor), "end": civil(stop)},
                            "windowSizeDays": 1,
                            "pageSize": 90,
                        },
                    )
                )
                cursor = stop
            return result
        field = spec.data_type.replace("-", "_") + (
            ".date" if spec.mode == "daily" else ".sample_time.civil_time"
        )
        expression = f'{field} >= "{query.start_date}" AND {field} < "{query.end_date}"'
        return await self.pages(token, spec.data_type, expression=expression)

    async def connection_status(self, token: AccessToken) -> ConnectionStatus:
        scopes = sorted(set(token.scopes) & set(HEALTH_SCOPES))
        values = {"granted_health_scopes": scopes, "checked_at": datetime.now(UTC)}
        if not scopes:
            return ConnectionStatus(
                status="missing_permission",
                message="Google sign-in succeeded, but no Google Health read permission was granted. Reconnect and allow the data you want to query.",
                **values,
            )
        try:
            identity = await self.request(token, "GET", "/identity")
            if not identity.get("healthUserId"):
                raise ProviderError("provider_error", "Google Health identity could not be verified.")
            return ConnectionStatus(
                status="connected",
                health_account_linked=True,
                message="The signed-in Google account is linked to Google Health. Data availability still depends on consent and recorded measurements.",
                **values,
            )
        except ProviderError as exc:
            return ConnectionStatus(
                status="account_not_linked" if exc.status == "account_not_linked" else "unavailable",
                health_account_linked=False if exc.status == "account_not_linked" else None,
                message=str(exc),
                **values,
            )

    def catalog(self, token: AccessToken) -> MetricCatalog:
        return MetricCatalog(
            metrics=[spec.info(token.scopes) for spec in SPECS],
            notes=[
                "Permission availability does not prove that a device has recorded this measurement.",
                "Workouts and sleep stages have dedicated tools.",
            ],
        )

    async def history(self, token: AccessToken, metric_id: str, query: QueryRange) -> MetricHistory:
        spec = SPEC_BY_ID[metric_id]
        samples, sources, notes = [], [], [CALENDAR_NOTE]
        status: DataStatus = "no_data"
        if spec.scope not in token.scopes:
            status = "missing_permission"
            notes.append(
                "This metric's read permission was not granted. Reconnect to request additional consent."
            )
        else:
            try:
                if spec.mode == "sleep":
                    sleep = await self.sleep(token, query)
                    status = sleep.status
                    notes.extend(sleep.notes)
                    by_day = defaultdict(list)
                    for session in sleep.sessions:
                        day = session.end.astimezone(ZoneInfo(query.timezone)).date()
                        if (
                            query.start_date <= day < query.end_date
                            and session.total_sleep_minutes is not None
                        ):
                            by_day[day].append(session.total_sleep_minutes / 60)
                            if session.source and session.source not in sources:
                                sources.append(session.source)
                    samples = [
                        DailySample(date=day, value=max(values)) for day, values in sorted(by_day.items())
                    ]
                    notes.append(
                        "Sleep duration uses the longest recorded session ending on each day; it does not add naps or invent a sleep score."
                    )
                else:
                    points = await self.metric_points(token, spec, query)
                    samples, sources = normalize_metric(points, spec, query)
                if status in {"no_data", "available"}:
                    status = "available" if samples else "no_data"
            except ProviderError as exc:
                status = exc.status
                notes.append(str(exc))
            except (ValueError, KeyError, TypeError, OverflowError):
                status = "provider_error"
                notes.append("Provider records could not be interpreted. No partial metric values were used.")
        days = (query.end_date - query.start_date).days
        values = [sample.value for sample in samples]
        observed = {sample.date for sample in samples}
        stats = MetricStatistics(recorded_days=len(samples), requested_days=days)
        if values:
            stats.latest_value, stats.latest_date = samples[-1].value, samples[-1].date
            stats.average, stats.minimum, stats.maximum = mean(values), min(values), max(values)
            if spec.aggregation == "Daily total":
                stats.total = sum(values)
        return MetricHistory(
            metric=spec.info(token.scopes),
            query=query,
            status=status,
            fetched_at=datetime.now(UTC),
            samples=samples,
            sources=sources,
            statistics=stats,
            missing_dates=[
                query.start_date + timedelta(days=offset)
                for offset in range(days)
                if query.start_date + timedelta(days=offset) not in observed
            ],
            notes=notes,
        )

    async def session_points(self, token: AccessToken, data_type: str, query: QueryRange) -> list[dict]:
        field = f"{data_type}.interval.civil_{'end' if data_type == 'sleep' else 'start'}_time"
        return await self.pages(
            token,
            data_type,
            expression=f'{field} >= "{query.start_date}" AND {field} < "{query.end_date}"',
            sessions=True,
        )

    async def sleep(self, token: AccessToken, query: QueryRange) -> SleepResult:
        result = SleepResult(
            query=query, status="no_data", fetched_at=datetime.now(UTC), notes=[CALENDAR_NOTE]
        )
        if f"{SCOPE_PREFIX}sleep.readonly" not in token.scopes:
            result.status = "missing_permission"
            result.notes.append("Sleep read permission was not granted.")
            return result
        try:
            points = await self.session_points(token, "sleep", query)
            result.sessions = sorted([normalize_sleep(point) for point in points], key=lambda item: item.end)
            result.status = "available" if result.sessions else "no_data"
            if any(session.total_sleep_minutes is None for session in result.sessions):
                result.notes.append(
                    "Some sessions have no recorded asleep duration; time in bed is not substituted."
                )
        except ProviderError as exc:
            result.status, result.notes = exc.status, [str(exc)]
        except (ValueError, KeyError, TypeError, OverflowError):
            result.status, result.notes = (
                "provider_error",
                ["Sleep records could not be interpreted. No partial sessions were used."],
            )
        result.fetched_at = datetime.now(UTC)
        return result

    async def workouts(self, token: AccessToken, query: QueryRange) -> WorkoutResult:
        result = WorkoutResult(
            query=query, status="no_data", fetched_at=datetime.now(UTC), notes=[CALENDAR_NOTE]
        )
        if f"{SCOPE_PREFIX}activity_and_fitness.readonly" not in token.scopes:
            result.status = "missing_permission"
            result.notes.append("Activity and fitness read permission was not granted.")
            return result
        try:
            points = await self.session_points(token, "exercise", query)
            result.workouts = sorted(
                [normalize_workout(point) for point in points], key=lambda item: item.start
            )
            result.status = "available" if result.workouts else "no_data"
        except ProviderError as exc:
            result.status, result.notes = exc.status, [str(exc)]
        except (ValueError, KeyError, TypeError, OverflowError):
            result.status, result.notes = (
                "provider_error",
                ["Workout records could not be interpreted. No partial workouts were used."],
            )
        result.fetched_at = datetime.now(UTC)
        return result
