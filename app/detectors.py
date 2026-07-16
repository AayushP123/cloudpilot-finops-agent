from __future__ import annotations

import hashlib
from typing import Any


INSTANCE_RIGHTSIZES = {
    "m5.2xlarge": ("m5.large", 0.25),
    "m5.xlarge": ("m5.large", 0.50),
    "c5.xlarge": ("c5.large", 0.50),
    "t3.xlarge": ("t3.medium", 0.30),
}

RDS_RIGHTSIZES = {
    "db.m6g.2xlarge": ("db.m6g.large", 0.35),
    "db.m5.xlarge": ("db.m5.large", 0.50),
}


def rec_id(resource_id: str, action: str) -> str:
    digest = hashlib.sha1(f"{resource_id}:{action}".encode("utf-8")).hexdigest()[:10]
    return f"rec_{digest}"


def detect_resource(resource: dict[str, Any]) -> list[dict[str, Any]]:
    resource_type = resource["type"]
    if resource_type == "ec2":
        return _detect_ec2(resource)
    if resource_type == "rds":
        return _detect_rds(resource)
    if resource_type == "load_balancer":
        return _detect_load_balancer(resource)
    if resource_type == "ebs_volume":
        return _detect_ebs(resource)
    return []


def _detect_ec2(resource: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = resource["metrics"]
    config = resource["config"]
    instance_type = config["instance_type"]
    avg_cpu = metrics.get("avg_cpu_14d_pct", 0)
    peak_cpu = metrics.get("peak_cpu_14d_pct", 0)
    network = metrics.get("avg_network_mbps", 0)
    if instance_type not in INSTANCE_RIGHTSIZES:
        return []
    if avg_cpu >= 12 or peak_cpu >= 55 or network >= 25:
        return []

    proposed_type, cost_factor = INSTANCE_RIGHTSIZES[instance_type]
    proposed_cost = round(resource["monthly_cost"] * cost_factor, 2)
    savings = round(resource["monthly_cost"] - proposed_cost, 2)
    return [
        {
            "id": rec_id(resource["id"], "downsize_ec2"),
            "resource_id": resource["id"],
            "account_id": resource["account_id"],
            "resource_type": resource["type"],
            "title": f"Downsize {resource['name']} from {instance_type} to {proposed_type}",
            "action": "downsize_ec2",
            "current_config": {"instance_type": instance_type},
            "proposed_config": {"instance_type": proposed_type},
            "savings_monthly": savings,
            "confidence": 0.88,
            "evidence": {
                "avg_cpu_14d_pct": avg_cpu,
                "peak_cpu_14d_pct": peak_cpu,
                "avg_network_mbps": network,
                "current_monthly_cost": resource["monthly_cost"],
                "estimated_monthly_cost_after": proposed_cost,
            },
            "risk_level": "low",
            "is_destructive": False,
        }
    ]


def _detect_rds(resource: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = resource["metrics"]
    config = resource["config"]
    instance_class = config["instance_class"]
    avg_cpu = metrics.get("avg_cpu_14d_pct", 0)
    peak_cpu = metrics.get("peak_cpu_14d_pct", 0)
    connections = metrics.get("avg_connections", 0)
    if instance_class not in RDS_RIGHTSIZES:
        return []
    if avg_cpu >= 16 or peak_cpu >= 60 or connections >= 50:
        return []

    proposed_class, cost_factor = RDS_RIGHTSIZES[instance_class]
    proposed_cost = round(resource["monthly_cost"] * cost_factor, 2)
    savings = round(resource["monthly_cost"] - proposed_cost, 2)
    return [
        {
            "id": rec_id(resource["id"], "downsize_rds"),
            "resource_id": resource["id"],
            "account_id": resource["account_id"],
            "resource_type": resource["type"],
            "title": f"Downsize {resource['name']} from {instance_class} to {proposed_class}",
            "action": "downsize_rds",
            "current_config": {"instance_class": instance_class},
            "proposed_config": {"instance_class": proposed_class},
            "savings_monthly": savings,
            "confidence": 0.82,
            "evidence": {
                "avg_cpu_14d_pct": avg_cpu,
                "peak_cpu_14d_pct": peak_cpu,
                "avg_connections": connections,
                "current_monthly_cost": resource["monthly_cost"],
                "estimated_monthly_cost_after": proposed_cost,
            },
            "risk_level": "low",
            "is_destructive": False,
        }
    ]


def _detect_load_balancer(resource: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = resource["metrics"]
    requests = metrics.get("requests_14d", 0)
    healthy_hosts = metrics.get("healthy_hosts", 0)
    if requests > 100 or healthy_hosts > 0:
        return []
    savings = round(resource["monthly_cost"], 2)
    return [
        {
            "id": rec_id(resource["id"], "delete_load_balancer"),
            "resource_id": resource["id"],
            "account_id": resource["account_id"],
            "resource_type": resource["type"],
            "title": f"Remove idle load balancer {resource['name']}",
            "action": "delete_load_balancer",
            "current_config": {"enabled": True},
            "proposed_config": {"enabled": False},
            "savings_monthly": savings,
            "confidence": 0.76,
            "evidence": {
                "requests_14d": requests,
                "healthy_hosts": healthy_hosts,
                "current_monthly_cost": resource["monthly_cost"],
            },
            "risk_level": "medium",
            "is_destructive": True,
        }
    ]


def _detect_ebs(resource: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = resource["metrics"]
    config = resource["config"]
    if metrics.get("attached", True):
        return []
    age_days = metrics.get("age_days", 0)
    if age_days < 14:
        return []
    savings = round(resource["monthly_cost"], 2)
    return [
        {
            "id": rec_id(resource["id"], "delete_ebs_volume"),
            "resource_id": resource["id"],
            "account_id": resource["account_id"],
            "resource_type": resource["type"],
            "title": f"Snapshot and delete unattached EBS volume {resource['name']}",
            "action": "delete_ebs_volume",
            "current_config": {"size_gb": config["size_gb"], "enabled": True},
            "proposed_config": {"snapshot_before_delete": True, "enabled": False},
            "savings_monthly": savings,
            "confidence": 0.91,
            "evidence": {
                "attached": False,
                "age_days": age_days,
                "size_gb": config["size_gb"],
                "current_monthly_cost": resource["monthly_cost"],
            },
            "risk_level": "medium",
            "is_destructive": True,
        }
    ]

