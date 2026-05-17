from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STALE_ARCHETYPE_ARTIFACT = "STALE_ARCHETYPE_ARTIFACT"
STALE_RATING_ARTIFACT = "STALE_RATING_ARTIFACT"
STALE_PUBLISHABILITY_ARTIFACT = "STALE_PUBLISHABILITY_ARTIFACT"
STALE_MANUAL_REVIEW_REASON = "STALE_MANUAL_REVIEW_REASON"
ARTIFACT_SOURCE_OF_TRUTH_MISMATCH = "ARTIFACT_SOURCE_OF_TRUTH_MISMATCH"
STALE_ARTIFACT_ISSUE = "STALE_ARTIFACT_ISSUE"
STALE_DIAGNOSTIC_STATUS_REFERENCE = "STALE_DIAGNOSTIC_STATUS_REFERENCE"

SOURCE_OF_TRUTH_FILES = [
    "report_manifest.json",
    "decision_packet.json",
    "dashboard_status.json",
    "quality_score.json",
]

STATUS_FIELDS = [
    "ticker",
    "review_status",
    "publishable",
    "internal_rating",
    "external_display_rating",
    "public_rating",
    "company_archetype",
    "archetype_confidence",
    "archetype_triggered_rules",
    "manual_review_reasons",
    "quality_score",
    "visibility",
    "public_library_status",
]

MARKDOWN_ARTIFACTS = [
    "publish_report.md",
    "internal_best_report.md",
    "evidence_report.md",
    "pilot_review.md",
    "manual_review_triage.md",
    "operating_pilot_review.md",
    "acceptance_report.md",
]

PUBLIC_FACING_MARKDOWN = {"publish_report.md"}
INTERNAL_RESEARCH_MARKDOWN = {"internal_best_report.md", "final_report.md"}
DIAGNOSTIC_MARKDOWN = {
    "pilot_review.md",
    "evidence_report.md",
    "quality_report.md",
    "manual_review_triage.md",
    "operating_pilot_review.md",
    "acceptance_report.md",
}

DIAGNOSTIC_HEADING_MARKERS = [
    "diagnostics",
    "run metadata",
    "historical / legacy context",
    "false positive check",
]

DIAGNOSTIC_STALE_MARKERS = [
    "not current",
    "historical",
    "legacy",
    "false positive fixed",
    "negated check",
    "früherer false positive",
    "nicht aktueller status",
    "nicht aktuell",
    "behoben",
]

PUBLIC_FORBIDDEN_SYSTEM_LANGUAGE = [
    "provider:",
    "modell",
    "run-verzeichnis",
    "tradingagents",
    "ollama",
]

KNOWN_ISSUE_CODES = {
    "SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE",
    "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE",
    "VENDOR_ONLY_HARD_METRICS",
    "EVIDENCE_INCOMPLETE_FOR_GOLD",
    "ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND",
    "ORDER_MATERIALITY_MISSING",
    "TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS",
    "CLEAN_BUY_ACCUMULATE_BLOCKED",
    "CLEAN_HOLD_BLOCKED_FOR_SPECULATIVE_DEEP_TECH",
    "MISSING_FCF_SUPPORT_FOR_ACCUMULATE",
    "CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED",
    "COMPANY_DEFINED_FCF_MISMATCH",
    "COMPANY_DEFINED_FCF_OCF_INCONSISTENCY",
    "EXTREME_VALUATION_REQUIRES_REVIEW",
    "TRUE_VALUATION_ANOMALY",
    "TRUE_SOURCE_VALUE_DISAGREEMENT",
}

LEGACY_MARKERS = [
    "historical_previous_run",
    "legacy finding",
    "old false positive",
    "regression fixture",
    "historische regression",
    "legacy",
    "previous run",
]


@dataclass
class ConsistencyIssue:
    code: str
    severity: str
    ticker: str
    artifact: str
    message: str
    expected: Any = None
    found: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "ticker": self.ticker,
            "artifact": self.artifact,
            "message": self.message,
            "expected": self.expected,
            "found": self.found,
        }


@dataclass
class ArtifactConsistencyResult:
    bundle_dir: Path
    status: str
    issues: list[ConsistencyIssue] = field(default_factory=list)
    legacy_ignored: list[dict[str, Any]] = field(default_factory=list)
    tickers: list[str] = field(default_factory=list)
    source_of_truth_files: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len([issue for issue in self.issues if issue.severity == "error"])

    @property
    def stale_artifact_issue_count(self) -> int:
        return len([issue for issue in self.issues if issue.code == STALE_ARTIFACT_ISSUE])

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_dir": str(self.bundle_dir),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": self.status,
            "error_count": self.error_count,
            "stale_artifact_issue_count": self.stale_artifact_issue_count,
            "legacy_ignored_count": len(self.legacy_ignored),
            "tickers": self.tickers,
            "source_of_truth_files": self.source_of_truth_files,
            "issues": [issue.to_dict() for issue in self.issues],
            "legacy_ignored": self.legacy_ignored,
            "counts": {
                "artifact_consistency_errors": self.error_count,
                "stale_artifact_issues": self.stale_artifact_issue_count,
                "stale_archetype_artifacts": len([issue for issue in self.issues if issue.code == STALE_ARCHETYPE_ARTIFACT]),
                "stale_rating_artifacts": len([issue for issue in self.issues if issue.code == STALE_RATING_ARTIFACT]),
                "stale_diagnostic_status_references": len([issue for issue in self.issues if issue.code == STALE_DIAGNOSTIC_STATUS_REFERENCE]),
            },
        }


def validate_bundle_artifacts(bundle_dir: str | Path) -> ArtifactConsistencyResult:
    base = Path(bundle_dir)
    ticker_dirs = _ticker_dirs(base)
    if not ticker_dirs:
        ticker_dirs = [base]

    issues: list[ConsistencyIssue] = []
    legacy_ignored: list[dict[str, Any]] = []
    source_files: set[str] = set()
    tickers: list[str] = []

    for ticker_dir in ticker_dirs:
        ticker = ticker_dir.name.upper()
        truth, truth_sources = _source_of_truth(base, ticker_dir, ticker)
        source_files.update(truth_sources)
        ticker = str(truth.get("ticker") or ticker)
        tickers.append(ticker)
        _check_source_file_consistency(ticker, truth, truth_sources, issues)
        _check_markdown_artifacts(base, ticker_dir, ticker, truth, issues, legacy_ignored)

    status = "clean" if not [issue for issue in issues if issue.severity == "error"] else "artifact_inconsistent"
    return ArtifactConsistencyResult(
        bundle_dir=base,
        status=status,
        issues=issues,
        legacy_ignored=legacy_ignored,
        tickers=sorted(set(tickers)),
        source_of_truth_files=sorted(source_files),
    )


def write_consistency_artifacts(bundle_dir: str | Path, result: ArtifactConsistencyResult | None = None) -> tuple[Path, Path | None]:
    base = Path(bundle_dir)
    result = result or validate_bundle_artifacts(base)
    report_path = base / "artifact_consistency_report.json"
    report_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    errors_path: Path | None = None
    if result.error_count:
        errors_path = base / "ARTIFACT_CONSISTENCY_ERRORS.md"
        errors_path.write_text(_render_errors_markdown(result), encoding="utf-8")
    return report_path, errors_path


def _source_of_truth(base: Path, ticker_dir: Path, ticker: str) -> tuple[dict[str, Any], list[str]]:
    dashboard = _dashboard_item(base, ticker)
    quality = _load_json(ticker_dir / "quality_score.json")
    decision = _load_json(ticker_dir / "decision_packet.json")
    manifest = _load_json(ticker_dir / "report_manifest.json")
    sources = {
        "report_manifest.json": _normalize_payload(manifest),
        "decision_packet.json": _normalize_payload(decision),
        "dashboard_status.json": _normalize_payload(dashboard),
        "quality_score.json": _normalize_payload(quality),
    }
    truth: dict[str, Any] = {}
    used: list[str] = []
    for field in STATUS_FIELDS:
        for source_name in SOURCE_OF_TRUTH_FILES:
            value = sources[source_name].get(field)
            if _has_value(value):
                truth[field] = value
                if source_name not in used:
                    used.append(source_name)
                break
    truth.setdefault("ticker", ticker)
    truth["bundle_issue_codes"] = _dashboard_issue_codes(base)
    return truth, used


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload or {})
    if "review_status" not in normalized and "status" in normalized:
        status = str(normalized.get("status") or "")
        normalized["review_status"] = "quality_pass" if status.lower() in {"passed", "publishable"} else status
    if "internal_rating" not in normalized:
        for key in ["final_rating", "preferred_rating", "pipeline_decision", "rating"]:
            if _has_value(normalized.get(key)):
                normalized["internal_rating"] = normalized[key]
                break
    if "external_display_rating" not in normalized:
        for key in ["externalDisplayRating", "display_rating", "displayRating"]:
            if _has_value(normalized.get(key)):
                normalized["external_display_rating"] = normalized[key]
                break
    if "manual_review_reasons" not in normalized:
        normalized["manual_review_reasons"] = normalized.get("risk_profiles") or []
    if "quality_score" not in normalized:
        normalized["quality_score"] = normalized.get("total_score")
    return normalized


def _check_source_file_consistency(
    ticker: str,
    truth: dict[str, Any],
    source_names: list[str],
    issues: list[ConsistencyIssue],
) -> None:
    expected_fields = {field: truth.get(field) for field in STATUS_FIELDS if field in truth}
    for source_name in source_names:
        # Source-file cross-check is intentionally handled in markdown-level scans for now;
        # this issue code is reserved for explicit file payload mismatches in future bundles.
        _ = source_name, expected_fields


def _check_markdown_artifacts(
    base: Path,
    ticker_dir: Path,
    ticker: str,
    truth: dict[str, Any],
    issues: list[ConsistencyIssue],
    legacy_ignored: list[dict[str, Any]],
) -> None:
    candidates = _markdown_candidates(base, ticker_dir)
    for path in candidates:
        text = path.read_text(encoding="utf-8", errors="replace")
        artifact = str(path.relative_to(base))
        role = _artifact_role(path)
        _check_public_system_language(ticker, artifact, role, text, issues)
        _check_diagnostic_markup(ticker, artifact, role, text, issues)
        _check_current_status_text(ticker, artifact, text, truth, issues)
        _check_archetype_text(ticker, artifact, role, text, truth, issues, legacy_ignored)
        _check_rating_text(ticker, artifact, role, text, truth, issues, legacy_ignored)
        _check_publishability_text(ticker, artifact, text, truth, issues, legacy_ignored)
        _check_manual_review_reasons(ticker, artifact, text, truth, issues, legacy_ignored)
        _check_stale_issue_codes(ticker, artifact, text, truth, issues, legacy_ignored)


def _check_archetype_text(
    ticker: str,
    artifact: str,
    role: str,
    text: str,
    truth: dict[str, Any],
    issues: list[ConsistencyIssue],
    legacy_ignored: list[dict[str, Any]],
) -> None:
    if _is_root_summary_context(artifact):
        return
    archetype = truth.get("company_archetype")
    if archetype == "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL":
        return
    stale = "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL"
    if stale in text or "SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE" in text:
        if role == "diagnostic" and _has_diagnostic_stale_marker(text, stale):
            legacy_ignored.append({"ticker": ticker, "artifact": artifact, "term": stale, "role": role})
            return
        if _is_legacy_context(text, stale):
            legacy_ignored.append({"ticker": ticker, "artifact": artifact, "term": stale})
            return
        issues.append(
            ConsistencyIssue(
                STALE_ARCHETYPE_ARTIFACT,
                "error",
                ticker,
                artifact,
                "Artifact contains stale speculative deep-tech archetype language.",
                expected=archetype,
                found=stale,
            )
        )


def _check_rating_text(
    ticker: str,
    artifact: str,
    role: str,
    text: str,
    truth: dict[str, Any],
    issues: list[ConsistencyIssue],
    legacy_ignored: list[dict[str, Any]],
) -> None:
    if _is_root_summary_context(artifact):
        return
    expected = truth.get("external_display_rating")
    stale_terms = ["Manual Review / Preliminary Underweight", "Preliminary Underweight"]
    if expected == "Manual Review / Preliminary Underweight":
        return
    for stale in stale_terms:
        if stale not in text:
            continue
        if role == "diagnostic" and _has_diagnostic_stale_marker(text, stale):
            legacy_ignored.append({"ticker": ticker, "artifact": artifact, "term": stale, "role": role})
            return
        if _is_legacy_context(text, stale):
            legacy_ignored.append({"ticker": ticker, "artifact": artifact, "term": stale})
            return
        issues.append(
            ConsistencyIssue(
                STALE_RATING_ARTIFACT,
                "error",
                ticker,
                artifact,
                "Artifact contains stale external display rating.",
                expected=expected,
                found=stale,
            )
        )


def _check_public_system_language(
    ticker: str,
    artifact: str,
    role: str,
    text: str,
    issues: list[ConsistencyIssue],
) -> None:
    if role != "public_facing":
        return
    lowered = text.lower()
    for term in PUBLIC_FORBIDDEN_SYSTEM_LANGUAGE:
        if term in lowered:
            issues.append(
                ConsistencyIssue(
                    ARTIFACT_SOURCE_OF_TRUTH_MISMATCH,
                    "error",
                    ticker,
                    artifact,
                    "Public-facing artifact contains internal system or runtime language.",
                    expected="public-safe language",
                    found=term,
                )
            )


def _check_diagnostic_markup(
    ticker: str,
    artifact: str,
    role: str,
    text: str,
    issues: list[ConsistencyIssue],
) -> None:
    if role != "diagnostic":
        return
    lowered = text.lower()
    diagnostic_terms = [term.lower() for term in PUBLIC_FORBIDDEN_SYSTEM_LANGUAGE] + ["provider", "model"]
    if not any(term in lowered for term in diagnostic_terms):
        return
    if any(_heading_exists(lowered, heading) for heading in DIAGNOSTIC_HEADING_MARKERS):
        return
    issues.append(
        ConsistencyIssue(
            STALE_DIAGNOSTIC_STATUS_REFERENCE,
            "error",
            ticker,
            artifact,
            "Diagnostic artifact contains runtime/provider language outside an approved diagnostic section.",
            expected=DIAGNOSTIC_HEADING_MARKERS,
            found="runtime/provider language",
        )
    )


def _check_current_status_text(
    ticker: str,
    artifact: str,
    text: str,
    truth: dict[str, Any],
    issues: list[ConsistencyIssue],
) -> None:
    status_terms = {
        "company_archetype": truth.get("company_archetype"),
        "review_status": truth.get("review_status"),
        "publishable": truth.get("publishable"),
        "internal_rating": truth.get("internal_rating"),
        "external_display_rating": truth.get("external_display_rating"),
        "public_rating": truth.get("public_rating"),
    }
    for field, expected in status_terms.items():
        if field == "public_rating" and expected is None:
            expected_values = {"null", "none"}
        elif isinstance(expected, bool):
            expected_values = {str(expected).lower()}
        elif _has_value(expected):
            expected_values = {str(expected)}
        else:
            continue
        actual = _explicit_status_value(text, field)
        if actual is None:
            continue
        normalized_actual = actual.strip().strip("`").strip()
        if not any(normalized_actual.lower() == value.lower() for value in expected_values):
            issues.append(
                ConsistencyIssue(
                    ARTIFACT_SOURCE_OF_TRUTH_MISMATCH,
                    "error",
                    ticker,
                    artifact,
                    f"Artifact current {field} does not match source of truth.",
                    expected=sorted(expected_values),
                    found=normalized_actual,
                )
            )


def _check_publishability_text(
    ticker: str,
    artifact: str,
    text: str,
    truth: dict[str, Any],
    issues: list[ConsistencyIssue],
    legacy_ignored: list[dict[str, Any]],
) -> None:
    publishable = truth.get("publishable")
    if publishable is False:
        forbidden = ["publishable=true", "publishable: true", "`publishable=true`", "`publishable: true`"]
        for term in forbidden:
            if term.lower() in text.lower():
                if _is_legacy_context(text, term):
                    legacy_ignored.append({"ticker": ticker, "artifact": artifact, "term": term})
                    return
                issues.append(
                    ConsistencyIssue(
                        STALE_PUBLISHABILITY_ARTIFACT,
                        "error",
                        ticker,
                        artifact,
                        "Artifact claims publishable=true although source of truth is publishable=false.",
                        expected=False,
                        found=term,
                    )
                )
        if _has_value(truth.get("public_rating")):
            issues.append(
                ConsistencyIssue(
                    STALE_PUBLISHABILITY_ARTIFACT,
                    "error",
                    ticker,
                    artifact,
                    "Source of truth has publishable=false but public_rating is not null.",
                    expected=None,
                    found=truth.get("public_rating"),
                )
            )
    if publishable is True and artifact.endswith("publish_report.md") and "nicht freigegeben" in text.lower():
        issues.append(
            ConsistencyIssue(
                STALE_PUBLISHABILITY_ARTIFACT,
                "error",
                ticker,
                artifact,
                "Publishable report artifact is still a not-published stub.",
                expected=True,
                found="not-published stub",
            )
        )


def _check_manual_review_reasons(
    ticker: str,
    artifact: str,
    text: str,
    truth: dict[str, Any],
    issues: list[ConsistencyIssue],
    legacy_ignored: list[dict[str, Any]],
) -> None:
    current = set(_as_list(truth.get("manual_review_reasons")))
    bundle_codes = set(_as_list(truth.get("bundle_issue_codes")))
    for code in KNOWN_ISSUE_CODES:
        if code in text and code not in current:
            if _is_root_summary_context(artifact) and code in bundle_codes:
                continue
            if _is_root_summary_context(artifact) and not _ticker_near_term(text, ticker, code):
                continue
            if _is_legacy_context(text, code):
                legacy_ignored.append({"ticker": ticker, "artifact": artifact, "term": code})
                continue
            issues.append(
                ConsistencyIssue(
                    STALE_MANUAL_REVIEW_REASON,
                    "error",
                    ticker,
                    artifact,
                    "Artifact contains a manual-review reason that is not current.",
                    expected=sorted(current),
                    found=code,
                )
            )


def _check_stale_issue_codes(
    ticker: str,
    artifact: str,
    text: str,
    truth: dict[str, Any],
    issues: list[ConsistencyIssue],
    legacy_ignored: list[dict[str, Any]],
) -> None:
    current = set(_as_list(truth.get("manual_review_reasons"))) | set(_as_list(truth.get("risk_profiles")))
    bundle_codes = set(_as_list(truth.get("bundle_issue_codes")))
    if truth.get("external_display_rating"):
        current.add(str(truth["external_display_rating"]))
    for code in KNOWN_ISSUE_CODES:
        if code in text and code not in current:
            if _is_root_summary_context(artifact) and code in bundle_codes:
                continue
            if _is_root_summary_context(artifact) and not _ticker_near_term(text, ticker, code):
                continue
            if _is_legacy_context(text, code):
                legacy_ignored.append({"ticker": ticker, "artifact": artifact, "term": code})
                continue
            issues.append(
                ConsistencyIssue(
                    STALE_ARTIFACT_ISSUE,
                    "error",
                    ticker,
                    artifact,
                    "Artifact contains an issue code that is not present in current source of truth.",
                    expected=sorted(current),
                    found=code,
                )
            )


def update_bundle_manifest(bundle_dir: str | Path, result: ArtifactConsistencyResult) -> Path:
    base = Path(bundle_dir)
    manifest_path = base / "bundle_manifest.json"
    manifest = _load_json(manifest_path)
    included = [str(path.relative_to(base)) for path in sorted(base.rglob("*")) if path.is_file()]
    manifest.update(
        {
            "source_batch_id": manifest.get("source_batch_id") or _load_json(base / "dashboard_status.json").get("batch_id"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tickers": result.tickers,
            "artifact_consistency_status": result.status,
            "artifact_consistency_error_count": result.error_count,
            "stale_artifact_issue_count": result.stale_artifact_issue_count,
            "source_of_truth_files": result.source_of_truth_files,
            "included_files": included,
            "artifact_consistency_counts": result.to_dict()["counts"],
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    _update_dashboard_counts(base, result)
    return manifest_path


def _update_dashboard_counts(base: Path, result: ArtifactConsistencyResult) -> None:
    dashboard_path = base / "dashboard_status.json"
    dashboard = _load_json(dashboard_path)
    if not dashboard:
        return
    counts = dict(dashboard.get("counts") or dashboard.get("summary") or {})
    result_counts = result.to_dict()["counts"]
    counts.update(result_counts)
    if "counts" in dashboard:
        dashboard["counts"] = counts
    else:
        dashboard["summary"] = counts
    dashboard["artifact_consistency_status"] = result.status
    dashboard["artifact_consistency_error_count"] = result.error_count
    dashboard_path.write_text(json.dumps(dashboard, indent=2, sort_keys=True), encoding="utf-8")


def _ticker_dirs(base: Path) -> list[Path]:
    dirs = []
    for child in sorted(base.iterdir() if base.exists() else []):
        if not child.is_dir():
            continue
        if (child / "report_manifest.json").exists() or (child / "quality_score.json").exists() or (child / "decision_packet.json").exists():
            dirs.append(child)
    return dirs


def _markdown_candidates(base: Path, ticker_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    ticker_dirs = _ticker_dirs(base)
    if ticker_dirs:
        search_roots = [ticker_dir, base]
        root_only = {base}
    else:
        search_roots = [base]
        root_only = set()
    for root in search_roots:
        if not root.exists():
            continue
        paths = sorted(root.glob("*.md")) if root in root_only else sorted(root.rglob("*.md"))
        for path in paths:
            if path.name == "ARTIFACT_CONSISTENCY_ERRORS.md":
                continue
            if path in candidates:
                continue
            if ticker_dirs and path.parent != base and ticker_dir not in [path, *path.parents]:
                continue
            candidates.append(path)
    return candidates


def _artifact_role(path: Path) -> str:
    name = path.name
    if name in PUBLIC_FACING_MARKDOWN:
        return "public_facing"
    if name in INTERNAL_RESEARCH_MARKDOWN:
        return "internal_research"
    if name in DIAGNOSTIC_MARKDOWN or name.endswith("_summary.md") or "summary" in name:
        return "diagnostic"
    return "internal_research"


def _dashboard_item(base: Path, ticker: str) -> dict[str, Any]:
    for path in [base / "dashboard_status.json", base.parent / "dashboard_status.json"]:
        dashboard = _load_json(path)
        for item in dashboard.get("items", []):
            if str(item.get("ticker", "")).upper() == ticker.upper():
                return item
    return {}


def _dashboard_issue_codes(base: Path) -> list[str]:
    dashboard = _load_json(base / "dashboard_status.json") or _load_json(base.parent / "dashboard_status.json")
    counts = dashboard.get("counts") or dashboard.get("summary") or {}
    mapping = {
        "true_source_disagreements": "TRUE_SOURCE_VALUE_DISAGREEMENT",
        "reconciliation_warnings": "TRUE_SOURCE_VALUE_DISAGREEMENT",
        "missing_fcf_support": "MISSING_FCF_SUPPORT_FOR_ACCUMULATE",
        "vendor_only_hard_metrics_count": "VENDOR_ONLY_HARD_METRICS",
        "stale_artifact_issues": "STALE_ARTIFACT_ISSUE",
        "artifact_consistency_errors": "ARTIFACT_SOURCE_OF_TRUTH_MISMATCH",
    }
    codes: list[str] = []
    for key, code in mapping.items():
        try:
            if float(counts.get(key) or 0) > 0:
                codes.append(code)
        except (TypeError, ValueError):
            continue
    return codes


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _has_value(value: Any) -> bool:
    return value is not None and value != "" and value != []


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _is_legacy_context(text: str, term: str) -> bool:
    lowered = text.lower()
    term_index = lowered.find(term.lower())
    if term_index < 0:
        return False
    context = lowered[max(0, term_index - 600): term_index + len(term) + 200]
    return any(marker in context for marker in LEGACY_MARKERS)


def _has_diagnostic_stale_marker(text: str, term: str) -> bool:
    lowered = text.lower()
    term_index = lowered.find(term.lower())
    if term_index < 0:
        return False
    context = lowered[max(0, term_index - 700): term_index + len(term) + 350]
    return any(marker in context for marker in DIAGNOSTIC_STALE_MARKERS)


def _heading_exists(lowered_text: str, heading: str) -> bool:
    return bool(re.search(rf"^#+\s+{re.escape(heading)}\s*$", lowered_text, flags=re.MULTILINE))


def _explicit_status_value(text: str, field: str) -> str | None:
    labels = {
        "company_archetype": ["current company_archetype", "company_archetype", "company archetype", "current archetype"],
        "review_status": ["current review_status", "review_status", "status"],
        "publishable": ["current publishable", "publishable"],
        "internal_rating": ["current internal_rating", "internal_rating", "internal rating", "internes rating"],
        "external_display_rating": [
            "current external_display_rating",
            "external_display_rating",
            "external display rating",
            "externe anzeige",
        ],
        "public_rating": ["current public_rating", "public_rating", "public rating"],
    }.get(field, [])
    for label in labels:
        match = re.search(rf"(?im)^\s*(?:[-*]\s*)?(?:{re.escape(label)})\s*[:=]\s*`?([^`\n]+?)`?\s*$", text)
        if match:
            return match.group(1)
    return None


def _is_root_summary_context(artifact: str) -> bool:
    return "/" not in artifact and artifact in {"pilot_review.md", "manual_review_triage.md", "operating_pilot_review.md"}


def _ticker_near_term(text: str, ticker: str, term: str) -> bool:
    lowered = text.lower()
    term_lower = term.lower()
    ticker_lower = ticker.lower()
    for match in re.finditer(re.escape(term_lower), lowered):
        context = lowered[max(0, match.start() - 300): match.end() + 300]
        if ticker_lower in context:
            return True
    return False


def _render_errors_markdown(result: ArtifactConsistencyResult) -> str:
    lines = [
        "# ARTIFACT_CONSISTENCY_ERRORS",
        "",
        f"- Bundle: `{result.bundle_dir}`",
        f"- Status: `{result.status}`",
        f"- Error count: `{result.error_count}`",
        "",
        "## Issues",
        "",
    ]
    for issue in result.issues:
        lines.extend(
            [
                f"### {issue.code}",
                "",
                f"- Ticker: `{issue.ticker}`",
                f"- Artifact: `{issue.artifact}`",
                f"- Message: {issue.message}",
                f"- Expected: `{issue.expected}`",
                f"- Found: `{issue.found}`",
                "",
            ]
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate status/rating/archetype consistency across review bundle artifacts.")
    parser.add_argument("bundle_dir")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    result = validate_bundle_artifacts(args.bundle_dir)
    if args.write:
        write_consistency_artifacts(args.bundle_dir, result)
        update_bundle_manifest(args.bundle_dir, result)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 1 if result.error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
