from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import settings


EC2_MONTHLY_ESTIMATES = {
    "t3.medium": 30.0,
    "t3.xlarge": 120.0,
    "m5.large": 70.0,
    "m5.xlarge": 140.0,
    "m5.2xlarge": 280.0,
    "c5.large": 62.0,
    "c5.xlarge": 124.0,
}

RDS_MONTHLY_ESTIMATES = {
    "db.m5.large": 180.0,
    "db.m5.xlarge": 360.0,
    "db.m6g.large": 224.0,
    "db.m6g.2xlarge": 640.0,
}


def fetch_live_resources() -> list[dict[str, Any]]:
    """Fetch a conservative AWS inventory using boto3 credentials.

    Cost Explorer per-resource cost requires AWS-side resource-level data to be
    enabled, so this adapter uses safe estimates when exact resource cost is not
    available. The system never applies infrastructure changes directly.
    """

    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("Install boto3 before using live AWS ingestion.") from exc

    session_kwargs: dict[str, str] = {}
    if settings.aws_profile:
        session_kwargs["profile_name"] = settings.aws_profile
    session = boto3.Session(**session_kwargs)

    resources: list[dict[str, Any]] = []
    for region in settings.parsed_aws_regions:
        resources.extend(_fetch_ec2_instances(session, region))
        resources.extend(_fetch_rds_instances(session, region))
        resources.extend(_fetch_ebs_volumes(session, region))
        resources.extend(_fetch_load_balancers(session, region))
    return resources


def _fetch_ec2_instances(session: Any, region: str) -> list[dict[str, Any]]:
    ec2 = session.client("ec2", region_name=region)
    resources: list[dict[str, Any]] = []
    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate(
        Filters=[{"Name": "instance-state-name", "Values": ["running", "stopped"]}]
    ):
        for reservation in page.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                tags = _tags(instance.get("Tags", []))
                instance_id = instance["InstanceId"]
                instance_type = instance["InstanceType"]
                metrics = _ec2_metrics(session, region, instance_id)
                resources.append(
                    {
                        "id": instance_id,
                        "account_id": settings.aws_account_id,
                        "type": "ec2",
                        "name": tags.get("Name", instance_id),
                        "region": region,
                        "terraform_address": tags.get(
                            "terraform_address",
                            f"aws_instance.{_safe_name(tags.get('Name', instance_id))}",
                        ),
                        "monthly_cost": EC2_MONTHLY_ESTIMATES.get(instance_type, 100.0),
                        "tags": tags,
                        "metrics": metrics,
                        "config": {"instance_type": instance_type, "state": instance.get("State", {}).get("Name")},
                    }
                )
    return resources


def _fetch_rds_instances(session: Any, region: str) -> list[dict[str, Any]]:
    rds = session.client("rds", region_name=region)
    resources: list[dict[str, Any]] = []
    paginator = rds.get_paginator("describe_db_instances")
    for page in paginator.paginate():
        for db in page.get("DBInstances", []):
            arn = db["DBInstanceArn"]
            tags = _rds_tags(rds, arn)
            identifier = db["DBInstanceIdentifier"]
            instance_class = db["DBInstanceClass"]
            metrics = _rds_metrics(session, region, identifier)
            resources.append(
                {
                    "id": identifier,
                    "account_id": settings.aws_account_id,
                    "type": "rds",
                    "name": tags.get("Name", identifier),
                    "region": region,
                    "terraform_address": tags.get(
                        "terraform_address",
                        f"aws_db_instance.{_safe_name(identifier)}",
                    ),
                    "monthly_cost": RDS_MONTHLY_ESTIMATES.get(instance_class, 300.0),
                    "tags": tags,
                    "metrics": metrics,
                    "config": {"instance_class": instance_class, "engine": db.get("Engine")},
                }
            )
    return resources


def _fetch_ebs_volumes(session: Any, region: str) -> list[dict[str, Any]]:
    ec2 = session.client("ec2", region_name=region)
    resources: list[dict[str, Any]] = []
    paginator = ec2.get_paginator("describe_volumes")
    for page in paginator.paginate():
        for volume in page.get("Volumes", []):
            tags = _tags(volume.get("Tags", []))
            volume_id = volume["VolumeId"]
            size_gb = float(volume.get("Size", 0))
            attached = bool(volume.get("Attachments"))
            created_at = volume.get("CreateTime")
            age_days = 0
            if created_at:
                age_days = (datetime.now(timezone.utc) - created_at).days
            resources.append(
                {
                    "id": volume_id,
                    "account_id": settings.aws_account_id,
                    "type": "ebs_volume",
                    "name": tags.get("Name", volume_id),
                    "region": region,
                    "terraform_address": tags.get(
                        "terraform_address",
                        f"aws_ebs_volume.{_safe_name(tags.get('Name', volume_id))}",
                    ),
                    "monthly_cost": round(size_gb * 0.08, 2),
                    "tags": tags,
                    "metrics": {"attached": attached, "age_days": age_days, "p95_latency_ms": 0, "error_rate_pct": 0},
                    "config": {"size_gb": size_gb, "type": volume.get("VolumeType")},
                }
            )
    return resources


def _fetch_load_balancers(session: Any, region: str) -> list[dict[str, Any]]:
    elbv2 = session.client("elbv2", region_name=region)
    resources: list[dict[str, Any]] = []
    paginator = elbv2.get_paginator("describe_load_balancers")
    for page in paginator.paginate():
        lbs = page.get("LoadBalancers", [])
        if not lbs:
            continue
        tag_map = _elbv2_tag_map(elbv2, [lb["LoadBalancerArn"] for lb in lbs])
        for lb in lbs:
            arn = lb["LoadBalancerArn"]
            name = lb["LoadBalancerName"]
            tags = tag_map.get(arn, {})
            metrics = _alb_metrics(session, region, arn)
            resources.append(
                {
                    "id": name,
                    "account_id": settings.aws_account_id,
                    "type": "load_balancer",
                    "name": tags.get("Name", name),
                    "region": region,
                    "terraform_address": tags.get(
                        "terraform_address",
                        f"aws_lb.{_safe_name(name)}",
                    ),
                    "monthly_cost": 22.4,
                    "tags": tags,
                    "metrics": metrics,
                    "config": {"type": lb.get("Type"), "scheme": lb.get("Scheme")},
                }
            )
    return resources


def _ec2_metrics(session: Any, region: str, instance_id: str) -> dict[str, Any]:
    cloudwatch = session.client("cloudwatch", region_name=region)
    cpu = _metric_stats(
        cloudwatch,
        namespace="AWS/EC2",
        metric_name="CPUUtilization",
        dimensions=[{"Name": "InstanceId", "Value": instance_id}],
    )
    network_in = _metric_stats(
        cloudwatch,
        namespace="AWS/EC2",
        metric_name="NetworkIn",
        dimensions=[{"Name": "InstanceId", "Value": instance_id}],
    )
    return {
        "avg_cpu_14d_pct": cpu["avg"],
        "peak_cpu_14d_pct": cpu["max"],
        "avg_network_mbps": round((network_in["avg"] * 8) / 1_000_000, 2),
        "p95_latency_ms": 0,
        "error_rate_pct": 0,
    }


def _rds_metrics(session: Any, region: str, identifier: str) -> dict[str, Any]:
    cloudwatch = session.client("cloudwatch", region_name=region)
    cpu = _metric_stats(
        cloudwatch,
        namespace="AWS/RDS",
        metric_name="CPUUtilization",
        dimensions=[{"Name": "DBInstanceIdentifier", "Value": identifier}],
    )
    connections = _metric_stats(
        cloudwatch,
        namespace="AWS/RDS",
        metric_name="DatabaseConnections",
        dimensions=[{"Name": "DBInstanceIdentifier", "Value": identifier}],
    )
    return {
        "avg_cpu_14d_pct": cpu["avg"],
        "peak_cpu_14d_pct": cpu["max"],
        "avg_connections": round(connections["avg"], 2),
        "p95_latency_ms": 0,
        "error_rate_pct": 0,
    }


def _alb_metrics(session: Any, region: str, lb_arn: str) -> dict[str, Any]:
    cloudwatch = session.client("cloudwatch", region_name=region)
    lb_dimension = lb_arn.split("loadbalancer/", 1)[-1]
    requests = _metric_stats(
        cloudwatch,
        namespace="AWS/ApplicationELB",
        metric_name="RequestCount",
        dimensions=[{"Name": "LoadBalancer", "Value": lb_dimension}],
        statistic="Sum",
    )
    return {
        "requests_14d": int(requests["sum"]),
        "healthy_hosts": 0,
        "p95_latency_ms": 0,
        "error_rate_pct": 0,
    }


def _metric_stats(
    cloudwatch: Any,
    *,
    namespace: str,
    metric_name: str,
    dimensions: list[dict[str, str]],
    statistic: str = "Average",
) -> dict[str, float]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=14)
    response = cloudwatch.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=dimensions,
        StartTime=start,
        EndTime=end,
        Period=86400,
        Statistics=[statistic, "Maximum"] if statistic != "Sum" else ["Sum"],
    )
    points = response.get("Datapoints", [])
    if not points:
        return {"avg": 0.0, "max": 0.0, "sum": 0.0}
    values = [float(point.get(statistic, 0.0)) for point in points]
    maximums = [float(point.get("Maximum", 0.0)) for point in points]
    return {
        "avg": round(sum(values) / len(values), 2),
        "max": round(max(maximums) if maximums else max(values), 2),
        "sum": round(sum(values), 2),
    }


def _tags(items: list[dict[str, str]]) -> dict[str, str]:
    return {item["Key"]: item.get("Value", "") for item in items}


def _rds_tags(rds: Any, arn: str) -> dict[str, str]:
    try:
        return _tags(rds.list_tags_for_resource(ResourceName=arn).get("TagList", []))
    except Exception:
        return {}


def _elbv2_tag_map(elbv2: Any, arns: list[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for chunk in [arns[index : index + 20] for index in range(0, len(arns), 20)]:
        try:
            response = elbv2.describe_tags(ResourceArns=chunk)
        except Exception:
            continue
        for item in response.get("TagDescriptions", []):
            result[item["ResourceArn"]] = _tags(item.get("Tags", []))
    return result


def _safe_name(value: str) -> str:
    safe = "".join(char.lower() if char.isalnum() else "_" for char in value)
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_") or "resource"

