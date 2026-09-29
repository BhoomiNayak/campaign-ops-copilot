"""API routes.

Thin HTTP layer over the analysis engine and in-memory store. Business logic
lives in app.analysis.* — routes only parse inputs, call the engine, and
serialize responses. This separation is what keeps the app easy to scale later
(e.g. swap the store for a database without touching analysis code).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse

from ..analysis import anomalies, metrics, reports, validation
from ..analysis.recommendations import recommendations_for  # noqa: F401 (re-export convenience)
from ..config import (
    APP_VERSION,
    DEFAULT_THRESHOLDS,
    MAX_UPLOAD_BYTES,
    THRESHOLD_META,
    Thresholds,
    merge_thresholds,
    thresholds_as_dict,
)
from ..data.sample import sample_csv_bytes
from ..models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CampaignsResponse,
    DatasetSummary,
    Finding,
    FindingStatus,
    HealthResponse,
    Severity,
    UploadResponse,
)
from ..store import DatasetRecord, store

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _require_dataset(dataset_id: str) -> DatasetRecord:
    record = store.get(dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dataset not found or expired (in-memory).")
    return record


def _ensure_analyzed(record: DatasetRecord) -> None:
    """Run analysis lazily if it hasn't been run yet, using default thresholds."""
    if not record.analyzed:
        findings, notes = anomalies.detect(record.df, DEFAULT_THRESHOLDS)
        store.set_findings(record.dataset_id, findings, notes, DEFAULT_THRESHOLDS)


def _record_thresholds(record: DatasetRecord) -> Thresholds:
    """The thresholds applied to a record's cached findings (defaults if unset)."""
    return record.thresholds if isinstance(record.thresholds, Thresholds) else DEFAULT_THRESHOLDS


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Liveness/readiness check."""
    return HealthResponse(status="ok", version=APP_VERSION)


# ---------------------------------------------------------------------------
# Sample CSV download
# ---------------------------------------------------------------------------
@router.get("/sample.csv", tags=["data"])
def sample_csv() -> PlainTextResponse:
    """Download a synthetic sample CSV (illustrative data only)."""
    return PlainTextResponse(
        content=sample_csv_bytes().decode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=campaigns_sample.csv"},
    )


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
async def _read_capped(file: UploadFile, cap: int) -> bytes:
    """Read an upload in bounded chunks, aborting as soon as the cap is exceeded.

    This avoids buffering an arbitrarily large body into memory before the size
    check (audit fix M2). Peak memory is bounded to ~cap + one chunk.
    """
    chunk_size = 64 * 1024
    total = 0
    parts: list[bytes] = []
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > cap:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Limit is {cap // (1024 * 1024)} MB.",
            )
        parts.append(chunk)
    return b"".join(parts)


def _looks_like_csv(file: UploadFile) -> bool:
    """Light content-type / extension guard for uploaded files."""
    name = (file.filename or "").lower()
    if name.endswith(".csv"):
        return True
    allowed_types = {
        "text/csv",
        "application/csv",
        "text/plain",
        "application/vnd.ms-excel",  # some browsers label .csv this way
        "application/octet-stream",
    }
    return (file.content_type or "") in allowed_types


@router.post("/upload", response_model=UploadResponse, tags=["data"])
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    """Upload and validate a campaign CSV.

    On success, stores the cleaned dataset in memory and returns an opaque
    dataset id, the validation report, and the computed summary.
    """
    if not _looks_like_csv(file):
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Please upload a .csv file.",
        )

    raw = await _read_capped(file, MAX_UPLOAD_BYTES)

    df, report = validation.parse_and_validate(raw)
    if df is None:
        # Validation failed at file level — return the report with a 422 body so
        # the client can render the specific errors.
        return UploadResponse(dataset_id="", validation=report, summary=None)

    dataset_id = store.create(df, source="upload")
    summary = metrics.compute_summary(df, dataset_id)
    return UploadResponse(dataset_id=dataset_id, validation=report, summary=summary)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
@router.post("/demo", response_model=UploadResponse, tags=["data"])
def load_demo() -> UploadResponse:
    """Load the clearly-labeled synthetic demo dataset and return its id.

    The demo runs through the exact same validation path as a real upload, so
    the stored DataFrame and the returned report are guaranteed to be consistent
    (audit L3 — no separate parse).
    """
    df, report = validation.parse_and_validate(sample_csv_bytes())
    if df is None:  # pragma: no cover - the bundled sample is always valid
        raise HTTPException(status_code=500, detail="Sample data failed validation.")
    dataset_id = store.create(df, source="demo")
    summary = metrics.compute_summary(df, dataset_id)
    return UploadResponse(dataset_id=dataset_id, validation=report, summary=summary)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
@router.get("/datasets/{dataset_id}/summary", response_model=DatasetSummary, tags=["analytics"])
def get_summary(dataset_id: str) -> DatasetSummary:
    """Aggregate metrics for a dataset."""
    record = _require_dataset(dataset_id)
    summary = metrics.compute_summary(record.df, dataset_id)
    _ensure_analyzed(record)
    summary.num_findings = len(record.findings or [])
    return summary


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------
@router.get("/datasets/{dataset_id}/campaigns", response_model=CampaignsResponse, tags=["analytics"])
def get_campaigns(dataset_id: str) -> CampaignsResponse:
    """Per-campaign metrics plus the dataset-wide daily trend."""
    record = _require_dataset(dataset_id)
    return CampaignsResponse(
        dataset_id=dataset_id,
        campaigns=metrics.compute_campaigns(record.df),
        trend=metrics.compute_trend(record.df),
    )


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------
@router.post("/datasets/{dataset_id}/analyze", response_model=AnalyzeResponse, tags=["analysis"])
def analyze(
    dataset_id: str,
    body: Optional[AnalyzeRequest] = Body(default=None),
) -> AnalyzeResponse:
    """Run deterministic anomaly detection and cache the findings.

    Optionally accepts a ``thresholds`` override in the body; omitted fields
    keep their defaults. The applied thresholds are stored with the dataset so
    subsequent /findings and /report calls stay consistent.
    """
    record = _require_dataset(dataset_id)
    overrides = body.thresholds.model_dump() if body and body.thresholds else None
    thresholds = merge_thresholds(overrides)
    findings, notes = anomalies.detect(record.df, thresholds)
    store.set_findings(dataset_id, findings, notes, thresholds)
    return AnalyzeResponse(
        dataset_id=dataset_id,
        findings=findings,
        thresholds=thresholds_as_dict(thresholds),
        insufficient_data_notes=notes,
    )


# ---------------------------------------------------------------------------
# Findings (filterable)
# ---------------------------------------------------------------------------
@router.get("/datasets/{dataset_id}/findings", response_model=AnalyzeResponse, tags=["analysis"])
def get_findings(
    dataset_id: str,
    severity: Optional[Severity] = Query(default=None),
    campaign: Optional[str] = Query(default=None),
    domain: Optional[str] = Query(default=None),
    status: Optional[FindingStatus] = Query(default=None),
) -> AnalyzeResponse:
    """Retrieve findings with optional filters. Analysis runs lazily if needed."""
    record = _require_dataset(dataset_id)
    _ensure_analyzed(record)
    findings = list(record.findings or [])

    if severity is not None:
        findings = [f for f in findings if f.severity == severity]
    if campaign is not None:
        findings = [f for f in findings if (f.campaign_name or "") == campaign]
    if domain is not None:
        findings = [f for f in findings if (f.domain or "") == domain]
    if status is not None:
        findings = [f for f in findings if f.status == status]

    return AnalyzeResponse(
        dataset_id=dataset_id,
        findings=findings,
        thresholds=thresholds_as_dict(_record_thresholds(record)),
        insufficient_data_notes=record.insufficient_notes,
    )


# ---------------------------------------------------------------------------
# Update finding status
# ---------------------------------------------------------------------------
@router.patch(
    "/datasets/{dataset_id}/findings/{finding_id}",
    response_model=Finding,
    tags=["analysis"],
)
def set_finding_status(dataset_id: str, finding_id: str, status: FindingStatus) -> Finding:
    """Update a finding's workflow status (Open/Investigating/Resolved/Dismissed)."""
    _require_dataset(dataset_id)
    updated = store.update_finding_status(dataset_id, finding_id, status)
    if updated is None:
        raise HTTPException(status_code=404, detail="Finding not found. Run analyze first.")
    return updated


# ---------------------------------------------------------------------------
# Report / export
# ---------------------------------------------------------------------------
@router.get("/datasets/{dataset_id}/report", tags=["reporting"])
def get_report(
    dataset_id: str,
    format: str = Query(default="html", pattern="^(html|summary_csv|findings_csv)$"),
):
    """Generate a downloadable report.

    format=html          -> print-friendly audit report
    format=summary_csv   -> campaign summary CSV
    format=findings_csv  -> findings CSV
    """
    record = _require_dataset(dataset_id)
    _ensure_analyzed(record)
    summary = metrics.compute_summary(record.df, dataset_id)
    summary.num_findings = len(record.findings or [])
    campaigns = metrics.compute_campaigns(record.df)
    findings = record.findings or []

    if format == "summary_csv":
        return PlainTextResponse(
            content=reports.summary_csv(summary, campaigns),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=campaign_summary.csv"},
        )
    if format == "findings_csv":
        return PlainTextResponse(
            content=reports.findings_csv(findings),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=findings.csv"},
        )

    html_doc = reports.audit_report_html(
        summary, campaigns, findings, record.insufficient_notes, _record_thresholds(record)
    )
    return HTMLResponse(content=html_doc)


# ---------------------------------------------------------------------------
# Threshold configuration
# ---------------------------------------------------------------------------
@router.get("/config/thresholds", tags=["system"])
def get_threshold_config() -> dict:
    """Return the default thresholds plus display metadata for the settings UI."""
    return {
        "defaults": thresholds_as_dict(DEFAULT_THRESHOLDS),
        "meta": THRESHOLD_META,
    }
