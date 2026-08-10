from __future__ import annotations

from research_agent.calibration.outcome_quality import (
    CalibrationStabilityReview,
    calculate_stability_review_sha256,
)
from research_agent.calibration.p6_promotion_gate import build_p6_human_promotion_gate
from research_agent.calibration.valuation_calibration import ValuationCalibrationReadiness


HASH = "sha256:" + "c" * 64


def _readiness(status="shadow_ready") -> ValuationCalibrationReadiness:
    return ValuationCalibrationReadiness(
        status=status,
        snapshot_count=75,
        eligible_snapshot_count=75,
        valid_matured_outcome_count=75,
        effective_sample_count=75,
        unique_issuer_count=25,
        sector_count=5,
    )


def _stability(status="human_review_required") -> CalibrationStabilityReview:
    report = CalibrationStabilityReview(
        status=status,
        valid_observation_count=75,
        unique_issuer_count=25,
        sector_count=5,
        market_phase_count=3,
        valuation_regime_count=3,
        directional_false_pass_count=10,
        directional_false_pass_rate=0.25,
        directional_false_block_count=8,
        directional_false_block_rate=0.228571,
        early_mean_excess_return=0.03,
        late_mean_excess_return=0.02,
        mean_excess_drift=-0.01,
        strata=[],
        blockers=[] if status == "human_review_required" else ["sample_missing"],
        definitions={
            "directional_false_pass": "fixture",
            "directional_false_block": "fixture",
            "mean_excess_drift": "fixture",
        },
        automatic_actions={
            "ratingChange": False,
            "weightChange": False,
            "methodChange": False,
            "modelRun": False,
            "reportPublish": False,
        },
        report_sha256=HASH,
    )
    return report.model_copy(update={"report_sha256": calculate_stability_review_sha256(report)})


def test_p6_gate_stays_blocked_without_independent_review_and_operator_signoff() -> None:
    gate = build_p6_human_promotion_gate(_readiness("not_ready"), _stability("not_ready"))
    assert gate.status == "blocked"
    assert "valuation_calibration_not_shadow_ready" in gate.blockers
    assert "independent_methodology_review_evidence_missing" in gate.blockers
    assert "operator_signoff_evidence_missing" in gate.blockers
    assert gate.live_activation_allowed is False
    assert all(value is False for value in gate.automatic_actions.values())


def test_complete_human_gate_still_requires_manual_code_promotion() -> None:
    gate = build_p6_human_promotion_gate(
        _readiness(),
        _stability(),
        methodology_review_evidence_sha256=HASH,
        independent_methodology_reviewer="Independent Methodology Reviewer",
        operator_signoff_evidence_sha256=HASH,
        operator_identity="Bjorn Rosinger",
        operator_decision="approve_manual_shadow_promotion_review",
    )
    assert gate.status == "human_gate_complete_manual_install_required"
    assert gate.blockers == []
    assert gate.live_activation_allowed is False
    assert gate.manual_code_promotion_required is True


def test_automation_identity_or_self_review_never_satisfies_gate() -> None:
    automation = build_p6_human_promotion_gate(
        _readiness(),
        _stability(),
        methodology_review_evidence_sha256=HASH,
        independent_methodology_reviewer="Codex Agent",
        operator_signoff_evidence_sha256=HASH,
        operator_identity="Codex Agent",
        operator_decision="approve_manual_shadow_promotion_review",
    )
    assert automation.status == "blocked"
    assert "independent_methodology_reviewer_invalid" in automation.blockers
    assert "operator_identity_invalid" in automation.blockers
    assert "operator_must_differ_from_methodology_reviewer" in automation.blockers


def test_changed_stability_review_invalidates_human_gate_binding() -> None:
    changed = _stability().model_copy(update={"mean_excess_drift": 0.99})
    gate = build_p6_human_promotion_gate(
        _readiness(),
        changed,
        methodology_review_evidence_sha256=HASH,
        independent_methodology_reviewer="Independent Methodology Reviewer",
        operator_signoff_evidence_sha256=HASH,
        operator_identity="Bjorn Rosinger",
        operator_decision="approve_manual_shadow_promotion_review",
    )
    assert gate.status == "blocked"
    assert "stability_review_hash_invalid" in gate.blockers
