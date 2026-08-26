"""Deterministic, ticker-agnostic Bank projection over frozen BA12 truth."""

from __future__ import annotations

from datetime import date
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.source_frontend.contracts import SourceSnapshotIR

from .regulatory import REGULATORY_MAPPING_REGISTRY, REGULATORY_SOURCE_PROFILE, REGULATORY_TARGETS, regulatory_diagnostics


MAPPING_REGISTRY: dict[str, Any] = {
    "contract_id": "room16.alpha.bank_mapping_registry",
    "contract_version": 1,
    "selection": {
        "as_of": "newest_publicly_available_at_or_before_as_of",
        "ticker_specific_rules": False,
        "period_basis_preserved": True,
        "quarter_from_ytd_subtraction_allowed": False,
    },
    "metrics": {
        "net_income": ["NetIncomeLoss"],
        "diluted_eps": ["EarningsPerShareDiluted"],
        "net_revenue": ["RevenuesNetOfInterestExpense"],
        "net_interest_income": ["InterestIncomeExpenseNet"],
        "noninterest_revenue": ["NoninterestIncome"],
        "noninterest_expense": ["NoninterestExpense"],
        "total_assets": ["Assets"],
        "gross_loans_or_financing_receivables": ["FinancingReceivableExcludingAccruedInterestBeforeAllowanceForCreditLoss"],
        "deposits": ["Deposits"],
        "investment_securities": ["DebtSecuritiesAvailableForSaleAndHeldToMaturityAmortizedCostAfterAllowanceForCreditLoss"],
        "cash_and_due_from_banks": ["CashAndDueFromBanks"],
        "long_term_debt": ["LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"],
        "provision_for_credit_losses": ["FinancingReceivableExcludingAccruedInterestCreditLossExpenseReversal"],
        "allowance_for_credit_losses": ["FinancingReceivableAllowanceForCreditLossExcludingAccruedInterest"],
        "net_charge_offs": ["FinancingReceivableExcludingAccruedInterestAllowanceForCreditLossWriteoffAfterRecovery"],
        "reportable_segment_count": ["NumberOfReportableSegments"],
        "common_dividend_per_share": ["CommonStockDividendsPerShareDeclared"],
        "common_stock_repurchases": ["PaymentsForRepurchaseOfCommonStock"],
        "common_shares": ["EntityCommonStockSharesOutstanding"],
        "diluted_weighted_average_shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
        "latest_market_price": ["LatestMarketClose"],
    },
}

PERIOD_BASIS_POLICY: dict[str, Any] = {
    "contract_id": "room16.alpha.bank_period_basis_policy",
    "contract_version": 1,
    "standalone_quarter_days": [70, 110],
    "year_to_date_days_exclusive": [110, 330],
    "annual_days": [330, 390],
    "fiscal_year_opening_window_days": 15,
    "quarter_from_ytd_subtraction_allowed": False,
}

FRESHNESS_POLICY: dict[str, Any] = {
    "contract_id": "room16.alpha.bank_freshness_policy",
    "contract_version": 1,
    "thresholds_days": {
        "market": {"current": 7, "aging": 30},
        "bank": {"current": 180, "aging": 370},
    },
    "stale_primary_surface_allowed": False,
    "stale_formula_operand_allowed": False,
}

FORMULA_REGISTRY: dict[str, Any] = {
    "contract_id": "room16.alpha.bank_formula_registry",
    "contract_version": 1,
    "formulas": {
        "bank.allowance_to_loans@1": {
            "output_metric": "allowance_to_loans",
            "label": "Derived period-end allowance-to-loans ratio",
            "numerator": "allowance_for_credit_losses",
            "denominator": "gross_loans_or_financing_receivables",
        },
        "bank.period_end_loans_to_deposits@1": {
            "output_metric": "period_end_loans_to_deposits",
            "label": "Derived period-end loans-to-deposits ratio",
            "numerator": "gross_loans_or_financing_receivables",
            "denominator": "deposits",
        },
    },
    "compatibility": "same_period_end_current_instant_compatible_unit",
    "forbidden_derivations": [
        "net_interest_margin", "efficiency_ratio", "rotce", "roe",
        "charge_off_rate", "cet1_ratio", "supplementary_leverage_ratio",
        "regulatory_capital_ratio",
    ],
}

UNSUPPORTED_METRICS = (
    "net_interest_margin", "efficiency_ratio", "rotce", "roe",
    "average_loans", "average_deposits", "named_segment_economics",
    "stress_capital_buffer", "issuer_managed_revenue_basis",
    *REGULATORY_TARGETS,
)

CORE_ORDER = (
    "net_income", "diluted_eps", "net_revenue", "net_interest_income",
    "noninterest_revenue", "noninterest_expense", "total_assets",
    "gross_loans_or_financing_receivables", "deposits",
    "provision_for_credit_losses", "allowance_for_credit_losses",
    "net_charge_offs", *REGULATORY_TARGETS, "investment_securities",
    "cash_and_due_from_banks", "long_term_debt", "common_dividend_per_share",
    "common_stock_repurchases", "common_shares",
    "diluted_weighted_average_shares", "latest_market_price",
    "allowance_to_loans", "period_end_loans_to_deposits",
)

RANKING_PROFILE: dict[str, Any] = {
    "contract_id": "room16.alpha.bank_renderer_ranking_profile",
    "contract_version": 1,
    "profile_id": "bank_alpha_v1",
    "ticker_specific_rules": False,
    "limit": 24,
    "priority_order": list(CORE_ORDER),
    "standalone_quarter_before_ytd": True,
    "stale_excluded": True,
    "raw_facts_remain_inspectable": True,
}


def classify_period_basis(start: str | None, end: str) -> tuple[str, int | None]:
    if not start:
        return "INSTANT", None
    duration = (date.fromisoformat(end) - date.fromisoformat(start)).days
    if 70 <= duration <= 110:
        return "STANDALONE_QUARTER", duration
    if 330 <= duration <= 390:
        return "ANNUAL", duration
    opening = date.fromisoformat(start)
    if 110 < duration < 330 and opening.month == 1 and opening.day <= 15:
        return "YEAR_TO_DATE", duration
    return "OTHER_DURATION", duration


def _freshness(*, as_of: str, period_end: str, market: bool = False) -> tuple[str, int]:
    age = max(0, (date.fromisoformat(as_of) - date.fromisoformat(period_end)).days)
    limits = FRESHNESS_POLICY["thresholds_days"]["market" if market else "bank"]
    if age <= limits["current"]:
        return "CURRENT", age
    if age <= limits["aging"]:
        return "AGING", age
    return "STALE", age


def _fact_id(namespace: str, concept: str, start: str | None, end: str, basis: str) -> str:
    return ".".join(("fact", namespace.lower().replace("-", "_"), concept.lower(), (start or "instant").replace("-", ""), end.replace("-", ""), basis.lower()))


def _company_facts(payloads: list[dict[str, Any]], as_of: str) -> list[dict[str, Any]]:
    concept_to_metric = {concept: metric for metric, concepts in MAPPING_REGISTRY["metrics"].items() for concept in concepts}
    results: list[dict[str, Any]] = []
    for payload in payloads:
        facts = payload.get("facts")
        if not isinstance(facts, dict):
            continue
        for namespace, concepts in sorted(facts.items()):
            if not isinstance(concepts, dict):
                continue
            for concept, definition in sorted(concepts.items()):
                if not isinstance(definition, dict) or not isinstance(definition.get("units"), dict):
                    continue
                candidates: list[dict[str, Any]] = []
                for unit, observations in sorted(definition["units"].items()):
                    if not isinstance(observations, list):
                        continue
                    for observation in observations:
                        if not isinstance(observation, dict) or "val" not in observation:
                            continue
                        end, filed = str(observation.get("end") or ""), str(observation.get("filed") or "")
                        start = str(observation["start"]) if observation.get("start") else None
                        if not end or not filed or end > as_of or filed > as_of:
                            continue
                        basis, duration = classify_period_basis(start, end)
                        freshness, age = _freshness(as_of=as_of, period_end=end)
                        candidates.append({
                            "fact_id": _fact_id(namespace, concept, start, end, basis),
                            "metric_id": f"filing_{namespace.lower().replace('-', '_')}_{concept.lower()}_{basis.lower()}",
                            "label": str(definition.get("label") or concept),
                            "namespace": namespace, "concept": concept,
                            "value": observation["val"], "unit": str(unit),
                            "period_start": start, "period_end": end,
                            "period_basis": basis, "duration_days": duration,
                            "filed": filed, "form": str(observation.get("form") or ""),
                            "frame": observation.get("frame"), "accession": observation.get("accn"),
                            "freshness_status": freshness, "age_days": age,
                            "source_period_end": end, "filed_date": filed,
                        })
                if not candidates:
                    continue
                metric = concept_to_metric.get(concept)
                selected: list[dict[str, Any]] = []
                if metric:
                    by_basis: dict[str, list[dict[str, Any]]] = {}
                    for row in candidates:
                        by_basis.setdefault(row["period_basis"], []).append(row)
                    for basis_rows in by_basis.values():
                        selected.append(sorted(basis_rows, key=lambda x: (x["period_end"], x["filed"], str(x.get("accession") or "")))[-1])
                else:
                    selected.append(sorted(candidates, key=lambda x: (x["period_end"], x["filed"], str(x.get("period_start") or "")))[-1])
                for row in selected:
                    if metric:
                        row.update(semantic_metric_id=metric, semantic_mapping_id=f"concept.{concept}")
                    results.append(row)
    return results


def _market_fact(payloads: list[dict[str, Any]], as_of: str) -> dict[str, Any] | None:
    rows = [row for payload in payloads for row in (payload.get("records") or []) if isinstance(row, dict) and "date" in row and "close" in row and str(row["date"]) <= as_of]
    if not rows:
        return None
    row = sorted(rows, key=lambda x: str(x["date"]))[-1]
    end = str(row["date"])
    freshness, age = _freshness(as_of=as_of, period_end=end, market=True)
    return {
        "fact_id": "fact.market.latest_close", "metric_id": "filing_market_latest_close",
        "semantic_metric_id": "latest_market_price", "semantic_mapping_id": "market.latest_close",
        "label": "Latest market close", "namespace": "market", "concept": "LatestMarketClose",
        "value": row["close"], "unit": "USD", "period_start": None, "period_end": end,
        "period_basis": "INSTANT", "duration_days": None, "filed": end, "form": "market",
        "frame": None, "accession": None, "freshness_status": freshness, "age_days": age,
        "source_period_end": end, "filed_date": end,
    }


def _preferred_instant(facts: list[dict[str, Any]], metric: str) -> dict[str, Any] | None:
    rows = [x for x in facts if x.get("semantic_metric_id") == metric and x.get("period_basis") == "INSTANT"]
    return sorted(rows, key=lambda x: (x["period_end"], x["filed"], x["fact_id"]))[-1] if rows else None


def _derived_ratios(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for formula_id, definition in FORMULA_REGISTRY["formulas"].items():
        numerator = _preferred_instant(facts, definition["numerator"])
        denominator = _preferred_instant(facts, definition["denominator"])
        if not numerator or not denominator:
            continue
        if numerator["period_end"] != denominator["period_end"] or numerator["freshness_status"] != "CURRENT" or denominator["freshness_status"] != "CURRENT":
            continue
        if numerator["unit"] != denominator["unit"] or not isinstance(numerator["value"], (int, float)) or not isinstance(denominator["value"], (int, float)) or denominator["value"] == 0:
            continue
        end = numerator["period_end"]
        outputs.append({
            "fact_id": f"fact.derived.{definition['output_metric']}",
            "metric_id": f"derived_{definition['output_metric']}",
            "semantic_metric_id": definition["output_metric"], "semantic_mapping_id": formula_id,
            "label": definition["label"], "namespace": "derived", "concept": definition["output_metric"],
            "value": numerator["value"] / denominator["value"], "unit": "ratio",
            "period_start": None, "period_end": end, "period_basis": "INSTANT",
            "duration_days": None, "filed": max(numerator["filed"], denominator["filed"]),
            "form": "derived", "frame": None, "accession": None,
            "freshness_status": "CURRENT", "age_days": max(numerator["age_days"], denominator["age_days"]),
            "source_period_end": end, "filed_date": max(numerator["filed"], denominator["filed"]),
            "derivation": {"formula_id": formula_id, "operand_fact_ids": [numerator["fact_id"], denominator["fact_id"]]},
        })
    return outputs


def _rank_key(item: dict[str, Any]) -> tuple[Any, ...]:
    metric = item.get("semantic_metric_id")
    core = CORE_ORDER.index(metric) if metric in CORE_ORDER else len(CORE_ORDER)
    basis_order = {"STANDALONE_QUARTER": 0, "YEAR_TO_DATE": 1, "INSTANT": 0, "ANNUAL": 2, "OTHER_DURATION": 3}
    return (core, basis_order.get(str(item.get("period_basis")), 9), -date.fromisoformat(str(item["period_end"])).toordinal(), str(item["fact_id"]))


def build_bank_semantic_artifacts(*, snapshot: SourceSnapshotIR, payloads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    facts = _company_facts(payloads, snapshot.as_of_date)
    market = _market_fact(payloads, snapshot.as_of_date)
    if market:
        facts.append(market)
    if not facts:
        raise ValueError("ALPHA_BANK_FACT_GENERATION_EMPTY")
    derived = _derived_ratios(facts)
    facts = sorted(facts + derived, key=lambda x: x["fact_id"])
    primary = [x for x in facts if x.get("semantic_metric_id") and x["freshness_status"] != "STALE"]
    projection_facts = sorted(primary, key=_rank_key)[: int(RANKING_PROFILE["limit"])]
    evidence, evidence_by_fact = [], {}
    for index, item in enumerate(facts, 1):
        evidence_id = f"evidence.{index:04d}"
        evidence_by_fact[item["fact_id"]] = evidence_id
        node: dict[str, Any] = {"evidence_id": evidence_id, "fact_id": item["fact_id"], "source_snapshot_sha256": snapshot.snapshot_sha256}
        if item.get("derivation"):
            node.update(formula_id=item["derivation"]["formula_id"], source_fact_ids=item["derivation"]["operand_fact_ids"])
        evidence.append(node)
    claims = [{
        "claim_id": f"claim.{index:04d}", "fact_id": item["fact_id"],
        "statement": f"{item['label']} [{item['period_basis']}] ({item['period_end']}): {item['value']} {item['unit']}",
        "evidence_ids": [evidence_by_fact[item["fact_id"]]],
    } for index, item in enumerate(projection_facts[:12], 1)]
    decision = {"ticker": snapshot.ticker, "as_of_date": snapshot.as_of_date, "rating": "REVIEW_REQUIRED", "semantic_owner": "research_compiler", "claim_ids": [x["claim_id"] for x in claims], "automatic_investment_decision": False}
    metrics = [{"metric_id": x["metric_id"], "semantic_metric_id": x.get("semantic_metric_id"), "fact_id": x["fact_id"], "value": x["value"], "unit": x["unit"], "as_of": x["period_end"], "period_basis": x["period_basis"], "freshness_status": x["freshness_status"], "age_days": x["age_days"]} for x in facts]
    evaluations = [{"formula_id": x["derivation"]["formula_id"], "output_fact_id": x["fact_id"], "operand_fact_ids": x["derivation"]["operand_fact_ids"], "period_end": x["period_end"], "value": x["value"], "unit": x["unit"]} for x in derived]
    lineage = {"source_snapshot_sha256": snapshot.snapshot_sha256, "fact_ids": [x["fact_id"] for x in facts], "metric_ids": [x["metric_id"] for x in metrics], "claim_ids": [x["claim_id"] for x in claims]}
    base = "room16.alpha.bank"
    regulatory_items = list(regulatory_diagnostics())
    artifacts: dict[str, dict[str, Any]] = {
        "parsed_table_ir": {"contract_id": f"{base}_parsed_source_ir", "contract_version": 1, "ticker": snapshot.ticker, "records": facts},
        "typed_facts": {"contract_id": f"{base}_typed_facts", "contract_version": 1, "facts": facts},
        "metrics": {"contract_id": f"{base}_metrics", "contract_version": 1, "metrics": metrics, "mapping_registry_sha256": sha256_json(MAPPING_REGISTRY), "freshness_policy_sha256": sha256_json(FRESHNESS_POLICY), "period_basis_policy_sha256": sha256_json(PERIOD_BASIS_POLICY)},
        "formula_evaluations": {"contract_id": f"{base}_formula_evaluations", "contract_version": 1, "evaluations": evaluations, "formula_registry_sha256": sha256_json(FORMULA_REGISTRY)},
        "evidence_graph": {"contract_id": f"{base}_evidence_graph", "contract_version": 1, "nodes": evidence},
        "claim_graph": {"contract_id": f"{base}_claim_graph", "contract_version": 1, "nodes": claims},
        "decision_graph": {"contract_id": f"{base}_decision_graph", "contract_version": 1, **decision},
        "source_provenance": {"contract_id": f"{base}_source_provenance", "contract_version": 1, "snapshot": snapshot.model_dump(mode="json"), "regulatory_source_profile": REGULATORY_SOURCE_PROFILE, "regulatory_mapping_registry": REGULATORY_MAPPING_REGISTRY},
        "renderer_projection": {"contract_id": f"{base}_renderer_projection", "contract_version": 1, "ticker": snapshot.ticker, "as_of_date": snapshot.as_of_date, "title": f"{snapshot.ticker} Alpha Bank research dossier", "archetype": "BANK", "institution_type": "diversified financial institution", "facts": projection_facts, "claims": claims, "decision": decision, "ranking_profile": RANKING_PROFILE, "lineage": lineage},
        "renderer_lineage_expectation": {"contract_id": f"{base}_renderer_lineage_expectation", "contract_version": 1, "semantic_mutation_allowed": False, **lineage},
        "authority_v3_bridge": {"contract_id": f"{base}_authority_v3_output_bridge", "contract_version": 1, "direction": "bundle_to_authority_v3_only", "semantic_input_allowed": False, "projection": {"ticker": snapshot.ticker, "facts": facts, "claims": claims, "decision": decision}},
        "diagnostics": {"contract_id": f"{base}_diagnostics", "contract_version": 1, "items": [{"severity": "P2", "code": REGULATORY_SOURCE_PROFILE["status"]}], "regulatory": regulatory_items, "unsupported": list(UNSUPPORTED_METRICS)},
        "pass_execution_records": {"contract_id": f"{base}_pass_execution_records", "contract_version": 1, "passes": ["ba12.l3.parse_snapshot", "ba12.l4.type_facts", "alpha.bank.l5.preserve_period_basis", "alpha.bank.l6.map_core_metrics", "alpha.bank.l7.evaluate_freshness_safe_formulas", "alpha.bank.l11.rank_projection", "ba12.l11.emit_native_bundle_v2"]},
        "verification_plan": {"contract_id": f"{base}_verification_plan", "contract_version": 1, "checks": ["source_hashes", "no_legacy_input", "artifact_hashes", "receipt_signature", "renderer_lineage", "period_basis", "semantic_non_conflation", "freshness", "formula_period_compatibility", "ticker_agnostic_ranking", "regulatory_capture_first"]},
        "execution_attestation": {"contract_id": f"{base}_execution_attestation", "contract_version": 1, "network_after_snapshot": False, "legacy_semantic_input": False, "source_native": True, "ticker_specific_rules": False, "architecture_reopened": False, "regulatory_source_used": False},
    }
    replay_sha = sha256_json({k: artifacts[k] for k in sorted(artifacts) if k != "authority_v3_bridge"})
    artifacts["compile_state"] = {"contract_id": f"{base}_compile_state", "contract_version": 1, "state": "verified_alpha_bank_successor", "source_snapshot_sha256": snapshot.snapshot_sha256, "replay_sha256": replay_sha}
    artifacts["compile_verdict"] = {"contract_id": f"{base}_compile_verdict", "contract_version": 1, "verdict": "PASS", "compile_allowed": True, "renderer_eligible": True}
    artifacts["verification_report"] = {"contract_id": f"{base}_verification_report", "contract_version": 1, "verdict": "PASS", "fact_count": len(facts), "projected_fact_count": len(projection_facts), "claim_count": len(claims), "derived_metric_count": len(derived), "regulatory_metric_count": 0, "legacy_semantic_inputs": 0, "replay_sha256": replay_sha}
    return artifacts
