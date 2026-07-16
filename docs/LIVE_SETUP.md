# Live setup

This guide turns the local demo into a real AWS + GitHub PR workflow.

## 1. Create a GitHub repository

Create a public repository, for example:

```text
cloudpilot-finops-agent
```

Recommended description:

```text
Human-in-the-loop AI remediation backend for AWS cost optimization.
```

Recommended topics:

```text
fastapi, aws, terraform, finops, github-actions, openai, infrastructure, platform-engineering
```

If GitHub CLI is installed:

```bash
chmod +x scripts/publish_to_github.sh
./scripts/publish_to_github.sh cloudpilot-finops-agent
```

## 2. Configure local environment

```bash
cp .env.example .env
```

Minimum live values:

```bash
FINOPS_AWS_PROFILE=your-profile
FINOPS_AWS_REGIONS=us-east-1
FINOPS_GITHUB_TOKEN=github_pat_or_token
FINOPS_GITHUB_REPO=owner/infra-repo
FINOPS_GITHUB_BASE_BRANCH=main
FINOPS_TERRAFORM_REPO_PATH=infra/main.tf
FINOPS_GITHUB_DRAFT_PR=true
FINOPS_REQUIRE_GITHUB_FOR_LIVE=true
```

## 3. AWS permissions

Use the smallest practical read-only policy for discovery plus STS identity:

- `sts:GetCallerIdentity`
- `ec2:DescribeInstances`
- `ec2:DescribeVolumes`
- `rds:DescribeDBInstances`
- `rds:ListTagsForResource`
- `elasticloadbalancing:DescribeLoadBalancers`
- `elasticloadbalancing:DescribeTags`
- `cloudwatch:GetMetricStatistics`

The app does not need write permissions to AWS because it never mutates AWS
resources directly.

## 4. Terraform mapping

For the cleanest live experience, tag AWS resources with their Terraform address:

```text
terraform_address=aws_instance.api_worker
```

If the tag is absent, CloudPilot infers a likely Terraform address from the
resource name. That is useful for demos but not guaranteed for real repos.

## 5. GitHub token permissions

For fine-grained personal access tokens, grant access to the target repository:

- Contents: read and write
- Pull requests: read and write
- Metadata: read

The PRs are drafts by default.

## 6. Validate configuration

```bash
python scripts/cli.py doctor --live
```

You want:

```text
ready_for_live_prs: true
```

## 7. Dry-run live scan

```bash
python scripts/cli.py live-autopilot --no-prs
```

This ingests AWS and scores recommendations without opening PRs.

## 8. Open real PRs

```bash
python scripts/cli.py live-autopilot
```

The command will fail if GitHub is not configured because
`FINOPS_REQUIRE_GITHUB_FOR_LIVE=true` by default.
