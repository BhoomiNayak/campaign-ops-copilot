# Metric Definitions & Limitations

This document is the source of truth for how every metric is calculated and what
each anomaly rule means. The analysis engine is deterministic: identical input
plus identical thresholds always produce identical output.

## Input columns

| Column          | Required | Type    | Notes |
| --------------- | :------: | ------- | ----- |
| `date`          |   yes    | date    | Any pandas-parseable date; normalized to `YYYY-MM-DD`. |
| `campaign_name` |   yes    | string  | Must be non-empty. |
| `sent`          |   yes    | int ≥ 0 | Emails attempted. |
| `bounced`       |   yes    | int ≥ 0 | Emails that bounced. |
| `replies`       |   yes    | int ≥ 0 | Replies received. |
| `domain`        |    no    | string  | Sending/recipient domain. |
| `mailbox`       |    no    | string  | Sending mailbox. |
| `delivered`     |    no    | int ≥ 0 | Emails delivered (sent − bounced, ideally). |
| `opens`         |    no    | int ≥ 0 | Opens. |
| `clicks`        |    no    | int ≥ 0 | Clicks. |

Validation distinguishes **required** from **optional** columns:

- A row is **dropped** (and reported as an error) only when a *required* field
  is bad: unparseable `date`, empty `campaign_name`, or a blank / non-numeric /
  negative `sent`, `bounced`, or `replies`.
- A blank *optional* numeric cell (`delivered`, `opens`, `clicks`) is treated as
  a legitimately **missing value** — the row is kept and the cell is left
  missing so metrics degrade gracefully and the `incomplete_data` rule can
  report it. Garbage or negative values in optional columns are also treated as
  missing, with a warning.

Exact duplicate rows are dropped and counted. File-level problems (empty file,
missing required columns, unparseable CSV) fail the whole upload with a
structured error list and create no dataset.

## Metric definitions

### Bounce rate
```
bounce_rate = bounced / sent
```
- Denominator: **`sent`**, always.
- Zero-safe: if `sent == 0`, the rate is defined as `0.0`.

### Reply rate
```
reply_rate = replies / delivered   when 'delivered' is COMPLETE for the group and its total > 0
reply_rate = replies / sent        otherwise
```
- The denominator actually used (`delivered` or `sent`) is **reported alongside
  every reply-rate value** — in the API (`reply_rate_denominator`), the tables,
  the KPI cards, and the exported reports.
- Rationale: `delivered` excludes bounced mail, so it is the more accurate base
  for engagement when available. When it is missing or zero, we fall back to
  `sent` and say so rather than omitting the metric.
- **`delivered` is used only when it is present for *every* row in the group.**
  If any row is missing `delivered`, we do not divide a full reply count by a
  partial delivered sum — the group falls back to `sent`. For period
  comparisons the choice is made once per campaign so both periods share the
  same denominator.
- Zero-safe: if the chosen denominator is `0`, the rate is defined as `0.0`.
- Each campaign (and the dataset-wide trend) picks its denominator based on the
  completeness of `delivered` in that scope.

### Aggregates
- `total_sent`, `total_bounced`, `total_replies` are simple sums.
- `total_delivered` is `null` when no valid `delivered` column exists.
- `num_campaigns` is the count of distinct `campaign_name` values.

> Note: rates are **not** clamped to ≤ 100%. If `bounced + replies` exceed
> `sent` in the source data, validation raises a warning but keeps the row so
> the metric reflects the data as given rather than silently masking it.

## Anomaly rules

All thresholds live in `backend/app/config.py` (`Thresholds`) and are echoed in
every analysis response and report so a finding can always cite the threshold
that triggered it.

| Rule | Trigger (default threshold) | Severity |
| ---- | --------------------------- | -------- |
| Elevated bounce | Campaign lifetime `bounce_rate ≥ 5%` (≥ 10% = high) | medium / high |
| Bounce spike | Later-period bounce rate exceeds earlier period by `≥ +3 pts` | high |
| Declining replies | Later-period reply rate is `≥ 30%` lower (relative) than earlier | medium |
| Low replies | Campaign lifetime `reply_rate ≤ 1%` | low |
| Repeated issue | Elevated bounce on `≥ 2` distinct dates for a campaign | high |
| Incomplete data | An optional column is missing/blank in `≥ 20%` of rows | info |

### Period comparisons (spike / decline)
Each campaign's distinct dates are sorted and split at the median into an
earlier ("prior") and later ("current") half. A comparison is performed **only
when both halves have at least `min_sent_for_comparison` (default 200) sent**.

When there is only one date, or a half lacks sufficient volume, the tool does
**not** invent a comparison. Instead it records an explicit *insufficient data*
note (surfaced in the UI and reports). This is a deliberate product decision:
absence of evidence is reported as such, never as a finding.

### Confidence
- `high` — enough volume for the rule to be reliable.
- `medium` — level-based engagement findings, or period comparisons at the
  volume floor.
- `low` — below `min_sent_for_comparison`; the finding is shown but flagged as
  potentially noisy via `data_limitations`.

### Finding de-duplication
When a campaign trips both the recurring-bounce rule (`repeated_issue`) and the
lifetime `elevated_bounce` rule, only the `repeated_issue` finding is kept — it
already conveys the elevated level (its evidence cites the lifetime rate) and is
the higher-signal result. A `bounce_spike` is always kept separately, because a
sudden increase is distinct information from a persistently elevated level.

### Campaign identity
A campaign is identified by `campaign_name` alone. If the same name appears
under multiple `domain` values, those rows are aggregated together and the
campaign's `domain` is reported as `"multiple"`. Use distinct campaign names if
you need per-domain separation.

## What this tool does not do

- It does **not** determine root cause. Findings describe *what* was observed and
  suggest *what to check*, never *why* it happened with certainty.
- It does **not** connect to any email platform or send data anywhere.
- It does **not** guarantee inbox placement or monitor live campaigns.
- Metrics reflect only the uploaded data; gaps in reporting degrade confidence
  rather than being filled with assumptions.

## Storage limitations

Datasets live in process memory only (see `backend/app/store.py`): they are lost
on restart, are not shared across worker processes (run a single Uvicorn
worker), and are bounded by a soft cap with oldest-first eviction.
