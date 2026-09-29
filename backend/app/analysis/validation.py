"""CSV parsing and validation.

Treats every uploaded file as untrusted input. Produces a normalized pandas
DataFrame plus a structured ValidationReport describing what was accepted,
dropped, or flagged. The parser never raises on bad *row* data — it collects
issues and drops offending rows so a mostly-good file still yields results.

File-level problems (empty file, missing required columns, unparseable CSV)
are returned as a failed report with ok=False and no DataFrame.
"""

from __future__ import annotations

import io
from typing import Optional

import pandas as pd

from ..config import (
    MAX_ROWS,
    NUMERIC_COLUMNS,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
)
from ..models import ValidationIssue, ValidationReport


ALL_KNOWN_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase/strip header names so 'Campaign_Name' == 'campaign_name'."""
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def parse_and_validate(raw: bytes) -> tuple[Optional[pd.DataFrame], ValidationReport]:
    """Parse raw CSV bytes and validate them.

    Returns (clean_dataframe_or_None, report). The DataFrame is only returned
    when at least one valid row survives validation.
    """
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    # --- Parse ------------------------------------------------------------
    if not raw or not raw.strip():
        return None, ValidationReport(
            ok=False,
            total_rows=0,
            valid_rows=0,
            errors=[ValidationIssue(code="empty_file", message="The uploaded file is empty.")],
        )

    try:
        df = pd.read_csv(io.BytesIO(raw))
    except pd.errors.ParserError:
        # The file is ragged (rows with inconsistent field counts, usually from
        # unquoted commas inside values). Rather than reject the whole file with
        # a cryptic tokenizer error, skip the malformed lines and keep going so
        # that column-level validation can still run and give a clear message
        # (e.g. "missing required columns"). Skipped lines are reported.
        try:
            df = pd.read_csv(
                io.BytesIO(raw),
                engine="python",
                on_bad_lines="skip",
            )
        except Exception as exc:  # noqa: BLE001 - still unparseable
            return None, ValidationReport(
                ok=False,
                total_rows=0,
                valid_rows=0,
                errors=[
                    ValidationIssue(
                        code="parse_error",
                        message=f"Could not parse the file as CSV: {exc}",
                    )
                ],
            )
        # Estimate how many data lines were dropped so the user knows.
        data_lines = sum(
            1 for line in raw.decode("utf-8", errors="replace").splitlines() if line.strip()
        )
        skipped = max(data_lines - 1 - int(len(df)), 0)  # -1 for the header
        if skipped:
            warnings.append(
                ValidationIssue(
                    code="skipped_malformed_lines",
                    message=(
                        f"Skipped {skipped} malformed line(s) with an unexpected number of "
                        "columns (often caused by unquoted commas inside a value)."
                    ),
                )
            )
    except Exception as exc:  # noqa: BLE001 - surface any other parse failure cleanly
        return None, ValidationReport(
            ok=False,
            total_rows=0,
            valid_rows=0,
            errors=[
                ValidationIssue(
                    code="parse_error",
                    message=f"Could not parse the file as CSV: {exc}",
                )
            ],
        )

    df = _normalize_columns(df)
    detected = list(df.columns)
    total_rows = int(len(df))

    if total_rows == 0:
        return None, ValidationReport(
            ok=False,
            total_rows=0,
            valid_rows=0,
            detected_columns=detected,
            errors=[ValidationIssue(code="no_rows", message="The file has headers but no data rows.")],
        )

    if total_rows > MAX_ROWS:
        return None, ValidationReport(
            ok=False,
            total_rows=total_rows,
            valid_rows=0,
            detected_columns=detected,
            errors=[
                ValidationIssue(
                    code="too_many_rows",
                    message=f"File has {total_rows} rows; the limit is {MAX_ROWS}.",
                )
            ],
        )

    # --- Required columns -------------------------------------------------
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return None, ValidationReport(
            ok=False,
            total_rows=total_rows,
            valid_rows=0,
            detected_columns=detected,
            missing_required_columns=missing,
            errors=[
                ValidationIssue(
                    code="missing_column",
                    column=col,
                    message=f"Required column '{col}' is missing.",
                )
                for col in missing
            ],
            warnings=warnings,
        )

    # Warn about unknown columns (kept, but flagged).
    for col in df.columns:
        if col not in ALL_KNOWN_COLUMNS:
            warnings.append(
                ValidationIssue(
                    code="unknown_column",
                    column=col,
                    message=f"Column '{col}' is not a recognized field and will be ignored.",
                )
            )

    # --- Row-level validation --------------------------------------------
    # Track which rows are valid. Row numbers are 1-based for humans and
    # account for the header line, so data row 0 -> CSV line 2.
    valid_mask = pd.Series(True, index=df.index)

    # Dates
    parsed_dates = pd.to_datetime(df["date"], errors="coerce")
    bad_date_idx = parsed_dates.isna()
    for i in df.index[bad_date_idx]:
        errors.append(
            ValidationIssue(
                row=int(i) + 2,
                column="date",
                code="invalid_date",
                message=f"Unparseable date: {df.at[i, 'date']!r}.",
            )
        )
    valid_mask &= ~bad_date_idx
    df["date"] = parsed_dates

    # campaign_name must be non-empty
    empty_name = df["campaign_name"].isna() | (
        df["campaign_name"].astype(str).str.strip() == ""
    )
    for i in df.index[empty_name]:
        errors.append(
            ValidationIssue(
                row=int(i) + 2,
                column="campaign_name",
                code="empty_campaign_name",
                message="campaign_name is empty.",
            )
        )
    valid_mask &= ~empty_name

    # Numeric columns split into required (strict) and optional (lenient).
    #
    # Required numeric columns (sent, bounced, replies): a blank, non-numeric,
    # or negative value invalidates the row — it is dropped and reported as an
    # error. These drive every metric, so they must be trustworthy.
    #
    # Optional numeric columns (delivered, opens, clicks): a blank cell is a
    # legitimately *missing* value, NOT an error. The row is kept and the cell
    # is left as missing (<NA>) so downstream metrics can degrade gracefully and
    # the incomplete_data rule can report it. Actual garbage or negative values
    # in optional columns are also treated as missing, but with a warning.
    # (Audit fix H1.)
    required_numeric = [c for c in NUMERIC_COLUMNS if c in REQUIRED_COLUMNS and c in df.columns]
    optional_numeric = [c for c in NUMERIC_COLUMNS if c in OPTIONAL_COLUMNS and c in df.columns]
    present_numeric = required_numeric + optional_numeric

    for col in required_numeric:
        coerced = pd.to_numeric(df[col], errors="coerce")
        bad = coerced.isna()
        for i in df.index[bad]:
            errors.append(
                ValidationIssue(
                    row=int(i) + 2,
                    column=col,
                    code="non_numeric",
                    message=f"Column '{col}' has a missing or non-numeric value: {df.at[i, col]!r}.",
                )
            )
        negative = coerced < 0
        for i in df.index[negative & ~bad]:
            errors.append(
                ValidationIssue(
                    row=int(i) + 2,
                    column=col,
                    code="negative_value",
                    message=f"Column '{col}' has a negative value: {coerced.at[i]}.",
                )
            )
        valid_mask &= ~(bad | negative)
        df[col] = coerced

    for col in optional_numeric:
        original = df[col]
        coerced = pd.to_numeric(original, errors="coerce")
        blank = original.isna() | (original.astype(str).str.strip() == "")
        # Non-blank values that failed to parse are genuine garbage -> warn.
        garbage = coerced.isna() & ~blank
        for i in df.index[garbage]:
            warnings.append(
                ValidationIssue(
                    row=int(i) + 2,
                    column=col,
                    code="optional_non_numeric",
                    message=(
                        f"Optional column '{col}' has a non-numeric value: "
                        f"{original.at[i]!r}; treated as missing."
                    ),
                )
            )
        negative = coerced < 0
        for i in df.index[negative]:
            warnings.append(
                ValidationIssue(
                    row=int(i) + 2,
                    column=col,
                    code="optional_negative",
                    message=(
                        f"Optional column '{col}' has a negative value: "
                        f"{coerced.at[i]}; treated as missing."
                    ),
                )
            )
        # Garbage/negative become missing; blanks are already NaN. Row is kept.
        coerced = coerced.where(~negative)
        df[col] = coerced

    # Logical consistency: bounced + replies should not exceed sent; if a
    # 'delivered' column exists, delivered should not exceed sent. These are
    # warnings (we keep the row) unless sent is zero with positive activity.
    if valid_mask.any():
        sub = df[valid_mask]
        over = sub["bounced"].fillna(0) + sub["replies"].fillna(0) > sub["sent"].fillna(0)
        for i in sub.index[over]:
            warnings.append(
                ValidationIssue(
                    row=int(i) + 2,
                    code="counts_exceed_sent",
                    message=(
                        f"bounced + replies ({int(df.at[i, 'bounced'])}+{int(df.at[i, 'replies'])}) "
                        f"exceed sent ({int(df.at[i, 'sent'])})."
                    ),
                )
            )
        if "delivered" in df.columns:
            del_over = sub["delivered"].fillna(0) > sub["sent"].fillna(0)
            for i in sub.index[del_over]:
                warnings.append(
                    ValidationIssue(
                        row=int(i) + 2,
                        column="delivered",
                        code="delivered_exceeds_sent",
                        message=(
                            f"delivered ({int(df.at[i, 'delivered'])}) exceeds "
                            f"sent ({int(df.at[i, 'sent'])})."
                        ),
                    )
                )

    clean = df[valid_mask].copy()

    # --- Duplicate detection ---------------------------------------------
    # A duplicate is an identical (date, campaign_name, domain?) key with the
    # same metric values. We drop exact duplicates but report the count.
    dup_keys = ["date", "campaign_name"]
    if "domain" in clean.columns:
        dup_keys.append("domain")
    duplicate_mask = clean.duplicated(subset=dup_keys + [c for c in present_numeric], keep="first")
    duplicate_count = int(duplicate_mask.sum())
    if duplicate_count:
        warnings.append(
            ValidationIssue(
                code="duplicate_rows",
                message=f"Dropped {duplicate_count} exact duplicate row(s).",
            )
        )
    clean = clean[~duplicate_mask].copy()

    valid_rows = int(len(clean))
    dropped = total_rows - valid_rows - duplicate_count

    report = ValidationReport(
        ok=valid_rows > 0,
        total_rows=total_rows,
        valid_rows=valid_rows,
        dropped_rows=max(dropped, 0),
        duplicate_rows=duplicate_count,
        detected_columns=detected,
        missing_required_columns=[],
        errors=errors,
        warnings=warnings,
    )

    if valid_rows == 0:
        return None, report

    # Normalize date to ISO date string for downstream stability.
    clean["date"] = clean["date"].dt.strftime("%Y-%m-%d")
    # Required numeric columns are guaranteed non-null -> plain int64.
    for col in required_numeric:
        clean[col] = clean[col].round().astype("int64")
    # Optional numeric columns may contain missing values -> nullable Int64 so
    # <NA> is preserved for the metrics/incomplete_data logic downstream.
    for col in optional_numeric:
        clean[col] = clean[col].round().astype("Int64")

    clean = clean.reset_index(drop=True)
    return clean, report
