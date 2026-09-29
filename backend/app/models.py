"""Pydantic models for API requests and responses.

These are the stable contract between backend and frontend. Analysis modules
produce plain dicts / dataclasses internally; routes serialize them through
these models so the OpenAPI schema stays accurate.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Severity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"


class FindingCategory(str, Enum):
    elevated_bounce = "elevated_bounce"
    bounce_spike = "bounce_spike"
    declining_replies = "declining_replies"
    low_replies = "low_replies"
    repeated_issue = "repeated_issue"
    incomplete_data = "incomplete_data"


class FindingStatus(str, Enum):
    open = "Open"
    investigating = "Investigating"
    resolved = "Resolved"
    dismissed = "Dismissed"


class Confidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
class ValidationIssue(BaseModel):
    row: Optional[int] = Field(
        default=None,
        description="1-based row number in the source CSV (None for file-level issues).",
    )
    column: Optional[str] = None
    code: str = Field(description="Machine-readable issue code, e.g. 'missing_column'.")
    message: str


class ValidationReport(BaseModel):
    ok: bool
    total_rows: int
    valid_rows: int
    dropped_rows: int = 0
    duplicate_rows: int = 0
    detected_columns: list[str] = []
    missing_required_columns: list[str] = []
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricNote(BaseModel):
    """Explains exactly how a metric was computed (e.g. which denominator)."""

    metric: str
    definition: str
    denominator_used: Optional[str] = None


class DatasetSummary(BaseModel):
    dataset_id: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    total_sent: int
    total_bounced: int
    total_replies: int
    total_delivered: Optional[int] = None
    bounce_rate: float
    reply_rate: float
    reply_rate_denominator: str = Field(
        description="Which denominator was used for the overall reply rate: 'delivered' or 'sent'."
    )
    num_campaigns: int
    num_findings: int = 0
    notes: list[MetricNote] = []


class CampaignMetrics(BaseModel):
    campaign_name: str
    domain: Optional[str] = None
    sent: int
    bounced: int
    replies: int
    delivered: Optional[int] = None
    bounce_rate: float
    reply_rate: float
    reply_rate_denominator: str
    periods: int = Field(description="Number of distinct dates observed for this campaign.")


class TrendPoint(BaseModel):
    date: str
    sent: int
    bounced: int
    replies: int
    bounce_rate: float
    reply_rate: float


class CampaignsResponse(BaseModel):
    dataset_id: str
    campaigns: list[CampaignMetrics]
    trend: list[TrendPoint] = Field(
        default=[], description="Dataset-wide daily trend across all campaigns."
    )


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------
class PeriodComparison(BaseModel):
    label: str
    current_value: Optional[float] = None
    prior_value: Optional[float] = None
    current_period: Optional[str] = None
    prior_period: Optional[str] = None


class Finding(BaseModel):
    id: str
    campaign_name: Optional[str] = None
    domain: Optional[str] = None
    severity: Severity
    category: FindingCategory
    title: str
    metric: str = Field(description="The metric that triggered the alert.")
    evidence: str = Field(description="Concrete numbers behind the finding.")
    explanation: str = Field(description="Plain-English description of what was observed.")
    recommendations: list[str] = []
    comparison: Optional[PeriodComparison] = None
    confidence: Confidence
    data_limitations: Optional[str] = None
    threshold_used: Optional[str] = None
    status: FindingStatus = FindingStatus.open


class AnalyzeResponse(BaseModel):
    dataset_id: str
    findings: list[Finding]
    thresholds: dict = Field(description="The threshold configuration used for this analysis.")
    insufficient_data_notes: list[str] = []


class ThresholdConfig(BaseModel):
    """User-supplied overrides for the anomaly thresholds.

    Every field is optional; omitted fields keep their default. Rate fields are
    fractions in [0, 1]; count fields are positive integers. Values are bounds-
    checked so the engine can never be handed a nonsensical configuration.
    """

    elevated_bounce_rate: Optional[float] = Field(default=None, ge=0, le=1)
    high_bounce_rate: Optional[float] = Field(default=None, ge=0, le=1)
    bounce_spike_delta: Optional[float] = Field(default=None, ge=0, le=1)
    low_reply_rate: Optional[float] = Field(default=None, ge=0, le=1)
    reply_decline_ratio: Optional[float] = Field(default=None, ge=0, le=1)
    min_sent_for_comparison: Optional[int] = Field(default=None, ge=1, le=10_000_000)
    repeated_issue_min_periods: Optional[int] = Field(default=None, ge=1, le=1000)
    incomplete_data_ratio: Optional[float] = Field(default=None, ge=0, le=1)


class AnalyzeRequest(BaseModel):
    """Optional body for POST /analyze."""

    thresholds: Optional[ThresholdConfig] = None


# ---------------------------------------------------------------------------
# Upload / dataset lifecycle
# ---------------------------------------------------------------------------
class UploadResponse(BaseModel):
    dataset_id: str
    validation: ValidationReport
    summary: Optional[DatasetSummary] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
