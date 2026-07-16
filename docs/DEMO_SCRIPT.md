# Demo script

Use this when walking through the project in an interview.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/demo.py
```

## What to say

> CloudPilot is a human-in-the-loop AI remediation backend for AWS cost
> optimization. It ingests AWS telemetry, detects waste, scores reliability risk,
> generates Terraform diffs, opens PRs, and tracks approvals through an audit log.

## Walkthrough

1. Show `/dashboard`.
2. Explain that demo mode loaded five AWS-style resources.
3. Show that the agent found four savings opportunities.
4. Point out that the busy production EC2 instance was not touched.
5. Open one generated PR artifact in `artifacts/prs`.
6. Show the Terraform diff, rollback plan, risk level, and policy status.
7. Show `/audit` to demonstrate traceability.
8. Show `python scripts/cli.py doctor` to demonstrate production readiness checks.

## Strongest technical points

- Safety-first automation: PRs, not direct infra mutation.
- Backend workflow: ingestion, detection, policy, review, diffing, approval, audit.
- Production-shaped integrations: AWS, GitHub, Slack, OpenAI, Postgres.
- Clear fallback behavior: local demos work without credentials.

