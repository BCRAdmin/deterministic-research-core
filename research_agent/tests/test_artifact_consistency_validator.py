import json
import zipfile
from pathlib import Path

from research_agent.batch.artifact_consistency_validator import (
    STALE_ARCHETYPE_ARTIFACT,
    STALE_DIAGNOSTIC_STATUS_REFERENCE,
    STALE_PUBLISHABILITY_ARTIFACT,
    STALE_RATING_ARTIFACT,
    ARTIFACT_SOURCE_OF_TRUTH_MISMATCH,
    QCOM_SUPERSEDED_BANNER,
    QCOM_SUPERSEDED_RAW_ACCUMULATE,
    validate_bundle_artifacts,
)
from research_agent.batch.review_bundle import REVIEW_BUNDLE_REQUIRED_FILES, create_chatgpt_review_bundle


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ticker_bundle(
    base: Path,
    ticker: str = "MSFT",
    *,
    archetype: str = "MEGA_CAP_PLATFORM",
    external: str = "Manual Review / Hold Pending Primary Evidence",
    publishable: bool = False,
    internal: str = "Hold",
    reasons: list[str] | None = None,
) -> Path:
    reasons = reasons or ["EVIDENCE_INCOMPLETE_FOR_GOLD"]
    ticker_dir = base / ticker
    ticker_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        ticker_dir / "report_manifest.json",
        {
            "ticker": ticker,
            "publishable": publishable,
            "internal_rating": internal,
            "external_display_rating": external,
            "public_rating": None if not publishable else internal,
            "company_archetype": archetype,
            "manual_review_reasons": reasons,
            "quality_score": 75,
        },
    )
    _write_json(
        ticker_dir / "decision_packet.json",
        {
            "ticker": ticker,
            "pipeline_decision": internal,
            "publishable": publishable,
            "internal_rating": internal,
            "external_display_rating": external,
            "public_rating": None if not publishable else internal,
            "company_archetype": archetype,
            "manual_review_reasons": reasons,
        },
    )
    _write_json(
        ticker_dir / "quality_score.json",
        {
            "ticker": ticker,
            "publishable": publishable,
            "internal_rating": internal,
            "external_display_rating": external,
            "public_rating": None if not publishable else internal,
            "company_archetype": archetype,
            "manual_review_reasons": reasons,
            "quality_score": 75,
        },
    )
    _write_json(
        base / "dashboard_status.json",
        {
            "batch_id": "fixture",
            "items": [
                {
                    "ticker": ticker,
                    "publishable": publishable,
                    "internal_rating": internal,
                    "external_display_rating": external,
                    "public_rating": None if not publishable else internal,
                    "company_archetype": archetype,
                    "manual_review_reasons": reasons,
                    "quality_score": 75,
                }
            ],
        },
    )
    (base / "pilot_review.md").write_text("# Pilot Review\n\n", encoding="utf-8")
    return ticker_dir


def test_msft_no_stale_deeptech_artifacts(tmp_path):
    ticker_dir = _ticker_bundle(tmp_path)
    (ticker_dir / "evidence_report.md").write_text("Current artifact says SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL.", encoding="utf-8")

    result = validate_bundle_artifacts(tmp_path)

    assert result.status == "artifact_inconsistent"
    assert STALE_ARCHETYPE_ARTIFACT in {issue.code for issue in result.issues}


def test_rating_display_mismatch_detected(tmp_path):
    ticker_dir = _ticker_bundle(tmp_path)
    (ticker_dir / "publish_report.md").write_text("Manual Review / Preliminary Underweight", encoding="utf-8")

    result = validate_bundle_artifacts(tmp_path)

    assert STALE_RATING_ARTIFACT in {issue.code for issue in result.issues}


def test_bare_preliminary_underweight_mismatch_detected(tmp_path):
    ticker_dir = _ticker_bundle(tmp_path)
    (ticker_dir / "pilot_review.md").write_text("MSFT is not a Preliminary Underweight case.", encoding="utf-8")

    result = validate_bundle_artifacts(tmp_path)

    assert STALE_RATING_ARTIFACT in {issue.code for issue in result.issues}


def test_publishability_mismatch_detected(tmp_path):
    _ticker_bundle(tmp_path, publishable=False)
    (tmp_path / "pilot_review.md").write_text("MSFT says publishable=true", encoding="utf-8")

    result = validate_bundle_artifacts(tmp_path)

    assert STALE_PUBLISHABILITY_ARTIFACT in {issue.code for issue in result.issues}


def test_legacy_marked_artifact_allowed(tmp_path):
    ticker_dir = _ticker_bundle(tmp_path)
    (ticker_dir / "evidence_report.md").write_text(
        "## Legacy / Historical Previous Run\n\nold false positive: SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL",
        encoding="utf-8",
    )

    result = validate_bundle_artifacts(tmp_path)

    assert result.status == "clean"
    assert result.legacy_ignored


def test_diagnostic_unmarked_stale_archetype_fails(tmp_path):
    ticker_dir = _ticker_bundle(tmp_path)
    (ticker_dir / "msft_gold_candidate_summary.md").write_text(
        "# Summary\n\nSPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL appears in the diagnostic summary.",
        encoding="utf-8",
    )

    result = validate_bundle_artifacts(tmp_path)

    assert STALE_ARCHETYPE_ARTIFACT in {issue.code for issue in result.issues}


def test_diagnostic_false_positive_fixed_reference_passes(tmp_path):
    ticker_dir = _ticker_bundle(tmp_path)
    (ticker_dir / "msft_gold_candidate_summary.md").write_text(
        "# Summary\n\n## False Positive Check\n\n"
        "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL was a false positive fixed and is not current.",
        encoding="utf-8",
    )

    result = validate_bundle_artifacts(tmp_path)

    assert result.status == "clean"
    assert result.legacy_ignored


def test_diagnostic_runtime_language_requires_diagnostics_heading(tmp_path):
    ticker_dir = _ticker_bundle(tmp_path)
    (ticker_dir / "msft_gold_candidate_summary.md").write_text(
        "# Summary\n\nProvider: ollama\nRun-Verzeichnis: /tmp/run",
        encoding="utf-8",
    )

    result = validate_bundle_artifacts(tmp_path)

    assert STALE_DIAGNOSTIC_STATUS_REFERENCE in {issue.code for issue in result.issues}


def test_diagnostic_runtime_language_under_diagnostics_heading_passes(tmp_path):
    ticker_dir = _ticker_bundle(tmp_path)
    (ticker_dir / "msft_gold_candidate_summary.md").write_text(
        "# Summary\n\n## Diagnostics\n\nProvider: ollama\nRun-Verzeichnis: /tmp/run",
        encoding="utf-8",
    )

    result = validate_bundle_artifacts(tmp_path)

    assert result.status == "clean"


def test_publish_report_internal_system_language_fails(tmp_path):
    ticker_dir = _ticker_bundle(tmp_path, publishable=False)
    (ticker_dir / "publish_report.md").write_text(
        "# Publish Stub\n\nProvider: ollama\nManual Review / Hold Pending Primary Evidence",
        encoding="utf-8",
    )

    result = validate_bundle_artifacts(tmp_path)

    assert ARTIFACT_SOURCE_OF_TRUTH_MISMATCH in {issue.code for issue in result.issues}


def test_msft_diagnostic_summary_clean(tmp_path):
    ticker_dir = _ticker_bundle(tmp_path)
    (ticker_dir / "msft_gold_candidate_summary.md").write_text(
        "# MSFT Gold Candidate Summary\n\n"
        "- Status: `manual_review`\n"
        "- current company_archetype: `MEGA_CAP_PLATFORM`\n"
        "- current external_display_rating: `Manual Review / Hold Pending Primary Evidence`\n"
        "- publishable: `false`\n"
        "- public_rating: `null`\n\n"
        "## False Positive Check\n\n"
        "`SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL` war ein früherer False Positive und ist nicht aktueller Status.\n\n"
        "## Diagnostics\n\n"
        "- `Provider:`\n- `Run-Verzeichnis`\n- `TradingAgents`\n",
        encoding="utf-8",
    )

    result = validate_bundle_artifacts(tmp_path)

    assert result.status == "clean"


def test_bundle_builder_blocks_inconsistent_bundle(tmp_path):
    batch = tmp_path / "batch"
    source = batch / "MSFT_source"
    source.mkdir(parents=True)
    artifacts = {}
    for name in REVIEW_BUNDLE_REQUIRED_FILES:
        path = source / name
        if name.endswith(".json"):
            payload = {"ticker": "MSFT"}
            if name == "report_manifest.json":
                payload.update({"publishable": False, "external_display_rating": "Manual Review / Hold Pending Primary Evidence", "company_archetype": "MEGA_CAP_PLATFORM"})
            if name == "quality_score.json":
                payload.update({"publishable": False, "external_display_rating": "Manual Review / Hold Pending Primary Evidence", "company_archetype": "MEGA_CAP_PLATFORM"})
            if name == "decision_packet.json":
                payload.update({"publishable": False, "internal_rating": "Hold", "external_display_rating": "Manual Review / Hold Pending Primary Evidence", "public_rating": None})
            path.write_text(json.dumps(payload), encoding="utf-8")
        elif name == "publish_report.md":
            path.write_text("Manual Review / Preliminary Underweight", encoding="utf-8")
        else:
            path.write_text("# artifact\n", encoding="utf-8")
        artifacts[name] = str(path)
    _write_json(
        batch / "dashboard_status.json",
        {
            "batch_id": "fixture",
            "items": [
                {
                    "ticker": "MSFT",
                    "publishable": False,
                    "internal_rating": "Hold",
                    "external_display_rating": "Manual Review / Hold Pending Primary Evidence",
                    "company_archetype": "MEGA_CAP_PLATFORM",
                    "artifacts": artifacts,
                }
            ],
        },
    )
    (batch / "pilot_review.md").write_text("# Review\n", encoding="utf-8")

    zip_path = create_chatgpt_review_bundle(batch, ["MSFT"])

    assert zip_path.name.endswith("_FAILED_ARTIFACT_CONSISTENCY.zip")
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "chatgpt_review_bundle/ARTIFACT_CONSISTENCY_ERRORS.md" in names


def test_clean_bundle_passes(tmp_path):
    ticker_dir = _ticker_bundle(tmp_path, ticker="GOOGL", archetype="MEGA_CAP_PLATFORM", external="Hold", publishable=True, internal="Hold", reasons=[])
    (ticker_dir / "publish_report.md").write_text("Public rating: Hold", encoding="utf-8")
    (ticker_dir / "evidence_report.md").write_text("# Evidence Report\n\nNo stale issues.", encoding="utf-8")

    result = validate_bundle_artifacts(tmp_path)

    assert result.status == "clean"


def test_qcom_display_rule_consistency(tmp_path):
    ticker_dir = _ticker_bundle(tmp_path, ticker="QCOM", archetype="SEMICONDUCTOR_AI_INFRA", external="Hold Pending FCF Support", publishable=False, internal="Accumulate", reasons=["MISSING_FCF_SUPPORT_FOR_ACCUMULATE"])
    (ticker_dir / "publish_report.md").write_text("Hold Pending FCF Support", encoding="utf-8")

    result = validate_bundle_artifacts(tmp_path)

    assert result.status == "clean"


def test_qcom_raw_accumulate_public_artifact_requires_superseded_banner(tmp_path):
    ticker_dir = _ticker_bundle(
        tmp_path,
        ticker="QCOM",
        archetype="SEMICONDUCTOR_AI_INFRA",
        external="Hold Pending FCF Support",
        publishable=False,
        internal="Accumulate",
        reasons=["MISSING_FCF_SUPPORT_FOR_ACCUMULATE"],
    )
    (ticker_dir / "publish_report.md").write_text("We rate QCOM Accumulate at the latest close.", encoding="utf-8")

    result = validate_bundle_artifacts(tmp_path)

    assert result.status == "artifact_inconsistent"
    assert QCOM_SUPERSEDED_RAW_ACCUMULATE in {issue.code for issue in result.issues}


def test_qcom_superseded_raw_accumulate_public_artifact_passes_with_banner(tmp_path):
    ticker_dir = _ticker_bundle(
        tmp_path,
        ticker="QCOM",
        archetype="SEMICONDUCTOR_AI_INFRA",
        external="Hold Pending FCF Support",
        publishable=False,
        internal="Accumulate",
        reasons=["MISSING_FCF_SUPPORT_FOR_ACCUMULATE"],
    )
    (ticker_dir / "publish_report.md").write_text(
        f"{QCOM_SUPERSEDED_BANNER}\n\nWe rate QCOM Accumulate at the latest close.",
        encoding="utf-8",
    )

    result = validate_bundle_artifacts(tmp_path)

    assert result.status == "clean"
    assert result.legacy_ignored


def test_rgti_preliminary_underweight_consistency(tmp_path):
    ticker_dir = _ticker_bundle(
        tmp_path,
        ticker="RGTI",
        archetype="SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL",
        external="Manual Review / Preliminary Underweight",
        publishable=False,
        internal="Preliminary Underweight",
        reasons=["SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE", "VENDOR_ONLY_HARD_METRICS"],
    )
    (ticker_dir / "publish_report.md").write_text("Manual Review / Preliminary Underweight\nSPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL", encoding="utf-8")

    result = validate_bundle_artifacts(tmp_path)

    assert result.status == "clean"
