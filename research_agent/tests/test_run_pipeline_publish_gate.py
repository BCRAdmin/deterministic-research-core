from types import SimpleNamespace

from research_agent.audit.audit_report import AuditIssue, AuditReport
from research_agent.run_pipeline import (
    _apply_readable_report_audit_failure,
    _empty_publish_quality_payload,
    _manual_review_report,
    _merge_audit_reports,
    _remove_unapproved_publish_artifacts,
)


def test_unapproved_report_leaves_no_publish_artifact(tmp_path):
    publish_report = tmp_path / "publish_report.md"
    publish_quality = tmp_path / "publish_report_quality_score.json"
    internal_report = tmp_path / "internal_best_report.md"
    publish_report.write_text("not approved", encoding="utf-8")
    publish_quality.write_text("{}", encoding="utf-8")
    internal_report.write_text("internal", encoding="utf-8")

    _remove_unapproved_publish_artifacts(tmp_path)

    assert not publish_report.exists()
    assert not publish_quality.exists()
    assert internal_report.read_text(encoding="utf-8") == "internal"
    assert _empty_publish_quality_payload()["publish_report_exists"] == 0


def test_manual_review_report_surfaces_active_reason_codes_once():
    report = _manual_review_report(
        "# CAT Research Report\n",
        [
            "EARNINGS_DATE_UNAVAILABLE",
            "BALANCE_SHEET_DATE_MISMATCH_EXCLUDED",
            "BALANCE_SHEET_DATE_MISMATCH_EXCLUDED",
        ],
    )

    assert report.startswith("# Manual Review Required")
    assert report.count("`BALANCE_SHEET_DATE_MISMATCH_EXCLUDED`") == 1
    assert "# CAT Research Report" in report


def test_manual_review_report_explains_machine_reason_codes():
    report = _manual_review_report(
        "# TSLA Research Report\n",
        ["TRUE_FINANCIAL_ANOMALY", "EARNINGS_DATE_UNAVAILABLE"],
        issue_details=[
            {
                "code": "TRUE_FINANCIAL_ANOMALY",
                "message": "P/FCF above 100x requires explicit explanation.",
            },
            {
                "code": "EARNINGS_DATE_UNAVAILABLE",
                "message": "Next earnings date is unavailable.",
            },
        ],
    )

    assert (
        "`TRUE_FINANCIAL_ANOMALY`: P/FCF above 100x requires explicit explanation."
        in report
    )
    assert (
        "`EARNINGS_DATE_UNAVAILABLE`: Next earnings date is unavailable."
        in report
    )


def test_readable_report_audit_failure_blocks_the_readable_surface():
    clean = AuditReport.from_issues([], ticker="CRM")
    failed = AuditReport.from_issues(
        [
            AuditIssue(
                severity="error",
                code="NUMERIC_MISMATCH",
                message="Readable report contains a stale revenue value.",
            )
        ],
        ticker="CRM",
    )
    merged = _merge_audit_reports(clean, failed)
    quality = SimpleNamespace(
        total_score=90,
        content_score=90,
        internal_research_quality_score=90,
        publishable=True,
        status="Pass",
        grade="A",
        score_explanation_short="",
        manual_review_reasons=[],
    )

    _apply_readable_report_audit_failure(quality, merged)

    assert merged.has_blocking_errors
    assert quality.publishable is False
    assert quality.total_score == 60
    assert quality.internal_research_quality_score == 60
    assert quality.manual_review_reasons == ["NUMERIC_MISMATCH"]
    assert quality.status == "Needs manual review"
