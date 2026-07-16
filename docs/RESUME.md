# Résumé bullets and talking points

## Current truthful project bullet

- Built an AI-assisted FinOps backend that detected cloud waste, generated Terraform diffs, routed approvals, and tracked audit history

## Backend/platform-focused version

- Implemented a FastAPI remediation agent with cloud-waste detection, reliability guardrails, Terraform diffs, and approval workflows

## Use after live AWS + GitHub PR validation

- Built an AI FinOps agent that detected AWS waste, scored reliability risk, generated Terraform diffs, and opened reviewable PRs

## Interview explanation

CloudPilot is an AI-assisted backend for safe cloud cost remediation. It ingests
AWS resource and utilization data, detects waste such as oversized EC2/RDS
instances or idle load balancers, checks reliability risk, generates Terraform
diffs, and opens reviewable GitHub PRs instead of directly modifying infrastructure.

The core design goal is safe automation: recommendations can be generated
automatically, but production infrastructure changes still go through policy
checks, PR review, rollback planning, and audit logging.

