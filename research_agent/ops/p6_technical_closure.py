from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_agent.calibration.outcome_quality import assess_calibration_stability
from research_agent.calibration.p6_promotion_gate import build_p6_human_promotion_gate
from research_agent.calibration.strategy_quality import assess_strategy_metrics
from research_agent.calibration.valuation_calibration import (
    MIN_EFFECTIVE_SAMPLES,
    MIN_SECTORS,
    MIN_UNIQUE_ISSUERS,
    VALUATION_CALIBRATION_HORIZON_TRADING_DAYS,
    ValuationCalibrationOutcome,
    ValuationCalibrationReadiness,
)
from research_agent.capabilities.market_registry import load_market_capability_registry


RESEARCH_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
CONTRACT_ID = "room16.p6_technical_closure"
REQUIRED_FILES = (
    "research_agent/calibration/valuation_calibration.py",
    "research_agent/calibration/valuation_outcome_workbench.py",
    "research_agent/calibration/retrospective_replay.py",
    "research_agent/calibration/outcome_quality.py",
    "research_agent/calibration/strategy_quality.py",
    "research_agent/calibration/p6_promotion_gate.py",
    "research_agent/tests/test_valuation_calibration.py",
    "research_agent/tests/test_valuation_outcome_workbench.py",
    "research_agent/tests/test_retrospective_replay.py",
    "research_agent/tests/test_outcome_quality.py",
    "research_agent/tests/test_strategy_quality.py",
    "research_agent/tests/test_p6_promotion_gate.py",
    "docs/VALUATION_CALIBRATION_V1.md",
    "docs/ROOM16_P6_TECHNICAL_CLOSURE_2026-08-10.md",
)


def evaluate(
    *,
    research_root: Path = RESEARCH_ROOT,
    product_root: Path = PRODUCT_ROOT,
) -> dict[str, Any]:
    requirements = [
        _required_files(research_root),
        _outcome_contract(),
        _stability_contract(),
        _strategy_contract(),
        _human_gate_contract(),
        _cost_and_runtime_gate(research_root),
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
        "performanceClaimsAllowed": False,
        "liveCalibrationActivationAllowed": False,
        "singleReportSharpeAllowed": False,
        "automaticRatingOrWeightChangeAllowed": False,
        "counts": {
            "requirements": len(requirements),
            "passed": len(requirements) - len(failures),
            "blocked": len(failures),
        },
        "blockingIssues": failures,
        "requirements": requirements,
        "humanAndCalendarGates": [
            "verified_total_return_instrument_and_benchmark_series",
            "minimum_75_effective_matured_observations",
            "minimum_25_issuers_and_5_sectors",
            "independent_classification_and_methodology_review",
            "signed_operator_shadow_promotion_review",
            "manual_code_promotion_after_new_audit",
            "approximately_252_trading_days_for_prospective_evidence",
        ],
    }


def _required_files(root: Path) -> dict[str, Any]:
    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    return {
        "id": "p6_contract_and_test_surface",
        "status": "pass" if not missing else "fail",
        "evidence": {"requiredFileCount": len(REQUIRED_FILES), "missingFiles": missing},
    }


def _outcome_contract() -> dict[str, Any]:
    fields = ValuationCalibrationOutcome.model_fields
    errors = []
    if VALUATION_CALIBRATION_HORIZON_TRADING_DAYS != 252:
        errors.append("valuation_horizon_not_252")
    if "instrument_max_drawdown" not in fields or "benchmark_max_drawdown" not in fields:
        errors.append("outcome_drawdown_fields_missing")
    if (MIN_EFFECTIVE_SAMPLES, MIN_UNIQUE_ISSUERS, MIN_SECTORS) != (75, 25, 5):
        errors.append("calibration_sample_policy_changed")
    return {
        "id": "verified_252d_total_return_and_drawdown_contract",
        "status": "pass" if not errors else "fail",
        "evidence": {
            "horizonTradingDays": VALUATION_CALIBRATION_HORIZON_TRADING_DAYS,
            "minimumEffectiveSamples": MIN_EFFECTIVE_SAMPLES,
            "minimumUniqueIssuers": MIN_UNIQUE_ISSUERS,
            "minimumSectors": MIN_SECTORS,
            "drawdownFields": ["instrument_max_drawdown", "benchmark_max_drawdown"],
            "errors": errors,
        },
    }


def _empty_readiness() -> ValuationCalibrationReadiness:
    return ValuationCalibrationReadiness(
        status="not_ready",
        snapshot_count=0,
        eligible_snapshot_count=0,
        valid_matured_outcome_count=0,
        effective_sample_count=0,
        unique_issuer_count=0,
        sector_count=0,
        readiness_reasons=[
            "minimum_effective_sample_count_not_met",
            "minimum_unique_issuer_count_not_met",
            "minimum_sector_coverage_not_met",
        ],
    )


def _stability_contract() -> dict[str, Any]:
    report = assess_calibration_stability([], [], _empty_readiness(), None)
    errors = []
    if report.status != "not_ready" or "classification_overlay_missing" not in report.blockers:
        errors.append("empty_stability_review_not_blocked")
    if report.live_activation_allowed is not False or any(report.automatic_actions.values()):
        errors.append("stability_review_automatic_action_enabled")
    return {
        "id": "sector_phase_regime_false_pass_and_drift_review",
        "status": "pass" if not errors else "fail",
        "evidence": {
            "statusWithoutEvidence": report.status,
            "definitions": report.definitions,
            "automaticActions": report.automatic_actions,
            "errors": errors,
        },
    }


def _strategy_contract() -> dict[str, Any]:
    review = assess_strategy_metrics(None, [], return_series_sha256=None)
    errors = []
    if review.status != "not_ready" or "portfolio_strategy_definition_missing" not in review.blockers:
        errors.append("undefined_strategy_not_blocked")
    if review.sharpe_ratio is not None:
        errors.append("sharpe_calculated_without_strategy")
    if review.single_report_metric_use_allowed or review.automatic_rating_use_allowed:
        errors.append("strategy_metric_scope_leak")
    return {
        "id": "portfolio_strategy_metric_boundary",
        "status": "pass" if not errors else "fail",
        "evidence": {"statusWithoutStrategy": review.status, "blockers": review.blockers, "errors": errors},
    }


def _human_gate_contract() -> dict[str, Any]:
    stability = assess_calibration_stability([], [], _empty_readiness(), None)
    gate = build_p6_human_promotion_gate(_empty_readiness(), stability)
    errors = []
    if gate.status != "blocked" or gate.live_activation_allowed is not False:
        errors.append("empty_human_gate_not_blocked")
    if not gate.manual_code_promotion_required or any(gate.automatic_actions.values()):
        errors.append("human_gate_automatic_promotion_enabled")
    return {
        "id": "independent_methodology_and_signed_operator_gate",
        "status": "pass" if not errors else "fail",
        "evidence": {
            "statusWithoutHumanEvidence": gate.status,
            "manualCodePromotionRequired": gate.manual_code_promotion_required,
            "automaticActions": gate.automatic_actions,
            "errors": errors,
        },
    }


def _cost_and_runtime_gate(root: Path) -> dict[str, Any]:
    errors = []
    registry = load_market_capability_registry()
    tiingo = next(item for item in registry["providers"] if item["providerId"] == "tiingo_eod")
    if tiingo["integrationStatus"] != "paused_no_cost" or tiingo["authorityUse"] is not False:
        errors.append("tiingo_not_paused")
    if registry["policies"]["automaticPaidProviderSelectionAllowed"] is not False:
        errors.append("automatic_paid_provider_selection_enabled")
    runtime_status_path = (
        root
        / ".runtime/valuation-calibration-v1/with-retrospective-replay/valuation_calibration_readiness.json"
    )
    observed = "not_present_safe"
    if runtime_status_path.is_file():
        try:
            runtime = json.loads(runtime_status_path.read_text(encoding="utf-8"))
            observed = str(runtime.get("status") or "unknown")
            if runtime.get("live_activation_allowed") is not False:
                errors.append("runtime_calibration_activation_not_false")
        except (OSError, json.JSONDecodeError):
            errors.append("runtime_calibration_status_invalid")
    return {
        "id": "zero_cost_provider_and_runtime_fail_closed",
        "status": "pass" if not errors else "fail",
        "evidence": {
            "tiingoStatus": tiingo["integrationStatus"],
            "runtimeReadinessStatus": observed,
            "errors": errors,
        },
    }


def _product_hardening_coverage(root: Path) -> dict[str, Any]:
    errors = []
    try:
        package = json.loads((root / "room16-app/package.json").read_text(encoding="utf-8"))
        if "verify:p6-technical-closure" not in (package.get("scripts") or {}):
            errors.append("p6_closure_npm_script_missing")
        hardening = (root / "room16-app/scripts/room16_night_hardening_loop.mjs").read_text(
            encoding="utf-8"
        )
        labels = set(re.findall(r'runCommand\("([^"]+)"', hardening))
        if "verify_p6_technical_closure" not in labels:
            errors.append("p6_closure_hardening_missing")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    return {
        "id": "product_p6_hardening_coverage",
        "status": "pass" if not errors else "fail",
        "evidence": {"errors": errors},
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Room16 P6 technical closure.")
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
