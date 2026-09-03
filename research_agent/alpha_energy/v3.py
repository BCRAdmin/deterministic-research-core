"""Additive Energy v3 semantic candidate over raw, hash-bound evidence.

Energy v3 deliberately does not call a provider and does not inherit an Energy
v1 selection receipt.  It selects directly from raw or typed SEC fact
candidates and emits a complete deterministic receipt.  Energy v1 and v2 stay
available as historical regression authorities.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterable, Mapping

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.sources.sec.sec_inline_facts import (
    _InlineStatementParser,
    _inline_numeric_value,
)

from .projection import classify_period_basis


PROFILE_STATUS = "CANDIDATE_NOT_FROZEN"


class _EnergyV3InlineParser(_InlineStatementParser):
    """Energy-local unit decoding without changing the shared SEC parser."""

    def __init__(self) -> None:
        super().__init__()
        self.units: dict[str, str] = {}
        self._unit_id: str | None = None
        self._unit_measure_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        super().handle_starttag(tag, attrs)
        normalized_tag = tag.lower()
        attributes = {str(key).lower(): str(value or "") for key, value in attrs}
        if normalized_tag == "xbrli:unit":
            self._unit_id = attributes.get("id") or None
        elif normalized_tag == "xbrli:measure" and self._unit_id:
            self._unit_measure_parts = []

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "xbrli:measure" and self._unit_id:
            measure = " ".join("".join(self._unit_measure_parts or []).split())
            if measure:
                self.units[self._unit_id] = measure
            self._unit_measure_parts = None
        elif normalized_tag == "xbrli:unit":
            self._unit_id = None
            self._unit_measure_parts = None
        super().handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        super().handle_data(data)
        if self._unit_measure_parts is not None:
            self._unit_measure_parts.append(data)


REVENUE_COMPARABILITY_CONTRACT_V3: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_revenue_comparability_v3_candidate",
    "contract_version": 3,
    "ticker_specific_rules": False,
    "label_similarity_is_authority": False,
    "concepts": {
        "Revenues": {
            "grade": "A",
            "economic_scope": "exact_consolidated_total_revenue",
        },
        "RevenueFromContractWithCustomerExcludingAssessedTax": {
            "grade": "B",
            "economic_scope": "consolidated_customer_revenue_excluding_assessed_tax",
        },
        "RevenueFromContractWithCustomerIncludingAssessedTax": {
            "grade": "B",
            "economic_scope": "consolidated_customer_revenue_including_assessed_tax",
        },
    },
    "grade_b_is_grade_a": False,
    "grade_c_counts_as_comparable": False,
    "dimensionless_consolidated_scope_required": True,
    "issuer_extension_concepts_allowed": False,
}

CAPEX_COMPARABILITY_CONTRACT_V3: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_capex_comparability_v3_candidate",
    "contract_version": 3,
    "ticker_specific_rules": False,
    "label_similarity_is_authority": False,
    "concepts": {
        "PaymentsToAcquirePropertyPlantAndEquipment": {
            "grade": "A",
            "economic_scope": "cash_payments_to_acquire_property_plant_and_equipment",
        },
        "PaymentsToAcquireProductiveAssets": {
            "grade": "B",
            "economic_scope": "cash_payments_to_acquire_productive_assets",
        },
        "PaymentsToAcquireOilAndGasPropertyAndEquipment": {
            "grade": "B",
            "economic_scope": "cash_payments_to_acquire_oil_gas_property_and_equipment",
        },
        "PaymentsToAcquireOilAndGasProperty": {
            "grade": "B",
            "economic_scope": "cash_payments_to_acquire_oil_and_gas_property",
        },
    },
    "grade_c_counts_as_comparable": False,
    "dimensionless_consolidated_scope_required": True,
    "issuer_extension_concepts_allowed": False,
}

DEBT_COMPARABILITY_CONTRACT_V3: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_debt_comparability_v3_candidate",
    "contract_version": 3,
    "ticker_specific_rules": False,
    "economic_slot_label": "long_term_debt_measure",
    "concepts": {
        "LongTermDebtNoncurrent": {
            "grade": "A",
            "economic_scope": "noncurrent_long_term_debt",
        },
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent": {
            "grade": "B",
            "economic_scope": "noncurrent_long_term_debt_and_finance_leases",
        },
        "LongTermDebtAndCapitalLeaseObligations": {
            "grade": "B",
            "economic_scope": "reported_long_term_debt_and_capital_lease_obligations",
        },
        "LongTermDebt": {
            "grade": "B",
            "economic_scope": "reported_long_term_debt_measure",
        },
    },
    "grade_b_is_grade_a": False,
    "current_noncurrent_components_summed": False,
}

ENERGY_SEMANTIC_CONTRACT_V3: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_semantic_contract_v3_candidate",
    "contract_version": 3,
    "profile_family": "Energy",
    "ticker_specific_rules": False,
    "manual_semantic_interventions": False,
    "lifecycle_context_policy": {
        "dimensionless_context_grade": "A",
        "sole_business_acquisition_successor_context_grade": "B",
        "predecessor_context_counts_as_current_entity": False,
        "additional_dimensions_allowed": False,
    },
    "metrics": {
        "revenue": REVENUE_COMPARABILITY_CONTRACT_V3["concepts"],
        "net_income": {
            "NetIncomeLoss": {
                "grade": "A",
                "economic_scope": "net_income_loss_attributable_to_parent",
            }
        },
        "operating_cash_flow": {
            "NetCashProvidedByUsedInOperatingActivities": {
                "grade": "A",
                "economic_scope": "net_cash_from_operating_activities",
            }
        },
        "capital_expenditure": CAPEX_COMPARABILITY_CONTRACT_V3["concepts"],
        "long_term_debt_measure": DEBT_COMPARABILITY_CONTRACT_V3["concepts"],
    },
}

PERIOD_FRESHNESS_POLICY_V3: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_period_freshness_policy_v3_candidate",
    "contract_version": 3,
    "financial_current_max_age_days": 190,
    "financial_aging_max_age_days": 550,
    "accepted_availability": ["CURRENT_COMPARABLE", "AGING_BUT_VALID_DISCLOSED"],
    "historical_only_counts_as_resolved": False,
    "quarter_from_ytd_subtraction_allowed": False,
    "period_basis_relabeling_allowed": False,
    "incomparable_period_combination_allowed": False,
    "unit_conversion_allowed": False,
    "source_lineage_required": True,
    "duration_basis_policy": {
        "revenue": ["STANDALONE_QUARTER"],
        "net_income": ["STANDALONE_QUARTER"],
        "operating_cash_flow": ["YEAR_TO_DATE", "ANNUAL", "STANDALONE_QUARTER"],
        "capital_expenditure": ["YEAR_TO_DATE", "ANNUAL", "STANDALONE_QUARTER"],
        "long_term_debt_measure": ["INSTANT"],
    },
}

AUTHORIZED_SEMANTIC_SHA256 = sha256_json(ENERGY_SEMANTIC_CONTRACT_V3)
AUTHORIZED_PERIOD_POLICY_SHA256 = sha256_json(PERIOD_FRESHNESS_POLICY_V3)

CANDIDATE_INTEGRITY_CONTRACT_V3: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_v3.candidate_integrity_contract",
    "contract_version": 1,
    "accepted_candidate_contracts": [
        "room16.rfc0011.raw_fact_candidate_ir",
        "room16.alpha.energy_v3.inline_raw_typed_candidate",
    ],
    "hash_algorithm": "SHA-256",
    "canonical_serialization": "SORTED_COMPACT_JSON_UTF8",
    "source_lineage_sha256_fields": [
        "source_artifact_sha256",
        "source_payload_sha256",
        "source_snapshot_sha256",
    ],
    "supplied_hash_recomputed": True,
    "candidate_id_recomputed": True,
    "unknown_candidate_contracts_allowed": False,
}

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RAW_FACT_IDENTITY_FIELDS = (
    "source_snapshot_sha256",
    "source_artifact_sha256",
    "namespace",
    "concept",
    "unit",
    "start_or_null",
    "end",
    "filed",
    "form",
    "accession_or_null",
    "frame_or_null",
    "value",
)
_CANDIDATE_REQUIRED_FIELDS = (
    "candidate_id",
    "candidate_sha256",
    "source_artifact_sha256",
    "source_snapshot_sha256",
    "namespace",
    "concept",
    "value",
    "unit",
    "end",
    "filed",
    "form",
    "dimensions_present",
    "dimension_key",
)


def require_authorized_contract_v3(
    value: Mapping[str, Any], *, expected_id: str, expected_sha256: str, label: str
) -> None:
    """Reject same-ID mutations by binding the complete canonical contract."""

    if not isinstance(value, Mapping) or value.get("contract_id") != expected_id:
        raise ValueError(f"ENERGY_V3_{label}_NOT_AUTHORIZED")
    if sha256_json(dict(value)) != expected_sha256:
        raise ValueError(f"ENERGY_V3_{label}_HASH_NOT_AUTHORIZED")


def validate_candidate_integrity_v3(raw: Mapping[str, Any]) -> dict[str, str]:
    """Recompute a supported raw candidate's hash, identity, and lineage.

    RFC-0011 raw facts and Energy-v3 inline facts use different historical ID
    formulas.  Both are validated byte-semantically here; neither may supply an
    opaque caller-controlled hash or place selectable fields outside its hash.
    """

    if not isinstance(raw, Mapping):
        raise ValueError("ENERGY_V3_CANDIDATE_NOT_A_MAPPING")
    missing = [field for field in _CANDIDATE_REQUIRED_FIELDS if field not in raw]
    if missing:
        raise ValueError(f"ENERGY_V3_CANDIDATE_REQUIRED_FIELD_MISSING:{','.join(missing)}")
    supplied_hash = str(raw.get("candidate_sha256") or "")
    if not _SHA256.fullmatch(supplied_hash):
        raise ValueError("ENERGY_V3_CANDIDATE_HASH_FORMAT_INVALID")
    for field in CANDIDATE_INTEGRITY_CONTRACT_V3["source_lineage_sha256_fields"]:
        value = raw.get(field)
        if field == "source_payload_sha256" and value is None:
            continue
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise ValueError(f"ENERGY_V3_CANDIDATE_LINEAGE_HASH_INVALID:{field}")

    contract_id = raw.get("contract_id")
    if contract_id == "room16.rfc0011.raw_fact_candidate_ir":
        if raw.get("contract_version") != 1:
            raise ValueError("ENERGY_V3_CANDIDATE_CONTRACT_VERSION_INVALID")
        body = dict(raw)
        body.pop("candidate_sha256", None)
        observed_hash = sha256_json(body)
        identity = {field: raw.get(field) for field in _RAW_FACT_IDENTITY_FIELDS}
        expected_id = f"raw.{sha256_json(identity)}"
        validation_mode = "RFC0011_RAW_FACT_COMPATIBILITY"
    elif contract_id == "room16.alpha.energy_v3.inline_raw_typed_candidate":
        if raw.get("contract_version") != 3:
            raise ValueError("ENERGY_V3_CANDIDATE_CONTRACT_VERSION_INVALID")
        body = {
            key: value
            for key, value in raw.items()
            if key not in {"contract_id", "contract_version", "candidate_id", "candidate_sha256"}
        }
        observed_hash = sha256_json(body)
        expected_id = f"energy-v3-inline.{observed_hash}"
        validation_mode = "ENERGY_V3_INLINE_CANONICAL"
    else:
        raise ValueError("ENERGY_V3_CANDIDATE_CONTRACT_NOT_AUTHORIZED")

    if observed_hash != supplied_hash:
        raise ValueError("ENERGY_V3_CANDIDATE_SELF_HASH_MISMATCH")
    if raw.get("candidate_id") != expected_id:
        raise ValueError("ENERGY_V3_CANDIDATE_ID_HASH_MISMATCH")
    return {
        "candidate_id": expected_id,
        "candidate_sha256": observed_hash,
        "validation_mode": validation_mode,
    }

CORE_SLOT_REGISTRY_V3: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_core_slot_registry_v3_candidate",
    "contract_version": 3,
    "profile_family": "Energy",
    "profile_version": 3,
    "subsector_decision": "COMMON_CORE_CONFIRMED",
    "subsector_assignment_by_ticker": False,
    "slots": [
        "revenue",
        "net_income",
        "operating_cash_flow",
        "capital_expenditure",
        "long_term_debt_measure",
    ],
}

ENERGY_PROFILE_V3_CANDIDATE: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_profile_v3_candidate",
    "contract_version": 3,
    "profile_family": "Energy",
    "profile_version": 3,
    "development_status": PROFILE_STATUS,
    "default_cutover": False,
    "freeze_authorized": False,
    "ticker_specific_rules": False,
    "manual_semantic_interventions": False,
    "selection_authority": "RAW_TYPED_FACT_EVIDENCE_ONLY",
    "v1_receipt_selection_authority": False,
    "semantic_contract_v3_sha256": sha256_json(ENERGY_SEMANTIC_CONTRACT_V3),
    "period_freshness_policy_v3_sha256": sha256_json(PERIOD_FRESHNESS_POLICY_V3),
    "core_slot_registry_v3_sha256": sha256_json(CORE_SLOT_REGISTRY_V3),
}

_BASIS_ORDER = {
    metric_id: {basis: index for index, basis in enumerate(bases)}
    for metric_id, bases in PERIOD_FRESHNESS_POLICY_V3["duration_basis_policy"].items()
}


def registry_hashes_v3() -> dict[str, str]:
    """Return all independently bindable Energy v3 registry hashes."""

    return {
        "energy_semantic_contract_v3_sha256": sha256_json(ENERGY_SEMANTIC_CONTRACT_V3),
        "revenue_comparability_contract_v3_sha256": sha256_json(REVENUE_COMPARABILITY_CONTRACT_V3),
        "capex_comparability_contract_v3_sha256": sha256_json(CAPEX_COMPARABILITY_CONTRACT_V3),
        "debt_comparability_contract_v3_sha256": sha256_json(DEBT_COMPARABILITY_CONTRACT_V3),
        "period_freshness_policy_v3_sha256": sha256_json(PERIOD_FRESHNESS_POLICY_V3),
        "core_slot_registry_v3_sha256": sha256_json(CORE_SLOT_REGISTRY_V3),
        "energy_profile_v3_candidate_sha256": sha256_json(ENERGY_PROFILE_V3_CANDIDATE),
    }


def _normalise_fact(raw: dict[str, Any]) -> dict[str, Any]:
    start = raw.get("start_or_null", raw.get("period_start"))
    end = raw.get("end", raw.get("period_end"))
    basis = raw.get("preliminary_duration_role", raw.get("period_basis"))
    if not basis and end:
        basis = "INSTANT" if not start else classify_period_basis(str(start), str(end))[0]
    candidate_id = raw.get("candidate_id", raw.get("evidence_id"))
    source_artifact_sha256 = raw.get("source_artifact_sha256", raw.get("source_entry_sha256"))
    return {
        "candidate_id": candidate_id,
        "candidate_sha256": raw.get("candidate_sha256") or sha256_json(raw),
        "source_artifact_sha256": source_artifact_sha256,
        "source_payload_sha256": raw.get("source_payload_sha256"),
        "source_snapshot_sha256": raw.get("source_snapshot_sha256"),
        "namespace": raw.get("namespace") or "us-gaap",
        "concept": raw.get("concept"),
        "label": raw.get("label") or raw.get("concept"),
        "value": raw.get("value", raw.get("numeric_value")),
        "unit": raw.get("unit"),
        "period_start": start,
        "period_end": end,
        "period_basis": basis,
        "filed": raw.get("filed", raw.get("filed_date")),
        "form": raw.get("form"),
        "accession": raw.get("accession_or_null", raw.get("accession")),
        "dimensions_present": bool(raw.get("dimensions_present", False)),
        "dimension_key": raw.get("dimension_key", "NO_DIMENSIONS"),
        "dimensions": raw.get("dimensions") or {},
        "source_kind": raw.get("source_kind"),
        "source_id": raw.get("source_id"),
        "presentation_evidence": raw.get("presentation_evidence"),
        "statement_role": raw.get("statement_role"),
    }


def _availability(as_of: str, period_end: str, policy: dict[str, Any]) -> tuple[str, int]:
    age = max(0, (date.fromisoformat(as_of) - date.fromisoformat(period_end)).days)
    if age <= int(policy["financial_current_max_age_days"]):
        return "CURRENT_COMPARABLE", age
    if age <= int(policy["financial_aging_max_age_days"]):
        return "AGING_BUT_VALID_DISCLOSED", age
    return "HISTORICAL_ONLY", age


def _rank(metric_id: str, row: dict[str, Any], concepts: dict[str, Any]) -> tuple[Any, ...]:
    return (
        {"CURRENT_COMPARABLE": 0, "AGING_BUT_VALID_DISCLOSED": 1}[row["availability_state"]],
        -int(str(row["period_end"]).replace("-", "")),
        {"A": 0, "B": 1}.get(str(row["economic_scope_grade"]), 99),
        {"A": 0, "B": 1}.get(str(row["context_scope_grade"]), 99),
        _BASIS_ORDER[metric_id].get(str(row["period_basis"]), 99),
        -int(str(row.get("filed") or "0000-00-00").replace("-", "")),
        tuple(concepts).index(str(row["concept"])),
        str(row["candidate_id"]),
    )


def _context_scope(row: dict[str, Any]) -> tuple[str | None, str | None]:
    if not row["dimensions_present"] and row["dimension_key"] == "NO_DIMENSIONS":
        return "A", "CONSOLIDATED_DIMENSIONLESS"
    dimensions = row.get("dimensions") or {}
    if len(dimensions) == 1:
        dimension, member = next(iter(dimensions.items()))
        if str(dimension).casefold() == "us-gaap:businessacquisitionaxis" and str(
            member
        ).casefold().endswith(":successormember"):
            return "B", "LIFECYCLE_CONSOLIDATED_SUCCESSOR"
    return None, None


def select_metric_v3(
    metric_id: str,
    raw_typed_candidates: Iterable[dict[str, Any]],
    *,
    as_of: str,
    semantic_contract: dict[str, Any] = ENERGY_SEMANTIC_CONTRACT_V3,
    period_policy: dict[str, Any] = PERIOD_FRESHNESS_POLICY_V3,
) -> dict[str, Any]:
    """Select the newest admissible fact without consulting an Energy v1 receipt."""

    require_authorized_contract_v3(
        semantic_contract,
        expected_id=ENERGY_SEMANTIC_CONTRACT_V3["contract_id"],
        expected_sha256=AUTHORIZED_SEMANTIC_SHA256,
        label="SEMANTIC_CONTRACT",
    )
    require_authorized_contract_v3(
        period_policy,
        expected_id=PERIOD_FRESHNESS_POLICY_V3["contract_id"],
        expected_sha256=AUTHORIZED_PERIOD_POLICY_SHA256,
        label="PERIOD_POLICY",
    )
    metrics = semantic_contract.get("metrics") or {}
    if metric_id not in metrics:
        raise ValueError(f"UNKNOWN_ENERGY_V3_METRIC:{metric_id}")
    concepts = metrics[metric_id]
    accepted_basis = set(period_policy["duration_basis_policy"][metric_id])
    eligible: list[dict[str, Any]] = []
    historical: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for raw in raw_typed_candidates:
        validate_candidate_integrity_v3(raw)
        row = _normalise_fact(raw)
        if row["concept"] not in concepts:
            continue
        reasons: list[str] = []
        if row["namespace"] != "us-gaap":
            reasons.append("NON_US_GAAP_NAMESPACE")
        context_scope_grade, context_scope = _context_scope(row)
        if context_scope_grade is None:
            reasons.append("DIMENSIONED_OR_SEGMENT_FACT")
        if row["unit"] != "USD":
            reasons.append("UNIT_NOT_USD")
        if not row["candidate_id"] or not row["candidate_sha256"]:
            reasons.append("RAW_CANDIDATE_IDENTITY_OR_HASH_MISSING")
        if not row["source_artifact_sha256"] or not row["source_snapshot_sha256"]:
            reasons.append("RAW_SOURCE_LINEAGE_MISSING")
        if not row["period_end"]:
            reasons.append("PERIOD_END_MISSING")
        if row["filed"] and row["filed"] > as_of:
            reasons.append("FILED_AFTER_AS_OF")
        if row["period_basis"] not in accepted_basis:
            reasons.append("PERIOD_BASIS_NOT_ADMISSIBLE")
        comparison = concepts[row["concept"]]
        if comparison.get("grade") not in {"A", "B"}:
            reasons.append("ECONOMIC_SCOPE_GRADE_NOT_COMPARABLE")
        if reasons:
            rejected.append(
                {"candidate_id": row["candidate_id"], "reason_codes": sorted(set(reasons))}
            )
            continue
        status, age = _availability(as_of, str(row["period_end"]), period_policy)
        candidate = {
            **row,
            "availability_state": status,
            "age_days": age,
            "economic_scope_grade": comparison["grade"],
            "economic_scope": comparison["economic_scope"],
            "context_scope_grade": context_scope_grade,
            "context_scope": context_scope,
        }
        if status == "HISTORICAL_ONLY":
            historical.append(candidate)
        else:
            eligible.append(candidate)
    eligible.sort(key=lambda row: _rank(metric_id, row, concepts))
    historical.sort(key=lambda row: (row["age_days"], str(row["candidate_id"])))
    selected = eligible[0] if eligible else None
    status = (
        selected["availability_state"]
        if selected
        else "HISTORICAL_ONLY"
        if historical
        else "ABSENT"
    )
    ranking_inputs = (
        {
            "availability_state": selected["availability_state"],
            "period_end": selected["period_end"],
            "economic_scope_grade": selected["economic_scope_grade"],
            "context_scope_grade": selected["context_scope_grade"],
            "period_basis": selected["period_basis"],
            "filed": selected["filed"],
            "concept": selected["concept"],
            "candidate_id": selected["candidate_id"],
        }
        if selected
        else None
    )
    body = {
        "contract_id": "room16.alpha.energy_v3_metric_selection_receipt",
        "contract_version": 3,
        "metric_id": metric_id,
        "status": status,
        "counted": int(selected is not None),
        "selected_fact": selected,
        "best_historical_fact": historical[0] if historical else None,
        "eligible_candidate_count": len(eligible),
        "historical_candidate_count": len(historical),
        "rejected_candidates": sorted(
            rejected, key=lambda row: (str(row["candidate_id"]), row["reason_codes"])
        ),
        "deterministic_ranking_inputs": ranking_inputs,
        "selection_authority": "RAW_TYPED_FACT_EVIDENCE_ONLY",
        "v1_resolution_receipt_used": False,
        "period_basis_relabelled": False,
        "quarter_from_ytd_subtraction_used": False,
        "unit_conversion_used": False,
        "current_noncurrent_debt_summed": False,
    }
    return {**body, "receipt_sha256": sha256_json(body)}


def evaluate_energy_v3_case(
    *, ticker: str, as_of: str, raw_typed_candidates: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Evaluate all five common-core slots from raw evidence only."""

    candidates = tuple(raw_typed_candidates)
    receipts = [
        select_metric_v3(metric_id, candidates, as_of=as_of)
        for metric_id in CORE_SLOT_REGISTRY_V3["slots"]
    ]
    resolved = sum(row["counted"] for row in receipts)
    body = {
        "contract_id": "room16.alpha.energy_profile_v3_development_case",
        "contract_version": 3,
        "ticker": ticker.strip().upper(),
        "as_of": as_of,
        "profile_version": 3,
        "development_status": PROFILE_STATUS,
        "provider_call_count": 0,
        "ticker_specific_rules": False,
        "manual_semantic_interventions": 0,
        "selection_authority": "RAW_TYPED_FACT_EVIDENCE_ONLY",
        "v1_resolution_receipt_used": False,
        "resolved_slot_count": resolved,
        "slot_count": len(receipts),
        "coverage_percent": resolved * 100 // len(receipts),
        "current_only_coverage_percent": (
            sum(row["status"] == "CURRENT_COMPARABLE" for row in receipts) * 100 // len(receipts)
        ),
        "aging_slot_count": sum(row["status"] == "AGING_BUT_VALID_DISCLOSED" for row in receipts),
        "slot_receipts": receipts,
    }
    return {**body, "case_sha256": sha256_json(body)}


def _inline_unit(parser: _EnergyV3InlineParser, unit_ref: str) -> str | None:
    measure = parser.units.get(unit_ref, unit_ref)
    normalized = re.sub(r"[^a-z]", "", str(measure).casefold())
    return {"usd": "USD", "isousd": "USD"}.get(normalized)


def inline_xbrl_candidates_v3(
    html: bytes | str,
    *,
    source_artifact_sha256: str,
    source_payload_sha256: str,
    source_snapshot_sha256: str,
    filing_date: str,
    form: str,
    accession: str,
    source_id: str,
) -> list[dict[str, Any]]:
    """Convert admissible standard inline-XBRL facts into hash-bound v3 candidates."""

    parser = _EnergyV3InlineParser()
    parser.feed(html.decode("utf-8", "replace") if isinstance(html, bytes) else html)
    presentation = {
        id(fact): row["text"]
        for row in parser.rows
        for fact in row.get("facts", [])
        if row.get("text")
    }
    allowed = {
        concept
        for concepts in ENERGY_SEMANTIC_CONTRACT_V3["metrics"].values()
        for concept in concepts
    }
    unique: dict[str, dict[str, Any]] = {}
    for fact in parser.facts:
        if fact.get("_tag") != "ix:nonfraction" or fact.get("xsi:nil") == "true":
            continue
        namespace, separator, concept = str(fact.get("name") or "").partition(":")
        if not separator or namespace.casefold() != "us-gaap" or concept not in allowed:
            continue
        context = parser.contexts.get(str(fact.get("contextref") or ""), {})
        start = str(context.get("start") or "") or None
        end = str(context.get("end") or context.get("instant") or "") or None
        value = _inline_numeric_value(fact)
        unit = _inline_unit(parser, str(fact.get("unitref") or ""))
        if end is None or value is None or unit is None:
            continue
        dimensions = dict(sorted((context.get("dimensions") or {}).items()))
        basis = "INSTANT" if context.get("instant") else classify_period_basis(start, end)[0]
        body = {
            "namespace": "us-gaap",
            "concept": concept,
            "label": concept,
            "value": str(value),
            "unit": unit,
            "start_or_null": start,
            "end": end,
            "filed": filing_date,
            "form": form,
            "accession_or_null": accession,
            "dimensions_present": bool(dimensions),
            "dimension_key": "NO_DIMENSIONS" if not dimensions else sha256_json(dimensions),
            "dimensions": dimensions,
            "preliminary_duration_role": basis,
            "source_artifact_sha256": source_artifact_sha256,
            "source_payload_sha256": source_payload_sha256,
            "source_snapshot_sha256": source_snapshot_sha256,
            "source_kind": "inline_xbrl",
            "source_id": source_id,
            "statement_role": "INLINE_XBRL_REPORTED_FACT",
            "presentation_evidence": presentation.get(id(fact)),
        }
        candidate_sha256 = sha256_json(body)
        candidate = {
            "contract_id": "room16.alpha.energy_v3.inline_raw_typed_candidate",
            "contract_version": 3,
            "candidate_id": f"energy-v3-inline.{candidate_sha256}",
            "candidate_sha256": candidate_sha256,
            **body,
        }
        unique[candidate["candidate_id"]] = candidate
    return [unique[key] for key in sorted(unique)]
