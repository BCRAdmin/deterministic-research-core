"""Cross-artifact consistency checks for the Room16 quality verdict."""

from __future__ import annotations


def verify_quality_state(
    *,
    quality_report,
    audit_report,
    semantic_invariant_report=None,
    visible_citation_completeness=None,
) -> dict:
    checks: list[dict[str, object]] = []

    def check(check_id: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "check_id": check_id,
                "status": "pass" if passed else "fail",
                "blocking": True,
                "detail": detail,
            }
        )

    blocking_audit = bool(audit_report.has_blocking_errors)
    check(
        "blocking_audit_caps_internal_score",
        not blocking_audit
        or (
            quality_report.publishable is False
            and quality_report.internal_research_quality_score <= 60
        ),
        (
            f"blocking_audit={blocking_audit} publishable={quality_report.publishable} "
            f"internal_score={quality_report.internal_research_quality_score}"
        ),
    )
    check(
        "archetype_confidence_is_explainable",
        quality_report.archetype_confidence < 1.0
        or bool(quality_report.archetype_triggered_rules),
        (
            f"confidence={quality_report.archetype_confidence} "
            f"triggered_rules={len(quality_report.archetype_triggered_rules)}"
        ),
    )
    check(
        "business_kpi_coverage_is_consistent",
        quality_report.business_model_kpi_coverage_complete
        == (
            quality_report.business_model_kpi_gap_count == 0
            and not quality_report.missing_business_kpis
        ),
        (
            f"complete={quality_report.business_model_kpi_coverage_complete} "
            f"gap_count={quality_report.business_model_kpi_gap_count}"
        ),
    )
    mismatch_count = sum(
        issue.code == "COMPANY_DEFINED_FCF_MISMATCH"
        for issue in audit_report.issues
    )
    check(
        "fcf_mismatch_count_matches_audit",
        quality_report.company_defined_fcf_mismatch_count == mismatch_count,
        (
            f"quality_count={quality_report.company_defined_fcf_mismatch_count} "
            f"audit_count={mismatch_count}"
        ),
    )
    failures = [
        str(item["check_id"])
        for item in checks
        if item["status"] != "pass"
    ]
    semantic_passed = bool(
        not semantic_invariant_report
        or semantic_invariant_report.get("semantic_integrity_passed") is True
    )
    citations_passed = bool(
        not visible_citation_completeness
        or visible_citation_completeness.get("status") == "pass"
    )
    integrity_passed = not failures and semantic_passed and citations_passed
    internally_reviewable = integrity_passed
    release_candidate = bool(
        integrity_passed
        and not audit_report.has_blocking_errors
        and quality_report.publishable
        and quality_report.current_report_allowed
        and quality_report.grade in {"A", "B"}
    )
    publication_allowed = bool(
        release_candidate and quality_report.status == "publishable"
    )
    return {
        "contract_id": "room16.quality_state_integrity",
        "contract_version": 3,
        "status": "pass" if integrity_passed else "fail",
        "integrity_contract_passed": integrity_passed,
        "internally_reviewable": internally_reviewable,
        "release_candidate": release_candidate,
        "release_allowed": release_candidate,
        "report_publishable": bool(quality_report.publishable),
        "publication_allowed": publication_allowed,
        "quality_status": quality_report.status,
        "checks": checks,
        "blocking_failures": [
            *failures,
            *([] if semantic_passed else ["semantic_invariant_report"]),
            *([] if citations_passed else ["visible_citation_completeness"]),
        ],
    }
