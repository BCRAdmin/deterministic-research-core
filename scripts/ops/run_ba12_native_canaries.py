#!/usr/bin/env python3
"""Execute authorized live WM/COST/ABT BA12 canaries."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from research_agent.ba12_native.canary import COMPANIES, run_live_canary

ROOT = Path(__file__).resolve().parents[2]


def git(value: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", value], text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--execution-root", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--as-of-date", default="2026-08-25")
    parser.add_argument("--sec-user-agent", required=True)
    args = parser.parse_args()
    commit, tree = git("HEAD"), git("HEAD^{tree}")
    rows = []
    for counter, ticker in enumerate(COMPANIES, 100,):
        result = run_live_canary(ticker=ticker, as_of_date=args.as_of_date, execution_root=args.execution_root / ticker, output_root=args.output_root / ticker, sec_user_agent=args.sec_user_agent, research_commit=commit, research_tree=tree, monotonic_counter=counter)
        rows.append({"ticker": ticker, "snapshot_sha256": result.snapshot_sha256, "live_receipt_sha256s": result.live_receipt_sha256s, "bundle_sha256": result.compile_result.manifest["bundle_sha256"], "bundle_receipt_sha256": result.compile_result.receipt["receipt_sha256"], "native_run_receipt_sha256": result.compile_result.native_run_receipt.record_sha256, "bridge_verification": result.bridge_verification, "bundle_verification": result.compile_result.verification})
    report = {"contract_id": "room16.ba12.live_canary_execution", "contract_version": 1, "as_of_date": args.as_of_date, "network_mode": "actual_live_acquisition", "provider_ids": ["nasdaq", "sec"], "results": rows, "status": "PASS"}
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
