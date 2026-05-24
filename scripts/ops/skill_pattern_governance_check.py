#!/usr/bin/env python3
"""Run the local Block 8 skill-pattern governance check."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_agent.ops.skill_pattern_governance import (  # noqa: E402
    check_skill_pattern_governance,
    render_markdown,
    report_to_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that Block 8 skill-pattern governance stays pattern-only."
    )
    parser.add_argument("--repo", default=".", help="Repository root to verify.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    args = parser.parse_args()

    report = check_skill_pattern_governance(Path(args.repo))
    print(report_to_json(report) if args.json else render_markdown(report), end="")
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
