from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Resource(BaseModel):
    id: str
    account_id: str
    type: str
    name: str
    region: str
    terraform_address: str
    monthly_cost: float
    tags: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[str] = None


class Recommendation(BaseModel):
    id: str
    resource_id: str
    account_id: str
    resource_type: str
    title: str
    action: str
    current_config: dict[str, Any]
    proposed_config: dict[str, Any]
    savings_monthly: float
    risk_level: Literal["low", "medium", "high"]
    confidence: float
    evidence: dict[str, Any]
    rationale: str
    rollback_plan: str
    policy_status: Literal["allowed", "needs_review", "blocked"]
    status: Literal["open", "approved", "rejected", "pr_opened", "realized"]
    terraform_patch: Optional[str] = None
    pr_url: Optional[str] = None
    slack_message: Optional[str] = None
    created_at: str
    updated_at: str


class ScanResponse(BaseModel):
    scanned_resources: int
    created_or_updated_recommendations: int
    estimated_monthly_savings: float
    recommendation_ids: list[str]
    opened_prs: list[str] = Field(default_factory=list)


class IngestResponse(BaseModel):
    resources_loaded: int
    source: str


class AutopilotRequest(BaseModel):
    open_prs: bool = True


class LiveAutopilotRequest(BaseModel):
    open_prs: bool = True
    require_github: bool = True


class LiveAutopilotResponse(ScanResponse):
    ingested_resources: int
    source: str


class ApprovalRequest(BaseModel):
    actor: str = "local-user"
    reason: Optional[str] = None


class RealizeRequest(BaseModel):
    actor: str = "local-user"
    realized_monthly_savings: Optional[float] = None


class Summary(BaseModel):
    resources: int
    recommendations: int
    open_recommendations: int
    pr_opened: int
    approved: int
    rejected: int
    realized: int
    estimated_open_monthly_savings: float
    estimated_total_monthly_savings: float
