from __future__ import annotations

import json
from pathlib import Path

from .config import settings
from .db import add_audit, connect, init_db, reset_db
from .repository import upsert_resource


def load_demo_resources(path: Path | None = None) -> list[dict]:
    source = path or settings.demo_resources_path
    with source.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def reset_demo_data() -> dict[str, int]:
    init_db()
    resources = load_demo_resources()
    reset_db()
    with connect() as conn:
        for resource in resources:
            upsert_resource(conn, resource)
        add_audit(
            conn,
            actor="system",
            action="demo_reset",
            target_type="account",
            target_id="demo-aws",
            details={"resources_loaded": len(resources)},
        )
    return {"resources_loaded": len(resources)}

