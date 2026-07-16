from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.demo_loader import reset_demo_data
from app.doctor import run_doctor
from app.service import ingest_live_aws, live_autopilot, open_pr, scan_account, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="AI FinOps Remediation Agent CLI")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("demo-reset", help="Load demo AWS resources into the database")
    subcommands.add_parser("ingest-aws", help="Ingest live AWS resources using boto3 credentials")
    subcommands.add_parser("scan", help="Score resources and create recommendations")

    doctor = subcommands.add_parser("doctor", help="Check local/live configuration without printing secrets")
    doctor.add_argument("--live", action="store_true", help="Make network calls to verify AWS STS and GitHub access")

    autopilot = subcommands.add_parser("autopilot", help="Scan and open PRs for non-blocked recommendations")
    autopilot.add_argument("--no-prs", action="store_true", help="Score only; do not open PR artifacts/PRs")

    live = subcommands.add_parser("live-autopilot", help="Ingest live AWS data, scan, and open GitHub PRs")
    live.add_argument("--no-prs", action="store_true", help="Ingest/score only; do not open GitHub PRs")
    live.add_argument(
        "--allow-local-artifacts",
        action="store_true",
        help="Use local PR artifacts if GitHub is not configured",
    )

    open_pr_parser = subcommands.add_parser("open-pr", help="Open a PR artifact or GitHub PR for one recommendation")
    open_pr_parser.add_argument("recommendation_id")
    open_pr_parser.add_argument("--require-github", action="store_true", help="Fail unless a real GitHub PR is opened")

    subcommands.add_parser("summary", help="Print current savings/recommendation summary")

    args = parser.parse_args()
    try:
        if args.command == "demo-reset":
            print_json(reset_demo_data())
        elif args.command == "doctor":
            print_json(run_doctor(live=args.live))
        elif args.command == "ingest-aws":
            print_json(ingest_live_aws())
        elif args.command == "scan":
            print_json(scan_account())
        elif args.command == "autopilot":
            print_json(scan_account(open_prs=not args.no_prs))
        elif args.command == "live-autopilot":
            print_json(
                live_autopilot(
                    open_prs=not args.no_prs,
                    require_github=not args.allow_local_artifacts,
                )
            )
        elif args.command == "open-pr":
            print_json(open_pr(args.recommendation_id, actor="cli", require_github=args.require_github))
        elif args.command == "summary":
            print_json(summary())
    except Exception as exc:
        print_json({"ok": False, "error_type": exc.__class__.__name__, "error": str(exc)})
        raise SystemExit(1)


def print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
