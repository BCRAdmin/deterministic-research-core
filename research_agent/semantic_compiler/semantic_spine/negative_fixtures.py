"""Finding-specific red/green/reintroduction proofs for RFC-0002."""

from __future__ import annotations

import copy
from typing import Any, Callable

from research_agent.compiler_foundation.canonical import sha256_json

from .contracts import TypedFactSpineIR, create_hashed
from .pass_protocol import load_pass_contracts, validate_pass_contracts
from .signature_authority import MetricSignatureAuthority


def _fact(signature: Any, **changes: str) -> TypedFactSpineIR:
    values = {
        "fact_id": "FACT_FIXTURE",
        "metric_id": signature.legacy_metric_id,
        "metric_definition_id": signature.metric_definition_id,
        "fact_kind": signature.fact_kind,
        "fact_type": signature.fact_subtype,
        "value_state": "value",
        "value": 1.0,
        "dimension": signature.dimension,
        "unit": signature.unit,
        "currency": signature.currency,
        "scale": signature.scale,
        "period_kind": signature.period_role,
        "period_start": None,
        "period_end": None,
        "source_ids": ("SOURCE_FIXTURE",),
        "evidence_ids": ("EVIDENCE_FIXTURE",),
        "source_locator": "fixture://locator",
        "table_id": None,
        "cell_id": None,
        "normalized_record_sha256": "b" * 64,
    }
    values.update(changes)
    return create_hashed(TypedFactSpineIR, **values)


def _proof(fixture_id: str, finding_id: str, expected_code: str, defective: Any, corrected: Any, evaluator: Callable[[Any], None]) -> dict[str, Any]:
    def run(payload: Any) -> dict[str, Any]:
        try:
            evaluator(payload)
        except Exception as exc:  # fixture evidence intentionally captures the fail-closed surface
            return {"gate_allowed": False, "actual_diagnostic": str(exc), "payload_sha256": sha256_json(payload)}
        return {"gate_allowed": True, "actual_diagnostic": None, "payload_sha256": sha256_json(payload)}

    defective_result = run(defective)
    corrected_result = run(corrected)
    reintroduced_result = run(copy.deepcopy(defective))
    closed = (
        not defective_result["gate_allowed"]
        and corrected_result["gate_allowed"]
        and not reintroduced_result["gate_allowed"]
    )
    return {
        "fixture_id": fixture_id,
        "finding_id": finding_id,
        "expected_diagnostic_code": expected_code,
        "defective": defective,
        "corrected": corrected,
        "reintroduced": copy.deepcopy(defective),
        "defective_result": defective_result,
        "corrected_result": corrected_result,
        "reintroduced_result": reintroduced_result,
        "closure_proven": closed,
    }


def build_negative_fixture_proofs() -> tuple[dict[str, Any], ...]:
    authority = MetricSignatureAuthority.load()
    field_map = {
        "fact_kind": "fact_kind",
        "fact_type": "fact_subtype",
        "period_kind": "period_role",
        "dimension": "dimension",
        "unit": "unit",
        "currency": "currency",
    }
    wrong_cases = {
        "stock_as_period_flow": {"fact_kind": "flow", "fact_type": "period_total", "period_kind": "duration"},
        "absolute_rate_as_yoy_change": {"fact_type": "year_over_year_change", "period_kind": "comparison"},
        "quarterly_rate_as_period_total": {"fact_type": "period_total", "period_kind": "duration"},
        "count_as_currency": {"dimension": "currency", "unit": "USD", "currency": "USD"},
        "guidance_as_historical_actual": {"fact_kind": "guidance_range", "fact_type": "guidance_range", "period_kind": "guidance"},
        "per_share_as_total_cash_flow": {"dimension": "currency", "fact_kind": "flow", "fact_type": "flow_value", "unit": "USD"},
        "percentage_of_total_as_change": {"fact_type": "contribution_to_change", "period_kind": "comparison"},
    }
    proofs: list[dict[str, Any]] = []
    for fixture_id, changes in wrong_cases.items():
        signature = next(
            item for item in authority.signatures.values()
            if any(getattr(item, field_map[key]) != value for key, value in changes.items())
        )
        corrected = _fact(signature).model_dump(mode="json")
        defective = _fact(signature, **changes).model_dump(mode="json")

        def evaluate(payload: dict[str, Any]) -> None:
            authority.require_fact_signature(TypedFactSpineIR.model_validate(payload))

        proofs.append(_proof(
            f"metric.{fixture_id}",
            "SCW-004",
            "METRIC_SIGNATURE_CONTRACT_MISMATCH",
            defective,
            corrected,
            evaluate,
        ))
    pass_payload, _ = load_pass_contracts()
    mutations = {
        "pass.version": lambda value: value.update({"contract_version": 99}),
        "pass.order": lambda value: value["passes"].reverse(),
        "pass.skip": lambda value: value["passes"][0].update({"skippable": True}),
        "pass.ba10": lambda value: value.update({"ba10_authorized": True}),
    }
    for fixture_id, mutate in mutations.items():
        defective = copy.deepcopy(pass_payload)
        mutate(defective)
        proofs.append(_proof(
            fixture_id,
            "SCW-001",
            "PASS_PROTOCOL_CONTRACT_VIOLATION",
            defective,
            pass_payload,
            lambda payload: validate_pass_contracts(payload),
        ))
    return tuple(proofs)
