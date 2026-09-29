"""Deterministic synthetic sample data generator.

The output is SYNTHETIC and for illustration only — it contains no real
recipients or campaigns. Values are generated with a fixed seed so the demo is
reproducible, and are hand-shaped so the anomaly engine surfaces a variety of
findings:

  * "Q3 Founders Outreach" — healthy baseline (no findings expected).
  * "Enterprise ABM"       — bounce rate spikes in the later period.
  * "Reactivation Blast"   — reply rate declines sharply over time.
  * "Cold List Import"     — persistently elevated bounce rate (repeated issue).

A 'delivered' column is included so the delivered-based reply-rate path is
exercised.
"""

from __future__ import annotations

import io
import random
from datetime import date, timedelta

import pandas as pd

SEED = 42
_START = date(2026, 8, 1)
_DAYS = 14


def _rows() -> list[dict]:
    rng = random.Random(SEED)
    rows: list[dict] = []

    def emit(campaign: str, domain: str, day: int, sent: int, bounce_rate: float, reply_rate: float):
        bounced = int(round(sent * bounce_rate))
        delivered = max(sent - bounced, 0)
        replies = int(round(delivered * reply_rate))
        opens = min(delivered, int(round(delivered * rng.uniform(0.3, 0.6))))
        clicks = int(round(opens * rng.uniform(0.05, 0.2)))
        rows.append(
            {
                "date": (_START + timedelta(days=day)).isoformat(),
                "campaign_name": campaign,
                "domain": domain,
                "mailbox": f"outreach@{domain}",
                "sent": sent,
                "delivered": delivered,
                "bounced": bounced,
                "replies": replies,
                "opens": opens,
                "clicks": clicks,
            }
        )

    for d in range(_DAYS):
        # Healthy baseline campaign.
        emit(
            "Q3 Founders Outreach",
            "founders.example.com",
            d,
            sent=rng.randint(180, 220),
            bounce_rate=rng.uniform(0.01, 0.02),
            reply_rate=rng.uniform(0.04, 0.06),
        )

        # Enterprise ABM: bounce spikes in the second half.
        spike = 0.0 if d < _DAYS // 2 else 0.08
        emit(
            "Enterprise ABM",
            "abm.example.com",
            d,
            sent=rng.randint(150, 200),
            bounce_rate=rng.uniform(0.01, 0.02) + spike,
            reply_rate=rng.uniform(0.03, 0.05),
        )

        # Reactivation Blast: reply rate declines over the window.
        decline = max(0.06 - d * 0.005, 0.005)
        emit(
            "Reactivation Blast",
            "reactivate.example.com",
            d,
            sent=rng.randint(160, 210),
            bounce_rate=rng.uniform(0.015, 0.03),
            reply_rate=decline,
        )

        # Cold List Import: persistently high bounce (repeated issue).
        emit(
            "Cold List Import",
            "coldlist.example.com",
            d,
            sent=rng.randint(120, 170),
            bounce_rate=rng.uniform(0.09, 0.14),
            reply_rate=rng.uniform(0.005, 0.015),
        )

    return rows


def sample_dataframe() -> pd.DataFrame:
    """Return the synthetic dataset as a validated-shape DataFrame."""
    df = pd.DataFrame(_rows())
    # Match the validated dtypes used elsewhere.
    for col in ("sent", "delivered", "bounced", "replies", "opens", "clicks"):
        df[col] = df[col].astype("int64")
    return df


def sample_csv_bytes() -> bytes:
    """Return the synthetic dataset serialized as CSV bytes (for downloads)."""
    buf = io.StringIO()
    sample_dataframe().to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")
