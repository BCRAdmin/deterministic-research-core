"""Create and verify the only supported hand-off into Room16 report generation.

The bundle is deliberately company-agnostic. It validates packet identity,
source authority, evidence coverage, calculation status, and rating permission
without branching on a ticker or company name.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from research_agent.batch.freshness import evaluate_price_freshness
from research_agent.evidence.evidence_ledger import unit_for_metric
from research_agent.research_core.models.metrics_packet import (
    MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED,
)
from research_agent.research_core.ingestion.source_snapshot import (
    verify_source_snapshot_manifest,
)
from research_agent.quality.research_scope_coverage import (
    verify_research_scope_coverage,
)


AUTHORITY_CONTRACT_ID = "room16.research_authority_bundle"
AUTHORITY_CONTRACT_VERSION = 3
PIPELINE_VERSION = "research_agent_v0.1.0"

REQUIRED_PACKET_FILES = {
    "data_packet": "data_packet.json",
    "metrics_packet": "metrics_packet.json",
    "validation_report": "validation_report.json",
    "decision_packet": "decision_packet.json",
    "evidence_ledger": "evidence_ledger.json",
}

PRIMARY_FINANCIAL_SOURCE_TYPES = {"company_ir", "sec_filing"}
PRICE_SOURCE_TYPES = {"exchange_ohlcv", "trusted_market_data_vendor"}
FINANCIAL_SOURCE_USES = {
    "revenue",
    "revenue_ttm",
    "gross_profit",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "capex",
    "free_cash_flow",
    "sbc",
    "cash",
    "debt",
    "shares",
    "eps",
}
PRICE_SOURCE_USES = {"price", "volume", "technical_indicators"}
MATERIAL_METRIC_KEYS = {
    # Values rendered by Room16's deterministic fundamental section.
    "revenue_ttm",
    "revenue_growth_yoy",
    "operating_income_ttm",
    "operating_margin_ttm",
    "net_income_ttm",
    "net_margin_ttm",
    "trailing_eps",
    "ebitda_ttm",
    "operating_cash_flow_ttm",
    "capex_ttm",
    "free_cash_flow_ttm",
    "fcf_margin_ttm",
    "free_cash_flow_conversion_ttm",
    "depreciation_and_amortization_ttm",
    "interest_expense_ttm",
    "operating_income_interest_coverage_ttm",
    "free_cash_flow_interest_coverage_ttm",
    "cash_and_equivalents",
    "buybacks",
    "dividends_paid",
    "shareholder_distributions_ttm",
    "shareholder_distributions_minus_fcf_ttm",
    "buybacks_current_period",
    "dividends_paid_current_period",
    "shareholder_distributions_current_period",
    "free_cash_flow_current_period",
    "shareholder_distributions_minus_fcf_current_period",
    "sbc_ttm",
    "sbc_to_revenue",
    "sbc_to_fcf",
    "cash_and_investments",
    "current_assets",
    "current_liabilities",
    "current_ratio",
    "total_debt",
    "total_lease_liabilities",
    "equity",
    "net_cash",
    "economic_share_count",
    "listed_share_count",
    "diluted_share_count",
    "treasury_share_count",
    "treasury_stock_value",
    # Values rendered by Room16's deterministic valuation section.
    "market_cap",
    "enterprise_value",
    "trailing_pe",
    "price_to_fcf",
    "ev_to_sales",
    "ev_to_ebit",
    "ev_to_ebitda",
    "fcf_yield",
    # Values rendered by the deterministic market section.
    "close",
    "sma_50",
    "sma_200",
    "rsi_14",
    "avg_volume_20",
}
TECHNICAL_METRIC_KEYS = {
    "close",
    "sma_50",
    "sma_200",
    "rsi_14",
    "avg_volume_20",
}


class AuthorityBundleError(ValueError):
    """Raised when a research authority bundle cannot be built or verified."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AuthorityBundleError(f"required authority artifact missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AuthorityBundleError(f"invalid JSON authority artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise AuthorityBundleError(f"authority artifact must contain a JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _iso_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise AuthorityBundleError(f"invalid ISO date in authority packet: {text!r}") from exc


def _check(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    *,
    blocking: bool = True,
    detail: str = "",
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "status": "pass" if passed else "fail",
            "blocking": blocking,
            "detail": detail,
        }
    )


def _manifest_gate_consistent(manifest: Mapping[str, Any]) -> bool:
    declared_failures = manifest.get("blocking_failures")
    manifest_checks = manifest.get("checks")
    if not isinstance(declared_failures, list) or not isinstance(manifest_checks, list):
        return False
    if not manifest_checks or any(not isinstance(item, Mapping) for item in manifest_checks):
        return False
    check_ids: set[str] = set()
    derived_failures: list[str] = []
    for item in manifest_checks:
        check_id = str(item.get("check_id") or "")
        status = item.get("status")
        blocking = item.get("blocking")
        if (
            not check_id
            or check_id in check_ids
            or status not in {"pass", "fail"}
            or not isinstance(blocking, bool)
        ):
            return False
        check_ids.add(check_id)
        if blocking and status != "pass":
            derived_failures.append(check_id)
    return (
        [str(item) for item in declared_failures] == derived_failures
        and manifest.get("analysis_allowed") is (not derived_failures)
    )


def _metric_items(metrics_packet: Mapping[str, Any]) -> Iterable[tuple[str, Any]]:
    for section in ("technical", "fundamentals", "valuation"):
        values = metrics_packet.get(section)
        if not isinstance(values, Mapping):
            continue
        for key, value in values.items():
            if key in MATERIAL_METRIC_KEYS and value is not None:
                yield key, value


def _has_exact_numeric_evidence(
    evidence_items: Iterable[Mapping[str, Any]],
    metric_name: str,
    value: Any,
    *,
    currency: str,
    price_date: str,
    indicator_date: str,
) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    expected = float(value)
    expected_unit = unit_for_metric(metric_name, currency=currency)
    for item in evidence_items:
        evidence_value = (
            item.get("normalized_value")
            if item.get("normalized_value") is not None
            else item.get("value")
        )
        if (
            metric_name not in (item.get("supports_metrics") or [])
            or not isinstance(evidence_value, (int, float))
            or isinstance(evidence_value, bool)
            or not math.isclose(
                float(evidence_value),
                expected,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
        ):
            continue
        actual_unit = str(item.get("unit") or "").strip()
        if (
            actual_unit
            and expected_unit
            and _normalize_unit(actual_unit) != _normalize_unit(expected_unit)
        ):
            continue
        if metric_name in TECHNICAL_METRIC_KEYS and item.get("date"):
            expected_date = price_date if metric_name == "close" else indicator_date
            if str(item.get("date")) != expected_date:
                continue
        if not _ttm_period_is_compatible(item, metric_name):
            continue
        if (
            (
                item.get("formula_id")
                and isinstance(item.get("formula_operands"), Mapping)
                and item.get("formula_operands")
            )
            or item.get("raw_value") is not None
            or item.get("normalized_value") is not None
            or (item.get("date") and item.get("period"))
        ):
            return True
    return False


def _normalize_unit(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("/", "_per_")
    return "_".join(normalized.replace("-", "_").split())


def _ttm_period_is_compatible(
    item: Mapping[str, Any],
    metric_name: str,
) -> bool:
    if not metric_name.endswith("_ttm") and metric_name not in {
        "buybacks",
        "dividends_paid",
    }:
        return True
    duration_days = item.get("duration_days")
    if isinstance(duration_days, (int, float)) and not 300 <= duration_days <= 430:
        return False
    period = str(item.get("period") or "").strip().lower()
    if not period or "ttm" in period or ".." in period:
        return True
    return not any(token in period for token in ("q1", "q2", "q3", "q4"))


def _unit_normalization_failures(
    evidence_items: Iterable[Mapping[str, Any]],
) -> list[str]:
    """Validate source-to-base conversion for emitted operating KPI evidence."""

    multipliers = {
        "base": 1.0,
        "thousand": 1_000.0,
        "k": 1_000.0,
        "million": 1_000_000.0,
        "m": 1_000_000.0,
        "mn": 1_000_000.0,
        "billion": 1_000_000_000.0,
        "b": 1_000_000_000.0,
        "bn": 1_000_000_000.0,
        "percent": 0.01,
    }
    failures: list[str] = []
    for item in evidence_items:
        source_id = str(item.get("source_id") or "")
        supports_claims = {str(value) for value in item.get("supports_claims") or []}
        if (
            "business_model_operating_kpi" not in supports_claims
            and "_KPI_" not in source_id
        ):
            continue
        evidence_id = str(item.get("evidence_id") or source_id or "unknown")
        raw = item.get("raw_value")
        normalized = item.get("normalized_value")
        if raw is None and normalized is None:
            # Registry-derived KPI capability rows carry no numeric claim and
            # therefore have no source-to-base conversion to verify.
            continue
        scale = str(item.get("source_scale") or "").casefold()
        source_unit = str(item.get("source_unit") or "")
        unit = str(item.get("unit") or "")
        source_sign = item.get("source_sign", 1)
        if (
            not isinstance(raw, (int, float))
            or isinstance(raw, bool)
            or not isinstance(normalized, (int, float))
            or isinstance(normalized, bool)
            or scale not in multipliers
            or source_unit != unit
            or source_sign not in {-1, 1}
        ):
            failures.append(evidence_id)
            continue
        expected = float(raw) * multipliers[scale] * float(source_sign)
        if not math.isclose(float(normalized), expected, rel_tol=1e-12, abs_tol=1e-9):
            failures.append(evidence_id)
            continue
        if unit == "currency" and not item.get("currency"):
            failures.append(evidence_id)
    return sorted(set(failures))


def _resolve_source_registry_path(
    packet_dir: Path,
    data_packet: Mapping[str, Any],
    explicit_path: str | Path | None,
) -> Path:
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()
    adjacent = packet_dir / "source_registry.json"
    if adjacent.exists():
        return adjacent
    registry_id = str(data_packet.get("source_registry_id") or "").strip()
    packets_root = packet_dir.parent.parent
    candidate = packets_root / f"{registry_id}_source_registry.json"
    if registry_id and candidate.exists():
        return candidate
    raise AuthorityBundleError(
        "source_registry.json is missing; pass source_registry_path or keep the "
        "registered source file beside the packet hierarchy"
    )


def _build_validated_context(
    *,
    data_packet: Mapping[str, Any],
    metrics_packet: Mapping[str, Any],
    validation_report: Mapping[str, Any],
    decision_packet: Mapping[str, Any],
    source_registry: Mapping[str, Any],
    evidence_ledger: Mapping[str, Any],
) -> str:
    evidence_items = evidence_ledger.get("evidence_items")
    evidence_items = evidence_items if isinstance(evidence_items, list) else []
    evidence_summary = {
        "item_count": len(evidence_items),
        "source_ids": sorted(
            {
                str(item.get("source_id"))
                for item in evidence_items
                if isinstance(item, Mapping) and item.get("source_id")
            }
        ),
        "supported_metrics": sorted(
            {
                str(metric)
                for item in evidence_items
                if isinstance(item, Mapping)
                for metric in item.get("supports_metrics") or []
            }
        ),
    }
    payload = {
        "data_packet": data_packet,
        "metrics_packet": metrics_packet,
        "validation_report": validation_report,
        "decision_packet": decision_packet,
        "source_registry": source_registry,
        "evidence_summary": evidence_summary,
    }
    return "\n".join(
        [
            "# Room16 Validated Research Context",
            "",
            "This context is the sole factual and numerical authority for the report.",
            "Interpret it, but do not invent, refresh, or replace values in it.",
            "Missing information must remain explicitly unavailable.",
            "A final rating is allowed only when the decision packet carries an analytical or provisional conclusion; safety-fallback values are never report ratings.",
            "",
            "```json",
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
            "```",
            "",
        ]
    )


def _assess_packets(
    *,
    data_packet: Mapping[str, Any],
    metrics_packet: Mapping[str, Any],
    validation_report: Mapping[str, Any],
    decision_packet: Mapping[str, Any],
    source_registry: Mapping[str, Any],
    evidence_ledger: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str, str]:
    checks: list[dict[str, Any]] = []
    ticker = _normalized_symbol(data_packet.get("ticker"))
    as_of_date = _iso_date(data_packet.get("as_of_date"))
    _check(checks, "ticker_present", bool(ticker), detail=ticker)

    packet_identities = {
        "data_packet": (
            _normalized_symbol(data_packet.get("ticker")),
            str(data_packet.get("as_of_date") or ""),
        ),
        "metrics_packet": (
            _normalized_symbol(metrics_packet.get("ticker")),
            str(metrics_packet.get("as_of_date") or ""),
        ),
        "validation_report": (
            _normalized_symbol(validation_report.get("ticker")),
            str(validation_report.get("as_of_date") or ""),
        ),
        "decision_packet": (
            _normalized_symbol(decision_packet.get("ticker")),
            str(decision_packet.get("as_of_date") or ""),
        ),
        "evidence_ledger": (
            _normalized_symbol(evidence_ledger.get("ticker")),
            str(evidence_ledger.get("as_of_date") or ""),
        ),
    }
    expected_identity = (ticker, as_of_date)
    mismatches = {
        name: identity
        for name, identity in packet_identities.items()
        if identity != expected_identity
    }
    _check(
        checks,
        "packet_identity_consistent",
        not mismatches,
        detail=json.dumps(mismatches, sort_keys=True),
    )

    price_basis = data_packet.get("price_basis")
    price_basis = price_basis if isinstance(price_basis, Mapping) else {}
    price_date = str(price_basis.get("date") or "")
    try:
        price_not_future = bool(price_date) and date.fromisoformat(price_date) <= date.fromisoformat(as_of_date)
    except ValueError:
        price_not_future = False
    _check(checks, "price_basis_not_after_as_of", price_not_future, detail=price_date)
    price_freshness = evaluate_price_freshness(
        price_date,
        reference_date=as_of_date,
        max_trading_day_age=2,
    )
    _check(
        checks,
        "price_basis_current_for_analysis",
        price_not_future and price_freshness.current_report_allowed,
        detail=json.dumps(price_freshness.to_dict(), sort_keys=True),
    )

    validation_issues = validation_report.get("issues")
    validation_issues = validation_issues if isinstance(validation_issues, list) else []
    blocking_issue_codes = [
        str(issue.get("code") or "")
        for issue in validation_issues
        if isinstance(issue, Mapping) and str(issue.get("severity") or "").lower() == "error"
    ]
    validation_clean = not bool(validation_report.get("has_blocking_errors")) and not blocking_issue_codes
    _check(
        checks,
        "deterministic_validation_clean",
        validation_clean,
        detail=",".join(blocking_issue_codes),
    )

    registry_id = str(source_registry.get("registry_id") or "")
    _check(
        checks,
        "source_registry_identity",
        bool(registry_id) and registry_id == str(data_packet.get("source_registry_id") or ""),
        detail=registry_id,
    )
    sources = source_registry.get("sources")
    sources = sources if isinstance(sources, list) else []
    source_ids = {
        str(source.get("source_id") or "")
        for source in sources
        if isinstance(source, Mapping) and source.get("source_id")
    }
    source_tickers = {
        _normalized_symbol(source.get("ticker"))
        for source in sources
        if isinstance(source, Mapping)
    }
    _check(
        checks,
        "source_ticker_consistent",
        bool(source_tickers) and source_tickers == {ticker},
        detail=",".join(sorted(source_tickers)),
    )

    def source_supports(
        source: Mapping[str, Any],
        *,
        source_types: set[str],
        used_for: set[str],
        max_rank: int,
    ) -> bool:
        source_type = str(source.get("source_type") or "")
        source_uses = {str(item) for item in source.get("used_for") or []}
        try:
            rank = int(source.get("authority_rank") or 99)
        except (TypeError, ValueError):
            rank = 99
        return source_type in source_types and rank <= max_rank and bool(source_uses & used_for)

    has_primary_financial = any(
        isinstance(source, Mapping)
        and source_supports(
            source,
            source_types=PRIMARY_FINANCIAL_SOURCE_TYPES,
            used_for=FINANCIAL_SOURCE_USES,
            max_rank=1,
        )
        for source in sources
    )
    _check(checks, "primary_financial_source_present", has_primary_financial)
    has_price_source = any(
        isinstance(source, Mapping)
        and source_supports(
            source,
            source_types=PRICE_SOURCE_TYPES,
            used_for=PRICE_SOURCE_USES,
            max_rank=2,
        )
        for source in sources
    )
    _check(checks, "authoritative_price_source_present", has_price_source)

    evidence_items = evidence_ledger.get("evidence_items")
    evidence_items = evidence_items if isinstance(evidence_items, list) else []
    unknown_evidence_sources = sorted(
        {
            str(item.get("source_id") or "")
            for item in evidence_items
            if isinstance(item, Mapping)
            and item.get("source_id")
            and str(item.get("source_id")) not in source_ids
        }
    )
    evidence_tickers = {
        _normalized_symbol(item.get("ticker"))
        for item in evidence_items
        if isinstance(item, Mapping)
    }
    _check(
        checks,
        "evidence_ledger_present",
        bool(evidence_items),
        detail=f"items={len(evidence_items)}",
    )
    _check(
        checks,
        "evidence_sources_registered",
        not unknown_evidence_sources,
        detail=",".join(unknown_evidence_sources),
    )
    _check(
        checks,
        "evidence_ticker_consistent",
        bool(evidence_tickers) and evidence_tickers == {ticker},
        detail=",".join(sorted(evidence_tickers)),
    )
    evidence_ids = [
        str(item.get("evidence_id") or "").strip()
        for item in evidence_items
        if isinstance(item, Mapping)
    ]
    evidence_id_counts = Counter(evidence_ids)
    duplicate_evidence_ids = sorted(
        evidence_id
        for evidence_id, count in evidence_id_counts.items()
        if evidence_id and count > 1
    )
    missing_evidence_id_count = sum(not evidence_id for evidence_id in evidence_ids)
    _check(
        checks,
        "evidence_ids_unique",
        not duplicate_evidence_ids and missing_evidence_id_count == 0,
        detail=json.dumps(
            {
                "duplicate_ids": duplicate_evidence_ids,
                "missing_id_count": missing_evidence_id_count,
            },
            sort_keys=True,
        ),
    )
    unit_failures = _unit_normalization_failures(
        item for item in evidence_items if isinstance(item, Mapping)
    )
    _check(
        checks,
        "unit_normalization_valid",
        not unit_failures,
        detail=",".join(unit_failures),
    )

    material_metrics = dict(_metric_items(metrics_packet))
    technical = metrics_packet.get("technical")
    technical = technical if isinstance(technical, Mapping) else {}
    missing_metric_evidence = sorted(
        metric_name
        for metric_name, value in material_metrics.items()
        if not _has_exact_numeric_evidence(
            (
                item
                for item in evidence_items
                if isinstance(item, Mapping)
            ),
            metric_name,
            value,
            currency=str(price_basis.get("currency") or "USD"),
            price_date=price_date,
            indicator_date=str(technical.get("indicator_date") or ""),
        )
    )
    _check(
        checks,
        "material_metrics_evidence_mapped",
        not missing_metric_evidence,
        detail=",".join(missing_metric_evidence),
    )

    fundamentals = metrics_packet.get("fundamentals")
    fundamentals = fundamentals if isinstance(fundamentals, Mapping) else {}
    valuation = metrics_packet.get("valuation")
    valuation = valuation if isinstance(valuation, Mapping) else {}
    listed_share_count = fundamentals.get("listed_share_count")
    market_cap = valuation.get("market_cap")
    share_basis = str(valuation.get("market_cap_share_basis") or "")
    _check(
        checks,
        "market_cap_uses_point_in_time_shares",
        not (
            market_cap is not None
            and listed_share_count is not None
            and share_basis != "listed_share_count"
        ),
        detail=share_basis,
    )
    _check(
        checks,
        "market_cap_rejects_unverified_multi_class_price_basis",
        not (
            market_cap is not None
            and fundamentals.get("economic_share_count_basis")
            == MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED
        ),
        detail=str(fundamentals.get("economic_share_count_basis") or ""),
    )

    ttm_metric_names = {
        name
        for name in (
            "revenue_ttm",
            "operating_income_ttm",
            "net_income_ttm",
            "operating_cash_flow_ttm",
            "capex_ttm",
            "free_cash_flow_ttm",
            "buybacks",
            "dividends_paid",
            "shareholder_distributions_ttm",
            "shareholder_distributions_minus_fcf_ttm",
            "sbc_ttm",
        )
        if fundamentals.get(name) is not None
    }
    ttm_evidence = {
        metric
        for item in evidence_items
        if isinstance(item, Mapping)
        and (
            (
                item.get("formula_id")
                and isinstance(item.get("formula_operands"), Mapping)
                and item.get("formula_operands")
            )
            or (
                item.get("value") is not None
                and re.search(
                    r"(?:^|_)FY$|^FY\d{4}$",
                    str(item.get("period") or ""),
                    re.IGNORECASE,
                )
            )
        )
        for metric in item.get("supports_metrics") or []
    }
    missing_ttm_bridges = sorted(ttm_metric_names - ttm_evidence)
    _check(
        checks,
        "ttm_formula_operands_evidenced",
        not missing_ttm_bridges,
        detail=",".join(missing_ttm_bridges),
    )

    fcf_formula = str(fundamentals.get("free_cash_flow_formula") or "")
    _check(
        checks,
        "fcf_definition_explicit",
        fundamentals.get("free_cash_flow_ttm") is None
        or fcf_formula
        in {
            "cfo_minus_capex",
            "company_defined",
            "analyst_defined",
        },
        detail=fcf_formula,
    )

    permission = decision_packet.get("rating_permission")
    permission = permission if isinstance(permission, Mapping) else {}
    preferred = str(permission.get("preferred_rating") or "")
    allowed = {str(item) for item in permission.get("allowed_ratings") or []}
    blocked = {str(item) for item in permission.get("blocked_ratings") or []}
    _check(
        checks,
        "decision_permission_consistent",
        bool(preferred) and preferred in allowed and preferred not in blocked,
        detail=preferred,
    )
    analytical_rating = str(
        decision_packet.get("analytical_rating_unconstrained") or ""
    )
    conclusion_status = str(decision_packet.get("conclusion_status") or "")
    evidence_maturity = str(decision_packet.get("evidence_maturity") or "")
    publication_permission = str(
        decision_packet.get("publication_permission") or ""
    )
    permission_type = str(permission.get("permission_type") or "")
    display_rating = str(permission.get("display_rating") or "")
    publication_allowed = permission.get("publication_allowed")
    fallback_only = permission.get("fallback_only")
    expected_maturity = {
        "rated": "complete",
        "provisional": "partial",
        "not_rated": "incomplete",
        "blocked": "blocked",
    }.get(conclusion_status)
    expected_publication_permission = {
        "rated": "eligible",
        "provisional": "manual_review",
        "not_rated": "blocked",
        "blocked": "blocked",
    }.get(conclusion_status)
    _check(
        checks,
        "decision_status_dimensions_consistent",
        bool(expected_maturity)
        and evidence_maturity == expected_maturity
        and publication_permission == expected_publication_permission,
        detail=(
            f"status={conclusion_status};maturity={evidence_maturity};"
            f"publication={publication_permission}"
        ),
    )
    if conclusion_status == "rated":
        rating_state_valid = (
            bool(analytical_rating)
            and analytical_rating == preferred
            and permission_type == "analytical"
            and display_rating == analytical_rating
            and publication_allowed is True
            and fallback_only is False
        )
    elif conclusion_status == "provisional":
        rating_state_valid = (
            bool(analytical_rating)
            and analytical_rating == preferred
            and permission_type == "provisional"
            and display_rating == f"Provisional — {analytical_rating}"
            and publication_allowed is False
            and fallback_only is False
        )
    elif conclusion_status in {"not_rated", "blocked"}:
        rating_state_valid = (
            not analytical_rating
            and permission_type == "safety_fallback"
            and display_rating == "Unrated"
            and publication_allowed is False
            and fallback_only is True
        )
    else:
        rating_state_valid = False
    _check(
        checks,
        "analytical_rating_state_consistent",
        rating_state_valid,
        detail=(
            f"status={conclusion_status};analytical={analytical_rating or 'null'};"
            f"display={display_rating};permission_type={permission_type}"
        ),
    )
    return checks, ticker, as_of_date


def build_authority_bundle(
    *,
    packet_dir: str | Path,
    output_dir: str | Path,
    source_registry_path: str | Path | None = None,
    fact_ledger_path: str | Path | None = None,
    source_snapshot_manifest_path: str | Path | None = None,
    source_snapshot_root: str | Path | None = None,
    research_scope_coverage_path: str | Path | None = None,
    pipeline_version: str = PIPELINE_VERSION,
) -> dict[str, Any]:
    """Export a self-contained, hashed authority bundle from validated packets."""

    source_dir = Path(packet_dir).expanduser().resolve()
    target_dir = Path(output_dir).expanduser().resolve()
    payloads: dict[str, dict[str, Any]] = {}
    source_paths: dict[str, Path] = {}
    for role, filename in REQUIRED_PACKET_FILES.items():
        path = source_dir / filename
        source_paths[role] = path
        payloads[role] = _read_json(path)
    registry_path = _resolve_source_registry_path(
        source_dir,
        payloads["data_packet"],
        source_registry_path,
    )
    source_paths["source_registry"] = registry_path
    payloads["source_registry"] = _read_json(registry_path)
    if fact_ledger_path is None:
        adjacent_fact_ledger = source_dir / "fact_ledger.json"
        if adjacent_fact_ledger.is_file():
            fact_ledger_path = adjacent_fact_ledger
    if fact_ledger_path:
        ledger_path = Path(fact_ledger_path).expanduser().resolve()
        source_paths["fact_ledger"] = ledger_path
        payloads["fact_ledger"] = _read_json(ledger_path)
    if source_snapshot_manifest_path is None or source_snapshot_root is None:
        raise AuthorityBundleError(
            "source snapshot manifest and source root are required by authority contract v3"
        )
    snapshot_manifest_path = Path(source_snapshot_manifest_path).expanduser().resolve()
    snapshot_root = Path(source_snapshot_root).expanduser().resolve()
    source_snapshot_manifest = _read_json(snapshot_manifest_path)
    snapshot_verification = verify_source_snapshot_manifest(
        source_snapshot_manifest,
        source_root=snapshot_root,
    )
    if research_scope_coverage_path is None:
        raise AuthorityBundleError(
            "research scope coverage is required by authority contract v3"
        )
    scope_path = Path(research_scope_coverage_path).expanduser().resolve()
    source_paths["research_scope_coverage"] = scope_path
    research_scope_coverage = _read_json(scope_path)
    scope_verification = verify_research_scope_coverage(research_scope_coverage)

    checks, ticker, as_of_date = _assess_packets(
        data_packet=payloads["data_packet"],
        metrics_packet=payloads["metrics_packet"],
        validation_report=payloads["validation_report"],
        decision_packet=payloads["decision_packet"],
        source_registry=payloads["source_registry"],
        evidence_ledger=payloads["evidence_ledger"],
    )
    _check(
        checks,
        "canonical_fact_ledger_present",
        "fact_ledger" in payloads,
        detail=str(source_paths.get("fact_ledger") or ""),
    )
    if "fact_ledger" in payloads:
        fact_ledger = payloads["fact_ledger"]
        _check(
            checks,
            "fact_ledger_identity_matches_packets",
            _normalized_symbol(fact_ledger.get("ticker")) == ticker
            and str(fact_ledger.get("report_asof") or "") == as_of_date,
            detail=(
                f"{fact_ledger.get('ticker')}@"
                f"{fact_ledger.get('report_asof')}"
            ),
        )
    _check(
        checks,
        "source_snapshot_contract_valid",
        bool(snapshot_verification["verified"]),
        detail=", ".join(snapshot_verification["blocking_failures"]),
    )
    _check(
        checks,
        "source_snapshot_identity_matches_packets",
        _normalized_symbol(source_snapshot_manifest.get("ticker")) == ticker
        and str(source_snapshot_manifest.get("as_of_date") or "") == as_of_date,
        detail=(
            f"{source_snapshot_manifest.get('ticker')}@"
            f"{source_snapshot_manifest.get('as_of_date')}"
        ),
    )
    _check(
        checks,
        "all_registry_sources_dispositioned",
        bool(source_snapshot_manifest.get("all_sources_dispositioned")),
        detail=", ".join(source_snapshot_manifest.get("blocking_source_ids") or []),
    )
    snapshot_quality_axes = source_snapshot_manifest.get("quality_axes")
    snapshot_quality_axes = (
        snapshot_quality_axes if isinstance(snapshot_quality_axes, Mapping) else {}
    )
    _check(
        checks,
        "source_inventory_complete",
        snapshot_quality_axes.get("source_inventory_complete") is True,
    )
    _check(
        checks,
        "material_event_content_complete",
        snapshot_quality_axes.get("material_event_content_complete") is True,
    )
    registry_source_ids = {
        str(item.get("source_id") or "")
        for item in payloads["source_registry"].get("sources") or []
    }
    snapshot_source_ids = {
        str(item.get("source_id") or "")
        for item in source_snapshot_manifest.get("source_dispositions") or []
    }
    _check(
        checks,
        "source_snapshot_registry_matches",
        registry_source_ids == snapshot_source_ids and "" not in registry_source_ids,
        detail=(
            f"registry={len(registry_source_ids)} "
            f"snapshots={len(snapshot_source_ids)}"
        ),
    )
    _check(
        checks,
        "research_scope_coverage_valid",
        bool(scope_verification["verified"]),
        detail=", ".join(scope_verification["blocking_failures"]),
    )
    _check(
        checks,
        "research_scope_identity_matches_packets",
        _normalized_symbol(research_scope_coverage.get("ticker")) == ticker
        and str(research_scope_coverage.get("as_of_date") or "") == as_of_date,
        detail=(
            f"{research_scope_coverage.get('ticker')}@"
            f"{research_scope_coverage.get('as_of_date')}"
        ),
    )
    _check(
        checks,
        "all_required_research_scopes_complete",
        bool(research_scope_coverage.get("all_required_scopes_complete")),
        detail=", ".join(
            research_scope_coverage.get("blocking_scope_gaps") or []
        ),
    )
    blocking_failures = [
        item["check_id"]
        for item in checks
        if item["blocking"] and item["status"] != "pass"
    ]

    target_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, dict[str, Any]] = {}
    for role, source_path in source_paths.items():
        target_path = target_dir / source_path.name
        shutil.copy2(source_path, target_path)
        artifacts[role] = {
            "path": target_path.name,
            "sha256": _sha256(target_path),
            "bytes": target_path.stat().st_size,
        }

    snapshot_target_root = target_dir / "source_snapshots"
    snapshot_target_root.mkdir(parents=True, exist_ok=True)
    for item in source_snapshot_manifest.get("artifacts") or []:
        relative = Path(str(item.get("path") or ""))
        source_path = (snapshot_root / relative).resolve()
        target_path = (snapshot_target_root / relative).resolve()
        if (
            snapshot_root not in source_path.parents
            or snapshot_target_root not in target_path.parents
        ):
            raise AuthorityBundleError(f"invalid source snapshot path: {relative}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
    exported_snapshot_manifest = dict(source_snapshot_manifest)
    exported_snapshot_manifest["source_root"] = "source_snapshots"
    exported_snapshot_manifest_path = target_dir / "source_snapshot_manifest.json"
    exported_snapshot_manifest_path.write_text(
        json.dumps(
            exported_snapshot_manifest,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    artifacts["source_snapshot_manifest"] = {
        "path": exported_snapshot_manifest_path.name,
        "sha256": _sha256(exported_snapshot_manifest_path),
        "bytes": exported_snapshot_manifest_path.stat().st_size,
    }

    context_path = target_dir / "validated_context.md"
    context_path.write_text(
        _build_validated_context(
            data_packet=payloads["data_packet"],
            metrics_packet=payloads["metrics_packet"],
            validation_report=payloads["validation_report"],
            decision_packet=payloads["decision_packet"],
            source_registry=payloads["source_registry"],
            evidence_ledger=payloads["evidence_ledger"],
        ),
        encoding="utf-8",
    )
    artifacts["validated_context"] = {
        "path": context_path.name,
        "sha256": _sha256(context_path),
        "bytes": context_path.stat().st_size,
    }

    manifest = {
        "contract_id": AUTHORITY_CONTRACT_ID,
        "contract_version": AUTHORITY_CONTRACT_VERSION,
        "pipeline_version": pipeline_version,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "ticker": ticker,
        "as_of_date": as_of_date,
        "analysis_allowed": not blocking_failures,
        "publication_allowed": bool(
            not blocking_failures
            and payloads["decision_packet"].get("publication_permission")
            == "eligible"
            and (
                payloads["decision_packet"].get("rating_permission") or {}
            ).get("publication_allowed")
            is True
        ),
        "blocking_failures": blocking_failures,
        "checks": checks,
        "artifacts": artifacts,
        "rating_permission": payloads["decision_packet"].get("rating_permission") or {},
    }
    manifest_path = target_dir / "authority_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_authority_bundle(bundle_dir: str | Path) -> dict[str, Any]:
    """Verify identity, hashes, packets, and permission without mutating the bundle."""

    root = Path(bundle_dir).expanduser().resolve()
    manifest = _read_json(root / "authority_manifest.json")
    checks: list[dict[str, Any]] = []
    _check(
        checks,
        "contract_identity",
        manifest.get("contract_id") == AUTHORITY_CONTRACT_ID
        and manifest.get("contract_version") == AUTHORITY_CONTRACT_VERSION,
        detail=f"{manifest.get('contract_id')}@{manifest.get('contract_version')}",
    )
    _check(
        checks,
        "manifest_gate_consistent",
        _manifest_gate_consistent(manifest),
    )
    artifacts = manifest.get("artifacts")
    artifacts = artifacts if isinstance(artifacts, Mapping) else {}
    payloads: dict[str, dict[str, Any]] = {}
    for role in (
        *REQUIRED_PACKET_FILES.keys(),
        "source_registry",
        "fact_ledger",
        "source_snapshot_manifest",
        "research_scope_coverage",
        "validated_context",
    ):
        item = artifacts.get(role)
        if not isinstance(item, Mapping):
            _check(checks, f"artifact_{role}", False, detail="manifest entry missing")
            continue
        path = root / str(item.get("path") or "")
        exists = path.is_file()
        hash_matches = exists and _sha256(path) == str(item.get("sha256") or "")
        _check(
            checks,
            f"artifact_{role}",
            bool(exists and hash_matches),
            detail=str(path),
        )
        if role != "validated_context" and exists and hash_matches:
            payloads[role] = _read_json(path)

    if "source_snapshot_manifest" in payloads:
        snapshot_verification = verify_source_snapshot_manifest(
            payloads["source_snapshot_manifest"],
            source_root=root / "source_snapshots",
        )
        _check(
            checks,
            "source_snapshot_contract_valid",
            bool(snapshot_verification["verified"]),
            detail=", ".join(snapshot_verification["blocking_failures"]),
        )
        _check(
            checks,
            "all_registry_sources_dispositioned",
            bool(payloads["source_snapshot_manifest"].get("all_sources_dispositioned")),
            detail=", ".join(
                payloads["source_snapshot_manifest"].get("blocking_source_ids") or []
            ),
        )
        snapshot_quality_axes = payloads["source_snapshot_manifest"].get(
            "quality_axes"
        )
        snapshot_quality_axes = (
            snapshot_quality_axes
            if isinstance(snapshot_quality_axes, Mapping)
            else {}
        )
        _check(
            checks,
            "source_inventory_complete",
            snapshot_quality_axes.get("source_inventory_complete") is True,
        )
        _check(
            checks,
            "material_event_content_complete",
            snapshot_quality_axes.get("material_event_content_complete") is True,
        )
        snapshot_source_ids = {
            str(item.get("source_id") or "")
            for item in payloads["source_snapshot_manifest"].get(
                "source_dispositions"
            )
            or []
        }
        registry_source_ids = {
            str(item.get("source_id") or "")
            for item in payloads.get("source_registry", {}).get("sources") or []
        }
        _check(
            checks,
            "source_snapshot_registry_matches",
            bool(registry_source_ids)
            and registry_source_ids == snapshot_source_ids
            and "" not in registry_source_ids,
            detail=(
                f"registry={len(registry_source_ids)} "
                f"snapshots={len(snapshot_source_ids)}"
            ),
        )

    if "research_scope_coverage" in payloads:
        scope_verification = verify_research_scope_coverage(
            payloads["research_scope_coverage"]
        )
        _check(
            checks,
            "research_scope_coverage_valid",
            bool(scope_verification["verified"]),
            detail=", ".join(scope_verification["blocking_failures"]),
        )
        _check(
            checks,
            "all_required_research_scopes_complete",
            bool(
                payloads["research_scope_coverage"].get(
                    "all_required_scopes_complete"
                )
            ),
            detail=", ".join(
                payloads["research_scope_coverage"].get("blocking_scope_gaps")
                or []
            ),
        )

    if all(role in payloads for role in (*REQUIRED_PACKET_FILES.keys(), "source_registry")):
        packet_checks, ticker, as_of_date = _assess_packets(
            data_packet=payloads["data_packet"],
            metrics_packet=payloads["metrics_packet"],
            validation_report=payloads["validation_report"],
            decision_packet=payloads["decision_packet"],
            source_registry=payloads["source_registry"],
            evidence_ledger=payloads["evidence_ledger"],
        )
        checks.extend(packet_checks)
        _check(
            checks,
            "manifest_identity_matches_packets",
            _normalized_symbol(manifest.get("ticker")) == ticker
            and str(manifest.get("as_of_date") or "") == as_of_date,
        )
        if "fact_ledger" in payloads:
            _check(
                checks,
                "fact_ledger_identity_matches_packets",
                _normalized_symbol(payloads["fact_ledger"].get("ticker"))
                == ticker
                and str(
                    payloads["fact_ledger"].get("report_asof") or ""
                )
                == as_of_date,
            )
        if "research_scope_coverage" in payloads:
            _check(
                checks,
                "research_scope_identity_matches_packets",
                _normalized_symbol(
                    payloads["research_scope_coverage"].get("ticker")
                )
                == ticker
                and str(
                    payloads["research_scope_coverage"].get("as_of_date") or ""
                )
                == as_of_date,
            )
    blocking_failures = [
        item["check_id"]
        for item in checks
        if item["blocking"] and item["status"] != "pass"
    ]
    manifest_allows = bool(manifest.get("analysis_allowed"))
    verified = manifest_allows and not blocking_failures
    return {
        "contract_id": AUTHORITY_CONTRACT_ID,
        "contract_version": AUTHORITY_CONTRACT_VERSION,
        "status": "pass" if verified else "fail",
        "analysis_allowed": verified,
        "blocking_failures": blocking_failures,
        "checks": checks,
        "manifest": manifest,
    }
