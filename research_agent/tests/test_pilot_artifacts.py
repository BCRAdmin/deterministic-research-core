import json

from research_agent.batch.pilot_artifacts import (
    generate_manual_review_triage,
    generate_operating_pilot_review,
)


def test_manual_review_triage_and_operating_review(tmp_path):
    batch = tmp_path / "phase12_operating_pilot_050"
    batch.mkdir(parents=True)
    dashboard = {
        "batch_id": "phase12_operating_pilot_050",
        "items": [
            {
                "ticker": "GOOGL",
                "status": "passed",
                "quality_score": 95,
                "external_display_rating": "Hold",
                "manual_review_reasons": [],
                "evidence_warning_codes": [],
                "reconciliation_warning_codes": [],
                "counts": {
                    "hard_claim_evidence_ratio": 100,
                    "publish_valuation_sensitivity_present": 1,
                    "publish_action_plan_trigger_count": 3,
                },
            },
            {
                "ticker": "QCOM",
                "status": "manual_review",
                "quality_score": 87,
                "external_display_rating": "Hold Pending FCF Support",
                "manual_review_reasons": ["MISSING_FCF_SUPPORT_FOR_ACCUMULATE"],
                "evidence_warning_codes": [],
                "reconciliation_warning_codes": [],
                "counts": {
                    "hard_claim_evidence_ratio": 100,
                    "fcf_unavailable_block_count": 1,
                    "publish_valuation_sensitivity_present": 1,
                    "publish_action_plan_trigger_count": 3,
                },
            },
            {
                "ticker": "ANET",
                "status": "manual_review",
                "quality_score": 74,
                "external_display_rating": "Hold",
                "manual_review_reasons": ["TRUE_FINANCIAL_ANOMALY"],
                "evidence_warning_codes": [],
                "reconciliation_warning_codes": ["TRUE_SOURCE_VALUE_DISAGREEMENT"],
                "counts": {
                    "hard_claim_evidence_ratio": 100,
                    "true_anomaly": 1,
                    "publish_valuation_sensitivity_present": 1,
                    "publish_action_plan_trigger_count": 3,
                },
            },
        ],
        "manual_review_queue": [],
        "summary": {
            "passed": 1,
            "manual_review": 2,
            "failed": 0,
        },
    }
    (batch / "dashboard_status.json").write_text(json.dumps(dashboard), encoding="utf-8")

    md_path, json_path = generate_manual_review_triage(batch)
    assert md_path.exists()
    triage = json.loads(json_path.read_text(encoding="utf-8"))
    assert triage["count_by_reason_group"]["missing_fcf_support"] == 1
    assert triage["count_by_reason_group"]["true_anomaly"] == 1

    review_path = generate_operating_pilot_review(batch)
    review_text = review_path.read_text(encoding="utf-8")
    assert "Operating Pilot Review - phase12_operating_pilot_050" in review_text
    assert "pilotfaehig" in review_text
