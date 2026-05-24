#!/usr/bin/env python3
"""Verify that historical backlog blocks are closed or correctly gated."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_agent.ops.past_blocks_closure import (
    DEFAULT_LIONCOM_ROOT,
    DEFAULT_VAULT,
    build_past_blocks_closure_report,
    render_past_blocks_closure_markdown,
    report_to_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check historical block closure state.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="Human Overview vault path.")
    parser.add_argument("--lioncom-root", default=str(DEFAULT_LIONCOM_ROOT), help="LIONCOM repository root.")
    parser.add_argument("--output-dir", default="outputs/agent_os_readiness", help="Output directory.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = build_past_blocks_closure_report(
        root=root,
        vault=Path(args.vault).resolve(),
        lioncom_root=Path(args.lioncom_root).resolve(),
    )
    (out / "PAST_BLOCKS_CLOSURE.json").write_text(report_to_json(report), encoding="utf-8")
    (out / "PAST_BLOCKS_CLOSURE.md").write_text(render_past_blocks_closure_markdown(report), encoding="utf-8")
    print(report_to_json(report), end="")
    return 0 if report.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
