from __future__ import annotations

import os
from pathlib import Path

os.environ["FINOPS_DB_PATH"] = str(Path(__file__).resolve().parents[1] / "data" / "api_test.db")

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_demo_api_flow() -> None:
    reset = client.post("/demo/reset")
    assert reset.status_code == 200
    assert reset.json()["resources_loaded"] == 5

    scan = client.post("/scan")
    assert scan.status_code == 200
    scan_body = scan.json()
    assert scan_body["created_or_updated_recommendations"] == 4

    rec_id = scan_body["recommendation_ids"][0]
    pr = client.post(f"/recommendations/{rec_id}/open-pr")
    assert pr.status_code == 200
    assert pr.json()["status"] == "pr_opened"

    approve = client.post(
        f"/recommendations/{rec_id}/approve",
        json={"actor": "pytest", "reason": "safe demo recommendation"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    audit = client.get("/audit")
    assert audit.status_code == 200
    assert len(audit.json()) >= 3

