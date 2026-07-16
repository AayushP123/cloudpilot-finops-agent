# Security

CloudPilot is designed to recommend infrastructure changes, not apply them.

## Secret handling

- Do not commit `.env`.
- Do not log AWS keys, GitHub tokens, Slack webhook URLs, or OpenAI keys.
- Use `python scripts/cli.py doctor --live` to verify configuration without
  printing secret values.

## AWS permissions

Use read-only AWS permissions for discovery and metrics. The app does not need
AWS write permissions because it never directly modifies infrastructure.

## GitHub permissions

Use the smallest token scope practical for the target repo:

- Contents: read/write
- Pull requests: read/write
- Metadata: read

## Reporting issues

If you find a security issue, do not open a public issue with secret values.
Rotate exposed credentials immediately.

