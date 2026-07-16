from __future__ import annotations

import json
from typing import Any

from .config import settings


def review_recommendation(
    resource: dict[str, Any],
    candidate: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, str]:
    """Review a recommendation with an LLM when configured, else local logic.

    The final agent should be demonstrable without paid APIs, so OpenAI is an
    opt-in adapter controlled by OPENAI_API_KEY. If the LLM request fails, the
    deterministic reviewer keeps the remediation pipeline moving.
    """
    if settings.openai_api_key:
        try:
            return _review_with_openai(resource, candidate, policy)
        except Exception as exc:
            local = _review_locally(resource, candidate, policy)
            local["rationale"] += f" LLM fallback note: OpenAI review failed locally with {exc.__class__.__name__}."
            return local

    return _review_locally(resource, candidate, policy)


def _review_with_openai(
    resource: dict[str, Any],
    candidate: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, str]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    payload = {
        "resource": resource,
        "recommendation_candidate": candidate,
        "policy": policy,
    }
    response = client.responses.create(
        model=settings.openai_model,
        instructions=(
            "You are a senior infrastructure reliability engineer reviewing a cloud FinOps "
            "recommendation. Return strict JSON with keys rationale and rollback_plan. "
            "Be concrete, mention evidence, avoid hype, and never claim a change was applied."
        ),
        input=json.dumps(payload, sort_keys=True),
    )
    text = response.output_text
    parsed = json.loads(text)
    return {
        "rationale": str(parsed["rationale"]),
        "rollback_plan": str(parsed["rollback_plan"]),
    }


def _review_locally(
    resource: dict[str, Any],
    candidate: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, str]:
    savings = candidate["savings_monthly"]
    action = candidate["action"].replace("_", " ")
    evidence = candidate["evidence"]
    policy_text = " ".join(policy["reasons"])

    rationale = (
        f"{resource['name']} is a {resource['type']} candidate for {action} because recent "
        f"telemetry shows low utilization relative to ${resource['monthly_cost']:.2f}/month spend. "
        f"The recommendation is expected to save about ${savings:.2f}/month. "
        f"Key evidence: {format_evidence(evidence)}. Policy result: {policy_text}"
    )

    rollback = (
        f"Revert the generated Terraform PR for {resource['terraform_address']} and re-apply the "
        "previous resource configuration. For destructive changes, restore from the named snapshot "
        "or keep the PR unmerged until the owner verifies the resource is unused."
    )

    return {"rationale": rationale, "rollback_plan": rollback}


def format_evidence(evidence: dict[str, Any]) -> str:
    parts = []
    for key, value in evidence.items():
        label = key.replace("_", " ")
        if isinstance(value, float):
            parts.append(f"{label}={value:.2f}")
        else:
            parts.append(f"{label}={value}")
    return ", ".join(parts)
