#!/usr/bin/env python3
"""Verify the fail-closed BA12 R3 frozen BA3 live-receipt conflict."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from research_agent.semantic_compiler.source_frontend.contracts import (
    CompilePolicyIR,
    RetrievalReceiptIR,
    SourceAcquisitionItemIR,
)


ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
EVIDENCE = ROOT / "docs/compiler_foundation/rfcs/BA12_R3_LIVE_SOURCE_CONTRACT_CONFLICT_STOP.json"
CONTRACTS = ROOT / "research_agent/semantic_compiler/source_frontend/contracts.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _run_json(command: list[str]) -> dict[str, Any]:
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if process.returncode:
        raise RuntimeError(f"command failed: {command}: {process.stdout}: {process.stderr}")
    value = json.loads(process.stdout)
    if not isinstance(value, dict) or value.get("status") != "PASS":
        raise RuntimeError(f"command did not PASS: {command}")
    return value


def verify(product_repo: Path = PRODUCT) -> dict[str, Any]:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    bindings = evidence["bindings"]
    schema = RetrievalReceiptIR.model_json_schema()
    allowed = tuple(sorted(schema["properties"]["transport"]["enum"]))
    try:
        RetrievalReceiptIR(
            receipt_id="receipt.live",
            acquisition_id="acquisition.live",
            source_id="live-source",
            source_type="sec_companyfacts",
            provider_id="sec",
            original_locator="https://data.sec.gov/example.json",
            media_type="application/json",
            payload_sha256="0" * 64,
            payload_bytes=1,
            retrieved_at="2026-08-24T12:00:00Z",
            available_at="2026-08-24T12:00:00Z",
            transport="live_acquisition",
        )
    except ValidationError:
        live_rejected = True
    else:
        live_rejected = False
    policy_live_values = tuple(sorted(CompilePolicyIR.model_json_schema()["properties"]["network_mode"]["enum"]))
    acquisition_live_values = tuple(sorted(SourceAcquisitionItemIR.model_json_schema()["properties"]["retrieval_mode"]["enum"]))
    semantic = _run_json([".venv/bin/python", "scripts/ops/verify_semantic_compiler_wave_freeze.py", "--product-repo", str(product_repo), "--json"])
    rfc9 = _run_json([".venv/bin/python", "scripts/ops/verify_rfc0009_native_trust_freeze.py", "--product-repo", str(product_repo), "--json"])
    checks = {
        "evidence_contract": evidence.get("contract_id") == "room16.ba12.r3.live_source_contract_conflict_stop_evidence@1" and evidence.get("status") == "STOPPED_RFC_TRIGGER_REQUIRED",
        "compile_policy_live_representable": "live_acquisition" in policy_live_values,
        "source_plan_live_representable": "live_acquisition" in acquisition_live_values,
        "receipt_live_unrepresentable": allowed == ("offline_fixture", "offline_replay") and live_rejected,
        "frozen_contract_exact": _sha(CONTRACTS) == bindings["source_frontend_contract_file_sha256"],
        "semantic_wave_freeze": semantic.get("version_lock_sha256") == bindings["semantic_wave_version_lock_sha256"],
        "rfc0009_freeze": rfc9.get("freeze_sha256") == bindings["rfc0009_freeze_sha256"] and rfc9.get("ba12_resume_authorized") is True,
        "product_identity": _git(product_repo, "remote", "get-url", "origin") == "https://github.com/BCRAdmin/company-dossier-lab.git" and _git(product_repo, "rev-parse", bindings["product_commit"] + "^{tree}") == bindings["product_tree"] and subprocess.run(["git", "merge-base", "--is-ancestor", bindings["product_commit"], "HEAD"], cwd=product_repo).returncode == 0,
        "stop_semantics": evidence.get("stop_conditions") == [2, 4] and evidence["forbidden_actions_preserved"]["ba3_ba9_changed"] is False and evidence["forbidden_actions_preserved"]["product_changed"] is False and evidence["forbidden_actions_preserved"]["release"] is False and evidence["forbidden_actions_preserved"]["publication"] is False and evidence["forbidden_actions_preserved"]["deploy"] is False,
    }
    failed = sorted(key for key, value in checks.items() if not value)
    return {"contract_id": "room16.ba12.r3.live_source_contract_conflict_verification@1", "status": "PASS" if not failed else "FAIL", "diagnostic_code": evidence["diagnostic_code"], "allowed_receipt_transport_values": list(allowed), "required_transport_value": "live_acquisition", "checks": checks, "failed_checks": failed, "stop_conditions": evidence["stop_conditions"], "runtime_code_changed": False, "product_changed": False, "ready_for_independent_rereview": False, "ba12_implementation_ready": False, "ba12_frozen": False, "release_ready": False, "release_authorized": False, "publication_authorized": False, "deploy_authorized": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-repo", type=Path, default=PRODUCT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = verify(args.product_repo.resolve())
    except Exception as exc:
        result = {"contract_id": "room16.ba12.r3.live_source_contract_conflict_verification@1", "status": "FAIL", "error": f"{type(exc).__name__}:{exc}"}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
