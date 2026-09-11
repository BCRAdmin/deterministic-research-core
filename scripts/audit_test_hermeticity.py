#!/usr/bin/env python3
"""Fail when committed tests depend on operator-specific paths or a local venv."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PATTERNS = {
    "mac_user_absolute": re.compile(r"/Users/[^/]+/"),
    "downloads_absolute": re.compile(r"/Downloads/"),
    "venv_python": re.compile(r"\.venv/(?:bin|Scripts)/python"),
}
ALLOW_MARKERS = ("HERMETICITY_NEGATIVE_FIXTURE", "EXPECTED_BAD_PATH_TEST_DATA")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    roots = [args.repo / "research_agent" / "tests", args.repo / "tests"]
    findings = []
    for root in roots:
        if not root.exists():
            continue
        for file in root.rglob("*.py"):
            for line_number, line in enumerate(file.read_text(errors="replace").splitlines(), 1):
                if any(marker in line for marker in ALLOW_MARKERS):
                    continue
                for kind, pattern in PATTERNS.items():
                    if pattern.search(line):
                        findings.append(
                            {
                                "file": str(file.relative_to(args.repo)),
                                "line": line_number,
                                "kind": kind,
                                "text": line.strip()[:240],
                            }
                        )
    result = {
        "contract_id": "room16.r16.test_hermeticity_static_audit@1",
        "status": "PASS" if not findings else "BLOCK",
        "findings": findings,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if not findings else 2)


if __name__ == "__main__":
    main()
