# Scheduled, read-only health insight reports

A user connects Google Health MCP once through Google sign-in, then asks an assistant that supports scheduled tasks to run a morning or evening workflow. Scheduling and delivery happen in that assistant. Google Health MCP has no internal scheduler, outbound notification service, goal database or AI model; it returns this user's authorized Google Health data and descriptive arithmetic when called.

The Google OAuth proxy keeps provider tokens private and supports refresh. Persist both keys and OAuth storage across restarts. If Google authorization or the MCP refresh grant expires or is revoked, the scheduled task must ask the user to reconnect rather than inventing a report. Testing-mode Google grant limits can make unattended development connections shorter-lived than a publicly approved app.

## Morning sleep report

Example schedule: **09:00 every day, Europe/Istanbul**. Set the assistant's schedule time zone explicitly; do not interpret 09:00 as the server's UTC time.

The task can request the `morning_sleep_review` prompt with `timezone="Europe/Istanbul"` at every invocation. Alternatively, use this English instruction in the assistant's scheduler:

```text
Every morning at 09:00 Europe/Istanbul, use my connected Google Health MCP MCP to review the
sleep sessions ending on today's local date. Check connection status first.
Use get_daily_health_context for sleep_duration, hrv and resting_heart_rate,
with a seven-day personal baseline, and get_sleep_sessions for available stages.

Prepare a concise report: what was recorded, changes from my personal baseline,
one useful observation, and the data gaps. Show the recorded date and retrieval
time. Do not replace missing sleep with zero, time in bed, or invented stages.
If the sleep record has not arrived yet, say so. A personal baseline deviation
is not a clinical abnormality. Deliver the report through this assistant's
configured task channel.
```

For a report date `D`, query sessions with `start_date=D` and `end_date=D+1`. Sleep belongs to its recorded end date. The personal baseline reads `D-7` through `D` exclusively, so the current sleep result cannot contaminate its baseline. At least three recorded baseline days are required for a comparison.

## Evening goal review

Example schedule: **21:00 every day, Europe/Istanbul**. The user supplies their own goals to the assistant, such as an already-chosen activity target or a training plan. Google Health MCP does not prescribe targets or persist those preferences.

The task can request `evening_goal_review(goals=..., timezone="Europe/Istanbul")` on each run, or use this instruction:

```text
Every evening at 21:00 Europe/Istanbul, use my connected Google Health MCP MCP to review
today's recorded health data against the goals I gave you. Resolve today's
date in that time zone on each run. Check connection status and permitted
metrics, then use get_daily_health_context for relevant measurements and
get_workouts when training is relevant.

Write a short report with goal progress, descriptive changes from my prior
seven recorded calendar days, missing data, and one next step grounded in my
stated goals. Mark unsupported goal judgments as unassessed. Today's totals
are provisional; device synchronization and late logging may change them.

Keep goal targets, personal baselines, and clinical reference intervals
separate. If a reference-range assessment is relevant, verify and cite a
reliable source appropriate to the measurement and my known context. Do not
apply instantaneous-reading ranges to daily summaries. If that context or
research capability is unavailable, mark the clinical assessment not assessed.
Use generic public research queries without including identifiable health
records. Do not diagnose or infer causation. Deliver through this assistant's
configured task channel.
```

## What can be assessed

| Comparison | Source | Report interpretation |
| --- | --- | --- |
| Progress toward a personal goal | The user's explicit target, retained by the assistant | Assess only when the recorded metric and target refer to the same quantity and period |
| Change from a personal baseline | The user's preceding permitted, recorded calendar days | Descriptive arithmetic; minimum three recorded baseline days; not a medical classification |
| Within/outside a clinical interval | Independently verified, measurement-appropriate reference plus necessary user context | The assistant must cite the reference; otherwise leave it unassessed |

The MCP tools do not research the web or assign clinical reference intervals. The chosen assistant can use its own research tools when available. A nightly skin-temperature reading, a provider daily heart-rate average, an intraday resting reading and a laboratory measurement have different meanings; units alone do not establish interchangeable clinical thresholds.

## Report structure

A useful report contains:

1. Report date/time zone, recorded measurement dates and retrieval time.
2. Observations with units and explicit daily aggregation methods.
3. Goal progress where a matching goal was provided.
4. Descriptive personal-baseline changes with recorded-day coverage.
5. Separately sourced clinical-range assessments, or an explicit unassessed status.
6. Missing permissions, absent readings, failed queries and possible late synchronization.

The current day is not a finished reporting period at 21:00. `calendar_day_finished` is false for today; `provider_coverage_complete` remains unknown for all days. An assistant should not label the available cloud data complete merely because the MCP request succeeded.

Scheduled task capability and authorization handling belong to each client. The recipes are documentation and MCP prompts, not tasks created in Codex, Claude, Grok, Grok Bot or Muse by this repository change.
