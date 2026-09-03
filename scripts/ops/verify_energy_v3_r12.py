#!/usr/bin/env python3
"""Standalone standard-library verifier for Room16 Energy-v3 R12 evidence."""

from __future__ import annotations

import hashlib
import io
import json
import statistics
import sys
import zipfile
from datetime import date
from pathlib import PurePosixPath
from typing import Any


EXPECTED_R11_SHA256 = "30cf4d6eb45593a8e1ef12ce5ac80c659501bd0d95c7395455474fea7bbabf95"
EXPECTED_R11_MANIFEST_SHA256 = "69331b77e987b4c684657ff8a2592e0d12e5f824a6a8e736253a1921b3dff781"
EXPECTED_R11_SELECTION_SEAL_SHA256 = (
    "9a31809ee960a05c1478b12905f2c442875aac360371cff574d9d39dd6ae5997"
)
EXPECTED_UNIVERSE_SHA256 = "5f10ceb149efb59b73e8d8ac7ebef6a2e774f0bc832773910e66416e28f85ba0"
AS_OF = "2026-09-03"


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: bytes) -> Any:
    return json.loads(value.decode("utf-8"))


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
    if sha(canonical(body)) != claim or (expected is not None and claim != expected):
        raise RuntimeError(f"SELFHASH_MISMATCH:{field}")
    return claim


def git_oid(kind: str, payload: bytes) -> str:
    return hashlib.sha1(f"{kind} {len(payload)}\0".encode("ascii") + payload).hexdigest()


def availability(period_end: str, policy: dict[str, Any]) -> tuple[str, int]:
    age = max(0, (date.fromisoformat(AS_OF) - date.fromisoformat(period_end)).days)
    if age <= int(policy["financial_current_max_age_days"]):
        return "CURRENT_COMPARABLE", age
    if age <= int(policy["financial_aging_max_age_days"]):
        return "AGING_BUT_VALID_DISCLOSED", age
    return "HISTORICAL_ONLY", age


def normalise(raw: dict[str, Any]) -> dict[str, Any]:
    start = raw.get("start_or_null", raw.get("period_start"))
    end = raw.get("end", raw.get("period_end"))
    basis = raw.get("preliminary_duration_role", raw.get("period_basis"))
    return {
        "candidate_id": raw.get("candidate_id", raw.get("evidence_id")),
        "candidate_sha256": raw.get("candidate_sha256") or sha(canonical(raw)),
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
        if str(dimension).casefold() == "us-gaap:businessacquisitionaxis" and str(
            member
        ).casefold().endswith(":successormember"):
            return "B", "LIFECYCLE_CONSOLIDATED_SUCCESSOR"
    return None, None


def select_metric(
    metric: str,
    candidates: list[dict[str, Any]],
    semantic: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    concepts = semantic["metrics"][metric]
    accepted_basis = set(policy["duration_basis_policy"][metric])
    basis_order = {
        basis: index for index, basis in enumerate(policy["duration_basis_policy"][metric])
    }
    eligible = []
    historical = []
    rejected = []
    for raw in candidates:
        row = normalise(raw)
        if row["concept"] not in concepts:
            continue
        reasons = []
        if row["namespace"] != "us-gaap":
            reasons.append("NON_US_GAAP_NAMESPACE")
        context_grade, context = context_scope(row)
        if context_grade is None:
            reasons.append("DIMENSIONED_OR_SEGMENT_FACT")
        if row["unit"] != "USD":
            reasons.append("UNIT_NOT_USD")
        if not row["candidate_id"] or not row["candidate_sha256"]:
            reasons.append("RAW_CANDIDATE_IDENTITY_OR_HASH_MISSING")
        if not row["source_artifact_sha256"] or not row["source_snapshot_sha256"]:
            reasons.append("RAW_SOURCE_LINEAGE_MISSING")
        if not row["period_end"]:
            reasons.append("PERIOD_END_MISSING")
        if row["filed"] and row["filed"] > AS_OF:
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
        status, age = availability(str(row["period_end"]), policy)
        candidate = {
            **row,
            "availability_state": status,
            "age_days": age,
            "economic_scope_grade": comparison["grade"],
            "economic_scope": comparison["economic_scope"],
            "context_scope_grade": context_grade,
            "context_scope": context,
        }
        if status == "HISTORICAL_ONLY":
            historical.append(candidate)
        else:
            eligible.append(candidate)

    def rank(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            {"CURRENT_COMPARABLE": 0, "AGING_BUT_VALID_DISCLOSED": 1}[row["availability_state"]],
            -int(str(row["period_end"]).replace("-", "")),
            {"A": 0, "B": 1}.get(str(row["economic_scope_grade"]), 99),
            {"A": 0, "B": 1}.get(str(row["context_scope_grade"]), 99),
            basis_order.get(str(row["period_basis"]), 99),
            -int(str(row.get("filed") or "0000-00-00").replace("-", "")),
            tuple(concepts).index(str(row["concept"])),
            str(row["candidate_id"]),
        )

    eligible.sort(key=rank)
    historical.sort(key=lambda row: (row["age_days"], str(row["candidate_id"])))
    selected = eligible[0] if eligible else None
    status = (
        selected["availability_state"]
        if selected
        else "HISTORICAL_ONLY"
        if historical
        else "ABSENT"
    )
    ranking = (
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
        "metric_id": metric,
        "status": status,
        "counted": int(selected is not None),
        "selected_fact": selected,
        "best_historical_fact": historical[0] if historical else None,
        "eligible_candidate_count": len(eligible),
        "historical_candidate_count": len(historical),
        "rejected_candidates": sorted(
            rejected, key=lambda row: (str(row["candidate_id"]), row["reason_codes"])
        ),
        "deterministic_ranking_inputs": ranking,
        "selection_authority": "RAW_TYPED_FACT_EVIDENCE_ONLY",
        "v1_resolution_receipt_used": False,
        "period_basis_relabelled": False,
        "quarter_from_ytd_subtraction_used": False,
        "unit_conversion_used": False,
        "current_noncurrent_debt_summed": False,
    }
    return {**body, "receipt_sha256": sha(canonical(body))}


def evaluate_case(
    ticker: str,
    candidates: list[dict[str, Any]],
    semantic: dict[str, Any],
    policy: dict[str, Any],
    slots: list[str],
) -> dict[str, Any]:
    receipts = [select_metric(metric, candidates, semantic, policy) for metric in slots]
    resolved = sum(row["counted"] for row in receipts)
    body = {
        "contract_id": "room16.alpha.energy_profile_v3_development_case",
        "contract_version": 3,
        "ticker": ticker,
        "as_of": AS_OF,
        "profile_version": 3,
        "development_status": "CANDIDATE_NOT_FROZEN",
        "provider_call_count": 0,
        "ticker_specific_rules": False,
        "manual_semantic_interventions": 0,
        "selection_authority": "RAW_TYPED_FACT_EVIDENCE_ONLY",
        "v1_resolution_receipt_used": False,
        "resolved_slot_count": resolved,
        "slot_count": len(receipts),
        "coverage_percent": resolved * 100 // len(receipts),
        "current_only_coverage_percent": sum(
            row["status"] == "CURRENT_COMPARABLE" for row in receipts
        )
        * 100
        // len(receipts),
        "aging_slot_count": sum(row["status"] == "AGING_BUT_VALID_DISCLOSED" for row in receipts),
        "slot_receipts": receipts,
    }
    return {**body, "case_sha256": sha(canonical(body))}


def main(path: str) -> None:
    with zipfile.ZipFile(path) as archive:
        names = safe_names(archive)
        manifest = json_bytes(archive.read("MANIFEST.json"))
        verify_selfhash(manifest, "manifest_sha256")
        rows = {row["path"]: row for row in manifest["files"]}
        if manifest["file_count"] != len(rows):
            raise RuntimeError("MANIFEST_COUNT_MISMATCH")
        for name, row in rows.items():
            payload = archive.read(name)
            if len(payload) != row["bytes"] or sha(payload) != row["sha256"]:
                raise RuntimeError(f"PAYLOAD_MISMATCH:{name}")
        checksums = archive.read("CHECKSUMS.sha256").decode("utf-8").splitlines()
        checksum_map = {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in checksums}
        if checksum_map.get("MANIFEST.json") != sha(archive.read("MANIFEST.json")):
            raise RuntimeError("CHECKSUM_MANIFEST_MISMATCH")
        if any(checksum_map.get(name) != row["sha256"] for name, row in rows.items()):
            raise RuntimeError("CHECKSUM_PAYLOAD_MISMATCH")

        r11_manifest = json_bytes(archive.read("r11_binding/R11_MANIFEST.json"))
        verify_selfhash(r11_manifest, "manifest_sha256", EXPECTED_R11_MANIFEST_SHA256)
        r11_selection = json_bytes(archive.read("r11_binding/R11_SELECTION_CONTRACT.json"))
        r11_epoch = json_bytes(archive.read("r11_binding/R11_SELECTED_CASES_SEALED.json"))
        verify_selfhash(r11_selection, "selection_contract_sha256")
        verify_selfhash(r11_epoch, "seal_sha256", EXPECTED_R11_SELECTION_SEAL_SHA256)
        if manifest["r11_input_sha256"] != EXPECTED_R11_SHA256:
            raise RuntimeError("R11_INPUT_BINDING_MISMATCH")

        exposure = json_bytes(archive.read("01_VALIDATION_EPOCH_TRANSITION_AND_EXPOSURE_LOCK.json"))
        taxonomy = json_bytes(archive.read("02_ENERGY_V2_FAILURE_TAXONOMY.json"))
        seal = json_bytes(archive.read("05_ENERGY_V3_CANDIDATE_SEAL.json"))
        eligibility = json_bytes(archive.read("06_CLEAN_VALIDATION_EPOCH2_ELIGIBILITY.json"))
        selection = json_bytes(archive.read("07_EPOCH2_SELECTION_CONTRACT.json"))
        epoch = json_bytes(archive.read("08_EPOCH2_SELECTED_CASES_SEALED.json"))
        verify_selfhash(exposure, "exposure_lock_sha256")
        verify_selfhash(taxonomy, "taxonomy_sha256")
        verify_selfhash(seal, "candidate_seal_sha256")
        verify_selfhash(eligibility, "eligibility_sha256")
        verify_selfhash(selection, "selection_contract_sha256")
        verify_selfhash(epoch, "epoch2_seal_sha256")
        if exposure["r11_exposed_case_count"] != 12 or taxonomy["decision_count"] != 60:
            raise RuntimeError("EXPOSURE_OR_TAXONOMY_COUNT_MISMATCH")
        if (
            eligibility["eligible_count"] < 12
            or selection["universe_sha256"] != EXPECTED_UNIVERSE_SHA256
        ):
            raise RuntimeError("ELIGIBILITY_OR_UNIVERSE_MISMATCH")
        exposed_tickers = {row["ticker"] for row in exposure["cases"]}
        if exposed_tickers & {row["ticker"] for row in eligibility["eligible"]}:
            raise RuntimeError("EXPOSED_IDENTITY_REMAINED_ELIGIBLE")
        ranked = []
        for row in eligibility["eligible"]:
            key = sha(
                seal["candidate_seal_sha256"].encode("ascii")
                + EXPECTED_R11_SELECTION_SEAL_SHA256.encode("ascii")
                + EXPECTED_UNIVERSE_SHA256.encode("ascii")
                + row["canonical_identity_json"].encode("utf-8")
            )
            ranked.append((key, row["canonical_identity_json"], row["ticker"]))
        ranked.sort()
        selected = [row[2] for row in ranked[:12]]
        if selected != [row["ticker"] for row in epoch["selected_cases"]]:
            raise RuntimeError("DETERMINISTIC_SELECTION_MISMATCH")
        if selection["provider_calls_before_epoch2_seal"] != 0:
            raise RuntimeError("PROVIDER_CALL_BEFORE_SEAL")

        semantic = seal["semantic_contract_v3"]
        policy = seal["period_policy_v3"]
        slots = seal["core_subsector_registry_v3"]["slots"]
        case_results = json_bytes(archive.read("10_EPOCH2_CASE_RESULTS.json"))
        result_by_ticker = {row["ticker"]: row for row in case_results["cases"]}
        recomputed = []
        source_hashes = set()
        for case in epoch["selected_cases"]:
            outer_name = f"raw_cases/{case['sequence']:02d}_{case['ticker']}.zip"
            payload = archive.read(outer_name)
            with zipfile.ZipFile(io.BytesIO(payload)) as nested:
                nested_names = safe_names(nested)
                prefix = f"{case['sequence']:02d}_{case['ticker']}/"
                candidate_doc = json_bytes(nested.read(prefix + "21_ENERGY_V3_RAW_CANDIDATES.json"))
                candidates = candidate_doc["candidates"]
                if sha(canonical(candidates)) != candidate_doc["candidate_set_sha256"]:
                    raise RuntimeError(f"CANDIDATE_SET_MISMATCH:{case['ticker']}")
                for row in candidates:
                    if row.get("source_payload_sha256"):
                        source_hashes.add(str(row["source_payload_sha256"]))
                observed_payload_hashes = {
                    sha(nested.read(name))
                    for name in nested_names
                    if "/captures/" in name and "/metadata/" not in name
                }
                inline_hashes = {
                    str(row["source_payload_sha256"])
                    for row in candidates
                    if row.get("source_kind") == "inline_xbrl"
                }
                if not inline_hashes <= observed_payload_hashes:
                    raise RuntimeError(f"INLINE_SOURCE_PAYLOAD_MISSING:{case['ticker']}")
                result = evaluate_case(case["ticker"], candidates, semantic, policy, slots)
                stored = result_by_ticker[case["ticker"]]["v3_result"]
                if result != stored:
                    raise RuntimeError(f"CASE_RECOMPUTE_MISMATCH:{case['ticker']}")
                recomputed.append(result)
        usable = [row["coverage_percent"] for row in recomputed]
        current = [row["current_only_coverage_percent"] for row in recomputed]
        acceptance = json_bytes(archive.read("11_EPOCH2_BATCH_ACCEPTANCE.json"))
        observed_checks = {
            "exactly_12_complete_cases": len(recomputed) == 12,
            "usable_batch_median_at_least_80": statistics.median(usable) >= 80,
            "usable_company_minimum_at_least_60": min(usable) >= 60,
            "current_only_batch_median_at_least_60": statistics.median(current) >= 60,
            "current_only_company_minimum_at_least_40": min(current) >= 40,
            "maximum_aging_slots_per_company_at_most_2": max(
                row["aging_slot_count"] for row in recomputed
            )
            <= 2,
            "historical_only_counts_as_resolved_false": not any(
                receipt["counted"] and receipt["status"] == "HISTORICAL_ONLY"
                for row in recomputed
                for receipt in row["slot_receipts"]
            ),
        }
        if observed_checks != acceptance["checks"]:
            raise RuntimeError("ACCEPTANCE_RECOMPUTE_MISMATCH")
        expected_verdict = (
            "ENERGY_V3_CLEAN_VALIDATION_EPOCH2_PASS_READY_FOR_INDEPENDENT_FREEZE_REVIEW"
            if all(observed_checks.values())
            else "ENERGY_V3_CLEAN_VALIDATION_EPOCH2_FAIL_CANDIDATE_NOT_FREEZE_READY"
        )
        if manifest["verdict"] != expected_verdict or acceptance["verdict"] != expected_verdict:
            raise RuntimeError("VERDICT_MISMATCH")

        no_tuning = json_bytes(archive.read("12_NO_TUNING_NO_REPLACEMENT.json"))
        energy = json_bytes(archive.read("13_ENERGY_V1_V2_NONINTERFERENCE.json"))
        shared = json_bytes(archive.read("14_SHARED_AUTHORITY_NONINTERFERENCE.json"))
        product = json_bytes(archive.read("15_PRODUCT_NONINTERFERENCE.json"))
        regression = json_bytes(archive.read("16_HISTORICAL_REPLAY_AND_FULL_REGRESSION.json"))
        boundary = json_bytes(archive.read("17_BOUNDARY_GATE.json"))
        adversarial = json_bytes(archive.read("18_ADVERSARIAL_R12_TESTS.json"))
        matrix = json_bytes(archive.read("19_R12_ACCEPTANCE_MATRIX.json"))
        if any(
            no_tuning[key]
            for key in (
                "replaced_case_count",
                "semantic_changes_after_seal",
                "threshold_changes_after_seal",
                "source_changes_after_seal",
            )
        ):
            raise RuntimeError("NO_TUNING_RECEIPT_MISMATCH")
        if energy["energy_v1_changed"] or energy["historical_energy_v2_evidence_changed"]:
            raise RuntimeError("ENERGY_NONINTERFERENCE_MISMATCH")
        if shared["shared_authority_changed"] or product["product_changed"]:
            raise RuntimeError("SHARED_OR_PRODUCT_NONINTERFERENCE_MISMATCH")
        if regression["status"] != "PASS" or boundary["status"] != "PASS":
            raise RuntimeError("REGRESSION_OR_BOUNDARY_FAILURE")
        if adversarial["executed"] < 30 or adversarial["passed"] != adversarial["executed"]:
            raise RuntimeError("ADVERSARIAL_FAILURE")
        if matrix["status"] != "PASS" or matrix["failed"] or matrix["pending"]:
            raise RuntimeError("ACCEPTANCE_MATRIX_FAILURE")

        for prefix, expected_commit, expected_tree in (
            ("research", manifest["research_commit"], manifest["research_tree"]),
            ("product", manifest["product_commit"], manifest["product_tree"]),
        ):
            commit = archive.read(f"git_binding/{prefix}/commit.raw")
            tree_name = f"git_binding/{prefix}/tree.{expected_tree}.raw"
            tree = archive.read(tree_name)
            if (
                git_oid("commit", commit) != expected_commit
                or git_oid("tree", tree) != expected_tree
            ):
                raise RuntimeError(f"GIT_OBJECT_BINDING_MISMATCH:{prefix}")
            first_line = commit.decode("utf-8", "replace").splitlines()[0]
            if first_line != f"tree {expected_tree}":
                raise RuntimeError(f"GIT_COMMIT_TREE_MISMATCH:{prefix}")

        result = {
            "status": "PASS",
            "verdict": expected_verdict,
            "outer_entry_count": len(names),
            "manifest_file_count": manifest["file_count"],
            "payload_hash_mismatches": 0,
            "r11_rebound": True,
            "exposed_case_count": len(exposed_tickers),
            "taxonomy_decision_count": taxonomy["decision_count"],
            "eligible_count": eligibility["eligible_count"],
            "selected_tickers": selected,
            "case_results_recomputed": len(recomputed),
            "usable_median": statistics.median(usable),
            "usable_minimum": min(usable),
            "current_only_median": statistics.median(current),
            "current_only_minimum": min(current),
            "maximum_aging_slots": max(row["aging_slot_count"] for row in recomputed),
            "source_payload_hashes_observed": len(source_hashes),
            "adversarial_executed": adversarial["executed"],
            "freeze_authorized": False,
        }
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_energy_v3_r12.py RESULT.zip")
    try:
        main(sys.argv[1])
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        raise SystemExit(1) from exc
