"""End-to-end API tests via FastAPI TestClient."""

import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


GOOD_CSV = (
    "date,campaign_name,sent,bounced,replies,delivered\n"
    "2026-08-01,Alpha,300,3,15,297\n"
    "2026-08-02,Alpha,300,3,15,297\n"
    "2026-08-03,Alpha,300,45,4,255\n"
    "2026-08-04,Alpha,300,45,4,255\n"
)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_demo_flow():
    r = client.post("/api/demo")
    assert r.status_code == 200
    body = r.json()
    did = body["dataset_id"]
    assert did
    assert body["summary"]["total_sent"] > 0

    # Summary carries findings count after lazy analysis.
    s = client.get(f"/api/datasets/{did}/summary")
    assert s.status_code == 200
    assert s.json()["num_findings"] >= 1

    # Campaigns + trend.
    c = client.get(f"/api/datasets/{did}/campaigns")
    assert c.status_code == 200
    assert len(c.json()["campaigns"]) == 4
    assert len(c.json()["trend"]) > 0


def test_upload_and_analyze():
    files = {"file": ("data.csv", io.BytesIO(GOOD_CSV.encode()), "text/csv")}
    r = client.post("/api/upload", files=files)
    assert r.status_code == 200
    did = r.json()["dataset_id"]
    assert did

    a = client.post(f"/api/datasets/{did}/analyze")
    assert a.status_code == 200
    findings = a.json()["findings"]
    assert len(findings) >= 1
    assert "elevated_bounce_rate" in a.json()["thresholds"]


def test_findings_filter_and_status_update():
    files = {"file": ("data.csv", io.BytesIO(GOOD_CSV.encode()), "text/csv")}
    did = client.post("/api/upload", files=files).json()["dataset_id"]
    client.post(f"/api/datasets/{did}/analyze")

    all_findings = client.get(f"/api/datasets/{did}/findings").json()["findings"]
    assert all_findings

    high = client.get(f"/api/datasets/{did}/findings?severity=high").json()["findings"]
    assert all(f["severity"] == "high" for f in high)

    fid = all_findings[0]["id"]
    patched = client.patch(f"/api/datasets/{did}/findings/{fid}?status=Investigating")
    assert patched.status_code == 200
    assert patched.json()["status"] == "Investigating"

    investigating = client.get(f"/api/datasets/{did}/findings?status=Investigating").json()["findings"]
    assert any(f["id"] == fid for f in investigating)


def test_upload_invalid_returns_report_without_dataset():
    bad = "campaign_name,sent\nAlpha,100\n"  # missing required columns
    files = {"file": ("bad.csv", io.BytesIO(bad.encode()), "text/csv")}
    r = client.post("/api/upload", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["dataset_id"] == ""
    assert body["validation"]["ok"] is False


def test_report_formats():
    did = client.post("/api/demo").json()["dataset_id"]
    assert client.get(f"/api/datasets/{did}/report").status_code == 200
    assert client.get(f"/api/datasets/{did}/report?format=summary_csv").status_code == 200
    assert client.get(f"/api/datasets/{did}/report?format=findings_csv").status_code == 200


def test_unknown_dataset_404():
    assert client.get("/api/datasets/nope/summary").status_code == 404


def test_threshold_config_endpoint():
    r = client.get("/api/config/thresholds")
    assert r.status_code == 200
    body = r.json()
    assert body["defaults"]["elevated_bounce_rate"] == 0.05
    assert "elevated_bounce_rate" in body["meta"]


def test_analyze_with_custom_thresholds_persists():
    did = client.post("/api/demo").json()["dataset_id"]
    default = client.post(f"/api/datasets/{did}/analyze").json()
    tuned = client.post(
        f"/api/datasets/{did}/analyze",
        json={"thresholds": {"elevated_bounce_rate": 0.02}},
    ).json()
    # A stricter bounce threshold should never yield fewer findings.
    assert len(tuned["findings"]) >= len(default["findings"])
    assert tuned["thresholds"]["elevated_bounce_rate"] == 0.02
    # The applied thresholds persist for subsequent reads.
    later = client.get(f"/api/datasets/{did}/findings").json()
    assert later["thresholds"]["elevated_bounce_rate"] == 0.02


def test_analyze_rejects_out_of_range_threshold():
    did = client.post("/api/demo").json()["dataset_id"]
    r = client.post(
        f"/api/datasets/{did}/analyze",
        json={"thresholds": {"elevated_bounce_rate": 1.5}},  # > 1.0
    )
    assert r.status_code == 422


def test_upload_rejects_non_csv_type():
    files = {"file": ("data.txt", io.BytesIO(b"not,a,csv"), "application/pdf")}
    r = client.post("/api/upload", files=files)
    assert r.status_code == 415


def test_upload_rejects_oversized_file():
    # Exceed the configured cap; must be rejected without processing.
    from app.config import MAX_UPLOAD_BYTES

    header = b"date,campaign_name,sent,bounced,replies\n"
    row = b"2026-08-01,A,1,0,0\n"  # 19 bytes
    big = header + row * ((MAX_UPLOAD_BYTES // len(row)) + 1000)
    assert len(big) > MAX_UPLOAD_BYTES
    files = {"file": ("big.csv", io.BytesIO(big), "text/csv")}
    r = client.post("/api/upload", files=files)
    assert r.status_code == 413
