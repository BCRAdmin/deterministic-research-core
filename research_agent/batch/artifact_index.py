from __future__ import annotations

from pathlib import Path
from typing import Union


ARTIFACT_NAMES = [
    "final_report.md",
    "publish_report.md",
    "final_repaired_report.md",
    "repaired_report.md",
    "draft_failed_audit.md",
    "manual_review_required.md",
    "internal_best_report.md",
    "data_packet.json",
    "source_registry.json",
    "metrics_packet.json",
    "validation_report.json",
    "audit_report.json",
    "decision_packet.json",
    "quality_score.json",
    "publish_report_quality_score.json",
    "analyst_claims.json",
    "fact_ledger.json",
    "evidence_ledger.json",
    "evidence_report.md",
    "canonical_financials.json",
    "reconciliation_report.md",
    "current_period_reconciliation_summary.md",
    "report_manifest.json",
    "outcome_report_60d.json",
]


def build_artifact_index(output_path: Union[str, Path]) -> dict[str, str]:
    base = Path(output_path)
    artifacts: dict[str, str] = {}
    for name in ARTIFACT_NAMES:
        path = base / name
        if path.exists():
            artifacts[name] = str(path)
    return artifacts
