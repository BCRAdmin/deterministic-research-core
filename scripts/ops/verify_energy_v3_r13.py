#!/usr/bin/env python3
"""Standalone standard-library verifier for the Energy-v3 R13 result package."""

from __future__ import annotations

import hashlib
import io
import json
import statistics
import sys
import zipfile
from copy import deepcopy
from datetime import date
from pathlib import PurePosixPath
from typing import Any

EXPECTED_R12_SHA256 = "d639efbfdb43a7310572e79a9354f9c1f8a15a89f067203fb3cc8a7df2db034d"
EXPECTED_R12_MANIFEST_SHA256 = "bb4fa0847a807f173acabc8c2dfb1a5a70406f32030df53439db9b8860eb74e7"
EXPECTED_R12_SEAL_SHA256 = "cc5ed70dfa0c0b84943f64671d2ff92f8c671a0b8d3a23cd48f71902c52db7d3"
EXPECTED_R12_SEMANTIC_SHA256 = "888dac95b998ec7d093bdccd781f1f0a7bf9166dd91450da61f92b8684a7da7d"
EXPECTED_R13_VERDICT = "ENERGY_V3_R13_FREEZE_CLOSURE_PASS_READY_FOR_FINAL_INDEPENDENT_FREEZE"
EXPECTED_TICKERS = ["DWSN", "EPM", "OVV", "ANNA", "BKV", "EGY", "AR", "CNR", "CVI", "CKX", "XPRO", "HAL"]
AS_OF = "2026-09-03"
SHA_FIELDS = {
    "01_R12_INDEPENDENT_REVIEW_INPUT_BINDING.json": "binding_sha256",
    "02_PRESEAL_ENERGY_V3_SEMANTIC_AUTHORITY_STUDY.json": "study_sha256",
    "03_MONOTONIC_HARDENING_CHANGE_CLASSIFICATION.json": "classification_sha256",
    "04_R12_MONOTONIC_EQUIVALENCE_REPLAY.json": "equivalence_sha256",
    "05_ACTIVE_ADVERSARIAL_FREEZE_TESTS.json": "adversarial_sha256",
    "06_CONTRACT_AUTHORITY_GUARD.json": "guard_sha256",
    "07_CANDIDATE_INTEGRITY_CONTRACT.json": "integrity_contract_sha256",
    "08_FULL_REGRESSION.json": "regression_sha256",
    "09_ENERGY_V1_V2_NONINTERFERENCE.json": "noninterference_sha256",
    "10_SHARED_AUTHORITY_NONINTERFERENCE.json": "noninterference_sha256",
    "11_PRODUCT_NONINTERFERENCE.json": "noninterference_sha256",
    "12_BOUNDARY_GATE.json": "boundary_sha256",
    "13_R13_ACCEPTANCE_MATRIX.json": "matrix_sha256",
    "14_CHANGESET_AND_SCOPE.json": "changeset_sha256",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_json(value: Any) -> str:
    return sha(canonical(value))


def safe_names(archive: zipfile.ZipFile) -> list[str]:
    names = archive.namelist()
    if len(names) != len(set(names)) or archive.testzip() is not None:
        raise RuntimeError("ZIP_DUPLICATE_OR_CRC_FAILURE")
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise RuntimeError(f"UNSAFE_ZIP_PATH:{name}")
    return names


def verify_selfhash(value: dict[str, Any], field: str, expected: str | None = None) -> str:
    body = dict(value)
    claim = str(body.pop(field))
    if sha_json(body) != claim or (expected is not None and claim != expected):
        raise RuntimeError(f"SELFHASH_MISMATCH:{field}")
    return claim


def validate_candidate(raw: dict[str, Any]) -> None:
    supplied = str(raw.get("candidate_sha256") or "")
    if len(supplied) != 64 or any(char not in "0123456789abcdef" for char in supplied):
        raise ValueError("CANDIDATE_HASH_FORMAT_INVALID")
    for field in ("source_artifact_sha256", "source_snapshot_sha256"):
        value = raw.get(field)
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"CANDIDATE_LINEAGE_HASH_INVALID:{field}")
    if raw.get("source_payload_sha256") is not None:
        value = str(raw["source_payload_sha256"])
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("CANDIDATE_LINEAGE_HASH_INVALID:source_payload_sha256")
    if raw.get("contract_id") == "room16.rfc0011.raw_fact_candidate_ir":
        body = dict(raw); body.pop("candidate_sha256", None)
        observed = sha_json(body)
        identity = {key: raw.get(key) for key in ("source_snapshot_sha256", "source_artifact_sha256", "namespace", "concept", "unit", "start_or_null", "end", "filed", "form", "accession_or_null", "frame_or_null", "value")}
        expected_id = f"raw.{sha_json(identity)}"
    elif raw.get("contract_id") == "room16.alpha.energy_v3.inline_raw_typed_candidate":
        body = {key: value for key, value in raw.items() if key not in {"contract_id", "contract_version", "candidate_id", "candidate_sha256"}}
        observed = sha_json(body)
        expected_id = f"energy-v3-inline.{observed}"
    else:
        raise ValueError("CANDIDATE_CONTRACT_NOT_AUTHORIZED")
    if observed != supplied:
        raise ValueError("CANDIDATE_SELF_HASH_MISMATCH")
    if raw.get("candidate_id") != expected_id:
        raise ValueError("CANDIDATE_ID_HASH_MISMATCH")


def normalise(raw: dict[str, Any]) -> dict[str, Any]:
    start = raw.get("start_or_null", raw.get("period_start"))
    end = raw.get("end", raw.get("period_end"))
    basis = raw.get("preliminary_duration_role", raw.get("period_basis"))
    return {
        "candidate_id": raw.get("candidate_id", raw.get("evidence_id")),
        "candidate_sha256": raw.get("candidate_sha256"),
        "source_artifact_sha256": raw.get("source_artifact_sha256", raw.get("source_entry_sha256")),
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


def context_scope(row: dict[str, Any]) -> tuple[str | None, str | None]:
    if not row["dimensions_present"] and row["dimension_key"] == "NO_DIMENSIONS":
        return "A", "CONSOLIDATED_DIMENSIONLESS"
    dimensions = row.get("dimensions") or {}
    if len(dimensions) == 1:
        dimension, member = next(iter(dimensions.items()))
        if str(dimension).casefold() == "us-gaap:businessacquisitionaxis" and str(member).casefold().endswith(":successormember"):
            return "B", "LIFECYCLE_CONSOLIDATED_SUCCESSOR"
    return None, None


def require_contract(value: dict[str, Any], expected_id: str, expected_sha: str, label: str) -> None:
    if value.get("contract_id") != expected_id:
        raise ValueError(f"{label}_NOT_AUTHORIZED")
    if sha_json(value) != expected_sha:
        raise ValueError(f"{label}_HASH_NOT_AUTHORIZED")


def select_metric(metric: str, candidates: list[dict[str, Any]], semantic: dict[str, Any], policy: dict[str, Any], semantic_sha: str, policy_sha: str) -> dict[str, Any]:
    require_contract(semantic, "room16.alpha.energy_semantic_contract_v3_candidate", semantic_sha, "SEMANTIC_CONTRACT")
    require_contract(policy, "room16.alpha.energy_period_freshness_policy_v3_candidate", policy_sha, "PERIOD_POLICY")
    concepts = semantic["metrics"][metric]
    accepted_basis = set(policy["duration_basis_policy"][metric])
    basis_order = {basis: index for index, basis in enumerate(policy["duration_basis_policy"][metric])}
    eligible = []
    historical = []
    rejected = []
    for raw in candidates:
        validate_candidate(raw)
        row = normalise(raw)
        if row["concept"] not in concepts:
            continue
        reasons = []
        if row["namespace"] != "us-gaap": reasons.append("NON_US_GAAP_NAMESPACE")
        context_grade, context = context_scope(row)
        if context_grade is None: reasons.append("DIMENSIONED_OR_SEGMENT_FACT")
        if row["unit"] != "USD": reasons.append("UNIT_NOT_USD")
        if not row["source_artifact_sha256"] or not row["source_snapshot_sha256"]: reasons.append("RAW_SOURCE_LINEAGE_MISSING")
        if not row["period_end"]: reasons.append("PERIOD_END_MISSING")
        if row["filed"] and row["filed"] > AS_OF: reasons.append("FILED_AFTER_AS_OF")
        if row["period_basis"] not in accepted_basis: reasons.append("PERIOD_BASIS_NOT_ADMISSIBLE")
        comparison = concepts[row["concept"]]
        if comparison.get("grade") not in {"A", "B"}: reasons.append("ECONOMIC_SCOPE_GRADE_NOT_COMPARABLE")
        if reasons:
            rejected.append({"candidate_id": row["candidate_id"], "reason_codes": sorted(set(reasons))})
            continue
        age = max(0, (date.fromisoformat(AS_OF) - date.fromisoformat(str(row["period_end"]))).days)
        availability = "CURRENT_COMPARABLE" if age <= policy["financial_current_max_age_days"] else "AGING_BUT_VALID_DISCLOSED" if age <= policy["financial_aging_max_age_days"] else "HISTORICAL_ONLY"
        candidate = {**row, "availability_state": availability, "age_days": age, "economic_scope_grade": comparison["grade"], "economic_scope": comparison["economic_scope"], "context_scope_grade": context_grade, "context_scope": context}
        (historical if availability == "HISTORICAL_ONLY" else eligible).append(candidate)
    eligible.sort(key=lambda row: ({"CURRENT_COMPARABLE": 0, "AGING_BUT_VALID_DISCLOSED": 1}[row["availability_state"]], -int(str(row["period_end"]).replace("-", "")), {"A": 0, "B": 1}.get(row["economic_scope_grade"], 99), {"A": 0, "B": 1}.get(row["context_scope_grade"], 99), basis_order.get(row["period_basis"], 99), -int(str(row.get("filed") or "0000-00-00").replace("-", "")), tuple(concepts).index(row["concept"]), str(row["candidate_id"])))
    historical.sort(key=lambda row: (row["age_days"], str(row["candidate_id"])))
    selected = eligible[0] if eligible else None
    return {
        "metric_id": metric,
        "status": selected["availability_state"] if selected else "HISTORICAL_ONLY" if historical else "ABSENT",
        "counted": int(selected is not None),
        "selected_fact": selected,
        "best_historical_fact": historical[0] if historical else None,
        "rejected_candidates": sorted(rejected, key=lambda row: (str(row["candidate_id"]), row["reason_codes"])),
        "current_noncurrent_debt_summed": False,
    }


def projection(receipts: list[dict[str, Any]], coverage: int, current: int, aging: int) -> dict[str, Any]:
    return {
        "coverage_percent": coverage,
        "current_only_coverage_percent": current,
        "aging_slot_count": aging,
        "metrics": {row["metric_id"]: {"status": row["status"], "counted": row["counted"], "selected": None if row["selected_fact"] is None else {key: row["selected_fact"].get(source) for key, source in (("concept", "concept"), ("value", "value"), ("period_start", "period_start"), ("period_end", "period_end"), ("period_basis", "period_basis"), ("economic_scope_grade", "economic_scope_grade"), ("context_scope_grade", "context_scope_grade"), ("availability", "availability_state"))}} for row in receipts},
    }


def recompute_case(candidates: list[dict[str, Any]], semantic: dict[str, Any], policy: dict[str, Any], slots: list[str], semantic_sha: str, policy_sha: str) -> dict[str, Any]:
    receipts = [select_metric(metric, candidates, semantic, policy, semantic_sha, policy_sha) for metric in slots]
    return projection(receipts, sum(row["counted"] for row in receipts) * 100 // len(receipts), sum(row["status"] == "CURRENT_COMPARABLE" for row in receipts) * 100 // len(receipts), sum(row["status"] == "AGING_BUT_VALID_DISCLOSED" for row in receipts))


def run_guard_attacks(semantic: dict[str, Any], policy: dict[str, Any], semantic_sha: str, policy_sha: str, candidate: dict[str, Any]) -> int:
    blocked = 0
    mutations = []
    for mutate in (
        lambda x: x["metrics"]["revenue"].update({"IssuerRevenue": {"grade": "B", "economic_scope": "extension"}}),
        lambda x: x["metrics"]["revenue"]["RevenueFromContractWithCustomerExcludingAssessedTax"].update({"grade": "A"}),
        lambda x: x.update({"issuer_extension_concepts_allowed": True}),
    ):
        value = deepcopy(semantic); mutate(value); mutations.append((value, policy, "SEMANTIC_CONTRACT_HASH_NOT_AUTHORIZED"))
    for mutate in (
        lambda x: x["duration_basis_policy"]["revenue"].append("YEAR_TO_DATE"),
        lambda x: x.update({"financial_current_max_age_days": 9999}),
        lambda x: x.update({"historical_only_counts_as_resolved": True}),
        lambda x: x.update({"current_noncurrent_debt_summed": True}),
    ):
        value = deepcopy(policy); mutate(value); mutations.append((semantic, value, "PERIOD_POLICY_HASH_NOT_AUTHORIZED"))
    for sem, pol, expected in mutations:
        try: select_metric("revenue", [], sem, pol, semantic_sha, policy_sha)
        except ValueError as exc:
            if expected not in str(exc): raise
            blocked += 1
        else: raise RuntimeError("SAME_ID_MUTATION_ACCEPTED")
    for field, replacement, expected in (
        ("value", "101", "CANDIDATE_SELF_HASH_MISMATCH"),
        ("concept", "NetIncomeLoss", "CANDIDATE_SELF_HASH_MISMATCH"),
        ("end", "2026-06-29", "CANDIDATE_SELF_HASH_MISMATCH"),
        ("dimensions", {"axis": "member"}, "CANDIDATE_SELF_HASH_MISMATCH"),
        ("source_artifact_sha256", "d" * 64, "CANDIDATE_SELF_HASH_MISMATCH"),
        ("candidate_id", f"energy-v3-inline.{'e' * 64}", "CANDIDATE_ID_HASH_MISMATCH"),
        ("candidate_sha256", "forged", "CANDIDATE_HASH_FORMAT_INVALID"),
    ):
        value = deepcopy(candidate); value[field] = replacement
        try: validate_candidate(value)
        except ValueError as exc:
            if expected not in str(exc): raise
            blocked += 1
        else: raise RuntimeError("CANDIDATE_TAMPER_ACCEPTED")
    return blocked


def main(path: str) -> None:
    with zipfile.ZipFile(path) as archive:
        names = safe_names(archive)
        manifest = json.loads(archive.read("MANIFEST.json"))
        verify_selfhash(manifest, "manifest_sha256")
        if manifest["verdict"] != EXPECTED_R13_VERDICT or manifest["freeze_authorized"]:
            raise RuntimeError("R13_MANIFEST_VERDICT_OR_FREEZE_INVALID")
        rows = {row["path"]: row for row in manifest["files"]}
        if len(rows) != manifest["file_count"]:
            raise RuntimeError("R13_MANIFEST_COUNT_MISMATCH")
        for name, row in rows.items():
            payload = archive.read(name)
            if len(payload) != row["bytes"] or sha(payload) != row["sha256"]:
                raise RuntimeError(f"R13_PAYLOAD_MISMATCH:{name}")
        checksums = archive.read("CHECKSUMS.sha256").decode().splitlines()
        checksum_map = {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in checksums}
        if checksum_map.get("MANIFEST.json") != sha(archive.read("MANIFEST.json")) or any(checksum_map.get(name) != row["sha256"] for name, row in rows.items()):
            raise RuntimeError("R13_CHECKSUM_MISMATCH")
        evidence = {}
        for name, field in SHA_FIELDS.items():
            value = json.loads(archive.read(name))
            verify_selfhash(value, field)
            evidence[name] = value
        if any(value.get("status") != "PASS" for value in evidence.values()):
            raise RuntimeError("R13_EVIDENCE_STATUS_NOT_PASS")

        r12_name = next(name for name in names if name.startswith("r12_binding/") and name.endswith(".zip"))
        r12_bytes = archive.read(r12_name)
        if sha(r12_bytes) != EXPECTED_R12_SHA256:
            raise RuntimeError("R12_NESTED_ZIP_HASH_MISMATCH")
        with zipfile.ZipFile(io.BytesIO(r12_bytes)) as r12zip:
            safe_names(r12zip)
            r12_manifest = json.loads(r12zip.read("MANIFEST.json"))
            verify_selfhash(r12_manifest, "manifest_sha256", EXPECTED_R12_MANIFEST_SHA256)
            seal = json.loads(r12zip.read("05_ENERGY_V3_CANDIDATE_SEAL.json"))
            verify_selfhash(seal, "candidate_seal_sha256", EXPECTED_R12_SEAL_SHA256)
            if seal["candidate_semantic_sha256"] != EXPECTED_R12_SEMANTIC_SHA256:
                raise RuntimeError("R12_SEMANTIC_BINDING_MISMATCH")
            semantic = seal["semantic_contract_v3"]
            policy = seal["period_policy_v3"]
            slots = seal["core_subsector_registry_v3"]["slots"]
            semantic_sha = sha_json(semantic)
            policy_sha = sha_json(policy)
            guard = evidence["06_CONTRACT_AUTHORITY_GUARD.json"]
            if semantic_sha != guard["authorized_semantic_sha256"] or policy_sha != guard["authorized_period_policy_sha256"]:
                raise RuntimeError("R13_GUARD_AUTHORITY_MISMATCH")
            epoch = json.loads(r12zip.read("08_EPOCH2_SELECTED_CASES_SEALED.json"))
            if [row["ticker"] for row in epoch["selected_cases"]] != EXPECTED_TICKERS:
                raise RuntimeError("R12_TICKER_SELECTION_MISMATCH")
            stored = {row["ticker"]: row["v3_result"] for row in json.loads(r12zip.read("10_EPOCH2_CASE_RESULTS.json"))["cases"]}
            computed = []
            first_candidate = None
            for case in epoch["selected_cases"]:
                nested_bytes = r12zip.read(f"raw_cases/{case['sequence']:02d}_{case['ticker']}.zip")
                with zipfile.ZipFile(io.BytesIO(nested_bytes)) as nested:
                    safe_names(nested)
                    doc = json.loads(nested.read(f"{case['sequence']:02d}_{case['ticker']}/21_ENERGY_V3_RAW_CANDIDATES.json"))
                    candidates = doc["candidates"]
                    first_candidate = first_candidate or next(row for row in candidates if row.get("contract_id") == "room16.alpha.energy_v3.inline_raw_typed_candidate")
                    observed = recompute_case(candidates, semantic, policy, slots, semantic_sha, policy_sha)
                    expected = evidence["04_R12_MONOTONIC_EQUIVALENCE_REPLAY.json"]["r12_epoch2_cases"][case["sequence"] - 1]["expected_projection_sha256"]
                    if sha_json(observed) != expected:
                        raise RuntimeError(f"R13_CASE_EQUIVALENCE_MISMATCH:{case['ticker']}")
                    computed.append(observed)
            usable = [row["coverage_percent"] for row in computed]
            current = [row["current_only_coverage_percent"] for row in computed]
            if (statistics.median(usable), min(usable), statistics.median(current), min(current), max(row["aging_slot_count"] for row in computed)) != (100, 60, 100, 60, 0):
                raise RuntimeError("R13_ACCEPTANCE_RECOMPUTE_MISMATCH")
            attacks = run_guard_attacks(semantic, policy, semantic_sha, policy_sha, first_candidate)

        study = evidence["02_PRESEAL_ENERGY_V3_SEMANTIC_AUTHORITY_STUDY.json"]
        if study["epoch2_outcomes_used_for_rule_justification"] or study["new_provider_calls"] or set(study["development_tickers"]) & set(EXPECTED_TICKERS):
            raise RuntimeError("R13_PRESEAL_AUTHORITY_CONTAMINATED")
        if not study["study_is_exhaustive_over_available_preseal_candidates"] or not study["all_grade_b_rules_covered"]:
            raise RuntimeError("R13_PRESEAL_AUTHORITY_INCOMPLETE")
        equivalence = evidence["04_R12_MONOTONIC_EQUIVALENCE_REPLAY.json"]
        if equivalence["r12_epoch2_semantic_decisions_identical"] != 60 or equivalence["development_semantic_decisions_identical"] != 110:
            raise RuntimeError("R13_EQUIVALENCE_COUNTS_INVALID")
        adversarial = evidence["05_ACTIVE_ADVERSARIAL_FREEZE_TESTS.json"]
        if adversarial["attack_count"] < 30 or adversarial["blocked_count"] != adversarial["attack_count"] or adversarial["predicate_only_checks"]:
            raise RuntimeError("R13_ACTIVE_ADVERSARIAL_INVALID")
        regression = evidence["08_FULL_REGRESSION.json"]
        for suite in (regression["full_research"], regression["focused_energy_v3_r13"]):
            if suite["status"] != "PASS" or suite["failures"] or suite["errors"] or suite["skipped"]:
                raise RuntimeError("R13_REGRESSION_INVALID")
        matrix = evidence["13_R13_ACCEPTANCE_MATRIX.json"]
        if matrix["failed"] or matrix["passed"] != matrix["row_count"] or matrix["freeze_authorized"]:
            raise RuntimeError("R13_MATRIX_INVALID")
        for name in ("09_ENERGY_V1_V2_NONINTERFERENCE.json", "10_SHARED_AUTHORITY_NONINTERFERENCE.json", "11_PRODUCT_NONINTERFERENCE.json", "12_BOUNDARY_GATE.json"):
            if evidence[name]["status"] != "PASS":
                raise RuntimeError(f"R13_NONINTERFERENCE_INVALID:{name}")

        receipt = {
            "status": "PASS",
            "verdict": EXPECTED_R13_VERDICT,
            "outer_entry_count": len(names),
            "manifest_file_count": manifest["file_count"],
            "manifest_sha256": manifest["manifest_sha256"],
            "payload_hash_mismatches": 0,
            "r12_rebound": True,
            "r12_case_results_recomputed": len(computed),
            "r12_epoch2_semantic_decisions_recomputed": len(computed) * len(slots),
            "same_id_contract_attacks_reexecuted": 7,
            "candidate_integrity_attacks_reexecuted": attacks - 7,
            "total_critical_attacks_reexecuted": attacks,
            "usable_median": statistics.median(usable),
            "usable_minimum": min(usable),
            "current_only_median": statistics.median(current),
            "current_only_minimum": min(current),
            "maximum_aging_slots": max(row["aging_slot_count"] for row in computed),
            "freeze_authorized": False,
            "new_provider_calls": 0,
            "new_validation_cases": 0,
        }
        print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_energy_v3_r13.py PACKAGE.zip")
    main(sys.argv[1])
