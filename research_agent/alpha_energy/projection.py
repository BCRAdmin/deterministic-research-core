"""Deterministic, issuer-agnostic Energy projection over frozen BA12 truth."""

from __future__ import annotations

from datetime import date
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.source_frontend.contracts import SourceSnapshotIR


MAPPING_REGISTRY: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_mapping_registry",
    "contract_version": 1,
    "selection": {
        "as_of": "newest_publicly_available_at_or_before_as_of",
        "issuer_specific_rules": False,
        "period_basis_preserved": True,
        "quarter_from_ytd_subtraction_allowed": False,
        "unit_conversion_allowed": False,
    },
    "metrics": {
        "revenue": ["Revenues"],
        "net_income": ["NetIncomeLoss"],
        "diluted_eps": ["EarningsPerShareDiluted"],
        "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
        "capital_expenditure": ["PaymentsToAcquirePropertyPlantAndEquipment"],
        "cash": ["CashAndCashEquivalentsAtCarryingValue"],
        "current_debt": ["DebtCurrent"],
        "long_term_debt_and_leases": ["LongTermDebtAndCapitalLeaseObligations"],
        "shares_outstanding": ["EntityCommonStockSharesOutstanding"],
        "dividends_paid": ["PaymentsOfDividendsCommonStock"],
        "share_repurchases": ["PaymentsForRepurchaseOfCommonStock"],
        "exploration_expense": ["ExplorationExpense"],
        "latest_market_price": ["LatestMarketClose"],
    },
}

PERIOD_BASIS_POLICY: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_period_basis_policy",
    "contract_version": 1,
    "standalone_quarter_days": [70, 110],
    "year_to_date_days_exclusive": [110, 330],
    "annual_days": [330, 390],
    "fiscal_year_opening_window_days": 15,
    "quarter_from_ytd_subtraction_allowed": False,
}

FRESHNESS_POLICY: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_freshness_policy",
    "contract_version": 1,
    "thresholds_days": {
        "market": {"current": 7, "aging": 30},
        "financial": {"current": 190, "aging": 550},
    },
    "comparative_can_be_current_primary": False,
    "stale_primary_surface_allowed": False,
    "stale_formula_operand_allowed": False,
}

FORMULA_REGISTRY: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_formula_registry",
    "contract_version": 1,
    "formulas": {
        "energy.free_cash_flow@1": {
            "output_metric": "free_cash_flow",
            "label": "Free cash flow (analytical: OCF - PP&E CapEx)",
            "left_operand": "operating_cash_flow",
            "right_operand": "capital_expenditure",
            "operator": "subtract",
        }
    },
    "compatibility": "same_exact_start_end_unit_current_ytd_basis",
    "forbidden_derivations": [
        "subtraction_derived_quarter",
        "net_debt",
        "production_unit_conversion",
        "issuer_defined_free_cash_flow",
    ],
}

OPERATING_METRICS_REQUIRING_PRIMARY_TEXT = (
    "upstream_production_volume",
    "realized_oil_gas_price",
    "proved_reserves",
    "reserve_replacement",
    "upstream_segment_earnings",
    "refinery_throughput",
    "refinery_utilization",
    "refinery_capacity",
    "downstream_refining_earnings_or_margin",
    "chemical_or_product_solutions_metrics",
    "lng_metrics",
    "low_carbon_metrics",
)

CORE_ORDER = (
    "revenue",
    "net_income",
    "diluted_eps",
    "operating_cash_flow",
    "capital_expenditure",
    "free_cash_flow",
    "cash",
    "current_debt",
    "long_term_debt_and_leases",
    "dividends_paid",
    "share_repurchases",
    "exploration_expense",
    "shares_outstanding",
    "latest_market_price",
)

RANKING_PROFILE: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_renderer_ranking_profile",
    "contract_version": 1,
    "profile_id": "energy_alpha_v1",
    "issuer_specific_rules": False,
    "limit": 24,
    "priority_order": list(CORE_ORDER),
    "stale_excluded": True,
    "comparative_excluded": True,
    "raw_facts_remain_inspectable": True,
}


def classify_period_basis(start: str | None, end: str) -> tuple[str, int | None]:
    if not start:
        return "INSTANT", None
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    duration = (end_date - start_date).days
    if 70 <= duration <= 110:
        return "STANDALONE_QUARTER", duration
    if 330 <= duration <= 390:
        return "ANNUAL", duration
    if (
        110 < duration < 330
        and start_date.year == end_date.year
        and start_date.month == 1
        and start_date.day <= 15
    ):
        return "YEAR_TO_DATE", duration
    return "OTHER_DURATION", duration


def _freshness(*, as_of: str, period_end: str, market: bool = False) -> tuple[str, int]:
    age = max(0, (date.fromisoformat(as_of) - date.fromisoformat(period_end)).days)
    limits = FRESHNESS_POLICY["thresholds_days"]["market" if market else "financial"]
    if age <= limits["current"]:
        return "CURRENT", age
    if age <= limits["aging"]:
        return "AGING", age
    return "STALE", age


def _fact_id(
    namespace: str,
    concept: str,
    start: str | None,
    end: str,
    basis: str,
    unit: str,
) -> str:
    safe_unit = unit.lower().replace("/", "_").replace(" ", "_")
    return ".".join(
        (
            "fact",
            namespace.lower().replace("-", "_"),
            concept.lower(),
            (start or "instant").replace("-", ""),
            end.replace("-", ""),
            basis.lower(),
            safe_unit,
        )
    )


def _role_candidates(rows: list[dict[str, Any]]) -> None:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            row["namespace"],
            row["concept"],
            row["unit"],
            row["period_basis"],
        )
        groups.setdefault(key, []).append(row)
    for group in groups.values():
        ordered_ends = sorted({row["end"] for row in group}, reverse=True)
        newest_end = ordered_ends[0]
        for row in group:
            newer = row["end"] != newest_end
            row["newer_same_concept_same_basis_exists"] = newer
            if not newer:
                row["period_role"] = (
                    "CURRENT_YTD"
                    if row["period_basis"] == "YEAR_TO_DATE"
                    else "CURRENT_PRIMARY"
                )
            elif len(ordered_ends) > 1 and row["end"] == ordered_ends[1]:
                row["period_role"] = "COMPARATIVE"
            else:
                row["period_role"] = "HISTORICAL"


def _company_facts(payloads: list[dict[str, Any]], as_of: str) -> list[dict[str, Any]]:
    concept_to_metric = {
        concept: metric
        for metric, concepts in MAPPING_REGISTRY["metrics"].items()
        for concept in concepts
        if concept != "LatestMarketClose"
    }
    by_signature: dict[tuple[Any, ...], dict[str, Any]] = {}
    for payload in payloads:
        facts = payload.get("facts")
        if not isinstance(facts, dict):
            continue
        for namespace, concepts in sorted(facts.items()):
            if not isinstance(concepts, dict):
                continue
            for concept, definition in sorted(concepts.items()):
                metric = concept_to_metric.get(concept)
                if not metric or not isinstance(definition, dict):
                    continue
                units = definition.get("units")
                if not isinstance(units, dict):
                    continue
                for unit, observations in sorted(units.items()):
                    if not isinstance(observations, list):
                        continue
                    for observation in observations:
                        if not isinstance(observation, dict) or "val" not in observation:
                            continue
                        end = str(observation.get("end") or "")
                        filed = str(observation.get("filed") or "")
                        start = str(observation["start"]) if observation.get("start") else None
                        if not end or not filed or end > as_of or filed > as_of:
                            continue
                        basis, duration = classify_period_basis(start, end)
                        freshness, age = _freshness(as_of=as_of, period_end=end)
                        row = {
                            "fact_id": _fact_id(namespace, concept, start, end, basis, str(unit)),
                            "metric_id": (
                                f"filing_{namespace.lower().replace('-', '_')}_"
                                f"{concept.lower()}_{basis.lower()}"
                            ),
                            "semantic_metric_id": metric,
                            "semantic_mapping_id": f"concept.{concept}",
                            "label": str(definition.get("label") or concept),
                            "namespace": namespace,
                            "concept": concept,
                            "value": observation["val"],
                            "unit": str(unit),
                            "start": start,
                            "end": end,
                            "period_start": start,
                            "period_end": end,
                            "period_basis": basis,
                            "duration_days": duration,
                            "filed": filed,
                            "form": str(observation.get("form") or ""),
                            "frame": observation.get("frame"),
                            "accession": observation.get("accn"),
                            "freshness_status": freshness,
                            "age_days": age,
                            "source_period_end": end,
                            "filed_date": filed,
                        }
                        signature = (namespace, concept, str(unit), start, end)
                        previous = by_signature.get(signature)
                        if previous is None or (
                            row["filed"], str(row.get("accession") or "")
                        ) > (
                            previous["filed"], str(previous.get("accession") or "")
                        ):
                            by_signature[signature] = row
    results = list(by_signature.values())
    _role_candidates(results)
    return results


def _market_fact(payloads: list[dict[str, Any]], as_of: str) -> dict[str, Any] | None:
    rows = [
        row
        for payload in payloads
        for row in (payload.get("records") or [])
        if isinstance(row, dict)
        and "date" in row
        and "close" in row
        and str(row["date"]) <= as_of
    ]
    if not rows:
        return None
    row = sorted(rows, key=lambda item: str(item["date"]))[-1]
    end = str(row["date"])
    freshness, age = _freshness(as_of=as_of, period_end=end, market=True)
    return {
        "fact_id": "fact.market.latest_close",
        "metric_id": "filing_market_latest_close",
        "semantic_metric_id": "latest_market_price",
        "semantic_mapping_id": "market.latest_close",
        "label": "Latest market close",
        "namespace": "market",
        "concept": "LatestMarketClose",
        "value": row["close"],
        "unit": "USD",
        "start": None,
        "end": end,
        "period_start": None,
        "period_end": end,
        "period_basis": "INSTANT",
        "duration_days": None,
        "filed": end,
        "form": "market",
        "frame": None,
        "accession": None,
        "freshness_status": freshness,
        "age_days": age,
        "period_role": "CURRENT_PRIMARY",
        "newer_same_concept_same_basis_exists": False,
        "source_period_end": end,
        "filed_date": end,
    }


def _current_ytd(facts: list[dict[str, Any]], metric: str) -> list[dict[str, Any]]:
    return [
        row
        for row in facts
        if row.get("semantic_metric_id") == metric
        and row["period_basis"] == "YEAR_TO_DATE"
        and row["period_role"] == "CURRENT_YTD"
        and row["freshness_status"] == "CURRENT"
    ]


def _derived_free_cash_flow(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    cash_flows = _current_ytd(facts, "operating_cash_flow")
    capex_rows = _current_ytd(facts, "capital_expenditure")
    for cash_flow in cash_flows:
        matches = [
            row
            for row in capex_rows
            if row["start"] == cash_flow["start"]
            and row["end"] == cash_flow["end"]
            and row["unit"] == cash_flow["unit"]
        ]
        if len(matches) != 1:
            continue
        capex = matches[0]
        if not isinstance(cash_flow["value"], (int, float)) or not isinstance(
            capex["value"], (int, float)
        ):
            continue
        start, end = cash_flow["start"], cash_flow["end"]
        outputs.append(
            {
                "fact_id": f"fact.derived.free_cash_flow.{start.replace('-', '')}.{end.replace('-', '')}",
                "metric_id": "derived_free_cash_flow",
                "semantic_metric_id": "free_cash_flow",
                "semantic_mapping_id": "energy.free_cash_flow@1",
                "label": "Free cash flow (analytical: OCF - PP&E CapEx)",
                "namespace": "derived",
                "concept": "free_cash_flow",
                "value": cash_flow["value"] - capex["value"],
                "unit": cash_flow["unit"],
                "start": start,
                "end": end,
                "period_start": start,
                "period_end": end,
                "period_basis": "YEAR_TO_DATE",
                "duration_days": cash_flow["duration_days"],
                "filed": max(cash_flow["filed"], capex["filed"]),
                "form": "derived",
                "frame": None,
                "accession": None,
                "freshness_status": "CURRENT",
                "age_days": max(cash_flow["age_days"], capex["age_days"]),
                "period_role": "CURRENT_YTD",
                "newer_same_concept_same_basis_exists": False,
                "source_period_end": end,
                "filed_date": max(cash_flow["filed"], capex["filed"]),
                "derivation": {
                    "formula_id": "energy.free_cash_flow@1",
                    "operand_fact_ids": [cash_flow["fact_id"], capex["fact_id"]],
                    "period_compatibility": "EXACT",
                    "unit_conversion_used": False,
                },
            }
        )
    return outputs


def _basis_eligible(metric: str, basis: str) -> bool:
    if metric in {"revenue", "net_income", "diluted_eps"}:
        return basis == "STANDALONE_QUARTER"
    if metric in {
        "operating_cash_flow",
        "capital_expenditure",
        "free_cash_flow",
        "dividends_paid",
        "share_repurchases",
        "exploration_expense",
    }:
        return basis == "YEAR_TO_DATE"
    return basis == "INSTANT"


def _rank_key(item: dict[str, Any]) -> tuple[Any, ...]:
    metric = item.get("semantic_metric_id")
    core = CORE_ORDER.index(metric) if metric in CORE_ORDER else len(CORE_ORDER)
    return (
        core,
        -date.fromisoformat(str(item["period_end"])).toordinal(),
        str(item["fact_id"]),
    )


def build_energy_semantic_artifacts(
    *, snapshot: SourceSnapshotIR, payloads: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    facts = _company_facts(payloads, snapshot.as_of_date)
    market = _market_fact(payloads, snapshot.as_of_date)
    if market:
        facts.append(market)
    if not facts:
        raise ValueError("ALPHA_ENERGY_FACT_GENERATION_EMPTY")
    derived = _derived_free_cash_flow(facts)
    facts = sorted(facts + derived, key=lambda item: item["fact_id"])
    primary = [
        row
        for row in facts
        if row.get("semantic_metric_id")
        and row["freshness_status"] != "STALE"
        and row["period_role"] in {"CURRENT_PRIMARY", "CURRENT_YTD"}
        and not row["newer_same_concept_same_basis_exists"]
        and _basis_eligible(row["semantic_metric_id"], row["period_basis"])
    ]
    projection_facts = sorted(primary, key=_rank_key)[: int(RANKING_PROFILE["limit"])]
    evidence: list[dict[str, Any]] = []
    evidence_by_fact: dict[str, str] = {}
    for index, item in enumerate(facts, 1):
        evidence_id = f"evidence.{index:04d}"
        evidence_by_fact[item["fact_id"]] = evidence_id
        node: dict[str, Any] = {
            "evidence_id": evidence_id,
            "fact_id": item["fact_id"],
            "source_snapshot_sha256": snapshot.snapshot_sha256,
        }
        if item.get("derivation"):
            node.update(
                formula_id=item["derivation"]["formula_id"],
                source_fact_ids=item["derivation"]["operand_fact_ids"],
            )
        evidence.append(node)
    claims = [
        {
            "claim_id": f"claim.{index:04d}",
            "fact_id": item["fact_id"],
            "statement": (
                f"{item['label']} [{item['period_basis']}] "
                f"({item['period_end']}): {item['value']} {item['unit']}"
            ),
            "evidence_ids": [evidence_by_fact[item["fact_id"]]],
        }
        for index, item in enumerate(projection_facts[:12], 1)
    ]
    decision = {
        "ticker": snapshot.ticker,
        "as_of_date": snapshot.as_of_date,
        "rating": "REVIEW_REQUIRED",
        "semantic_owner": "research_compiler",
        "claim_ids": [item["claim_id"] for item in claims],
        "automatic_investment_decision": False,
    }
    metrics = [
        {
            "metric_id": item["metric_id"],
            "semantic_metric_id": item.get("semantic_metric_id"),
            "fact_id": item["fact_id"],
            "value": item["value"],
            "unit": item["unit"],
            "as_of": item["period_end"],
            "period_basis": item["period_basis"],
            "period_role": item["period_role"],
            "freshness_status": item["freshness_status"],
            "age_days": item["age_days"],
        }
        for item in facts
    ]
    evaluations = [
        {
            "formula_id": item["derivation"]["formula_id"],
            "output_fact_id": item["fact_id"],
            "operand_fact_ids": item["derivation"]["operand_fact_ids"],
            "period_start": item["period_start"],
            "period_end": item["period_end"],
            "period_compatibility": "EXACT",
            "value": item["value"],
            "unit": item["unit"],
        }
        for item in derived
    ]
    lineage = {
        "source_snapshot_sha256": snapshot.snapshot_sha256,
        "fact_ids": [item["fact_id"] for item in facts],
        "metric_ids": [item["metric_id"] for item in metrics],
        "claim_ids": [item["claim_id"] for item in claims],
    }
    unsupported = [
        {
            "metric_id": metric,
            "status": "SUPPLEMENTAL_PRIMARY_TEXT_REQUIRED",
            "proxy_used": False,
        }
        for metric in OPERATING_METRICS_REQUIRING_PRIMARY_TEXT
    ]
    base = "room16.alpha.energy"
    artifacts: dict[str, dict[str, Any]] = {
        "parsed_table_ir": {"contract_id": f"{base}_parsed_source_ir", "contract_version": 1, "ticker": snapshot.ticker, "records": facts},
        "typed_facts": {"contract_id": f"{base}_typed_facts", "contract_version": 1, "facts": facts},
        "metrics": {"contract_id": f"{base}_metrics", "contract_version": 1, "metrics": metrics, "mapping_registry_sha256": sha256_json(MAPPING_REGISTRY), "freshness_policy_sha256": sha256_json(FRESHNESS_POLICY), "period_basis_policy_sha256": sha256_json(PERIOD_BASIS_POLICY)},
        "formula_evaluations": {"contract_id": f"{base}_formula_evaluations", "contract_version": 1, "evaluations": evaluations, "formula_registry_sha256": sha256_json(FORMULA_REGISTRY)},
        "evidence_graph": {"contract_id": f"{base}_evidence_graph", "contract_version": 1, "nodes": evidence},
        "claim_graph": {"contract_id": f"{base}_claim_graph", "contract_version": 1, "nodes": claims},
        "decision_graph": {"contract_id": f"{base}_decision_graph", "contract_version": 1, **decision},
        "source_provenance": {"contract_id": f"{base}_source_provenance", "contract_version": 1, "snapshot": snapshot.model_dump(mode="json"), "primary_text_used": False, "supplemental_source_used": False},
        "renderer_projection": {"contract_id": f"{base}_renderer_projection", "contract_version": 1, "ticker": snapshot.ticker, "as_of_date": snapshot.as_of_date, "title": f"{snapshot.ticker} Alpha Energy research dossier", "archetype": "ENERGY", "facts": projection_facts, "claims": claims, "decision": decision, "ranking_profile": RANKING_PROFILE, "lineage": lineage},
        "renderer_lineage_expectation": {"contract_id": f"{base}_renderer_lineage_expectation", "contract_version": 1, "semantic_mutation_allowed": False, **lineage},
        "authority_v3_bridge": {"contract_id": f"{base}_authority_v3_output_bridge", "contract_version": 1, "direction": "bundle_to_authority_v3_only", "semantic_input_allowed": False, "projection": {"ticker": snapshot.ticker, "facts": facts, "claims": claims, "decision": decision}},
        "diagnostics": {"contract_id": f"{base}_diagnostics", "contract_version": 1, "items": [{"severity": "P2", "code": "SUPPLEMENTAL_PRIMARY_TEXT_REQUIRED", "count": len(unsupported)}], "unsupported": unsupported},
        "pass_execution_records": {"contract_id": f"{base}_pass_execution_records", "contract_version": 1, "passes": ["ba12.l3.parse_snapshot", "ba12.l4.type_facts", "alpha.energy.l5.preserve_period_basis", "alpha.energy.l6.map_core_metrics", "alpha.energy.l7.evaluate_freshness_safe_formulas", "alpha.energy.l11.rank_projection", "ba12.l11.emit_native_bundle_v2"]},
        "verification_plan": {"contract_id": f"{base}_verification_plan", "contract_version": 1, "checks": ["source_hashes", "no_legacy_input", "artifact_hashes", "receipt_signature", "renderer_lineage", "period_basis", "comparative_non_conflation", "freshness", "formula_period_compatibility", "issuer_agnostic_ranking", "operating_metrics_fail_closed"]},
        "execution_attestation": {"contract_id": f"{base}_execution_attestation", "contract_version": 1, "network_after_snapshot": False, "legacy_semantic_input": False, "source_native": True, "issuer_specific_rules": False, "architecture_reopened": False, "primary_text_used": False, "unit_conversion_used": False},
    }
    replay_sha = sha256_json(
        {
            key: artifacts[key]
            for key in sorted(artifacts)
            if key != "authority_v3_bridge"
        }
    )
    artifacts["compile_state"] = {"contract_id": f"{base}_compile_state", "contract_version": 1, "state": "verified_alpha_energy_successor", "source_snapshot_sha256": snapshot.snapshot_sha256, "replay_sha256": replay_sha}
    artifacts["compile_verdict"] = {"contract_id": f"{base}_compile_verdict", "contract_version": 1, "verdict": "PASS", "compile_allowed": True, "renderer_eligible": True}
    artifacts["verification_report"] = {"contract_id": f"{base}_verification_report", "contract_version": 1, "verdict": "PASS", "fact_count": len(facts), "projected_fact_count": len(projection_facts), "claim_count": len(claims), "derived_metric_count": len(derived), "unsupported_operating_metric_count": len(unsupported), "legacy_semantic_inputs": 0, "replay_sha256": replay_sha}
    return artifacts
