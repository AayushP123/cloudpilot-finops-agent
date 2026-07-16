from __future__ import annotations

from typing import Any


def evaluate_policy(resource: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    tags = resource.get("tags", {})
    metrics = resource.get("metrics", {})
    env = tags.get("env", "unknown").lower()
    action = candidate["action"]
    reasons: list[str] = []

    if env == "prod" and action in {"delete_load_balancer", "delete_ebs_volume"}:
        reasons.append("Destructive action against production infrastructure requires manual review.")

    if metrics.get("p95_latency_ms", 0) >= 250:
        reasons.append("Latency is already elevated, so downsizing could hurt reliability.")

    if metrics.get("error_rate_pct", 0) >= 1:
        reasons.append("Error rate is above the reliability guardrail.")

    if action.startswith("downsize") and metrics.get("avg_cpu_14d_pct", 0) >= 35:
        reasons.append("Average CPU is too high for automated right-sizing.")

    if action.startswith("downsize") and metrics.get("peak_cpu_14d_pct", 0) >= 70:
        reasons.append("Peak CPU is too high for automated right-sizing.")

    if candidate["savings_monthly"] < 10:
        reasons.append("Savings are too small to justify an infrastructure change.")

    if any("requires manual review" in reason for reason in reasons):
        status = "needs_review"
        risk = "medium"
    elif reasons:
        status = "blocked"
        risk = "high"
    elif candidate.get("is_destructive"):
        status = "needs_review"
        risk = "medium"
        reasons.append("Deletion recommendations are never auto-approved.")
    else:
        status = "allowed"
        risk = candidate.get("risk_level", "low")
        reasons.append("Utilization and reliability signals are within right-sizing guardrails.")

    return {
        "policy_status": status,
        "risk_level": risk,
        "reasons": reasons,
    }

