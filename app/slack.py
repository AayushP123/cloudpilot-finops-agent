from __future__ import annotations

from typing import Any

import httpx

from .config import settings


def build_approval_message(recommendation: dict[str, Any]) -> str:
    return (
        f"[{settings.slack_channel}] FinOps recommendation {recommendation['id']}: "
        f"{recommendation['title']} | savings=${recommendation['savings_monthly']:.2f}/mo | "
        f"risk={recommendation['risk_level']} | policy={recommendation['policy_status']} | "
        f"approve via POST /recommendations/{recommendation['id']}/approve"
    )


def notify_approval_channel(recommendation: dict[str, Any]) -> str:
    message = build_approval_message(recommendation)
    if not settings.slack_webhook_url:
        return message

    response = httpx.post(
        settings.slack_webhook_url,
        json={"text": message},
        timeout=10,
    )
    response.raise_for_status()
    return f"sent:{settings.slack_channel}:{recommendation['id']}"
