"""Application configuration and tunable anomaly-detection thresholds.

All rule thresholds live here so anomaly detection stays *deterministic* and
*configurable*. Nothing in the analysis engine should hardcode a threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from typing import Any


# ---------------------------------------------------------------------------
# File / upload limits
# ---------------------------------------------------------------------------
MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MB cap on uploaded CSVs
MAX_ROWS: int = 200_000  # guard against pathological inputs

# Required and optional CSV columns (documented in the project brief).
REQUIRED_COLUMNS: tuple[str, ...] = ("date", "campaign_name", "sent", "bounced", "replies")
OPTIONAL_COLUMNS: tuple[str, ...] = ("domain", "mailbox", "delivered", "opens", "clicks")
NUMERIC_COLUMNS: tuple[str, ...] = ("sent", "bounced", "replies", "delivered", "opens", "clicks")


@dataclass(frozen=True)
class Thresholds:
    """Deterministic thresholds used by the anomaly engine.

    Every value here is intentionally explicit and documented so that findings
    can cite the exact threshold that triggered them.
    """

    # A bounce rate at/above this fraction is considered "elevated".
    elevated_bounce_rate: float = 0.05  # 5%
    # A high-severity bounce rate.
    high_bounce_rate: float = 0.10  # 10%

    # Absolute increase in bounce rate (current period vs. prior) that counts as
    # a "sudden spike", expressed in rate points (e.g. 0.03 == +3 percentage pts).
    bounce_spike_delta: float = 0.03

    # A reply rate at/below this fraction is considered "low".
    low_reply_rate: float = 0.01  # 1%
    # Relative decline in reply rate vs. prior period that counts as "declining".
    reply_decline_ratio: float = 0.30  # a 30% relative drop

    # Minimum sent volume in a period for a comparison to be statistically
    # meaningful. Below this we explicitly flag "insufficient data".
    min_sent_for_comparison: int = 200

    # A campaign flagged in this many or more distinct periods is a "repeated issue".
    repeated_issue_min_periods: int = 2

    # Fraction of rows allowed to have missing optional reporting fields before
    # we raise an "incomplete data" finding.
    incomplete_data_ratio: float = 0.20  # 20%


DEFAULT_THRESHOLDS = Thresholds()


def thresholds_as_dict(t: Thresholds = DEFAULT_THRESHOLDS) -> dict[str, Any]:
    """Serialize thresholds for inclusion in reports / API responses."""
    return asdict(t)


def merge_thresholds(overrides: dict[str, Any] | None) -> Thresholds:
    """Return a Thresholds built from the defaults plus any provided overrides.

    Only keys present (and non-None) in ``overrides`` replace a default, so a
    partial config is fine. Unknown keys are ignored. This is the single place
    that turns a user-supplied config into the immutable dataclass the engine
    consumes.
    """
    if not overrides:
        return DEFAULT_THRESHOLDS
    valid = {f.name for f in fields(Thresholds)}
    clean = {k: v for k, v in overrides.items() if k in valid and v is not None}
    from dataclasses import replace

    return replace(DEFAULT_THRESHOLDS, **clean)


# Human-friendly metadata for each threshold, used to render the settings UI.
# kind: "rate" (0-1 shown as %) or "count" (integer).
THRESHOLD_META: dict[str, dict[str, Any]] = {
    "elevated_bounce_rate": {"label": "Elevated bounce rate", "kind": "rate"},
    "high_bounce_rate": {"label": "High bounce rate", "kind": "rate"},
    "bounce_spike_delta": {"label": "Bounce spike (increase)", "kind": "rate"},
    "low_reply_rate": {"label": "Low reply rate", "kind": "rate"},
    "reply_decline_ratio": {"label": "Reply decline (relative)", "kind": "rate"},
    "min_sent_for_comparison": {"label": "Min sent to compare periods", "kind": "count"},
    "repeated_issue_min_periods": {"label": "Repeated-issue min periods", "kind": "count"},
    "incomplete_data_ratio": {"label": "Incomplete-data threshold", "kind": "rate"},
}


# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------
APP_TITLE = "Campaign Ops Copilot API"
APP_DESCRIPTION = (
    "Analyze email campaign CSV data: compute metrics, detect anomalies with "
    "deterministic rules, and generate evidence-based recommendations. "
    "Rule-based only — no external AI services, no data leaves this server."
)
APP_VERSION = "0.1.0"
