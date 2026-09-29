"""Tests for metric calculations, including zero-denominator edge cases."""

import pandas as pd

from app.analysis.metrics import (
    compute_campaigns,
    compute_reply_rate,
    compute_summary,
    compute_trend,
    safe_rate,
)


def test_safe_rate_zero_denominator():
    assert safe_rate(5, 0) == 0.0
    assert safe_rate(0, 0) == 0.0
    assert safe_rate(2, 8) == 0.25


def test_reply_rate_prefers_delivered():
    rate, denom = compute_reply_rate(replies=10, delivered=200, sent=250)
    assert denom == "delivered"
    assert rate == 10 / 200


def test_reply_rate_falls_back_to_sent():
    rate, denom = compute_reply_rate(replies=10, delivered=None, sent=250)
    assert denom == "sent"
    assert rate == 10 / 250


def test_reply_rate_falls_back_when_delivered_zero():
    rate, denom = compute_reply_rate(replies=10, delivered=0, sent=250)
    assert denom == "sent"


def test_delivered_total_none_when_incomplete():
    # H2 regression: if any delivered cell is missing, delivered must not be
    # used as a denominator (would divide full replies by a partial sum).
    from app.analysis.metrics import delivered_total

    complete = pd.DataFrame(
        [
            {"date": "2026-08-01", "campaign_name": "A", "sent": 100, "bounced": 2, "replies": 4, "delivered": 98},
            {"date": "2026-08-02", "campaign_name": "A", "sent": 100, "bounced": 2, "replies": 4, "delivered": 98},
        ]
    )
    assert delivered_total(complete) == 196

    incomplete = complete.copy()
    incomplete.loc[1, "delivered"] = None
    assert delivered_total(incomplete) is None


def test_summary_falls_back_to_sent_when_delivered_incomplete():
    df = pd.DataFrame(
        [
            {"date": "2026-08-01", "campaign_name": "A", "sent": 100, "bounced": 2, "replies": 4, "delivered": 98},
            {"date": "2026-08-02", "campaign_name": "A", "sent": 100, "bounced": 2, "replies": 4, "delivered": None},
        ]
    )
    s = compute_summary(df, "d1")
    assert s.reply_rate_denominator == "sent"
    assert s.total_delivered is None


def _df():
    return pd.DataFrame(
        [
            {"date": "2026-08-01", "campaign_name": "A", "sent": 100, "bounced": 5, "replies": 4, "delivered": 95},
            {"date": "2026-08-02", "campaign_name": "A", "sent": 100, "bounced": 5, "replies": 6, "delivered": 95},
            {"date": "2026-08-01", "campaign_name": "B", "sent": 50, "bounced": 0, "replies": 2, "delivered": 50},
        ]
    )


def test_summary_totals_and_denominator():
    s = compute_summary(_df(), "d1")
    assert s.total_sent == 250
    assert s.total_bounced == 10
    assert s.total_replies == 12
    assert s.bounce_rate == 10 / 250
    assert s.reply_rate_denominator == "delivered"
    assert s.num_campaigns == 2
    assert s.period_start == "2026-08-01"
    assert s.period_end == "2026-08-02"


def test_summary_reply_denominator_sent_when_no_delivered():
    df = _df().drop(columns=["delivered"])
    s = compute_summary(df, "d1")
    assert s.reply_rate_denominator == "sent"
    assert s.total_delivered is None


def test_campaigns_sorted_by_volume():
    cs = compute_campaigns(_df())
    assert cs[0].campaign_name == "A"  # higher volume first
    assert cs[0].sent == 200
    assert cs[1].campaign_name == "B"


def test_trend_ordered_by_date():
    t = compute_trend(_df())
    dates = [p.date for p in t]
    assert dates == sorted(dates)
    assert t[0].sent == 150  # 2026-08-01: A(100) + B(50)
