from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import settings


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def loads(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


class DatabaseConnection:
    def __init__(self, raw: Any, backend: str) -> None:
        self.raw = raw
        self.backend = backend

    def execute(self, sql: str, params: Any = ()) -> Any:
        if self.backend == "postgres":
            sql = _postgres_placeholders(sql)
        return self.raw.execute(sql, params)

    def executescript(self, sql: str) -> None:
        statements = [statement.strip() for statement in sql.split(";") if statement.strip()]
        for statement in statements:
            self.execute(statement)

    def commit(self) -> None:
        self.raw.commit()

    def close(self) -> None:
        self.raw.close()


def _postgres_placeholders(sql: str) -> str:
    return sql.replace("?", "%s")


@contextmanager
def connect() -> Iterator[DatabaseConnection]:
    if settings.database_backend == "postgres":
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("Install psycopg or unset FINOPS_DATABASE_URL to use SQLite.") from exc
        raw = psycopg.connect(settings.database_url, row_factory=dict_row)
        conn = DatabaseConnection(raw, "postgres")
    else:
        ensure_parent(settings.database_path)
        raw = sqlite3.connect(settings.database_path)
        raw.row_factory = sqlite3.Row
        conn = DatabaseConnection(raw, "sqlite")
    try:
        if conn.backend == "sqlite":
            conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        if settings.database_backend == "postgres":
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS resources (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    region TEXT NOT NULL,
                    terraform_address TEXT NOT NULL,
                    monthly_cost DOUBLE PRECISION NOT NULL,
                    tags TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    config TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS recommendations (
                    id TEXT PRIMARY KEY,
                    resource_id TEXT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
                    account_id TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    action TEXT NOT NULL,
                    current_config TEXT NOT NULL,
                    proposed_config TEXT NOT NULL,
                    savings_monthly DOUBLE PRECISION NOT NULL,
                    risk_level TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    evidence TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    rollback_plan TEXT NOT NULL,
                    policy_status TEXT NOT NULL,
                    status TEXT NOT NULL,
                    terraform_patch TEXT,
                    pr_url TEXT,
                    slack_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audits (
                    id BIGSERIAL PRIMARY KEY,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            return
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS resources (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                region TEXT NOT NULL,
                terraform_address TEXT NOT NULL,
                monthly_cost REAL NOT NULL,
                tags TEXT NOT NULL,
                metrics TEXT NOT NULL,
                config TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id TEXT PRIMARY KEY,
                resource_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                title TEXT NOT NULL,
                action TEXT NOT NULL,
                current_config TEXT NOT NULL,
                proposed_config TEXT NOT NULL,
                savings_monthly REAL NOT NULL,
                risk_level TEXT NOT NULL,
                confidence REAL NOT NULL,
                evidence TEXT NOT NULL,
                rationale TEXT NOT NULL,
                rollback_plan TEXT NOT NULL,
                policy_status TEXT NOT NULL,
                status TEXT NOT NULL,
                terraform_patch TEXT,
                pr_url TEXT,
                slack_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def reset_db() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM audits")
        conn.execute("DELETE FROM recommendations")
        conn.execute("DELETE FROM resources")


def add_audit(
    conn: sqlite3.Connection,
    *,
    actor: str,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO audits(actor, action, target_type, target_id, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (actor, action, target_type, target_id, dumps(details or {}), now_iso()),
    )


def row_to_resource(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "type": row["type"],
        "name": row["name"],
        "region": row["region"],
        "terraform_address": row["terraform_address"],
        "monthly_cost": row["monthly_cost"],
        "tags": loads(row["tags"], {}),
        "metrics": loads(row["metrics"], {}),
        "config": loads(row["config"], {}),
        "updated_at": row["updated_at"],
    }


def row_to_recommendation(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "resource_id": row["resource_id"],
        "account_id": row["account_id"],
        "resource_type": row["resource_type"],
        "title": row["title"],
        "action": row["action"],
        "current_config": loads(row["current_config"], {}),
        "proposed_config": loads(row["proposed_config"], {}),
        "savings_monthly": row["savings_monthly"],
        "risk_level": row["risk_level"],
        "confidence": row["confidence"],
        "evidence": loads(row["evidence"], {}),
        "rationale": row["rationale"],
        "rollback_plan": row["rollback_plan"],
        "policy_status": row["policy_status"],
        "status": row["status"],
        "terraform_patch": row["terraform_patch"],
        "pr_url": row["pr_url"],
        "slack_message": row["slack_message"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def row_to_audit(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "actor": row["actor"],
        "action": row["action"],
        "target_type": row["target_type"],
        "target_id": row["target_id"],
        "details": loads(row["details"], {}),
        "created_at": row["created_at"],
    }
