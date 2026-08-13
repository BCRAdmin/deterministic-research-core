"""Cross-artifact consistency checks for the Room16 quality verdict."""

from __future__ import annotations

import re


def verify_quality_state(
    *,
    quality_report,
    audit_report,
    semantic_invariant_report=None,
    visible_citation_completeness=None,
) -> dict:
    checks: list[dict[str, object]] = []

    def check(
        check_id: str,
        passed: bool,
        detail: str,
        *,
        blocking: bool = True,
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "status": "pass" if passed else "fail",
                "blocking": blocking,
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
    audit_missing_business_kpis: set[str] = set()
    for issue in audit_report.issues:
        if issue.code != "BUSINESS_MODEL_KPI_COVERAGE_INCOMPLETE":
            continue
        match = re.search(r"missing:\s*(.+)$", issue.message, re.IGNORECASE)
        if match:
            audit_missing_business_kpis.update(
                value.strip()
                for value in match.group(1).split(",")
                if value.strip()
            )
    quality_missing_business_kpis = set(quality_report.missing_business_kpis or [])
    check(
        "business_kpi_coverage_matches_canonical_audit",
        audit_missing_business_kpis == quality_missing_business_kpis,
        (
            f"canonical_audit_missing={sorted(audit_missing_business_kpis)} "
            f"quality_missing={sorted(quality_missing_business_kpis)}"
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
        if item["status"] != "pass" and item["blocking"]
    ]
    semantic_passed = bool(
        not semantic_invariant_report
        or semantic_invariant_report.get("semantic_integrity_passed") is True
    )
    citations_passed = bool(
        not visible_citation_completeness
        or visible_citation_completeness.get("status") == "pass"
    )
    semantic_numeric_audit_codes = {
        "MISSING_EVIDENCE_FOR_HARD_CLAIM",
        "NUMERIC_MISMATCH",
        "PERIOD_MISMATCH",
        "UNVERIFIED_HARD_METRIC",
    }
    semantic_numeric_audit_passed = not any(
        issue.code in semantic_numeric_audit_codes
        for issue in audit_report.issues
    )
    check(
        "rendered_numeric_lineage_complete",
        semantic_numeric_audit_passed,
        "Every rendered hard number has unique claim/fact/evidence/source lineage.",
        blocking=True,
    )
    failures = [
        str(item["check_id"])
        for item in checks
        if item["status"] != "pass" and item["blocking"]
    ]
    integrity_passed = not failures and semantic_passed and citations_passed
    internally_reviewable = integrity_passed and semantic_numeric_audit_passed
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
    quality_state = "passed" if integrity_passed else "blocked"
    internal_review_state = "ready" if internally_reviewable else "blocked"
    release_state = "candidate" if release_candidate else "blocked"
    publication_state = (
        "allowed"
        if publication_allowed
        else "awaiting_operator_review"
        if release_candidate
        else "blocked"
    )
    state_conflict = publication_allowed and not release_candidate
    check(
        "release_publication_state_consistent",
        not state_conflict,
        (
            f"release_state={release_state} publication_state={publication_state} "
            f"release_candidate={release_candidate} publication_allowed={publication_allowed}"
        ),
    )
    if state_conflict:
        integrity_passed = False
        quality_state = "blocked"
        internal_review_state = "blocked"
    failures = [
        str(item["check_id"])
        for item in checks
        if item["status"] != "pass" and item["blocking"]
    ]
    return {
        "contract_id": "room16.quality_state_integrity",
        "contract_version": 4,
        "status": "pass" if integrity_passed else "fail",
        "integrity_contract_passed": integrity_passed,
        "internally_reviewable": internally_reviewable,
        "release_candidate": release_candidate,
        "release_allowed": publication_allowed,
        "report_publishable": bool(quality_report.publishable),
        "publication_allowed": publication_allowed,
        "quality_state": quality_state,
        "internal_review_state": internal_review_state,
        "release_state": release_state,
        "publication_state": publication_state,
        "quality_status": quality_report.status,
        "checks": checks,
        "blocking_failures": [
            *failures,
            *([] if semantic_passed else ["semantic_invariant_report"]),
            *([] if citations_passed else ["visible_citation_completeness"]),
        ],
        "internal_review_blockers": (
            []
            if semantic_numeric_audit_passed
            else ["rendered_numeric_lineage_complete"]
        ),
    }
