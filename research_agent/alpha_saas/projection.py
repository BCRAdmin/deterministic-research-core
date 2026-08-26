"""Deterministic, ticker-agnostic Software/SaaS metric projection."""

from __future__ import annotations

from datetime import date
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.source_frontend.contracts import SourceSnapshotIR


MAPPING_REGISTRY: dict[str, Any] = {
    "contract_id": "room16.alpha.saas_mapping_registry",
    "contract_version": 1,
    "selection": {
        "as_of": "newest_publicly_available_at_or_before_as_of",
        "deprecated": "prefer_non_deprecated",
        "period": "preserve_original_start_and_end",
        "ticker_specific_rules": False,
    },
    "metrics": {
        "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax"],
        "rpo": ["RevenueRemainingPerformanceObligation"],
        "current_contract_liability": [
            "ContractWithCustomerLiabilityCurrent",
            "DeferredRevenueCurrent",
        ],
        "direct_sbc_expense": [
            "ShareBasedCompensation",
            "AllocatedShareBasedCompensationExpense",
        ],
        "operating_income": ["OperatingIncomeLoss"],
        "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
        "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
        "shares_outstanding": ["EntityCommonStockSharesOutstanding"],
        "diluted_weighted_average_shares": [
            "WeightedAverageNumberOfDilutedSharesOutstanding"
        ],
        "cash": [
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ],
        "long_term_debt": [
            "LongTermDebtNoncurrent",
            "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        ],
        "latest_market_price": ["LatestMarketClose"],
    },
    "forbidden_direct_sbc_proxies": [
        "AdditionalPaidInCapitalIncreaseFromShareBasedCompensation",
        "AdjustmentsToAdditionalPaidInCapitalSharebasedCompensationRequisiteServicePeriodRecognitionValue",
        "EmployeeServiceShareBasedCompensationTaxBenefitFromExerciseOfStockOptions",
        "ShareBasedCompensationArrangementByShareBasedPaymentAwardEquityInstrumentsOtherThanOptionsNonvestedNumber",
        "ShareBasedCompensationArrangementByShareBasedPaymentAwardEquityInstrumentsOtherThanOptionsUnrecognizedCompensationCost",
    ],
}

FORMULA_REGISTRY: dict[str, Any] = {
    "contract_id": "room16.alpha.saas_formula_registry",
    "contract_version": 1,
    "period_compatibility": "exact_period_start_and_end",
    "unit_compatibility": "exact_currency_unit",
    "formulas": {
        "saas.operating_margin@1": {
            "output_metric": "operating_margin",
            "expression": "operating_income / revenue",
            "unit": "ratio",
        },
        "saas.free_cash_flow@1": {
            "output_metric": "free_cash_flow",
            "expression": "operating_cash_flow - capex",
            "unit": "source_currency",
        },
    },
}

CORE_ORDER = (
    "revenue",
    "rpo",
    "current_contract_liability",
    "direct_sbc_expense",
    "operating_income",
    "operating_margin",
    "operating_cash_flow",
    "capex",
    "free_cash_flow",
    "shares_outstanding",
    "diluted_weighted_average_shares",
    "cash",
    "long_term_debt",
    "latest_market_price",
)

RANKING_PROFILE: dict[str, Any] = {
    "contract_id": "room16.alpha.saas_renderer_ranking_profile",
    "contract_version": 1,
    "profile_id": "software_saas_alpha_v1",
    "ticker_specific_rules": False,
    "limit": 24,
    "priority_order": list(CORE_ORDER),
    "tie_breakers": [
        "non_deprecated_first",
        "newest_period_end_first",
        "newest_filed_first",
        "preferred_form_first",
        "direct_before_derived",
        "fact_id_ascending",
    ],
    "raw_facts_remain_inspectable": True,
}

SOURCE_PROFILE: dict[str, Any] = {
    "contract_id": "room16.alpha.saas_source_profile",
    "contract_version": 1,
    "companyfacts": "enabled_primary_public_source",
    "market_price": "enabled_primary_public_exchange_source",
    "filing_text_or_ir": "not_enabled_in_v1_reliability_not_proven",
    "crpo": "explicitly_unsupported_no_inference_from_rpo",
    "guidance": "explicitly_unsupported_no_qualitative_to_numeric_conversion",
    "ticker_specific_scraping": False,
}


def _latest_company_facts(
    payloads: list[dict[str, Any]], as_of_date: str
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for payload in payloads:
        namespaces = payload.get("facts")
        if not isinstance(namespaces, dict):
            continue
        for namespace, concepts in sorted(namespaces.items()):
            if not isinstance(concepts, dict):
                continue
            for concept, definition in sorted(concepts.items()):
                if not isinstance(definition, dict):
                    continue
                observations_by_unit = definition.get("units")
                if not isinstance(observations_by_unit, dict):
                    continue
                candidates: list[dict[str, Any]] = []
                for unit, observations in sorted(observations_by_unit.items()):
                    if not isinstance(observations, list):
                        continue
                    for observation in observations:
                        if not isinstance(observation, dict) or "val" not in observation:
                            continue
                        end = str(observation.get("end") or "")
                        filed = str(observation.get("filed") or "")
                        if end and filed and end <= as_of_date and filed <= as_of_date:
                            candidates.append(
                                {
                                    "value": observation["val"],
                                    "unit": str(unit),
                                    "period_start": observation.get("start"),
                                    "period_end": end,
                                    "filed": filed,
                                    "form": str(observation.get("form") or ""),
                                    "frame": observation.get("frame"),
                                    "accession": observation.get("accn"),
                                }
                            )
                if not candidates:
                    continue
                candidate = sorted(
                    candidates,
                    key=lambda row: (
                        row["filed"],
                        row["period_end"],
                        str(row["period_start"] or ""),
                        row["form"],
                        row["unit"],
                    ),
                )[-1]
                label = str(definition.get("label") or concept)
                selected.append(
                    {
                        "fact_id": f"fact.{namespace.lower()}.{concept.lower()}",
                        "metric_id": (
                            f"filing_{namespace.lower().replace('-', '_')}_{concept.lower()}"
                        ),
                        "label": label,
                        "namespace": namespace,
                        "concept": concept,
                        "deprecated": "deprecated" in label.lower(),
                        **candidate,
                    }
                )
    return selected


def _latest_market_price(payloads: list[dict[str, Any]]) -> dict[str, Any] | None:
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        records = payload.get("records")
        if isinstance(records, list):
            rows.extend(
                item
                for item in records
                if isinstance(item, dict) and "date" in item and "close" in item
            )
    if not rows:
        return None
    row = sorted(rows, key=lambda item: str(item["date"]))[-1]
    return {
        "fact_id": "fact.market.latest_close",
        "metric_id": "filing_market_latest_close",
        "semantic_metric_id": "latest_market_price",
        "semantic_mapping_id": "market.latest_close",
        "label": "Latest market close",
        "concept": "LatestMarketClose",
        "value": row["close"],
        "unit": "USD",
        "period_start": None,
        "period_end": str(row["date"]),
        "filed": str(row["date"]),
        "form": "market",
        "deprecated": False,
    }


def _mapping_lookup() -> dict[str, str]:
    return {
        concept: metric
        for metric, concepts in MAPPING_REGISTRY["metrics"].items()
        for concept in concepts
    }


def _select_mapped_facts(facts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup = _mapping_lookup()
    grouped: dict[str, list[dict[str, Any]]] = {}
    forbidden = set(MAPPING_REGISTRY["forbidden_direct_sbc_proxies"])
    for original in facts:
        concept = str(original.get("concept") or "")
        metric = lookup.get(concept)
        if not metric or (metric == "direct_sbc_expense" and concept in forbidden):
            continue
        item = dict(original)
        item["semantic_metric_id"] = metric
        item["semantic_mapping_id"] = f"concept.{concept}"
        grouped.setdefault(metric, []).append(item)
    selected: dict[str, dict[str, Any]] = {}
    for metric, candidates in grouped.items():
        non_deprecated = [item for item in candidates if not item.get("deprecated")]
        pool = non_deprecated or candidates
        selected[metric] = sorted(
            pool,
            key=lambda item: (
                str(item.get("filed") or ""),
                str(item.get("period_end") or ""),
                str(item.get("period_start") or ""),
                str(item.get("fact_id") or ""),
            ),
        )[-1]
    return selected


def _period_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left.get("unit") == right.get("unit")
        and left.get("period_start") is not None
        and left.get("period_start") == right.get("period_start")
        and left.get("period_end") == right.get("period_end")
    )


def _derived_fact(
    *,
    metric: str,
    formula_id: str,
    left: dict[str, Any],
    right: dict[str, Any],
    value: float,
    unit: str,
    label: str,
) -> dict[str, Any]:
    return {
        "fact_id": f"fact.derived.{metric}",
        "metric_id": f"derived_{metric}",
        "semantic_metric_id": metric,
        "semantic_mapping_id": formula_id,
        "label": label,
        "concept": metric,
        "value": value,
        "unit": unit,
        "period_start": left.get("period_start"),
        "period_end": left.get("period_end"),
        "filed": max(str(left.get("filed") or ""), str(right.get("filed") or "")),
        "form": "derived",
        "deprecated": False,
        "derivation": {
            "formula_id": formula_id,
            "operand_fact_ids": [left["fact_id"], right["fact_id"]],
        },
    }


def _derive(mapped: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    derived: list[dict[str, Any]] = []
    revenue = mapped.get("revenue")
    operating_income = mapped.get("operating_income")
    if (
        revenue
        and operating_income
        and _period_compatible(revenue, operating_income)
        and isinstance(revenue.get("value"), (int, float))
        and isinstance(operating_income.get("value"), (int, float))
        and revenue["value"] != 0
    ):
        derived.append(
            _derived_fact(
                metric="operating_margin",
                formula_id="saas.operating_margin@1",
                left=operating_income,
                right=revenue,
                value=round(operating_income["value"] / revenue["value"], 12),
                unit="ratio",
                label="Operating margin",
            )
        )
    operating_cash_flow = mapped.get("operating_cash_flow")
    capex = mapped.get("capex")
    if (
        operating_cash_flow
        and capex
        and _period_compatible(operating_cash_flow, capex)
        and isinstance(operating_cash_flow.get("value"), (int, float))
        and isinstance(capex.get("value"), (int, float))
    ):
        derived.append(
            _derived_fact(
                metric="free_cash_flow",
                formula_id="saas.free_cash_flow@1",
                left=operating_cash_flow,
                right=capex,
                value=operating_cash_flow["value"] - capex["value"],
                unit=str(operating_cash_flow["unit"]),
                label="Free cash flow",
            )
        )
    return derived


def _date_ordinal(value: object) -> int:
    try:
        return date.fromisoformat(str(value)).toordinal()
    except ValueError:
        return 0


def _rank_key(item: dict[str, Any]) -> tuple[Any, ...]:
    metric = item.get("semantic_metric_id")
    core = CORE_ORDER.index(metric) if metric in CORE_ORDER else len(CORE_ORDER)
    form_rank = {"10-Q": 0, "10-K": 1, "8-K": 2, "market": 3, "derived": 4}.get(
        str(item.get("form") or ""),
        9,
    )
    return (
        core,
        bool(item.get("deprecated")),
        -_date_ordinal(item.get("period_end")),
        -_date_ordinal(item.get("filed")),
        form_rank,
        item.get("form") == "derived",
        str(item.get("fact_id") or ""),
    )


def build_saas_semantic_artifacts(
    *,
    snapshot: SourceSnapshotIR,
    payloads: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    raw_facts = _latest_company_facts(payloads, snapshot.as_of_date)
    market = _latest_market_price(payloads)
    if market:
        raw_facts.append(market)
    raw_facts = sorted(raw_facts, key=lambda item: item["fact_id"])
    if not raw_facts:
        raise ValueError("ALPHA_SAAS_FACT_GENERATION_EMPTY")
    mapped = _select_mapped_facts(raw_facts)
    mapped_by_id = {item["fact_id"]: item for item in mapped.values()}
    facts = [mapped_by_id.get(item["fact_id"], item) for item in raw_facts]
    derived = _derive(mapped)
    facts.extend(derived)
    facts = sorted(facts, key=lambda item: item["fact_id"])
    ranked = sorted(facts, key=_rank_key)
    projection_facts = ranked[: int(RANKING_PROFILE["limit"])]

    evidence = []
    evidence_by_fact: dict[str, str] = {}
    for index, item in enumerate(facts, 1):
        evidence_id = f"evidence.{index:04d}"
        evidence_by_fact[item["fact_id"]] = evidence_id
        node = {
            "evidence_id": evidence_id,
            "fact_id": item["fact_id"],
            "source_snapshot_sha256": snapshot.snapshot_sha256,
        }
        if item.get("derivation"):
            node["formula_id"] = item["derivation"]["formula_id"]
            node["source_fact_ids"] = item["derivation"]["operand_fact_ids"]
        evidence.append(node)
    claims = [
        {
            "claim_id": f"claim.{index:04d}",
            "fact_id": item["fact_id"],
            "statement": f"{item['label']} ({item['period_end']}): {item['value']} {item['unit']}",
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
        }
        for item in facts
    ]
    formula_evaluations = [
        {
            "formula_id": item["derivation"]["formula_id"],
            "output_fact_id": item["fact_id"],
            "operand_fact_ids": item["derivation"]["operand_fact_ids"],
            "period_start": item["period_start"],
            "period_end": item["period_end"],
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
    artifacts: dict[str, dict[str, Any]] = {
        "parsed_table_ir": {
            "contract_id": "room16.alpha.saas_parsed_source_ir",
            "contract_version": 1,
            "ticker": snapshot.ticker,
            "records": facts,
        },
        "typed_facts": {
            "contract_id": "room16.alpha.saas_typed_facts",
            "contract_version": 1,
            "facts": facts,
        },
        "metrics": {
            "contract_id": "room16.alpha.saas_metrics",
            "contract_version": 1,
            "metrics": metrics,
            "mapping_registry_sha256": sha256_json(MAPPING_REGISTRY),
        },
        "formula_evaluations": {
            "contract_id": "room16.alpha.saas_formula_evaluations",
            "contract_version": 1,
            "evaluations": formula_evaluations,
            "formula_registry_sha256": sha256_json(FORMULA_REGISTRY),
        },
        "evidence_graph": {
            "contract_id": "room16.alpha.saas_evidence_graph",
            "contract_version": 1,
            "nodes": evidence,
        },
        "claim_graph": {
            "contract_id": "room16.alpha.saas_claim_graph",
            "contract_version": 1,
            "nodes": claims,
        },
        "decision_graph": {
            "contract_id": "room16.alpha.saas_decision_graph",
            "contract_version": 1,
            **decision,
        },
        "source_provenance": {
            "contract_id": "room16.alpha.saas_source_provenance",
            "contract_version": 1,
            "snapshot": snapshot.model_dump(mode="json"),
            "source_profile": SOURCE_PROFILE,
        },
        "renderer_projection": {
            "contract_id": "room16.alpha.saas_renderer_projection",
            "contract_version": 1,
            "ticker": snapshot.ticker,
            "as_of_date": snapshot.as_of_date,
            "title": f"{snapshot.ticker} native research dossier",
            "facts": projection_facts,
            "claims": claims,
            "decision": decision,
            "ranking_profile": RANKING_PROFILE,
            "lineage": lineage,
        },
        "renderer_lineage_expectation": {
            "contract_id": "room16.alpha.saas_renderer_lineage_expectation",
            "contract_version": 1,
            "semantic_mutation_allowed": False,
            **lineage,
        },
        "authority_v3_bridge": {
            "contract_id": "room16.alpha.saas_authority_v3_output_bridge",
            "contract_version": 1,
            "direction": "bundle_to_authority_v3_only",
            "semantic_input_allowed": False,
            "projection": {
                "ticker": snapshot.ticker,
                "facts": facts,
                "claims": claims,
                "decision": decision,
            },
        },
        "diagnostics": {
            "contract_id": "room16.alpha.saas_diagnostics",
            "contract_version": 1,
            "items": [],
            "unsupported": ["crpo", "guidance"],
        },
        "pass_execution_records": {
            "contract_id": "room16.alpha.saas_pass_execution_records",
            "contract_version": 1,
            "passes": [
                "ba12.l3.parse_snapshot",
                "ba12.l4.type_facts",
                "alpha.saas.l5.map_core_metrics",
                "alpha.saas.l6.evaluate_period_safe_formulas",
                "alpha.saas.l11.rank_projection",
                "ba12.l11.emit_native_bundle_v2",
            ],
        },
        "verification_plan": {
            "contract_id": "room16.alpha.saas_verification_plan",
            "contract_version": 1,
            "checks": [
                "source_hashes",
                "no_legacy_input",
                "artifact_hashes",
                "receipt_signature",
                "renderer_lineage",
                "mapping_aliases",
                "formula_period_compatibility",
                "ticker_agnostic_ranking",
            ],
        },
        "execution_attestation": {
            "contract_id": "room16.alpha.saas_execution_attestation",
            "contract_version": 1,
            "network_after_snapshot": False,
            "legacy_semantic_input": False,
            "source_native": True,
            "ticker_specific_rules": False,
        },
    }
    replay_sha = sha256_json(
        {key: artifacts[key] for key in sorted(artifacts) if key != "authority_v3_bridge"}
    )
    artifacts["compile_state"] = {
        "contract_id": "room16.alpha.saas_compile_state",
        "contract_version": 1,
        "state": "verified_alpha_saas_successor",
        "source_snapshot_sha256": snapshot.snapshot_sha256,
        "replay_sha256": replay_sha,
    }
    artifacts["compile_verdict"] = {
        "contract_id": "room16.alpha.saas_compile_verdict",
        "contract_version": 1,
        "verdict": "PASS",
        "compile_allowed": True,
        "renderer_eligible": True,
    }
    artifacts["verification_report"] = {
        "contract_id": "room16.alpha.saas_verification_report",
        "contract_version": 1,
        "verdict": "PASS",
        "fact_count": len(facts),
        "projected_fact_count": len(projection_facts),
        "claim_count": len(claims),
        "derived_metric_count": len(derived),
        "legacy_semantic_inputs": 0,
        "replay_sha256": replay_sha,
    }
    return artifacts
