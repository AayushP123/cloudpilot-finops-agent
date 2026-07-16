from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from ..config import settings
from ..terraform import build_pr_body, generate_terraform_change, generate_terraform_change_from_text, write_pr_artifact


def github_is_configured() -> bool:
    return bool(settings.github_token and settings.github_repo)


def publish_remediation(
    recommendation: dict[str, Any],
    resource: dict[str, Any],
    *,
    require_github: bool = False,
) -> dict[str, str]:
    """Publish a recommendation as a GitHub PR or local PR artifact.

    In GitHub mode, the Terraform file is fetched from the configured repository
    and branch before the change is generated. That makes live PRs modify the
    actual infra file instead of blindly uploading the local demo fixture.
    """

    if not github_is_configured() and require_github:
        raise ValueError("GitHub is required but FINOPS_GITHUB_TOKEN or FINOPS_GITHUB_REPO is missing")
    if not github_is_configured():
        change = generate_terraform_change(resource, recommendation)
        return {
            "publisher": "local",
            "pr_url": write_pr_artifact(recommendation, resource, change["patch"]),
            "terraform_patch": change["patch"],
        }

    owner_repo = settings.github_repo
    if not owner_repo or "/" not in owner_repo:
        raise ValueError("FINOPS_GITHUB_REPO must look like owner/repo")

    branch = f"{settings.github_branch_prefix}/{recommendation['id']}-{int(time.time())}"
    api = "https://api.github.com"
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client(timeout=30, headers=headers) as client:
        source = _fetch_repo_file(client, api, owner_repo)
        change = generate_terraform_change_from_text(
            source["text"],
            source_label=f"github://{owner_repo}/{settings.terraform_repo_path}@{settings.github_base_branch}",
            resource=resource,
            recommendation=recommendation,
        )
        base_ref = client.get(f"{api}/repos/{owner_repo}/git/ref/heads/{settings.github_base_branch}")
        base_ref.raise_for_status()
        base_sha = base_ref.json()["object"]["sha"]

        created_ref = client.post(
            f"{api}/repos/{owner_repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
        )
        created_ref.raise_for_status()

        content_url = f"{api}/repos/{owner_repo}/contents/{settings.terraform_repo_path}"
        payload = {
            "message": f"{recommendation['title']} ({recommendation['id']})",
            "content": base64.b64encode(change["proposed_terraform"].encode("utf-8")).decode("ascii"),
            "branch": branch,
            "sha": source["sha"],
        }
        updated = client.put(content_url, json=payload)
        updated.raise_for_status()

        pr = client.post(
            f"{api}/repos/{owner_repo}/pulls",
            json={
                "title": recommendation["title"],
                "head": branch,
                "base": settings.github_base_branch,
                "body": build_pr_body(recommendation, resource, change["patch"]),
                "draft": settings.github_draft_pr,
            },
        )
        pr.raise_for_status()
        return {
            "publisher": "github",
            "pr_url": pr.json()["html_url"],
            "terraform_patch": change["patch"],
        }


def _fetch_repo_file(client: httpx.Client, api: str, owner_repo: str) -> dict[str, str]:
    content_url = f"{api}/repos/{owner_repo}/contents/{settings.terraform_repo_path}"
    current = client.get(content_url, params={"ref": settings.github_base_branch})
    current.raise_for_status()
    body = current.json()
    if body.get("type") != "file" or not body.get("content"):
        raise ValueError(f"{settings.terraform_repo_path} is not a readable file in {owner_repo}")
    encoded = body["content"].replace("\n", "")
    return {
        "sha": body["sha"],
        "text": base64.b64decode(encoded).decode("utf-8"),
    }


def publish_pull_request(
    recommendation: dict[str, Any],
    resource: dict[str, Any],
    patch: str,
    proposed_terraform: str,
) -> str:
    """Backward-compatible wrapper for the older service path."""

    if not github_is_configured():
        return write_pr_artifact(recommendation, resource, patch)
    result = publish_remediation(recommendation, resource, require_github=True)
    return result["pr_url"]
