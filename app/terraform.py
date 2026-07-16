from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any

from .config import settings


def generate_patch(resource: dict[str, Any], recommendation: dict[str, Any]) -> str:
    return generate_terraform_change(resource, recommendation)["patch"]


def generate_terraform_change(resource: dict[str, Any], recommendation: dict[str, Any]) -> dict[str, str]:
    source_path = settings.terraform_path
    before_text = source_path.read_text(encoding="utf-8")
    return generate_terraform_change_from_text(
        before_text,
        source_label=str(source_path),
        resource=resource,
        recommendation=recommendation,
    )


def generate_terraform_change_from_text(
    before_text: str,
    *,
    source_label: str,
    resource: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, str]:
    before = before_text.splitlines(keepends=True)
    after_text = apply_virtual_change(before_text, resource, recommendation)
    after = after_text.splitlines(keepends=True)
    patch = "".join(
        difflib.unified_diff(
            before,
            after,
            fromfile=source_label,
            tofile=f"{source_label} (proposed)",
        )
    )
    return {"patch": patch, "proposed_terraform": after_text}


def apply_virtual_change(terraform_text: str, resource: dict[str, Any], recommendation: dict[str, Any]) -> str:
    action = recommendation["action"]
    current = recommendation["current_config"]
    proposed = recommendation["proposed_config"]

    if action == "downsize_ec2":
        return _replace_attribute(
            terraform_text,
            resource["terraform_address"],
            "instance_type",
            current["instance_type"],
            proposed["instance_type"],
        )
    if action == "downsize_rds":
        return _replace_attribute(
            terraform_text,
            resource["terraform_address"],
            "instance_class",
            current["instance_class"],
            proposed["instance_class"],
        )
    if action in {"delete_load_balancer", "delete_ebs_volume"}:
        return _comment_resource_block(terraform_text, resource["terraform_address"], recommendation["title"])
    raise ValueError(f"Unsupported Terraform action: {action}")


def _replace_attribute(
    terraform_text: str,
    terraform_address: str,
    attr: str,
    old_value: str,
    new_value: str,
) -> str:
    block_start = _resource_block_header(terraform_address)
    lines = terraform_text.splitlines()
    output: list[str] = []
    in_block = False
    depth = 0
    replaced = False

    for line in lines:
        if block_start in line:
            in_block = True
            depth = 0
        if in_block:
            depth += line.count("{")
            depth -= line.count("}")
            pattern = rf'({re.escape(attr)}\s*=\s*)"{re.escape(old_value)}"'
            if re.search(pattern, line):
                line = re.sub(pattern, rf'\1"{new_value}"', line)
                replaced = True
            if depth == 0:
                in_block = False
        output.append(line)

    if not replaced:
        raise ValueError(f"Could not find {attr}={old_value} in {terraform_address}")
    return "\n".join(output) + "\n"


def _comment_resource_block(terraform_text: str, terraform_address: str, reason: str) -> str:
    block_start = _resource_block_header(terraform_address)
    lines = terraform_text.splitlines()
    output: list[str] = []
    in_block = False
    depth = 0
    commented = False

    for line in lines:
        if block_start in line:
            in_block = True
            depth = 0
            output.append(f"# FINOPS_AGENT_RECOMMENDATION: {reason}")
        if in_block:
            depth += line.count("{")
            depth -= line.count("}")
            output.append(f"# {line}")
            commented = True
            if depth == 0:
                in_block = False
            continue
        output.append(line)

    if not commented:
        raise ValueError(f"Could not find Terraform block {terraform_address}")
    return "\n".join(output) + "\n"


def _resource_block_header(terraform_address: str) -> str:
    resource_type, resource_name = terraform_address.split(".", 1)
    return f'resource "{resource_type}" "{resource_name}"'


def write_pr_artifact(
    recommendation: dict[str, Any],
    resource: dict[str, Any],
    patch: str,
    *,
    artifact_dir: Path | None = None,
) -> str:
    target_dir = artifact_dir or settings.pr_artifact_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{recommendation['id']}.md"
    path.write_text(build_pr_body(recommendation, resource, patch), encoding="utf-8")
    return f"local://{path}"


def build_pr_body(recommendation: dict[str, Any], resource: dict[str, Any], patch: str) -> str:
    return f"""# {recommendation['title']}

## Summary
{recommendation['rationale']}

## Estimated savings
${recommendation['savings_monthly']:.2f}/month

## Risk and policy
- Risk: {recommendation['risk_level']}
- Policy: {recommendation['policy_status']}

## Rollback
{recommendation['rollback_plan']}

## Resource
- ID: {resource['id']}
- Terraform address: `{resource['terraform_address']}`

## Proposed Terraform diff
```diff
{patch}
```
"""
