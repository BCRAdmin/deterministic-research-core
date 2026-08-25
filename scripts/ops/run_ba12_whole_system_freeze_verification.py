#!/usr/bin/env python3
"""Run and bind the complete BA12 whole-system freeze verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"


def receipt(name: str, command: list[str], cwd: Path) -> dict[str, object]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return {
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "exit_code": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
        "stdout_tail": result.stdout[-6000:],
        "stderr_tail": result.stderr[-6000:],
        "status": "PASS" if result.returncode == 0 else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--boundary-output", type=Path, required=True)
    parser.add_argument("--r5-regression-output", type=Path, required=True)
    args = parser.parse_args()
    py = str(ROOT / ".venv/bin/python")
    r5_command = [
        py,
        "scripts/ops/run_ba12_r5_full_verification.py",
        "--output",
        str(args.r5_regression_output.resolve()),
        "--boundary-output",
        str(args.boundary_output.resolve()),
    ]
    r5 = receipt("r5_complete_regression_set", r5_command, ROOT)
    receipts = [r5]
    if r5["status"] == "PASS":
        r5_report = json.loads(args.r5_regression_output.resolve().read_text(encoding="utf-8"))
        receipts.extend(r5_report["receipts"])
    receipts.extend(
        [
            receipt(
                "whole_system_freeze_matrix_30",
                [py, "-m", "pytest", "-q", "research_agent/tests/test_ba12_whole_system_freeze.py"],
                ROOT,
            ),
            receipt(
                "whole_system_freeze_verifier",
                [py, "scripts/ops/verify_ba12_whole_system_freeze.py", "--json"],
                ROOT,
            ),
        ]
    )
    report = {
        "contract_id": "room16.ba12.whole_system_freeze_full_verification@1",
        "research_head": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip(),
        "research_tree": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD^{tree}"], text=True
        ).strip(),
        "product_head": subprocess.check_output(
            ["git", "-C", str(PRODUCT), "rev-parse", "HEAD"], text=True
        ).strip(),
        "product_tree": subprocess.check_output(
            ["git", "-C", str(PRODUCT), "rev-parse", "HEAD^{tree}"], text=True
        ).strip(),
        "receipts": receipts,
        "status": "PASS" if all(item["status"] == "PASS" for item in receipts) else "FAIL",
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "receipt_count": len(receipts)}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
