from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_agent.capabilities.market_registry import (
    validate_market_capability_registry,
)
from research_agent.scale.change_detector import detect_authority_changes
from research_agent.scale.scale_contract import ScalePlanRequest, build_scale_plan, validate_scale_plan


RESEARCH_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
CONTRACT_ID = "room16.p5_technical_closure"
REQUIRED_RESEARCH_FILES = (
    "research_agent/capabilities/market_capabilities.json",
    "research_agent/capabilities/market_registry.py",
    "research_agent/scale/scale_contract.py",
    "research_agent/scale/change_detector.py",
    "research_agent/scale/__main__.py",
    "research_agent/tests/test_market_capability_registry.py",
    "research_agent/tests/test_scale_contract.py",
    "research_agent/tests/test_change_detector.py",
    "docs/ROOM16_P5_TECHNICAL_CLOSURE_2026-08-10.md",
)
REQUIRED_PRODUCT_FILES = (
    "room16-app/config/market-capabilities.snapshot.json",
    "room16-app/config/market-capabilities.binding.json",
    "room16-app/server-modules/market-capabilities.mjs",
    "room16-app/server-modules/adapter-readiness.mjs",
    "room16-app/scripts/verify_market_capability_snapshot.mjs",
    "room16-app/scripts/test_market_capability_snapshot.mjs",
    "room16-app/scripts/test_adapter_readiness.mjs",
)


def evaluate(
    *,
    research_root: Path = RESEARCH_ROOT,
    product_root: Path = PRODUCT_ROOT,
) -> dict[str, Any]:
    requirements = [
        _required_files(research_root, "research_capability_and_scale_surface", REQUIRED_RESEARCH_FILES),
        _required_files(product_root, "product_capability_surface", REQUIRED_PRODUCT_FILES),
        _registry_policy(research_root),
        _scale_contract(),
        _passive_change_contract(),
        _product_snapshot_binding(research_root, product_root),
        _product_hardening_coverage(product_root),
    ]
    failures = [item["id"] for item in requirements if item["status"] != "pass"]
    return {
        "contractId": CONTRACT_ID,
        "contractVersion": 1,
        "generatedAt": _utc_now(),
        "status": "technically_ready_for_human_verification" if not failures else "blocked",
        "technicalScopeComplete": not failures,
        "humanVerificationRequired": True,
        "scopeExpansionAllowed": False,
        "automaticMarketAdapterCreationAllowed": False,
        "automaticPaidProviderActivationAllowed": False,
        "automaticMonitoringAllowed": False,
        "counts": {
            "requirements": len(requirements),
            "passed": len(requirements) - len(failures),
            "blocked": len(failures),
        },
        "blockingIssues": failures,
        "requirements": requirements,
        "humanGates": [
            "real_100_item_operator_plan_review",
            "real_100_item_zero_cost_execution_review",
            "resume_and_failure_ledger_operator_review",
            "change_review_task_operator_review",
            "country_adapter_demand_decision",
            "paid_data_provider_go_if_ever_needed",
        ],
        "deferredOptions": {
            "edinet": "only_after_real_japan_case",
            "opendart": "only_after_real_korea_case",
            "fred": "only_after_claim_mapping_review",
            "tiingo_eod": "paused_until_data_and_cost_go",
            "eodhd": "reserve_only_after_verified_geographic_gap",
            "tradingview": "manual_plausibility_check_only",
            "scheduled_change_monitor": "deferred_until_core_analysis_human_verification",
        },
    }


def _required_files(root: Path, requirement_id: str, files: tuple[str, ...]) -> dict[str, Any]:
    missing = [relative for relative in files if not (root / relative).is_file()]
    return {
        "id": requirement_id,
        "status": "pass" if not missing else "fail",
        "evidence": {"requiredFileCount": len(files), "missingFiles": missing},
    }


def _registry_policy(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    supported: list[str] = []
    recognized: list[str] = []
    try:
        registry = validate_market_capability_registry(
            _read_object(root / "research_agent/capabilities/market_capabilities.json")
        )
        supported = sorted(
            item["code"] for item in registry["jurisdictions"] if item["status"] == "supported"
        )
        recognized = sorted(
            item["code"]
            for item in registry["jurisdictions"]
            if item["status"] == "recognized_unsupported"
        )
        if supported != ["HU", "US"]:
            errors.append("supported_market_baseline_invalid")
        if recognized != ["JP", "KR"]:
            errors.append("recognized_market_baseline_invalid")
        if any(registry["policies"].values()):
            errors.append("fail_closed_policy_invalid")
    except (RuntimeError, ValueError) as exc:
        errors.append(str(exc))
    return {
        "id": "canonical_market_provider_policy",
        "status": "pass" if not errors else "fail",
        "evidence": {"supported": supported, "recognizedUnsupported": recognized, "errors": errors},
    }


def _scale_contract() -> dict[str, Any]:
    errors: list[str] = []
    plan = build_scale_plan(
        ScalePlanRequest(
            as_of_date="2026-08-10",
            minimum_interval_seconds=0.25,
            items=[
                {"ticker": "KO", "jurisdiction": "US"},
                {"ticker": "MOL", "jurisdiction": "HU"},
                {"ticker": "7203", "jurisdiction": "JP"},
                {"ticker": "005930.KS", "jurisdiction": "KR"},
            ],
        )
    )
    try:
        validate_scale_plan(plan)
    except RuntimeError as exc:
        errors.append(str(exc))
    policy = plan.get("executionPolicy") or {}
    expected_false = (
        "modelRunsAllowed",
        "paidProvidersAllowed",
        "reportPublishingAllowed",
        "externalAutomationAllowed",
    )
    if plan.get("itemCount") != 4 or len(str(plan.get("planSha256") or "")) != 64:
        errors.append("scale_plan_identity_invalid")
    if policy.get("maxParallelJobs") != 1 or policy.get("confirmationRequired") is not True:
        errors.append("scale_execution_guard_invalid")
    if any(policy.get(key) is not False for key in expected_false):
        errors.append("scale_automatic_action_policy_invalid")
    if [item["status"] for item in plan["items"]] != ["ready", "ready", "blocked", "blocked"]:
        errors.append("scale_market_status_invalid")
    return {
        "id": "confirmed_zero_cost_scale_contract",
        "status": "pass" if not errors else "fail",
        "evidence": {
            "maximumItems": 1_000,
            "maxParallelJobs": policy.get("maxParallelJobs"),
            "planSha256": plan.get("planSha256"),
            "itemStatuses": [item["status"] for item in plan["items"]],
            "errors": errors,
        },
    }


def _passive_change_contract() -> dict[str, Any]:
    base = {
        "contract_id": "room16.research_authority_bundle",
        "contract_version": 2,
        "ticker": "KO",
        "as_of_date": "2026-08-09",
        "pipeline_version": "research_agent_v0.1.0",
        "analysis_allowed": True,
        "blocking_failures": [],
        "rating_permission": {"preferred_rating": "Hold"},
        "artifacts": {"data_packet": {"sha256": "a" * 64}},
    }
    changed = dict(base)
    changed["as_of_date"] = "2026-08-10"
    result = detect_authority_changes(base, changed)
    actions = result.get("automaticActions") or {}
    errors = []
    if result.get("reviewRequired") is not True or not result.get("reviewTask"):
        errors.append("change_review_task_missing")
    if not actions or any(value is not False for value in actions.values()):
        errors.append("automatic_change_action_enabled")
    return {
        "id": "passive_change_review_only",
        "status": "pass" if not errors else "fail",
        "evidence": {"automaticActions": actions, "errors": errors},
    }


def _product_snapshot_binding(research_root: Path, product_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    source = research_root / "research_agent/capabilities/market_capabilities.json"
    snapshot = product_root / "room16-app/config/market-capabilities.snapshot.json"
    binding_path = product_root / "room16-app/config/market-capabilities.binding.json"
    binding: dict[str, Any] = {}
    try:
        binding = _read_object(binding_path)
        source_hash = _sha(source)
        snapshot_hash = _sha(snapshot)
        if source_hash != snapshot_hash:
            errors.append("product_snapshot_differs_from_canonical_registry")
        if binding.get("sourceSha256") != source_hash:
            errors.append("source_hash_binding_invalid")
        if binding.get("snapshotSha256") != snapshot_hash:
            errors.append("snapshot_hash_binding_invalid")
        module = (product_root / "room16-app/server-modules/symbol-resolver.mjs").read_text(
            encoding="utf-8"
        )
        if "jurisdictionCapability" not in module or "ADAPTER_MARKETS" in module:
            errors.append("product_resolver_not_registry_bound")
    except (OSError, RuntimeError) as exc:
        errors.append(str(exc))
    return {
        "id": "product_registry_snapshot_binding",
        "status": "pass" if not errors else "fail",
        "evidence": {
            "sourceSha256": binding.get("sourceSha256"),
            "snapshotSha256": binding.get("snapshotSha256"),
            "errors": errors,
        },
    }


def _product_hardening_coverage(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        package = _read_object(root / "room16-app/package.json")
        scripts = package.get("scripts") or {}
        if "verify:market-capabilities" not in scripts:
            errors.append("market_capability_verifier_script_missing")
        if "verify:p5-technical-closure" not in scripts:
            errors.append("p5_closure_verifier_script_missing")
        hardening = (root / "room16-app/scripts/room16_night_hardening_loop.mjs").read_text(
            encoding="utf-8"
        )
        labels = set(re.findall(r'runCommand\("([^"]+)"', hardening))
        if "verify_market_capabilities" not in labels:
            errors.append("market_capability_hardening_missing")
        if "verify_p5_technical_closure" not in labels:
            errors.append("p5_closure_hardening_missing")
    except (OSError, RuntimeError) as exc:
        errors.append(str(exc))
    return {
        "id": "product_hardening_coverage",
        "status": "pass" if not errors else "fail",
        "evidence": {"errors": errors},
    }


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid_json:{path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"invalid_json_object:{path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Room16 P5 technical closure.")
    parser.add_argument("--research-root", type=Path, default=RESEARCH_ROOT)
    parser.add_argument("--product-root", type=Path, default=PRODUCT_ROOT)
    args = parser.parse_args()
    report = evaluate(
        research_root=args.research_root.expanduser().resolve(),
        product_root=args.product_root.expanduser().resolve(),
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["technicalScopeComplete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
