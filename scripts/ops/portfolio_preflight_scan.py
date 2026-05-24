#!/usr/bin/env python3
"""Run the local portfolio preflight scan."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_agent.ops.portfolio_preflight_scan import (  # noqa: E402
    render_markdown,
    report_to_json,
    scan_changed_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan changed files for generated artifacts, large files and obvious secret patterns."
    )
    parser.add_argument("--repo", default=".", help="Git repository to scan.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument(
        "--strict-review",
        action="store_true",
        help="Return non-zero when review findings exist, not only blocking findings.",
    )
    args = parser.parse_args()

    report = scan_changed_paths(Path(args.repo))
    print(report_to_json(report) if args.json else render_markdown(report), end="")
    if report.blocking_findings:
        return 2
    if args.strict_review and report.review_findings:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
