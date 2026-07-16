from __future__ import annotations

from typing import Any

import httpx

from .config import settings
from .db import init_db
from .integrations.github import github_is_configured


def run_doctor(*, live: bool = False) -> dict[str, Any]:
    checks = {
        "database": _check_database(),
        "terraform": _check_terraform(),
        "aws": _check_aws(live=live),
        "github": _check_github(live=live),
        "slack": _check_slack(),
        "openai": _check_openai(),
    }
    ready_for_live_prs = (
        checks["database"]["ok"]
        and checks["terraform"]["ok"]
        and checks["aws"]["configured"]
        and checks["github"]["configured"]
    )
    return {
        "ok": all(check["ok"] for check in checks.values() if check.get("required_for_local", False)),
        "ready_for_live_prs": ready_for_live_prs,
        "live_network_checks": live,
        "checks": checks,
    }


def _check_database() -> dict[str, Any]:
    try:
        init_db()
        return {
            "ok": True,
            "required_for_local": True,
            "backend": settings.database_backend,
            "message": "Database initialized.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "required_for_local": True,
            "backend": settings.database_backend,
            "message": f"{exc.__class__.__name__}: {exc}",
        }


def _check_terraform() -> dict[str, Any]:
    exists = settings.terraform_path.exists()
    return {
        "ok": exists,
        "required_for_local": True,
        "path": str(settings.terraform_path),
        "repo_path": settings.terraform_repo_path,
        "message": "Local Terraform fixture found." if exists else "Local Terraform file is missing.",
    }


def _check_aws(*, live: bool) -> dict[str, Any]:
    try:
        import boto3
    except ImportError as exc:
        return {
            "ok": False,
            "configured": False,
            "required_for_local": False,
            "message": f"boto3 unavailable: {exc}",
        }

    try:
        session_kwargs: dict[str, str] = {}
        if settings.aws_profile:
            session_kwargs["profile_name"] = settings.aws_profile
        session = boto3.Session(**session_kwargs)
        credentials = session.get_credentials()
        configured = credentials is not None
        result: dict[str, Any] = {
            "ok": True,
            "configured": configured,
            "required_for_local": False,
            "regions": settings.parsed_aws_regions,
            "profile_set": bool(settings.aws_profile),
            "message": "AWS credentials found." if configured else "AWS credentials not found.",
        }
        if live and configured:
            identity = session.client("sts").get_caller_identity()
            result["account"] = identity.get("Account")
            result["arn_type"] = _arn_type(identity.get("Arn", ""))
            result["message"] = "AWS STS identity verified."
        return result
    except Exception as exc:
        return {
            "ok": False,
            "configured": False,
            "required_for_local": False,
            "regions": settings.parsed_aws_regions,
            "message": f"{exc.__class__.__name__}: {exc}",
        }


def _check_github(*, live: bool) -> dict[str, Any]:
    configured = github_is_configured()
    result: dict[str, Any] = {
        "ok": True,
        "configured": configured,
        "required_for_local": False,
        "repo_set": bool(settings.github_repo),
        "token_set": bool(settings.github_token),
        "base_branch": settings.github_base_branch,
        "terraform_repo_path": settings.terraform_repo_path,
        "draft_prs": settings.github_draft_pr,
        "message": "GitHub configured." if configured else "GitHub token/repo not configured; local PR artifacts will be used.",
    }
    if not live or not configured:
        return result

    try:
        api = "https://api.github.com"
        headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        with httpx.Client(timeout=15, headers=headers) as client:
            repo = client.get(f"{api}/repos/{settings.github_repo}")
            repo.raise_for_status()
            content = client.get(
                f"{api}/repos/{settings.github_repo}/contents/{settings.terraform_repo_path}",
                params={"ref": settings.github_base_branch},
            )
            content.raise_for_status()
        result["message"] = "GitHub repo and Terraform file verified."
        result["private_repo"] = bool(repo.json().get("private"))
        return result
    except Exception as exc:
        return {
            **result,
            "ok": False,
            "message": f"{exc.__class__.__name__}: {exc}",
        }


def _check_slack() -> dict[str, Any]:
    configured = bool(settings.slack_webhook_url)
    return {
        "ok": True,
        "configured": configured,
        "required_for_local": False,
        "channel": settings.slack_channel,
        "message": "Slack webhook configured." if configured else "Slack webhook missing; approval messages stay local.",
    }


def _check_openai() -> dict[str, Any]:
    configured = bool(settings.openai_api_key)
    return {
        "ok": True,
        "configured": configured,
        "required_for_local": False,
        "model": settings.openai_model,
        "message": "OpenAI reviewer configured." if configured else "OpenAI key missing; deterministic reviewer will be used.",
    }


def _arn_type(arn: str) -> str:
    if ":assumed-role/" in arn:
        return "assumed-role"
    if ":user/" in arn:
        return "iam-user"
    if ":role/" in arn:
        return "iam-role"
    return "unknown"

