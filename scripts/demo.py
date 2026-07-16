from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.demo_loader import reset_demo_data
from app.service import open_pr, scan_account, summary


def main() -> None:
    print("Resetting demo data...")
    print(reset_demo_data())

    print("\nScanning demo AWS account...")
    scan = scan_account()
    print(scan)

    print("\nOpening local PR artifacts for non-blocked recommendations...")
    opened = []
    for rec_id in scan["recommendation_ids"]:
        try:
            rec = open_pr(rec_id, actor="demo-script")
            opened.append(rec["pr_url"])
            print(f"- {rec['title']}: {rec['pr_url']}")
        except ValueError as exc:
            print(f"- skipped {rec_id}: {exc}")

    print("\nSummary:")
    print(summary())
    print("\nGenerated PR artifacts:")
    for url in opened:
        print(f"- {url.replace('local://', '')}")


if __name__ == "__main__":
    main()
