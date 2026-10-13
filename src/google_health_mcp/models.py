from datetime import date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, model_validator

DataStatus = Literal[
    "available", "no_data", "missing_permission", "unavailable", "provider_error", "account_not_linked"
]


class QueryRange(BaseModel):
    start_date: date
    end_date: date
    timezone: str = "UTC"

    @model_validator(mode="after")
    def validate_range(self):
        if not 1 <= (self.end_date - self.start_date).days <= 90:
            raise ValueError("Use a range of 1 to 90 days. start_date is inclusive; end_date is exclusive.")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("timezone must be an IANA time zone, such as Europe/Istanbul or UTC.") from None
        return self


class MetricInfo(BaseModel):
    id: str
    label: str
    unit: str
    aggregation: str
    data_type: str
    required_scope: str
    permission_granted: bool


class MetricCatalog(BaseModel):
    provider: Literal["google_health"] = "google_health"
    metrics: list[MetricInfo]
    notes: list[str]


class ConnectionStatus(BaseModel):
    provider: Literal["google_health"] = "google_health"
    status: Literal["connected", "missing_permission", "account_not_linked", "unavailable"]
    health_account_linked: bool | None = None
    granted_health_scopes: list[str]
    checked_at: datetime
    message: str


class DailySample(BaseModel):
    date: date
    value: float


class MetricStatistics(BaseModel):
    recorded_days: int
    requested_days: int
    latest_value: float | None = None
    latest_date: date | None = None
    average: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    total: float | None = None


class MetricHistory(BaseModel):
    provider: Literal["google_health"] = "google_health"
    metric: MetricInfo
    query: QueryRange
    status: DataStatus
    fetched_at: datetime
    samples: list[DailySample] = Field(default_factory=list)
    missing_dates: list[date] = Field(default_factory=list)
    statistics: MetricStatistics
    sources: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SleepStage(BaseModel):
    stage: str
    start: datetime
    end: datetime


class SleepSession(BaseModel):
    id: str | None = None
    start: datetime
    end: datetime
    total_sleep_minutes: float | None = None
    stages: list[SleepStage] = Field(default_factory=list)
    source: dict[str, Any] | None = None


class Workout(BaseModel):
    id: str | None = None
    title: str
    activity_type: str
    start: datetime
    end: datetime
    duration_minutes: float
    calories_kcal: float | None = None
    distance_km: float | None = None
    average_heart_rate_bpm: float | None = None
    source: dict[str, Any] | None = None


class SleepResult(BaseModel):
    provider: Literal["google_health"] = "google_health"
    query: QueryRange
    status: DataStatus
    fetched_at: datetime
    sessions: list[SleepSession] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkoutResult(BaseModel):
    provider: Literal["google_health"] = "google_health"
    query: QueryRange
    status: DataStatus
    fetched_at: datetime
    workouts: list[Workout] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HealthOverview(BaseModel):
    provider: Literal["google_health"] = "google_health"
    query: QueryRange
    fetched_at: datetime
    metrics: list[MetricHistory]
    notes: list[str]


class BaselineComparison(BaseModel):
    basis: Literal["personal_recorded_baseline"] = "personal_recorded_baseline"
    status: Literal["compared", "missing_day_value", "insufficient_baseline"]
    baseline_recorded_days: int
    minimum_baseline_days: int = 3
    day_value: float | None = None
    baseline_average: float | None = None
    absolute_change: float | None = None
    relative_change_percent: float | None = None
    clinical_reference_status: Literal["not_assessed"] = "not_assessed"


class DailyMetricContext(BaseModel):
    day: MetricHistory
    baseline: MetricHistory
    comparison: BaselineComparison


class DailyHealthContext(BaseModel):
    provider: Literal["google_health"] = "google_health"
    date: date
    timezone: str
    fetched_at: datetime
    calendar_day_finished: bool
    provider_coverage_complete: bool | None = None
    metrics: list[DailyMetricContext]
    notes: list[str]
