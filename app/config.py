from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI FinOps Remediation Agent"
    environment: str = os.getenv("FINOPS_ENV", "local")
    database_url: str | None = os.getenv("FINOPS_DATABASE_URL")
    database_path: Path = Path(os.getenv("FINOPS_DB_PATH", PROJECT_ROOT / "data" / "finops.db"))
    demo_resources_path: Path = Path(
        os.getenv("FINOPS_DEMO_RESOURCES", PROJECT_ROOT / "demo" / "aws" / "resources.json")
    )
    terraform_path: Path = Path(
        os.getenv("FINOPS_TERRAFORM_PATH", PROJECT_ROOT / "demo" / "terraform" / "main.tf")
    )
    terraform_repo_path: str = os.getenv("FINOPS_TERRAFORM_REPO_PATH", "demo/terraform/main.tf")
    pr_artifact_dir: Path = Path(os.getenv("FINOPS_PR_DIR", PROJECT_ROOT / "artifacts" / "prs"))
    slack_channel: str = os.getenv("FINOPS_SLACK_CHANNEL", "#finops-approvals")
    slack_webhook_url: str | None = os.getenv("FINOPS_SLACK_WEBHOOK_URL")
    github_token: str | None = os.getenv("FINOPS_GITHUB_TOKEN")
    github_repo: str | None = os.getenv("FINOPS_GITHUB_REPO")
    github_base_branch: str = os.getenv("FINOPS_GITHUB_BASE_BRANCH", "main")
    github_branch_prefix: str = os.getenv("FINOPS_GITHUB_BRANCH_PREFIX", "finops")
    github_draft_pr: bool = os.getenv("FINOPS_GITHUB_DRAFT_PR", "true").lower() in {"1", "true", "yes", "on"}
    require_github_for_live: bool = os.getenv("FINOPS_REQUIRE_GITHUB_FOR_LIVE", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    aws_profile: str | None = os.getenv("FINOPS_AWS_PROFILE")
    aws_regions: str = os.getenv("FINOPS_AWS_REGIONS", "us-east-1")
    aws_account_id: str = os.getenv("FINOPS_AWS_ACCOUNT_ID", "live-aws")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("FINOPS_OPENAI_MODEL", "gpt-4.1-mini")

    @property
    def database_backend(self) -> str:
        if self.database_url and self.database_url.startswith(("postgres://", "postgresql://")):
            return "postgres"
        return "sqlite"

    @property
    def parsed_aws_regions(self) -> list[str]:
        return [region.strip() for region in self.aws_regions.split(",") if region.strip()]


settings = Settings()
