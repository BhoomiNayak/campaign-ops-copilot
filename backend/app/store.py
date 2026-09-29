"""In-memory dataset store.

Datasets are keyed by opaque, unguessable ids (uuid4 hex). This is an MVP
store with clearly documented limitations:

  * Data lives only in the current process memory. It is lost on restart.
  * It is NOT shared across multiple worker processes; run a single worker
    (the default for `uvicorn app.main:app`) for consistent behavior.
  * There is no persistence, eviction, or auth. A soft cap bounds memory use.

Findings are cached per dataset after analysis so that GET /findings and the
report endpoint can filter without recomputing.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from .models import Finding


# Soft cap on number of datasets retained; oldest is evicted beyond this.
MAX_DATASETS = 50


@dataclass
class DatasetRecord:
    dataset_id: str
    df: pd.DataFrame
    source: str  # "upload" or "demo"
    findings: Optional[list[Finding]] = None
    insufficient_notes: list[str] = field(default_factory=list)
    analyzed: bool = False
    # The Thresholds used for the cached findings (None -> defaults were used).
    thresholds: Optional[object] = None


class DatasetStore:
    """Thread-safe in-memory store for validated datasets."""

    def __init__(self, max_datasets: int = MAX_DATASETS) -> None:
        self._data: dict[str, DatasetRecord] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._max = max_datasets

    def create(self, df: pd.DataFrame, source: str) -> str:
        dataset_id = uuid.uuid4().hex
        record = DatasetRecord(dataset_id=dataset_id, df=df, source=source)
        with self._lock:
            self._data[dataset_id] = record
            self._order.append(dataset_id)
            self._evict_if_needed()
        return dataset_id

    def get(self, dataset_id: str) -> Optional[DatasetRecord]:
        with self._lock:
            return self._data.get(dataset_id)

    def set_findings(
        self,
        dataset_id: str,
        findings: list[Finding],
        insufficient_notes: list[str],
        thresholds: Optional[object] = None,
    ) -> None:
        with self._lock:
            record = self._data.get(dataset_id)
            if record is not None:
                record.findings = findings
                record.insufficient_notes = insufficient_notes
                record.analyzed = True
                record.thresholds = thresholds

    def update_finding_status(
        self, dataset_id: str, finding_id: str, status
    ) -> Optional[Finding]:
        with self._lock:
            record = self._data.get(dataset_id)
            if record is None or record.findings is None:
                return None
            for f in record.findings:
                if f.id == finding_id:
                    f.status = status
                    return f
            return None

    def _evict_if_needed(self) -> None:
        while len(self._order) > self._max:
            oldest = self._order.pop(0)
            self._data.pop(oldest, None)


# Module-level singleton used by the API routes.
store = DatasetStore()
