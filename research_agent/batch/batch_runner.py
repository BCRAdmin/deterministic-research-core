from __future__ import annotations

import argparse
import inspect
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from research_agent.batch.artifact_index import build_artifact_index
from research_agent.batch.batch_config import BatchConfig, BatchTickerConfig, load_batch_config
from research_agent.batch.batch_manifest import BatchManifest, BatchRunItem, save_batch_manifest
from research_agent.batch.batch_status import DATA_UNAVAILABLE, FAILED, final_batch_status, status_from_result
from research_agent.batch.dashboard_adapter import build_dashboard_status, save_dashboard_status
from research_agent.batch.display_policy import external_action_label, external_rating_label
from research_agent.batch.failure_router import classify_failure
from research_agent.batch.freshness import evaluate_price_freshness


class BatchRunner:
    def __init__(self, config: BatchConfig, pipeline_runner=None):
        self.config = config
        self.batch_dir = Path(config.output_dir) / config.batch_id
        self.batch_dir.mkdir(parents=True, exist_ok=True)
        self.pipeline_runner = pipeline_runner or _DefaultPipelineRunner(
            output_dir=self.batch_dir / "reports",
            pipeline_version=config.pipeline_version,
            batch_config=config,
        )

    def run(self) -> BatchManifest:
        manifest = self._init_manifest()
        self._save_manifest(manifest)
        self._write_dashboard_status(manifest)

        for ticker_config in self.config.tickers:
            self._update_item_status(manifest, ticker_config.ticker, "running")
            self._save_manifest(manifest)
            self._write_dashboard_status(manifest)

            try:
                result = self._run_pipeline(ticker_config)
                status = status_from_result(result)
                self._update_item_result(
                    manifest=manifest,
                    ticker=ticker_config.ticker,
                    status=status,
                    result=result,
                )
            except Exception as exc:  # noqa: BLE001 - batch runners must isolate ticker failures.
                failure_type = classify_failure(str(exc))
                self._update_item_status(
                    manifest=manifest,
                    ticker=ticker_config.ticker,
                    status=_status_from_failure_type(failure_type),
                    error_message=str(exc),
                    failure_type=failure_type,
                )

            manifest.status = final_batch_status(manifest.items)
            self._save_manifest(manifest)
            self._write_dashboard_status(manifest)

        manifest.finished_at = _utc_now()
        manifest.status = final_batch_status(manifest.items)
        self._save_manifest(manifest)
        self._write_dashboard_status(manifest)
        self._write_pilot_review(manifest)
        self._write_score_split_report(manifest)
        return manifest

    def _init_manifest(self) -> BatchManifest:
        return BatchManifest(
            batch_id=self.config.batch_id,
            as_of_date=self.config.as_of_date,
            batch_mode=self.config.batch_mode,
            started_at=_utc_now(),
            status="running",
            items=[
                BatchRunItem(ticker=item.ticker.upper(), status="pending")
                for item in self.config.tickers
            ],
        )

    def _run_pipeline(self, ticker_config: BatchTickerConfig):
        method = self.pipeline_runner.run if hasattr(self.pipeline_runner, "run") else self.pipeline_runner
        kwargs = {
            "ticker": ticker_config.ticker.upper(),
            "as_of_date": self.config.as_of_date,
            "mode": ticker_config.mode,
            "ticker_config": ticker_config,
            "batch_config": self.config,
            "output_dir": str(self.batch_dir / ticker_config.ticker.upper()),
        }
        return _call_with_supported_kwargs(method, kwargs)

    def _update_item_status(
        self,
        manifest: BatchManifest,
        ticker: str,
        status: str,
        error_message: Optional[str] = None,
        failure_type: Optional[str] = None,
    ) -> None:
        item = self._find_item(manifest, ticker)
        item.status = status
        item.error_message = error_message
        item.failure_type = failure_type

    def _update_item_result(self, manifest: BatchManifest, ticker: str, status: str, result) -> None:
        item = self._find_item(manifest, ticker)
        output_path = _result_output_path(result) or str(self.batch_dir / "reports" / ticker.upper() / self.config.as_of_date)
        artifacts = build_artifact_index(output_path)
        artifacts.update(_result_artifacts(result))
        report_manifest = _load_report_manifest_from_artifacts(artifacts)
        artifacts.update(_artifacts_from_report_manifest(report_manifest))

        item.status = status
        item.output_path = output_path
        item.quality_score = _result_quality_score(result, report_manifest, artifacts)
        item.artifacts = artifacts
        self._apply_freshness(item, report_manifest)
        item.final_rating = _result_rating(result, "final_rating", report_manifest)
        item.preferred_rating = _result_rating(result, "preferred_rating", report_manifest)
        item.publishable = _result_publishable(result, report_manifest, status)
        if item.current_report_allowed is False and self.config.batch_mode == "current_research":
            item.status = "manual_review"
            item.publishable = False
        item.error_message = _result_error_message(result)
        item.failure_type = classify_failure(item.error_message) if item.error_message else None
        item.counts = _counts_from_artifacts(artifacts)
        if item.stale_price_basis:
            item.counts["stale_price_basis_count"] = 1
        if item.historical_qa_only:
            item.counts["historical_qa_only_count"] = 1
        if item.current_report_allowed is False:
            item.counts["current_report_blocked_by_freshness_count"] = int(self.config.batch_mode == "current_research")

    def _apply_freshness(self, item: BatchRunItem, report_manifest: Optional[dict]) -> None:
        price_basis_date = _result_price_basis_date(report_manifest, item.artifacts)
        if not price_basis_date:
            item.price_basis_date = None
            item.data_freshness_status = "not_evaluated"
            item.stale_price_basis = False
            item.current_report_allowed = None
            item.historical_qa_only = False
            return
        freshness = evaluate_price_freshness(
            price_basis_date,
            batch_mode=self.config.batch_mode,
            reference_date=self.config.freshness_reference_date,
            max_trading_day_age=self.config.freshness_max_trading_days,
        )
        item.price_basis_date = freshness.price_basis_date
        item.data_freshness_status = freshness.data_freshness_status
        item.stale_price_basis = freshness.stale_price_basis
        item.current_report_allowed = freshness.current_report_allowed
        item.historical_qa_only = freshness.historical_qa_only

    def _find_item(self, manifest: BatchManifest, ticker: str) -> BatchRunItem:
        ticker = ticker.upper()
        for item in manifest.items:
            if item.ticker.upper() == ticker:
                return item
        raise KeyError(f"Ticker {ticker} not found in batch manifest.")

    def _save_manifest(self, manifest: BatchManifest) -> Path:
        return save_batch_manifest(manifest, self.batch_dir / "batch_manifest.json")

    def _write_dashboard_status(self, manifest: BatchManifest) -> Path:
        status = build_dashboard_status(manifest)
        return save_dashboard_status(status, self.batch_dir / "dashboard_status.json")

    def _write_pilot_review(self, manifest: BatchManifest) -> Path:
        markdown = _render_pilot_review(manifest)
        target = self.batch_dir / "pilot_review.md"
        target.write_text(markdown, encoding="utf-8")
        return target

    def _write_score_split_report(self, manifest: BatchManifest) -> Path:
        markdown = _render_score_split_report(manifest)
        target = self.batch_dir / "score_split_report.md"
        target.write_text(markdown, encoding="utf-8")
        return target


class _DefaultPipelineRunner:
    def __init__(self, output_dir: Path, pipeline_version: str, batch_config: Optional[BatchConfig] = None):
        self.output_dir = output_dir
        self.pipeline_version = pipeline_version
        self.batch_config = batch_config

    def run(self, ticker: str, as_of_date: str, mode: str, output_dir: Optional[str] = None):
        from research_agent.research_core.models.report_config import ReportConfig
        from research_agent.run_pipeline import run_research_pipeline

        output_base = Path(output_dir) if output_dir else self.output_dir / ticker.upper()
        config = ReportConfig(
            ticker=ticker,
            as_of_date=as_of_date,
            source_mode=mode,
            output_dir=str(output_base / "reports"),
            price_csv_dir=_batch_value(self.batch_config, "price_csv_dir"),
            price_start_date=_batch_value(self.batch_config, "price_start_date"),
            cik_records_path=_batch_value(self.batch_config, "cik_records_path"),
            sec_companyfacts_path=_companyfacts_path(self.batch_config, ticker),
            sec_user_agent=_batch_value(self.batch_config, "sec_user_agent"),
            earnings_calendar_path=_batch_value(self.batch_config, "earnings_calendar_path"),
            ir_release_dir=_batch_ir_release_dir(self.batch_config),
            batch_mode=_batch_value(self.batch_config, "batch_mode") or "current_research",
            freshness_reference_date=_batch_value(self.batch_config, "freshness_reference_date"),
            freshness_max_trading_days=int(_batch_value(self.batch_config, "freshness_max_trading_days") or 2),
        )
        try:
            run_research_pipeline(ticker=ticker, as_of_date=as_of_date, config=config)
        except FileNotFoundError as exc:
            if mode == "manual_packet_mode":
                fixture_result = _try_run_manual_fixture_case(ticker, as_of_date, output_base)
                if fixture_result is not None:
                    return fixture_result
            raise exc

        ticker_dir = output_base / "reports" / ticker.upper() / as_of_date
        artifacts = build_artifact_index(ticker_dir)
        report_manifest_path = ticker_dir / "report_manifest.json"
        if report_manifest_path.exists():
            artifacts["report_manifest.json"] = str(report_manifest_path)
        quality_path = ticker_dir / "quality_score.json"
        publishable = True
        if quality_path.exists():
            artifacts["quality_score.json"] = str(quality_path)
            quality_payload = json.loads(quality_path.read_text(encoding="utf-8"))
            publishable = bool(quality_payload.get("publishable", True))
        report_path = output_base / "reports" / f"{ticker.upper()}_{as_of_date}_report.md"
        if report_path.exists():
            artifacts["final_report.md"] = str(report_path)
        if (ticker_dir / "manual_review_required.md").exists():
            artifacts["manual_review_required.md"] = str(ticker_dir / "manual_review_required.md")
        return {
            "output_path": str(ticker_dir),
            "artifacts": artifacts,
            "publishable": publishable,
            "manual_review_required": not publishable,
        }


def _try_run_manual_fixture_case(ticker: str, as_of_date: str, output_base: Path) -> Optional[dict]:
    fixture_id = f"{ticker.lower()}_{as_of_date.replace('-', '_')}"
    fixture_path = Path("research_agent/tests/fixtures") / fixture_id
    if not fixture_path.exists():
        return None

    from research_agent.e2e.e2e_runner import E2ERunner
    from research_agent.e2e.golden_expectations import build_golden_case

    runner = E2ERunner(str(output_base))
    result = runner.run_case(build_golden_case(fixture_id, fixture_path.parent))
    case_output = output_base / fixture_id
    artifacts = build_artifact_index(case_output)
    return {
        "output_path": str(case_output),
        "artifacts": artifacts,
        "quality_score": result.quality_score,
        "decision_packet": result.decision_packet,
        "repaired": result.repaired,
        "final_status": result.final_status,
        "publishable": result.quality_score.publishable,
        "final_rating": result.decision_packet.rating_permission.preferred_rating.value,
        "preferred_rating": result.decision_packet.rating_permission.preferred_rating.value,
    }


def _batch_value(batch_config: Optional[BatchConfig], name: str) -> Optional[str]:
    if batch_config is None:
        return None
    return getattr(batch_config, name, None)


def _batch_ir_release_dir(batch_config: Optional[BatchConfig]) -> Optional[str]:
    configured = _batch_value(batch_config, "ir_release_dir")
    if configured:
        return configured
    if batch_config is None:
        return None
    inferred = Path("outputs/source_inputs") / batch_config.batch_id / "ir_releases"
    return str(inferred) if inferred.exists() else None


def _companyfacts_path(batch_config: Optional[BatchConfig], ticker: str) -> Optional[str]:
    directory = _batch_value(batch_config, "sec_companyfacts_dir")
    if not directory:
        return None
    path = Path(directory) / f"{ticker.upper()}.json"
    return str(path) if path.exists() else None


def _call_with_supported_kwargs(method, kwargs: dict):
    signature = inspect.signature(method)
    parameters = signature.parameters
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters.values()):
        return method(**kwargs)
    supported = {
        name: value
        for name, value in kwargs.items()
        if name in parameters
    }
    return method(**supported)


def _result_output_path(result) -> Optional[str]:
    return _get_value(result, "output_path") or _get_value(result, "output_dir") or _get_value(result, "artifact_dir")


def _result_artifacts(result) -> dict[str, str]:
    artifacts = _get_value(result, "artifacts")
    return dict(artifacts or {})


def _result_quality_score(result, report_manifest: Optional[dict], artifacts: Optional[dict[str, str]] = None) -> Optional[float]:
    quality = _get_value(result, "quality_score") or _get_value(result, "quality_report")
    if quality is not None:
        if isinstance(quality, (int, float)):
            return float(quality)
        total = _get_value(quality, "total_score")
        if total is not None:
            return float(total)
    if report_manifest and report_manifest.get("quality_score") is not None:
        return float(report_manifest["quality_score"])
    quality_path = (artifacts or _result_artifacts(result)).get("quality_score.json")
    if quality_path and Path(quality_path).exists():
        payload = json.loads(Path(quality_path).read_text(encoding="utf-8"))
        if payload.get("total_score") is not None:
            return float(payload["total_score"])
    return None


def _result_rating(result, field_name: str, report_manifest: Optional[dict]) -> Optional[str]:
    value = _get_value(result, field_name)
    if value is not None:
        return str(_enum_value(value))
    decision_packet = _get_value(result, "decision_packet")
    permission = _get_value(decision_packet, "rating_permission") if decision_packet is not None else None
    if field_name == "preferred_rating" and permission is not None:
        preferred = _get_value(permission, "preferred_rating")
        return str(_enum_value(preferred))
    if report_manifest and report_manifest.get(field_name):
        return str(report_manifest[field_name])
    if field_name == "final_rating" and report_manifest and report_manifest.get("preferred_rating"):
        return str(report_manifest["preferred_rating"])
    return None


def _result_publishable(result, report_manifest: Optional[dict], status: str) -> Optional[bool]:
    value = _get_value(result, "publishable")
    if value is not None:
        return bool(value)
    quality = _get_value(result, "quality_score") or _get_value(result, "quality_report")
    if quality is not None:
        quality_publishable = _get_value(quality, "publishable")
        if quality_publishable is not None:
            return bool(quality_publishable)
    if report_manifest and report_manifest.get("publishable") is not None:
        return bool(report_manifest["publishable"])
    if status in {"passed", "repaired"}:
        return True
    if status in {"manual_review", "failed", "data_unavailable"}:
        return False
    return None


def _result_price_basis_date(report_manifest: Optional[dict], artifacts: Optional[dict[str, str]] = None) -> Optional[str]:
    if report_manifest and report_manifest.get("price_basis_date"):
        return str(report_manifest["price_basis_date"])
    data_packet_path = (artifacts or {}).get("data_packet.json")
    if data_packet_path and Path(data_packet_path).exists():
        try:
            payload = json.loads(Path(data_packet_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        price_basis = payload.get("price_basis") or {}
        if price_basis.get("date"):
            return str(price_basis["date"])
    return None


def _result_error_message(result) -> Optional[str]:
    return _get_value(result, "error_message") or _get_value(result, "error")


def _status_from_failure_type(failure_type: str) -> str:
    if failure_type in {"data_error", "source_ingestion_error"}:
        return DATA_UNAVAILABLE
    return FAILED


def _load_report_manifest_from_artifacts(artifacts: dict[str, str]) -> Optional[dict]:
    manifest_path = artifacts.get("report_manifest.json")
    if not manifest_path:
        return None
    path = Path(manifest_path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _artifacts_from_report_manifest(report_manifest: Optional[dict]) -> dict[str, str]:
    if not report_manifest:
        return {}
    artifacts = {
        "report_manifest.json": _optional_path(report_manifest.get("report_manifest_path")),
        "final_report.md": _optional_path(report_manifest.get("final_report_path")),
        "metrics_packet.json": _optional_path(report_manifest.get("metrics_packet_path")),
        "validation_report.json": _optional_path(report_manifest.get("validation_report_path")),
        "decision_packet.json": _optional_path(report_manifest.get("decision_packet_path")),
        "audit_report.json": _optional_path(report_manifest.get("audit_report_path")),
    }
    metadata = report_manifest.get("metadata") or {}
    metadata_artifacts = {
        "data_packet.json": metadata.get("data_packet_path"),
        "source_registry.json": metadata.get("source_registry_path"),
        "quality_score.json": metadata.get("quality_score_path"),
        "internal_best_report.md": metadata.get("internal_best_report_path"),
        "analyst_claims.json": metadata.get("analyst_claims_path"),
        "fact_ledger.json": metadata.get("fact_ledger_path"),
        "evidence_ledger.json": metadata.get("evidence_ledger_path"),
        "evidence_report.md": metadata.get("evidence_report_path"),
        "canonical_financials.json": metadata.get("canonical_financials_path"),
        "reconciliation_report.md": metadata.get("reconciliation_report_path"),
        "reconciliation_warnings.json": metadata.get("reconciliation_warnings_path"),
        "current_period_reconciliation_summary.md": metadata.get("current_period_reconciliation_summary_path"),
    }
    artifacts.update(metadata_artifacts)
    return {
        name: str(path)
        for name, path in artifacts.items()
        if path and Path(path).exists()
    }


def _counts_from_artifacts(artifacts: dict[str, str]) -> dict[str, int]:
    counts = {
        "validation_errors": 0,
        "validation_warnings": 0,
        "audit_errors": 0,
        "audit_warnings": 0,
        "reconciliation_warnings": 0,
        "evidence_warnings": 0,
        "true_source_disagreements": 0,
        "ignored_frame_variants": 0,
        "canonical_metrics_created": 0,
        "earnings_confirmed_count": 0,
        "earnings_unavailable_count": 0,
        "earnings_within_10_trading_days_count": 0,
        "company_guidance_available_count": 0,
        "consensus_only_count": 0,
        "guidance_consensus_mismatch_count": 0,
        "hard_claims_without_evidence_count": 0,
        "vendor_only_hard_claim_count": 0,
        "source_ingestion_post_audit_block_count": 0,
        "publish_quality_score": 0,
        "internal_research_quality_score": 0,
        "data_confidence_score": 0,
        "claim_coverage_complete": 0,
        "claim_coverage_gap_count": 0,
        "unsupported_guidance_claims": 0,
        "unsupported_earnings_event_claims": 0,
        "analyst_claim_count": 0,
        "substantive_analyst_claim_count": 0,
        "substantive_claim_count": 0,
        "substantive_claim_ratio": 0,
        "generic_claim_count": 0,
        "data_limitation_claim_count": 0,
        "current_period_kpi_claim_count": 0,
        "current_period_kpi_metric_count": 0,
        "current_period_kpi_claim_count_main_body": 0,
        "current_kpi_appendix_only_count": 0,
        "missing_current_period_context_count": 0,
        "ticker_specific_kpi_claim_count": 0,
        "final_rating_rationale_quality": 0,
        "mechanical_rating_language_count": 0,
        "mechanical_rating_language_count_main_body": 0,
        "placeholder_business_context_count": 0,
        "publish_report_exists": 0,
        "publish_report_quality_score": 0,
        "publish_mechanical_language_count": 0,
        "publish_current_kpi_count": 0,
        "publish_evidence_appendix_exists": 0,
        "publish_claim_id_main_body_count": 0,
        "publish_valuation_sensitivity_present": 0,
        "publish_action_plan_trigger_count": 0,
        "fcf_ocf_inconsistency_count": 0,
        "company_defined_fcf_used": 0,
        "sec_derived_fcf_used": 0,
        "company_defined_fcf_mismatch_count": 0,
        "fcf_unavailable_block_count": 0,
        "evidence_mapped_claim_ratio": 0,
        "hard_claim_evidence_ratio": 0,
        "generic_claim_ratio": 0,
        "company_specific_claim_count": 0,
        "valuation_specific_claim_count": 0,
        "technical_specific_claim_count": 0,
        "rating_rationale_claim_count": 0,
        "content_completeness_score": 0,
        "financial_sanity_errors": 0,
        "period_bug": 0,
        "data_bug": 0,
        "true_anomaly": 0,
        "extreme_valuation_review": 0,
        "true_valuation_anomaly": 0,
        "guard_threshold_review": 0,
        "speculative_deep_tech_profile_count": 0,
        "early_commercial_capital_intensive_tech_count": 0,
        "accounting_gain_not_operating_turnaround_count": 0,
        "vendor_only_hard_metrics_count": 0,
        "order_materiality_missing_count": 0,
        "technical_overweight_in_thesis_count": 0,
        "stale_price_basis_count": 0,
        "historical_qa_only_count": 0,
        "current_report_blocked_by_freshness_count": 0,
    }
    _count_issue_file(
        artifacts.get("validation_report.json"),
        counts,
        error_key="validation_errors",
        warning_key="validation_warnings",
    )
    _count_issue_file(
        artifacts.get("audit_report.json"),
        counts,
        error_key="audit_errors",
        warning_key="audit_warnings",
    )
    _count_special_validation_issues(artifacts.get("validation_report.json"), counts)
    _count_special_audit_issues(artifacts.get("audit_report.json"), counts)
    _count_data_packet_status(artifacts.get("data_packet.json"), counts)
    reconciliation_path = artifacts.get("reconciliation_warnings.json")
    if reconciliation_path and Path(reconciliation_path).exists():
        warnings = json.loads(Path(reconciliation_path).read_text(encoding="utf-8"))
        for warning in warnings:
            code = warning.get("code")
            severity = warning.get("severity")
            if severity == "warning":
                counts["reconciliation_warnings"] += 1
            if code == "TRUE_SOURCE_VALUE_DISAGREEMENT":
                counts["true_source_disagreements"] += int(warning.get("count") or 1)
            if code in {"SOURCE_FRAME_VARIANT_IGNORED", "PERIOD_TYPE_MISMATCH_IGNORED"}:
                counts["ignored_frame_variants"] += int(warning.get("count") or 1)

    evidence_report_path = artifacts.get("evidence_report.md")
    if evidence_report_path and Path(evidence_report_path).exists():
        text = Path(evidence_report_path).read_text(encoding="utf-8")
        for code in {
            "MISSING_EVIDENCE_FOR_METRIC",
            "NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC",
            "VENDOR_SOURCE_USED_AS_PRIMARY",
            "MISSING_DATE_FOR_NEWS_EVENT",
            "GUIDANCE_CONSENSUS_CONFLATION",
        }:
            counts["evidence_warnings"] += text.count(code)

    canonical_path = artifacts.get("canonical_financials.json")
    if canonical_path and Path(canonical_path).exists():
        payload = json.loads(Path(canonical_path).read_text(encoding="utf-8"))
        counts["canonical_metrics_created"] = len(payload.get("metrics", []))
    _count_quality_content(artifacts.get("quality_score.json"), counts)
    _count_claims(artifacts.get("analyst_claims.json"), counts)
    return counts


def _count_special_validation_issues(path: Optional[str], counts: dict[str, int]) -> None:
    if not path or not Path(path).exists():
        return
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    for issue in payload.get("issues", []):
        if issue.get("code") == "FORWARD_EPS_GUIDANCE_MISMATCH":
            counts["guidance_consensus_mismatch_count"] += 1


def _count_special_audit_issues(path: Optional[str], counts: dict[str, int]) -> None:
    if not path or not Path(path).exists():
        return
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("has_blocking_errors"):
        counts["source_ingestion_post_audit_block_count"] += 1
    period_bug_flagged = False
    for issue in payload.get("issues", []):
        code = issue.get("code")
        if code == "MISSING_EVIDENCE_FOR_HARD_CLAIM":
            counts["hard_claims_without_evidence_count"] += 1
        elif code == "VENDOR_SOURCE_USED_AS_PRIMARY":
            counts["vendor_only_hard_claim_count"] += 1
        elif code == "UNSUPPORTED_GUIDANCE_CLAIM":
            counts["unsupported_guidance_claims"] += 1
        elif code == "UNSUPPORTED_EARNINGS_EVENT_CLAIM":
            counts["unsupported_earnings_event_claims"] += 1
        elif code == "PERIOD_DENOMINATOR_BUG":
            if not period_bug_flagged:
                counts["period_bug"] += 1
                period_bug_flagged = True
            counts["financial_sanity_errors"] += 1
        elif code == "TRUE_FINANCIAL_ANOMALY":
            counts["true_anomaly"] += 1
            counts["financial_sanity_errors"] += 1
        elif code == "EXTREME_VALUATION_REQUIRES_REVIEW":
            counts["extreme_valuation_review"] += 1
            counts["true_anomaly"] += 1
            counts["financial_sanity_errors"] += 1
        elif code == "TRUE_VALUATION_ANOMALY":
            counts["true_valuation_anomaly"] += 1
            counts["true_anomaly"] += 1
            counts["financial_sanity_errors"] += 1
        elif code == "GUARD_THRESHOLD_REVIEW":
            counts["guard_threshold_review"] += 1
        elif code == "CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED":
            if not period_bug_flagged:
                counts["period_bug"] += 1
                period_bug_flagged = True
        elif code == "COMPANY_DEFINED_FCF_MISMATCH":
            counts["company_defined_fcf_mismatch_count"] += 1
            counts["financial_sanity_errors"] += 1
        elif code == "FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT":
            counts["fcf_unavailable_block_count"] += 1
        elif code == "COMPANY_DEFINED_FCF_OCF_INCONSISTENCY":
            counts["fcf_ocf_inconsistency_count"] += 1
        elif code == "MISSING_CURRENT_PERIOD_CONTEXT":
            counts["missing_current_period_context_count"] += 1
        elif code == "SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE":
            counts["speculative_deep_tech_profile_count"] += 1
        elif code == "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE":
            counts["early_commercial_capital_intensive_tech_count"] += 1
        elif code == "ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND":
            counts["accounting_gain_not_operating_turnaround_count"] += 1
        elif code == "VENDOR_ONLY_HARD_METRICS":
            counts["vendor_only_hard_metrics_count"] += 1
        elif code == "ORDER_MATERIALITY_MISSING":
            counts["order_materiality_missing_count"] += 1
        elif code == "TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS":
            counts["technical_overweight_in_thesis_count"] += 1
        elif code in {"MISSING_CURRENT_PERIOD_KPI_CONTEXT", "AVGO_CURRENT_KPI_CONTEXT_REQUIRED"}:
            counts["missing_current_period_context_count"] += 1
        elif str(code or "").startswith("FINANCIAL_SANITY_"):
            counts["financial_sanity_errors"] += 1


def _count_quality_content(path: Optional[str], counts: dict[str, int]) -> None:
    if not path or not Path(path).exists():
        return
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    counts["publish_quality_score"] = int(payload.get("publish_quality_score") or payload.get("total_score") or 0)
    counts["internal_research_quality_score"] = int(payload.get("internal_research_quality_score") or 0)
    counts["data_confidence_score"] = int(payload.get("data_confidence_score") or 0)
    counts["content_completeness_score"] = int(payload.get("content_score") or 0)
    counts["claim_coverage_complete"] = int(bool(payload.get("claim_coverage_complete")))
    counts["claim_coverage_gap_count"] = len(payload.get("claim_coverage_gaps") or [])
    counts["analyst_claim_count"] = int(payload.get("analyst_claim_count") or counts.get("analyst_claim_count", 0))
    counts["substantive_analyst_claim_count"] = int(payload.get("substantive_analyst_claim_count") or 0)
    counts["substantive_claim_count"] = int(payload.get("substantive_claim_count") or counts["substantive_analyst_claim_count"])
    counts["substantive_claim_ratio"] = int(round(float(payload.get("substantive_claim_ratio") or 0) * 100))
    counts["evidence_mapped_claim_ratio"] = int(round(float(payload.get("evidence_mapped_claim_ratio") or 0) * 100))
    counts["hard_claim_evidence_ratio"] = int(round(float(payload.get("hard_claim_evidence_ratio") or 0) * 100))
    counts["generic_claim_count"] = int(payload.get("generic_claim_count") or 0)
    counts["data_limitation_claim_count"] = int(payload.get("data_limitation_claim_count") or 0)
    counts["current_period_kpi_claim_count"] = int(payload.get("current_period_kpi_claim_count") or 0)
    counts["current_period_kpi_metric_count"] = int(payload.get("current_period_kpi_metric_count") or 0)
    counts["current_period_kpi_claim_count_main_body"] = int(payload.get("current_period_kpi_claim_count_main_body") or 0)
    counts["current_kpi_appendix_only_count"] = int(payload.get("current_kpi_appendix_only_count") or 0)
    counts["missing_current_period_context_count"] = int(payload.get("missing_current_period_context_count") or counts.get("missing_current_period_context_count", 0))
    counts["ticker_specific_kpi_claim_count"] = int(payload.get("ticker_specific_kpi_claim_count") or 0)
    counts["final_rating_rationale_quality"] = int(payload.get("final_rating_rationale_quality") or 0)
    counts["mechanical_rating_language_count"] = int(payload.get("mechanical_rating_language_count") or 0)
    counts["mechanical_rating_language_count_main_body"] = int(payload.get("mechanical_rating_language_count_main_body") or 0)
    counts["placeholder_business_context_count"] = int(payload.get("placeholder_business_context_count") or 0)
    counts["publish_report_exists"] = int(payload.get("publish_report_exists") or 0)
    counts["publish_report_quality_score"] = int(payload.get("publish_report_quality_score") or 0)
    counts["publish_mechanical_language_count"] = int(payload.get("publish_mechanical_language_count") or 0)
    counts["publish_current_kpi_count"] = int(payload.get("publish_current_kpi_count") or 0)
    counts["publish_evidence_appendix_exists"] = int(payload.get("publish_evidence_appendix_exists") or 0)
    counts["publish_claim_id_main_body_count"] = int(payload.get("publish_claim_id_main_body_count") or 0)
    counts["publish_valuation_sensitivity_present"] = int(payload.get("publish_valuation_sensitivity_present") or 0)
    counts["publish_action_plan_trigger_count"] = int(payload.get("publish_action_plan_trigger_count") or 0)
    counts["fcf_ocf_inconsistency_count"] = int(payload.get("fcf_ocf_inconsistency_count") or counts.get("fcf_ocf_inconsistency_count", 0))
    counts["company_defined_fcf_used"] = int(payload.get("company_defined_fcf_used") or 0)
    counts["sec_derived_fcf_used"] = int(payload.get("sec_derived_fcf_used") or 0)
    counts["company_defined_fcf_mismatch_count"] = int(payload.get("company_defined_fcf_mismatch_count") or counts.get("company_defined_fcf_mismatch_count", 0))
    counts["fcf_unavailable_block_count"] = int(payload.get("fcf_unavailable_block_count") or counts.get("fcf_unavailable_block_count", 0))
    counts["generic_claim_ratio"] = int(round(float(payload.get("generic_claim_ratio") or 0) * 100))
    counts["company_specific_claim_count"] = int(payload.get("company_specific_claim_count") or 0)
    counts["valuation_specific_claim_count"] = int(payload.get("valuation_specific_claim_count") or 0)
    counts["technical_specific_claim_count"] = int(payload.get("technical_specific_claim_count") or 0)
    counts["rating_rationale_claim_count"] = int(payload.get("rating_rationale_claim_count") or 0)
    counts["speculative_deep_tech_profile_count"] = int(payload.get("speculative_deep_tech_profile_count") or counts.get("speculative_deep_tech_profile_count", 0))
    counts["early_commercial_capital_intensive_tech_count"] = int(payload.get("early_commercial_capital_intensive_tech_count") or counts.get("early_commercial_capital_intensive_tech_count", 0))
    counts["accounting_gain_not_operating_turnaround_count"] = int(payload.get("accounting_gain_not_operating_turnaround_count") or counts.get("accounting_gain_not_operating_turnaround_count", 0))
    counts["vendor_only_hard_metrics_count"] = int(payload.get("vendor_only_hard_metrics_count") or counts.get("vendor_only_hard_metrics_count", 0))
    counts["order_materiality_missing_count"] = int(payload.get("order_materiality_missing_count") or counts.get("order_materiality_missing_count", 0))
    counts["technical_overweight_in_thesis_count"] = int(payload.get("technical_overweight_in_thesis_count") or counts.get("technical_overweight_in_thesis_count", 0))
    if payload.get("company_archetype"):
        counts["company_archetype_present"] = 1
    if payload.get("stale_price_basis"):
        counts["stale_price_basis_count"] = 1
    if payload.get("historical_qa_only"):
        counts["historical_qa_only_count"] = 1
    if payload.get("current_report_allowed") is False and payload.get("freshness_issue_code"):
        counts["current_report_blocked_by_freshness_count"] = 1


def _count_claims(path: Optional[str], counts: dict[str, int]) -> None:
    if not path or not Path(path).exists():
        return
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    counts["analyst_claim_count"] = len(payload)
    if payload:
        mapped = sum(1 for claim in payload if claim.get("evidence_ids"))
        hard = [
            claim for claim in payload
            if claim.get("claim_type") in {"financial_metric", "valuation_metric", "technical_metric", "price_data"}
        ]
        hard_mapped = sum(1 for claim in hard if claim.get("evidence_ids"))
        counts["evidence_mapped_claim_ratio"] = int(round((mapped / len(payload)) * 100))
        counts["hard_claim_evidence_ratio"] = int(round(((hard_mapped / len(hard)) if hard else 1.0) * 100))
        if counts.get("substantive_claim_count", 0) == 0 and counts.get("substantive_analyst_claim_count", 0):
            counts["substantive_claim_count"] = counts["substantive_analyst_claim_count"]


def _count_data_packet_status(path: Optional[str], counts: dict[str, int]) -> None:
    if not path or not Path(path).exists():
        return
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    event = payload.get("next_events") or {}
    guidance = payload.get("company_guidance_eps")
    consensus = payload.get("forward_eps")
    if event.get("confirmed") and event.get("next_earnings_date"):
        counts["earnings_confirmed_count"] += 1
        if _within_days(payload.get("as_of_date"), event.get("next_earnings_date"), 10):
            counts["earnings_within_10_trading_days_count"] += 1
    else:
        counts["earnings_unavailable_count"] += 1
    if guidance:
        counts["company_guidance_available_count"] += 1
    elif consensus:
        counts["consensus_only_count"] += 1


def _within_days(start: Optional[str], end: Optional[str], days: int) -> bool:
    if not start or not end:
        return False
    try:
        from datetime import date

        start_date = date.fromisoformat(start[:10])
        end_date = date.fromisoformat(end[:10])
    except ValueError:
        return False
    return 0 <= (end_date - start_date).days <= days


def _count_issue_file(path: Optional[str], counts: dict[str, int], error_key: str, warning_key: str) -> None:
    if not path or not Path(path).exists():
        return
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    for issue in payload.get("issues", []):
        if issue.get("severity") == "error":
            counts[error_key] += 1
        elif issue.get("severity") == "warning":
            counts[warning_key] += 1


def _optional_path(value) -> Optional[str]:
    return str(value) if value else None


def _get_value(obj, name: str):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _enum_value(value):
    return getattr(value, "value", value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _render_pilot_review(manifest: BatchManifest) -> str:
    total = len(manifest.items)
    quality_scores = [item.quality_score for item in manifest.items if item.quality_score is not None]
    avg_quality = (sum(quality_scores) / len(quality_scores)) if quality_scores else None
    median_quality = _median(quality_scores)
    repaired = sum(1 for item in manifest.items if item.status == "repaired")
    manual_review = sum(1 for item in manifest.items if item.status == "manual_review")
    data_unavailable = sum(1 for item in manifest.items if item.status == "data_unavailable")
    failed = sum(1 for item in manifest.items if item.status == "failed")
    repair_rate = repaired / total if total else 0
    manual_review_rate = manual_review / total if total else 0
    counts = _aggregate_item_counts(manifest)
    best_score = max(quality_scores) if quality_scores else None
    worst_score = min(quality_scores) if quality_scores else None
    best = [item.ticker for item in manifest.items if item.quality_score == best_score]
    worst = [item.ticker for item in manifest.items if item.quality_score == worst_score]
    old_source_disagreements = _baseline_source_disagreements(manifest.batch_id)
    old_ignored_variants = _baseline_ignored_variants(manifest.batch_id)
    validation_issues = _issue_code_counts(manifest, "validation_report.json")
    audit_issues = _issue_code_counts(manifest, "audit_report.json")
    reconciliation_issues = _reconciliation_code_counts(manifest)
    evidence_issues = _evidence_code_counts(manifest)
    worst_data_quality = _rank_data_quality(manifest, reverse=False)[:5]
    best_data_quality = _rank_data_quality(manifest, reverse=True)[:5]
    insufficient = [
        item.ticker
        for item in manifest.items
        if item.status in {"failed", "manual_review", "data_unavailable"}
        or (item.quality_score is not None and item.quality_score < 85)
        or (item.counts or {}).get("validation_errors", 0) > 0
        or (item.counts or {}).get("audit_errors", 0) > 0
    ]
    recommendation = _pilot_recommendation(
        failed=failed,
        manual_review=manual_review,
        avg_quality=avg_quality,
        true_disagreements=counts.get("true_source_disagreements", 0),
    )

    lines = [
        f"# Pilot Review - {manifest.batch_id}",
        "",
        f"- As-of date: `{manifest.as_of_date}`",
        f"- Batch status: `{manifest.status}`",
        f"- Tickers: `{total}`",
        "",
        "## Status Summary",
        "",
        f"- Passed: `{sum(1 for item in manifest.items if item.status == 'passed')}`",
        f"- Repaired: `{repaired}`",
        f"- Manual review: `{manual_review}`",
        f"- Data unavailable: `{data_unavailable}`",
        f"- Failed: `{failed}`",
        f"- Average quality score: `{avg_quality}`",
        f"- Median quality score: `{median_quality}`",
        f"- Lowest quality score: `{worst_score}`",
        f"- Repair rate: `{repair_rate:.1%}`",
        f"- Manual review rate: `{manual_review_rate:.1%}`",
        "",
        "## Before / After Reconciliation",
        "",
    ]
    if old_source_disagreements is not None:
        lines.append(f"- Old `SOURCE_VALUE_DISAGREEMENT`: `{old_source_disagreements}`")
    else:
        lines.append("- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`")
    if old_ignored_variants is not None:
        lines.append(f"- Old ignored frame / period variants: `{old_ignored_variants}`")
    lines.extend([
        f"- New `true_source_disagreements`: `{counts.get('true_source_disagreements', 0)}`",
        f"- Ignored frame / period variants: `{counts.get('ignored_frame_variants', 0)}`",
        "",
        "## Dashboard Counts",
        "",
    ])
    for key in sorted(counts):
        lines.append(f"- `{key}`: `{counts[key]}`")

    lines.extend([
        "",
        "## Frequent Issues",
        "",
        "### Validation Issues",
        "",
    ])
    lines.extend(_format_counter(validation_issues))
    lines.extend([
        "",
        "### Audit Issues",
        "",
    ])
    lines.extend(_format_counter(audit_issues))
    lines.extend([
        "",
        "### Evidence Issues",
        "",
    ])
    lines.extend(_format_counter(evidence_issues))
    lines.extend([
        "",
        "### Reconciliation Warnings / Info",
        "",
    ])
    lines.extend(_format_counter(reconciliation_issues))

    lines.extend([
        "",
        "## Ticker Results",
        "",
        "| Ticker | Status | Quality | External Rating | External Action | True Disagreements | Ignored Variants |",
        "|---|---|---:|---|---|---:|---:|",
    ])
    for item in manifest.items:
        item_counts = item.counts or {}
        rating = external_rating_label(item)
        action = external_action_label(item)
        lines.append(
            f"| {item.ticker} | {item.status} | {item.quality_score} | {rating} | {action} | "
            f"{item_counts.get('true_source_disagreements', 0)} | {item_counts.get('ignored_frame_variants', 0)} |"
        )

    lines.extend([
        "",
        "## Best / Worst Result",
        "",
        f"- Best result: `{', '.join(best) if best else 'n/a'}` with quality `{best_score}`.",
        f"- Weakest result: `{', '.join(worst) if worst else 'n/a'}` with quality `{worst_score}`.",
        "",
        "## Data Quality Ranking",
        "",
        "### Top 5 Weakest Data Quality",
        "",
    ])
    lines.extend(_format_ranked_items(worst_data_quality))
    lines.extend([
        "",
        "### Top 5 Best Data Quality",
        "",
    ])
    lines.extend(_format_ranked_items(best_data_quality))
    lines.extend([
        "",
        "## Source Ingestion Sufficiency",
        "",
        f"- Tickers where `source_ingestion_mode` was not sufficient: `{', '.join(insufficient) if insufficient else 'none'}`",
        f"- Recommendation: `{recommendation}`",
        "",
        "## Production Readiness Assessment",
        "",
    ])
    true_count = counts.get("true_source_disagreements", 0)
    if recommendation == "produktionsreif":
        lines.append("- `source_ingestion_mode` looks production-ready for this universe.")
    elif recommendation == "pilotfaehig":
        lines.append("- `source_ingestion_mode` looks operational for controlled pilots after reconciliation hardening.")
    else:
        lines.append("- `source_ingestion_mode` still needs manual review before production operation.")
    lines.extend([
        "- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.",
        "",
        "## Artifact Check",
        "",
    ])
    required = ["report_manifest.json", "quality_score.json", "evidence_ledger.json", "reconciliation_report.md"]
    missing = []
    for item in manifest.items:
        for name in required:
            path = item.artifacts.get(name)
            if not path or not Path(path).exists():
                missing.append(f"{item.ticker} missing {name}")
        if not any(name in item.artifacts for name in ["final_report.md", "manual_review_required.md"]):
            missing.append(f"{item.ticker} missing final_report.md or manual_review_required.md")
    if missing:
        lines.extend(f"- {item}" for item in missing)
    else:
        lines.append("- All required dashboard artifact paths are present.")
    return "\n".join(lines) + "\n"


def _render_score_split_report(manifest: BatchManifest) -> str:
    lines = [
        f"# Score Split Report - {manifest.batch_id}",
        "",
        f"- As-of date: `{manifest.as_of_date}`",
        f"- Batch status: `{manifest.status}`",
        "",
        "| Ticker | Status | Publish Quality | Internal Research | Data Confidence | Legacy Total | Publishable | Explanation |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for item in manifest.items:
        payload = _quality_payload(item)
        publish_quality = payload.get("publish_quality_score") or (item.counts or {}).get("publish_quality_score") or item.quality_score
        internal_quality = payload.get("internal_research_quality_score") or (item.counts or {}).get("internal_research_quality_score")
        data_confidence = payload.get("data_confidence_score") or (item.counts or {}).get("data_confidence_score")
        explanation = str(payload.get("score_explanation_short") or "").replace("|", "/")
        lines.append(
            f"| {item.ticker} | {item.status} | {_display_score(publish_quality)} | {_display_score(internal_quality)} | "
            f"{_display_score(data_confidence)} | {_display_score(item.quality_score)} | {str(item.publishable).lower()} | {explanation} |"
        )
    return "\n".join(lines) + "\n"


def _quality_payload(item: BatchRunItem) -> dict:
    path = (item.artifacts or {}).get("quality_score.json")
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _display_score(value) -> str:
    if value is None:
        return "n/a"
    try:
        return str(int(round(float(value))))
    except (TypeError, ValueError):
        return str(value)


def _aggregate_item_counts(manifest: BatchManifest) -> dict[str, int]:
    totals: dict[str, int] = {}
    for item in manifest.items:
        for key, value in (item.counts or {}).items():
            totals[key] = totals.get(key, 0) + int(value or 0)
    return totals


def _median(values: list[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[midpoint])
    return float((ordered[midpoint - 1] + ordered[midpoint]) / 2)


def _issue_code_counts(manifest: BatchManifest, artifact_name: str) -> Counter:
    counter: Counter = Counter()
    for item in manifest.items:
        path = (item.artifacts or {}).get(artifact_name)
        if not path or not Path(path).exists():
            continue
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        for issue in payload.get("issues", []):
            code = issue.get("code")
            if code:
                counter[code] += 1
    return counter


def _reconciliation_code_counts(manifest: BatchManifest) -> Counter:
    counter: Counter = Counter()
    for item in manifest.items:
        path = (item.artifacts or {}).get("reconciliation_warnings.json")
        if not path or not Path(path).exists():
            continue
        warnings = json.loads(Path(path).read_text(encoding="utf-8"))
        for warning in warnings:
            code = warning.get("code")
            if code:
                counter[code] += int(warning.get("count") or 1)
    return counter


def _evidence_code_counts(manifest: BatchManifest) -> Counter:
    counter: Counter = Counter()
    codes = {
        "MISSING_EVIDENCE_FOR_METRIC",
        "NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC",
        "VENDOR_SOURCE_USED_AS_PRIMARY",
        "MISSING_DATE_FOR_NEWS_EVENT",
        "GUIDANCE_CONSENSUS_CONFLATION",
    }
    for item in manifest.items:
        path = (item.artifacts or {}).get("evidence_report.md")
        if not path or not Path(path).exists():
            continue
        text = Path(path).read_text(encoding="utf-8")
        for code in codes:
            counter[code] += text.count(code)
    return counter


def _format_counter(counter: Counter, limit: int = 10) -> list[str]:
    if not counter:
        return ["- None"]
    return [f"- `{code}`: `{count}`" for code, count in counter.most_common(limit)]


def _rank_data_quality(manifest: BatchManifest, reverse: bool) -> list[BatchRunItem]:
    def sort_key(item: BatchRunItem):
        counts = item.counts or {}
        quality = item.quality_score if item.quality_score is not None else -1
        penalty = (
            counts.get("validation_errors", 0) * 100
            + counts.get("audit_errors", 0) * 100
            + counts.get("true_source_disagreements", 0)
            + counts.get("evidence_warnings", 0) * 5
            + counts.get("reconciliation_warnings", 0)
        )
        if reverse:
            return (quality, -penalty)
        return (quality, -penalty)

    return sorted(manifest.items, key=sort_key, reverse=reverse)


def _format_ranked_items(items: list[BatchRunItem]) -> list[str]:
    if not items:
        return ["- None"]
    lines = []
    for item in items:
        counts = item.counts or {}
        lines.append(
            f"- `{item.ticker}`: quality `{item.quality_score}`, "
            f"true disagreements `{counts.get('true_source_disagreements', 0)}`, "
            f"validation errors `{counts.get('validation_errors', 0)}`, "
            f"audit errors `{counts.get('audit_errors', 0)}`"
        )
    return lines


def _pilot_recommendation(
    failed: int,
    manual_review: int,
    avg_quality: Optional[float],
    true_disagreements: int,
) -> str:
    if failed == 0 and manual_review == 0 and (avg_quality or 0) >= 90 and true_disagreements < 200:
        return "produktionsreif"
    if failed <= 2 and manual_review <= 5 and (avg_quality or 0) >= 85 and true_disagreements < 600:
        return "pilotfaehig"
    return "nicht produktionsreif"


def _baseline_source_disagreements(batch_id: str) -> Optional[int]:
    if "real_pilot_031" in batch_id:
        return 370
    if "real_pilot_002" in batch_id or "hardening" in batch_id:
        return 3687
    return None


def _baseline_ignored_variants(batch_id: str) -> Optional[int]:
    if "real_pilot_031" in batch_id:
        return 5299
    return None


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run a batch of stock research pipeline jobs.")
    parser.add_argument("--config", required=True, help="Path to batch_config.json or tickers.csv.")
    args = parser.parse_args(argv)

    config = load_batch_config(args.config)
    manifest = BatchRunner(config).run()
    return 0 if manifest.status in {"completed", "completed_with_issues"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
