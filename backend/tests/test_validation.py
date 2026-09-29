"""Tests for CSV parsing and validation."""

from app.analysis.validation import parse_and_validate


def _csv(text: str) -> bytes:
    return text.strip().encode("utf-8")


GOOD = _csv(
    """
date,campaign_name,sent,bounced,replies
2026-08-01,Alpha,100,2,5
2026-08-02,Alpha,120,3,4
"""
)


def test_valid_file_passes():
    df, report = parse_and_validate(GOOD)
    assert report.ok is True
    assert df is not None
    assert report.total_rows == 2
    assert report.valid_rows == 2
    assert report.errors == []


def test_empty_file_fails():
    df, report = parse_and_validate(b"")
    assert df is None
    assert report.ok is False
    assert report.errors[0].code == "empty_file"


def test_missing_required_column():
    df, report = parse_and_validate(_csv("date,campaign_name,sent,bounced\n2026-08-01,A,10,1"))
    assert df is None
    assert report.ok is False
    assert "replies" in report.missing_required_columns


def test_invalid_date_row_dropped():
    data = _csv(
        """
date,campaign_name,sent,bounced,replies
not-a-date,Alpha,100,2,5
2026-08-02,Alpha,120,3,4
"""
    )
    df, report = parse_and_validate(data)
    assert df is not None
    assert report.valid_rows == 1
    assert any(e.code == "invalid_date" for e in report.errors)


def test_negative_and_non_numeric_dropped():
    data = _csv(
        """
date,campaign_name,sent,bounced,replies
2026-08-01,Alpha,-5,2,5
2026-08-02,Alpha,abc,3,4
2026-08-03,Alpha,120,3,4
"""
    )
    df, report = parse_and_validate(data)
    assert report.valid_rows == 1
    codes = {e.code for e in report.errors}
    assert "negative_value" in codes
    assert "non_numeric" in codes


def test_duplicate_rows_dropped_and_counted():
    data = _csv(
        """
date,campaign_name,sent,bounced,replies
2026-08-01,Alpha,100,2,5
2026-08-01,Alpha,100,2,5
2026-08-02,Alpha,120,3,4
"""
    )
    df, report = parse_and_validate(data)
    assert report.duplicate_rows == 1
    assert report.valid_rows == 2


def test_case_insensitive_headers():
    data = _csv("Date,Campaign_Name,Sent,Bounced,Replies\n2026-08-01,A,10,1,2")
    df, report = parse_and_validate(data)
    assert report.ok is True
    assert "campaign_name" in df.columns


def test_ragged_lines_skipped_then_missing_columns_reported():
    # A file with the wrong shape AND inconsistent field counts (like an HR
    # contact export). The parser should skip the bad lines and then report the
    # real problem: missing required columns — not a cryptic tokenizer error.
    data = _csv(
        """
SNo,Name,Email,Title,Company,,
1,Akanksha Puri,akanksha@x.com,Director HR,SourceFuse,,
2,Akhila Chandan,akhila@y.com,AVP HR," Estuate,",,
3,Bad Row,extra@z.com,Title,Company,extra1,extra2,extra3,extra4
"""
    )
    df, report = parse_and_validate(data)
    assert df is None
    assert report.ok is False
    # The real, actionable message:
    for col in ("date", "campaign_name", "sent", "bounced", "replies"):
        assert col in report.missing_required_columns
    # No raw "Expected N fields" tokenizer error surfaced to the user.
    assert not any(e.code == "parse_error" for e in report.errors)


def test_ragged_lines_skipped_but_valid_data_still_loads():
    # Correct columns, but one row has extra unquoted commas. The good rows
    # should still load, with a warning about the skipped line.
    data = _csv(
        """
date,campaign_name,sent,bounced,replies
2026-08-01,Alpha,100,2,5
2026-08-02,Bad,Row,With,Too,Many,Commas
2026-08-03,Alpha,120,3,4
"""
    )
    df, report = parse_and_validate(data)
    assert df is not None
    assert report.ok is True
    assert report.valid_rows == 2
    assert any(w.code == "skipped_malformed_lines" for w in report.warnings)


def test_blank_optional_column_keeps_row():
    # H1 regression: a blank OPTIONAL numeric cell must NOT drop the row.
    data = _csv(
        """
date,campaign_name,sent,bounced,replies,opens
2026-08-01,A,100,2,5,40
2026-08-02,A,120,3,6,
2026-08-03,A,110,2,5,
"""
    )
    df, report = parse_and_validate(data)
    assert df is not None
    assert report.valid_rows == 3  # all rows kept
    assert not any(e.code == "non_numeric" for e in report.errors)
    # The two blank opens survive as missing values.
    assert int(df["opens"].isna().sum()) == 2


def test_blank_required_column_still_drops_row():
    # Contrast: a blank REQUIRED numeric cell must still drop the row.
    data = _csv(
        """
date,campaign_name,sent,bounced,replies
2026-08-01,A,100,2,5
2026-08-02,A,,3,6
"""
    )
    df, report = parse_and_validate(data)
    assert report.valid_rows == 1
    assert any(e.code == "non_numeric" and e.column == "sent" for e in report.errors)


def test_garbage_optional_value_warns_and_kept_as_missing():
    data = _csv(
        """
date,campaign_name,sent,bounced,replies,clicks
2026-08-01,A,100,2,5,abc
2026-08-02,A,120,3,6,10
"""
    )
    df, report = parse_and_validate(data)
    assert report.valid_rows == 2
    assert any(w.code == "optional_non_numeric" for w in report.warnings)


def test_counts_exceed_sent_warns_but_keeps_row():
    data = _csv("date,campaign_name,sent,bounced,replies\n2026-08-01,A,10,8,5")
    df, report = parse_and_validate(data)
    assert report.valid_rows == 1
    assert any(w.code == "counts_exceed_sent" for w in report.warnings)
