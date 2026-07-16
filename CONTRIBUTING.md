# Contributing

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Local demo

```bash
python scripts/demo.py
```

## Before opening a PR

- Run `pytest -q`.
- Do not commit `.env`, database files, local PR artifacts, or credentials.
- Keep live integrations behind environment variables.
- Prefer draft PRs for infrastructure changes.

