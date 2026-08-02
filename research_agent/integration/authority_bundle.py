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


AUTHORITY_CONTRACT_ID = "room16.research_authority_bundle"
AUTHORITY_CONTRACT_VERSION = 2
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
            "The final rating must remain within `decision_packet.rating_permission.allowed_ratings`.",
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
    _check(
        checks,
        "analytical_rating_independent_present",
        bool(analytical_rating),
        detail=analytical_rating,
    )
    return checks, ticker, as_of_date


def build_authority_bundle(
    *,
    packet_dir: str | Path,
    output_dir: str | Path,
    source_registry_path: str | Path | None = None,
    fact_ledger_path: str | Path | None = None,
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
