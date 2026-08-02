from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from research_agent.batch.freshness import evaluate_price_freshness
from research_agent.content.claim_generator import (
    claim_coverage_gaps,
    claim_quality_metrics,
    generate_research_claims,
)
from research_agent.content.publish_composer import (
    compose_early_commercial_manual_review_publish_stub,
    compose_internal_best_report,
    compose_manual_review_publish_stub,
    compose_publish_report,
    publish_report_quality,
    save_internal_best_report,
    save_publish_quality,
    save_publish_report,
)
from research_agent.content.report_composer import compose_research_report, save_research_claims
from research_agent.audit.report_linter import audit_markdown_report
from research_agent.decision.rating_engine import build_decision_packet
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import (
    build_fundamental_derivation_evidence,
    build_evidence_ledger_from_source_registry,
    build_technical_derivation_evidence,
)
from research_agent.evidence.fact_ledger import build_fact_ledger, save_fact_ledger
from research_agent.evidence.evidence_report import render_evidence_report, save_evidence_report
from research_agent.evidence.source_ranker import rank_source
from research_agent.integration.authority_bundle import build_authority_bundle
from research_agent.outcomes.report_manifest import build_report_manifest, save_report_manifest
from research_agent.quality.quality_score import (
    calculate_quality_score,
    count_empty_required_archetype_sections,
    save_quality_report,
)
from research_agent.quality.deeptech_manual_review import (
    assess_speculative_deep_tech_manual_review,
    manual_review_banner,
)
from research_agent.reconciliation.canonical_financials import (
    CanonicalFinancials,
    CanonicalMetric,
    save_canonical_financials,
)
from research_agent.reconciliation.reconciliation_report import (
    render_current_period_reconciliation_summary,
    render_reconciliation_report,
    save_current_period_reconciliation_summary,
    save_reconciliation_report,
    save_reconciliation_warnings,
)
from research_agent.reconciliation.source_reconciler import (
    build_canonical_financials_from_facts,
    canonical_financials_to_fundamentals,
    quality_relevant_reconciliation_warnings,
)
from research_agent.research_core.calculations.fundamentals import calculate_fundamental_metrics
from research_agent.research_core.calculations.technicals import calculate_technical_metrics
from research_agent.research_core.calculations.valuation import calculate_valuation_metrics
from research_agent.research_core.ingestion.fundamentals_loader import load_fundamentals
from research_agent.research_core.ingestion.news_loader import (
    load_news,
    news_evidence_items,
)
from research_agent.research_core.ingestion.price_loader import load_price_history
from research_agent.research_core.ingestion.source_registry import (
    SourceRegistry,
    load_source_registry,
    merge_evidence_sources,
    save_source_registry,
)
from research_agent.research_core.models.data_packet import (
    CompanyGuidanceEPS,
    DataPacket,
    EventInfo,
    FiscalContext,
    ForwardEPS,
    MaterialNewsEvent,
    NewsCoverage,
    PriceBasis,
)
from research_agent.research_core.models.metrics_packet import MetricsPacket, ValuationMetrics
from research_agent.research_core.models.report_config import ReportConfig
from research_agent.research_core.normalization.normalize_events import normalize_events
from research_agent.research_core.normalization.normalize_fundamentals import normalize_fundamentals
from research_agent.research_core.normalization.normalize_prices import normalize_prices
from research_agent.research_core.reporting.markdown_renderer import save_report
from research_agent.research_core.reporting.report_builder import render_markdown_report
from research_agent.research_core.validation.runner import run_all_validations
from research_agent.sources.prices.csv_price_provider import CsvPriceProvider
from research_agent.sources.earnings.earnings_calendar import (
    earnings_event_to_evidence,
    is_event_risk_window,
    load_earnings_events,
    next_earnings_event as select_next_earnings_event,
)
from research_agent.sources.ir.earnings_release_parser import (
    extract_guidance_ranges,
    guidance_range_to_evidence,
)
from research_agent.sources.sec.cik_mapper import load_cik_mapper
from research_agent.sources.sec.companyfacts_parser import CompanyFactsParser
from research_agent.sources.sec.sec_client import SecClient, SecClientConfig
from research_agent.sources.sec.sec_filing_risks import load_sec_risk_evidence
from research_agent.sources.sec.sec_fundamentals_builder import (
    SEC_FUNDAMENTAL_METRICS,
    build_sec_evidence_for_source_ids,
    build_sec_fundamentals,
    build_sec_fundamentals_from_companyfacts,
)


def run_research_pipeline(
    ticker: str,
    as_of_date: str,
    config: Optional[ReportConfig] = None,
) -> str:
    config = config or ReportConfig(ticker=ticker, as_of_date=as_of_date)

    (
        prices,
        fundamentals,
        news,
        source_evidence_items,
        canonical_financials,
        reconciliation_warnings,
    ) = _load_pipeline_inputs(ticker, as_of_date, config)

    normalized_prices = normalize_prices(prices)
    normalized_fundamentals = normalize_fundamentals(fundamentals)
    normalized_news = normalize_events(news)

    data_packet = build_data_packet(
        ticker=ticker,
        as_of_date=as_of_date,
        prices=normalized_prices,
        fundamentals=normalized_fundamentals,
        news=normalized_news,
        price_currency=config.price_currency,
    )
    freshness = evaluate_price_freshness(
        data_packet.price_basis.date,
        batch_mode=config.batch_mode if config.batch_mode in {"current_research", "historical_guardrail_test"} else "current_research",
        reference_date=config.freshness_reference_date,
        max_trading_day_age=config.freshness_max_trading_days,
    )
    packet_root = Path(config.packet_dir)
    data_packet_path = save_json_packet(
        data_packet, "data_packet", ticker, as_of_date, packet_root=packet_root
    )

    technical_metrics = calculate_technical_metrics(normalized_prices, data_packet)
    fundamental_metrics = calculate_fundamental_metrics(
        normalized_fundamentals,
        fcf_definition=config.fcf_definition,
    )
    valuation_metrics = calculate_valuation_metrics(
        close_price=data_packet.price_basis.close,
        fundamentals=fundamental_metrics,
        forward_eps=data_packet.forward_eps,
        company_guidance_eps=data_packet.company_guidance_eps,
        trailing_eps=normalized_fundamentals.get("trailing_eps"),
        growth_rate=normalized_fundamentals.get("growth_rate"),
    )

    metrics_packet = MetricsPacket(
        ticker=data_packet.ticker,
        as_of_date=data_packet.as_of_date,
        technical=technical_metrics,
        fundamentals=fundamental_metrics,
        valuation=valuation_metrics or ValuationMetrics(),
    )
    metrics_packet_path = save_json_packet(
        metrics_packet, "metrics_packet", ticker, as_of_date, packet_root=packet_root
    )
    reconciliation_paths = _save_reconciliation_artifacts(
        canonical_financials=canonical_financials,
        metrics_packet=metrics_packet,
        warnings=reconciliation_warnings,
        ticker=ticker,
        as_of_date=as_of_date,
        packet_root=packet_root,
    )

    source_registry = _load_optional_source_registry(
        data_packet.source_registry_id, packet_root=packet_root
    )
    technical_derivation_evidence = build_technical_derivation_evidence(
        ticker=data_packet.ticker,
        as_of_date=data_packet.as_of_date,
        metrics_packet=metrics_packet,
        source_registry=source_registry,
        runtime_evidence=source_evidence_items,
        currency=config.price_currency,
    )
    source_evidence_items.extend(technical_derivation_evidence)
    price_source_id = next(
        (
            item.source_id
            for item in technical_derivation_evidence
            if "close" in item.supports_metrics
        ),
        None,
    )
    source_evidence_items.extend(
        build_fundamental_derivation_evidence(
            ticker=data_packet.ticker,
            as_of_date=data_packet.as_of_date,
            metrics_packet=metrics_packet,
            normalized_fundamentals=normalized_fundamentals,
            price_source_id=price_source_id,
            runtime_evidence=source_evidence_items,
            currency=config.price_currency,
        )
    )
    source_registry = merge_evidence_sources(
        source_registry,
        registry_id=data_packet.source_registry_id,
        ticker=data_packet.ticker,
        evidence_items=source_evidence_items,
    )
    source_registry_path = _source_registry_path(
        data_packet.source_registry_id, packet_root=packet_root
    )
    save_source_registry(source_registry, source_registry_path)
    evidence_ledger = build_evidence_ledger_from_source_registry(
        ticker=data_packet.ticker,
        as_of_date=data_packet.as_of_date,
        source_registry=source_registry,
        metrics_packet=metrics_packet,
        currency=config.price_currency,
    )
    evidence_ledger.evidence_items.extend(source_evidence_items)
    evidence_ledger_path = save_json_packet(
        evidence_ledger, "evidence_ledger", ticker, as_of_date, packet_root=packet_root
    )
    evidence_report_path = _save_evidence_report(
        evidence_ledger,
        metrics_packet,
        ticker,
        as_of_date,
        packet_root=packet_root,
    )
    validation_report = run_all_validations(
        data_packet=data_packet,
        metrics_packet=metrics_packet,
        source_registry=source_registry,
    )
    validation_report_path = save_json_packet(
        validation_report, "validation_report", ticker, as_of_date, packet_root=packet_root
    )

    if validation_report.has_blocking_errors and config.block_on_validation_errors:
        raise RuntimeError("Blocking validation errors. Final report generation stopped.")

    decision_packet = build_decision_packet(
        metrics_packet=metrics_packet,
        validation_report=validation_report,
    )
    decision_packet_path = save_json_packet(
        decision_packet, "decision_packet", ticker, as_of_date, packet_root=packet_root
    )
    claims = generate_research_claims(
        data_packet=data_packet,
        metrics_packet=metrics_packet,
        evidence_ledger=evidence_ledger,
        decision_packet=decision_packet,
        validation_report=validation_report,
        canonical_financials=canonical_financials,
    )
    manifest_output_dir = Path(config.output_dir) / data_packet.ticker / data_packet.as_of_date
    claim_metrics = claim_quality_metrics(claims)
    coverage_gaps = claim_coverage_gaps(claim_metrics)
    claim_coverage_complete = not coverage_gaps
    analyst_claims_path = save_research_claims(
        claims,
        manifest_output_dir / "analyst_claims.json",
    )
    fact_ledger_path = save_fact_ledger(
        build_fact_ledger(
            data_packet=data_packet,
            claims=claims,
            evidence_ledger=evidence_ledger,
            source_registry=source_registry,
        ),
        manifest_output_dir / "fact_ledger.json",
    )
    authority_bundle_dir = manifest_output_dir / "authority_bundle"
    authority_manifest = build_authority_bundle(
        packet_dir=data_packet_path.parent,
        source_registry_path=source_registry_path,
        fact_ledger_path=fact_ledger_path,
        output_dir=authority_bundle_dir,
    )
    if not authority_manifest["analysis_allowed"]:
        failures = ", ".join(authority_manifest["blocking_failures"])
        raise RuntimeError(
            "Research authority bundle rejected report generation: "
            f"{failures or 'unknown authority failure'}"
        )

    if claim_coverage_complete:
        report = compose_research_report(
            data_packet=data_packet,
            metrics_packet=metrics_packet,
            validation_report=validation_report,
            decision_packet=decision_packet,
            evidence_ledger=evidence_ledger,
            claims=claims,
            reconciliation_warnings=reconciliation_warnings,
        )
    else:
        report = render_markdown_report(
            data_packet=data_packet,
            metrics_packet=metrics_packet,
            validation_report=validation_report,
            claims=claims,
            source_registry=source_registry,
            evidence_ledger=evidence_ledger if evidence_ledger.evidence_items else None,
            decision_packet=decision_packet,
        )
        report += (
            "\n\n## Research Coverage Status\n\n"
            f"{_coverage_status_message(coverage_gaps)}\n"
        )
    report_path = manifest_output_dir / "final_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    final_report_path = str(report_path)
    deeptech_assessment = assess_speculative_deep_tech_manual_review(
        markdown=report,
        metrics_packet=metrics_packet,
        source_registry=source_registry,
    )
    audit_report = audit_markdown_report(
        markdown=report,
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        source_registry=source_registry,
        decision_packet=decision_packet,
        evidence_ledger=evidence_ledger if evidence_ledger.evidence_items else None,
        canonical_financials=canonical_financials,
        reconciliation_warnings=reconciliation_warnings,
        ticker=data_packet.ticker,
    )
    audit_report_path = _save_model_json(audit_report, manifest_output_dir / "audit_report.json")
    publish_quality_payload = _empty_publish_quality_payload()
    publish_report_path = ""
    publish_quality_path = ""
    if claim_coverage_complete:
        early_commercial_manual_review = (
            deeptech_assessment.company_archetype.value == "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH"
            and not deeptech_assessment.publishable
        )
        missing_fcf_accumulate_support = _count_audit_code(audit_report, "MISSING_FCF_SUPPORT_FOR_ACCUMULATE") > 0
        if early_commercial_manual_review:
            publish_report = compose_early_commercial_manual_review_publish_stub(
                data_packet=data_packet,
                metrics_packet=metrics_packet,
                evidence_ledger=evidence_ledger,
                claims=claims,
            )
        elif missing_fcf_accumulate_support:
            publish_report = compose_manual_review_publish_stub(
                data_packet=data_packet,
                metrics_packet=metrics_packet,
                evidence_ledger=evidence_ledger,
                claims=claims,
                external_display_rating="Hold Pending FCF Support",
                reason="MISSING_FCF_SUPPORT_FOR_ACCUMULATE",
            )
        else:
            publish_report = compose_publish_report(
                data_packet=data_packet,
                metrics_packet=metrics_packet,
                decision_packet=decision_packet,
                evidence_ledger=evidence_ledger,
                claims=claims,
            )
        if deeptech_assessment.status == "manual_review" and not early_commercial_manual_review and not missing_fcf_accumulate_support:
            publish_report = manual_review_banner(deeptech_assessment) + publish_report
        publish_report_path = str(save_publish_report(publish_report, manifest_output_dir / "publish_report.md"))
        publish_quality_payload = publish_report_quality(publish_report)
        publish_quality_path = str(save_publish_quality(publish_quality_payload, manifest_output_dir / "publish_report_quality_score.json"))
    quality_report = calculate_quality_score(
        validation_report=validation_report,
        audit_report=audit_report,
        decision_packet=decision_packet,
        final_markdown=report,
        reconciliation_warnings=quality_relevant_reconciliation_warnings(
            reconciliation_warnings,
            normalized_fundamentals,
        ),
        analyst_claim_count=int(claim_metrics["analyst_claim_count"]),
        evidence_mapped_claim_ratio=float(claim_metrics["evidence_mapped_claim_ratio"]),
        hard_claim_evidence_ratio=float(claim_metrics["hard_claim_evidence_ratio"]),
        substantive_analyst_claim_count=int(claim_metrics["substantive_analyst_claim_count"]),
        substantive_claim_ratio=float(claim_metrics["substantive_claim_ratio"]),
        generic_claim_count=int(claim_metrics["generic_claim_count"]),
        generic_claim_ratio=float(claim_metrics["generic_claim_ratio"]),
        data_limitation_claim_count=int(claim_metrics["data_limitation_claim_count"]),
        current_period_kpi_claim_count=int(claim_metrics["current_period_kpi_claim_count"]),
        current_period_kpi_metric_count=int(claim_metrics["current_period_kpi_metric_count"]),
        missing_current_period_context_count=(
            _count_audit_code(audit_report, "MISSING_CURRENT_PERIOD_CONTEXT")
            + _count_audit_code(audit_report, "MISSING_CURRENT_PERIOD_KPI_CONTEXT")
            + _count_audit_code(audit_report, "AVGO_CURRENT_KPI_CONTEXT_REQUIRED")
        ),
        ticker_specific_kpi_claim_count=int(claim_metrics["ticker_specific_kpi_claim_count"]),
        final_rating_rationale_quality=int(claim_metrics["final_rating_rationale_quality"]),
        mechanical_rating_language_count=int(claim_metrics["mechanical_rating_language_count"]),
        publish_report_exists=publish_quality_payload["publish_report_exists"],
        publish_mechanical_language_count=publish_quality_payload["publish_mechanical_language_count"],
        publish_current_kpi_count=publish_quality_payload["publish_current_kpi_count"],
        publish_evidence_appendix_exists=publish_quality_payload["publish_evidence_appendix_exists"],
        publish_claim_id_main_body_count=publish_quality_payload["publish_claim_id_main_body_count"],
        publish_valuation_sensitivity_present=publish_quality_payload["publish_valuation_sensitivity_present"],
        publish_action_plan_trigger_count=publish_quality_payload["publish_action_plan_trigger_count"],
        fcf_ocf_inconsistency_count=_count_audit_code(audit_report, "COMPANY_DEFINED_FCF_OCF_INCONSISTENCY"),
        company_defined_fcf_used=_company_defined_fcf_used(canonical_financials),
        sec_derived_fcf_used=_sec_derived_fcf_used(evidence_ledger),
        company_defined_fcf_mismatch_count=_count_audit_code(audit_report, "COMPANY_DEFINED_FCF_MISMATCH"),
        fcf_unavailable_block_count=_count_audit_code(audit_report, "FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT"),
        company_specific_claim_count=int(claim_metrics["company_specific_claim_count"]),
        valuation_specific_claim_count=int(claim_metrics["valuation_specific_claim_count"]),
        technical_specific_claim_count=int(claim_metrics["technical_specific_claim_count"]),
        rating_rationale_claim_count=int(claim_metrics["rating_rationale_claim_count"]),
        risk_specific_claim_count=int(claim_metrics["risk_specific_claim_count"]),
        data_freshness_status=freshness.data_freshness_status,
        stale_price_basis=int(freshness.stale_price_basis),
        current_report_allowed=freshness.current_report_allowed,
        historical_qa_only=freshness.historical_qa_only,
        freshness_issue_code=freshness.issue_code,
        **deeptech_assessment.to_quality_payload(),
    )
    if not quality_report.publishable:
        _remove_unapproved_publish_artifacts(manifest_output_dir)
        publish_report_path = ""
        publish_quality_path = ""
        publish_quality_payload = _empty_publish_quality_payload()
        _apply_publish_quality_to_report(quality_report, publish_quality_payload)
    quality_report_path = manifest_output_dir / "quality_score.json"
    internal_best_report_path = ""
    if audit_report.has_blocking_errors or not quality_report.publishable:
        manifest_output_dir.mkdir(parents=True, exist_ok=True)
        (manifest_output_dir / "manual_review_required.md").write_text(report, encoding="utf-8")
        if claim_coverage_complete:
            internal_best_report = compose_internal_best_report(
                data_packet=data_packet,
                metrics_packet=metrics_packet,
                decision_packet=decision_packet,
                evidence_ledger=evidence_ledger,
                claims=claims,
                status="manual_review" if not quality_report.publishable else quality_report.status,
                publishable=quality_report.publishable,
                external_display_rating=quality_report.external_display_rating,
                company_archetype=quality_report.company_archetype,
                quality_score=quality_report.total_score,
                publish_quality_score=quality_report.publish_quality_score,
                internal_research_quality_score=quality_report.internal_research_quality_score,
                data_confidence_score=quality_report.data_confidence_score,
            )
        else:
            internal_best_report = report
        empty_required_sections = count_empty_required_archetype_sections(
            internal_best_report,
            company_archetype=quality_report.company_archetype,
            speculative_deep_tech_profile_count=quality_report.speculative_deep_tech_profile_count,
            early_commercial_capital_intensive_tech_count=quality_report.early_commercial_capital_intensive_tech_count,
        )
        if empty_required_sections:
            _apply_empty_required_section_cap(quality_report, empty_required_sections)
            if claim_coverage_complete:
                internal_best_report = compose_internal_best_report(
                    data_packet=data_packet,
                    metrics_packet=metrics_packet,
                    decision_packet=decision_packet,
                    evidence_ledger=evidence_ledger,
                    claims=claims,
                    status="manual_review" if not quality_report.publishable else quality_report.status,
                    publishable=quality_report.publishable,
                    external_display_rating=quality_report.external_display_rating,
                    company_archetype=quality_report.company_archetype,
                    quality_score=quality_report.total_score,
                    publish_quality_score=quality_report.publish_quality_score,
                    internal_research_quality_score=quality_report.internal_research_quality_score,
                    data_confidence_score=quality_report.data_confidence_score,
                )
        internal_best_report_path = str(
            save_internal_best_report(
                internal_best_report,
                manifest_output_dir / "internal_best_report.md",
            )
        )
    quality_report_path = save_quality_report(
        quality_report,
        quality_report_path,
    )
    save_report(ticker, as_of_date, report, config.output_dir)
    manifest = build_report_manifest(
        ticker=data_packet.ticker,
        company_name=data_packet.company_name,
        as_of_date=data_packet.as_of_date,
        price_basis_date=data_packet.price_basis.date,
        price_basis_close=data_packet.price_basis.close,
        final_rating=decision_packet.rating_permission.preferred_rating.value,
        preferred_rating=decision_packet.rating_permission.preferred_rating.value,
        allowed_ratings=[rating.value for rating in decision_packet.rating_permission.allowed_ratings],
        quality_score=quality_report.total_score,
        publishable=quality_report.publishable,
        decision_packet_path=decision_packet_path,
        metrics_packet_path=metrics_packet_path,
        validation_report_path=validation_report_path,
        audit_report_path=audit_report_path,
        final_report_path=final_report_path,
        pipeline_version="research_agent_v0.1.0",
        metadata={
            "data_packet_path": str(data_packet_path),
            "source_registry_path": str(source_registry_path),
            "quality_score_path": str(quality_report_path),
            "publish_quality_score": quality_report.publish_quality_score,
            "internal_research_quality_score": quality_report.internal_research_quality_score,
            "data_confidence_score": quality_report.data_confidence_score,
            "total_score_legacy": quality_report.total_score,
            "score_explanation_short": quality_report.score_explanation_short,
            "quality_status": quality_report.status,
            "external_display_rating": quality_report.external_display_rating,
            "company_archetype": quality_report.company_archetype,
            "manual_review_reasons": quality_report.manual_review_reasons,
            "batch_mode": config.batch_mode,
            "data_freshness_status": freshness.data_freshness_status,
            "stale_price_basis": freshness.stale_price_basis,
            "current_report_allowed": freshness.current_report_allowed,
            "historical_qa_only": freshness.historical_qa_only,
            "freshness_issue_code": freshness.issue_code or "",
            "publish_report_path": publish_report_path,
            "publish_report_quality_score_path": publish_quality_path,
            "internal_best_report_path": internal_best_report_path,
            "analyst_claims_path": str(analyst_claims_path),
            "fact_ledger_path": str(fact_ledger_path),
            "evidence_ledger_path": str(evidence_ledger_path),
            "evidence_report_path": str(evidence_report_path),
            "authority_bundle_path": str(authority_bundle_dir),
            "authority_contract_id": authority_manifest["contract_id"],
            "authority_contract_version": authority_manifest["contract_version"],
            **reconciliation_paths,
        },
    )
    save_report_manifest(manifest, config.output_dir)
    return report


def _coverage_status_message(coverage_gaps: list[str]) -> str:
    if coverage_gaps == ["missing_risk_analysis"]:
        return (
            "Research coverage is incomplete: no evidence-backed risk "
            "analysis is available."
        )
    readable = ", ".join(gap.replace("_", " ") for gap in coverage_gaps)
    return f"Research coverage is incomplete: {readable}."


def build_data_packet(
    ticker: str,
    as_of_date: str,
    prices,
    fundamentals: dict[str, Any],
    news: list[dict[str, Any]],
    price_currency: str = "USD",
) -> DataPacket:
    latest_price = prices.iloc[-1]
    latest_event = _next_earnings_event(news)
    event_confirmed = bool(latest_event.get("confirmed")) if latest_event else False
    coverage_record = next(
        (
            item
            for item in news
            if item.get("event_type") == "coverage_manifest"
        ),
        {},
    )
    material_events = [
        MaterialNewsEvent(
            date=str(item.get("date") or "")[:10],
            headline=str(item.get("headline") or ""),
            event_type=str(item.get("event_type") or "company_event"),
            source_id=str(item.get("source_id") or ""),
            source_type=str(item.get("source_type") or ""),
            url=item.get("url"),
            summary=item.get("summary"),
        )
        for item in news
        if item.get("event_type") != "coverage_manifest"
        and item.get("material", True)
        and item.get("date")
        and str(item.get("date"))[:10] <= as_of_date
        and item.get("headline")
        and item.get("source_id")
        and item.get("source_type")
    ]
    return DataPacket(
        ticker=ticker.upper(),
        company_name=fundamentals.get("company_name"),
        as_of_date=as_of_date,
        price_basis=PriceBasis(
            close=float(latest_price["close"]),
            date=str(latest_price["date"]),
            currency=price_currency,
            source=fundamentals.get("price_source", "ohlcv_provider"),
            series_adjustment_status=str(
                latest_price.get("series_adjustment_status", "unknown")
            ),
            corporate_action_count=int(
                latest_price.get("corporate_action_count", 0) or 0
            ),
        ),
        fiscal_context=FiscalContext(
            latest_fiscal_year=fundamentals.get("latest_fiscal_year"),
            latest_quarter=fundamentals.get("latest_quarter"),
            fiscal_year_end=fundamentals.get("fiscal_year_end"),
        ),
        next_events=EventInfo(
            next_earnings_date=latest_event.get("date") if latest_event else None,
            confirmed=event_confirmed,
            source=(latest_event.get("source_id") or latest_event.get("source")) if latest_event else None,
            status=(latest_event.get("status") or ("confirmed" if event_confirmed else "unconfirmed")) if latest_event else "unavailable",
        ),
        news_coverage=NewsCoverage(
            status=str(coverage_record.get("status") or "unavailable"),
            checked_at=coverage_record.get("checked_at"),
            window_start=coverage_record.get("window_start"),
            window_end=coverage_record.get("window_end"),
            sources_checked=[
                str(value) for value in coverage_record.get("sources_checked") or []
            ],
            material_events=material_events,
        ),
        source_registry_id=fundamentals.get("source_registry_id", f"{ticker.upper()}_{as_of_date}"),
        forward_eps=ForwardEPS(**fundamentals["forward_eps"]) if fundamentals.get("forward_eps") else None,
        company_guidance_eps=CompanyGuidanceEPS(**fundamentals["company_guidance_eps"]) if fundamentals.get("company_guidance_eps") else None,
    )


def _load_pipeline_inputs(ticker: str, as_of_date: str, config: ReportConfig):
    if config.source_mode == "manual_packet_mode":
        return load_price_history(ticker), load_fundamentals(ticker), load_news(ticker), [], None, []
    if config.source_mode == "source_ingestion_mode":
        return _load_source_ingestion_inputs(ticker, as_of_date, config)
    raise ValueError(f"Unknown source_mode: {config.source_mode}")


def _load_source_ingestion_inputs(ticker: str, as_of_date: str, config: ReportConfig):
    if not config.price_csv_dir:
        raise ValueError("source_ingestion_mode requires price_csv_dir for the first deterministic build.")
    price_start = config.price_start_date or "1900-01-01"
    prices = CsvPriceProvider(config.price_csv_dir).get_history(ticker, price_start, as_of_date)
    fundamentals: dict[str, Any] = {
        "company_name": None,
        "price_source": config.price_source_id or "csv_price_provider",
        "source_registry_id": f"{ticker.upper()}_{as_of_date}",
    }
    evidence_items = _price_evidence_items(ticker, prices, config)
    canonical_financials = None
    reconciliation_warnings: list[dict] = []
    if config.cik_records_path:
        cik_mapper = load_cik_mapper(config.cik_records_path)
        fundamentals["company_name"] = cik_mapper.get_company_name(ticker)
        if config.sec_companyfacts_path:
            raw = json.loads(Path(config.sec_companyfacts_path).read_text(encoding="utf-8"))
            sec_metrics, sec_evidence_items = build_sec_fundamentals_from_companyfacts(
                ticker=ticker,
                cik=cik_mapper.get_cik(ticker),
                companyfacts_json=raw,
            )
        else:
            if not config.sec_user_agent:
                raise ValueError("source_ingestion_mode SEC fetch requires sec_user_agent or sec_companyfacts_path.")
            sec_client = SecClient(SecClientConfig(user_agent=config.sec_user_agent))
            raw = sec_client.get_companyfacts(cik_mapper.get_cik(ticker))
            sec_metrics, sec_evidence_items = build_sec_fundamentals_from_companyfacts(
                ticker=ticker,
                cik=cik_mapper.get_cik(ticker),
                companyfacts_json=raw,
            )
        evidence_items.extend(sec_evidence_items)
        canonical_financials, reconciliation_warnings = _build_canonical_from_companyfacts(
            ticker=ticker,
            as_of_date=as_of_date,
            cik=cik_mapper.get_cik(ticker),
            companyfacts_json=raw,
        )
        fundamentals.update(sec_metrics)
        canonical_fundamentals = canonical_financials_to_fundamentals(
            canonical_financials
        )
        fundamentals.update(canonical_fundamentals)
        bridge_source_ids = {
            str(source_id)
            for bridge in [
                *(
                    canonical_fundamentals.get("ttm_bridges") or {}
                ).values(),
                canonical_fundamentals.get(
                    "revenue_growth_yoy_bridge"
                ),
            ]
            if isinstance(bridge, dict)
            for source_id in bridge.get("source_ids") or []
            if source_id
        }
        exact_bridge_evidence = build_sec_evidence_for_source_ids(
            ticker=ticker,
            cik=cik_mapper.get_cik(ticker),
            companyfacts_json=raw,
            source_ids=bridge_source_ids,
        )
        known_evidence_ids = {
            item.evidence_id for item in evidence_items
        }
        evidence_items.extend(
            item
            for item in exact_bridge_evidence
            if item.evidence_id not in known_evidence_ids
        )
        reconciliation_warnings.extend(
            canonical_fundamentals.get("reconciliation_issues", [])
        )
    if config.sec_risk_factors_path:
        evidence_items.extend(
            load_sec_risk_evidence(config.sec_risk_factors_path, ticker=ticker)
        )
    if config.ir_release_dir:
        guidance_fundamentals, guidance_evidence, guidance_canonical = _load_ir_guidance_inputs(ticker, config.ir_release_dir)
        _merge_fundamentals(fundamentals, guidance_fundamentals)
        _apply_cash_and_marketable_total(fundamentals, guidance_fundamentals)
        evidence_items.extend(guidance_evidence)
        if guidance_canonical:
            if canonical_financials is None:
                canonical_financials = CanonicalFinancials(
                    ticker=ticker.upper(),
                    as_of_date=as_of_date,
                    metrics=guidance_canonical,
                )
            else:
                canonical_financials.metrics.extend(guidance_canonical)
            canonical_fundamentals = canonical_financials_to_fundamentals(
                canonical_financials
            )
            _merge_fundamentals(fundamentals, canonical_fundamentals)
            reconciliation_warnings.extend(
                canonical_fundamentals.get("reconciliation_issues", [])
            )
    news = load_news(
        ticker,
        config.official_news_dir or "research_agent/data/raw",
    )
    issuer_fcf_formulas = {
        str(item.get("issuer_fcf_formula"))
        for item in news
        if item.get("issuer_fcf_formula")
    }
    if len(issuer_fcf_formulas) > 1:
        raise ValueError(
            "official news inputs contain conflicting issuer FCF definitions"
        )
    if issuer_fcf_formulas:
        issuer_fcf_formula = issuer_fcf_formulas.pop()
        if issuer_fcf_formula != config.fcf_definition.formula_id:
            raise ValueError(
                "configured FCF formula conflicts with the issuer definition"
            )
        fundamentals["free_cash_flow_definition_basis"] = "issuer_defined"
    evidence_items.extend(news_evidence_items(ticker, news))
    if config.earnings_calendar_path:
        earnings_event = select_next_earnings_event(
            ticker=ticker,
            events=load_earnings_events(config.earnings_calendar_path),
            as_of_date=as_of_date,
        )
        if earnings_event:
            news.append({
                "event_type": "earnings",
                "date": earnings_event.report_date,
                "confirmed": bool(earnings_event.confirmed),
                "source": earnings_event.source_id,
                "source_id": earnings_event.source_id,
                "status": "confirmed" if earnings_event.confirmed else "planned",
                "within_10_trading_days": is_event_risk_window(earnings_event, as_of_date),
            })
            evidence_items.append(earnings_event_to_evidence(earnings_event))
    return prices, fundamentals, news, evidence_items, canonical_financials, reconciliation_warnings


def _build_canonical_from_companyfacts(ticker: str, as_of_date: str, cik: str, companyfacts_json: dict[str, Any]):
    parser = CompanyFactsParser(ticker=ticker, cik=cik, companyfacts_json=companyfacts_json)
    facts = []
    for metric in SEC_FUNDAMENTAL_METRICS:
        facts.extend(parser.get_facts_for_metric(metric))
    return build_canonical_financials_from_facts(ticker=ticker, as_of_date=as_of_date, facts=facts)


def _price_evidence_items(
    ticker: str,
    prices,
    config: Optional[ReportConfig] = None,
) -> list[EvidenceItem]:
    if prices.empty:
        return []
    latest = prices.iloc[-1]
    close = float(latest["close"])
    date = str(latest["date"])
    source_id = (
        config.price_source_id
        if config and config.price_source_id
        else f"{ticker.upper()}_CSV_PRICE_PROVIDER"
    )
    source_type = config.price_source_type if config else "exchange_ohlcv"
    return [
        EvidenceItem(
            evidence_id=f"{ticker.upper()}_CSV_PRICE_CLOSE_{date}",
            ticker=ticker.upper(),
            claim_type="price_data",
            source_id=source_id,
            source_type=source_type,
            authority_rank=rank_source(source_type),
            statement=f"{ticker.upper()} closed at {close} on {date}.",
            value=close,
            unit=config.price_currency if config else "USD",
            period="daily",
            date=date,
            url=config.price_source_url if config else None,
            retrieved_at=config.price_retrieved_at if config else None,
            supports_metrics=["close", "price_data", "price_basis"],
            confidence="high",
        )
    ]


def _load_ir_guidance_inputs(ticker: str, release_dir: str) -> tuple[dict[str, Any], list[EvidenceItem], list[CanonicalMetric]]:
    source = _find_ir_release_file(ticker, release_dir)
    if source is None:
        return {}, [], []
    payload = _read_ir_release_payload(source)
    text = payload.get("text") or ""
    period = payload.get("period") or "forward"
    source_id = payload.get("source_id") or f"{ticker.upper()}_IR_EARNINGS_RELEASE"
    source_type = payload.get("source_type") or "earnings_release"
    if source_type not in {"company_ir", "earnings_release", "sec_filing", "official_press_release"}:
        return {}, [], []

    ranges = extract_guidance_ranges(text, period=period)
    evidence = [
        guidance_range_to_evidence(
            ticker=ticker,
            guidance=guidance,
            source_id=source_id,
            source_type=source_type,
            url=payload.get("url"),
            retrieved_at=payload.get("retrieved_at"),
        )
        for guidance in ranges
    ]
    fundamentals: dict[str, Any] = {}
    if payload.get("company_name"):
        fundamentals["company_name"] = str(payload["company_name"])
    metrics = payload.get("metrics") or []
    annual_periods = [
        row
        for row in metrics
        if row.get("period_bucket") == "annual"
        and row.get("fiscal_year") is not None
    ]
    if annual_periods:
        latest_annual = max(
            annual_periods,
            key=lambda row: (
                int(row.get("fiscal_year") or 0),
                str(row.get("end_date") or row.get("date") or ""),
            ),
        )
        fundamentals["latest_fiscal_year"] = (
            f"FY{int(latest_annual['fiscal_year'])}"
        )
        annual_end = str(
            latest_annual.get("end_date") or latest_annual.get("date") or ""
        )
        if len(annual_end) >= 10:
            fundamentals["fiscal_year_end"] = annual_end[5:10]
    quarterly_periods = [
        row
        for row in metrics
        if row.get("period_bucket") == "quarterly"
        and row.get("fiscal_period")
    ]
    if quarterly_periods:
        latest_quarter = max(
            quarterly_periods,
            key=lambda row: str(row.get("end_date") or row.get("date") or ""),
        )
        latest_quarter_label = str(
            latest_quarter.get("period")
            or (
                f"FY{int(latest_quarter['fiscal_year'])}_"
                f"{latest_quarter['fiscal_period']}"
            )
        )
        fundamentals["latest_quarter"] = latest_quarter_label
        fundamentals["fiscal_period"] = f"TTM through {latest_quarter_label}"
    canonical_metrics: list[CanonicalMetric] = []
    metric_evidence, metric_fundamentals, metric_canonical = _ir_current_metric_inputs(
        ticker=ticker,
        metrics=metrics,
        source_id=source_id,
        source_type=source_type,
        url=payload.get("url"),
        retrieved_at=payload.get("retrieved_at"),
    )
    evidence.extend(metric_evidence)
    _merge_fundamentals(fundamentals, metric_fundamentals)
    canonical_metrics.extend(metric_canonical)
    eps_guidance = next((guidance for guidance in ranges if guidance.metric == "company_guidance_eps"), None)
    if eps_guidance:
        basis = "non_gaap" if "non-gaap" in eps_guidance.source_text.lower() else "company_defined"
        fundamentals["company_guidance_eps"] = {
            "low": eps_guidance.low,
            "high": eps_guidance.high,
            "source_type": source_type,
            "period": eps_guidance.period,
            "basis": basis,
        }
    return fundamentals, evidence, canonical_metrics


def _ir_current_metric_inputs(
    ticker: str,
    metrics: list[dict[str, Any]],
    source_id: str,
    source_type: str,
    url: Optional[str],
    retrieved_at: Optional[str],
) -> tuple[list[EvidenceItem], dict[str, Any], list[CanonicalMetric]]:
    evidence: list[EvidenceItem] = []
    fundamentals: dict[str, Any] = {"annual": {}, "balance_sheet": {}}
    canonical: list[CanonicalMetric] = []
    values: dict[str, float] = {}
    for row in metrics:
        metric_name = row.get("metric_name")
        value = row.get("value")
        if metric_name is None or value is None:
            continue
        value = float(value)
        values[metric_name] = value
        period = row.get("period") or "current_period"
        unit = row.get("unit") or "usd"
        basis = row.get("basis") or ("company_defined" if metric_name in {"free_cash_flow", "cash_and_marketable_securities"} else "gaap")
        statement_type = row.get("statement_type") or _ir_statement_type(metric_name)
        period_bucket = row.get("period_bucket") or ("instant" if statement_type == "balance_sheet" else "annual")
        supports_metrics = row.get("supports_metrics") or _ir_supports_metrics(metric_name)
        evidence_id = f"{ticker.upper()}_{source_id}_{metric_name}_{period}".replace(" ", "_")
        statement = row.get("statement") or f"{ticker.upper()} reported {metric_name} of {value} {unit} for {period}."
        evidence.append(
            EvidenceItem(
                evidence_id=evidence_id,
                ticker=ticker.upper(),
                claim_type=row.get("claim_type") or ("financial_metric" if statement_type != "balance_sheet" else "financial_metric"),
                source_id=source_id,
                source_type=source_type,
                authority_rank=rank_source(source_type),
                statement=statement,
                value=value,
                unit=unit,
                period=period,
                date=row.get("date"),
                url=url,
                retrieved_at=retrieved_at,
                supports_metrics=supports_metrics,
                confidence="high",
            )
        )
        canonical.append(
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit=unit,
                period=period,
                fiscal_year=row.get("fiscal_year"),
                fiscal_period=row.get("fiscal_period"),
                period_bucket=period_bucket,
                start_date=row.get("start_date"),
                end_date=row.get("end_date") or row.get("date"),
                duration_days=row.get("duration_days"),
                basis=basis,
                statement_type=statement_type,
                source_ids=[source_id],
                evidence_ids=[evidence_id],
                confidence="high",
                reconciliation_notes=[row.get("reconciliation_note") or "Current-period IR/Earnings Release metric ingested explicitly."],
            )
        )
        if metric_name in {
            "revenue",
            "gross_profit",
            "operating_income",
            "ebitda",
            "net_income",
            "operating_cash_flow",
            "capex",
            "sbc",
        } and period_bucket in {"annual", "ttm"}:
            fundamentals["annual"][metric_name] = value
        elif metric_name in {"free_cash_flow", "adjusted_free_cash_flow"} and period_bucket in {"annual", "ttm"}:
            fundamentals["annual"][metric_name] = value
        elif metric_name in {
            "cash_and_equivalents",
            "marketable_securities",
            "short_term_investments",
            "total_debt",
            "current_assets",
            "current_liabilities",
            "equity",
        }:
            fundamentals["balance_sheet"][metric_name] = value
        elif metric_name == "cash_and_marketable_securities":
            fundamentals["_cash_and_marketable_securities"] = value
        elif metric_name == "shares_diluted":
            fundamentals.setdefault("share_data", {})["diluted_share_count"] = value
        elif metric_name in {
            "listed_share_count",
            "treasury_share_count",
            "economic_share_count",
        }:
            fundamentals.setdefault("share_data", {})[metric_name] = value
    if "operating_cash_flow" in values and "free_cash_flow" in values:
        fundamentals["annual"]["operating_cash_flow"] = values["operating_cash_flow"]
        fundamentals["annual"]["capex"] = max(values["operating_cash_flow"] - values["free_cash_flow"], 0.0)
    return evidence, fundamentals, canonical


def _ir_supports_metrics(metric_name: str) -> list[str]:
    aliases = {
        "revenue": ["revenue", "revenue_ttm"],
        "gross_profit": ["gross_profit", "gross_profit_ttm", "gross_margin_ttm"],
        "operating_income": [
            "operating_income",
            "operating_income_ttm",
            "operating_margin_ttm",
        ],
        "ebitda": ["ebitda", "ebitda_ttm", "ev_to_ebitda"],
        "net_income": ["net_income", "net_income_ttm", "net_margin_ttm"],
        "operating_cash_flow": ["operating_cash_flow", "operating_cash_flow_ttm"],
        "capex": ["capex", "capex_ttm", "free_cash_flow_ttm"],
        "free_cash_flow": ["free_cash_flow", "free_cash_flow_ttm", "company_defined_fcf"],
        "adjusted_free_cash_flow": ["adjusted_free_cash_flow", "free_cash_flow_ttm", "company_defined_fcf"],
        "adjusted_free_cash_flow_margin": ["adjusted_free_cash_flow_margin", "free_cash_flow_margin_guidance"],
        "sbc": ["sbc", "sbc_ttm", "sbc_to_revenue"],
        "cash_and_equivalents": ["cash_and_equivalents", "cash", "cash_and_investments"],
        "marketable_securities": ["marketable_securities", "cash_and_investments"],
        "short_term_investments": ["short_term_investments", "cash_and_investments"],
        "total_debt": ["total_debt", "debt", "net_cash"],
        "current_assets": ["current_assets", "current_ratio"],
        "current_liabilities": ["current_liabilities", "current_ratio"],
        "equity": ["equity", "debt_to_equity"],
        "listed_share_count": ["listed_share_count", "market_cap"],
        "treasury_share_count": ["treasury_share_count", "economic_share_count"],
        "economic_share_count": ["economic_share_count", "trailing_eps"],
        "cash_and_marketable_securities": ["cash_and_marketable_securities", "cash_and_investments"],
        "shares_diluted": ["shares_diluted", "diluted_share_count"],
    }
    return aliases.get(metric_name, [metric_name])


def _ir_statement_type(metric_name: str) -> str:
    if metric_name in {"operating_cash_flow", "free_cash_flow", "adjusted_free_cash_flow", "adjusted_free_cash_flow_margin"}:
        return "cash_flow"
    if metric_name in {
        "cash_and_marketable_securities",
        "cash_and_equivalents",
        "marketable_securities",
        "short_term_investments",
        "total_debt",
        "current_assets",
        "current_liabilities",
        "equity",
    }:
        return "balance_sheet"
    if metric_name in {"listed_share_count", "treasury_share_count", "economic_share_count"}:
        return "balance_sheet"
    return "income_statement"


def _merge_fundamentals(target: dict[str, Any], update: dict[str, Any]) -> None:
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            target[key].update(value)
            if key == "annual" and isinstance(target.get("quarterly"), dict):
                for metric_name in value:
                    target["quarterly"].pop(metric_name, None)
            if key == "balance_sheet" and "marketable_securities" in value:
                target[key].pop("short_term_investments", None)
        else:
            target[key] = value


def _apply_cash_and_marketable_total(fundamentals: dict[str, Any], update: dict[str, Any]) -> None:
    total = update.get("_cash_and_marketable_securities")
    if total is None:
        return
    balance_sheet = fundamentals.setdefault("balance_sheet", {})
    cash = float(balance_sheet.get("cash_and_equivalents") or 0.0)
    balance_sheet["marketable_securities"] = max(float(total) - cash, 0.0)


def _find_ir_release_file(ticker: str, release_dir: str) -> Optional[Path]:
    base = Path(release_dir)
    if not base.exists():
        return None
    for suffix in [".json", ".txt", ".md", ".html"]:
        path = base / f"{ticker.upper()}{suffix}"
        if path.exists():
            return path
        lower_path = base / f"{ticker.lower()}{suffix}"
        if lower_path.exists():
            return lower_path
    return None


def _read_ir_release_payload(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        return dict(payload)
    return {
        "text": path.read_text(encoding="utf-8"),
        "period": "forward",
        "source_id": path.stem.upper(),
        "source_type": "earnings_release",
    }


def save_json_packet(
    model,
    packet_name: str,
    ticker: str,
    as_of_date: str,
    *,
    packet_root: Path = Path("research_agent/data/packets"),
) -> Path:
    target_dir = packet_root / ticker.upper() / as_of_date
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{packet_name}.json"
    target.write_text(json.dumps(_model_to_dict(model), indent=2, sort_keys=True), encoding="utf-8")
    return target


def _save_evidence_report(
    evidence_ledger,
    metrics_packet,
    ticker: str,
    as_of_date: str,
    *,
    packet_root: Path = Path("research_agent/data/packets"),
) -> Path:
    target = packet_root / ticker.upper() / as_of_date / "evidence_report.md"
    required_metrics = ["revenue_ttm"]
    if metrics_packet.fundamentals.free_cash_flow_ttm is not None:
        required_metrics.append("free_cash_flow_ttm")
    if metrics_packet.fundamentals.sbc_to_revenue is not None:
        required_metrics.append("sbc_to_revenue")
    markdown = render_evidence_report(
        evidence_ledger,
        required_metrics=required_metrics,
    )
    return save_evidence_report(markdown, target)


def _save_reconciliation_artifacts(
    canonical_financials,
    metrics_packet,
    warnings: list[dict],
    ticker: str,
    as_of_date: str,
    *,
    packet_root: Path = Path("research_agent/data/packets"),
) -> dict[str, str]:
    if canonical_financials is None:
        return {}
    target_dir = packet_root / ticker.upper() / as_of_date
    canonical_path = save_canonical_financials(canonical_financials, target_dir / "canonical_financials.json")
    report_path = save_reconciliation_report(
        render_reconciliation_report(canonical_financials, warnings),
        target_dir / "reconciliation_report.md",
    )
    warnings_path = save_reconciliation_warnings(warnings, target_dir / "reconciliation_warnings.json")
    current_summary_path = save_current_period_reconciliation_summary(
        render_current_period_reconciliation_summary(canonical_financials, metrics_packet, warnings),
        target_dir / "current_period_reconciliation_summary.md",
    )
    return {
        "canonical_financials_path": str(canonical_path),
        "reconciliation_report_path": str(report_path),
        "reconciliation_warnings_path": str(warnings_path),
        "current_period_reconciliation_summary_path": str(current_summary_path),
    }


def _load_optional_source_registry(
    source_registry_id: str,
    *,
    packet_root: Path = Path("research_agent/data/packets"),
) -> Optional[SourceRegistry]:
    path = _optional_source_registry_path(source_registry_id, packet_root=packet_root)
    if path is None:
        return None
    return load_source_registry(path)


def _optional_source_registry_path(
    source_registry_id: str,
    *,
    packet_root: Path = Path("research_agent/data/packets"),
) -> Optional[Path]:
    path = _source_registry_path(source_registry_id, packet_root=packet_root)
    if not path.exists():
        return None
    return path


def _source_registry_path(
    source_registry_id: str,
    *,
    packet_root: Path = Path("research_agent/data/packets"),
) -> Path:
    return packet_root / f"{source_registry_id}_source_registry.json"


def _save_model_json(model, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_model_to_dict(model), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _next_earnings_event(news: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    earnings_events = [item for item in news if item.get("event_type") == "earnings"]
    return earnings_events[0] if earnings_events else None


def _model_to_dict(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _count_audit_code(audit_report, code: str) -> int:
    return sum(1 for issue in audit_report.issues if issue.code == code)


def _empty_publish_quality_payload() -> dict[str, int]:
    return {
        "publish_report_exists": 0,
        "publish_mechanical_language_count": 0,
        "publish_current_kpi_count": 0,
        "publish_evidence_appendix_exists": 0,
        "publish_claim_id_main_body_count": 0,
        "publish_valuation_sensitivity_present": 0,
        "publish_action_plan_trigger_count": 0,
        "publish_report_quality_score": 0,
    }


def _remove_unapproved_publish_artifacts(output_dir: Path) -> None:
    for filename in ("publish_report.md", "publish_report_quality_score.json"):
        (output_dir / filename).unlink(missing_ok=True)


def _apply_publish_quality_to_report(quality_report, payload: dict[str, int]) -> None:
    quality_report.publish_report_exists = int(payload.get("publish_report_exists") or 0)
    quality_report.publish_mechanical_language_count = int(payload.get("publish_mechanical_language_count") or 0)
    quality_report.publish_current_kpi_count = int(payload.get("publish_current_kpi_count") or 0)
    quality_report.publish_evidence_appendix_exists = int(payload.get("publish_evidence_appendix_exists") or 0)
    quality_report.publish_claim_id_main_body_count = int(payload.get("publish_claim_id_main_body_count") or 0)
    quality_report.publish_valuation_sensitivity_present = int(payload.get("publish_valuation_sensitivity_present") or 0)
    quality_report.publish_action_plan_trigger_count = int(payload.get("publish_action_plan_trigger_count") or 0)
    quality_report.publish_report_quality_score = int(payload.get("publish_report_quality_score") or 0)


def _apply_empty_required_section_cap(quality_report, empty_required_sections: int) -> None:
    quality_report.empty_required_section_count = int(empty_required_sections)
    quality_report.content_score = min(quality_report.content_score, 76 if empty_required_sections >= 3 else 84)
    quality_report.internal_research_quality_score = min(
        quality_report.internal_research_quality_score,
        70 if empty_required_sections >= 3 else 75,
    )


def _company_defined_fcf_used(canonical_financials) -> int:
    if canonical_financials is None:
        return 0
    return int(any(
        metric.metric_name in {"free_cash_flow", "adjusted_free_cash_flow"}
        and metric.basis in {"company_defined", "non_gaap"}
        and any("IR" in source_id or "EARNINGS" in source_id for source_id in metric.source_ids)
        for metric in canonical_financials.metrics
    ))


def _sec_derived_fcf_used(evidence_ledger) -> int:
    if evidence_ledger is None:
        return 0
    return int(
        any(
            "free_cash_flow_ttm" in item.supports_metrics
            and (
                item.source_type == "sec_filing"
                or any(
                    source_id.startswith("SEC_")
                    for source_id in item.source_lineage
                )
            )
            for item in evidence_ledger.evidence_items
        )
    )
