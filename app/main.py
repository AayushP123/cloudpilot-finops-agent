from __future__ import annotations

from contextlib import asynccontextmanager
from html import escape
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .config import settings
from .db import connect, init_db
from .demo_loader import reset_demo_data
from .doctor import run_doctor
from .integrations.github import github_is_configured
from .models import (
    ApprovalRequest,
    AutopilotRequest,
    IngestResponse,
    LiveAutopilotRequest,
    LiveAutopilotResponse,
    RealizeRequest,
    Recommendation,
    Resource,
    ScanResponse,
    Summary,
)
from .repository import get_recommendation, list_audits, list_recommendations, list_resources
from .service import (
    approve_recommendation,
    ingest_live_aws,
    live_autopilot,
    open_pr,
    realize_recommendation,
    reject_recommendation,
    scan_account,
    summary,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI FinOps Remediation Agent", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/demo/reset")
def demo_reset() -> dict[str, int]:
    return reset_demo_data()


@app.post("/ingest/aws", response_model=IngestResponse)
def ingest_aws() -> dict:
    try:
        return ingest_live_aws()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/scan", response_model=ScanResponse)
def scan() -> dict:
    return scan_account()


@app.post("/autopilot", response_model=ScanResponse)
def autopilot(request: AutopilotRequest) -> dict:
    return scan_account(open_prs=request.open_prs)


@app.post("/live/autopilot", response_model=LiveAutopilotResponse)
def autopilot_live(request: LiveAutopilotRequest) -> dict:
    try:
        return live_autopilot(open_prs=request.open_prs, require_github=request.require_github)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/config")
def config() -> dict[str, object]:
    return {
        "environment": settings.environment,
        "database_backend": settings.database_backend,
        "aws_regions": settings.parsed_aws_regions,
        "github_prs_enabled": github_is_configured(),
        "slack_webhook_enabled": bool(settings.slack_webhook_url),
        "openai_reviewer_enabled": bool(settings.openai_api_key),
        "terraform_path": str(settings.terraform_path),
        "terraform_repo_path": settings.terraform_repo_path,
    }


@app.get("/doctor")
def doctor(live: bool = False) -> dict[str, object]:
    return run_doctor(live=live)


@app.get("/resources", response_model=list[Resource])
def resources() -> list[dict]:
    with connect() as conn:
        return list_resources(conn)


@app.get("/recommendations", response_model=list[Recommendation])
def recommendations(status: Optional[str] = None) -> list[dict]:
    with connect() as conn:
        return list_recommendations(conn, status=status)


@app.get("/recommendations/{rec_id}", response_model=Recommendation)
def recommendation(rec_id: str) -> dict:
    with connect() as conn:
        rec = get_recommendation(conn, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@app.post("/recommendations/{rec_id}/open-pr", response_model=Recommendation)
def recommendation_open_pr(rec_id: str, require_github: bool = False) -> dict:
    try:
        return open_pr(rec_id, require_github=require_github)
    except KeyError:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/recommendations/{rec_id}/approve", response_model=Recommendation)
def recommendation_approve(rec_id: str, request: ApprovalRequest) -> dict:
    try:
        return approve_recommendation(rec_id, actor=request.actor, reason=request.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail="Recommendation not found")


@app.post("/recommendations/{rec_id}/reject", response_model=Recommendation)
def recommendation_reject(rec_id: str, request: ApprovalRequest) -> dict:
    try:
        return reject_recommendation(rec_id, actor=request.actor, reason=request.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail="Recommendation not found")


@app.post("/recommendations/{rec_id}/realize", response_model=Recommendation)
def recommendation_realize(rec_id: str, request: RealizeRequest) -> dict:
    try:
        return realize_recommendation(
            rec_id,
            actor=request.actor,
            realized_monthly_savings=request.realized_monthly_savings,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Recommendation not found")


@app.get("/audit")
def audit() -> list[dict]:
    with connect() as conn:
        return list_audits(conn)


@app.get("/summary", response_model=Summary)
def get_summary() -> dict:
    return summary()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    with connect() as conn:
        recs = list_recommendations(conn)
    rows = "\n".join(
        f"""
        <tr>
          <td>{escape(rec['id'])}</td>
          <td>{escape(rec['title'])}</td>
          <td>${rec['savings_monthly']:.2f}</td>
          <td>{escape(rec['risk_level'])}</td>
          <td>{escape(rec['policy_status'])}</td>
          <td>{escape(rec['status'])}</td>
          <td><a href="/recommendations/{escape(rec['id'])}">json</a></td>
        </tr>
        """
        for rec in recs
    )
    return f"""
    <!doctype html>
    <html>
    <head>
      <title>AI FinOps Remediation Agent</title>
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 40px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border-bottom: 1px solid #ddd; padding: 10px; text-align: left; }}
        code {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
      </style>
    </head>
    <body>
      <h1>AI FinOps Remediation Agent</h1>
      <p>Run <code>POST /demo/reset</code>, then <code>POST /autopilot</code> to scan and open local or GitHub PRs.</p>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Recommendation</th>
            <th>Savings</th>
            <th>Risk</th>
            <th>Policy</th>
            <th>Status</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </body>
    </html>
    """
