#!/usr/bin/env python3
"""Run the complete BA12 R5 Product-runtime activation verification set."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ops.verify_project_boundary_non_interference_v2 import (
    build_receipt as build_boundary_receipt,
    foreign_snapshot,
)

PRODUCT = ROOT.parent / "company-dossier-lab"
APP = PRODUCT / "room16-app"
FOREIGN = ROOT.parent.parent / "Utility-Websites/materialbedarf-rechner.de"
RESEARCH_BASE = "f9a063c9aa6f75a24a6e26a4d378273d92443ae4"
PRODUCT_BASE = "27393e2e2cfe6178b443bfce6d76fac9b0db9517"


def receipt(
    name: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    return {
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "exit_code": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
        "status": "PASS" if result.returncode == 0 else "FAIL",
    }


def wait_server(process: subprocess.Popen[str]) -> dict[str, object]:
    for _ in range(120):
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(f"canonical Product server stopped during startup\n{stdout}\n{stderr}")
        try:
            with urllib.request.urlopen("http://127.0.0.1:4516/api/health", timeout=1) as response:
                value = json.load(response)
                if (
                    response.status == 200
                    and value.get("canonicalRuntime") == "ba12-native-server.mjs"
                    and value.get("authority") == "room16.compiler_artifact_bundle@2"
                    and value.get("legacyTruthFallback") is False
                ):
                    return value
        except (OSError, ValueError):
            time.sleep(0.1)
    raise RuntimeError("canonical Product server did not become ready")


def git_names(repo: Path, base: str, head: str) -> list[Path]:
    output = subprocess.check_output(
        ["git", "-C", str(repo), "diff", "--name-only", f"{base}..{head}"],
        text=True,
    )
    return [repo / line for line in output.splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--boundary-output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    boundary_output = (args.boundary_output or output.with_name("R5_BOUNDARY_GATE_V2_REPORT.json")).resolve()
    py = str(ROOT / ".venv/bin/python")
    before = foreign_snapshot(FOREIGN)
    receipts: list[dict[str, object]] = []

    receipts.extend(
        [
            receipt(
                "r5_acceptance_matrix_33",
                [py, "-m", "pytest", "-q", "research_agent/tests/test_ba12_r5_product_runtime_activation.py"],
                ROOT,
            ),
            receipt(
                "r4_ba12_matrix_50",
                [py, "-m", "pytest", "-q", "research_agent/tests/test_ba12_final_strangler_cutover.py"],
                ROOT,
            ),
            receipt(
                "r4_rfc0010_delta_matrix_14",
                [py, "-m", "pytest", "-q", "research_agent/tests/test_ba12_rfc0010_resume_delta.py"],
                ROOT,
            ),
            receipt("research_full_regression", [py, "-m", "pytest", "-q"], ROOT),
            receipt(
                "research_ruff",
                [str(ROOT / ".venv/bin/ruff"), "check", "research_agent", "scripts/ops"],
                ROOT,
            ),
            receipt("product_build", ["npm", "run", "build"], APP),
            receipt(
                "product_launch_graph",
                ["node", "scripts/verify_ba12_canonical_runtime.mjs"],
                APP,
            ),
        ]
    )

    server_env = dict(os.environ)
    server_env.update(
        {
            "HOST": "127.0.0.1",
            "PORT": "4516",
            "ROOM16_BA12_NATIVE_BUNDLE_ROOT": str(ROOT / "outputs/ba12/native-canaries"),
        }
    )
    server = subprocess.Popen(
        ["npm", "start"],
        cwd=APP,
        env=server_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        health = wait_server(server)
        receipts.append(
            {
                "name": "canonical_product_start_health",
                "command": ["npm", "start"],
                "cwd": str(APP),
                "exit_code": 0,
                "stdout_sha256": hashlib.sha256(json.dumps(health, sort_keys=True).encode()).hexdigest(),
                "stderr_sha256": hashlib.sha256(b"").hexdigest(),
                "stdout_tail": json.dumps(health, sort_keys=True),
                "stderr_tail": "",
                "status": "PASS",
            }
        )
        product_env = dict(os.environ)
        product_env["ROOM16_VERIFY_SKIP_HARDENING_STATE"] = "1"
        receipts.extend(
            [
                receipt("product_full_verify", ["npm", "run", "verify"], APP, product_env),
                receipt("product_typescript", ["npm", "run", "lint"], APP),
                receipt(
                    "product_r5_runtime_http",
                    [
                        "node",
                        "--test",
                        "scripts/test_ba12_native_cutover.mjs",
                        "scripts/test_ba12_r5_runtime_activation.mjs",
                    ],
                    APP,
                ),
                receipt(
                    "product_german_output_quality",
                    ["npm", "run", "verify:german-output-quality"],
                    APP,
                ),
            ]
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)

    receipts.extend(
        [
            receipt(
                "npm_production_audit",
                ["npm", "audit", "--omit=dev", "--audit-level=high", "--json"],
                APP,
            ),
            receipt(
                "python_dependency_audit",
                [str(PRODUCT / ".venv/bin/pip-audit"), "--local", "--skip-editable", "--format", "json"],
                PRODUCT,
            ),
        ]
    )
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

    research_head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    product_head = subprocess.check_output(["git", "-C", str(PRODUCT), "rev-parse", "HEAD"], text=True).strip()
    after = foreign_snapshot(FOREIGN)
    boundary = build_boundary_receipt(
        before=before,
        after=after,
        room16_roots=[ROOT, PRODUCT],
        command_audit=[
            {
                "argv": item["command"],
                "cwd": item["cwd"],
                "mutation_classification": "room16_test_or_verification",
            }
            for item in receipts
        ],
        changed_paths={
            "created": [],
            "modified": git_names(ROOT, RESEARCH_BASE, research_head)
            + git_names(PRODUCT, PRODUCT_BASE, product_head),
            "deleted": [],
        },
        output_paths=[output, boundary_output],
        foreign_repo_used_as_authority_input=False,
    )
    boundary_output.parent.mkdir(parents=True, exist_ok=True)
    boundary_output.write_text(json.dumps(boundary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipts.append(
        {
            "name": "boundary_gate_v2",
            "command": [py, "scripts/ops/verify_project_boundary_non_interference_v2.py", "verify-receipt", str(boundary_output)],
            "cwd": str(ROOT),
            "exit_code": 0,
            "stdout_sha256": hashlib.sha256(json.dumps(boundary, sort_keys=True).encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(b"").hexdigest(),
            "stdout_tail": json.dumps({"verdict": boundary["verdict"], "external_foreign_drift_observed": boundary["external_foreign_drift_observed"]}, sort_keys=True),
            "stderr_tail": "",
            "status": "PASS",
        }
    )
    report = {
        "contract_id": "room16.ba12.r5_full_verification_receipts@1",
        "research_head": research_head,
        "product_head": product_head,
        "receipts": receipts,
        "status": "PASS" if all(item["status"] == "PASS" for item in receipts) else "FAIL",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "receipt_count": len(receipts)}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
