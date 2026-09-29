"""Metric calculations.

Pure functions over a validated pandas DataFrame. No I/O, no globals. Every
rate is computed with an explicit, documented denominator and is safe against
zero denominators (a rate over zero volume is defined as 0.0, and the fact is
surfaced via the accompanying denominator label / notes).

Reply-rate denominator policy (decided for this project):
    reply_rate = replies / delivered   when a valid 'delivered' total (> 0) exists
    reply_rate = replies / sent        otherwise
The chosen denominator is always reported alongside the value.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from ..models import (
    CampaignMetrics,
    DatasetSummary,
    MetricNote,
    TrendPoint,
)


def safe_rate(numerator: float, denominator: float) -> float:
    """Return numerator/denominator, or 0.0 when the denominator is 0.

    Rates are clamped to [0, 1] is intentionally NOT done here — callers may
    have data where counts exceed sent (already warned during validation), and
    hiding that by clamping would misrepresent the data. We only guard div-by-zero.
    """
    if denominator is None or denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def delivered_total(df: pd.DataFrame) -> Optional[int]:
    """Return the usable 'delivered' total for a set of rows, or None.

    'delivered' is only used as a reply-rate denominator when it is BOTH
    present for every row in the group AND sums to > 0. If any row is missing
    'delivered' we must not divide a full reply count by a partial delivered
    sum (that would inflate the rate), so we return None and callers fall back
    to 'sent'. This is the guard for audit issue H2.
    """
    if "delivered" not in df.columns:
        return None
    col = df["delivered"]
    if col.isna().any():
        return None
    total = int(col.sum())
    return total if total > 0 else None


def compute_reply_rate(replies: int, delivered: Optional[int], sent: int) -> tuple[float, str]:
    """Compute reply rate and report which denominator was used.

    Returns (rate, denominator_label) where label is 'delivered' or 'sent'.
    """
    if delivered is not None and delivered > 0:
        return safe_rate(replies, delivered), "delivered"
    return safe_rate(replies, sent), "sent"


def compute_summary(df: pd.DataFrame, dataset_id: str) -> DatasetSummary:
    """Aggregate dataset-wide metrics."""
    total_sent = int(df["sent"].sum())
    total_bounced = int(df["bounced"].sum())
    total_replies = int(df["replies"].sum())

    total_delivered: Optional[int] = delivered_total(df)

    bounce_rate = safe_rate(total_bounced, total_sent)
    reply_rate, reply_denom = compute_reply_rate(total_replies, total_delivered, total_sent)

    dates = df["date"].dropna()
    period_start = str(dates.min()) if not dates.empty else None
    period_end = str(dates.max()) if not dates.empty else None

    notes = [
        MetricNote(
            metric="bounce_rate",
            definition="bounced / sent",
            denominator_used="sent",
        ),
        MetricNote(
            metric="reply_rate",
            definition="replies / delivered when delivered totals > 0, otherwise replies / sent",
            denominator_used=reply_denom,
        ),
    ]

    return DatasetSummary(
        dataset_id=dataset_id,
        period_start=period_start,
        period_end=period_end,
        total_sent=total_sent,
        total_bounced=total_bounced,
        total_replies=total_replies,
        total_delivered=total_delivered,
        bounce_rate=bounce_rate,
        reply_rate=reply_rate,
        reply_rate_denominator=reply_denom,
        num_campaigns=int(df["campaign_name"].nunique()),
        notes=notes,
    )


def compute_campaigns(df: pd.DataFrame) -> list[CampaignMetrics]:
    """Per-campaign aggregated metrics.

    Groups by campaign_name (and domain when present). Each campaign reports its
    own reply-rate denominator, since some campaigns may have delivered data and
    others may not.
    """
    has_domain = "domain" in df.columns

    group_keys = ["campaign_name"]
    results: list[CampaignMetrics] = []

    grouped = df.groupby(group_keys, dropna=False)
    for name, g in grouped:
        campaign_name = name if isinstance(name, str) else name[0]
        sent = int(g["sent"].sum())
        bounced = int(g["bounced"].sum())
        replies = int(g["replies"].sum())

        delivered: Optional[int] = delivered_total(g)

        bounce_rate = safe_rate(bounced, sent)
        reply_rate, reply_denom = compute_reply_rate(replies, delivered, sent)

        domain: Optional[str] = None
        if has_domain:
            domains = [d for d in g["domain"].dropna().unique().tolist() if str(d).strip()]
            domain = domains[0] if len(domains) == 1 else (None if not domains else "multiple")

        results.append(
            CampaignMetrics(
                campaign_name=str(campaign_name),
                domain=domain,
                sent=sent,
                bounced=bounced,
                replies=replies,
                delivered=delivered,
                bounce_rate=bounce_rate,
                reply_rate=reply_rate,
                reply_rate_denominator=reply_denom,
                periods=int(g["date"].nunique()),
            )
        )

    results.sort(key=lambda c: c.sent, reverse=True)
    return results


def compute_trend(df: pd.DataFrame) -> list[TrendPoint]:
    """Dataset-wide daily trend, summed across campaigns, ordered by date."""
    # Use delivered for the trend only when it is complete across the whole
    # dataset; otherwise fall back to sent consistently for every day (H2).
    has_delivered = delivered_total(df) is not None
    agg: dict[str, str] = {"sent": "sum", "bounced": "sum", "replies": "sum"}
    if has_delivered:
        agg["delivered"] = "sum"

    daily = df.groupby("date", dropna=True).agg(agg).reset_index().sort_values("date")

    points: list[TrendPoint] = []
    for _, row in daily.iterrows():
        sent = int(row["sent"])
        bounced = int(row["bounced"])
        replies = int(row["replies"])
        delivered = int(row["delivered"]) if has_delivered else None
        reply_rate, _ = compute_reply_rate(replies, delivered, sent)
        points.append(
            TrendPoint(
                date=str(row["date"]),
                sent=sent,
                bounced=bounced,
                replies=replies,
                bounce_rate=safe_rate(bounced, sent),
                reply_rate=reply_rate,
            )
        )
    return points
