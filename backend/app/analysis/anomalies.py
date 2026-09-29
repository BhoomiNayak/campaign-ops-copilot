"""Deterministic anomaly detection.

Rules are pure functions of the validated DataFrame plus a Thresholds config.
Given identical input and thresholds, the output is identical — no randomness,
no external calls.

Period comparisons split each campaign's timeline into an earlier ("prior") and
later ("current") half by the median date. A comparison is only performed when
BOTH halves carry enough sent volume (Thresholds.min_sent_for_comparison);
otherwise we do NOT invent a comparison — we record an explicit
"insufficient data" note (and, for engagement, may still raise a level-based
finding without a trend claim).

Rules implemented:
  1. elevated_bounce   - campaign lifetime bounce rate >= elevated/high threshold
  2. bounce_spike      - current-half bounce rate exceeds prior-half by >= delta
  3. declining_replies - current-half reply rate dropped >= ratio vs prior-half
  4. low_replies       - campaign lifetime reply rate <= low threshold
  5. repeated_issue    - a campaign is flagged in >= N distinct periods (dates)
  6. incomplete_data   - too many rows missing optional reporting fields
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from ..config import DEFAULT_THRESHOLDS, OPTIONAL_COLUMNS, Thresholds
from ..models import (
    Confidence,
    Finding,
    FindingCategory,
    PeriodComparison,
    Severity,
)
from .metrics import compute_reply_rate, delivered_total, safe_rate
from .recommendations import recommendations_for


@dataclass
class _HalfMetrics:
    sent: int
    bounced: int
    replies: int
    delivered: Optional[int]
    bounce_rate: float
    reply_rate: float
    reply_denom: str
    period_label: str


def _finding_id(*parts: str) -> str:
    """Stable, opaque id derived from the finding's identity (deterministic)."""
    raw = "|".join(parts)
    return "f_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _split_halves(
    g: pd.DataFrame, use_delivered: bool
) -> Optional[tuple[_HalfMetrics, _HalfMetrics]]:
    """Split a campaign group into (prior, current) halves by median date.

    Returns None when there are fewer than 2 distinct dates (no basis for a
    time comparison at all).

    ``use_delivered`` is decided once at the campaign level so BOTH halves use
    the same reply-rate denominator — otherwise a decline could compare
    replies/delivered against replies/sent (audit fixes H2 + M1). It is only
    True when the campaign's 'delivered' column is complete, so summing it per
    half never divides by a partial denominator.
    """
    dates = sorted(g["date"].dropna().unique().tolist())
    if len(dates) < 2:
        return None

    mid = len(dates) // 2
    prior_dates = set(dates[:mid])
    current_dates = set(dates[mid:])

    def _agg(sub: pd.DataFrame, label: str) -> _HalfMetrics:
        sent = int(sub["sent"].sum())
        bounced = int(sub["bounced"].sum())
        replies = int(sub["replies"].sum())
        delivered = int(sub["delivered"].sum()) if use_delivered else None
        reply_rate, denom = compute_reply_rate(replies, delivered, sent)
        return _HalfMetrics(
            sent=sent,
            bounced=bounced,
            replies=replies,
            delivered=delivered,
            bounce_rate=safe_rate(bounced, sent),
            reply_rate=reply_rate,
            reply_denom=denom,
            period_label=label,
        )

    prior = g[g["date"].isin(prior_dates)]
    current = g[g["date"].isin(current_dates)]
    prior_label = f"{min(prior_dates)}..{max(prior_dates)}"
    current_label = f"{min(current_dates)}..{max(current_dates)}"
    return _agg(prior, prior_label), _agg(current, current_label)


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def detect(
    df: pd.DataFrame,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> tuple[list[Finding], list[str]]:
    """Run all rules. Returns (findings, insufficient_data_notes)."""
    findings: list[Finding] = []
    insufficient: list[str] = []

    has_domain = "domain" in df.columns

    def _domain_for(g: pd.DataFrame) -> Optional[str]:
        if not has_domain:
            return None
        vals = [d for d in g["domain"].dropna().unique().tolist() if str(d).strip()]
        if len(vals) == 1:
            return str(vals[0])
        return "multiple" if vals else None

    # Track per-campaign flag counts for the "repeated issue" rule. We count the
    # number of distinct dates on which a campaign exhibited an elevated bounce
    # rate, as a proxy for a recurring problem.
    repeated_periods: dict[str, int] = {}
    # Lifetime bounce rate per campaign, so a repeated_issue finding can cite it
    # (used when we suppress the redundant lifetime elevated_bounce; audit M3).
    lifetime_bounce: dict[str, float] = {}

    for campaign_name, g in df.groupby("campaign_name", dropna=False):
        campaign = str(campaign_name)
        domain = _domain_for(g)

        sent = int(g["sent"].sum())
        bounced = int(g["bounced"].sum())
        replies = int(g["replies"].sum())
        # 'delivered' is used only when complete for this campaign (H2/M1).
        camp_delivered = delivered_total(g)
        use_delivered = camp_delivered is not None
        delivered = camp_delivered

        bounce_rate = safe_rate(bounced, sent)
        reply_rate, reply_denom = compute_reply_rate(replies, delivered, sent)
        lifetime_bounce[campaign] = bounce_rate

        # --- Rule 1: elevated bounce (lifetime) --------------------------
        if sent > 0 and bounce_rate >= thresholds.elevated_bounce_rate:
            is_high = bounce_rate >= thresholds.high_bounce_rate
            severity = Severity.high if is_high else Severity.medium
            threshold_val = (
                thresholds.high_bounce_rate if is_high else thresholds.elevated_bounce_rate
            )
            confidence = (
                Confidence.high
                if sent >= thresholds.min_sent_for_comparison
                else Confidence.low
            )
            limitation = (
                None
                if sent >= thresholds.min_sent_for_comparison
                else f"Low volume ({sent} sent) — rate may be noisy."
            )
            findings.append(
                Finding(
                    id=_finding_id("elevated_bounce", campaign, domain or ""),
                    campaign_name=campaign,
                    domain=domain,
                    severity=severity,
                    category=FindingCategory.elevated_bounce,
                    title=f"Elevated bounce rate for '{campaign}'",
                    metric="bounce_rate",
                    evidence=f"Bounce rate {_pct(bounce_rate)} over {sent} sent ({bounced} bounced).",
                    explanation=(
                        f"The lifetime bounce rate for '{campaign}' is {_pct(bounce_rate)}, "
                        f"at or above the {_pct(threshold_val)} threshold."
                    ),
                    recommendations=recommendations_for(FindingCategory.elevated_bounce),
                    confidence=confidence,
                    data_limitations=limitation,
                    threshold_used=f"bounce_rate >= {_pct(threshold_val)}",
                )
            )

        # Count per-date elevated bounce occurrences for repeated-issue rule.
        daily = g.groupby("date").agg({"sent": "sum", "bounced": "sum"})
        for _, row in daily.iterrows():
            r = safe_rate(int(row["bounced"]), int(row["sent"]))
            if int(row["sent"]) > 0 and r >= thresholds.elevated_bounce_rate:
                repeated_periods[campaign] = repeated_periods.get(campaign, 0) + 1

        # --- Rule 4: low replies (lifetime) ------------------------------
        if sent > 0 and reply_rate <= thresholds.low_reply_rate:
            confidence = (
                Confidence.medium
                if sent >= thresholds.min_sent_for_comparison
                else Confidence.low
            )
            findings.append(
                Finding(
                    id=_finding_id("low_replies", campaign, domain or ""),
                    campaign_name=campaign,
                    domain=domain,
                    severity=Severity.low,
                    category=FindingCategory.low_replies,
                    title=f"Low reply rate for '{campaign}'",
                    metric="reply_rate",
                    evidence=(
                        f"Reply rate {_pct(reply_rate)} "
                        f"({replies} replies / {reply_denom}={delivered if reply_denom=='delivered' else sent})."
                    ),
                    explanation=(
                        f"The reply rate for '{campaign}' is {_pct(reply_rate)}, at or below the "
                        f"{_pct(thresholds.low_reply_rate)} threshold. Reply rate denominator: {reply_denom}."
                    ),
                    recommendations=recommendations_for(FindingCategory.low_replies),
                    confidence=confidence,
                    data_limitations=(
                        None
                        if sent >= thresholds.min_sent_for_comparison
                        else f"Low volume ({sent} sent) — engagement rate may be noisy."
                    ),
                    threshold_used=f"reply_rate <= {_pct(thresholds.low_reply_rate)}",
                )
            )

        # --- Period-comparison rules (2 & 3) -----------------------------
        halves = _split_halves(g, use_delivered)
        if halves is None:
            insufficient.append(
                f"'{campaign}': only one reporting date — cannot compare periods."
            )
            continue

        prior, current = halves
        enough = (
            prior.sent >= thresholds.min_sent_for_comparison
            and current.sent >= thresholds.min_sent_for_comparison
        )
        if not enough:
            insufficient.append(
                f"'{campaign}': insufficient volume to compare periods "
                f"(prior sent={prior.sent}, current sent={current.sent}, "
                f"need >= {thresholds.min_sent_for_comparison} each)."
            )
            continue

        # Rule 2: bounce spike
        delta = current.bounce_rate - prior.bounce_rate
        if delta >= thresholds.bounce_spike_delta:
            findings.append(
                Finding(
                    id=_finding_id("bounce_spike", campaign, domain or "", current.period_label),
                    campaign_name=campaign,
                    domain=domain,
                    severity=Severity.high,
                    category=FindingCategory.bounce_spike,
                    title=f"Sudden bounce-rate increase for '{campaign}'",
                    metric="bounce_rate",
                    evidence=(
                        f"Bounce rate rose from {_pct(prior.bounce_rate)} to {_pct(current.bounce_rate)} "
                        f"(+{_pct(delta)})."
                    ),
                    explanation=(
                        f"'{campaign}' bounce rate increased by {_pct(delta)} between the prior and "
                        f"current period, at or above the +{_pct(thresholds.bounce_spike_delta)} threshold."
                    ),
                    recommendations=recommendations_for(FindingCategory.bounce_spike),
                    comparison=PeriodComparison(
                        label="bounce_rate",
                        current_value=current.bounce_rate,
                        prior_value=prior.bounce_rate,
                        current_period=current.period_label,
                        prior_period=prior.period_label,
                    ),
                    confidence=Confidence.high,
                    threshold_used=f"delta_bounce_rate >= +{_pct(thresholds.bounce_spike_delta)}",
                )
            )

        # Rule 3: declining replies (relative drop)
        if prior.reply_rate > 0:
            rel_drop = (prior.reply_rate - current.reply_rate) / prior.reply_rate
            if rel_drop >= thresholds.reply_decline_ratio:
                findings.append(
                    Finding(
                        id=_finding_id("declining_replies", campaign, domain or "", current.period_label),
                        campaign_name=campaign,
                        domain=domain,
                        severity=Severity.medium,
                        category=FindingCategory.declining_replies,
                        title=f"Declining reply rate for '{campaign}'",
                        metric="reply_rate",
                        evidence=(
                            f"Reply rate fell from {_pct(prior.reply_rate)} to {_pct(current.reply_rate)} "
                            f"(-{_pct(rel_drop)} relative)."
                        ),
                        explanation=(
                            f"'{campaign}' reply rate declined {_pct(rel_drop)} relative to the prior "
                            f"period, at or above the {_pct(thresholds.reply_decline_ratio)} threshold. "
                            f"Denominator: {current.reply_denom}."
                        ),
                        recommendations=recommendations_for(FindingCategory.declining_replies),
                        comparison=PeriodComparison(
                            label="reply_rate",
                            current_value=current.reply_rate,
                            prior_value=prior.reply_rate,
                            current_period=current.period_label,
                            prior_period=prior.period_label,
                        ),
                        confidence=Confidence.medium,
                        threshold_used=f"relative_reply_decline >= {_pct(thresholds.reply_decline_ratio)}",
                    )
                )

    # --- Rule 5: repeated issue ------------------------------------------
    for campaign, count in repeated_periods.items():
        if count >= thresholds.repeated_issue_min_periods:
            g = df[df["campaign_name"] == campaign]
            domain = _domain_for(g)
            findings.append(
                Finding(
                    id=_finding_id("repeated_issue", campaign, domain or ""),
                    campaign_name=campaign,
                    domain=domain,
                    severity=Severity.high,
                    category=FindingCategory.repeated_issue,
                    title=f"Recurring bounce issue for '{campaign}'",
                    metric="bounce_rate",
                    evidence=(
                        f"Elevated bounce rate observed on {count} distinct dates; "
                        f"lifetime bounce rate {_pct(lifetime_bounce.get(campaign, 0.0))}."
                    ),
                    explanation=(
                        f"'{campaign}' showed an elevated bounce rate on {count} separate dates, "
                        f"at or above the {thresholds.repeated_issue_min_periods}-period threshold, "
                        f"indicating a recurring rather than one-off problem. This finding "
                        f"subsumes the lifetime elevated-bounce signal for this campaign."
                    ),
                    recommendations=recommendations_for(FindingCategory.repeated_issue),
                    confidence=Confidence.high,
                    threshold_used=f"elevated_dates >= {thresholds.repeated_issue_min_periods}",
                )
            )

    # --- Rule 6: incomplete data -----------------------------------------
    present_optional = [c for c in OPTIONAL_COLUMNS if c in df.columns]
    total = len(df)
    if total > 0:
        for col in present_optional:
            series = df[col]
            # A value is "missing" if it is null, or (for text columns) blank.
            missing_mask = series.isna()
            if series.dtype == object:
                missing_mask = missing_mask | (series.astype(str).str.strip() == "")
            missing = int(missing_mask.sum())
            ratio = missing / total
            if ratio >= thresholds.incomplete_data_ratio:
                findings.append(
                    Finding(
                        id=_finding_id("incomplete_data", col),
                        campaign_name=None,
                        domain=None,
                        severity=Severity.info,
                        category=FindingCategory.incomplete_data,
                        title=f"Incomplete reporting data in '{col}'",
                        metric=col,
                        evidence=f"{missing} of {total} rows ({_pct(ratio)}) are missing '{col}'.",
                        explanation=(
                            f"The optional column '{col}' is missing in {_pct(ratio)} of rows, "
                            f"at or above the {_pct(thresholds.incomplete_data_ratio)} threshold. "
                            f"Metrics relying on it may be less reliable."
                        ),
                        recommendations=recommendations_for(FindingCategory.incomplete_data),
                        confidence=Confidence.high,
                        data_limitations=f"'{col}' is incomplete; dependent metrics degrade gracefully.",
                        threshold_used=f"missing_ratio >= {_pct(thresholds.incomplete_data_ratio)}",
                    )
                )

    # --- Deduplicate overlapping findings (audit M3) ---------------------
    # A repeated_issue already conveys (and subsumes) the lifetime
    # elevated_bounce for the same campaign, so drop the redundant one to keep
    # the findings list focused. bounce_spike is kept: it is a distinct
    # "got worse over time" signal, not the same as an elevated level.
    repeated_campaigns = {
        f.campaign_name for f in findings if f.category == FindingCategory.repeated_issue
    }
    if repeated_campaigns:
        findings = [
            f
            for f in findings
            if not (
                f.category == FindingCategory.elevated_bounce
                and f.campaign_name in repeated_campaigns
            )
        ]

    # Deterministic ordering: severity desc, then category, then campaign.
    severity_order = {Severity.high: 0, Severity.medium: 1, Severity.low: 2, Severity.info: 3}
    findings.sort(
        key=lambda f: (
            severity_order[f.severity],
            f.category.value,
            f.campaign_name or "",
            f.id,
        )
    )
    return findings, insufficient
