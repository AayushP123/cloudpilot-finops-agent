from __future__ import annotations

import sqlite3
from typing import Any

from .db import add_audit, dumps, now_iso, row_to_audit, row_to_recommendation, row_to_resource


def upsert_resource(conn: sqlite3.Connection, resource: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO resources(
            id, account_id, type, name, region, terraform_address, monthly_cost,
            tags, metrics, config, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            account_id = excluded.account_id,
            type = excluded.type,
            name = excluded.name,
            region = excluded.region,
            terraform_address = excluded.terraform_address,
            monthly_cost = excluded.monthly_cost,
            tags = excluded.tags,
            metrics = excluded.metrics,
            config = excluded.config,
            updated_at = excluded.updated_at
        """,
        (
            resource["id"],
            resource["account_id"],
            resource["type"],
            resource["name"],
            resource["region"],
            resource["terraform_address"],
            resource["monthly_cost"],
            dumps(resource.get("tags", {})),
            dumps(resource.get("metrics", {})),
            dumps(resource.get("config", {})),
            now_iso(),
        ),
    )


def list_resources(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM resources ORDER BY monthly_cost DESC").fetchall()
    return [row_to_resource(row) for row in rows]


def get_resource(conn: sqlite3.Connection, resource_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
    return row_to_resource(row) if row else None


def upsert_recommendation(conn: sqlite3.Connection, recommendation: dict[str, Any]) -> None:
    existing = conn.execute(
        "SELECT status, pr_url, terraform_patch, slack_message, created_at FROM recommendations WHERE id = ?",
        (recommendation["id"],),
    ).fetchone()
    created_at = existing["created_at"] if existing else now_iso()
    status = existing["status"] if existing and existing["status"] != "open" else recommendation["status"]
    pr_url = existing["pr_url"] if existing and existing["pr_url"] else recommendation.get("pr_url")
    terraform_patch = (
        existing["terraform_patch"]
        if existing and existing["terraform_patch"]
        else recommendation.get("terraform_patch")
    )
    slack_message = (
        existing["slack_message"]
        if existing and existing["slack_message"]
        else recommendation.get("slack_message")
    )
    conn.execute(
        """
        INSERT INTO recommendations(
            id, resource_id, account_id, resource_type, title, action, current_config,
            proposed_config, savings_monthly, risk_level, confidence, evidence,
            rationale, rollback_plan, policy_status, status, terraform_patch, pr_url,
            slack_message, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            current_config = excluded.current_config,
            proposed_config = excluded.proposed_config,
            savings_monthly = excluded.savings_monthly,
            risk_level = excluded.risk_level,
            confidence = excluded.confidence,
            evidence = excluded.evidence,
            rationale = excluded.rationale,
            rollback_plan = excluded.rollback_plan,
            policy_status = excluded.policy_status,
            status = excluded.status,
            terraform_patch = excluded.terraform_patch,
            pr_url = excluded.pr_url,
            slack_message = excluded.slack_message,
            updated_at = excluded.updated_at
        """,
        (
            recommendation["id"],
            recommendation["resource_id"],
            recommendation["account_id"],
            recommendation["resource_type"],
            recommendation["title"],
            recommendation["action"],
            dumps(recommendation["current_config"]),
            dumps(recommendation["proposed_config"]),
            recommendation["savings_monthly"],
            recommendation["risk_level"],
            recommendation["confidence"],
            dumps(recommendation["evidence"]),
            recommendation["rationale"],
            recommendation["rollback_plan"],
            recommendation["policy_status"],
            status,
            terraform_patch,
            pr_url,
            slack_message,
            created_at,
            now_iso(),
        ),
    )


def list_recommendations(conn: sqlite3.Connection, status: str | None = None) -> list[dict[str, Any]]:
    if status:
        rows = conn.execute(
            "SELECT * FROM recommendations WHERE status = ? ORDER BY savings_monthly DESC",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM recommendations ORDER BY savings_monthly DESC").fetchall()
    return [row_to_recommendation(row) for row in rows]


def get_recommendation(conn: sqlite3.Connection, rec_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,)).fetchone()
    return row_to_recommendation(row) if row else None


def update_recommendation(
    conn: sqlite3.Connection,
    rec_id: str,
    *,
    actor: str,
    action: str,
    status: str | None = None,
    fields: dict[str, Any] | None = None,
    audit_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updates = fields.copy() if fields else {}
    if status:
        updates["status"] = status
    updates["updated_at"] = now_iso()
    if not updates:
        raise ValueError("No fields provided")
    set_sql = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values())
    values.append(rec_id)
    conn.execute(f"UPDATE recommendations SET {set_sql} WHERE id = ?", values)
    add_audit(
        conn,
        actor=actor,
        action=action,
        target_type="recommendation",
        target_id=rec_id,
        details=audit_details or {},
    )
    updated = get_recommendation(conn, rec_id)
    if updated is None:
        raise KeyError(rec_id)
    return updated


def list_audits(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM audits ORDER BY id DESC").fetchall()
    return [row_to_audit(row) for row in rows]

