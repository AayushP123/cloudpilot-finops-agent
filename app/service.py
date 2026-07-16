from __future__ import annotations

from typing import Any

from .ai_reviewer import review_recommendation
from .config import settings
from .db import add_audit, connect, init_db
from .detectors import detect_resource
from .integrations.aws_live import fetch_live_resources
from .integrations.github import publish_remediation
from .policy import evaluate_policy
from .repository import (
    get_recommendation,
    get_resource,
    list_recommendations,
    list_resources,
    update_recommendation,
    upsert_resource,
    upsert_recommendation,
)
from .slack import notify_approval_channel


def ingest_resources(resources: list[dict[str, Any]], *, actor: str, source: str) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        for resource in resources:
            upsert_resource(conn, resource)
        add_audit(
            conn,
            actor=actor,
            action="resources_ingested",
            target_type="source",
            target_id=source,
            details={"resources_loaded": len(resources)},
        )
    return {"resources_loaded": len(resources), "source": source}


def ingest_live_aws() -> dict[str, Any]:
    resources = fetch_live_resources()
    return ingest_resources(resources, actor="aws-live-adapter", source="aws")


def scan_account(open_prs: bool = False, *, require_github: bool = False) -> dict[str, Any]:
    init_db()
    created_or_updated: list[str] = []
    opened_prs: list[str] = []
    with connect() as conn:
        resources = list_resources(conn)
        for resource in resources:
            candidates = detect_resource(resource)
            for candidate in candidates:
                policy = evaluate_policy(resource, candidate)
                review = review_recommendation(resource, candidate, policy)
                recommendation = {
                    **candidate,
                    "risk_level": policy["risk_level"],
                    "policy_status": policy["policy_status"],
                    "rationale": review["rationale"],
                    "rollback_plan": review["rollback_plan"],
                    "status": "open",
                    "terraform_patch": None,
                    "pr_url": None,
                    "slack_message": None,
                }
                upsert_recommendation(conn, recommendation)
                add_audit(
                    conn,
                    actor="agent",
                    action="recommendation_scored",
                    target_type="recommendation",
                    target_id=recommendation["id"],
                    details={
                        "resource_id": resource["id"],
                        "policy_status": recommendation["policy_status"],
                        "savings_monthly": recommendation["savings_monthly"],
                    },
                )
                created_or_updated.append(recommendation["id"])

    if open_prs:
        for rec_id in created_or_updated:
            rec = recommendations_by_ids([rec_id])[0]
            if rec["policy_status"] in {"allowed", "needs_review"}:
                try:
                    opened = open_pr(rec_id, actor="autopilot", require_github=require_github)
                    opened_prs.append(opened["pr_url"] or rec_id)
                except Exception:
                    continue

    recs = recommendations_by_ids(created_or_updated)
    return {
        "scanned_resources": len(resources),
        "created_or_updated_recommendations": len(created_or_updated),
        "estimated_monthly_savings": round(sum(rec["savings_monthly"] for rec in recs), 2),
        "recommendation_ids": created_or_updated,
        "opened_prs": opened_prs,
    }


def recommendations_by_ids(ids: list[str]) -> list[dict[str, Any]]:
    with connect() as conn:
        return [rec for rec_id in ids if (rec := get_recommendation(conn, rec_id))]


def open_pr(rec_id: str, actor: str = "agent", *, require_github: bool = False) -> dict[str, Any]:
    with connect() as conn:
        recommendation = get_recommendation(conn, rec_id)
        if recommendation is None:
            raise KeyError(rec_id)
        resource = get_resource(conn, recommendation["resource_id"])
        if resource is None:
            raise KeyError(recommendation["resource_id"])
        if recommendation["policy_status"] == "blocked":
            raise ValueError("Blocked recommendations cannot open PRs")
        publication = publish_remediation(
            recommendation,
            resource,
            require_github=require_github,
        )
        patch = publication["terraform_patch"]
        pr_url = publication["pr_url"]
        try:
            slack_message = notify_approval_channel({**recommendation, "terraform_patch": patch, "pr_url": pr_url})
        except Exception as exc:
            slack_message = f"slack_error:{exc.__class__.__name__}:{exc}"
        return update_recommendation(
            conn,
            rec_id,
            actor=actor,
            action="pr_opened",
            status="pr_opened",
            fields={"terraform_patch": patch, "pr_url": pr_url, "slack_message": slack_message},
            audit_details={"pr_url": pr_url, "publisher": publication["publisher"], "slack_message": slack_message},
        )


def live_autopilot(open_prs: bool = True, *, require_github: bool | None = None) -> dict[str, Any]:
    """Ingest live AWS data, score recommendations, and optionally open GitHub PRs."""

    ingest_result = ingest_live_aws()
    scan_result = scan_account(
        open_prs=open_prs,
        require_github=settings.require_github_for_live if require_github is None else require_github,
    )
    return {
        **scan_result,
        "ingested_resources": ingest_result["resources_loaded"],
        "source": ingest_result["source"],
    }


def approve_recommendation(rec_id: str, *, actor: str, reason: str | None = None) -> dict[str, Any]:
    with connect() as conn:
        if get_recommendation(conn, rec_id) is None:
            raise KeyError(rec_id)
        return update_recommendation(
            conn,
            rec_id,
            actor=actor,
            action="approved",
            status="approved",
            audit_details={"reason": reason},
        )


def reject_recommendation(rec_id: str, *, actor: str, reason: str | None = None) -> dict[str, Any]:
    with connect() as conn:
        if get_recommendation(conn, rec_id) is None:
            raise KeyError(rec_id)
        return update_recommendation(
            conn,
            rec_id,
            actor=actor,
            action="rejected",
            status="rejected",
            audit_details={"reason": reason},
        )


def realize_recommendation(
    rec_id: str,
    *,
    actor: str,
    realized_monthly_savings: float | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        recommendation = get_recommendation(conn, rec_id)
        if recommendation is None:
            raise KeyError(rec_id)
        return update_recommendation(
            conn,
            rec_id,
            actor=actor,
            action="realized",
            status="realized",
            audit_details={
                "realized_monthly_savings": realized_monthly_savings
                if realized_monthly_savings is not None
                else recommendation["savings_monthly"]
            },
        )


def summary() -> dict[str, Any]:
    with connect() as conn:
        resources = list_resources(conn)
        recs = list_recommendations(conn)
    by_status = {status: len([rec for rec in recs if rec["status"] == status]) for status in {
        "open",
        "pr_opened",
        "approved",
        "rejected",
        "realized",
    }}
    return {
        "resources": len(resources),
        "recommendations": len(recs),
        "open_recommendations": by_status["open"],
        "pr_opened": by_status["pr_opened"],
        "approved": by_status["approved"],
        "rejected": by_status["rejected"],
        "realized": by_status["realized"],
        "estimated_open_monthly_savings": round(
            sum(rec["savings_monthly"] for rec in recs if rec["status"] in {"open", "pr_opened"}), 2
        ),
        "estimated_total_monthly_savings": round(sum(rec["savings_monthly"] for rec in recs), 2),
    }
