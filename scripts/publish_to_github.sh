#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="${1:-cloudpilot-finops-agent}"
DESCRIPTION="Human-in-the-loop AI remediation backend for AWS cost optimization."

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI is required. Install it, then run: gh auth login"
  exit 1
fi

gh auth status >/dev/null

if [ ! -d .git ]; then
  git init
  git branch -M main
fi

git add -A
if ! git diff --cached --quiet; then
  git commit -m "Initial CloudPilot FinOps Agent release"
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create "$REPO_NAME" \
    --public \
    --description "$DESCRIPTION" \
    --source=. \
    --remote=origin \
    --push
else
  git push -u origin "$(git branch --show-current)"
fi

echo "Published repository:"
gh repo view --web

