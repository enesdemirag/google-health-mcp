# Scheduled reports

Connect your Google account once, then use an assistant with scheduled tasks to request daily reports. The assistant keeps your goals, runs the schedule and delivers the report. HealPot reads authorized data and computes personal comparisons when called. It has no scheduler or AI model.

Set the schedule's time zone. Each run should resolve the local date, check the connection and ask you to reconnect if authorization has expired or been revoked.

## Morning sleep report

Use this instruction in your assistant's scheduler.

```text
Every day at 09:00 Europe/Istanbul, review the sleep sessions ending on today's
local date through my connected Google Health MCP server.

Check get_connection_status first. Use get_daily_health_context for
sleep_duration, hrv and resting_heart_rate with a seven-day baseline.
Use get_sleep_sessions for recorded stages.

Report the recorded dates, retrieval time, units, changes from my baseline
and data gaps. Include one useful observation. If the sleep record has not
arrived, say so. Do not replace missing sleep with zero or time in bed,
invent stages, or treat a baseline change as a clinical abnormality.
Deliver through this assistant's task channel.
```

You can also invoke `morning_sleep_review(timezone="Europe/Istanbul")` on each run. For a report date `D`, read sessions with `start_date=D` and `end_date=D+1`. Sleep belongs to its recorded end date. The seven-day baseline excludes `D` and needs at least three recorded days.

## Evening goal review

Give the assistant your goals, then use this instruction.

```text
Every day at 21:00 Europe/Istanbul, review today's recorded health data against
the goals I gave you. Resolve today's local date on each run.

Check the connection and permitted metrics. Use get_daily_health_context for
relevant measurements and get_workouts when reviewing training.

Report the date, retrieval time, goal progress, changes from the previous seven
calendar days, units, aggregation methods, recorded-day coverage and missing data.
Suggest one next step based on my goals.
Leave unsupported goal judgments unassessed. Today's totals are provisional
because device uploads and late logging can change them.

Keep personal goals, baselines and clinical ranges separate. For a clinical
comparison, cite a reliable reference that fits the measurement and my context.
Do not apply ranges for individual readings to daily averages. If the reference
or context is missing, leave the assessment unassessed. Keep identifiable health
records out of public research queries. Do not diagnose or infer causation.
Deliver through this assistant's task channel.
```

You can also invoke `evening_goal_review(goals=..., timezone="Europe/Istanbul")` on each run. HealPot does not store your goals.

## Interpret the results

| Comparison | What it needs |
| --- | --- |
| Goal progress | A user-supplied target for the same quantity and period |
| Personal baseline change | At least three recorded days before the report day |
| Clinical range | A cited reference for the specific measurement and relevant user context |

HealPot does not research clinical ranges. Your assistant needs its own research tools for that comparison. A daily average, nightly temperature and laboratory result are different measurements even when they share a unit.

At 21:00, today's reporting period is still open. `calendar_day_finished` is false, and `provider_coverage_complete` remains unknown. A successful request does not prove that every device has synchronized.

Invoke MCP prompts again on each scheduled run. Saving an already-rendered prompt can freeze its date. These recipes do not create tasks in an assistant. See [client setup](clients.md) and [tool details](tools.md).
