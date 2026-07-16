from __future__ import annotations

import os
from pathlib import Path

os.environ["FINOPS_DB_PATH"] = str(Path(__file__).resolve().parents[1] / "data" / "test.db")

from app.demo_loader import reset_demo_data
from app.service import open_pr, scan_account, summary


def test_scan_creates_recommendations() -> None:
    reset_demo_data()
    result = scan_account()
    assert result["scanned_resources"] == 5
    assert result["created_or_updated_recommendations"] == 4
    assert result["estimated_monthly_savings"] > 500
    assert len(result["recommendation_ids"]) == 4


def test_open_pr_creates_patch_artifact() -> None:
    reset_demo_data()
    result = scan_account()
    rec = open_pr(result["recommendation_ids"][0], actor="pytest")
    assert rec["status"] == "pr_opened"
    assert rec["pr_url"] is not None
    assert rec["terraform_patch"] is not None
    assert "---" in rec["terraform_patch"]
    assert "+++" in rec["terraform_patch"]


def test_summary_tracks_recommendations() -> None:
    reset_demo_data()
    scan_account()
    result = summary()
    assert result["resources"] == 5
    assert result["recommendations"] == 4
    assert result["estimated_total_monthly_savings"] > 500

