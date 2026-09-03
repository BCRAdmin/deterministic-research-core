"""REIT v3 candidate with additive SEC primary-text authority."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from lxml import html

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.profile_authority.contracts import (
    build_sector_profile_contract,
    selection_receipt,
)
from research_agent.profile_authority.integrity import SHA256_RE, canonical_sha256, with_self_hash
from research_agent.profile_authority.source_extension import build_source_extension_contract

from .v2 import ACCEPTANCE_THRESHOLDS_V2, ACCEPTANCE_THRESHOLDS_V2_SHA256

DISCOVERY_PARSER_SPEC = {
    "id": "room16.reit.v3.sec_discovery_parser",
    "version": 1,
    "ordering": "filing_date_desc,accession_asc,document_name_asc",
    "financial_forms": ["10-Q", "10-K"],
    "event_items": ["2.02", "7.01"],
    "exhibit_tokens": ["ex99", "exhibit99", "earnings", "supplement", "presentation"],
}
DISCOVERY_PARSER_SHA256 = canonical_sha256(DISCOVERY_PARSER_SPEC)
SOURCE_EXTENSION_CONTRACT = build_source_extension_contract(
    family="REIT",
    version=3,
    discovery_parser_sha256=DISCOVERY_PARSER_SHA256,
    maximum_discovered_documents=4,
)

PRIMARY_TEXT_PARSER_SPEC = {
    "id": "room16.reit.v3.primary_text_parser",
    "version": 1,
    "method": "HTML_TABLE_ROW_EXPLICIT_FFO",
    "grade_a": ["EXPLICIT_NAREIT_FFO", "UNQUALIFIED_FFO_WITH_RECONCILIATION"],
    "grade_c": ["AFFO", "CORE_FFO", "NORMALIZED_FFO", "ADJUSTED_FFO"],
    "per_share_excluded_from_absolute_slot": True,
    "synthetic_ffo_prohibited": True,
}
PRIMARY_TEXT_PARSER_SHA256 = canonical_sha256(PRIMARY_TEXT_PARSER_SPEC)

CORE_SLOT_CONTRACT = with_self_hash(
    {
        "contract_id": "room16.reit.v3.core_slot_contract@1",
        "slots": [
            {
                "slot_id": "revenue_measure",
                "source_metric_ids": ["revenue"],
                "usable_grades": ["A"],
            },
            {
                "slot_id": "net_income_measure",
                "source_metric_ids": ["net_income", "profit_loss"],
                "usable_grades": ["A", "B"],
            },
            {
                "slot_id": "reit_operating_performance_measure",
                "source_metric_ids": ["reported_ffo"],
                "usable_grades": ["A"],
            },
            {
                "slot_id": "operating_cash_flow",
                "source_metric_ids": ["operating_cash_flow"],
                "usable_grades": ["A"],
            },
            {
                "slot_id": "total_debt_measure",
                "source_metric_ids": ["total_debt"],
                "usable_grades": ["A"],
            },
        ],
        "grade_c_visible_not_counted": True,
        "economic_scope_preserved": True,
        "renaming_does_not_create_comparability": True,
    },
    "core_slot_contract_sha256",
)


def _metric(metric_id: str, grade: str, *, primary: bool = False) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "ordered_concept_scope_rules": ["SEALED_REIT_V3_CORE_SLOT_CONTRACT"],
        "comparability_grade": grade,
        "accepted_units": ["USD"],
        "accepted_period_bases": ["EXPLICIT_REPORTED_PERIOD"]
        if primary
        else ["STANDALONE_QUARTER", "YEAR_TO_DATE", "INSTANT"],
        "source_lineage_required": True,
        "context_dimension_policy": "CONSOLIDATED_ONLY_FAIL_CLOSED",
        "primary_text_required": primary,
    }


REIT_V3_PROFILE = build_sector_profile_contract(
    family="REIT",
    version=3,
    archetype="REIT",
    status="CANDIDATE",
    metrics=[
        _metric("revenue_measure", "A"),
        _metric("net_income_measure", "A"),
        _metric("reit_operating_performance_measure", "A", primary=True),
        _metric("operating_cash_flow", "A"),
        _metric("total_debt_measure", "A"),
    ],
    period_freshness={
        "current_max_age_days": {"flow": 550, "instant": 550, "market": 7},
        "aging_max_age_days": {"flow": 550, "instant": 550, "market": 7},
        "historical_behavior": "VISIBLE_NOT_COUNTED_AS_CURRENT",
        "synthesis_prohibitions": [
            "SYNTHETIC_FFO",
            "QUARTER_FROM_YTD",
            "MISSING_PERIOD_YEAR",
            "LABEL_SIMILARITY",
        ],
    },
    candidate_integrity={
        "allowed_raw_candidate_contracts": [
            "room16.rfc0011.raw_fact_candidate_ir",
            "room16.reit.v3.primary_text_candidate@1",
        ],
        "hash_formula": "SHA256(CANONICAL_JSON(candidate_without_candidate_sha256))",
        "identity_formula": "candidate_id binds full candidate_sha256",
        "required_lineage_hashes": ["source_artifact_sha256", "source_snapshot_sha256"],
    },
    runtime_authority={
        "full_contract_hash_authorization": True,
        "same_id_mutation_allowed": False,
        "frozen_profile_binding_required_if_frozen": True,
    },
)


def _number(cell: str) -> Decimal | None:
    text = cell.strip().replace("$", "").replace(",", "").replace(" ", "")
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return -value if negative else value


def parse_primary_text_candidates(
    path: Path,
    *,
    ticker: str,
    cik: str,
    filing: Mapping[str, Any],
    source_artifact_sha256: str,
    source_snapshot_sha256: str,
) -> list[dict[str, Any]]:
    """Extract explicit reported FFO rows from already captured HTML bytes."""
    if not path.is_file():
        raise ValueError("REIT_V3_CAPTURE_REQUIRED_BEFORE_PRIMARY_TEXT_PARSE")
    if not SHA256_RE.fullmatch(source_artifact_sha256) or not SHA256_RE.fullmatch(
        source_snapshot_sha256
    ):
        raise ValueError("REIT_V3_SOURCE_HASH_INVALID")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != source_artifact_sha256:
        raise ValueError("REIT_V3_SOURCE_ARTIFACT_HASH_MISMATCH")
    root = html.fromstring(payload)
    document_text = " ".join(" ".join(root.itertext()).split())
    lower_document = document_text.lower()
    scale = (
        Decimal(1000) if re.search(r"(?:\$\s*000|\bin thousands\b)", lower_document) else Decimal(1)
    )
    candidates: list[dict[str, Any]] = []
    for row_index, row in enumerate(root.xpath("//tr")):
        cells = [
            " ".join(" ".join(node.itertext()).replace("\xa0", " ").split())
            for node in row.xpath("./th|./td")
        ]
        if not cells:
            continue
        label = cells[0]
        normalized = label.lower()
        if not ("ffo" in normalized or "funds from operations" in normalized):
            continue
        if (
            "per share" in normalized
            or "per diluted share" in normalized
            or "per basic share" in normalized
        ):
            continue
        adjusted = any(
            token in normalized for token in ("affo", "adjusted", "core ffo", "normalized ffo")
        )
        numbers = [value for value in (_number(cell) for cell in cells[1:]) if value is not None]
        if not numbers:
            continue
        reconciliation = "net income" in lower_document and (
            "reconciliation" in lower_document or "nareit" in lower_document
        )
        explicit_nareit = "nareit" in normalized
        grade = "C" if adjusted else ("A" if explicit_nareit or reconciliation else "B")
        semantic = (
            "reported_affo"
            if "affo" in normalized
            else ("reported_core_ffo" if adjusted else "reported_ffo")
        )
        body = {
            "contract_id": "room16.reit.v3.primary_text_candidate@1",
            "candidate_id": "PENDING_HASH",
            "metric_id": semantic,
            "reported_label": label,
            "normalized_semantic_family": "FFO_FAMILY",
            "numeric_value": str(numbers[0] * scale),
            "reported_numeric_value": str(numbers[0]),
            "reported_scale": "USD_THOUSANDS" if scale == 1000 else "USD",
            "unit": "USD",
            "period_start": filing.get("period_start"),
            "period_end": filing.get("report_date"),
            "period_basis": "EXPLICIT_REPORTED_PERIOD",
            "filing_date": filing.get("filing_date"),
            "accession": filing.get("accession"),
            "form": filing.get("form"),
            "document_identity": filing.get("document_name"),
            "source_lineage": {
                "source_artifact_sha256": source_artifact_sha256,
                "source_snapshot_sha256": source_snapshot_sha256,
            },
            "table_section_locator": f"html-tr:{row_index}",
            "reconciliation_identity": "GAAP_NET_INCOME_RECONCILIATION_PRESENT"
            if reconciliation
            else "NOT_PROVEN",
            "economic_scope_grade": grade,
            "context_scope_grade": "CONSOLIDATED_ATTRIBUTABLE"
            if "attributable" in normalized
            else "CONSOLIDATED_REPORTED",
            "extraction_parser_sha256": PRIMARY_TEXT_PARSER_SHA256,
            "synthetic": False,
            "ticker_specific_rule": False,
        }
        preimage = {**body, "candidate_id": "HASH_BOUND"}
        digest = canonical_sha256(preimage)
        body["candidate_id"] = f"room16.reit.v3.primary.{digest}"
        digest = canonical_sha256(body)
        body["candidate_id"] = f"room16.reit.v3.primary.{digest}"
        # Candidate identity participates in the final hash. Stabilize by defining
        # identity as the hash of every selectable field except the display prefix.
        body["candidate_identity_payload_sha256"] = canonical_sha256(
            {key: value for key, value in body.items() if key != "candidate_id"}
        )
        body["candidate_id"] = f"room16.reit.v3.primary.{body['candidate_identity_payload_sha256']}"
        result = with_self_hash(body, "candidate_sha256")
        candidates.append(result)
    return candidates


def validate_primary_text_candidate(candidate: Mapping[str, Any]) -> str:
    if candidate.get("contract_id") != "room16.reit.v3.primary_text_candidate@1":
        raise ValueError("REIT_V3_PRIMARY_CANDIDATE_CONTRACT_INVALID")
    supplied = str(candidate.get("candidate_sha256", ""))
    if not SHA256_RE.fullmatch(supplied):
        raise ValueError("REIT_V3_PRIMARY_CANDIDATE_HASH_INVALID")
    if (
        canonical_sha256({k: v for k, v in candidate.items() if k != "candidate_sha256"})
        != supplied
    ):
        raise ValueError("REIT_V3_PRIMARY_CANDIDATE_HASH_MISMATCH")
    identity = str(candidate.get("candidate_id", ""))
    identity_hash = str(candidate.get("candidate_identity_payload_sha256", ""))
    if not identity.endswith(identity_hash) or not SHA256_RE.fullmatch(identity_hash):
        raise ValueError("REIT_V3_PRIMARY_CANDIDATE_ID_MISMATCH")
    lineage = candidate.get("source_lineage")
    if not isinstance(lineage, Mapping) or any(
        not SHA256_RE.fullmatch(str(lineage.get(key, "")))
        for key in ("source_artifact_sha256", "source_snapshot_sha256")
    ):
        raise ValueError("REIT_V3_PRIMARY_CANDIDATE_LINEAGE_INVALID")
    if candidate.get("synthetic") or candidate.get("ticker_specific_rule"):
        raise ValueError("REIT_V3_PRIMARY_CANDIDATE_POLICY_INVALID")
    return supplied


def select_reported_ffo(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid = []
    rejected = []
    for candidate in candidates:
        validate_primary_text_candidate(candidate)
        if candidate.get("metric_id") != "reported_ffo":
            rejected.append(
                {"candidate_sha256": candidate["candidate_sha256"], "reason": "NON_CORE_FFO_FAMILY"}
            )
        elif candidate.get("economic_scope_grade") != "A":
            rejected.append(
                {
                    "candidate_sha256": candidate["candidate_sha256"],
                    "reason": "GRADE_NOT_CORE_USABLE",
                }
            )
        elif not candidate.get("period_end"):
            rejected.append(
                {"candidate_sha256": candidate["candidate_sha256"], "reason": "PERIOD_END_MISSING"}
            )
        else:
            valid.append(candidate)
    valid.sort(
        key=lambda item: (
            str(item.get("period_end", "")),
            str(item.get("filing_date", "")),
            str(item.get("candidate_sha256", "")),
        ),
        reverse=True,
    )
    selected = valid[0] if valid else None
    receipt = selection_receipt(
        profile=REIT_V3_PROFILE,
        metric_id="reit_operating_performance_measure",
        status="SELECTED" if selected else "UNSUPPORTED",
        selected_candidate=selected,
        rejected_candidates=rejected
        + [
            {"candidate_sha256": item["candidate_sha256"], "reason": "LOWER_DETERMINISTIC_RANK"}
            for item in valid[1:]
        ],
        period_basis=selected.get("period_basis") if selected else None,
        availability="PRIMARY_TEXT_CAPTURED" if selected else "PRIMARY_TEXT_NO_CORE_FFO",
    )
    return {"selected": selected, "receipt": receipt}


def resolve_core_slots(
    base_semantic_metric_ids: Sequence[str], ffo_selection: Mapping[str, Any]
) -> list[dict[str, Any]]:
    present = set(base_semantic_metric_ids)
    mapping = {
        "revenue_measure": "revenue" in present,
        "net_income_measure": bool({"net_income", "profit_loss"} & present),
        "reit_operating_performance_measure": ffo_selection.get("selected") is not None,
        "operating_cash_flow": "operating_cash_flow" in present,
        "total_debt_measure": "total_debt" in present,
    }
    return [
        {
            "slot_id": slot,
            "status": "RESOLVED" if resolved else "UNSUPPORTED",
            "counted": int(resolved),
            "economic_scope_grade": "A" if resolved else None,
            "core_slot_contract_sha256": CORE_SLOT_CONTRACT["core_slot_contract_sha256"],
        }
        for slot, resolved in mapping.items()
    ]


def seal_reit_v3_candidate(
    *,
    research_commit: str,
    research_tree: str,
    study_hashes: Mapping[str, str],
    development_corpus_hashes: Sequence[str],
    full_tests_sha256: str,
) -> dict[str, Any]:
    body = {
        "contract_id": "room16.reit_v3.candidate_seal@1",
        "profile_family": "REIT",
        "profile_version": 3,
        "research_commit": research_commit,
        "research_tree": research_tree,
        "shared_profile_contract_sha256": REIT_V3_PROFILE["profile_contract_sha256"],
        "source_extension_contract_sha256": SOURCE_EXTENSION_CONTRACT["source_extension_sha256"],
        "sec_discovery_parser_sha256": DISCOVERY_PARSER_SHA256,
        "primary_text_parser_sha256": PRIMARY_TEXT_PARSER_SHA256,
        "study_hashes": dict(study_hashes),
        "metric_registry_sha256": sha256_json(
            [m["metric_id"] for m in REIT_V3_PROFILE["metric_contracts"]]
        ),
        "core_slot_contract_sha256": CORE_SLOT_CONTRACT["core_slot_contract_sha256"],
        "formula_registry_sha256": canonical_sha256(
            {"synthetic_ffo": "PROHIBITED", "total_debt": "EXACT_EXHAUSTIVE_ONLY"}
        ),
        "freshness_period_policy_sha256": canonical_sha256(
            REIT_V3_PROFILE["period_freshness_contract"]
        ),
        "candidate_integrity_contract_sha256": canonical_sha256(
            REIT_V3_PROFILE["candidate_integrity_contract"]
        ),
        "acceptance_threshold_sha256": ACCEPTANCE_THRESHOLDS_V2_SHA256,
        "development_corpus_hashes": list(development_corpus_hashes),
        "full_tests_sha256": full_tests_sha256,
        "semantic_changes_after_seal": 0,
        "formula_changes_after_seal": 0,
        "source_selection_rule_changes_after_seal": 0,
        "parser_changes_after_seal": 0,
        "threshold_changes_after_seal": 0,
        "profile_changes_after_seal": 0,
    }
    return with_self_hash(body, "candidate_seal_sha256")


R15_ATTACK_FIELDS = {
    "frozen_energy_mutation",
    "cross_profile_substitution",
    "same_id_descriptor_mutation",
    "shared_historical_mutation",
    "candidate_integrity_bypass",
    "period_policy_mutation",
    "threshold_authority_mutation",
    "energy_v1_mutation",
    "energy_v2_mutation",
    "energy_v3_mutation",
    "unapproved_domain",
    "parse_before_capture",
    "result_based_discovery",
    "unsealed_exhibit_fetch",
    "accession_substitution",
    "cross_filing_exhibit",
    "post_as_of_filing",
    "ticker_specific_sec_url",
    "unbounded_discovery",
    "document_hash_mutation",
    "ffo_without_period",
    "per_share_as_absolute",
    "affo_as_nareit_ffo",
    "core_ffo_as_unqualified",
    "header_period_mismatch",
    "candidate_value_outside_hash",
    "source_hash_forgery",
    "reconciliation_source_substitution",
    "ticker_phrase_allowlist",
    "live_html_semantic_parse",
    "profit_loss_renamed",
    "lease_income_as_revenue_grade_a",
    "secured_debt_as_total",
    "mismatched_debt_periods",
    "debt_double_count",
    "stale_as_current",
    "historical_only_resolved",
    "manual_semantic_patch",
    "threshold_mutation",
    "post_seal_semantic_change",
    "exposed_ticker_selection",
    "exposed_alias_selection",
    "exposed_cik_selection",
    "provider_call_before_seal",
    "result_based_selection",
    "replacement_case",
    "thirteenth_case",
    "second_validation_batch",
    "product_mutation",
    "premature_reit_freeze_claim",
}


def guard_r15_action(action: Mapping[str, Any]) -> None:
    active = sorted(key for key in R15_ATTACK_FIELDS if action.get(key))
    if active:
        raise ValueError(f"R15_POLICY_BLOCK:{active[0]}")
    if action.get("provider_calls_before_selection_seal", 0):
        raise ValueError("R15_POLICY_BLOCK:provider_call_before_seal")
    if action.get("case_count", 12) != 12:
        raise ValueError("R15_POLICY_BLOCK:batch_cardinality")


__all__ = [
    "ACCEPTANCE_THRESHOLDS_V2",
    "CORE_SLOT_CONTRACT",
    "DISCOVERY_PARSER_SHA256",
    "PRIMARY_TEXT_PARSER_SHA256",
    "REIT_V3_PROFILE",
    "R15_ATTACK_FIELDS",
    "SOURCE_EXTENSION_CONTRACT",
    "guard_r15_action",
    "parse_primary_text_candidates",
    "resolve_core_slots",
    "seal_reit_v3_candidate",
    "select_reported_ffo",
    "validate_primary_text_candidate",
]
