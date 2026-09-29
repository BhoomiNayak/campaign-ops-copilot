"""Tests for deterministic anomaly detection, including insufficient-data handling."""

import pandas as pd

from app.analysis.anomalies import detect
from app.config import Thresholds
from app.models import FindingCategory


def _rows(campaign, days, sent, bounced, replies, delivered=None):
    out = []
    for i in range(days):
        row = {
            "date": f"2026-08-{i + 1:02d}",
            "campaign_name": campaign,
            "sent": sent,
            "bounced": bounced,
            "replies": replies,
        }
        if delivered is not None:
            row["delivered"] = delivered
        out.append(row)
    return out


def test_elevated_bounce_detected():
    # 12% bounce over high volume on a single date -> high severity elevated
    # bounce (single date, so no repeated_issue suppression).
    df = pd.DataFrame(_rows("HighBounce", days=1, sent=1200, bounced=144, replies=12))
    findings, _ = detect(df)
    cats = {f.category for f in findings}
    assert FindingCategory.elevated_bounce in cats
    eb = next(f for f in findings if f.category == FindingCategory.elevated_bounce)
    assert eb.severity.value == "high"
    assert eb.threshold_used is not None


def test_healthy_campaign_no_bounce_finding():
    df = pd.DataFrame(_rows("Healthy", days=4, sent=300, bounced=3, replies=15))
    findings, _ = detect(df)
    assert not any(f.category == FindingCategory.elevated_bounce for f in findings)


def test_insufficient_data_reported_not_invented():
    # Only one date -> cannot compare periods; must be a note, not a finding.
    df = pd.DataFrame(_rows("OneDay", days=1, sent=500, bounced=5, replies=10))
    findings, notes = detect(df)
    assert any("only one reporting date" in n for n in notes)
    assert not any(f.category == FindingCategory.bounce_spike for f in findings)


def test_low_volume_blocks_comparison():
    # Two dates but tiny volume -> insufficient for comparison.
    df = pd.DataFrame(_rows("Tiny", days=2, sent=10, bounced=1, replies=0))
    _, notes = detect(df)
    assert any("insufficient volume" in n for n in notes)


def test_bounce_spike_detected_with_enough_volume():
    # First half low bounce, second half high bounce, each half >= 200 sent/day.
    rows = _rows("Spike", days=2, sent=300, bounced=3, replies=10)  # prior: ~1%
    rows += [
        {"date": "2026-08-03", "campaign_name": "Spike", "sent": 300, "bounced": 45, "replies": 10},
        {"date": "2026-08-04", "campaign_name": "Spike", "sent": 300, "bounced": 45, "replies": 10},
    ]
    df = pd.DataFrame(rows)
    findings, _ = detect(df)
    spike = [f for f in findings if f.category == FindingCategory.bounce_spike]
    assert spike, "expected a bounce_spike finding"
    assert spike[0].comparison is not None
    assert spike[0].comparison.current_value > spike[0].comparison.prior_value


def test_declining_replies_detected():
    # Reply rate halves between periods, volume sufficient, low bounce.
    rows = [
        {"date": "2026-08-01", "campaign_name": "Decline", "sent": 300, "bounced": 3, "replies": 30},
        {"date": "2026-08-02", "campaign_name": "Decline", "sent": 300, "bounced": 3, "replies": 30},
        {"date": "2026-08-03", "campaign_name": "Decline", "sent": 300, "bounced": 3, "replies": 6},
        {"date": "2026-08-04", "campaign_name": "Decline", "sent": 300, "bounced": 3, "replies": 6},
    ]
    df = pd.DataFrame(rows)
    findings, _ = detect(df)
    assert any(f.category == FindingCategory.declining_replies for f in findings)


def test_repeated_issue_detected():
    # Elevated bounce on multiple dates -> repeated issue.
    df = pd.DataFrame(_rows("Repeat", days=3, sent=300, bounced=36, replies=3))
    findings, _ = detect(df)
    assert any(f.category == FindingCategory.repeated_issue for f in findings)


def test_repeated_issue_suppresses_redundant_elevated_bounce():
    # A campaign elevated on multiple dates yields repeated_issue; the redundant
    # lifetime elevated_bounce for that same campaign should be suppressed (M3).
    df = pd.DataFrame(_rows("Repeat", days=3, sent=300, bounced=36, replies=3))
    findings, _ = detect(df)
    cats = [f.category for f in findings]
    assert FindingCategory.repeated_issue in cats
    assert FindingCategory.elevated_bounce not in cats
    # The lifetime rate is preserved in the repeated_issue evidence.
    ri = next(f for f in findings if f.category == FindingCategory.repeated_issue)
    assert "lifetime bounce rate" in ri.evidence


def test_elevated_bounce_kept_without_repeated_issue():
    # Elevated on a single date only -> no repeated_issue, elevated_bounce stays.
    df = pd.DataFrame(_rows("OnceHigh", days=1, sent=400, bounced=48, replies=4))
    findings, _ = detect(df)
    cats = [f.category for f in findings]
    assert FindingCategory.elevated_bounce in cats
    assert FindingCategory.repeated_issue not in cats


def test_incomplete_data_detected():
    rows = [
        {"date": "2026-08-01", "campaign_name": "A", "sent": 100, "bounced": 2, "replies": 5, "opens": None},
        {"date": "2026-08-02", "campaign_name": "A", "sent": 100, "bounced": 2, "replies": 5, "opens": None},
        {"date": "2026-08-03", "campaign_name": "A", "sent": 100, "bounced": 2, "replies": 5, "opens": 40},
    ]
    df = pd.DataFrame(rows)
    findings, _ = detect(df)
    assert any(f.category == FindingCategory.incomplete_data for f in findings)


def test_determinism():
    df = pd.DataFrame(_rows("HighBounce", days=4, sent=300, bounced=36, replies=3))
    a, _ = detect(df)
    b, _ = detect(df)
    assert [f.id for f in a] == [f.id for f in b]


def test_thresholds_are_configurable():
    df = pd.DataFrame(_rows("Mild", days=1, sent=600, bounced=36, replies=20))  # 6% bounce, single date
    strict = Thresholds(elevated_bounce_rate=0.05)
    lax = Thresholds(elevated_bounce_rate=0.10)
    assert any(f.category == FindingCategory.elevated_bounce for f in detect(df, strict)[0])
    assert not any(f.category == FindingCategory.elevated_bounce for f in detect(df, lax)[0])
