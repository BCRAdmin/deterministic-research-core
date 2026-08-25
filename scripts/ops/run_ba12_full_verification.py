#!/usr/bin/env python3
"""Run and persist the complete BA12 verification command set."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
APP = PRODUCT / "room16-app"


def receipt(name: str, command: list[str], cwd: Path, env: dict[str, str] | None = None) -> dict[str, object]:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    return {
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "exit_code": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
        "status": "PASS" if result.returncode == 0 else "FAIL",
    }


def wait_server(process: subprocess.Popen[str]) -> None:
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Product verification server stopped during startup")
        try:
            with urllib.request.urlopen("http://127.0.0.1:4516/api/health", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Product verification server did not become ready")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    py = str(ROOT / ".venv/bin/python")
    receipts = [
        receipt("research_full_regression", [py, "-m", "pytest", "-q"], ROOT),
        receipt("research_ruff", [str(ROOT / ".venv/bin/ruff"), "check", "research_agent", "scripts/ops"], ROOT),
    ]
    server = subprocess.Popen(["npm", "start"], cwd=APP, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        wait_server(server)
        product_env = dict(os.environ)
        product_env["ROOM16_VERIFY_SKIP_HARDENING_STATE"] = "1"
        receipts.extend([
            receipt("product_full_verify", ["npm", "run", "verify"], APP, product_env),
            receipt("product_typescript", ["npm", "run", "lint"], APP),
            receipt("product_ba12_native", ["node", "--test", "scripts/test_ba12_native_cutover.mjs"], APP),
        ])
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
    receipts.extend([
        receipt("npm_production_audit", ["npm", "audit", "--omit=dev", "--audit-level=high", "--json"], APP),
        receipt("python_dependency_audit", [str(PRODUCT / ".venv/bin/pip-audit"), "--local", "--skip-editable", "--format", "json"], PRODUCT),
    ])
    freeze_commands = (
        ("foundation_freeze", [py, "scripts/ops/verify_compiler_foundation_freeze.py", "--product-repo", str(PRODUCT)]),
        ("registry_freeze", [py, "scripts/ops/verify_registry_foundation_freeze.py"]),
        ("semantic_wave_freeze", [py, "scripts/ops/verify_semantic_compiler_wave_freeze.py", "--product-repo", str(PRODUCT), "--json"]),
        ("ba10_freeze", [py, "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py", "--product-repo", str(PRODUCT), "--json"]),
        ("ba11_freeze", [py, "scripts/ops/verify_ba11_canary_governance_freeze.py", "--json"]),
        ("rfc0008_freeze", [py, "scripts/ops/verify_rfc0008_v2_trust_freeze.py", "--json"]),
        ("rfc0009_freeze", [py, "scripts/ops/verify_rfc0009_native_trust_freeze.py", "--product-repo", str(PRODUCT), "--json"]),
        ("rfc0010_freeze", [py, "scripts/ops/verify_rfc0010_freeze.py", "--product-repo", str(PRODUCT), "--json"]),
    )
    receipts.extend(receipt(name, command, ROOT) for name, command in freeze_commands)
    report = {
        "contract_id": "room16.ba12.full_verification_receipts",
        "contract_version": 1,
        "research_head": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "product_head": subprocess.check_output(["git", "-C", str(PRODUCT), "rev-parse", "HEAD"], text=True).strip(),
        "receipts": receipts,
        "status": "PASS" if all(item["status"] == "PASS" for item in receipts) else "FAIL",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "receipt_count": len(receipts)}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
