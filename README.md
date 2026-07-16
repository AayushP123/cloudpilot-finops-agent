# CloudPilot FinOps Agent

[![CI](https://github.com/AayushP123/cloudpilot-finops-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/AayushP123/cloudpilot-finops-agent/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CloudPilot is a human-in-the-loop AI remediation backend for AWS cost optimization.
It ingests cloud telemetry, detects waste, scores reliability risk, generates Terraform
diffs, opens GitHub PRs, routes approval messages, and tracks every recommendation
through an audit trail.

The agent is intentionally safe: it never runs `terraform apply` and never mutates
cloud infrastructure directly. Every remediation becomes a reviewable Terraform PR.

## Why this exists

Cloud waste is usually easy to spot after the bill arrives and hard to fix safely.
CloudPilot turns waste detection into an engineering workflow:

```mermaid
flowchart LR
  A["AWS inventory + CloudWatch metrics"] --> B["FastAPI ingestion"]
  B --> C["Waste detection engine"]
  C --> D["Reliability policy gate"]
  D --> E["AI recommendation reviewer"]
  E --> F["Terraform diff generator"]
  F --> G["GitHub draft PR"]
  G --> H["Slack approval message"]
  H --> I["Audit + savings tracking"]
```

## Features

- AWS ingestion for EC2, RDS, EBS volumes, and Application Load Balancers.
- Demo mode with realistic AWS-style fixtures; no cloud credentials required.
- Cloud-waste detection for oversized compute/database resources and idle assets.
- Reliability guardrails for prod resources, CPU spikes, latency, error rates, and destructive actions.
- Optional OpenAI reviewer for recommendation rationale and rollback planning.
- Deterministic local reviewer fallback for no-key demos and tests.
- Terraform diff generation for right-sizing and cleanup recommendations.
- Real GitHub draft PR creation against a configured infrastructure repository.
- Local PR artifact fallback for portfolio demos.
- Slack webhook notifications for human approval.
- SQLite locally; Postgres-ready via `FINOPS_DATABASE_URL`.
- CLI, FastAPI API, dashboard, Docker, docker-compose, and tests.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design,
data model, recommendation lifecycle, and safety model.

## Quick demo

```bash
git clone https://github.com/AayushP123/cloudpilot-finops-agent.git
cd cloudpilot-finops-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/demo.py
```

Expected demo behavior:

- Loads 5 AWS-style resources.
- Creates 4 recommendations.
- Estimates `$712.40/month` in potential savings.
- Writes local PR artifacts to `artifacts/prs/`.
- Leaves the busy production EC2 instance untouched.

## Run the API

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Open:

- Dashboard: <http://127.0.0.1:8000/dashboard>
- API docs: <http://127.0.0.1:8000/docs>
- Readiness: <http://127.0.0.1:8000/doctor>

## CLI

```bash
python scripts/cli.py doctor
python scripts/cli.py demo-reset
python scripts/cli.py scan
python scripts/cli.py autopilot
python scripts/cli.py summary
```

Live AWS + real GitHub PR flow:

```bash
python scripts/cli.py doctor --live
python scripts/cli.py live-autopilot --no-prs
python scripts/cli.py live-autopilot
```

`live-autopilot` requires GitHub by default so production mode does not quietly
fall back to local markdown artifacts.

## Configuration

Copy the example env file:

```bash
cp .env.example .env
```

Minimum live configuration:

```bash
FINOPS_AWS_PROFILE=your-aws-profile
FINOPS_AWS_REGIONS=us-east-1
FINOPS_GITHUB_TOKEN=github_pat_or_token
FINOPS_GITHUB_REPO=owner/infra-repo
FINOPS_GITHUB_BASE_BRANCH=main
FINOPS_TERRAFORM_REPO_PATH=infra/main.tf
FINOPS_GITHUB_DRAFT_PR=true
FINOPS_REQUIRE_GITHUB_FOR_LIVE=true
```

Optional:

```bash
FINOPS_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
OPENAI_API_KEY=sk-...
FINOPS_DATABASE_URL=postgresql://finops:finops@localhost:5432/finops
```

See [docs/LIVE_SETUP.md](docs/LIVE_SETUP.md) for the complete live setup guide.

## Docker + Postgres

```bash
docker compose up --build
```

Then open <http://127.0.0.1:8000/dashboard>.

## API examples

```bash
curl -X POST http://127.0.0.1:8000/demo/reset
curl -X POST http://127.0.0.1:8000/scan
curl -X POST http://127.0.0.1:8000/autopilot \
  -H 'content-type: application/json' \
  -d '{"open_prs": true}'
curl http://127.0.0.1:8000/recommendations
curl http://127.0.0.1:8000/audit
curl http://127.0.0.1:8000/summary
```

Require a real GitHub PR for one recommendation:

```bash
curl -X POST 'http://127.0.0.1:8000/recommendations/REC_ID/open-pr?require_github=true'
```

## Tests

```bash
pytest -q
```

Current local verification:

```text
4 passed
```

## Project status

Portfolio-ready. Demo mode is fully runnable locally. Live AWS/GitHub/Slack/OpenAI
paths are implemented behind environment configuration and should be validated
with `python scripts/cli.py doctor --live` before running against a real account.

## Repository guide

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design and data flow.
- [docs/LIVE_SETUP.md](docs/LIVE_SETUP.md) — AWS/GitHub/Slack/OpenAI setup.
- [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) — interview/demo walkthrough.
- [docs/RESUME.md](docs/RESUME.md) — résumé bullets and talking points.
- [CONTRIBUTING.md](CONTRIBUTING.md) — development workflow.
- [SECURITY.md](SECURITY.md) — safety and secret-handling notes.

## Publish to GitHub

After installing and authenticating GitHub CLI:

```bash
gh auth login
chmod +x scripts/publish_to_github.sh
./scripts/publish_to_github.sh cloudpilot-finops-agent
```
