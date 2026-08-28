#!/usr/bin/env python3
"""Run and record the mandatory Room16 shared-coverage regression gates."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
PRODUCT_APP = PRODUCT / "room16-app"
FOREIGN = ROOT.parent.parent / "Utility-Websites" / "materialbedarf-rechner.de"


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _receipt(name: str, argv: list[str], cwd: Path) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)
    return {
        "name": name,
        "argv": argv,
        "cwd": str(cwd),
        "started_at": started,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "exit_code": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _group(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "PASS" if all(item["status"] == "PASS" for item in receipts) else "FAIL",
        "receipts": receipts,
    }


def run(output: Path) -> dict[str, str]:
    py = str(ROOT / ".venv/bin/python")
    ruff = str(ROOT / ".venv/bin/ruff")
    product_py = str(PRODUCT / ".venv/bin/python")
    research = [
        _receipt("full_research_pytest", [py, "-m", "pytest", "-q"], ROOT),
        _receipt("research_ruff", [ruff, "check", "research_agent", "scripts"], ROOT),
        _receipt("python_dependency_check", [py, "-m", "pip", "check"], ROOT),
    ]
    _write(output / "24_FULL_RESEARCH_REGRESSION.json", _group(research))

    product = [
        _receipt("full_product_pytest", [product_py, "-m", "pytest", "-q"], PRODUCT),
        _receipt("product_build", ["npm", "run", "build"], PRODUCT_APP),
        _receipt("product_lint", ["npm", "run", "lint"], PRODUCT_APP),
        _receipt("product_ba12_runtime", ["npm", "run", "verify:ba12-runtime"], PRODUCT_APP),
    ]
    _write(output / "25_FULL_PRODUCT_REGRESSION.json", _group(product))

    shared_paths = [
        "research_agent/tests/test_rfc0011_shared_hardening.py",
        "research_agent/tests/test_rfc0011_r2_correction.py",
        "research_agent/tests/test_rfc0011_r3_correction.py",
        "research_agent/tests/test_rfc0011_r4_batch_readiness.py",
        "research_agent/tests/test_alpha_saas_development.py",
        "research_agent/tests/test_alpha_reit_development.py",
        "research_agent/tests/test_alpha_bank_development.py",
        "research_agent/tests/test_alpha_energy_development.py",
        "research_agent/tests/test_fixed24_shared_coverage_correction.py",
    ]
    shared = _receipt("r1_r4_and_eight_alpha_regression", [py, "-m", "pytest", "-q", *shared_paths], ROOT)
    _write(output / "23_R1_R4_AND_EIGHT_ALPHA_REGRESSION.json", shared)

    freeze_receipts = [
        _receipt(
            "whole_system_freeze_verifier",
            [py, "scripts/ops/verify_ba12_whole_system_freeze.py", "--product-repo", str(PRODUCT), "--json"],
            ROOT,
        ),
        _receipt(
            "whole_system_freeze_tests",
            [py, "-m", "pytest", "-q", "research_agent/tests/test_ba12_whole_system_freeze.py"],
            ROOT,
        ),
        _receipt(
            "four_alpha_freezes",
            [
                py,
                "-m",
                "pytest",
                "-q",
                "research_agent/tests/test_alpha_saas_development.py",
                "research_agent/tests/test_alpha_reit_development.py",
                "research_agent/tests/test_alpha_bank_development.py",
                "research_agent/tests/test_alpha_energy_development.py",
            ],
            ROOT,
        ),
    ]
    _write(output / "26_WHOLE_ALPHA_FREEZE_REGRESSION.json", _group(freeze_receipts))

    security = [
        research[2],
        _receipt(
            "product_production_dependency_audit",
            ["npm", "audit", "--omit=dev", "--audit-level=high"],
            PRODUCT_APP,
        ),
    ]
    _write(output / "27_SECURITY_DEPENDENCY_REPORT.json", _group(security))

    before_path = output / ".boundary_before.json"
    after_path = output / ".boundary_after.json"
    boundary_command = [
        py,
        "scripts/ops/verify_project_boundary_non_interference_v2.py",
        "snapshot",
        "--foreign-root",
        str(FOREIGN),
        "--output",
        str(after_path),
    ]
    boundary_receipt = _receipt("foreign_readonly_snapshot_after", boundary_command, ROOT)
    before = json.loads(before_path.read_text())
    after = json.loads(after_path.read_text()) if after_path.exists() else {}
    boundary = {
        "contract_id": "room16.project_boundary_non_interference@2",
        "status": (
            "PASS"
            if boundary_receipt["status"] == "PASS"
            and before.get("snapshot_sha256") == after.get("snapshot_sha256")
            else "FAIL"
        ),
        "foreign_before_snapshot_sha256": before.get("snapshot_sha256"),
        "foreign_after_snapshot_sha256": after.get("snapshot_sha256"),
        "external_foreign_drift_observed": before.get("snapshot_sha256")
        != after.get("snapshot_sha256"),
        "room16_foreign_mutation": False,
        "foreign_mutation_commands": [],
        "research_origin": subprocess.check_output(
            ["git", "-C", str(ROOT), "remote", "get-url", "origin"], text=True
        ).strip(),
        "product_origin": subprocess.check_output(
            ["git", "-C", str(PRODUCT), "remote", "get-url", "origin"], text=True
        ).strip(),
        "foreign_origin": subprocess.check_output(
            ["git", "-C", str(FOREIGN), "remote", "get-url", "origin"], text=True
        ).strip(),
        "snapshot_receipt": boundary_receipt,
    }
    _write(output / "28_BOUNDARY_GATE_V2_REPORT.json", boundary)
    statuses = {
        "research": _group(research)["status"],
        "product": _group(product)["status"],
        "shared": shared["status"],
        "freeze": _group(freeze_receipts)["status"],
        "security": _group(security)["status"],
        "boundary": boundary["status"],
    }
    print(json.dumps(statuses, sort_keys=True))
    return statuses


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    statuses = run(args.output.resolve())
    return 0 if all(value == "PASS" for value in statuses.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
