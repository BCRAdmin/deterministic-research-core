from research_agent.batch.batch_manifest import BatchManifest, BatchRunItem
from research_agent.batch.dashboard_adapter import build_dashboard_status


def test_dashboard_adapter_summary_counts():
    manifest = BatchManifest(
        batch_id="batch_test",
        as_of_date="2026-05-06",
        status="completed_with_issues",
        items=[
            BatchRunItem(ticker="AMZN", status="passed", quality_score=90),
            BatchRunItem(ticker="NVDA", status="repaired", quality_score=88),
            BatchRunItem(ticker="MDB", status="manual_review", quality_score=70),
            BatchRunItem(ticker="RKLB", status="data_unavailable"),
        ],
    )

    dashboard = build_dashboard_status(manifest)

    assert dashboard["summary"]["total"] == 4
    assert dashboard["summary"]["passed"] == 1
    assert dashboard["summary"]["repaired"] == 1
    assert dashboard["summary"]["manual_review"] == 1
    assert dashboard["summary"]["data_unavailable"] == 1
    assert dashboard["summary"]["avg_quality_score"] == (90 + 88 + 70) / 3
    assert dashboard["manual_review_queue"][0]["ticker"] == "MDB"


def test_dashboard_adapter_masks_accumulate_when_fcf_support_missing(tmp_path):
    audit_path = tmp_path / "audit_report.json"
    audit_path.write_text(
        """
        {
          "has_blocking_errors": true,
          "issues": [
            {
              "code": "MISSING_FCF_SUPPORT_FOR_ACCUMULATE",
              "severity": "error",
              "message": "Accumulate framing lacks FCF support."
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    manifest = BatchManifest(
        batch_id="batch_test",
        as_of_date="2026-05-08",
        status="completed_with_issues",
        items=[
            BatchRunItem(
                ticker="QCOM",
                status="manual_review",
                quality_score=87,
                final_rating="Accumulate",
                preferred_rating="Accumulate",
                artifacts={"audit_report.json": str(audit_path)},
            )
        ],
    )

    dashboard = build_dashboard_status(manifest)
    item = dashboard["items"][0]

    assert item["display_status"] == "Manual Review"
    assert item["final_rating"] == "Hold Pending FCF Support"
    assert item["preferred_rating"] == "Hold Pending FCF Support"
    assert item["display_rating"] == "Hold Pending FCF Support"
    assert item["display_action"] == "Accumulate only after FCF support"
    assert item["rating_display_reason"] == "MISSING_FCF_SUPPORT_FOR_ACCUMULATE"
    assert item["internal_final_rating"] == "Accumulate"
    assert item["internal_preferred_rating"] == "Accumulate"


def test_dashboard_adapter_masks_early_commercial_capital_intensive(tmp_path):
    audit_path = tmp_path / "audit_report.json"
    audit_path.write_text(
        """
        {
          "has_blocking_errors": true,
          "issues": [
            {
              "code": "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE",
              "severity": "warning",
              "message": "Early-commercial capital-intensive tech profile requires review."
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    manifest = BatchManifest(
        batch_id="batch_test",
        as_of_date="2026-05-15",
        status="completed_with_issues",
        items=[
            BatchRunItem(
                ticker="RKLB",
                status="manual_review",
                quality_score=78,
                final_rating="Hold",
                preferred_rating="Hold",
                counts={"early_commercial_capital_intensive_tech_count": 1},
                artifacts={"audit_report.json": str(audit_path)},
            )
        ],
    )

    dashboard = build_dashboard_status(manifest)
    item = dashboard["items"][0]

    assert dashboard["summary"]["early_commercial_capital_intensive_tech_count"] == 1
    assert item["display_status"] == "Manual Review"
    assert item["display_rating"] == "Manual Review / Hold Pending FCF and Execution Evidence"
    assert item["display_action"] == "Hold pending FCF path and execution evidence"
    assert item["rating_display_reason"] == "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE"
    assert item["internal_final_rating"] == "Hold"


def test_dashboard_adapter_surfaces_underweight_bias_and_reason_fields(tmp_path):
    publish_path = tmp_path / "publish_report.md"
    publish_path.write_text(
        "# SNOW Research Report\n\n## Final Rating & Action Plan\n\nFinal Rating: Hold with Underweight Bias.\n",
        encoding="utf-8",
    )
    audit_path = tmp_path / "audit_report.json"
    audit_path.write_text(
        """
        {
          "has_blocking_errors": false,
          "issues": [
            {
              "code": "MISSING_CURRENT_PERIOD_KPI_CONTEXT",
              "severity": "error",
              "message": "Current-period KPI context missing."
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    reconciliation_path = tmp_path / "reconciliation_warnings.json"
    reconciliation_path.write_text(
        """
        [
          {
            "code": "TRUE_SOURCE_VALUE_DISAGREEMENT",
            "severity": "warning",
            "count": 2
          }
        ]
        """,
        encoding="utf-8",
    )
    evidence_path = tmp_path / "evidence_report.md"
    evidence_path.write_text(
        "# Evidence\n\n## Warnings\n\n- MISSING_EVIDENCE_FOR_METRIC\n",
        encoding="utf-8",
    )
    manifest = BatchManifest(
        batch_id="batch_test",
        as_of_date="2026-05-08",
        status="completed_with_issues",
        items=[
            BatchRunItem(
                ticker="SNOW",
                status="passed",
                quality_score=95,
                final_rating="Hold",
                preferred_rating="Hold",
                counts={
                    "publish_valuation_sensitivity_present": 1,
                    "publish_action_plan_trigger_count": 3,
                },
                artifacts={
                    "publish_report.md": str(publish_path),
                },
            ),
            BatchRunItem(
                ticker="SNOW",
                status="manual_review",
                quality_score=95,
                final_rating="Hold",
                preferred_rating="Hold",
                counts={
                    "evidence_warnings": 1,
                    "reconciliation_warnings": 1,
                    "true_source_disagreements": 2,
                    "current_period_kpi_claim_count": 4,
                    "ticker_specific_kpi_claim_count": 4,
                    "substantive_claim_count": 16,
                    "mechanical_rating_language_count": 0,
                    "publish_valuation_sensitivity_present": 1,
                    "publish_action_plan_trigger_count": 3,
                },
                artifacts={
                    "publish_report.md": str(publish_path),
                    "audit_report.json": str(audit_path),
                    "reconciliation_warnings.json": str(reconciliation_path),
                    "evidence_report.md": str(evidence_path),
                },
            )
        ],
    )

    dashboard = build_dashboard_status(manifest)
    passed_item = dashboard["items"][0]
    item = dashboard["items"][1]

    assert passed_item["display_rating"] == "Hold with Underweight Bias"
    assert passed_item["external_display_rating"] == "Hold with Underweight Bias"
    assert item["manual_review_reasons"] == ["MISSING_CURRENT_PERIOD_KPI_CONTEXT", "TRUE_SOURCE_VALUE_DISAGREEMENT", "MISSING_EVIDENCE_FOR_METRIC"]
    assert item["evidence_warnings"] == 1
    assert item["reconciliation_warnings"] == 1
    assert item["true_source_disagreements"] == 2
    assert item["valuation_sensitivity_present"] is True
    assert item["action_plan_trigger_count"] == 3
